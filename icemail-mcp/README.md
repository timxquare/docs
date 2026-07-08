# Icemail MCP Server

A remote [Model Context Protocol](https://modelcontextprotocol.io) server that exposes Icemail's cold-email infrastructure — mailboxes, domains, DNS health, and provisioning — as tools that AI assistants (Claude, Cursor, ChatGPT, and any MCP client) can call.

It runs on **Cloudflare Workers** and is served at **`https://mcp.icemail.ai`**.

- **Streamable HTTP** (recommended): `https://mcp.icemail.ai/mcp`
- **SSE** (legacy clients): `https://mcp.icemail.ai/sse`

Each user authenticates with **their own Icemail API key**, passed as `Authorization: Bearer <key>`. The Worker forwards that key to the Icemail REST API — it holds no shared server-side secret and stores nothing.

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
   │  Authorization: Bearer <ICEMAIL_API_KEY>
   ▼
mcp.icemail.ai  (Cloudflare Worker — this repo)
   │  forwards the same key
   ▼
Icemail REST API  (ICEMAIL_API_BASE)
```

The Worker (`src/index.ts`) reads the bearer key off each request, hands it to the `McpAgent` session via `ctx.props`, and every tool calls the Icemail API on the user's behalf.

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
