import Stripe from "stripe";
import { SIGNUP_FLOW_SEQUENCE } from "./sequences.js";
import { MARKETING_SEQUENCE } from "./marketing-sequence.js";
import { SEED_EMAILS } from "./seed-emails.js";

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // One-time seed endpoint: populates KV with pre-existing Stripe customers.
    // Visit /seed?token=<SEED_TOKEN> in browser once, then remove this block.
    if (url.pathname === "/seed") {
      if (url.searchParams.get("token") !== env.SEED_TOKEN) {
        return new Response("Unauthorized", { status: 401 });
      }
      const ts = new Date().toISOString();
      const existing = await env.SIGNUP_LOG.get("__seeded__");
      if (existing) {
        return new Response("Already seeded. Nothing to do.", { status: 200 });
      }
      for (let i = 0; i < SEED_EMAILS.length; i += 100) {
        await Promise.all(
          SEED_EMAILS.slice(i, i + 100).map((email) =>
            env.SIGNUP_LOG.put(
              email,
              JSON.stringify({ signedUpAt: "pre-existing", importedAt: ts })
            )
          )
        );
      }
      await env.SIGNUP_LOG.put("__seeded__", ts);
      return new Response(
        `Seeded ${SEED_EMAILS.length} emails into SIGNUP_LOG.`,
        { status: 200 }
      );
    }

    // One-time backfill: triggers Day 2+ sequences for all Stripe customers
    // created in the last 30 days who haven't been sequenced yet.
    // Visit /backfill?token=<SEED_TOKEN> in browser once.
    if (url.pathname === "/backfill") {
      if (url.searchParams.get("token") !== env.SEED_TOKEN) {
        return new Response("Unauthorized", { status: 401 });
      }
      ctx.waitUntil(runBackfill(env));
      return new Response(
        "Backfill started in background. Check Trigger.dev dashboard for scheduled runs.",
        { status: 200 }
      );
    }


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

// Fetches all Stripe customers created in the last 30 days and schedules
// Day 2, Day 5, and all 9 marketing emails for any not yet sequenced.
async function runBackfill(env) {
  const since = Math.floor(Date.now() / 1000) - 30 * 86400; // 30 days ago
  let startingAfter = null;
  let queued = 0;
  let skipped = 0;

  while (true) {
    const params = new URLSearchParams({
      limit: "100",
      "created[gte]": String(since),
    });
    if (startingAfter) params.set("starting_after", startingAfter);

    const res = await fetch(`https://api.stripe.com/v1/customers?${params}`, {
      headers: { Authorization: `Bearer ${env.STRIPE_SECRET_KEY}` },
    });
    if (!res.ok) throw new Error(`Stripe list failed: ${res.status} ${await res.text()}`);

    const data = await res.json();

    for (const customer of data.data) {
      const toEmail = customer.email;
      const toName = customer.name || toEmail;
      if (!toEmail) continue;

      const existing = await env.SIGNUP_LOG.get(toEmail);
      // Only backfill those seeded as "pre-existing" (no sequence triggered yet)
      if (existing) {
        const parsed = JSON.parse(existing);
        if (parsed.sequencedAt || parsed.signedUpAt !== "pre-existing") {
          skipped++;
          continue;
        }
      }

      // Days since this customer signed up on Stripe
      const daysSinceSignup = (Date.now() / 1000 - customer.created) / 86400;

      // Schedule signup flow emails (Day 2, 5) that haven't fired yet
      const scheduledSequence = SIGNUP_FLOW_SEQUENCE.filter((s) => s.day !== 1);
      // Schedule marketing emails that haven't fired yet
      // daysFromNow = target day - days already elapsed (min 1 so it's always future)
      const daysElapsed = Math.floor(daysSinceSignup);

      await Promise.all([
        // Signup flow: only emails whose day hasn't passed yet
        ...scheduledSequence
          .filter(({ day }) => daysElapsed < day)
          .map(({ day }) => {
            const daysFromNow = Math.max(1, day - daysElapsed);
            return triggerScheduledEmail(env, toEmail, toName, day, daysFromNow).catch((e) =>
              console.error(`Backfill signup day ${day} failed for ${toEmail}:`, e.message)
            );
          }),
        // Marketing emails: only ones whose day hasn't passed yet
        ...MARKETING_SEQUENCE
          .filter(({ day }) => daysElapsed < day)
          .map(({ id, day }) => {
            const daysFromNow = Math.max(1, day - daysElapsed);
            return triggerMarketingEmail(env, toEmail, toName, id, day, daysFromNow).catch((e) =>
              console.error(`Backfill marketing ${id} failed for ${toEmail}:`, e.message)
            );
          }),
      ]);

      // Mark as sequenced so a re-run won't double-send
      await env.SIGNUP_LOG.put(
        toEmail,
        JSON.stringify({
          name: toName,
          email: toEmail,
          signedUpAt: "pre-existing",
          sequencedAt: new Date().toISOString(),
        })
      );
      queued++;
    }

    if (!data.has_more) break;
    startingAfter = data.data[data.data.length - 1].id;
  }

  console.log(`Backfill complete: ${queued} sequenced, ${skipped} skipped.`);
}

async function handleNewCustomer(env, toEmail, toName) {
  const existing = await env.SIGNUP_LOG.get(toEmail);
  if (existing) {
    console.log(`Signup flow already sent to ${toEmail}, skipping.`);
    return;
  }

  await env.SIGNUP_LOG.put(
    toEmail,
    JSON.stringify({ name: toName, email: toEmail, signedUpAt: new Date().toISOString() })
  );

  const firstName = getFirstName(toName, toEmail);

  // Day 1: send immediately via SendGrid (with Gmail fallback)
  const day1 = SIGNUP_FLOW_SEQUENCE.find((s) => s.day === 1);
  await sendDay1(env, toEmail, toName, day1.subject, day1.getBody(firstName)).catch(
    (err) => console.error(`Day 1 email failed for ${toEmail}:`, err.message)
  );

  // Signup flow Day 2 + Day 5: Trigger.dev, random weekday time
  const scheduledSignup = SIGNUP_FLOW_SEQUENCE.filter((s) => s.day !== 1);
  await Promise.all(
    scheduledSignup.map(({ day }) =>
      triggerScheduledEmail(env, toEmail, toName, day).catch((err) =>
        console.error(`Signup day ${day} trigger failed for ${toEmail}:`, err.message)
      )
    )
  );

  // Marketing sequence: 9 emails, one per week starting at Day 12
  await Promise.all(
    MARKETING_SEQUENCE.map(({ id, day }) =>
      triggerMarketingEmail(env, toEmail, toName, id, day).catch((err) =>
        console.error(`Marketing email ${id} trigger failed for ${toEmail}:`, err.message)
      )
    )
  );
}

// daysFromNow defaults to day — pass a smaller value for backfill
async function triggerScheduledEmail(env, toEmail, toName, day, daysFromNow = day) {
  const runAt = nextWeekdaySendAt(daysFromNow);
  const res = await fetch(
    "https://api.trigger.dev/api/v1/tasks/send-signup-email/trigger",
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.TRIGGER_SECRET_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        payload: { toEmail, toName, day },
        options: { delay: runAt },
      }),
    }
  );
  if (!res.ok) {
    throw new Error(`Trigger.dev failed: ${res.status} ${await res.text()}`);
  }
}

// daysFromNow defaults to day — pass a smaller value for backfill
async function triggerMarketingEmail(env, toEmail, toName, emailId, day, daysFromNow = day) {
  const runAt = nextWeekdaySendAt(daysFromNow);
  const res = await fetch(
    "https://api.trigger.dev/api/v1/tasks/send-marketing-email/trigger",
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.TRIGGER_SECRET_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        payload: { toEmail, toName, emailId },
        options: { delay: runAt },
      }),
    }
  );
  if (!res.ok) {
    throw new Error(`Trigger.dev failed: ${res.status} ${await res.text()}`);
  }
}

// Returns an ISO timestamp for a random time between 7am and 9pm ET
// on the next weekday >= daysFromNow. Handles EST/EDT automatically.
function nextWeekdaySendAt(daysFromNow) {
  const MS_PER_DAY = 86400 * 1000;

  // Random send time: hour 7–20 (so latest dispatch starts at 8pm), random minute
  const sendHourET = Math.floor(Math.random() * 14) + 7; // 7..20
  const sendMinute = Math.floor(Math.random() * 60);

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
  const utcOffsetHours = 12 - etHourAtNoon; // 5 EST, 4 EDT

  const sendUTCHour = sendHourET + utcOffsetHours;
  return new Date(
    `${dateStr}T${String(sendUTCHour).padStart(2, "0")}:${String(sendMinute).padStart(2, "0")}:00Z`
  ).toISOString();
}

function getFirstName(toName, toEmail) {
  return toName && toName !== toEmail ? toName.split(" ")[0] : "there";
}

async function sendDay1(env, toEmail, toName, subject, bodyText) {
  try {
    await sendViaSendGrid(env, toEmail, toName, subject, bodyText);
  } catch (sgErr) {
    console.error("SendGrid failed, falling back to Gmail:", sgErr.message);
    await sendViaGmail(env, toEmail, toName, subject, bodyText);
  }
}

async function sendViaSendGrid(env, toEmail, toName, subject, bodyText) {
  const res = await fetch("https://api.sendgrid.com/v3/mail/send", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.SENDGRID_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      personalizations: [{ to: [{ email: toEmail, name: toName }] }],
      from: { email: "tim@icemail.ai", name: "Tim from Icemail" },
      reply_to: { email: "tim@icemail.ai", name: "Tim from Icemail" },
      subject,
      content: [{ type: "text/plain", value: bodyText }],
    }),
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
