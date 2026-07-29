# Stripe → Founder Welcome Email (Cloudflare Worker)

Listens for Stripe `customer.created` events and sends a personal welcome
email from your Google Workspace account (`tim@xquare.vc`) via the Gmail API.

Runs on Cloudflare Workers. No `.env` file in production — secrets live in
Cloudflare via `wrangler secret put`.

## Setup

```bash
cd stripe-webhook
npm install
npx wrangler login        # opens browser, authorizes your Cloudflare account
```

### 1. Set the secrets (production)

Run each command and paste the value when prompted:

```bash
npx wrangler secret put STRIPE_SECRET_KEY
npx wrangler secret put STRIPE_WEBHOOK_SECRET
npx wrangler secret put GMAIL_CLIENT_ID
npx wrangler secret put GMAIL_CLIENT_SECRET
npx wrangler secret put GMAIL_REFRESH_TOKEN
npx wrangler secret put GMAIL_SENDER_ADDRESS
```

(You can also set these in the Cloudflare dashboard:
Workers & Pages → your worker → Settings → Variables and Secrets.)

### 2. Deploy

```bash
npx wrangler deploy
```

Wrangler prints your worker URL, e.g.
`https://stripe-founder-email.<your-subdomain>.workers.dev`

### 3. Register the Stripe webhook

In the [Stripe Dashboard → Webhooks](https://dashboard.stripe.com/webhooks):

- **Endpoint URL:** your worker URL from step 2
- **Events to send:** `customer.created`, `charge.succeeded`
  - `customer.created` → founder welcome email **and** Customer.io profile (Free Trial)
  - `charge.succeeded` → Customer.io `payment` event (moves the person to Paid)

Copy the signing secret Stripe shows (`whsec_...`) — that's the value for
`STRIPE_WEBHOOK_SECRET` above. If you set it before creating the endpoint,
update it now and redeploy.

## Customer.io segment sync

The worker also keeps the **Icemail** Customer.io workspace's three rule-based
segments in sync in real time:

| Segment | Rule (auto-updating) |
|---|---|
| **Paid** | made a payment in the last 45 days (rolling) |
| **Churned** | paid before, but not in the last 45 days |
| **Free Trial** | never made a payment |

How it works:

- `customer.created` → **identify** the person in Customer.io (email, first/last
  name, signup date). With no payment yet they fall into **Free Trial**.
- `charge.succeeded` → send a **`payment`** event → they move to **Paid**.
- Customer.io's 45-day rolling window ages people **Paid → Churned**
  automatically. No cron, no re-import.

Only four fields are ever written to a profile: first name, last name, email,
signup date. Nothing else.

### Set the Customer.io secrets

Get a **Tracking Site ID** + **Track API Key** from Customer.io →
Settings → API Credentials → **Tracking API Keys** (Icemail workspace), then:

```bash
npx wrangler secret put CIO_SITE_ID
npx wrangler secret put CIO_TRACK_API_KEY
# CIO_REGION defaults to "us" (Icemail is us); only set it for an EU workspace.
```

If `CIO_SITE_ID` / `CIO_TRACK_API_KEY` are unset, the Customer.io sync is simply
skipped and the email flows still run.

### One-time backfill of existing customers

Load all existing Stripe customers + their payment history into Customer.io so
the segments are correct from day one. Runs locally, pulls straight from Stripe,
idempotent (safe to re-run):

```bash
# Preview counts without writing anything:
STRIPE_SECRET_KEY=sk_live_... node backfill-customerio.mjs --dry-run

# Real run:
STRIPE_SECRET_KEY=sk_live_... \
CIO_SITE_ID=... CIO_TRACK_API_KEY=... CIO_REGION=us \
npm run backfill:cio
```

The three segments already exist in Icemail; they finish rebuilding within a few
minutes of the backfill completing.

## Local testing

```bash
cp .dev.vars.example .dev.vars   # fill in your values (this file is gitignored)
npx wrangler dev
# in another terminal:
stripe listen --forward-to http://localhost:8787
stripe trigger customer.created
```

## Editing the email

The subject and body live in `sendFounderEmail()` in `src/index.js`.
Replace `[Your Company]` with your company name before deploying.
