// Tolt (destination) API client. Creates partners, customers, transactions
// and commissions. Endpoints/fields per https://docs.tolt.com.

import { config } from "./config.mjs";
import { request, pick } from "./util.mjs";

function headers() {
  return {
    Authorization: `Bearer ${config.toltApiKey}`,
    "Content-Type": "application/json",
    Accept: "application/json",
  };
}

const u = (p) => config.toltBaseUrl.replace(/\/$/, "") + p;

/** Unwrap Tolt's { success, data } envelope and return the created object. */
function unwrap(body) {
  const data = body && body.data !== undefined ? body.data : body;
  return Array.isArray(data) ? data[0] : data;
}

export async function createPartner(payload) {
  const body = await request(u("/partners"), {
    method: "POST",
    headers: headers(),
    body: payload,
  });
  return unwrap(body);
}

export async function createCustomer(payload) {
  const body = await request(u("/customers"), {
    method: "POST",
    headers: headers(),
    body: payload,
  });
  return unwrap(body);
}

export async function createTransaction(payload) {
  const body = await request(u("/transactions"), {
    method: "POST",
    headers: headers(),
    body: payload,
  });
  return unwrap(body);
}

export async function createCommission(payload) {
  const body = await request(u("/commissions"), {
    method: "POST",
    headers: headers(),
    body: payload,
  });
  return unwrap(body);
}

/** Extract an id from a created Tolt object regardless of envelope quirks. */
export const toltId = (obj) => pick(obj, ["id", "uuid", "_id"]);
