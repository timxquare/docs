/**
 * Icemail remote MCP server (multi-tenant / whitelabel)
 * ------------------------------------------------------------------
 * A Model Context Protocol server that exposes Icemail's cold-email
 * infrastructure (mailboxes, domains, DNS health, provisioning) as tools
 * that AI assistants — Claude, Cursor, ChatGPT, etc. — can call.
 *
 * ONE Worker serves EVERY whitelabel customer. Each customer connects on their
 * own hostname (a Cloudflare custom domain), and requests are routed to that
 * customer's API base URL by the incoming `Host` header. See src/tenants.ts.
 *   - Streamable HTTP transport:  https://<tenant-host>/mcp   (current standard)
 *   - SSE transport (legacy):     https://<tenant-host>/sse   (older clients)
 *
 * AUTH: each user connects with THEIR OWN API key, passed on every request as
 * `Authorization: Bearer <API_KEY>`. The Worker forwards that key to the
 * tenant's REST API — it stores nothing and has no shared server-side secret.
 *
 * NOTE ON ENDPOINTS: the REST paths below (`/v1/mailboxes`, `/v1/domains`, …)
 * reflect the expected shape of the Icemail API. If your live API uses
 * different paths or field names, adjust `icemailFetch(...)` calls in each
 * tool — the transport, auth, tenant-routing, and hosting layers do not change.
 */

import { McpAgent } from "agents/mcp";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { TENANTS, type Tenant } from "./tenants.js";

interface Env {
  // Default API base — used for localhost dev and any host not in the registry
  // that we still choose to serve (see resolveTenant).
  ICEMAIL_API_BASE: string;
  MCP_OBJECT: DurableObjectNamespace;
}

/** Per-connection context, injected per request (see fetch handler). */
type Props = {
  apiKey: string;
  /** The resolved tenant's API base URL for this connection. */
  apiBase: string;
  /** The resolved tenant's display name (whitelabel branding). */
  tenantName: string;
};

/** Thrown by icemailFetch when the request has no bearer key. */
class MissingKeyError extends Error {}

export class IcemailMCP extends McpAgent<Env, unknown, Props> {
  // Assigned in init() so the server name can be branded per whitelabel tenant.
  // Safe: McpAgent.onStart sets this.props and calls init() before reading this.server.
  server!: McpServer;

  /** Call the tenant's REST API with the caller's key. */
  private async icemailFetch(
    path: string,
    init: RequestInit & { query?: Record<string, string | number | boolean | undefined> } = {},
  ): Promise<unknown> {
    const apiKey = this.props?.apiKey;
    if (!apiKey) {
      throw new MissingKeyError(
        "No API key provided. Connect with an `Authorization: Bearer <key>` header. Create a key in your account settings under API.",
      );
    }

    const base = (this.props?.apiBase ?? this.env.ICEMAIL_API_BASE).replace(/\/$/, "");
    const url = new URL(base + path);
    for (const [k, v] of Object.entries(init.query ?? {})) {
      if (v !== undefined) url.searchParams.set(k, String(v));
    }

    const res = await fetch(url, {
      ...init,
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
        Accept: "application/json",
        "User-Agent": "icemail-mcp/1.0",
        ...(init.headers ?? {}),
      },
    });

    const text = await res.text();
    let body: unknown;
    try {
      body = text ? JSON.parse(text) : null;
    } catch {
      body = text;
    }

    if (!res.ok) {
      const detail = typeof body === "string" ? body : JSON.stringify(body);
      throw new Error(`Icemail API ${res.status} ${res.statusText}: ${detail}`);
    }
    return body;
  }

  /** Wrap a tool body so API/auth errors surface as readable tool errors. */
  private async run(fn: () => Promise<unknown>) {
    try {
      const data = await fn();
      return {
        content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }],
      };
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      return {
        content: [{ type: "text" as const, text: `Error: ${message}` }],
        isError: true,
      };
    }
  }

  async init() {
    // Brand the MCP server per whitelabel tenant (name shown in the AI client).
    this.server = new McpServer({
      name: this.props?.tenantName ?? "Icemail",
      version: "1.0.0",
    });

    // ---- Account -----------------------------------------------------------
    this.server.tool(
      "get_account",
      "Get the authenticated Icemail account: workspace, plan, balance, and usage. Use this to confirm the API key works and to check remaining credit before provisioning.",
      {},
      () => this.run(() => this.icemailFetch("/v1/me")),
    );

    this.server.tool(
      "list_workspaces",
      "List the workspaces the account can access. Icemail isolates each domain/client into its own workspace to prevent cascading bans.",
      {},
      () => this.run(() => this.icemailFetch("/v1/workspaces")),
    );

    this.server.tool(
      "get_usage",
      "Get current billing-period usage and cost breakdown (mailboxes, domains, add-ons). Pay-as-you-go, so this reflects live spend.",
      {},
      () => this.run(() => this.icemailFetch("/v1/usage")),
    );

    // ---- Domains -----------------------------------------------------------
    this.server.tool(
      "list_domains",
      "List domains connected to Icemail with their DNS/deliverability status.",
      {
        status: z
          .enum(["pending", "active", "error", "all"])
          .optional()
          .describe("Filter by domain status. Defaults to all."),
        workspace_id: z.string().optional().describe("Restrict to a single workspace."),
      },
      ({ status, workspace_id }) =>
        this.run(() =>
          this.icemailFetch("/v1/domains", {
            query: { status: status === "all" ? undefined : status, workspace_id },
          }),
        ),
    );

    this.server.tool(
      "get_domain",
      "Get one domain's full record: required vs. observed DNS (SPF, DKIM, DMARC, MX), workspace, and mailbox count.",
      {
        domain: z.string().describe("The domain name, e.g. `outbound-acme.com`."),
      },
      ({ domain }) =>
        this.run(() => this.icemailFetch(`/v1/domains/${encodeURIComponent(domain)}`)),
    );

    this.server.tool(
      "check_domain_dns",
      "Re-check live DNS propagation for a domain and report whether SPF, DKIM, DMARC, and MX are correctly configured. Use after editing DNS at the registrar.",
      {
        domain: z.string().describe("The domain to verify."),
      },
      ({ domain }) =>
        this.run(() =>
          this.icemailFetch(`/v1/domains/${encodeURIComponent(domain)}/dns/verify`, {
            method: "POST",
          }),
        ),
    );

    this.server.tool(
      "find_domains",
      "Use Icemail's AI domain finder to suggest available sending domains for a brand or keyword, with price and availability.",
      {
        query: z.string().describe("Brand name or keyword to base suggestions on, e.g. `acme`."),
        tlds: z
          .array(z.string())
          .optional()
          .describe("Preferred TLDs without the dot, e.g. [\"com\", \"co\", \"io\"]."),
        limit: z.number().int().min(1).max(50).optional().describe("Max suggestions (default 10)."),
      },
      ({ query, tlds, limit }) =>
        this.run(() =>
          this.icemailFetch("/v1/domains/search", {
            query: { q: query, tlds: tlds?.join(","), limit },
          }),
        ),
    );

    // ---- Mailboxes ---------------------------------------------------------
    this.server.tool(
      "list_mailboxes",
      "List provisioned mailboxes with provider, warmup state, and health. Filter by domain, workspace, or status.",
      {
        domain: z.string().optional().describe("Only mailboxes on this domain."),
        workspace_id: z.string().optional().describe("Only mailboxes in this workspace."),
        status: z
          .enum(["provisioning", "warming", "active", "paused", "error", "all"])
          .optional()
          .describe("Filter by mailbox status. Defaults to all."),
        limit: z.number().int().min(1).max(200).optional().describe("Page size (default 50)."),
      },
      ({ domain, workspace_id, status, limit }) =>
        this.run(() =>
          this.icemailFetch("/v1/mailboxes", {
            query: {
              domain,
              workspace_id,
              status: status === "all" ? undefined : status,
              limit,
            },
          }),
        ),
    );

    this.server.tool(
      "get_mailbox",
      "Get one mailbox: provider, credentials metadata, warmup progress, and reputation signals.",
      {
        mailbox_id: z.string().describe("The mailbox ID or full email address."),
      },
      ({ mailbox_id }) =>
        this.run(() =>
          this.icemailFetch(`/v1/mailboxes/${encodeURIComponent(mailbox_id)}`),
        ),
    );

    this.server.tool(
      "provision_mailboxes",
      "Order new mailboxes on a domain. THIS IS A PAID ACTION — it charges the account's pay-as-you-go balance. Always confirm the count, provider, and domain with the user before calling.",
      {
        domain: z.string().describe("Domain to create the mailboxes on (must be active in Icemail)."),
        provider: z
          .enum(["google", "microsoft", "azure", "imap"])
          .describe("Mailbox provider: google (Workspace $2.50/mo), microsoft (M365 $2/mo), azure ($29/domain/mo), imap ($49/domain/mo)."),
        count: z.number().int().min(1).max(50).describe("How many mailboxes to create (1–50 per call)."),
        first_names: z
          .array(z.string())
          .optional()
          .describe("Optional list of first names to base local-parts on (e.g. [\"john\", \"sarah\"])."),
        workspace_id: z.string().optional().describe("Target workspace; defaults to the domain's workspace."),
      },
      ({ domain, provider, count, first_names, workspace_id }) =>
        this.run(() =>
          this.icemailFetch("/v1/mailboxes", {
            method: "POST",
            body: JSON.stringify({ domain, provider, count, first_names, workspace_id }),
          }),
        ),
    );

    this.server.tool(
      "export_mailboxes",
      "Export mailbox sending credentials for a domain in a format ready to import into a sending platform (Instantly, Smartlead, or Lemlist), or as raw CSV/JSON.",
      {
        domain: z.string().describe("Domain whose mailboxes to export."),
        format: z
          .enum(["instantly", "smartlead", "lemlist", "csv", "json"])
          .describe("Target platform or raw format."),
      },
      ({ domain, format }) =>
        this.run(() =>
          this.icemailFetch("/v1/mailboxes/export", {
            method: "POST",
            body: JSON.stringify({ domain, format }),
          }),
        ),
    );
  }
}

/** Extract a bearer token from the Authorization header (or `?api_key=`). */
function extractApiKey(request: Request): string {
  const auth = request.headers.get("Authorization") ?? "";
  const bearer = auth.match(/^Bearer\s+(.+)$/i);
  if (bearer) return bearer[1].trim();
  // Some clients can only attach query params — accept ?api_key= as a fallback.
  return new URL(request.url).searchParams.get("api_key")?.trim() ?? "";
}

/**
 * Map the request hostname to a whitelabel tenant.
 * - Exact host match in the registry wins.
 * - localhost / 127.0.0.1 fall back to the default API base (for `wrangler dev`).
 * - Anything else is an unknown tenant → null (served as 404).
 */
function resolveTenant(host: string, env: Env): Tenant | null {
  const registered = TENANTS[host];
  if (registered) return registered;
  if (host === "localhost" || host === "127.0.0.1") {
    return { name: "Icemail (dev)", apiBase: env.ICEMAIL_API_BASE };
  }
  return null;
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    const { pathname } = url;
    const host = url.hostname.toLowerCase();

    const tenant = resolveTenant(host, env);

    if (!tenant) {
      return new Response(
        `Unknown tenant for host "${host}". This host is not registered in the whitelabel tenant registry.`,
        { status: 404, headers: { "Content-Type": "text/plain; charset=utf-8" } },
      );
    }

    // Inject the caller's key + resolved tenant so the agent reads them via this.props.
    // McpAgent reads `ctx.props` at runtime; the type marks it readonly, so cast.
    (ctx as { props?: Props }).props = {
      apiKey: extractApiKey(request),
      apiBase: tenant.apiBase,
      tenantName: tenant.name,
    };

    // Streamable HTTP transport — the current MCP standard.
    if (pathname === "/mcp") {
      return IcemailMCP.serve("/mcp").fetch(request, env, ctx);
    }

    // SSE transport — kept for older MCP clients.
    if (pathname === "/sse" || pathname === "/sse/message") {
      return IcemailMCP.serveSSE("/sse").fetch(request, env, ctx);
    }

    // Health check — also reports which tenant this host resolves to.
    if (pathname === "/health") {
      return Response.json({ ok: true, service: "icemail-mcp", tenant: tenant.name, host });
    }

    // Landing page for anyone who opens the URL in a browser.
    if (pathname === "/" || pathname === "") {
      return new Response(
        [
          `${tenant.name} MCP server`,
          "",
          "Connect an MCP client to one of:",
          `  https://${host}/mcp   (Streamable HTTP — recommended)`,
          `  https://${host}/sse   (SSE — legacy clients)`,
          "",
          "Authenticate with your API key:",
          "  Authorization: Bearer <API_KEY>",
        ].join("\n"),
        { headers: { "Content-Type": "text/plain; charset=utf-8" } },
      );
    }

    return new Response("Not found", { status: 404 });
  },
};
