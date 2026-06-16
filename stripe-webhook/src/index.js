import Stripe from "stripe";

export default {
  async fetch(request, env, ctx) {
    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405 });
    }

    const stripe = new Stripe(env.STRIPE_SECRET_KEY, {
      httpClient: Stripe.createFetchHttpClient(),
    });
    const cryptoProvider = Stripe.createSubtleCryptoProvider();

    const sig = request.headers.get("stripe-signature");
    const body = await request.text();

    let event;
    try {
      event = await stripe.webhooks.constructEventAsync(
        body,
        sig,
        env.STRIPE_WEBHOOK_SECRET,
        undefined,
        cryptoProvider
      );
    } catch (err) {
      console.error("Signature verification failed:", err.message);
      return new Response(`Webhook Error: ${err.message}`, { status: 400 });
    }

    if (event.type === "customer.created") {
      const customer = event.data.object;
      const toEmail = customer.email;
      const toName = customer.name || toEmail;

      if (toEmail) {
        // Send in the background so we ACK Stripe immediately
        ctx.waitUntil(
          sendFounderEmail(env, toEmail, toName).catch((err) =>
            console.error(`Failed to email ${toEmail}:`, err.message)
          )
        );
      }
    }

    return new Response(JSON.stringify({ received: true }), {
      headers: { "Content-Type": "application/json" },
    });
  },
};

async function sendFounderEmail(env, toEmail, toName) {
  const firstName = toName && toName !== toEmail
    ? toName.split(" ")[0]
    : "there";

  const subject = "you're in";
  const bodyText = [
    `Hey ${firstName},`,
    ``,
    `Timothy here, founder of icemail. Thanks for signing up.`,
    ``,
    `You now have access to Google Workspace and Microsoft 365 mailboxes with DKIM, SPF, and DMARC already configured. No DNS work on your end.`,
    ``,
    `Three steps to get your first batch sending:`,
    ``,
    `1. Add a domain (or a few) in the dashboard`,
    `2. Pick how many mailboxes per domain. 2 or 3 is a good starting point.`,
    `3. Hit provision. The rest runs in the background.`,
    ``,
    `When they're ready, plug them straight into Instantly, Smartlead, or lemlist from the integrations tab.`,
    ``,
    `If anything looks off, reply to this email. It comes to me directly.`,
    ``,
    `Timothy`,
    `Founder, icemail(.)ai`,
    ``,
    `P.S. This was sent through a third-party tool, not icemail itself. So don't judge us if it landed somewhere other than Primary. Deliverability is humbling, even for the people who do it for a living.`,
  ].join("\n");

  try {
    await sendViaSendGrid(env, toEmail, toName, subject, bodyText);
  } catch (sgErr) {
    console.error("SendGrid failed, falling back to Gmail:", sgErr.message);
    await sendViaGmail(env, toEmail, toName, subject, bodyText);
  }
}

async function sendViaSendGrid(env, toEmail, toName, subject, bodyText) {
  const payload = {
    personalizations: [{ to: [{ email: toEmail, name: toName }] }],
    from: { email: "tim@icemail.ai", name: "Timothy Vadde" },
    reply_to: { email: "tim@icemail.ai", name: "Timothy Vadde" },
    subject,
    content: [{ type: "text/plain", value: bodyText }],
  };

  const res = await fetch("https://api.sendgrid.com/v3/mail/send", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.SENDGRID_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(`SendGrid send failed: ${res.status} ${await res.text()}`);
  }
}

async function sendViaGmail(env, toEmail, toName, subject, bodyText) {
  const accessToken = await getAccessToken(env);

  const rawMessage = [
    `From: Timothy Vadde <${env.GMAIL_SENDER_ADDRESS}>`,
    `To: ${toEmail}`,
    `Subject: ${subject}`,
    `Content-Type: text/plain; charset=utf-8`,
    ``,
    bodyText,
  ].join("\r\n");

  const res = await fetch(
    "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ raw: base64url(rawMessage) }),
    }
  );

  if (!res.ok) {
    throw new Error(`Gmail send failed: ${res.status} ${await res.text()}`);
  }
}

async function getAccessToken(env) {
  const res = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_id: env.GMAIL_CLIENT_ID,
      client_secret: env.GMAIL_CLIENT_SECRET,
      refresh_token: env.GMAIL_REFRESH_TOKEN,
      grant_type: "refresh_token",
    }),
  });

  if (!res.ok) {
    throw new Error(`Token refresh failed: ${res.status} ${await res.text()}`);
  }
  const data = await res.json();
  return data.access_token;
}

// Base64url-encode a UTF-8 string (Gmail API expects RFC 4648 base64url)
function base64url(str) {
  const bytes = new TextEncoder().encode(str);
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary)
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}
