# PromoteKit → Tolt migration (Cloudflare Worker)

The same migration as the standalone script, packaged as a **Cloudflare
Worker** so it runs on Cloudflare alongside your `stripe-webhook` — nothing
to install on your own computer beyond the Cloudflare CLI.

| PromoteKit          | →   | Tolt          |
| ------------------- | --- | ------------- |
| Affiliates (users)  | →   | Partners      |
| Referrals           | →   | Customers     |
| Referred sales      | →   | Transactions  |
| Affiliate earnings  | →   | Commissions   |

**How it works:** progress is stored in Cloudflare **KV**, so the job is
resumable. A **Cron Trigger** runs every minute and processes the next small
batch automatically until everything is migrated. You start, monitor, and
control it by visiting a few URLs protected with a secret password. It is
**safe by default** — the first run is a dry run that writes nothing.

---

## One-time setup

You'll use Cloudflare's `wrangler` command line. You don't need to install it
globally — `npx wrangler ...` downloads it on demand.

### 1. Log in to Cloudflare
```bash
cd promotekit-to-tolt-worker
npx wrangler login
```

### 2. Create the KV namespace (stores progress)
```bash
npx wrangler kv namespace create MIGRATION_KV
```
Copy the `id` it prints and paste it into `wrangler.toml`, replacing
`REPLACE_WITH_KV_ID`.

### 3. Fill in your Tolt program ID
In `wrangler.toml`, replace `REPLACE_WITH_TOLT_PROGRAM_ID` with your Tolt
program ID (Tolt dashboard → Programs).

### 4. Set the secrets
Run each of these; it will prompt you to paste the value:
```bash
npx wrangler secret put PROMOTEKIT_API_KEY    # PromoteKit → Settings → API Keys
npx wrangler secret put TOLT_API_KEY          # Tolt → Settings → Integrations
npx wrangler secret put MIGRATION_SECRET      # any random password you choose
```

### 5. Deploy
```bash
npx wrangler deploy
```
Wrangler prints your Worker URL, e.g.
`https://promotekit-to-tolt-migration.<your-subdomain>.workers.dev`.

---

## Running the migration

Replace `URL` with your Worker URL and `SECRET` with the `MIGRATION_SECRET`
you chose. You can paste the GET links into a browser; the POST ones are
easiest with `curl` in a terminal.

### 1. Check the connection (writes nothing)
Open in a browser:
```
URL/inspect?token=SECRET
```
You should see counts and a sample affiliate/referral. If you see a `404`
error here, your PromoteKit endpoint paths differ — update `PK_AFFILIATES_PATH`
/ `PK_REFERRALS_PATH` in `wrangler.toml` and redeploy.

### 2. Start a DRY RUN (writes nothing)
```bash
curl -X POST "URL/start?live=0&token=SECRET"
```
This loads all your data and begins simulating. Watch progress at:
```
URL/status?token=SECRET
```
The cron trigger advances it every minute. To push it along immediately:
```bash
curl -X POST "URL/run?token=SECRET"
```
When `status` shows `"phase": "done"`, review the `counts` — they should
roughly match your PromoteKit totals.

### 3. Run it for real
```bash
curl -X POST "URL/reset?token=SECRET"
curl -X POST "URL/start?live=1&token=SECRET"
```
Then watch `URL/status?token=SECRET` until `"phase": "done"`. The cron drains
it automatically; use `/run` if you want to go faster.

---

## Control endpoints

| Endpoint                         | Method | Purpose                          |
| -------------------------------- | ------ | -------------------------------- |
| `/status?token=...`              | GET    | Current phase + progress counts  |
| `/inspect?token=...`             | GET    | Sample source data (no writes)   |
| `/start?live=0&token=...`        | POST   | Load data, begin **dry run**     |
| `/start?live=1&token=...`        | POST   | Load data, begin **live** run    |
| `/run?token=...`                 | POST   | Process one batch immediately    |
| `/reset?token=...`               | POST   | Clear all saved progress         |

---

## Notes & limits

- **Batch size** (`BATCH_SIZE` in `wrangler.toml`, default 15) is how many
  records are processed per minute. Cloudflare's free plan allows 50
  subrequests per invocation, paid allows 1000 — 15 keeps you safely under
  either. Raise it on a paid plan to go faster.
- **Loading step:** `/start` pages through all of PromoteKit at once. For very
  large accounts (tens of thousands of records) this may exceed the free-plan
  subrequest limit; a paid Workers plan handles it comfortably.
- **Money** is stored in Tolt as cents. By default this assumes PromoteKit
  returns dollars and multiplies by 100. If yours is already in cents, set
  `PK_AMOUNTS_IN_CENTS = "true"` in `wrangler.toml`.
- **Idempotent & resumable:** every created record is remembered in KV, so
  re-running never double-creates. If something fails partway, just let the
  cron continue or call `/run` again.
- **When you're finished**, you can remove the cron by deleting the
  `[triggers]` block and redeploying, or delete the Worker entirely. Your
  `stripe-webhook` Worker is completely separate and unaffected.
