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
        // Send both emails in the background so we ACK Stripe immediately.
        // Day 1 fires immediately; Day 2 is scheduled via SendGrid's send_at.
        ctx.waitUntil(
          Promise.all([
            sendDay1Email(env, toEmail, toName).catch((err) =>
              console.error(`Day 1 email failed for ${toEmail}:`, err.message)
            ),
            sendDay2Email(env, toEmail, toName).catch((err) =>
              console.error(`Day 2 email failed for ${toEmail}:`, err.message)
            ),
          ])
        );
      }
    }

    return new Response(JSON.stringify({ received: true }), {
      headers: { "Content-Type": "application/json" },
    });
  },
};

function getFirstName(toName, toEmail) {
  return toName && toName !== toEmail ? toName.split(" ")[0] : "there";
}

async function sendDay1Email(env, toEmail, toName) {
  const firstName = getFirstName(toName, toEmail);

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

async function sendDay2Email(env, toEmail, toName) {
  const firstName = getFirstName(toName, toEmail);

  const subject = "a note before you start sending";
  const bodyText = [
    `Hey ${firstName},`,
    ``,
    `Wanted to flag one thing before you start sending.`,
    ``,
    `The biggest reason cold email infrastructure fails has nothing to do with DKIM, SPF, or your warmup tool. It's volume ramp.`,
    ``,
    `Most people provision 50 mailboxes on Monday and start sending 30 emails per mailbox on Tuesday. Google and Microsoft notice within days, and the domains get burned before they ever had a chance.`,
    ``,
    `What actually works:`,
    ``,
    `• Week 1: warmup only, no real sends`,
    `• Week 2: 5 to 10 real emails per mailbox per day`,
    `• Week 3 onward: add about 5 per day until you hit 30 to 40`,
    ``,
    `If you're using Instantly or Smartlead, set the daily limit inside the campaign, not just inside the warmup tool. The campaign cap is what actually throttles your sends.`,
    ``,
    `One more thing: keep your sending domain separate from your main brand domain. Use a lookalike like trygetdomain.com instead of getdomain.com. You can buy and configure them right inside the icemail dashboard.`,
    ``,
    `Running an agency, or want to skip the ramp entirely? We also do whitelabel setups, pre-warmed mailboxes, and flexible APIs. Reply and I'll send specifics.`,
    ``,
    `Happy to glance at your setup before you start sending. Just reply.`,
    ``,
    `Timothy`,
    ``,
    `P.S. Yes, the irony isn't lost on us. A deliverability email sent through a third-party tool that may or may not have landed in Primary. If this is sitting in Promotions, drag it over and we'll consider it a personal favor.`,
  ].join("\n");

  // Schedule for 24 hours after signup — Gmail fallback can't schedule so
  // we don't fall back here; a missed Day 2 is better than a double-send.
  const sendAt = Math.floor(Date.now() / 1000) + 86400;
  await sendViaSendGrid(env, toEmail, toName, subject, bodyText, sendAt);
}

async function sendViaSendGrid(env, toEmail, toName, subject, bodyText, sendAt) {
  const payload = {
    personalizations: [{ to: [{ email: toEmail, name: toName }] }],
    from: { email: "tim@icemail.ai", name: "Tim from Icemail" },
    reply_to: { email: "tim@icemail.ai", name: "Tim from Icemail" },
    subject,
    content: [{ type: "text/plain", value: bodyText }],
    ...(sendAt ? { send_at: sendAt } : {}),
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
    `From: Tim from Icemail <${env.GMAIL_SENDER_ADDRESS}>`,
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
