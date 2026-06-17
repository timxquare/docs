// Orchestrates the PromoteKit -> Tolt migration.
//
// Flow:
//   1. Affiliates  -> Tolt partners
//   2. Referrals   -> Tolt customers (linked to the partner who referred them)
//   3. Sale amount -> Tolt transaction
//   4. Commission  -> Tolt commission
//
// The run is idempotent and resumable: every created object is recorded in
// migration-state.json keyed by its PromoteKit id, so re-running skips work
// that's already done. Dry run is the default; pass --live to write.

import { config, validateConfig } from "./config.mjs";
import * as pk from "./promotekit.mjs";
import * as tolt from "./tolt.mjs";
import {
  log,
  sleep,
  splitName,
  toCents,
  loadState,
  saveState,
  writeReport,
  pick,
} from "./util.mjs";

// PromoteKit referral status -> Tolt customer status.
function mapCustomerStatus(raw) {
  const s = String(raw || "").toLowerCase();
  if (["active", "paid", "converted", "completed", "approved", "subscribed"].includes(s))
    return "active";
  if (["trial", "trialing"].includes(s)) return "trialing";
  if (["canceled", "cancelled", "refunded", "churned"].includes(s)) return "canceled";
  return "lead"; // default for new/pending/unknown
}

const summary = {
  partners: { created: 0, skipped: 0, failed: 0 },
  customers: { created: 0, skipped: 0, failed: 0 },
  transactions: { created: 0, skipped: 0, failed: 0 },
  commissions: { created: 0, skipped: 0, failed: 0 },
  errors: [],
};

async function inspect() {
  log.info("INSPECT MODE — fetching one sample of each source resource.\n");
  const affiliates = await pk.fetchAllPages(config.pkEndpoints.affiliates).catch((e) => {
    log.error(`Affiliates endpoint failed: ${e.message}`);
    return [];
  });
  log.ok(`Affiliates returned: ${affiliates.length}`);
  if (affiliates[0]) {
    log.info("Sample affiliate object keys: " + Object.keys(affiliates[0]).join(", "));
    log.info("Sample affiliate: " + JSON.stringify(affiliates[0], null, 2));
  }

  const referrals = await pk.getReferrals(affiliates.slice(0, 3)).catch((e) => {
    log.error(`Referrals endpoint failed: ${e.message}`);
    return [];
  });
  log.ok(`Referrals returned: ${referrals.length}`);
  if (referrals[0]) {
    log.info("Sample referral object keys: " + Object.keys(referrals[0]).join(", "));
    log.info("Sample referral: " + JSON.stringify(referrals[0], null, 2));
  }
  log.info(
    "\nIf the field mappings in src/promotekit.mjs don't match the keys above, " +
      "adjust the resolver lists there, then re-run."
  );
}

async function migratePartners(affiliates, state) {
  log.info(`\n=== Partners: ${affiliates.length} affiliates ===`);
  for (const aff of affiliates) {
    const srcId = pk.affiliateId(aff) || pk.affiliateEmail(aff);
    if (!srcId) {
      summary.partners.failed++;
      summary.errors.push({ stage: "partner", reason: "no id/email", record: aff });
      continue;
    }
    if (state.partners[srcId]) {
      summary.partners.skipped++;
      continue;
    }

    const email = pk.affiliateEmail(aff);
    if (!email) {
      summary.partners.failed++;
      summary.errors.push({ stage: "partner", reason: "missing email", srcId });
      log.warn(`Affiliate ${srcId} has no email; skipped.`);
      continue;
    }

    // Build name (Tolt requires first AND last name).
    let first = pk.affiliateFirstName(aff);
    let last = pk.affiliateLastName(aff);
    if (!first && !last) {
      ({ first_name: first, last_name: last } = splitName(pk.affiliateName(aff), email.split("@")[0]));
    }
    if (!last) last = "(n/a)";

    const payload = {
      first_name: first,
      last_name: last,
      email,
      program_id: config.toltProgramId,
    };
    if (config.toltGroupId) payload.group_id = config.toltGroupId;
    const company = pk.affiliateCompany(aff);
    if (company) payload.company_name = company;
    const country = pk.affiliateCountry(aff);
    if (country) payload.country_code = country;
    const paypal = pk.affiliatePaypalEmail(aff);
    if (paypal) {
      payload.payout_method = "paypal";
      payload.payout_details = paypal;
    }

    if (config.dryRun) {
      log.dim(`[dry-run] would create partner ${email}`);
      state.partners[srcId] = `DRYRUN:${email}`;
      summary.partners.created++;
      continue;
    }

    try {
      const created = await tolt.createPartner(payload);
      const id = tolt.toltId(created);
      state.partners[srcId] = id;
      saveState(config.stateFile, state);
      summary.partners.created++;
      log.ok(`partner created: ${email} -> ${id}`);
    } catch (e) {
      // Treat "already exists" as a soft skip if Tolt reports a duplicate.
      const msg = JSON.stringify(e.body || e.message).toLowerCase();
      if (msg.includes("exist") || e.status === 409) {
        summary.partners.skipped++;
        log.warn(`partner ${email} already exists in Tolt; recording as skipped.`);
        state.partners[srcId] = `EXISTS:${email}`;
        saveState(config.stateFile, state);
      } else {
        summary.partners.failed++;
        summary.errors.push({ stage: "partner", email, error: e.message });
        log.error(`partner ${email} failed: ${e.message}`);
      }
    }
    await sleep(config.writeDelayMs);
  }
}

async function migrateReferrals(referrals, state) {
  log.info(`\n=== Customers / Transactions / Commissions: ${referrals.length} referrals ===`);
  for (const ref of referrals) {
    const refId = pk.referralId(ref) || `${pk.referralAffiliateId(ref)}:${pk.referralEmail(ref)}`;
    const srcAffId = pk.referralAffiliateId(ref);
    const partnerId = srcAffId ? state.partners[srcAffId] : undefined;
    const email = pk.referralEmail(ref);

    if (!partnerId) {
      summary.customers.failed++;
      summary.errors.push({ stage: "customer", reason: "unmapped affiliate", srcAffId, refId });
      log.warn(`Referral ${refId}: no Tolt partner for affiliate ${srcAffId}; skipped.`);
      continue;
    }
    if (!email) {
      summary.customers.failed++;
      summary.errors.push({ stage: "customer", reason: "missing email", refId });
      continue;
    }

    // --- Customer ---
    let customerId = state.customers[refId];
    if (!customerId) {
      const payload = {
        email,
        partner_id: typeof partnerId === "string" && partnerId.includes(":") ? undefined : partnerId,
        status: mapCustomerStatus(pk.referralStatus(ref)),
      };
      // When partnerId is a DRYRUN/EXISTS placeholder we can't link by real id.
      const isRealPartner = partnerId && !/^(DRYRUN|EXISTS):/.test(partnerId);
      if (isRealPartner) payload.partner_id = partnerId;
      const name = pk.referralName(ref);
      if (name) payload.name = name;
      const createdAt = pk.referralCreatedAt(ref);
      if (createdAt) payload.created_at = new Date(createdAt).toISOString();
      const extId = pk.referralExternalCustomerId(ref);
      if (extId) payload.customer_id = String(extId);

      if (config.dryRun) {
        log.dim(`[dry-run] would create customer ${email} (partner ${srcAffId})`);
        customerId = `DRYRUN:${email}`;
        state.customers[refId] = customerId;
        summary.customers.created++;
      } else if (!isRealPartner) {
        summary.customers.failed++;
        summary.errors.push({ stage: "customer", reason: "partner not real id", refId });
        continue;
      } else {
        try {
          const created = await tolt.createCustomer(payload);
          customerId = tolt.toltId(created);
          state.customers[refId] = customerId;
          saveState(config.stateFile, state);
          summary.customers.created++;
          log.ok(`customer created: ${email} -> ${customerId}`);
        } catch (e) {
          summary.customers.failed++;
          summary.errors.push({ stage: "customer", email, error: e.message });
          log.error(`customer ${email} failed: ${e.message}`);
          continue;
        }
        await sleep(config.writeDelayMs);
      }
    } else {
      summary.customers.skipped++;
    }

    const realCustomer = customerId && !/^DRYRUN:/.test(customerId);

    // --- Transaction (the referred sale) ---
    const saleRaw = pk.referralSaleAmount(ref);
    if (saleRaw !== undefined && saleRaw !== null && saleRaw !== "" && Number(saleRaw) > 0) {
      const cents = toCents(saleRaw, config.sourceAmountsInCents);
      if (!state.transactions[refId]) {
        if (config.dryRun) {
          log.dim(`[dry-run] would create transaction ${cents}c for ${email}`);
          state.transactions[refId] = "DRYRUN";
          summary.transactions.created++;
        } else if (realCustomer && cents) {
          const payload = { amount: cents, customer_id: customerId };
          const createdAt = pk.referralCreatedAt(ref);
          if (createdAt) payload.created_at = new Date(createdAt).toISOString();
          try {
            const created = await tolt.createTransaction(payload);
            state.transactions[refId] = tolt.toltId(created) || true;
            saveState(config.stateFile, state);
            summary.transactions.created++;
            log.ok(`transaction created: ${cents}c for ${email}`);
          } catch (e) {
            summary.transactions.failed++;
            summary.errors.push({ stage: "transaction", email, error: e.message });
            log.error(`transaction for ${email} failed: ${e.message}`);
          }
          await sleep(config.writeDelayMs);
        }
      } else {
        summary.transactions.skipped++;
      }
    }

    // --- Commission (the affiliate's earning) ---
    const commRaw = pk.referralCommissionAmount(ref);
    if (commRaw !== undefined && commRaw !== null && commRaw !== "" && Number(commRaw) > 0) {
      const cents = toCents(commRaw, config.sourceAmountsInCents);
      if (!state.commissions[refId]) {
        if (config.dryRun) {
          log.dim(`[dry-run] would create commission ${cents}c for ${email}`);
          state.commissions[refId] = "DRYRUN";
          summary.commissions.created++;
        } else if (realCustomer && cents) {
          const payload = { amount: cents, customer_id: customerId };
          const saleCents = toCents(saleRaw, config.sourceAmountsInCents);
          if (saleCents) payload.revenue = saleCents;
          const createdAt = pk.referralCreatedAt(ref);
          if (createdAt) payload.created_at = new Date(createdAt).toISOString();
          try {
            const created = await tolt.createCommission(payload);
            state.commissions[refId] = tolt.toltId(created) || true;
            saveState(config.stateFile, state);
            summary.commissions.created++;
            log.ok(`commission created: ${cents}c for ${email}`);
          } catch (e) {
            summary.commissions.failed++;
            summary.errors.push({ stage: "commission", email, error: e.message });
            log.error(`commission for ${email} failed: ${e.message}`);
          }
          await sleep(config.writeDelayMs);
        }
      } else {
        summary.commissions.skipped++;
      }
    }
  }
}

export async function run() {
  validateConfig();

  log.info(
    `Mode: ${config.dryRun ? "DRY RUN (no data written)" : "LIVE (writing to Tolt)"}`
  );
  log.info(`Source: ${config.promotekitBaseUrl}`);
  log.info(`Destination: ${config.toltBaseUrl} (program ${config.toltProgramId})\n`);

  if (config.inspect) {
    await inspect();
    return;
  }

  const state = config.reset
    ? { partners: {}, customers: {}, transactions: {}, commissions: {} }
    : loadState(config.stateFile);

  let affiliates = await pk.getAffiliates();
  if (config.limit) affiliates = affiliates.slice(0, Number(config.limit));
  log.ok(`Loaded ${affiliates.length} affiliates.`);

  await migratePartners(affiliates, state);

  const referrals = await pk.getReferrals(affiliates);
  log.ok(`Loaded ${referrals.length} referrals.`);

  await migrateReferrals(referrals, state);

  saveState(config.stateFile, state);
  writeReport(config.reportFile, { mode: config.dryRun ? "dry-run" : "live", summary });

  log.info("\n========== SUMMARY ==========");
  for (const k of ["partners", "customers", "transactions", "commissions"]) {
    const s = summary[k];
    log.info(`${k.padEnd(13)} created=${s.created}  skipped=${s.skipped}  failed=${s.failed}`);
  }
  if (summary.errors.length) {
    log.warn(`${summary.errors.length} errors — see ${config.reportFile} and migration.log`);
  }
  if (config.dryRun) {
    log.info("\nThis was a DRY RUN. Re-run with --live to write data into Tolt.");
  } else {
    log.ok("\nMigration complete.");
  }
}
