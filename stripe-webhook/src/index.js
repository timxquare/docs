import Stripe from "stripe";

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Temporary diagnostic endpoint — remove after debugging.
    // GET /debug       → tests OAuth token refresh + Gmail profile (no email sent)
    // GET /debug?send=1 → also sends a test email to GMAIL_SENDER_ADDRESS
    if (request.method === "GET" && url.pathname === "/debug") {
      return debugCheck(env, url.searchParams.get("send") === "1");
    }

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

// Temporary diagnostic — reports which step of the Gmail path fails.
// Returns no secrets, only status strings. Remove after debugging.
async function debugCheck(env, doSend) {
  const result = { steps: {}, config: {} };

  // Non-secret config echo to verify the right values are wired up.
  // Client IDs and sender address are not secrets; refresh token/secret
  // are only reported as present/absent + length, never their values.
  result.config.clientId = env.GMAIL_CLIENT_ID || "(missing)";
  result.config.senderAddress = env.GMAIL_SENDER_ADDRESS || "(missing)";
  result.config.clientSecretPresent = env.GMAIL_CLIENT_SECRET
    ? `yes (len ${env.GMAIL_CLIENT_SECRET.length})`
    : "no";
  result.config.refreshTokenPresent = env.GMAIL_REFRESH_TOKEN
    ? `yes (len ${env.GMAIL_REFRESH_TOKEN.length})`
    : "no";
  // One-way hash prefixes — safe to expose, lets us confirm a value
  // actually changed between updates without revealing it.
  result.config.clientSecretFingerprint = await fingerprint(
    env.GMAIL_CLIENT_SECRET
  );
  result.config.refreshTokenFingerprint = await fingerprint(
    env.GMAIL_REFRESH_TOKEN
  );

  let accessToken;
  try {
    accessToken = await getAccessToken(env);
    result.steps.tokenRefresh = "ok";
  } catch (err) {
    result.steps.tokenRefresh = `FAILED: ${err.message}`;
    return jsonResponse(result);
  }

  try {
    const res = await fetch(
      "https://gmail.googleapis.com/gmail/v1/users/me/profile",
      { headers: { Authorization: `Bearer ${accessToken}` } }
    );
    const data = await res.json();
    result.steps.profile = res.ok
      ? `ok: authenticated as ${data.emailAddress}`
      : `FAILED ${res.status}: ${JSON.stringify(data)}`;
  } catch (err) {
    result.steps.profile = `FAILED: ${err.message}`;
  }

  if (doSend) {
    try {
      await sendFounderEmail(env, env.GMAIL_SENDER_ADDRESS, "Debug Test");
      result.steps.testSend = `ok: sent to ${env.GMAIL_SENDER_ADDRESS}`;
    } catch (err) {
      result.steps.testSend = `FAILED: ${err.message}`;
    }
  }

  return jsonResponse(result);
}

async function fingerprint(value) {
  if (!value) return "(missing)";
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(value)
  );
  return [...new Uint8Array(digest)]
    .slice(0, 6)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

function jsonResponse(obj) {
  return new Response(JSON.stringify(obj, null, 2), {
    headers: { "Content-Type": "application/json" },
  });
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

async function sendFounderEmail(env, toEmail, toName) {
  const accessToken = await getAccessToken(env);
  const firstName = toName.split(" ")[0];

  const subject = "Welcome — glad you're here";
  const bodyText = [
    `Hi ${firstName},`,
    ``,
    `I'm Tim, founder of Icemail. I wanted to reach out personally to welcome you.`,
    ``,
    `A few things I'd love to know:`,
    `- What brought you to Icemail?`,
    `- What are you hoping to get done?`,
    `- Is there anything that felt confusing or unclear?`,
    ``,
    `I read every reply. If you run into anything, just hit reply here and it comes straight to me.`,
    ``,
    `Timothy Vadde`,
    `Founder @ Icemail`,
    `icemail.ai`,
  ].join("\n");

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
