#!/usr/bin/env node
/**
 * One-time backfill: load every existing Stripe customer and their payment
 * history into Customer.io, so the Paid / Churned / Free Trial segments are
 * correct from day one (before the live webhook starts adding new events).
 *
 * It pulls straight from Stripe (no data file, always fresh) and writes to the
 * Customer.io Track API using the same identity + `payment` event the live
 * worker uses. Idempotent: identify is an upsert and re-sent payment events at
 * the same timestamp de-duplicate, so it is safe to re-run.
 *
 * Requires Node 18+ (global fetch).
 *
 * Usage:
 *   STRIPE_SECRET_KEY=sk_live_... \
 *   CIO_SITE_ID=... CIO_TRACK_API_KEY=... [CIO_REGION=us] \
 *   node backfill-customerio.mjs [--dry-run]
 *
 * Only these four fields are written per profile: first name, last name,
 * email, signup date (Stripe customer `created`). The `payment` event carries
 * just its timestamp — it exists to drive segmentation, not to store data.
 */

const DRY_RUN = process.argv.includes("--dry-run");
const STRIPE_KEY = process.env.STRIPE_SECRET_KEY;
const CIO_SITE_ID = process.env.CIO_SITE_ID;
const CIO_TRACK_API_KEY = process.env.CIO_TRACK_API_KEY;
const CIO_REGION = (process.env.CIO_REGION || "us").toLowerCase();
const CONCURRENCY = 8;

if (!STRIPE_KEY || (!DRY_RUN && (!CIO_SITE_ID || !CIO_TRACK_API_KEY))) {
  console.error(
    "Missing env vars. Required: STRIPE_SECRET_KEY, CIO_SITE_ID, CIO_TRACK_API_KEY (CIO_* optional with --dry-run)."
  );
  process.exit(1);
}

const CIO_BASE =
  CIO_REGION === "eu" ? "https://track-eu.customer.io" : "https://track.customer.io";
const CIO_AUTH =
  "Basic " + Buffer.from(`${CIO_SITE_ID}:${CIO_TRACK_API_KEY}`).toString("base64");

function splitName(name) {
  if (!name) return { first_name: "", last_name: "" };
  const p = name.trim().split(/\s+/).filter(Boolean);
  if (p.length === 0) return { first_name: "", last_name: "" };
  if (p.length === 1) return { first_name: p[0], last_name: "" };
  return { first_name: p[0], last_name: p.slice(1).join(" ") };
}

// fetch with retry/backoff on 429 and 5xx.
async function req(url, opts, label) {
  for (let attempt = 0; attempt < 6; attempt++) {
    const res = await fetch(url, opts);
    if (res.ok) return res;
    if (res.status === 429 || res.status >= 500) {
      const wait = Math.min(16000, 500 * 2 ** attempt);
      await new Promise((r) => setTimeout(r, wait));
      continue;
    }
    throw new Error(`${label} failed: ${res.status} ${await res.text()}`);
  }
  throw new Error(`${label} failed after retries`);
}

// Run async tasks with a bounded worker pool.
async function pool(items, worker) {
  let i = 0;
  let done = 0;
  const runners = Array.from({ length: CONCURRENCY }, async () => {
    while (i < items.length) {
      const idx = i++;
      await worker(items[idx]);
      if (++done % 200 === 0) console.log(`  ...${done}/${items.length}`);
    }
  });
  await Promise.all(runners);
}

async function stripeList(path, extra = {}) {
  const out = [];
  let startingAfter = null;
  while (true) {
    const params = new URLSearchParams({ limit: "100", ...extra });
    if (startingAfter) params.set("starting_after", startingAfter);
    const res = await req(
      `https://api.stripe.com/v1/${path}?${params}`,
      { headers: { Authorization: `Bearer ${STRIPE_KEY}` } },
      `Stripe ${path}`
    );
    const data = await res.json();
    out.push(...data.data);
    if (!data.has_more) break;
    startingAfter = data.data[data.data.length - 1].id;
  }
  return out;
}

async function cioIdentify({ email, name, createdAt }) {
  const id = email.trim().toLowerCase();
  const { first_name, last_name } = splitName(name);
  const attributes = { email: id, first_name, last_name };
  if (createdAt) attributes.created_at = Math.floor(createdAt);
  if (DRY_RUN) return;
  await req(
    `${CIO_BASE}/api/v1/customers/${encodeURIComponent(id)}`,
    {
      method: "PUT",
      headers: { Authorization: CIO_AUTH, "Content-Type": "application/json" },
      body: JSON.stringify(attributes),
    },
    "CIO identify"
  );
}

async function cioPayment({ email, timestamp }) {
  const id = email.trim().toLowerCase();
  if (DRY_RUN) return;
  await req(
    `${CIO_BASE}/api/v1/customers/${encodeURIComponent(id)}/events`,
    {
      method: "POST",
      headers: { Authorization: CIO_AUTH, "Content-Type": "application/json" },
      body: JSON.stringify({ name: "payment", timestamp: Math.floor(timestamp) }),
    },
    "CIO payment"
  );
}

async function main() {
  console.log(`Backfill starting${DRY_RUN ? " (DRY RUN — no writes)" : ""}...`);

  console.log("Fetching Stripe customers...");
  const customers = await stripeList("customers");
  console.log(`  ${customers.length} customers`);

  console.log("Fetching Stripe charges...");
  const charges = await stripeList("charges");
  const succeeded = charges.filter((c) => c.status === "succeeded" && c.paid);
  console.log(`  ${charges.length} charges (${succeeded.length} successful)`);

  // Map customer id -> canonical email so payment events land on the right profile.
  const idToEmail = new Map();
  const people = [];
  for (const c of customers) {
    const email = (c.email || "").trim().toLowerCase();
    if (!email) continue;
    idToEmail.set(c.id, email);
    people.push({ email, name: c.name, createdAt: c.created });
  }

  console.log(`Identifying ${people.length} profiles...`);
  await pool(people, cioIdentify);

  // One payment event per successful charge, at its real timestamp.
  const payments = [];
  let orphan = 0;
  for (const ch of succeeded) {
    const email =
      idToEmail.get(ch.customer) ||
      (ch.billing_details?.email || ch.receipt_email || "").trim().toLowerCase();
    if (!email) {
      orphan++;
      continue;
    }
    payments.push({ email, timestamp: ch.created });
  }

  console.log(`Recording ${payments.length} payment events...`);
  await pool(payments, cioPayment);

  console.log("\nDone.");
  console.log(`  Profiles identified: ${people.length}`);
  console.log(`  Payment events:      ${payments.length}`);
  if (orphan) console.log(`  Charges skipped (no email): ${orphan}`);
  console.log(
    "\nSegments in Customer.io will finish rebuilding within a few minutes."
  );
}

main().catch((e) => {
  console.error("Backfill error:", e);
  process.exit(1);
});
