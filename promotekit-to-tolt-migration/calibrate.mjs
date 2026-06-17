// Calibration: create the FIRST real partner+customer+transaction, then check
// whether Tolt auto-generated a commission. Writes results into the shared
// state file so the full migration skips these records. Always live.

import { config } from "./src/config.mjs";
import * as tolt from "./src/tolt.mjs";
import { request, log, sleep, toCents, loadState, saveState } from "./src/util.mjs";

const pkHeaders = { Authorization: `Bearer ${config.promotekitApiKey}`, Accept: "application/json" };
const toltHeaders = { Authorization: `Bearer ${config.toltApiKey}`, Accept: "application/json" };

async function toltGet(path) {
  const sep = path.includes("?") ? "&" : "?";
  return request(`${config.toltBaseUrl}${path}${sep}program_id=${config.toltProgramId}`, { headers: toltHeaders });
}

const body = await request(`${config.promotekitBaseUrl}/commissions?limit=100&page=1`, { headers: pkHeaders });
const c = body.data.find((r) => (r.revenue_amount || 0) > 0);
if (!c) throw new Error("no positive commission found");

const aff = c.affiliate;
const ref = c.referral;
log.info(`Calibrating with commission ${c.id}: affiliate ${aff.email}, referral ${ref.email}, revenue $${c.revenue_amount}, commission $${c.commission_amount}`);

const state = loadState(config.stateFile);

// 1. Partner
let partnerId = state.partners[aff.id];
if (!partnerId || /^(DRYRUN|EXISTS):/.test(partnerId)) {
  const p = await tolt.createPartner({
    first_name: aff.first_name || aff.email.split("@")[0],
    last_name: aff.last_name || "(n/a)",
    email: aff.email,
    program_id: config.toltProgramId,
    ...(aff.payout_email ? { payout_method: "paypal", payout_details: { paypal_email: aff.payout_email } } : {}),
  });
  partnerId = tolt.toltId(p);
  state.partners[aff.id] = partnerId;
  log.ok(`partner created -> ${partnerId}`);
}

// 2. Customer
let customerId = state.customers[ref.id];
if (!customerId || /^(DRYRUN|EXISTS):/.test(customerId)) {
  const cust = await tolt.createCustomer({
    email: ref.email,
    partner_id: partnerId,
    status: ref.subscription_status === "active" ? "active" : "lead",
    created_at: new Date(ref.signup_date || ref.created_at).toISOString(),
    ...(ref.stripe_customer_id ? { customer_id: ref.stripe_customer_id } : {}),
  });
  customerId = tolt.toltId(cust);
  state.customers[ref.id] = customerId;
  log.ok(`customer created -> ${customerId}`);
}
saveState(config.stateFile, state);

// 3. Commission count BEFORE transaction
const before = await toltGet(`/commissions?limit=100`);
const beforeCount = before.total_count;
log.info(`Tolt commissions before transaction: ${beforeCount}`);

// 4. Create the transaction
const tx = await tolt.createTransaction({
  amount: toCents(c.revenue_amount, false),
  customer_id: customerId,
  created_at: new Date(c.referral_date || c.created_at).toISOString(),
});
state.transactions[c.id] = true;
saveState(config.stateFile, state);
log.ok(`transaction created -> ${tolt.toltId(tx)} ($${c.revenue_amount})`);

// 5. Wait and re-check commissions
await sleep(4000);
const after = await toltGet(`/commissions?limit=100`);
const afterCount = after.total_count;
log.info(`Tolt commissions after transaction: ${afterCount}`);

if (afterCount > beforeCount) {
  const auto = after.data[0];
  log.warn(`>>> Tolt AUTO-CREATED a commission. amount=${auto.amount}c expected≈${toCents(c.commission_amount, false)}c`);
  log.warn(">>> DECISION: do NOT create commissions manually (set CREATE_COMMISSIONS=false). Mark this one done.");
  state.commissions[c.id] = true;
  saveState(config.stateFile, state);
} else {
  log.ok(">>> Tolt did NOT auto-create a commission.");
  log.ok(">>> DECISION: create commissions manually (CREATE_COMMISSIONS=true). Adding this one now.");
  const comm = await tolt.createCommission({
    amount: toCents(c.commission_amount, false),
    customer_id: customerId,
    revenue: toCents(c.revenue_amount, false),
    created_at: new Date(c.referral_date || c.created_at).toISOString(),
  });
  state.commissions[c.id] = true;
  saveState(config.stateFile, state);
  log.ok(`commission created -> ${tolt.toltId(comm)} ($${c.commission_amount})`);
}
