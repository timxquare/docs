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
- **Events to send:** `customer.created`

Copy the signing secret Stripe shows (`whsec_...`) — that's the value for
`STRIPE_WEBHOOK_SECRET` above. If you set it before creating the endpoint,
update it now and redeploy.

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
