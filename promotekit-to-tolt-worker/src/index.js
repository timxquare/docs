// Cloudflare Worker: migrate PromoteKit -> Tolt.
//
// State lives in KV (binding MIGRATION_KV) so the job is resumable. Work is
// done in small batches: a Cron Trigger drains the queue automatically once
// minute, and you can also push a batch immediately by visiting /run.
//
// Control endpoints (all require ?token=MIGRATION_SECRET):
//   GET  /status         current phase + progress summary
//   GET  /inspect        sample of source data (writes nothing)
//   POST /start?live=0   load source data and begin a DRY RUN (default)
//   POST /start?live=1   load source data and begin a LIVE migration
//   POST /run            process one batch right now (don't wait for cron)
//   POST /reset          clear all saved progress
//
// Tip: from a terminal you can call these with curl, e.g.
//   curl -X POST "https://<your-worker-url>/start?live=0&token=YOUR_SECRET"

const STATE_KEY = "state";
const AFFILIATES_KEY = "affiliates";
const REFERRALS_KEY = "referrals";

const EMPTY_STATE = () => ({
  phase: "idle", // idle | loading | partners | referrals | done
  live: false,
  partners: {}, // srcAffiliateId -> toltPartnerId
  customers: {}, // refId -> toltCustomerId
  transactions: {}, // refId -> true
  commissions: {}, // refId -> true
  cursorPartners: 0,
  cursorReferrals: 0,
  counts: {
    affiliates: 0,
    referrals: 0,
    partners: { created: 0, skipped: 0, failed: 0 },
    customers: { created: 0, skipped: 0, failed: 0 },
    transactions: { created: 0, skipped: 0, failed: 0 },
    commissions: { created: 0, skipped: 0, failed: 0 },
  },
  errors: [],
  startedAt: null,
  updatedAt: null,
});

// ---------- small helpers ----------

const json = (obj, status = 200) =>
  new Response(JSON.stringify(obj, null, 2), {
    status,
    headers: { "content-type": "application/json" },
  });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function pick(obj, keys, fallback = undefined) {
  if (!obj) return fallback;
  for (const k of keys) {
    const v = obj[k];
    if (v !== undefined && v !== null && v !== "") return v;
  }
  return fallback;
}

function firstArray(obj) {
  if (Array.isArray(obj)) return obj;
  if (!obj || typeof obj !== "object") return null;
  for (const k of Object.keys(obj)) if (Array.isArray(obj[k])) return obj[k];
  for (const k of Object.keys(obj))
    if (obj[k] && typeof obj[k] === "object") {
      const n = firstArray(obj[k]);
      if (n) return n;
    }
  return null;
}

function splitName(full, firstFallback, lastFallback = "(n/a)") {
  const name = (full || "").trim();
  if (!name) return { first_name: firstFallback || "Partner", last_name: lastFallback };
  const parts = name.split(/\s+/);
  if (parts.length === 1) return { first_name: parts[0], last_name: lastFallback };
  return { first_name: parts[0], last_name: parts.slice(1).join(" ") };
}

function toCents(value, alreadyCents) {
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  return alreadyCents ? Math.round(n) : Math.round(n * 100);
}

function mapCustomerStatus(raw) {
  const s = String(raw || "").toLowerCase();
  if (["active", "paid", "converted", "completed", "approved", "subscribed"].includes(s)) return "active";
  if (["trial", "trialing"].includes(s)) return "trialing";
  if (["canceled", "cancelled", "refunded", "churned"].includes(s)) return "canceled";
  return "lead";
}

// ---------- field resolvers (normalize unknown PromoteKit shapes) ----------

const affId = (a) => pick(a, ["id", "affiliate_id", "uuid", "_id", "reference"]);
const affEmail = (a) => pick(a, ["email", "affiliate_email", "user_email", "contact_email"]);
const affName = (a) => pick(a, ["name", "full_name", "affiliate_name", "display_name"]);
const affFirst = (a) => pick(a, ["first_name", "firstName", "given_name"]);
const affLast = (a) => pick(a, ["last_name", "lastName", "family_name", "surname"]);
const affCompany = (a) => pick(a, ["company", "company_name", "business_name"]);
const affCountry = (a) => pick(a, ["country_code", "country", "countryCode"]);
const affPaypal = (a) => pick(a, ["paypal_email", "paypal", "payout_email"]);

const refId = (r) => pick(r, ["id", "referral_id", "uuid", "_id"]);
const refAffId = (r) => pick(r, ["affiliate_id", "affiliateId", "affiliate", "partner_id"]);
const refEmail = (r) => pick(r, ["email", "customer_email", "referral_email", "lead_email", "user_email"]);
const refName = (r) => pick(r, ["name", "customer_name", "full_name"]);
const refStatus = (r) => pick(r, ["status", "state", "stage"]);
const refCreated = (r) => pick(r, ["created_at", "createdAt", "created", "referred_at", "date"]);
const refSale = (r) => pick(r, ["amount", "sale_amount", "revenue", "total", "purchase_amount", "mrr"]);
const refComm = (r) => pick(r, ["commission", "commission_amount", "earnings", "reward", "payout"]);
const refExtCustomer = (r) => pick(r, ["customer_id", "stripe_customer_id", "external_id"]);

// ---------- HTTP with one retry on 429/5xx ----------

async function apiRequest(url, { method = "GET", headers = {}, body } = {}) {
  for (let attempt = 1; attempt <= 3; attempt++) {
    const res = await fetch(url, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
    const text = await res.text();
    let data;
    try {
      data = text ? JSON.parse(text) : {};
    } catch {
      data = { raw: text };
    }
    if (res.ok) return data;
    if ((res.status === 429 || res.status >= 500) && attempt < 3) {
      await sleep(1000 * attempt);
      continue;
    }
    const err = new Error(`HTTP ${res.status} ${method} ${url} :: ${JSON.stringify(data).slice(0, 300)}`);
    err.status = res.status;
    err.body = data;
    throw err;
  }
}

// ---------- PromoteKit (source) ----------

function pkHeaders(env) {
  return {
    Authorization: `Bearer ${env.PROMOTEKIT_API_KEY}`,
    "Content-Type": "application/json",
    Accept: "application/json",
  };
}

async function pkFetchAll(env, path) {
  const base = (env.PROMOTEKIT_BASE_URL || "https://www.promotekit.com/api/v1").replace(/\/$/, "");
  const pageSize = 100;
  const all = [];
  let page = 1;
  while (true) {
    const u = new URL(base + path);
    u.searchParams.set("limit", pageSize);
    u.searchParams.set("page", page);
    const body = await apiRequest(u.toString(), { headers: pkHeaders(env) });
    const records = firstArray(body) || [];
    all.push(...records);
    if (records.length < pageSize || records.length === 0) break;
    page++;
    if (page > 5000) break;
  }
  return all;
}

// ---------- Tolt (destination) ----------

function toltHeaders(env) {
  return {
    Authorization: `Bearer ${env.TOLT_API_KEY}`,
    "Content-Type": "application/json",
    Accept: "application/json",
  };
}

function toltUrl(env, path) {
  return (env.TOLT_BASE_URL || "https://api.tolt.com/v1").replace(/\/$/, "") + path;
}

function unwrap(body) {
  const data = body && body.data !== undefined ? body.data : body;
  return Array.isArray(data) ? data[0] : data;
}

const toltCreatedId = (obj) => pick(obj, ["id", "uuid", "_id"]);

async function toltCreate(env, path, payload) {
  const body = await apiRequest(toltUrl(env, path), {
    method: "POST",
    headers: toltHeaders(env),
    body: payload,
  });
  return unwrap(body);
}

// ---------- state in KV ----------

async function loadState(env) {
  const raw = await env.MIGRATION_KV.get(STATE_KEY);
  return raw ? JSON.parse(raw) : EMPTY_STATE();
}
async function saveState(env, state) {
  state.updatedAt = new Date().toISOString();
  await env.MIGRATION_KV.put(STATE_KEY, JSON.stringify(state));
}

// ---------- migration steps ----------

async function doLoad(env, state, live) {
  const fresh = EMPTY_STATE();
  fresh.phase = "loading";
  fresh.live = live;
  fresh.startedAt = new Date().toISOString();
  await saveState(env, fresh);

  const affiliates = await pkFetchAll(env, env.PK_AFFILIATES_PATH || "/affiliates");
  let referrals = [];
  try {
    referrals = await pkFetchAll(env, env.PK_REFERRALS_PATH || "/referrals");
  } catch (e) {
    fresh.errors.push({ stage: "load-referrals", error: e.message });
  }

  await env.MIGRATION_KV.put(AFFILIATES_KEY, JSON.stringify(affiliates));
  await env.MIGRATION_KV.put(REFERRALS_KEY, JSON.stringify(referrals));

  fresh.counts.affiliates = affiliates.length;
  fresh.counts.referrals = referrals.length;
  fresh.phase = "partners";
  await saveState(env, fresh);
  return fresh;
}

async function processBatch(env) {
  const state = await loadState(env);
  if (state.phase === "idle" || state.phase === "done") return state;

  const batchSize = Number(env.BATCH_SIZE || 15);
  const amountsInCents = String(env.PK_AMOUNTS_IN_CENTS || "false") === "true";
  const programId = env.TOLT_PROGRAM_ID;
  const dryRun = !state.live;

  if (state.phase === "partners") {
    const affiliates = JSON.parse((await env.MIGRATION_KV.get(AFFILIATES_KEY)) || "[]");
    const end = Math.min(state.cursorPartners + batchSize, affiliates.length);
    for (let i = state.cursorPartners; i < end; i++) {
      const aff = affiliates[i];
      const srcId = affId(aff) || affEmail(aff);
      if (!srcId) {
        state.counts.partners.failed++;
        continue;
      }
      if (state.partners[srcId]) {
        state.counts.partners.skipped++;
        continue;
      }
      const email = affEmail(aff);
      if (!email) {
        state.counts.partners.failed++;
        state.errors.push({ stage: "partner", reason: "no email", srcId });
        continue;
      }
      let first = affFirst(aff);
      let last = affLast(aff);
      if (!first && !last) ({ first_name: first, last_name: last } = splitName(affName(aff), email.split("@")[0]));
      if (!last) last = "(n/a)";

      const payload = { first_name: first, last_name: last, email, program_id: programId };
      const company = affCompany(aff);
      if (company) payload.company_name = company;
      const country = affCountry(aff);
      if (country) payload.country_code = country;
      const paypal = affPaypal(aff);
      if (paypal) {
        payload.payout_method = "paypal";
        payload.payout_details = paypal;
      }

      if (dryRun) {
        state.partners[srcId] = `DRYRUN:${email}`;
        state.counts.partners.created++;
        continue;
      }
      try {
        const created = await toltCreate(env, "/partners", payload);
        state.partners[srcId] = toltCreatedId(created);
        state.counts.partners.created++;
      } catch (e) {
        const msg = JSON.stringify(e.body || e.message).toLowerCase();
        if (e.status === 409 || msg.includes("exist")) {
          state.partners[srcId] = `EXISTS:${email}`;
          state.counts.partners.skipped++;
        } else {
          state.counts.partners.failed++;
          state.errors.push({ stage: "partner", email, error: e.message });
        }
      }
      await sleep(150);
    }
    state.cursorPartners = end;
    if (state.cursorPartners >= affiliates.length) state.phase = "referrals";
    await saveState(env, state);
    return state;
  }

  if (state.phase === "referrals") {
    const referrals = JSON.parse((await env.MIGRATION_KV.get(REFERRALS_KEY)) || "[]");
    const end = Math.min(state.cursorReferrals + batchSize, referrals.length);
    for (let i = state.cursorReferrals; i < end; i++) {
      const ref = referrals[i];
      const rId = refId(ref) || `${refAffId(ref)}:${refEmail(ref)}`;
      const srcAffId = refAffId(ref);
      const partnerId = srcAffId ? state.partners[srcAffId] : undefined;
      const email = refEmail(ref);

      if (!partnerId || !email) {
        state.counts.customers.failed++;
        state.errors.push({ stage: "customer", reason: !email ? "no email" : "unmapped affiliate", rId });
        continue;
      }
      const realPartner = partnerId && !/^(DRYRUN|EXISTS):/.test(partnerId);

      // customer
      let customerId = state.customers[rId];
      if (!customerId) {
        const payload = { email, status: mapCustomerStatus(refStatus(ref)) };
        if (realPartner) payload.partner_id = partnerId;
        const nm = refName(ref);
        if (nm) payload.name = nm;
        const created = refCreated(ref);
        if (created) payload.created_at = new Date(created).toISOString();
        const ext = refExtCustomer(ref);
        if (ext) payload.customer_id = String(ext);

        if (dryRun) {
          customerId = `DRYRUN:${email}`;
          state.customers[rId] = customerId;
          state.counts.customers.created++;
        } else if (!realPartner) {
          state.counts.customers.failed++;
          state.errors.push({ stage: "customer", reason: "partner not real id", rId });
          continue;
        } else {
          try {
            const c = await toltCreate(env, "/customers", payload);
            customerId = toltCreatedId(c);
            state.customers[rId] = customerId;
            state.counts.customers.created++;
          } catch (e) {
            state.counts.customers.failed++;
            state.errors.push({ stage: "customer", email, error: e.message });
            continue;
          }
          await sleep(150);
        }
      } else {
        state.counts.customers.skipped++;
      }
      const realCustomer = customerId && !/^DRYRUN:/.test(customerId);

      // transaction
      const sale = refSale(ref);
      if (sale !== undefined && sale !== null && sale !== "" && Number(sale) > 0 && !state.transactions[rId]) {
        const cents = toCents(sale, amountsInCents);
        if (dryRun) {
          state.transactions[rId] = true;
          state.counts.transactions.created++;
        } else if (realCustomer && cents) {
          const payload = { amount: cents, customer_id: customerId };
          const created = refCreated(ref);
          if (created) payload.created_at = new Date(created).toISOString();
          try {
            await toltCreate(env, "/transactions", payload);
            state.transactions[rId] = true;
            state.counts.transactions.created++;
          } catch (e) {
            state.counts.transactions.failed++;
            state.errors.push({ stage: "transaction", email, error: e.message });
          }
          await sleep(150);
        }
      }

      // commission
      const comm = refComm(ref);
      if (comm !== undefined && comm !== null && comm !== "" && Number(comm) > 0 && !state.commissions[rId]) {
        const cents = toCents(comm, amountsInCents);
        if (dryRun) {
          state.commissions[rId] = true;
          state.counts.commissions.created++;
        } else if (realCustomer && cents) {
          const payload = { amount: cents, customer_id: customerId };
          const saleCents = toCents(sale, amountsInCents);
          if (saleCents) payload.revenue = saleCents;
          const created = refCreated(ref);
          if (created) payload.created_at = new Date(created).toISOString();
          try {
            await toltCreate(env, "/commissions", payload);
            state.commissions[rId] = true;
            state.counts.commissions.created++;
          } catch (e) {
            state.counts.commissions.failed++;
            state.errors.push({ stage: "commission", email, error: e.message });
          }
          await sleep(150);
        }
      }
    }
    state.cursorReferrals = end;
    if (state.cursorReferrals >= referrals.length) state.phase = "done";
    await saveState(env, state);
    return state;
  }

  return state;
}

// ---------- request routing ----------

function authorized(url, env) {
  return env.MIGRATION_SECRET && url.searchParams.get("token") === env.MIGRATION_SECRET;
}

async function inspect(env) {
  const out = {};
  try {
    const affiliates = await pkFetchAll(env, env.PK_AFFILIATES_PATH || "/affiliates");
    out.affiliateCount = affiliates.length;
    out.sampleAffiliate = affiliates[0] || null;
    out.affiliateKeys = affiliates[0] ? Object.keys(affiliates[0]) : [];
  } catch (e) {
    out.affiliateError = e.message;
  }
  try {
    const referrals = await pkFetchAll(env, env.PK_REFERRALS_PATH || "/referrals");
    out.referralCount = referrals.length;
    out.sampleReferral = referrals[0] || null;
    out.referralKeys = referrals[0] ? Object.keys(referrals[0]) : [];
  } catch (e) {
    out.referralError = e.message;
  }
  return out;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (path === "/" || path === "") {
      return json({
        service: "PromoteKit -> Tolt migration worker",
        endpoints: {
          "GET /status?token=...": "progress",
          "GET /inspect?token=...": "sample source data (writes nothing)",
          "POST /start?live=0&token=...": "begin DRY RUN",
          "POST /start?live=1&token=...": "begin LIVE migration",
          "POST /run?token=...": "process one batch now",
          "POST /reset?token=...": "clear progress",
        },
      });
    }

    if (!authorized(url, env)) return json({ error: "unauthorized: missing or wrong ?token" }, 401);

    if (!env.MIGRATION_KV) return json({ error: "KV namespace MIGRATION_KV is not bound" }, 500);

    try {
      if (path === "/status") return json(await loadState(env));

      if (path === "/inspect") return json(await inspect(env));

      if (path === "/start" && request.method === "POST") {
        if (!env.PROMOTEKIT_API_KEY || !env.TOLT_API_KEY || !env.TOLT_PROGRAM_ID)
          return json({ error: "Missing PROMOTEKIT_API_KEY, TOLT_API_KEY or TOLT_PROGRAM_ID" }, 400);
        const live = url.searchParams.get("live") === "1" || url.searchParams.get("live") === "true";
        const state = await doLoad(env, null, live);
        return json({
          message: `Loaded ${state.counts.affiliates} affiliates and ${state.counts.referrals} referrals. ` +
            `Mode: ${live ? "LIVE" : "DRY RUN"}. The cron trigger will now process batches every minute, ` +
            `or POST /run to push a batch immediately.`,
          state,
        });
      }

      if (path === "/run" && request.method === "POST") {
        return json(await processBatch(env));
      }

      if (path === "/reset" && request.method === "POST") {
        await env.MIGRATION_KV.put(STATE_KEY, JSON.stringify(EMPTY_STATE()));
        return json({ message: "Progress cleared." });
      }

      return json({ error: "not found", path }, 404);
    } catch (e) {
      return json({ error: e.message, stack: e.stack }, 500);
    }
  },

  // Cron Trigger: drain one batch per minute until done.
  async scheduled(event, env, ctx) {
    ctx.waitUntil(processBatch(env));
  },
};
