// Customer.io Behavioral Tracking (Track) API helpers.
//
// Keeps the Icemail workspace's rule-based segments (Paid / Churned / Free
// Trial) in sync with Stripe. Two operations:
//   - cioIdentify:     create/refresh a profile (signup). No payment => Free Trial.
//   - cioTrackPayment: record a `payment` event. The segments key on this event.
//
// Segment logic (defined in Customer.io, not here):
//   Paid       = performed `payment` in the last 45 days (rolling)
//   Churned    = performed `payment` ever, but not in the last 45 days
//   Free Trial = never performed `payment`
//
// Auth: HTTP Basic with the workspace's Tracking *Site ID* + *Track API Key*
// (Customer.io -> Settings -> API Credentials -> Tracking API Keys). These are
// NOT the same as the app/Bearer keys.
//
// Identity: we key every profile on its lowercased email (only the four
// approved fields are ever written: first name, last name, email, signup date).

function trackBase(env) {
  return (env.CIO_REGION || "us").toLowerCase() === "eu"
    ? "https://track-eu.customer.io"
    : "https://track.customer.io";
}

function authHeader(env) {
  return "Basic " + btoa(`${env.CIO_SITE_ID}:${env.CIO_TRACK_API_KEY}`);
}

// Split a Stripe `name` into first/last, matching how the profiles were seeded.
export function splitName(name) {
  if (!name) return { first_name: "", last_name: "" };
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return { first_name: "", last_name: "" };
  if (parts.length === 1) return { first_name: parts[0], last_name: "" };
  return { first_name: parts[0], last_name: parts.slice(1).join(" ") };
}

// Create or update a person. Writes ONLY the four approved fields.
// `createdAt` is the Stripe customer `created` unix timestamp = signup date.
export async function cioIdentify(env, { email, name, createdAt }) {
  if (!email) return;
  const id = email.trim().toLowerCase();
  const { first_name, last_name } = splitName(name);
  const attributes = { email: id, first_name, last_name };
  if (createdAt) attributes.created_at = Math.floor(createdAt);

  const res = await fetch(
    `${trackBase(env)}/api/v1/customers/${encodeURIComponent(id)}`,
    {
      method: "PUT",
      headers: {
        Authorization: authHeader(env),
        "Content-Type": "application/json",
      },
      body: JSON.stringify(attributes),
    }
  );
  if (!res.ok) {
    throw new Error(`CIO identify failed: ${res.status} ${await res.text()}`);
  }
}

// Record a payment. `timestamp` (unix seconds) is honored, so backfilled
// historical charges land at their real date and Churned vs Paid is correct.
export async function cioTrackPayment(env, { email, timestamp }) {
  if (!email) return;
  const id = email.trim().toLowerCase();
  const body = { name: "payment" };
  if (timestamp) body.timestamp = Math.floor(timestamp);

  const res = await fetch(
    `${trackBase(env)}/api/v1/customers/${encodeURIComponent(id)}/events`,
    {
      method: "POST",
      headers: {
        Authorization: authHeader(env),
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    }
  );
  if (!res.ok) {
    throw new Error(`CIO payment event failed: ${res.status} ${await res.text()}`);
  }
}
