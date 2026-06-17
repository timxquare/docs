// Tailored PromoteKit -> Tolt migration for the Icemail account.
// Built against the REAL, verified API shapes:
//
//   /affiliates  : { id, email, first_name, last_name, payout_email, ... }
//   /referrals   : { id, email, subscription_status, signup_date,
//                    stripe_customer_id, created_at, affiliate:{ id, ... } }
//   /commissions : { id, revenue_amount, commission_amount, currency,
//                    payout_status, referral_date, created_at,
//                    stripe_payment_id, affiliate:{id}, referral:{id,...} }
//
// Mapping:
//   affiliate            -> Tolt partner          (key: affiliate.id)
//   referral (customer)  -> Tolt customer         (key: referral.id)
//   commission.revenue   -> Tolt transaction      (key: commission.id)
//   commission.amount    -> Tolt commission       (key: commission.id)
//
// Amounts are in dollars in PromoteKit; Tolt wants cents.
// Dry run by default; pass --live to write. Idempotent + resumable.

import { config, validateConfig } from "./src/config.mjs";
import * as tolt from "./src/tolt.mjs";
import {
  request,
  log,
  sleep,
  toCents,
  splitName,
  loadState,
  saveState,
  writeReport,
} from "./src/util.mjs";

// Toggle these if Tolt is found to auto-create commissions from transactions.
const CREATE_TRANSACTIONS = process.env.CREATE_TRANSACTIONS !== "false";
const CREATE_COMMISSIONS = process.env.CREATE_COMMISSIONS !== "false";

const summary = {
  partners: { created: 0, skipped: 0, failed: 0 },
  customers: { created: 0, skipped: 0, failed: 0 },
  transactions: { created: 0, skipped: 0, failed: 0 },
  commissions: { created: 0, skipped: 0, failed: 0 },
  errors: [],
};

async function pkAll(path) {
  const headers = {
    Authorization: `Bearer ${config.promotekitApiKey}`,
    Accept: "application/json",
  };
  const base = config.promotekitBaseUrl.replace(/\/$/, "");
  let page = 1;
  const all = [];
  while (true) {
    const body = await request(`${base}${path}?limit=100&page=${page}`, { headers });
    const data = body.data || [];
    all.push(...data);
    const pg = body.pagination;
    log.dim(`  ${path} page ${page}/${pg ? pg.total_pages : "?"} (+${data.length}, total ${all.length})`);
    if (pg ? !pg.has_more : data.length < 100) break;
    page++;
    if (page > 2000) break;
  }
  return all;
}

// Tolt rejects names containing numbers or special characters. Keep only
// letters and spaces; fall back to a letters-only default if nothing remains.
function cleanName(s, fallback) {
  const cleaned = String(s || "")
    .replace(/[^\p{L} ]/gu, "")
    .replace(/\s+/g, " ")
    .trim();
  return cleaned || fallback;
}

function customerStatus(raw) {
  const s = String(raw || "").toLowerCase();
  if (["active", "paid", "subscribed"].includes(s)) return "active";
  if (["trialing", "trial"].includes(s)) return "trialing";
  if (["canceled", "cancelled", "churned", "refunded", "incomplete_expired"].includes(s))
    return "canceled";
  return "lead";
}

async function run() {
  validateConfig();
  const dry = config.dryRun;
  log.info(`Mode: ${dry ? "DRY RUN (writes nothing)" : "LIVE (writing to Tolt)"}`);
  log.info(`Tolt program: ${config.toltProgramId}`);
  log.info(`Create transactions: ${CREATE_TRANSACTIONS} | Create commissions: ${CREATE_COMMISSIONS}\n`);

  const state = config.reset
    ? { partners: {}, customers: {}, transactions: {}, commissions: {} }
    : loadState(config.stateFile);

  // ---- Fetch everything from PromoteKit ----
  log.info("Fetching affiliates…");
  const affiliates = await pkAll("/affiliates");
  log.info("Fetching referrals…");
  const referrals = await pkAll("/referrals");
  log.info("Fetching commissions…");
  const commissions = await pkAll("/commissions");
  log.ok(`Source totals: ${affiliates.length} affiliates, ${referrals.length} referrals, ${commissions.length} commissions\n`);

  // ---- 1. Partners ----
  log.info("=== Partners ===");
  for (const a of affiliates) {
    const key = a.id;
    if (!key || !a.email) {
      summary.partners.failed++;
      continue;
    }
    if (state.partners[key]) {
      summary.partners.skipped++;
      continue;
    }
    let first = a.first_name;
    let last = a.last_name;
    if (!first && !last) ({ first_name: first, last_name: last } = splitName(a.name, a.email.split("@")[0]));
    const emailLocalLetters = cleanName(a.email.split("@")[0], "Partner");
    const payload = {
      first_name: cleanName(first, emailLocalLetters),
      last_name: cleanName(last, "Affiliate"),
      email: a.email,
      program_id: config.toltProgramId,
    };
    if (a.payout_email) {
      payload.payout_method = "paypal";
      payload.payout_details = { paypal_email: a.payout_email };
    }
    if (dry) {
      state.partners[key] = `DRYRUN:${a.email}`;
      summary.partners.created++;
      continue;
    }
    try {
      const created = await tolt.createPartner(payload);
      state.partners[key] = tolt.toltId(created);
      saveState(config.stateFile, state);
      summary.partners.created++;
      log.ok(`partner ${a.email} -> ${state.partners[key]}`);
    } catch (e) {
      const msg = JSON.stringify(e.body || e.message).toLowerCase();
      if (e.status === 409 || msg.includes("exist")) {
        state.partners[key] = `EXISTS:${a.email}`;
        saveState(config.stateFile, state);
        summary.partners.skipped++;
      } else {
        summary.partners.failed++;
        summary.errors.push({ stage: "partner", email: a.email, error: e.message });
        log.error(`partner ${a.email}: ${e.message}`);
      }
    }
    await sleep(config.writeDelayMs);
  }

  // ---- 2. Customers (from referrals + referrals embedded in commissions) ----
  log.info("\n=== Customers ===");
  // Build a unique map of referral records keyed by referral id, capturing the
  // affiliate id from whichever source has it.
  const custMap = new Map();
  for (const r of referrals) {
    if (!r.id) continue;
    custMap.set(r.id, {
      id: r.id,
      email: r.email,
      status: r.subscription_status,
      created_at: r.signup_date || r.created_at,
      stripe_customer_id: r.stripe_customer_id,
      affiliateId: r.affiliate && r.affiliate.id,
    });
  }
  for (const c of commissions) {
    const r = c.referral;
    if (!r || !r.id) continue;
    if (!custMap.has(r.id)) {
      custMap.set(r.id, {
        id: r.id,
        email: r.email,
        status: r.subscription_status,
        created_at: r.signup_date || r.created_at,
        stripe_customer_id: r.stripe_customer_id,
        affiliateId: c.affiliate && c.affiliate.id,
      });
    } else if (!custMap.get(r.id).affiliateId && c.affiliate) {
      custMap.get(r.id).affiliateId = c.affiliate.id;
    }
  }

  for (const cust of custMap.values()) {
    if (state.customers[cust.id]) {
      summary.customers.skipped++;
      continue;
    }
    const partnerId = cust.affiliateId ? state.partners[cust.affiliateId] : undefined;
    const realPartner = partnerId && !/^(DRYRUN|EXISTS):/.test(partnerId);
    if (!cust.email || !partnerId) {
      summary.customers.failed++;
      summary.errors.push({ stage: "customer", id: cust.id, reason: !cust.email ? "no email" : "unmapped affiliate" });
      continue;
    }
    const payload = {
      email: cust.email,
      status: customerStatus(cust.status),
    };
    if (realPartner) payload.partner_id = partnerId;
    if (cust.created_at) payload.created_at = new Date(cust.created_at).toISOString();
    if (cust.stripe_customer_id) payload.customer_id = String(cust.stripe_customer_id);

    if (dry) {
      state.customers[cust.id] = `DRYRUN:${cust.email}`;
      summary.customers.created++;
      continue;
    }
    if (!realPartner) {
      summary.customers.failed++;
      summary.errors.push({ stage: "customer", id: cust.id, reason: "partner not a real id" });
      continue;
    }
    try {
      const created = await tolt.createCustomer(payload);
      state.customers[cust.id] = tolt.toltId(created);
      saveState(config.stateFile, state);
      summary.customers.created++;
      log.ok(`customer ${cust.email} -> ${state.customers[cust.id]}`);
    } catch (e) {
      const msg = JSON.stringify(e.body || e.message).toLowerCase();
      if (e.status === 409 || msg.includes("exist")) {
        state.customers[cust.id] = `EXISTS:${cust.email}`;
        saveState(config.stateFile, state);
        summary.customers.skipped++;
      } else {
        summary.customers.failed++;
        summary.errors.push({ stage: "customer", email: cust.email, error: e.message });
        log.error(`customer ${cust.email}: ${e.message}`);
      }
    }
    await sleep(config.writeDelayMs);
  }

  // ---- 3 & 4. Transactions + Commissions (from /commissions) ----
  log.info("\n=== Transactions & Commissions ===");
  for (const c of commissions) {
    const refId = c.referral && c.referral.id;
    const customerId = refId ? state.customers[refId] : undefined;
    const realCustomer = customerId && !/^(DRYRUN|EXISTS):/.test(customerId);
    const email = c.referral && c.referral.email;

    if (!customerId) {
      summary.transactions.failed++;
      summary.errors.push({ stage: "transaction", commissionId: c.id, reason: "no mapped customer" });
      continue;
    }

    const revenueCents = toCents(c.revenue_amount, config.sourceAmountsInCents);
    const commCents = toCents(c.commission_amount, config.sourceAmountsInCents);
    const when = c.referral_date || c.created_at;

    // Transaction (the revenue)
    if (CREATE_TRANSACTIONS && revenueCents > 0 && !state.transactions[c.id]) {
      if (dry) {
        state.transactions[c.id] = true;
        summary.transactions.created++;
      } else if (realCustomer) {
        const payload = { amount: revenueCents, customer_id: customerId };
        if (when) payload.created_at = new Date(when).toISOString();
        try {
          await tolt.createTransaction(payload);
          state.transactions[c.id] = true;
          saveState(config.stateFile, state);
          summary.transactions.created++;
          log.ok(`transaction ${revenueCents}c for ${email}`);
        } catch (e) {
          summary.transactions.failed++;
          summary.errors.push({ stage: "transaction", commissionId: c.id, error: e.message });
          log.error(`transaction ${c.id}: ${e.message}`);
        }
        await sleep(config.writeDelayMs);
      }
    } else if (state.transactions[c.id]) {
      summary.transactions.skipped++;
    }

    // Commission (the earning)
    if (CREATE_COMMISSIONS && commCents > 0 && !state.commissions[c.id]) {
      if (dry) {
        state.commissions[c.id] = true;
        summary.commissions.created++;
      } else if (realCustomer) {
        const payload = { amount: commCents, customer_id: customerId };
        if (revenueCents > 0) payload.revenue = revenueCents;
        if (when) payload.created_at = new Date(when).toISOString();
        try {
          await tolt.createCommission(payload);
          state.commissions[c.id] = true;
          saveState(config.stateFile, state);
          summary.commissions.created++;
          log.ok(`commission ${commCents}c for ${email}`);
        } catch (e) {
          summary.commissions.failed++;
          summary.errors.push({ stage: "commission", commissionId: c.id, error: e.message });
          log.error(`commission ${c.id}: ${e.message}`);
        }
        await sleep(config.writeDelayMs);
      }
    } else if (state.commissions[c.id]) {
      summary.commissions.skipped++;
    }
  }

  saveState(config.stateFile, state);
  writeReport(config.reportFile, { mode: dry ? "dry-run" : "live", summary });

  log.info("\n========== SUMMARY ==========");
  for (const k of ["partners", "customers", "transactions", "commissions"]) {
    const s = summary[k];
    log.info(`${k.padEnd(13)} created=${s.created}  skipped=${s.skipped}  failed=${s.failed}`);
  }
  if (summary.errors.length) {
    log.warn(`${summary.errors.length} issues — see ${config.reportFile}`);
    log.warn(JSON.stringify(summary.errors.slice(0, 5), null, 2));
  }
  log.info(dry ? "\nDRY RUN complete — nothing was written." : "\nLIVE migration complete.");
}

run().catch((e) => {
  log.error(e.stack || e.message);
  process.exit(1);
});
