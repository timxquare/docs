// Shared helpers: tiny .env loader, logging, HTTP with retry/backoff,
// field resolution, and JSON state persistence. No external dependencies.

import fs from "node:fs";
import path from "node:path";

const LOG_FILE = path.join(process.cwd(), "migration.log");

/** Minimal .env parser so users don't need to install `dotenv`. */
export function loadEnv(file = ".env") {
  const full = path.resolve(process.cwd(), file);
  if (!fs.existsSync(full)) return;
  const text = fs.readFileSync(full, "utf8");
  for (const rawLine of text.split("\n")) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq === -1) continue;
    const key = line.slice(0, eq).trim();
    let value = line.slice(eq + 1).trim();
    // Strip surrounding quotes if present.
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    if (!(key in process.env)) process.env[key] = value;
  }
}

const COLORS = {
  reset: "\x1b[0m",
  gray: "\x1b[90m",
  red: "\x1b[31m",
  green: "\x1b[32m",
  yellow: "\x1b[33m",
  cyan: "\x1b[36m",
};

function write(level, color, args) {
  const ts = new Date().toISOString();
  const msg = args
    .map((a) => (typeof a === "string" ? a : JSON.stringify(a)))
    .join(" ");
  // Console (colored) + plain log file.
  console.log(`${color}${level.padEnd(5)}${COLORS.reset} ${msg}`);
  try {
    fs.appendFileSync(LOG_FILE, `${ts} ${level.padEnd(5)} ${msg}\n`);
  } catch {
    /* logging must never crash the migration */
  }
}

export const log = {
  info: (...a) => write("INFO", COLORS.cyan, a),
  ok: (...a) => write("OK", COLORS.green, a),
  warn: (...a) => write("WARN", COLORS.yellow, a),
  error: (...a) => write("ERROR", COLORS.red, a),
  dim: (...a) => write("…", COLORS.gray, a),
};

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/**
 * HTTP request with automatic retry + exponential backoff for rate limits
 * (HTTP 429) and transient server errors (5xx). Returns the parsed JSON body.
 * Throws an Error (with .status and .body) for non-retryable failures.
 */
export async function request(url, opts = {}) {
  const {
    method = "GET",
    headers = {},
    body,
    maxRetries = 5,
    baseDelayMs = 2000,
  } = opts;

  let attempt = 0;
  // eslint-disable-next-line no-constant-condition
  while (true) {
    attempt++;
    let res;
    try {
      res = await fetch(url, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
      });
    } catch (networkErr) {
      // Network blip — retry with backoff.
      if (attempt > maxRetries) throw networkErr;
      const delay = baseDelayMs * 2 ** (attempt - 1);
      log.warn(`Network error (${networkErr.message}); retrying in ${delay}ms`);
      await sleep(delay);
      continue;
    }

    const text = await res.text();
    let json;
    try {
      json = text ? JSON.parse(text) : {};
    } catch {
      json = { raw: text };
    }

    if (res.ok) return json;

    // A definitive API rejection (JSON with success:false) won't change on
    // retry — fail fast. Only retry genuine transient conditions.
    const definitiveReject = json && json.success === false;
    const retryable = !definitiveReject && (res.status === 429 || res.status >= 500);
    if (retryable && attempt <= maxRetries) {
      // Honor Retry-After header if present, else exponential backoff.
      const retryAfter = Number(res.headers.get("retry-after"));
      const delay = Number.isFinite(retryAfter) && retryAfter > 0
        ? retryAfter * 1000
        : baseDelayMs * 2 ** (attempt - 1);
      log.warn(
        `${res.status} from ${method} ${url}; retrying in ${delay}ms (attempt ${attempt}/${maxRetries})`
      );
      await sleep(delay);
      continue;
    }

    const err = new Error(
      `HTTP ${res.status} ${method} ${url} :: ${JSON.stringify(json).slice(0, 500)}`
    );
    err.status = res.status;
    err.body = json;
    throw err;
  }
}

/** Return the first defined, non-null, non-empty value among candidate keys. */
export function pick(obj, candidates, fallback = undefined) {
  if (!obj) return fallback;
  for (const key of candidates) {
    const v = obj[key];
    if (v !== undefined && v !== null && v !== "") return v;
  }
  return fallback;
}

/** Find the first array-valued property of an object (used to locate the
 *  list of records inside an unknown API response envelope). */
export function firstArray(obj) {
  if (Array.isArray(obj)) return obj;
  if (!obj || typeof obj !== "object") return null;
  for (const key of Object.keys(obj)) {
    if (Array.isArray(obj[key])) return obj[key];
  }
  // One level deeper (e.g. { data: { affiliates: [...] } }).
  for (const key of Object.keys(obj)) {
    if (obj[key] && typeof obj[key] === "object") {
      const nested = firstArray(obj[key]);
      if (nested) return nested;
    }
  }
  return null;
}

/** Split a full name into { first_name, last_name }, with safe fallbacks
 *  because Tolt requires both fields. */
export function splitName(full, firstFallback, lastFallback = "(n/a)") {
  const name = (full || "").trim();
  if (!name) return { first_name: firstFallback || "Partner", last_name: lastFallback };
  const parts = name.split(/\s+/);
  if (parts.length === 1) return { first_name: parts[0], last_name: lastFallback };
  return { first_name: parts[0], last_name: parts.slice(1).join(" ") };
}

/** Convert a monetary value to integer cents (Tolt expects cents). */
export function toCents(value, alreadyCents) {
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  return alreadyCents ? Math.round(n) : Math.round(n * 100);
}

// ---- State persistence (resumable + idempotent migrations) ----

export function loadState(file) {
  const full = path.resolve(process.cwd(), file);
  if (!fs.existsSync(full)) {
    return { partners: {}, customers: {}, transactions: {}, commissions: {} };
  }
  try {
    return JSON.parse(fs.readFileSync(full, "utf8"));
  } catch {
    log.warn(`Could not parse state file ${file}; starting fresh.`);
    return { partners: {}, customers: {}, transactions: {}, commissions: {} };
  }
}

export function saveState(file, state) {
  const full = path.resolve(process.cwd(), file);
  fs.writeFileSync(full, JSON.stringify(state, null, 2));
}

/** Write a human-readable JSON summary report. */
export function writeReport(file, report) {
  const full = path.resolve(process.cwd(), file);
  fs.writeFileSync(full, JSON.stringify(report, null, 2));
}
