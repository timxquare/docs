import Stripe from "stripe";
import { SIGNUP_FLOW_SEQUENCE } from "./sequences.js";
import { MARKETING_SEQUENCE } from "./marketing-sequence.js";
import { SEED_EMAILS } from "./seed-emails.js";

const LOGO_SVG = `<svg width="160" height="24" viewBox="0 0 160 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M7.95343 21.1394C4.89586 21.1304 2.25471 19.458 0.987296 16.2895C-0.280118 13.121 0.108924 9.16314 1.74363 5.61504C4.8012 5.62409 7.44235 7.29648 8.70976 10.465C9.97718 13.6335 9.58814 17.5913 7.95343 21.1394Z" fill="white"/><path d="M7.95343 21.1394C4.89586 21.1304 2.25471 19.458 0.987296 16.2895C-0.280118 13.121 0.108924 9.16314 1.74363 5.61504C4.8012 5.62409 7.44235 7.29648 8.70976 10.465C9.97718 13.6335 9.58814 17.5913 7.95343 21.1394Z" fill="url(#a)"/><path d="M7.95343 21.1394C4.89586 21.1304 2.25471 19.458 0.987296 16.2895C-0.280118 13.121 0.108924 9.16314 1.74363 5.61504C4.8012 5.62409 7.44235 7.29648 8.70976 10.465C9.97718 13.6335 9.58814 17.5913 7.95343 21.1394Z" fill="black" fill-opacity="0.5" style="mix-blend-mode:hard-light"/><path d="M7.31038 21.2574C11.3543 20.2215 14.8836 17.3754 16.6285 13.2361C18.3735 9.09671 17.9448 4.58749 15.8598 0.976291C11.8159 2.01214 8.2866 4.85826 6.54167 8.99762C4.79674 13.137 5.2254 17.6462 7.31038 21.2574Z" fill="white"/><path d="M7.31038 21.2574C11.3543 20.2215 14.8836 17.3754 16.6285 13.2361C18.3735 9.09671 17.9448 4.58749 15.8598 0.976291C11.8159 2.01214 8.2866 4.85826 6.54167 8.99762C4.79674 13.137 5.2254 17.6462 7.31038 21.2574Z" fill="url(#b)"/><path d="M7.23368 21.2069C9.78906 23.2373 13.2102 23.9506 16.5772 22.8141C19.9441 21.6775 22.5058 18.9445 23.7304 15.6382C21.175 13.6078 17.7538 12.8944 14.3869 14.031C11.0199 15.1676 8.45822 17.9006 7.23368 21.2069Z" fill="white"/><path d="M7.23368 21.2069C9.78906 23.2373 13.2102 23.9506 16.5772 22.8141C19.9441 21.6775 22.5058 18.9445 23.7304 15.6382C21.175 13.6078 17.7538 12.8944 14.3869 14.031C11.0199 15.1676 8.45822 17.9006 7.23368 21.2069Z" fill="url(#c)"/><path d="M34.2124 19V5.4H39.4924L41.6924 12.2L42.3724 14.74L43.0524 12.2L45.2524 5.4H50.4124V19H46.3324L46.5924 9.98L45.5324 13.68L43.7924 19H40.8324L39.0524 13.6L38.0324 10.02L38.2924 19H34.2124ZM52.4155 7.3V4.6H56.2955V7.3H52.4155ZM52.4155 19V8.14H56.2955V19H52.4155ZM58.1038 19V8.14H61.9838V9.58C62.6638 8.34 63.7438 7.76 65.0038 7.76C66.9638 7.76 68.6238 8.98 68.6238 11.78V19H64.7438V12.56C64.7438 11.34 64.3038 10.86 63.4838 10.86C62.6038 10.86 61.9838 11.58 61.9838 12.88V19H58.1038ZM70.9327 15.22V11.06H69.7327V8.14H70.9327V5.62H74.8127V8.14H76.9327V11.06H74.8127V14.6C74.8127 15.5 75.0327 16.06 76.2127 16.06H76.9327V19C76.4927 19.2 75.6727 19.38 74.6527 19.38C72.1527 19.38 70.9327 17.88 70.9327 15.22Z" fill="#001E13"/><path d="M87.232 10.519C87.232 13.687 94.1125 11.2285 94.1125 15.832C94.1125 17.9935 92.3635 19.198 89.971 19.198C87.562 19.198 85.912 18.0925 85.417 15.832H87.001C87.364 17.1685 88.3705 17.8945 89.9875 17.8945C91.6705 17.8945 92.5615 17.152 92.5615 16.03C92.5615 12.598 85.681 15.1555 85.681 10.618C85.681 9.001 87.034 7.582 89.509 7.582C91.6705 7.582 93.403 8.6215 93.8155 11.014H92.215C91.8685 9.529 90.9115 8.8855 89.476 8.8855C88.057 8.8855 87.232 9.529 87.232 10.519ZM96.2499 16.4755V11.3935H95.0289V10.2385H96.2499V8.2255H97.7019V10.2385H99.6324V11.3935H97.7019V16.4755C97.7019 17.5315 98.0154 18.0265 99.3024 18.0265H99.5994V19.066C99.4344 19.1485 99.0714 19.198 98.6589 19.198C97.0254 19.198 96.2499 18.3235 96.2499 16.4755ZM102.516 13.093H101.064C101.345 11.1625 102.615 10.024 104.76 10.024C107.103 10.024 108.242 11.3935 108.242 13.4395V16.888C108.242 17.8945 108.324 18.5215 108.555 19H107.021C106.856 18.6535 106.806 18.142 106.79 17.614C106.047 18.7195 104.859 19.198 103.803 19.198C101.988 19.198 100.767 18.3565 100.767 16.69C100.767 15.4855 101.427 14.611 102.714 14.182C103.902 13.786 105.107 13.687 106.79 13.6705V13.4725C106.79 12.0535 106.13 11.278 104.628 11.278C103.374 11.278 102.698 11.971 102.516 13.093ZM102.252 16.657C102.252 17.4655 102.929 17.944 103.952 17.944C105.569 17.944 106.79 16.6735 106.79 15.172V14.7595C103.061 14.7925 102.252 15.5845 102.252 16.657ZM110.787 19V10.2385H112.239V11.5915C112.833 10.519 113.774 10.024 114.83 10.024C115.176 10.024 115.49 10.1065 115.655 10.2385V11.542C115.407 11.4595 115.094 11.4265 114.747 11.4265C112.998 11.4265 112.239 12.5155 112.239 14.0995V19H110.787ZM117.305 16.4755V11.3935H116.084V10.2385H117.305V8.2255H118.757V10.2385H120.688V11.3935H118.757V16.4755C118.757 17.5315 119.071 18.0265 120.358 18.0265H120.655V19.066C120.49 19.1485 120.127 19.198 119.714 19.198C118.081 19.198 117.305 18.3235 117.305 16.4755ZM129.809 16.1455C129.33 18.1915 127.862 19.198 125.865 19.198C123.324 19.198 121.79 17.482 121.79 14.6275C121.79 11.6575 123.324 10.024 125.783 10.024C128.258 10.024 129.743 11.7235 129.743 14.512V14.875H123.275C123.357 16.8385 124.281 17.944 125.865 17.944C127.103 17.944 127.977 17.35 128.291 16.1455H129.809ZM125.783 11.278C124.38 11.278 123.539 12.1525 123.324 13.786H128.225C128.027 12.169 127.152 11.278 125.783 11.278ZM131.843 19V10.2385H133.295V11.5915C133.889 10.519 134.829 10.024 135.885 10.024C136.232 10.024 136.545 10.1065 136.71 10.2385V11.542C136.463 11.4595 136.149 11.4265 135.803 11.4265C134.054 11.4265 133.295 12.5155 133.295 14.0995V19H131.843ZM141.763 19V7.78H143.281V13.192L148.413 7.78H150.327L145.047 13.291L150.459 19H148.413L143.281 13.621V19H141.763ZM152.06 9.067V7.12H153.512V9.067H152.06ZM152.06 19V10.2385H153.512V19H152.06ZM156.178 16.4755V11.3935H154.957V10.2385H156.178V8.2255H157.63V10.2385H159.56V11.3935H157.63V16.4755C157.63 17.5315 157.943 18.0265 159.23 18.0265H159.527V19.066C159.362 19.1485 158.999 19.198 158.587 19.198C156.953 19.198 156.178 18.3235 156.178 16.4755Z" fill="#001E13"/><defs><radialGradient id="a" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(-3.005 15.023) rotate(-10.029) scale(17.957 17.784)"><stop stop-color="#00B0BB"/><stop offset="1" stop-color="#00DB65"/></radialGradient><radialGradient id="b" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(8.114 20.882) rotate(-75.754) scale(21.625 23.777)"><stop stop-color="#00BBBB"/><stop offset=".713" stop-color="#00DB65"/></radialGradient><radialGradient id="c" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(7.845 21.518) rotate(-20.353) scale(18.56 17.32)"><stop stop-color="#00B0BB"/><stop offset="1" stop-color="#00DB65"/></radialGradient></defs></svg>`;

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Serve the Icemail logo for use in HTML emails
    if (url.pathname === "/logo.svg") {
      return new Response(LOGO_SVG, {
        headers: {
          "Content-Type": "image/svg+xml",
          "Cache-Control": "public, max-age=86400",
          "Access-Control-Allow-Origin": "*",
        },
      });
    }

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

    // Test endpoint: send one marketing email immediately (no scheduling).
    // Usage: /test-marketing-email?token=<SEED_TOKEN>&to=email@example.com&name=First+Last&emailId=prewarmed-01
    if (url.pathname === "/test-marketing-email") {
      if (url.searchParams.get("token") !== env.SEED_TOKEN) {
        return new Response("Unauthorized", { status: 401 });
      }
      const toEmail = url.searchParams.get("to");
      if (!toEmail) return new Response("Missing ?to= param", { status: 400 });
      const toName = url.searchParams.get("name") || toEmail;
      const emailId = url.searchParams.get("emailId") || MARKETING_SEQUENCE[0].id;

      const email = MARKETING_SEQUENCE.find((e) => e.id === emailId);
      if (!email) return new Response(`Unknown emailId: ${emailId}`, { status: 400 });

      const firstName = toName && toName !== toEmail ? toName.split(" ")[0] : "there";
      const logoUrl = `${new URL(request.url).origin}/logo.svg`;
      const html = email.html
        .replace(/\{\{firstName\}\}/g, firstName)
        .replace(/\{\{logoUrl\}\}/g, logoUrl);

      const sgRes = await fetch("https://api.sendgrid.com/v3/mail/send", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${env.SENDGRID_API_KEY}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          personalizations: [{ to: [{ email: toEmail, name: toName }] }],
          from: { email: "tim@icemail.ai", name: "Timothy" },
          reply_to: { email: "tim@icemail.ai", name: "Timothy" },
          subject: email.subject,
          content: [{ type: "text/html", value: html }],
        }),
      });

      if (!sgRes.ok) {
        const err = await sgRes.text();
        return new Response(`SendGrid error: ${sgRes.status} ${err}`, { status: 500 });
      }
      return new Response(`Sent "${email.subject}" (${emailId}) to ${toEmail}`, { status: 200 });
    }

    // Test endpoint: verify Trigger.dev connection by firing send-signup-email immediately.
    // Usage: /test-trigger?token=<SEED_TOKEN>&to=email@example.com&name=First+Last
    if (url.pathname === "/test-trigger") {
      if (url.searchParams.get("token") !== env.SEED_TOKEN) {
        return new Response("Unauthorized", { status: 401 });
      }
      const toEmail = url.searchParams.get("to");
      if (!toEmail) return new Response("Missing ?to= param", { status: 400 });
      const toName = url.searchParams.get("name") || toEmail;

      const trigRes = await fetch(
        "https://api.trigger.dev/api/v1/tasks/send-signup-email/trigger",
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${env.TRIGGER_SECRET_KEY}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            payload: { toEmail, toName, day: 2 },
            // No delay — runs immediately so you can verify in Trigger.dev dashboard
          }),
        }
      );
      const trigBody = await trigRes.text();
      if (!trigRes.ok) {
        return new Response(`Trigger.dev error ${trigRes.status}: ${trigBody}`, { status: 500 });
      }
      return new Response(`Trigger.dev OK: ${trigBody}`, { status: 200 });
    }

    // Internal endpoint called by Trigger.dev tasks when a scheduled send fires.
    // Trigger.dev is only the scheduler — all email logic runs here in Cloudflare.
    // Auth: Bearer token in Authorization header must match env.SEED_TOKEN.
    if (url.pathname === "/send-email" && request.method === "POST") {
      const auth = request.headers.get("Authorization");
      if (auth !== `Bearer ${env.SEED_TOKEN}`) {
        return new Response("Unauthorized", { status: 401 });
      }
      const { type, toEmail, toName, day, emailId } = await request.json();
      const firstName = getFirstName(toName, toEmail);

      if (type === "signup") {
        const sequence = SIGNUP_FLOW_SEQUENCE.find((s) => s.day === day);
        if (!sequence) return new Response(`No sequence for day ${day}`, { status: 400 });
        await sendViaSendGrid(env, toEmail, toName, sequence.subject, sequence.getBody(firstName));
        return new Response(JSON.stringify({ sent: true }), { headers: { "Content-Type": "application/json" } });
      }

      if (type === "marketing") {
        const email = MARKETING_SEQUENCE.find((e) => e.id === emailId);
        if (!email) return new Response(`Unknown emailId: ${emailId}`, { status: 400 });
        const logoUrl = `${new URL(request.url).origin}/logo.svg`;
        const html = email.html
          .replace(/\{\{firstName\}\}/g, firstName)
          .replace(/\{\{logoUrl\}\}/g, logoUrl);
        const sgRes = await fetch("https://api.sendgrid.com/v3/mail/send", {
          method: "POST",
          headers: {
            Authorization: `Bearer ${env.SENDGRID_API_KEY}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            personalizations: [{ to: [{ email: toEmail, name: toName }] }],
            from: { email: "tim@icemail.ai", name: "Timothy" },
            reply_to: { email: "tim@icemail.ai", name: "Timothy" },
            subject: email.subject,
            content: [{ type: "text/html", value: html }],
          }),
        });
        if (!sgRes.ok) throw new Error(`SendGrid failed: ${sgRes.status} ${await sgRes.text()}`);
        return new Response(JSON.stringify({ sent: true }), { headers: { "Content-Type": "application/json" } });
      }

      return new Response("Unknown type", { status: 400 });
    }

    const stripe = new Stripe(env.STRIPE_SECRET_KEY, { apiVersion: "2023-10-16" });
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

      // Start full sequence from today: Day 2, Day 5, and all 9 marketing emails
      const scheduledSequence = SIGNUP_FLOW_SEQUENCE.filter((s) => s.day !== 1);

      await Promise.all([
        ...scheduledSequence.map(({ day }) =>
          triggerScheduledEmail(env, toEmail, toName, day).catch((e) =>
            console.error(`Backfill signup day ${day} failed for ${toEmail}:`, e.message)
          )
        ),
        ...MARKETING_SEQUENCE.map(({ id, day }) =>
          triggerMarketingEmail(env, toEmail, toName, id, day).catch((e) =>
            console.error(`Backfill marketing ${id} failed for ${toEmail}:`, e.message)
          )
        ),
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
// Trigger.dev is only the scheduler; actual sending happens via /send-email on this Worker.
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
        payload: { toEmail, toName, day, workerUrl: env.WORKER_URL },
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
        payload: { toEmail, toName, emailId, workerUrl: env.WORKER_URL },
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
