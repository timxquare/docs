// PromoteKit (source) API client. Read-only.
//
// PromoteKit's public docs don't publish exact endpoint paths/field names,
// so this client is deliberately defensive: it locates the record array in
// whatever envelope is returned and resolves fields from a list of likely
// names. Run the migrator with --inspect to print real shapes.

import { config } from "./config.mjs";
import { request, firstArray, pick, log } from "./util.mjs";

function headers() {
  return {
    Authorization: `Bearer ${config.promotekitApiKey}`,
    "Content-Type": "application/json",
    Accept: "application/json",
  };
}

function url(pathname, params = {}) {
  const u = new URL(config.promotekitBaseUrl.replace(/\/$/, "") + pathname);
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null) u.searchParams.set(k, v);
  }
  return u.toString();
}

/** Fetch every page of a list endpoint and return all records. */
export async function fetchAllPages(pathname, extraParams = {}) {
  const all = [];
  let page = 1;
  // eslint-disable-next-line no-constant-condition
  while (true) {
    const body = await request(
      url(pathname, { limit: config.pageSize, page, ...extraParams }),
      { headers: headers() }
    );
    const records = firstArray(body) || [];
    all.push(...records);
    log.dim(`  ${pathname} page ${page}: ${records.length} records (total ${all.length})`);

    // Stop when a page returns fewer than a full page of results, or none.
    if (records.length < config.pageSize || records.length === 0) break;
    page++;
    // Safety valve against accidental infinite loops.
    if (page > 10000) {
      log.warn("Stopping pagination at 10,000 pages (safety limit).");
      break;
    }
  }
  return all;
}

export async function getAffiliates() {
  log.info("Fetching affiliates from PromoteKit…");
  return fetchAllPages(config.pkEndpoints.affiliates);
}

/**
 * Fetch all referrals. Tries the global referrals endpoint first; if that
 * isn't available (404), falls back to fetching per-affiliate.
 */
export async function getReferrals(affiliates) {
  log.info("Fetching referrals from PromoteKit…");
  try {
    const all = await fetchAllPages(config.pkEndpoints.referrals);
    if (all.length || affiliates.length === 0) return all;
    log.warn("Global referrals endpoint returned 0; trying per-affiliate.");
  } catch (e) {
    if (e.status === 404) {
      log.warn("Global referrals endpoint not found; trying per-affiliate.");
    } else {
      throw e;
    }
  }

  // Per-affiliate fallback.
  const all = [];
  for (const aff of affiliates) {
    const id = affiliateId(aff);
    if (!id) continue;
    const path = config.pkEndpoints.referralsPerAffiliate.replace("{id}", id);
    try {
      const recs = await fetchAllPages(path);
      // Stamp the affiliate id so downstream linking works even if the
      // per-affiliate payload omits it.
      for (const r of recs) if (r && r.__affiliate_id === undefined) r.__affiliate_id = id;
      all.push(...recs);
    } catch (e) {
      if (e.status === 404) continue;
      throw e;
    }
  }
  return all;
}

// ---- Field resolvers (normalize unknown PromoteKit shapes) ----

export const affiliateId = (a) =>
  pick(a, ["id", "affiliate_id", "uuid", "_id", "reference"]);

export const affiliateEmail = (a) =>
  pick(a, ["email", "affiliate_email", "user_email", "contact_email"]);

export const affiliateName = (a) =>
  pick(a, ["name", "full_name", "affiliate_name", "display_name"]);

export const affiliateFirstName = (a) =>
  pick(a, ["first_name", "firstName", "given_name"]);

export const affiliateLastName = (a) =>
  pick(a, ["last_name", "lastName", "family_name", "surname"]);

export const affiliateCompany = (a) =>
  pick(a, ["company", "company_name", "business_name"]);

export const affiliateCountry = (a) =>
  pick(a, ["country_code", "country", "countryCode"]);

export const affiliateCreatedAt = (a) =>
  pick(a, ["created_at", "createdAt", "created", "signup_date", "joined_at"]);

export const affiliatePaypalEmail = (a) =>
  pick(a, ["paypal_email", "paypal", "payout_email"]);

// Referral resolvers
export const referralAffiliateId = (r) =>
  pick(r, ["affiliate_id", "affiliateId", "affiliate", "partner_id", "__affiliate_id"]);

export const referralEmail = (r) =>
  pick(r, ["email", "customer_email", "referral_email", "lead_email", "user_email"]);

export const referralName = (r) =>
  pick(r, ["name", "customer_name", "full_name"]);

export const referralId = (r) =>
  pick(r, ["id", "referral_id", "uuid", "_id"]);

export const referralStatus = (r) =>
  pick(r, ["status", "state", "stage"]);

export const referralCreatedAt = (r) =>
  pick(r, ["created_at", "createdAt", "created", "referred_at", "date"]);

// Monetary fields on a referral
export const referralSaleAmount = (r) =>
  pick(r, ["amount", "sale_amount", "revenue", "total", "purchase_amount", "mrr"]);

export const referralCommissionAmount = (r) =>
  pick(r, ["commission", "commission_amount", "earnings", "reward", "payout"]);

export const referralExternalCustomerId = (r) =>
  pick(r, ["customer_id", "stripe_customer_id", "external_id"]);
