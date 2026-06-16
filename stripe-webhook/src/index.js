import Stripe from "stripe";
import { SIGNUP_FLOW_SEQUENCE } from "./sequences.js";

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
        ctx.waitUntil(handleNewCustomer(env, toEmail, toName));
      }
    }

    return new Response(JSON.stringify({ received: true }), {
      headers: { "Content-Type": "application/json" },
    });
  },
};

async function handleNewCustomer(env, toEmail, toName) {
  // Deduplicate: skip if this email has already been through the signup flow
  const existing = await env.SIGNUP_LOG.get(toEmail);
  if (existing) {
    console.log(`Signup flow already sent to ${toEmail}, skipping.`);
    return;
  }

  // Log before sending so a retry can't double-send
  await env.SIGNUP_LOG.put(
    toEmail,
    JSON.stringify({ signedUpAt: new Date().toISOString() })
  );

  const firstName = getFirstName(toName, toEmail);

  await Promise.all(
    SIGNUP_FLOW_SEQUENCE.map(({ day, subject, getBody }) => {
      const bodyText = getBody(firstName);
      const sendAt = day === 1 ? null : nextWeekdaySendAt(day);
      return sendEmail(env, toEmail, toName, subject, bodyText, sendAt).catch(
        (err) =>
          console.error(`Day ${day} email failed for ${toEmail}:`, err.message)
      );
    })
  );
}

// Returns a Unix timestamp for 9 AM ET on the next weekday >= daysFromNow.
// Handles EST/EDT automatically via Intl.
function nextWeekdaySendAt(daysFromNow) {
  const MS_PER_DAY = 86400 * 1000;
  const SEND_HOUR_ET = 9;

  let d = new Date(Date.now() + daysFromNow * MS_PER_DAY);

  while (true) {
    const dow = d.toLocaleDateString("en-US", {
      timeZone: "America/New_York",
      weekday: "short",
    });
    if (dow !== "Sat" && dow !== "Sun") break;
    d = new Date(d.getTime() + MS_PER_DAY);
  }

  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(d);
  const year = parts.find((p) => p.type === "year").value;
  const month = parts.find((p) => p.type === "month").value;
  const day = parts.find((p) => p.type === "day").value;
  const dateStr = `${year}-${month}-${day}`;

  const noonUTC = new Date(`${dateStr}T12:00:00Z`);
  const etHourAtNoon = parseInt(
    new Intl.DateTimeFormat("en-US", {
      timeZone: "America/New_York",
      hour: "2-digit",
      hour12: false,
    }).format(noonUTC)
  );
  const utcOffsetHours = 12 - etHourAtNoon; // 5 for EST, 4 for EDT

  const sendUTCHour = SEND_HOUR_ET + utcOffsetHours;
  return Math.floor(
    new Date(
      `${dateStr}T${String(sendUTCHour).padStart(2, "0")}:00:00Z`
    ).getTime() / 1000
  );
}

function getFirstName(toName, toEmail) {
  return toName && toName !== toEmail ? toName.split(" ")[0] : "there";
}

async function sendEmail(env, toEmail, toName, subject, bodyText, sendAt) {
  try {
    await sendViaSendGrid(env, toEmail, toName, subject, bodyText, sendAt);
  } catch (sgErr) {
    // Gmail fallback only for immediate sends — it can't schedule
    if (sendAt) throw sgErr;
    console.error("SendGrid failed, falling back to Gmail:", sgErr.message);
    await sendViaGmail(env, toEmail, toName, subject, bodyText);
  }
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
