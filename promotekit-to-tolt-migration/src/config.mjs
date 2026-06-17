// Central configuration. Reads from environment variables (loaded from .env)
// and command-line flags. Everything that might differ between accounts or
// that you may need to tweak lives here.

import { loadEnv } from "./util.mjs";

loadEnv();

const args = process.argv.slice(2);
const hasFlag = (name) => args.includes(name);
const flagValue = (name, fallback) => {
  const i = args.indexOf(name);
  return i !== -1 && args[i + 1] ? args[i + 1] : fallback;
};

const bool = (v, def = false) => {
  if (v === undefined) return def;
  return ["1", "true", "yes", "on"].includes(String(v).toLowerCase());
};

export const config = {
  // ---- Credentials (required) ----
  promotekitApiKey: process.env.PROMOTEKIT_API_KEY || "",
  toltApiKey: process.env.TOLT_API_KEY || "",
  // Every imported affiliate joins this Tolt program (required by Tolt).
  toltProgramId: process.env.TOLT_PROGRAM_ID || "",
  // Optional: assign all imported partners to one Tolt group.
  toltGroupId: process.env.TOLT_GROUP_ID || "",

  // ---- Base URLs ----
  promotekitBaseUrl:
    process.env.PROMOTEKIT_BASE_URL || "https://www.promotekit.com/api/v1",
  toltBaseUrl: process.env.TOLT_BASE_URL || "https://api.tolt.com/v1",

  // ---- Run mode ----
  // Dry run is the DEFAULT. Pass --live to actually write data into Tolt.
  dryRun: !hasFlag("--live"),
  inspect: hasFlag("--inspect"), // probe source API and print shapes, then exit
  reset: hasFlag("--reset"), // ignore/overwrite saved state and start fresh
  limit: flagValue("--limit", null), // cap number of affiliates (for testing)

  // ---- Source (PromoteKit) endpoint paths, relative to base URL ----
  // These are made configurable because PromoteKit's public docs do not
  // expose the exact paths/field names. Run with --inspect to verify, then
  // adjust here or via env vars if needed.
  pkEndpoints: {
    affiliates: process.env.PK_AFFILIATES_PATH || "/affiliates",
    // Global referrals list (preferred). If your account exposes referrals
    // only per-affiliate, set PK_REFERRALS_PER_AFFILIATE_PATH and the script
    // will fall back to it (the {id} token is replaced per affiliate).
    referrals: process.env.PK_REFERRALS_PATH || "/referrals",
    referralsPerAffiliate:
      process.env.PK_REFERRALS_PER_AFFILIATE_PATH || "/affiliates/{id}/referrals",
  },

  // ---- Amount handling ----
  // Tolt stores money in integer CENTS. Set this true if PromoteKit already
  // returns amounts in cents; leave false if it returns dollars/decimals.
  sourceAmountsInCents: bool(process.env.PK_AMOUNTS_IN_CENTS, false),

  // ---- Pagination & throttling ----
  pageSize: Number(process.env.PAGE_SIZE || 100),
  // Delay between Tolt writes (ms). PromoteKit allows 200 req/min; keep a
  // gentle pace to stay well under any limit on either side.
  writeDelayMs: Number(process.env.WRITE_DELAY_MS || 350),

  // ---- File paths ----
  stateFile: process.env.STATE_FILE || "migration-state.json",
  reportFile: process.env.REPORT_FILE || "migration-report.json",
};

export function validateConfig() {
  const missing = [];
  if (!config.promotekitApiKey) missing.push("PROMOTEKIT_API_KEY");
  if (!config.toltApiKey) missing.push("TOLT_API_KEY");
  if (!config.toltProgramId) missing.push("TOLT_PROGRAM_ID");
  if (missing.length) {
    throw new Error(
      `Missing required configuration: ${missing.join(", ")}. ` +
        `Copy .env.example to .env and fill these in.`
    );
  }
}
