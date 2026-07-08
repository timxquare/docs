# Icemail MCP Server

A remote [Model Context Protocol](https://modelcontextprotocol.io) server that exposes Icemail's cold-email infrastructure — mailboxes, domains, DNS health, and provisioning — as tools that AI assistants (Claude, Cursor, ChatGPT, and any MCP client) can call.

It runs on **Cloudflare Workers** and is served at **`https://mcp.icemail.ai`**.

- **Streamable HTTP** (recommended): `https://mcp.icemail.ai/mcp`
- **SSE** (legacy clients): `https://mcp.icemail.ai/sse`

Each user authenticates with **their own Icemail API key**, passed as `Authorization: Bearer <key>`. The Worker forwards that key to the Icemail REST API — it holds no shared server-side secret and stores nothing.

It is **multi-tenant**: one Worker serves every whitelabel customer, each on their own hostname with their own API base URL. See [Whitelabel / multi-tenant](#whitelabel--multi-tenant).

---

## Tools

| Tool | What it does |
|------|--------------|
| `get_account` | Account, workspace, plan, balance, usage (also confirms the key works) |
| `list_workspaces` | Workspaces the account can access |
| `get_usage` | Live pay-as-you-go spend for the current period |
| `list_domains` | Connected domains + DNS/deliverability status |
| `get_domain` | One domain's full record (SPF/DKIM/DMARC/MX, mailbox count) |
| `check_domain_dns` | Re-verify live DNS propagation for a domain |
| `find_domains` | AI domain finder — available sending domains for a brand/keyword |
| `list_mailboxes` | Provisioned mailboxes with provider, warmup, health |
| `get_mailbox` | One mailbox's details and reputation signals |
| `provision_mailboxes` | **Paid** — order new mailboxes on a domain |
| `export_mailboxes` | Export credentials for Instantly / Smartlead / Lemlist / CSV / JSON |

> **API endpoint mapping.** The tools call REST paths like `/v1/mailboxes` and `/v1/domains` (see `src/index.ts`). If the live Icemail API uses different paths or field names, adjust the `icemailFetch(...)` calls in each tool — the transport, auth, and hosting layers stay the same.

---

## Hosting on Cloudflare Workers

### Prerequisites

- A Cloudflare account with the **`icemail.ai`** zone already active on it.
- [Node.js](https://nodejs.org) 18+ and npm.

### 1. Install and authenticate

```bash
cd icemail-mcp
npm install
npx wrangler login
```

### 2. Deploy

```bash
npm run deploy
```

On the first deploy, Wrangler reads `wrangler.toml` and:

- Creates the `IcemailMCP` Durable Object (each MCP session lives in one).
- Attaches the custom domain **`mcp.icemail.ai`** — it adds the DNS record and provisions the TLS certificate automatically because the `icemail.ai` zone is on the same account. (Cert issuance can take a minute or two on the very first deploy.)

That's it — there are **no secrets to set**. The `ICEMAIL_API_BASE` var in `wrangler.toml` (default `https://api.icemail.ai`) is the only configuration, and auth is per-user via the request header.

### 3. Verify

```bash
curl https://mcp.icemail.ai/health
# {"ok":true,"service":"icemail-mcp"}
```

Then open the [MCP Inspector](https://github.com/modelcontextprotocol/inspector) against it:

```bash
npx @modelcontextprotocol/inspector
# Transport: Streamable HTTP
# URL:       https://mcp.icemail.ai/mcp
# Header:    Authorization: Bearer <your Icemail API key>
```

### Local development

```bash
npm run dev          # wrangler dev on http://localhost:8787
```

Copy `.dev.vars.example` to `.dev.vars` only if you need to point the tools at a local/staging Icemail API. Test with the Inspector against `http://localhost:8787/mcp`.

---

## How it fits together

```
MCP client (Claude / Cursor / ChatGPT)
   │  Host: mcp.<customer>.com   +   Authorization: Bearer <API_KEY>
   ▼
one Cloudflare Worker (this repo)
   │  resolve tenant by Host  ──►  src/tenants.ts  { name, apiBase }
   │  forward the same key
   ▼
that tenant's REST API  (tenant.apiBase)
```

The Worker (`src/index.ts`) resolves the tenant from the request hostname, reads the bearer key off the request, and hands both to the `McpAgent` session via `ctx.props`. Every tool then calls **that tenant's** API on the user's behalf, and the MCP server reports **that tenant's** name to the client.

---

## Whitelabel / multi-tenant

You want many branded MCP servers — `mcp.acmemail.com`, `mcp.coldreach.io`, … — each pointing at a **different base URL**. This repo does that with **one Worker, routed by hostname**. No per-customer code fork.

### How it works

- **`src/tenants.ts`** is the registry: a map from hostname → `{ name, apiBase }`.
  - `name` — the MCP server name shown in the customer's AI client (their branding).
  - `apiBase` — the REST API base URL for that customer.
- Each hostname is also a **custom-domain route** on the Worker (`wrangler.toml`).
- On every request the Worker matches `Host` → tenant, and uses that tenant's `apiBase` and `name`.

### Onboard a new whitelabel customer

1. Add an entry to `src/tenants.ts`:
   ```ts
   "mcp.acmemail.com": { name: "Acme Mail", apiBase: "https://api.acmemail.com" },
   ```
2. Add a route in `wrangler.toml`:
   ```toml
   [[routes]]
   pattern = "mcp.acmemail.com"
   custom_domain = true
   ```
   The customer's zone (`acmemail.com`) must be active on this Cloudflare account so Wrangler can create the DNS record + TLS cert. (If it's on the customer's own Cloudflare account, add it there as a Worker route instead, or use the per-customer-Worker model below.)
3. `npm run deploy`.

That customer now connects at `https://mcp.acmemail.com/mcp` with their own API keys, and their client shows **“Acme Mail”**.

### Verify a tenant resolves

```bash
curl https://mcp.acmemail.com/health
# {"ok":true,"service":"icemail-mcp","tenant":"Acme Mail","host":"mcp.acmemail.com"}
```

### Scaling tenant config (zero-deploy onboarding)

The code map is simplest and fully reviewable. If you'd rather onboard customers **without a code deploy**, move the registry into a KV namespace and look it up by hostname:

1. `npx wrangler kv namespace create TENANTS` and bind it in `wrangler.toml`.
2. In `resolveTenant`, fall back to `await env.TENANTS.get(host, "json")` when the host isn't in the code map.
3. Onboard = `wrangler kv key put --binding TENANTS "mcp.acmemail.com" '{"name":"Acme Mail","apiBase":"https://api.acmemail.com"}'` + add the domain route.

You still add the custom-domain route per host (that's a Cloudflare routing requirement), but the tenant's config no longer requires a redeploy.

### Alternative: one Worker per customer (hard isolation)

Prefer full isolation — separate Worker, Durable Objects, logs, limits, even separate Cloudflare accounts per customer? Use **Wrangler environments** instead of the shared Worker:

```toml
# wrangler.toml
[env.acme]
name = "acme-mcp"
vars = { ICEMAIL_API_BASE = "https://api.acmemail.com" }
routes = [{ pattern = "mcp.acmemail.com", custom_domain = true }]

[env.coldreach]
name = "coldreach-mcp"
vars = { ICEMAIL_API_BASE = "https://api.coldreach.io" }
routes = [{ pattern = "mcp.coldreach.io", custom_domain = true }]
```

Deploy each independently:

```bash
npx wrangler deploy --env acme
npx wrangler deploy --env coldreach
```

| | Shared multi-tenant Worker (default) | One Worker per customer (environments) |
|---|---|---|
| Deploys | One, serves all | One per customer |
| Isolation | Shared runtime & logs | Fully separate Worker/DO/logs/limits |
| Onboarding | Add tenant entry + route (or KV, zero-deploy) | Add `[env.x]` block + deploy |
| Best for | Many customers, low ops | Few customers, strict isolation / separate billing |

Both use the exact same `src/index.ts` — the shared model reads `apiBase` from the tenant registry; the environments model reads it from each env's `ICEMAIL_API_BASE` (the built-in fallback). You can start multi-tenant and peel a big customer out into their own environment later without code changes.

---

## User install instructions

Share these with your users (also published at **https://docs.icemail.ai/mcp-server**).

Everyone connects to the same URL — `https://mcp.icemail.ai/mcp` — with their **own** Icemail API key from **app.icemail.ai → Settings → API**.

**Claude Code**

```bash
claude mcp add --transport http icemail https://mcp.icemail.ai/mcp \
  --header "Authorization: Bearer YOUR_ICEMAIL_API_KEY"
```

**Claude Desktop / Cursor / Windsurf** (`mcpServers` config):

```json
{
  "mcpServers": {
    "icemail": {
      "url": "https://mcp.icemail.ai/mcp",
      "headers": { "Authorization": "Bearer YOUR_ICEMAIL_API_KEY" }
    }
  }
}
```

For clients that only support local (stdio) MCP servers, bridge with [`mcp-remote`](https://www.npmjs.com/package/mcp-remote):

```json
{
  "mcpServers": {
    "icemail": {
      "command": "npx",
      "args": [
        "-y", "mcp-remote", "https://mcp.icemail.ai/mcp",
        "--header", "Authorization: Bearer YOUR_ICEMAIL_API_KEY"
      ]
    }
  }
}
```
