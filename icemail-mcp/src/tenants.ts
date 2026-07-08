/**
 * Whitelabel tenant registry.
 * ------------------------------------------------------------------
 * One Worker serves every whitelabel customer. Each customer gets their own
 * hostname (a Cloudflare custom domain pointing at this Worker) and their own
 * Icemail-compatible API base URL. Requests are routed to the right tenant by
 * the incoming `Host` header.
 *
 * To onboard a new whitelabel customer:
 *   1. Add an entry here, keyed by the exact hostname they'll connect to.
 *   2. Add a matching `[[routes]]` custom_domain block in wrangler.toml.
 *   3. `npm run deploy`.
 *
 * `name`    → the MCP server name shown in the customer's AI client (branding).
 * `apiBase` → the REST API this tenant's tools call (no trailing slash needed).
 *
 * For zero-deploy onboarding at larger scale, move this map into a KV namespace
 * and look it up by hostname instead — see README (“Scaling tenant config”).
 */

export interface Tenant {
  name: string;
  apiBase: string;
}

export const TENANTS: Record<string, Tenant> = {
  "mcp.icemail.ai": {
    name: "Icemail",
    apiBase: "https://api.icemail.ai",
  },

  // --- Whitelabel customers (examples — replace with real hosts + API bases) ---
  // "mcp.acmemail.com": {
  //   name: "Acme Mail",
  //   apiBase: "https://api.acmemail.com",
  // },
  // "mcp.coldreach.io": {
  //   name: "ColdReach",
  //   apiBase: "https://api.coldreach.io",
  // },
};
