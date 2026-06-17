# PromoteKit → Tolt migration

A small, self-contained tool that copies your affiliate program from
**PromoteKit** into **Tolt**:

| PromoteKit            | →   | Tolt                       |
| --------------------- | --- | -------------------------- |
| Affiliates (users)    | →   | Partners                   |
| Referrals             | →   | Customers                  |
| Referred sales        | →   | Transactions               |
| Affiliate earnings    | →   | Commissions                |

It needs **no coding**. You only edit one settings file with your two API
keys and run a couple of commands. It is **safe by default**: the first run
writes nothing and just shows you what *would* happen.

---

## What you need first

1. **Node.js** installed (version 18 or newer). Check by opening a terminal
   and running `node --version`. If you don't have it, download it from
   <https://nodejs.org> (pick the "LTS" version) and install it.
2. **Your PromoteKit API key** — PromoteKit dashboard → Settings → API Keys.
3. **Your Tolt API key** — Tolt dashboard → Settings → Integrations.
4. **Your Tolt program ID** — the program in Tolt that affiliates should be
   imported into (Tolt dashboard → Programs).

---

## Step-by-step

### 1. Open a terminal in this folder

`cd` into the `promotekit-to-tolt-migration` folder.

### 2. Create your settings file

Copy the example file and open the copy in any text editor:

```bash
cp .env.example .env
```

Open `.env` and fill in these three lines:

```
PROMOTEKIT_API_KEY=your_promotekit_key_here
TOLT_API_KEY=your_tolt_key_here
TOLT_PROGRAM_ID=your_tolt_program_id_here
```

Save the file. (The `.env` file stays on your computer and is never committed
or shared.)

### 3. Check the connection (optional but recommended)

This reads a few records from PromoteKit and prints what they look like.
It does **not** change anything:

```bash
npm run inspect
```

If you see your affiliates/referrals listed, you're good. If it reports a
"404 Not Found", your PromoteKit account may use slightly different endpoint
names — see [Troubleshooting](#troubleshooting).

### 4. Do a dry run (writes nothing)

```bash
npm run dry-run
```

This pulls everything from PromoteKit and prints exactly what it *would*
create in Tolt, with a summary at the end. Review the numbers.

> Tip: to test on just a handful first, run `node index.mjs --limit 5`.

### 5. Run the real migration

When you're happy with the dry run:

```bash
npm run migrate
```

This writes everything into Tolt. Progress is saved continuously, so if it
stops for any reason you can simply run it again — it **skips anything already
imported** and continues where it left off.

---

## What happens during the run

- **Partners** are created from your affiliates (name, email, company,
  country, and PayPal payout email when available).
- **Customers** are created from referrals and linked to the partner who
  referred them.
- **Transactions** are created for referrals that had a sale amount.
- **Commissions** are created for referrals that had an earning amount.

When it finishes you'll get:

- A printed **summary** (created / skipped / failed for each type).
- `migration-report.json` — the same summary plus any errors, for your records.
- `migration-state.json` — the saved progress (lets you safely re-run).
- `migration.log` — a full timestamped log.

---

## Commands reference

| Command                      | What it does                                        |
| ---------------------------- | --------------------------------------------------- |
| `npm run inspect`            | Show sample source data; write nothing.             |
| `npm run dry-run`            | Full simulation; write nothing.                     |
| `npm run migrate`            | The real migration (writes to Tolt).                |
| `node index.mjs --limit 5`   | Only process the first 5 affiliates (for testing).  |
| `node index.mjs --live --reset` | Start over, ignoring saved progress.             |

---

## Money amounts

Tolt stores money in **cents**. By default this tool assumes PromoteKit gives
amounts in dollars (e.g. `49.00`) and multiplies by 100. If your PromoteKit
data is already in cents, set `PK_AMOUNTS_IN_CENTS=true` in `.env`. Use the
`inspect` command to check how amounts look in your data.

---

## Troubleshooting

**"Missing required configuration"** — you haven't filled in one of the three
required values in `.env`.

**A "404 Not Found" on affiliates or referrals** — PromoteKit's exact endpoint
paths aren't published publicly, so this tool uses the most likely ones
(`/affiliates`, `/referrals`). If your account differs, set the correct paths
in `.env`:

```
PK_AFFILIATES_PATH=/affiliates
PK_REFERRALS_PATH=/referrals
```

Run `npm run inspect` to see the field names in your data. If they don't match
what the tool expects, the field lists are at the bottom of
`src/promotekit.mjs` and are easy to extend.

**Partner "already exists"** — that's fine; the tool records it as skipped and
moves on.

**It stopped partway** — just run the same command again. It resumes
automatically.

---

## How it's built (for the curious)

Plain Node.js, no dependencies. Files:

- `index.mjs` — entry point / command-line handling
- `src/config.mjs` — all settings
- `src/promotekit.mjs` — reads from PromoteKit
- `src/tolt.mjs` — writes to Tolt
- `src/migrate.mjs` — the migration logic
- `src/util.mjs` — HTTP (with retries), logging, helpers
