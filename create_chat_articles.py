#!/usr/bin/env python3
"""
Creates 15 new Gleap help articles based on analysis of 2328 support chat conversations.
"""

import json
import re
import time
import urllib.request
import urllib.error
from pathlib import Path
import hashlib

TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpZCI6IjZhMmY4YjQ3ODYyODU5OWNlNWRjODE0OSIsInByb2plY3RJZCI6IjY4MzVjYzRkYTVkM2E0YjhlNGM4ZTI3NCIsInNlY3JldEFwaUtleSI6IjBoc1RKTmZDeUE0UTBLTEtad3FnZjAydzNIRThqUFVmIiwidXNlclR5cGUiOiJzZXJ2aWNlX2FjY291bnQiLCJpYXQiOjE3ODE1MDA3NDN9"
    ".lyJC8-8g8t106JRjPUU3dDB9t222k9C7HgW0xYoxL80"
)
PROJECT = "6835cc4da5d3a4b8e4c8e274"
API = "https://api.gleap.io"
GLEAP_DIR = Path(__file__).parent / "gleap"

COLLECTIONS = {
    "domain-management":          "6849b63fe92e06806c87c22a",
    "mailbox-management":         "6849b68247ecc2e7b5a14dfa",
    "mailbox-export-integrations":"6849b6b8e92e06806c8bd279",
    "billing-subscription":       "6849b6e7c3746dd2eeaefbdf",
    "faqs":                       "6849b767ed77fcb13166ed6d",
    "getting-started":            "6a2f9dacf10a74503708e7c7",
}


def api_req(method, path, body=None, retries=3):
    url = f"{API}{path}"
    data = json.dumps(body).encode() if body else None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, method=method, headers={
                "Authorization": f"Bearer {TOKEN}",
                "project": PROJECT,
                "Content-Type": "application/json",
            })
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body_text = e.read().decode()
            if attempt == retries - 1:
                raise RuntimeError(f"HTTP {e.code} on {method} {path}: {body_text[:200]}")
            time.sleep(2 ** attempt)
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def p(text, bold=False):
    node = {"type": "text", "text": text}
    if bold:
        node["marks"] = [{"type": "bold"}]
    return node


def paragraph(*parts):
    return {"type": "paragraph", "content": list(parts)}


def heading(level, text):
    return {"type": "heading", "attrs": {"level": level}, "content": [{"type": "text", "text": text}]}


def bullet_list(items):
    return {
        "type": "bulletList",
        "content": [
            {"type": "listItem", "content": [paragraph(p(item))]}
            for item in items
        ]
    }


def hr():
    return {"type": "horizontalRule"}


def md_to_hash(md_body):
    return hashlib.md5(md_body.encode()).hexdigest()[:8]


def create_article(title, collection_slug, filename, content_nodes, md_body):
    collection_id = COLLECTIONS[collection_slug]

    # 1. Create article in Gleap
    print(f"  Creating: {title[:60]}...")
    resp = api_req("POST", "/v3/helpcenter/articles", {
        "title": {"en": title},
        "collectionId": collection_id,
        "isDraft": False,
    })
    article_id = resp.get("id") or resp.get("_id")
    if not article_id:
        raise RuntimeError(f"No ID in response: {resp}")

    time.sleep(0.3)

    # 2. Push content
    api_req("PUT", f"/v3/helpcenter/articles/{article_id}", {
        "isDraft": False,
        "body": {"type": "doc", "content": content_nodes},
    })

    time.sleep(0.3)

    # 3. Save .mdx
    out_dir = GLEAP_DIR / collection_slug
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename

    frontmatter = f"""---
title: "{title}"
description: "{title}"
gleap_id: "{article_id}"
gleap_collection: "{collection_id}"
gleap_collection_slug: "{collection_slug}"
isDraft: false
content_hash: "{md_to_hash(md_body)}"
---

{md_body}"""

    out_path.write_text(frontmatter)
    print(f"  ✅ {article_id} → {out_path.name}")
    return article_id


# ─────────────────────────────────────────────────────────────────────────────
# ARTICLES
# ─────────────────────────────────────────────────────────────────────────────

ARTICLES = []

# 1. Mailboxes stuck in processing
ARTICLES.append({
    "title": "⏳ Mailboxes Stuck in Processing – Complete Troubleshooting Guide",
    "collection": "mailbox-management",
    "filename": "mailboxes-stuck-in-processing-troubleshooting-guide.mdx",
    "nodes": [
        paragraph(p("If your newly created mailboxes have been sitting in \"Processing\" status for hours, don't worry — this is one of the most common situations and is usually resolved automatically. Here's everything you need to know.")),
        hr(),
        heading(3, "What Does 'Processing' Mean?"),
        paragraph(p("When you create a mailbox in Icemail, it goes through a provisioning queue. During this stage, Icemail is:")),
        bullet_list([
            "Requesting a license from Google or Microsoft",
            "Configuring SPF, DKIM, DMARC, and MX records on your domain",
            "Setting up the mailbox credentials and app passwords",
        ]),
        paragraph(p("This process cannot be skipped or manually triggered — it runs automatically in the background.")),
        hr(),
        heading(3, "Expected Timelines"),
        paragraph(p("Google Workspace mailboxes:", True), p(" typically active within 1–4 hours.")),
        paragraph(p("Microsoft 365 mailboxes:", True), p(" typically take longer than Google — 4–24 hours depending on the provisioning queue.")),
        paragraph(p("During peak demand periods (e.g., many customers ordering at once), processing can take longer for both types.")),
        hr(),
        heading(3, "Common Causes of Longer Processing"),
        bullet_list([
            "DNS records not yet complete — SPF/DKIM/DMARC must be fully configured before mailboxes can activate",
            "High provisioning queue — other orders are ahead of yours",
            "Mailboxes ordered in large batches — the later ones in a batch take longer",
            "Creating additional mailboxes during processing — avoid adding more to the same domain while previous ones are still processing",
        ]),
        hr(),
        heading(3, "What To Do"),
        bullet_list([
            "Wait at least 4–6 hours before escalating",
            "Do NOT create additional mailboxes on the same domain while others are still processing",
            "For bulk orders (20+ mailboxes), allow up to 24 hours",
            "If still processing after 24 hours, contact team@icemail.ai with your domain name(s)",
        ]),
        hr(),
        heading(3, "When Will I Be Notified?"),
        paragraph(p("Once your mailboxes are active, you can export them directly from the Mailboxes dashboard. There is no automatic email notification — check your dashboard periodically.")),
        hr(),
        paragraph(p("Need Help? Email "), p("team@icemail.ai", True), p(" with your account email and the affected domain names.")),
    ],
    "md": """If your newly created mailboxes have been sitting in "Processing" status for hours, don't worry — this is one of the most common situations and is usually resolved automatically.

---

### What Does 'Processing' Mean?

When you create a mailbox in Icemail, it goes through a provisioning queue. During this stage, Icemail is:

- Requesting a license from Google or Microsoft
- Configuring SPF, DKIM, DMARC, and MX records on your domain
- Setting up the mailbox credentials and app passwords

This process cannot be skipped or manually triggered — it runs automatically in the background.

---

### Expected Timelines

**Google Workspace mailboxes:** typically active within 1–4 hours.

**Microsoft 365 mailboxes:** typically take longer than Google — 4–24 hours depending on the provisioning queue.

During peak demand periods (e.g., many customers ordering at once), processing can take longer for both types.

---

### Common Causes of Longer Processing

- DNS records not yet complete — SPF/DKIM/DMARC must be fully configured before mailboxes can activate
- High provisioning queue — other orders are ahead of yours
- Mailboxes ordered in large batches — the later ones in a batch take longer
- Creating additional mailboxes during processing — avoid adding more to the same domain while previous ones are still processing

---

### What To Do

- Wait at least 4–6 hours before escalating
- Do NOT create additional mailboxes on the same domain while others are still processing
- For bulk orders (20+ mailboxes), allow up to 24 hours
- If still processing after 24 hours, contact team@icemail.ai with your domain name(s)

---

### When Will I Be Notified?

Once your mailboxes are active, you can export them directly from the Mailboxes dashboard. There is no automatic email notification — check your dashboard periodically.

---

Need Help? Email **team@icemail.ai** with your account email and the affected domain names.""",
})

# 2. App passwords
ARTICLES.append({
    "title": "🔑 App Passwords for Google Mailboxes – How They Work & Common Issues",
    "collection": "mailbox-management",
    "filename": "app-passwords-for-google-mailboxes-how-they-work.mdx",
    "nodes": [
        paragraph(p("App passwords are automatically generated by Icemail when your Google Workspace mailbox becomes active. Understanding how they work prevents the most common SMTP connection errors.")),
        hr(),
        heading(3, "What Is an App Password?"),
        paragraph(p("An app password is a 16-character password generated specifically for SMTP/IMAP access. It's different from your Google account password and is required by outreach tools to connect to your mailbox.")),
        hr(),
        heading(3, "⚠️ Do NOT Change Your Mailbox Password"),
        paragraph(p("Never manually change your Google mailbox password through Google's UI. If you do:")),
        bullet_list([
            "The app password will be invalidated immediately",
            "Your outreach tool connections will break",
            "You'll need to contact team@icemail.ai to reset it",
        ]),
        paragraph(p("Icemail manages Google account credentials automatically. Let the system handle password management.")),
        hr(),
        heading(3, "Where to Find Your App Password"),
        bullet_list([
            "Go to Mailboxes in your Icemail dashboard",
            "Find your mailbox and click the details icon",
            "The app password is listed under SMTP credentials",
            "You can also download a CSV with all mailbox credentials from the Export section",
        ]),
        hr(),
        heading(3, "SMTP Settings for Google Mailboxes"),
        bullet_list([
            "SMTP Server: smtp.gmail.com | Port: 587 (TLS) or 465 (SSL)",
            "IMAP Server: imap.gmail.com | Port: 993 (SSL)",
            "Username: your full email address (e.g. john@yourdomain.com)",
            "Password: the app password (NOT your Google account password)",
        ]),
        hr(),
        heading(3, "App Password Is Missing?"),
        paragraph(p("If the app password field is blank, it means the mailbox is still in the processing state. Wait for the mailbox to become Active, then the app password will appear automatically.")),
        hr(),
        heading(3, "Mailbox Shows 'Disconnected' in My Outreach Tool?"),
        bullet_list([
            "Re-export the mailbox from Icemail (this refreshes the connection)",
            "If the error persists, contact team@icemail.ai — the team can regenerate the app password from the backend",
        ]),
        hr(),
        paragraph(p("Need help? Contact "), p("team@icemail.ai", True), p(" with the affected mailbox address.")),
    ],
    "md": """App passwords are automatically generated by Icemail when your Google Workspace mailbox becomes active. Understanding how they work prevents the most common SMTP connection errors.

---

### What Is an App Password?

An app password is a 16-character password generated specifically for SMTP/IMAP access. It's different from your Google account password and is required by outreach tools to connect to your mailbox.

---

### ⚠️ Do NOT Change Your Mailbox Password

Never manually change your Google mailbox password through Google's UI. If you do:

- The app password will be invalidated immediately
- Your outreach tool connections will break
- You'll need to contact team@icemail.ai to reset it

Icemail manages Google account credentials automatically. Let the system handle password management.

---

### Where to Find Your App Password

- Go to Mailboxes in your Icemail dashboard
- Find your mailbox and click the details icon
- The app password is listed under SMTP credentials
- You can also download a CSV with all mailbox credentials from the Export section

---

### SMTP Settings for Google Mailboxes

- SMTP Server: smtp.gmail.com | Port: 587 (TLS) or 465 (SSL)
- IMAP Server: imap.gmail.com | Port: 993 (SSL)
- Username: your full email address (e.g. john@yourdomain.com)
- Password: the app password (NOT your Google account password)

---

### App Password Is Missing?

If the app password field is blank, it means the mailbox is still in the processing state. Wait for the mailbox to become Active, then the app password will appear automatically.

---

### Mailbox Shows 'Disconnected' in My Outreach Tool?

- Re-export the mailbox from Icemail (this refreshes the connection)
- If the error persists, contact team@icemail.ai — the team can regenerate the app password from the backend

---

Need help? Contact **team@icemail.ai** with the affected mailbox address.""",
})

# 3. Cancel/delete mailboxes
ARTICLES.append({
    "title": "🗑️ How to Cancel or Delete Mailboxes in Icemail",
    "collection": "mailbox-management",
    "filename": "how-to-cancel-or-delete-mailboxes-in-icemail.mdx",
    "nodes": [
        paragraph(p("Need to stop a mailbox subscription or remove mailboxes you no longer need? Here's how deletion and cancellation work in Icemail.")),
        hr(),
        heading(3, "How to Delete a Mailbox"),
        bullet_list([
            "Go to Mailboxes in your Icemail dashboard",
            "Select the mailbox(es) you want to remove",
            "Click Delete or Deactivate",
            "Confirm the deletion",
        ]),
        paragraph(p("Once deleted from the UI, you will not be charged for those mailboxes in the next billing cycle.")),
        hr(),
        heading(3, "What Happens After Deletion?"),
        bullet_list([
            "Billing stops at the end of the current billing period",
            "Full deletion from the backend (Google/Microsoft systems) takes 24–48 hours",
            "Emails in the mailbox are permanently deleted — export anything you need beforehand",
            "Wallet credits are not refunded after mailbox deletion (your balance remains for future purchases)",
        ]),
        hr(),
        heading(3, "Mailbox Reactivation Window"),
        paragraph(p("Within 7 days of deletion:", True), p(" mailboxes can be reactivated at the standard rate ($2.50/mailbox/month). Contact team@icemail.ai to restore them.")),
        paragraph(p("After 7 days:", True), p(" mailboxes are permanently deleted from Google/Microsoft systems and cannot be recovered.")),
        hr(),
        heading(3, "Bulk Cancellation"),
        paragraph(p("For cancelling many mailboxes or entire domains at once, contact "), p("team@icemail.ai", True), p(" — the team can bulk delete from the backend. This is faster than deleting one by one in the UI.")),
        hr(),
        heading(3, "Cancelling a Domain"),
        paragraph(p("Cancelling a domain stops all mailboxes on that domain. To cancel a domain:")),
        bullet_list([
            "Go to Domains in your dashboard",
            "Click Manage next to the domain",
            "Select Cancel Domain / Delete Domain",
        ]),
        hr(),
        heading(3, "What About Wallet Credits?"),
        paragraph(p("Wallet credits are prepaid and are not refunded when you cancel mailboxes. Your remaining wallet balance can be used for future purchases. Stripe processing fees (3–4%) are also non-refundable.")),
        hr(),
        paragraph(p("Need help with bulk cancellations? Email "), p("team@icemail.ai", True), p(".")),
    ],
    "md": """Need to stop a mailbox subscription or remove mailboxes you no longer need? Here's how deletion and cancellation work in Icemail.

---

### How to Delete a Mailbox

- Go to Mailboxes in your Icemail dashboard
- Select the mailbox(es) you want to remove
- Click Delete or Deactivate
- Confirm the deletion

Once deleted from the UI, you will not be charged for those mailboxes in the next billing cycle.

---

### What Happens After Deletion?

- Billing stops at the end of the current billing period
- Full deletion from the backend (Google/Microsoft systems) takes 24–48 hours
- Emails in the mailbox are permanently deleted — export anything you need beforehand
- Wallet credits are not refunded after mailbox deletion (your balance remains for future purchases)

---

### Mailbox Reactivation Window

**Within 7 days of deletion:** mailboxes can be reactivated at the standard rate ($2.50/mailbox/month). Contact team@icemail.ai to restore them.

**After 7 days:** mailboxes are permanently deleted from Google/Microsoft systems and cannot be recovered.

---

### Bulk Cancellation

For cancelling many mailboxes or entire domains at once, contact **team@icemail.ai** — the team can bulk delete from the backend. This is faster than deleting one by one in the UI.

---

### Cancelling a Domain

Cancelling a domain stops all mailboxes on that domain. To cancel a domain:

- Go to Domains in your dashboard
- Click Manage next to the domain
- Select Cancel Domain / Delete Domain

---

### What About Wallet Credits?

Wallet credits are prepaid and are not refunded when you cancel mailboxes. Your remaining wallet balance can be used for future purchases. Stripe processing fees (3–4%) are also non-refundable.

---

Need help with bulk cancellations? Email **team@icemail.ai**.""",
})

# 4. Team members / workspace access
ARTICLES.append({
    "title": "👥 How to Add Team Members & Manage Workspace Access in Icemail",
    "collection": "mailbox-management",
    "filename": "how-to-add-team-members-manage-workspace-access.mdx",
    "nodes": [
        paragraph(p("Icemail uses workspaces to organize your domains and mailboxes. Here's how to add team members, manage client access, and work with multiple workspaces.")),
        hr(),
        heading(3, "How to Invite a Team Member"),
        bullet_list([
            "Go to Settings in your Icemail dashboard",
            "Click Team",
            "Click Invite Member",
            "Enter their email address and assign a role",
            "They'll receive an invitation email to join your workspace",
        ]),
        hr(),
        heading(3, "Client Access – Agency Use Case"),
        paragraph(p("If you manage mailboxes on behalf of clients:")),
        bullet_list([
            "Ask your client to sign up for their own Icemail account",
            "Have them invite you to their workspace (Settings → Team → Invite Member)",
            "This allows you to manage their account without sharing passwords",
            "Alternatively, create a workspace in your own account and invite the client",
        ]),
        hr(),
        heading(3, "Managing Multiple Workspaces"),
        paragraph(p("You can manage multiple workspaces from a single Icemail account:")),
        bullet_list([
            "Switch between workspaces using the workspace selector in the top navigation",
            "Each workspace has its own domains, mailboxes, and billing",
            "You can be a member of multiple workspaces simultaneously",
        ]),
        hr(),
        heading(3, "2FA on Mailboxes – Cannot Be Removed"),
        paragraph(p("A common question: can I remove 2FA from my mailboxes?")),
        paragraph(p("No — 2FA on Google and Microsoft mailboxes is required and managed automatically by Icemail. It cannot be removed because:")),
        bullet_list([
            "Google and Microsoft require it for secure API access",
            "Disabling it would break mailbox configuration and SMTP connections",
            "It's set up automatically during mailbox provisioning",
        ]),
        paragraph(p("To connect mailboxes to outreach tools, use the ", True), p("app password", True), p(" (not the Google/Microsoft account password) — available in your mailbox details.", True)),
        hr(),
        heading(3, "2FA on Icemail Dashboard Login"),
        paragraph(p("Your Icemail dashboard login 2FA is separate and managed per-user. Each team member controls their own 2FA settings under Account Settings.")),
        hr(),
        paragraph(p("Questions about team access? Email "), p("team@icemail.ai", True), p(".")),
    ],
    "md": """Icemail uses workspaces to organize your domains and mailboxes. Here's how to add team members, manage client access, and work with multiple workspaces.

---

### How to Invite a Team Member

- Go to Settings in your Icemail dashboard
- Click Team
- Click Invite Member
- Enter their email address and assign a role
- They'll receive an invitation email to join your workspace

---

### Client Access – Agency Use Case

If you manage mailboxes on behalf of clients:

- Ask your client to sign up for their own Icemail account
- Have them invite you to their workspace (Settings → Team → Invite Member)
- This allows you to manage their account without sharing passwords
- Alternatively, create a workspace in your own account and invite the client

---

### Managing Multiple Workspaces

You can manage multiple workspaces from a single Icemail account:

- Switch between workspaces using the workspace selector in the top navigation
- Each workspace has its own domains, mailboxes, and billing
- You can be a member of multiple workspaces simultaneously

---

### 2FA on Mailboxes – Cannot Be Removed

A common question: can I remove 2FA from my mailboxes?

No — 2FA on Google and Microsoft mailboxes is required and managed automatically by Icemail. It cannot be removed because:

- Google and Microsoft require it for secure API access
- Disabling it would break mailbox configuration and SMTP connections
- It's set up automatically during mailbox provisioning

To connect mailboxes to outreach tools, use the **app password** (not the Google/Microsoft account password) — available in your mailbox details.

---

### 2FA on Icemail Dashboard Login

Your Icemail dashboard login 2FA is separate and managed per-user. Each team member controls their own 2FA settings under Account Settings.

---

Questions about team access? Email **team@icemail.ai**.""",
})

# 5. Billing FAQ
ARTICLES.append({
    "title": "💳 Billing FAQ – Renewals, Auto-Renew, Auto Top-Up & Payment Issues",
    "collection": "billing-subscription",
    "filename": "billing-faq-renewals-auto-renew-auto-topup.mdx",
    "nodes": [
        paragraph(p("Quick answers to the most common billing questions in Icemail.")),
        hr(),
        heading(3, "What Is Auto-Renew?"),
        paragraph(p("Auto-renew automatically renews your mailbox subscriptions each month. It's enabled by default. If your wallet has enough balance, the renewal charge is deducted automatically. If not, the mailboxes are deactivated until you add funds.")),
        hr(),
        heading(3, "What Is Auto Top-Up?"),
        paragraph(p("Auto top-up adds wallet funds automatically when your balance falls below a threshold you set. For example: if your balance drops below $20, auto top-up adds $50. This prevents mailbox deactivations due to insufficient balance.")),
        paragraph(p("To configure: Settings → Wallet → Auto Top-Up → Edit.")),
        hr(),
        heading(3, "Why Was I Charged After Disabling Auto Top-Up?"),
        paragraph(p("Disabling auto top-up stops automatic wallet refills — but if your mailboxes have ", True), p("Auto-Renew", True), p(" enabled, renewal charges still apply. To stop charges completely, you must ", True), p("cancel the mailboxes", True), p(" themselves (not just auto top-up).", True)),
        hr(),
        heading(3, "My Mailboxes Were Deactivated Due to Pending Renewal"),
        paragraph(p("If mailboxes are deactivated, add wallet credits immediately to reactivate them:")),
        bullet_list([
            "Go to Billing → Wallet → Add More Balance",
            "Add enough to cover the renewal amount",
            "Mailboxes will reactivate within a few minutes",
        ]),
        paragraph(p("Note: if mailboxes have been deactivated for more than 7 days, they may be permanently deleted. Contact team@icemail.ai urgently in this case.")),
        hr(),
        heading(3, "Can I Get a Custom Invoice or Payment Link?"),
        paragraph(p("Standard purchases go through your wallet. For large orders or custom invoices (e.g., for a client), contact "), p("team@icemail.ai", True), p(" — the billing team can generate a direct payment link or custom invoice.")),
        hr(),
        heading(3, "Where Can I Download My Invoices?"),
        bullet_list([
            "Go to Billing → View Invoice",
            "Click Download PDF next to any invoice",
            "Invoices are available for all past transactions",
        ]),
        hr(),
        heading(3, "I Was Charged Twice / Wrong Amount"),
        paragraph(p("Contact "), p("team@icemail.ai", True), p(" immediately with your account email, the charge amount, and the date. Duplicate charges are resolved within 24–48 hours.")),
        hr(),
        paragraph(p("Billing questions? Email "), p("team@icemail.ai", True), p(" or use Live Chat in your dashboard.")),
    ],
    "md": """Quick answers to the most common billing questions in Icemail.

---

### What Is Auto-Renew?

Auto-renew automatically renews your mailbox subscriptions each month. It's enabled by default. If your wallet has enough balance, the renewal charge is deducted automatically. If not, the mailboxes are deactivated until you add funds.

---

### What Is Auto Top-Up?

Auto top-up adds wallet funds automatically when your balance falls below a threshold you set. For example: if your balance drops below $20, auto top-up adds $50. This prevents mailbox deactivations due to insufficient balance.

To configure: Settings → Wallet → Auto Top-Up → Edit.

---

### Why Was I Charged After Disabling Auto Top-Up?

Disabling auto top-up stops automatic wallet refills — but if your mailboxes have **Auto-Renew** enabled, renewal charges still apply. To stop charges completely, you must **cancel the mailboxes** themselves (not just auto top-up).

---

### My Mailboxes Were Deactivated Due to Pending Renewal

If mailboxes are deactivated, add wallet credits immediately to reactivate them:

- Go to Billing → Wallet → Add More Balance
- Add enough to cover the renewal amount
- Mailboxes will reactivate within a few minutes

Note: if mailboxes have been deactivated for more than 7 days, they may be permanently deleted. Contact team@icemail.ai urgently in this case.

---

### Can I Get a Custom Invoice or Payment Link?

Standard purchases go through your wallet. For large orders or custom invoices (e.g., for a client), contact **team@icemail.ai** — the billing team can generate a direct payment link or custom invoice.

---

### Where Can I Download My Invoices?

- Go to Billing → View Invoice
- Click Download PDF next to any invoice
- Invoices are available for all past transactions

---

### I Was Charged Twice / Wrong Amount

Contact **team@icemail.ai** immediately with your account email, the charge amount, and the date. Duplicate charges are resolved within 24–48 hours.

---

Billing questions? Email **team@icemail.ai** or use Live Chat in your dashboard.""",
})

# 6. API vs CSV export
ARTICLES.append({
    "title": "📤 How to Export Mailboxes from Icemail – API Integration vs CSV Method",
    "collection": "mailbox-export-integrations",
    "filename": "how-to-export-mailboxes-api-vs-csv-method.mdx",
    "nodes": [
        paragraph(p("Icemail gives you two ways to export mailboxes to outreach tools. Understanding the difference helps you choose the right method and avoid common errors.")),
        hr(),
        heading(3, "Method 1: Direct Integration (Recommended)"),
        paragraph(p("This is the preferred method for all supported platforms (Instantly, Smartlead, ReachInbox, Lemlist, Reply.io, etc.).")),
        bullet_list([
            "Go to Mailboxes and select the mailboxes you want to export",
            "Click Export Mailboxes",
            "Choose your outreach platform",
            "Authenticate with your outreach tool account",
            "Mailboxes are connected automatically via OAuth/API",
        ]),
        paragraph(p("Why it's better:", True), p(" Uses a secure API connection. Mailboxes stay synced. Re-connecting is faster if credentials change.")),
        hr(),
        heading(3, "Method 2: CSV Export"),
        paragraph(p("Use this only when your tool is not listed in the direct integration options.")),
        bullet_list([
            "Go to Mailboxes → Export → Download CSV",
            "The CSV contains mailbox email addresses, app passwords, and SMTP/IMAP settings",
            "Import the CSV into your outreach tool manually",
        ]),
        paragraph(p("Important:", True), p(" The CSV method uses IMAP credentials. For tools like Instantly, the API/OAuth method is strongly preferred over CSV — CSV exports via IMAP may be less reliable.")),
        hr(),
        heading(3, "Connecting to a Custom or Unlisted Tool"),
        paragraph(p("If your outreach tool isn't in the direct integration list, use these SMTP credentials manually:")),
        bullet_list([
            "Google: SMTP smtp.gmail.com:587, IMAP imap.gmail.com:993, Password: app password",
            "Microsoft: SMTP smtp.office365.com:587, IMAP outlook.office365.com:993",
            "Username: full email address",
        ]),
        paragraph(p("Need a custom Google Admin Client ID added? Contact "), p("team@icemail.ai", True), p(" — the team can add your Client ID to all provisioned mailboxes from the backend.")),
        hr(),
        heading(3, "Re-Exporting / Reconnecting Mailboxes"),
        paragraph(p("If your mailboxes disconnect from your outreach tool:")),
        bullet_list([
            "Return to Icemail → Mailboxes",
            "Select the disconnected mailboxes",
            "Click Export Mailboxes again and re-authenticate",
            "For persistent issues, contact team@icemail.ai",
        ]),
        hr(),
        paragraph(p("Need export help? Email "), p("team@icemail.ai", True), p(".")),
    ],
    "md": """Icemail gives you two ways to export mailboxes to outreach tools. Understanding the difference helps you choose the right method and avoid common errors.

---

### Method 1: Direct Integration (Recommended)

This is the preferred method for all supported platforms (Instantly, Smartlead, ReachInbox, Lemlist, Reply.io, etc.).

- Go to Mailboxes and select the mailboxes you want to export
- Click Export Mailboxes
- Choose your outreach platform
- Authenticate with your outreach tool account
- Mailboxes are connected automatically via OAuth/API

**Why it's better:** Uses a secure API connection. Mailboxes stay synced. Re-connecting is faster if credentials change.

---

### Method 2: CSV Export

Use this only when your tool is not listed in the direct integration options.

- Go to Mailboxes → Export → Download CSV
- The CSV contains mailbox email addresses, app passwords, and SMTP/IMAP settings
- Import the CSV into your outreach tool manually

**Important:** The CSV method uses IMAP credentials. For tools like Instantly, the API/OAuth method is strongly preferred over CSV — CSV exports via IMAP may be less reliable.

---

### Connecting to a Custom or Unlisted Tool

If your outreach tool isn't in the direct integration list, use these SMTP credentials manually:

- Google: SMTP smtp.gmail.com:587, IMAP imap.gmail.com:993, Password: app password
- Microsoft: SMTP smtp.office365.com:587, IMAP outlook.office365.com:993
- Username: full email address

Need a custom Google Admin Client ID added? Contact **team@icemail.ai** — the team can add your Client ID to all provisioned mailboxes from the backend.

---

### Re-Exporting / Reconnecting Mailboxes

If your mailboxes disconnect from your outreach tool:

- Return to Icemail → Mailboxes
- Select the disconnected mailboxes
- Click Export Mailboxes again and re-authenticate
- For persistent issues, contact team@icemail.ai

---

Need export help? Email **team@icemail.ai**.""",
})

# 7. Domain forwarding not working
ARTICLES.append({
    "title": "🔁 Domain Forwarding Not Working – Troubleshooting Guide",
    "collection": "domain-management",
    "filename": "domain-forwarding-not-working-troubleshooting.mdx",
    "nodes": [
        paragraph(p("If your domain forwarding isn't redirecting as expected, work through these checks in order.")),
        hr(),
        heading(3, "Check 1: Is the Target URL Correct?"),
        paragraph(p("The destination URL must include the protocol prefix:")),
        bullet_list([
            "✅ Correct: https://yourcompany.com",
            "❌ Wrong: yourcompany.com (missing https://)",
        ]),
        hr(),
        heading(3, "Check 2: Did You Save the Settings?"),
        paragraph(p("After entering the forwarding URL in Domain Settings, click ", True), p("Save", True), p(". Without saving, the forwarding will not activate.")),
        hr(),
        heading(3, "Check 3: Is This a Web Redirect or Email Redirect?"),
        paragraph(p("Domain forwarding in Icemail is for ", True), p("web traffic only", True), p(" — it redirects visitors who type your domain into a browser.")),
        paragraph(p("Email forwarding (receiving emails and routing them elsewhere) is a separate feature. Go to Domain Settings → Email Forwarding to configure that.")),
        hr(),
        heading(3, "Check 4: Clear Cache & Test in Incognito"),
        paragraph(p("Browser cache can make forwarding appear broken when it's actually working. Test in a private/incognito browser window.")),
        hr(),
        heading(3, "Check 5: Is the Domain Connected to Icemail?"),
        paragraph(p("Domain forwarding only works for domains actively managed by Icemail (connected via Cloudflare/nameservers). Verify your domain shows as 'Connected' in the Domains dashboard.")),
        hr(),
        heading(3, "Check 6: SSL Certificate Provisioning"),
        paragraph(p("If your target URL uses HTTPS and you're seeing SSL errors, give it 15–30 minutes. SSL certificates for masked/redirected domains can take time to provision.")),
        hr(),
        heading(3, "Still Not Working?"),
        paragraph(p("If none of the above resolves it, contact "), p("team@icemail.ai", True), p(" with:")),
        bullet_list([
            "The domain you're forwarding FROM",
            "The destination URL you're forwarding TO",
            "A screenshot of the Domain Settings tab",
        ]),
        paragraph(p("Our team can verify and fix forwarding from the backend.")),
    ],
    "md": """If your domain forwarding isn't redirecting as expected, work through these checks in order.

---

### Check 1: Is the Target URL Correct?

The destination URL must include the protocol prefix:

- ✅ Correct: https://yourcompany.com
- ❌ Wrong: yourcompany.com (missing https://)

---

### Check 2: Did You Save the Settings?

After entering the forwarding URL in Domain Settings, click **Save**. Without saving, the forwarding will not activate.

---

### Check 3: Is This a Web Redirect or Email Redirect?

Domain forwarding in Icemail is for **web traffic only** — it redirects visitors who type your domain into a browser.

Email forwarding (receiving emails and routing them elsewhere) is a separate feature. Go to Domain Settings → Email Forwarding to configure that.

---

### Check 4: Clear Cache & Test in Incognito

Browser cache can make forwarding appear broken when it's actually working. Test in a private/incognito browser window.

---

### Check 5: Is the Domain Connected to Icemail?

Domain forwarding only works for domains actively managed by Icemail (connected via Cloudflare/nameservers). Verify your domain shows as 'Connected' in the Domains dashboard.

---

### Check 6: SSL Certificate Provisioning

If your target URL uses HTTPS and you're seeing SSL errors, give it 15–30 minutes. SSL certificates for masked/redirected domains can take time to provision.

---

### Still Not Working?

If none of the above resolves it, contact **team@icemail.ai** with:

- The domain you're forwarding FROM
- The destination URL you're forwarding TO
- A screenshot of the Domain Settings tab

Our team can verify and fix forwarding from the backend.""",
})

# 8. 2FA understanding
ARTICLES.append({
    "title": "🔐 Understanding 2FA on Icemail Mailboxes – Why It Can't Be Removed",
    "collection": "mailbox-management",
    "filename": "understanding-2fa-on-mailboxes-why-it-cannot-be-removed.mdx",
    "nodes": [
        paragraph(p("Many users ask whether 2FA (two-factor authentication) can be removed from their mailboxes. This article explains why it can't and what to do instead.")),
        hr(),
        heading(3, "Two Types of 2FA in Icemail"),
        paragraph(p("1. ", True), p("Mailbox 2FA", True), p(" — on your Google or Microsoft mailbox itself (managed automatically by Icemail)")),
        paragraph(p("2. ", True), p("Dashboard 2FA", True), p(" — on your Icemail account login (managed by you)")),
        paragraph(p("These are completely separate. This article covers mailbox 2FA.")),
        hr(),
        heading(3, "Why Mailbox 2FA Cannot Be Removed"),
        paragraph(p("Icemail cannot remove 2FA from your Google or Microsoft mailboxes because:")),
        bullet_list([
            "Google and Microsoft require 2FA for API access and admin management",
            "Icemail uses these APIs to provision, configure, and manage your mailboxes",
            "Disabling 2FA would break Icemail's ability to sync mailbox settings, credentials, and configurations",
            "It's a security requirement enforced by Google and Microsoft, not an Icemail choice",
        ]),
        hr(),
        heading(3, "How to Use Your Mailbox With 2FA Active"),
        paragraph(p("You don't need to interact with 2FA manually. Here's how it works:")),
        bullet_list([
            "For outreach tools: use the app password (not your Google/Microsoft password) — this bypasses 2FA automatically",
            "For manual login: use the email + password provided in your Icemail dashboard, then approve the 2FA prompt",
            "App passwords are listed in Mailboxes → click mailbox → SMTP credentials",
        ]),
        hr(),
        heading(3, "Clients Needing Access to the Mailbox"),
        paragraph(p("If a client needs to manually access the mailbox:")),
        bullet_list([
            "Share the app password for SMTP/IMAP access",
            "For web login, share the Google/Microsoft credentials and they'll need to approve the 2FA step",
            "Adding the client email to your Icemail workspace gives them dashboard access without needing mailbox credentials",
        ]),
        hr(),
        heading(3, "Icemail Dashboard 2FA"),
        paragraph(p("Your Icemail login 2FA is a separate setting. Each user manages their own under Account Settings → Security. Support cannot disable it on your behalf.")),
        hr(),
        paragraph(p("Questions? Email "), p("team@icemail.ai", True), p(".")),
    ],
    "md": """Many users ask whether 2FA (two-factor authentication) can be removed from their mailboxes. This article explains why it can't and what to do instead.

---

### Two Types of 2FA in Icemail

1. **Mailbox 2FA** — on your Google or Microsoft mailbox itself (managed automatically by Icemail)
2. **Dashboard 2FA** — on your Icemail account login (managed by you)

These are completely separate. This article covers mailbox 2FA.

---

### Why Mailbox 2FA Cannot Be Removed

Icemail cannot remove 2FA from your Google or Microsoft mailboxes because:

- Google and Microsoft require 2FA for API access and admin management
- Icemail uses these APIs to provision, configure, and manage your mailboxes
- Disabling 2FA would break Icemail's ability to sync mailbox settings, credentials, and configurations
- It's a security requirement enforced by Google and Microsoft, not an Icemail choice

---

### How to Use Your Mailbox With 2FA Active

You don't need to interact with 2FA manually. Here's how it works:

- For outreach tools: use the app password (not your Google/Microsoft password) — this bypasses 2FA automatically
- For manual login: use the email + password provided in your Icemail dashboard, then approve the 2FA prompt
- App passwords are listed in Mailboxes → click mailbox → SMTP credentials

---

### Clients Needing Access to the Mailbox

If a client needs to manually access the mailbox:

- Share the app password for SMTP/IMAP access
- For web login, share the Google/Microsoft credentials and they'll need to approve the 2FA step
- Adding the client email to your Icemail workspace gives them dashboard access without needing mailbox credentials

---

### Icemail Dashboard 2FA

Your Icemail login 2FA is a separate setting. Each user manages their own under Account Settings → Security. Support cannot disable it on your behalf.

---

Questions? Email **team@icemail.ai**.""",
})

# 9. Cloudflare without changing NS
ARTICLES.append({
    "title": "☁️ How to Connect Domains via Cloudflare Without Changing Nameservers",
    "collection": "domain-management",
    "filename": "connecting-domains-via-cloudflare-without-changing-ns.mdx",
    "nodes": [
        paragraph(p("If your domain is already on Cloudflare, you can connect it to Icemail without changing your nameservers. This preserves your existing Cloudflare settings.")),
        hr(),
        heading(3, "Two Ways to Connect a Cloudflare Domain"),
        heading(3, "Option A: Connect via Cloudflare API (Recommended)"),
        paragraph(p("This method adds DNS records directly through the Cloudflare API, without requiring a nameserver change.")),
        bullet_list([
            "Go to Domains in your Icemail dashboard",
            "Click Add Domain → Connect Existing Domain",
            "Select Connect via Cloudflare",
            "Click Authorize and log in to your Cloudflare account",
            "Select the domain and click Connect",
            "Icemail automatically adds SPF, DKIM, DMARC, and MX records",
        ]),
        paragraph(p("Benefit:", True), p(" Your existing Cloudflare configuration (other DNS records, page rules, proxying settings) remains untouched.")),
        hr(),
        heading(3, "Option B: Change Nameservers (Standard Method)"),
        paragraph(p("If you prefer, you can update your domain's nameservers to point to Icemail/Cloudflare:")),
        bullet_list([
            "Go to Domains → Add Domain → Connect Existing Domain",
            "Copy the Icemail nameservers shown in the dashboard",
            "Log in to your domain registrar (GoDaddy, Namecheap, etc.)",
            "Replace the current nameservers with the Icemail nameservers",
            "DNS propagation takes up to 24 hours",
        ]),
        hr(),
        heading(3, "DNS Records Added Automatically"),
        paragraph(p("Both methods auto-configure the same DNS records once connected:")),
        bullet_list([
            "SPF — authorizes Icemail to send email on behalf of your domain",
            "DKIM — cryptographic signature for email authentication",
            "DMARC — policy for handling unauthenticated emails",
            "MX — routes incoming email to the right server",
        ]),
        hr(),
        heading(3, "Common Issue: Domain Already Has a Google Workspace"),
        paragraph(p("If you see a 'Workspace Already Exists' error, the domain has an existing Google Workspace that must be cleared first. Contact "), p("team@icemail.ai", True), p(" — the team can clear it from the backend.")),
        hr(),
        paragraph(p("Need help connecting your domain? Email "), p("team@icemail.ai", True), p(".")),
    ],
    "md": """If your domain is already on Cloudflare, you can connect it to Icemail without changing your nameservers. This preserves your existing Cloudflare settings.

---

### Two Ways to Connect a Cloudflare Domain

### Option A: Connect via Cloudflare API (Recommended)

This method adds DNS records directly through the Cloudflare API, without requiring a nameserver change.

- Go to Domains in your Icemail dashboard
- Click Add Domain → Connect Existing Domain
- Select Connect via Cloudflare
- Click Authorize and log in to your Cloudflare account
- Select the domain and click Connect
- Icemail automatically adds SPF, DKIM, DMARC, and MX records

**Benefit:** Your existing Cloudflare configuration (other DNS records, page rules, proxying settings) remains untouched.

---

### Option B: Change Nameservers (Standard Method)

If you prefer, you can update your domain's nameservers to point to Icemail/Cloudflare:

- Go to Domains → Add Domain → Connect Existing Domain
- Copy the Icemail nameservers shown in the dashboard
- Log in to your domain registrar (GoDaddy, Namecheap, etc.)
- Replace the current nameservers with the Icemail nameservers
- DNS propagation takes up to 24 hours

---

### DNS Records Added Automatically

Both methods auto-configure the same DNS records once connected:

- SPF — authorizes Icemail to send email on behalf of your domain
- DKIM — cryptographic signature for email authentication
- DMARC — policy for handling unauthenticated emails
- MX — routes incoming email to the right server

---

### Common Issue: Domain Already Has a Google Workspace

If you see a 'Workspace Already Exists' error, the domain has an existing Google Workspace that must be cleared first. Contact **team@icemail.ai** — the team can clear it from the backend.

---

Need help connecting your domain? Email **team@icemail.ai**.""",
})

# 10. Mailbox reactivation policy
ARTICLES.append({
    "title": "🔄 Mailbox Reactivation Policy – What Happens After Deletion",
    "collection": "billing-subscription",
    "filename": "mailbox-reactivation-policy.mdx",
    "nodes": [
        paragraph(p("Deleting a mailbox doesn't immediately remove it from Google or Microsoft systems. Here's exactly what happens and how to recover mailboxes if you change your mind.")),
        hr(),
        heading(3, "Soft Deletion vs Permanent Deletion"),
        paragraph(p("When you delete a mailbox from the Icemail UI, it enters a 7-day grace period:")),
        bullet_list([
            "Day 0–7: Mailbox is 'soft deleted' — it still exists on Google/Microsoft systems",
            "Day 7+: Mailbox is permanently deleted and cannot be recovered",
        ]),
        hr(),
        heading(3, "Reactivating Within 7 Days"),
        paragraph(p("If you deleted a mailbox by mistake or changed your mind within 7 days:")),
        bullet_list([
            "Contact team@icemail.ai immediately",
            "Provide your account email and the domain name(s) to restore",
            "Reactivation is charged at the standard rate: $2.50/mailbox/month for Google and Microsoft",
            "Mailboxes will be restored within a few hours",
        ]),
        hr(),
        heading(3, "After 7 Days – What's Lost Permanently"),
        paragraph(p("After the 7-day window closes:")),
        bullet_list([
            "The Google/Microsoft workspace licenses are released and cannot be recovered",
            "All emails in those mailboxes are permanently deleted",
            "The mailbox address cannot be restored on Icemail",
            "You'd need to create brand new mailboxes (which restarts the warmup process)",
        ]),
        hr(),
        heading(3, "Domain Reactivation"),
        paragraph(p("The same 7-day rule applies to domains. If you delete a domain from Icemail, contact "), p("team@icemail.ai", True), p(" within 7 days to restore it along with its mailboxes.")),
        hr(),
        heading(3, "Best Practice: Deactivate Instead of Delete"),
        paragraph(p("If you're unsure whether you'll need a mailbox again, consider deactivating it (which pauses billing) rather than permanently deleting it. Contact "), p("team@icemail.ai", True), p(" to discuss deactivation options.")),
        hr(),
        paragraph(p("Need to reactivate? Email "), p("team@icemail.ai", True), p(" immediately — don't wait.")),
    ],
    "md": """Deleting a mailbox doesn't immediately remove it from Google or Microsoft systems. Here's exactly what happens and how to recover mailboxes if you change your mind.

---

### Soft Deletion vs Permanent Deletion

When you delete a mailbox from the Icemail UI, it enters a 7-day grace period:

- Day 0–7: Mailbox is 'soft deleted' — it still exists on Google/Microsoft systems
- Day 7+: Mailbox is permanently deleted and cannot be recovered

---

### Reactivating Within 7 Days

If you deleted a mailbox by mistake or changed your mind within 7 days:

- Contact team@icemail.ai immediately
- Provide your account email and the domain name(s) to restore
- Reactivation is charged at the standard rate: $2.50/mailbox/month for Google and Microsoft
- Mailboxes will be restored within a few hours

---

### After 7 Days – What's Lost Permanently

After the 7-day window closes:

- The Google/Microsoft workspace licenses are released and cannot be recovered
- All emails in those mailboxes are permanently deleted
- The mailbox address cannot be restored on Icemail
- You'd need to create brand new mailboxes (which restarts the warmup process)

---

### Domain Reactivation

The same 7-day rule applies to domains. If you delete a domain from Icemail, contact **team@icemail.ai** within 7 days to restore it along with its mailboxes.

---

### Best Practice: Deactivate Instead of Delete

If you're unsure whether you'll need a mailbox again, consider deactivating it (which pauses billing) rather than permanently deleting it. Contact **team@icemail.ai** to discuss deactivation options.

---

Need to reactivate? Email **team@icemail.ai** immediately — don't wait.""",
})

# 11. Max mailboxes per domain
ARTICLES.append({
    "title": "📊 Maximum Mailboxes Per Domain – Limits & Best Practices",
    "collection": "mailbox-management",
    "filename": "maximum-mailboxes-per-domain-limits-best-practices.mdx",
    "nodes": [
        paragraph(p("How many mailboxes can you create on a single domain? The answer depends on mailbox type — and the recommended limit for cold email is lower than the technical maximum.")),
        hr(),
        heading(3, "Technical Limits by Mailbox Type"),
        bullet_list([
            "Google Workspace: up to 20 mailboxes per domain (technical limit)",
            "Microsoft 365: similar limits apply (~20 per domain)",
            "Azure: up to 100 mailboxes per domain ($30/domain/month flat rate)",
            "SMTP: up to 10 mailboxes per domain (dedicated IP per domain)",
        ]),
        hr(),
        heading(3, "Recommended Limit for Cold Email"),
        paragraph(p("For Google and Microsoft mailboxes used for cold email, Icemail recommends:")),
        paragraph(p("2–3 mailboxes per domain — not more.", True)),
        paragraph(p("Why:")),
        bullet_list([
            "Too many mailboxes on one domain concentrates your sending reputation risk",
            "If one mailbox gets flagged, it can affect all mailboxes sharing that domain",
            "Multiple domains with fewer mailboxes each is safer and more scalable",
            "2–3 mailboxes/domain × 15 cold emails/day = 30–45 cold emails per domain per day",
        ]),
        hr(),
        heading(3, "What Happens If You Exceed Limits?"),
        paragraph(p("If you attempt to create more mailboxes than the technical limit allows:")),
        bullet_list([
            "The excess mailboxes will show 'Failed' status",
            "You'll need to delete the extra mailboxes — the support team can help",
            "Previously created mailboxes on the same domain are not affected",
        ]),
        hr(),
        heading(3, "The Right Scaling Strategy"),
        paragraph(p("Instead of adding more mailboxes per domain, add more domains:")),
        bullet_list([
            "5 domains × 3 mailboxes = 15 mailboxes (safer than 1 domain × 15 mailboxes)",
            "Use the Mailbox Calculator at icemail.ai/cold-email-mailbox-calculator to plan your infrastructure",
            "Vary domain TLDs and names to diversify risk",
        ]),
        hr(),
        paragraph(p("Questions about scaling? Email "), p("team@icemail.ai", True), p(".")),
    ],
    "md": """How many mailboxes can you create on a single domain? The answer depends on mailbox type — and the recommended limit for cold email is lower than the technical maximum.

---

### Technical Limits by Mailbox Type

- Google Workspace: up to 20 mailboxes per domain (technical limit)
- Microsoft 365: similar limits apply (~20 per domain)
- Azure: up to 100 mailboxes per domain ($30/domain/month flat rate)
- SMTP: up to 10 mailboxes per domain (dedicated IP per domain)

---

### Recommended Limit for Cold Email

For Google and Microsoft mailboxes used for cold email, Icemail recommends:

**2–3 mailboxes per domain — not more.**

Why:

- Too many mailboxes on one domain concentrates your sending reputation risk
- If one mailbox gets flagged, it can affect all mailboxes sharing that domain
- Multiple domains with fewer mailboxes each is safer and more scalable
- 2–3 mailboxes/domain × 15 cold emails/day = 30–45 cold emails per domain per day

---

### What Happens If You Exceed Limits?

If you attempt to create more mailboxes than the technical limit allows:

- The excess mailboxes will show 'Failed' status
- You'll need to delete the extra mailboxes — the support team can help
- Previously created mailboxes on the same domain are not affected

---

### The Right Scaling Strategy

Instead of adding more mailboxes per domain, add more domains:

- 5 domains × 3 mailboxes = 15 mailboxes (safer than 1 domain × 15 mailboxes)
- Use the Mailbox Calculator at icemail.ai/cold-email-mailbox-calculator to plan your infrastructure
- Vary domain TLDs and names to diversify risk

---

Questions about scaling? Email **team@icemail.ai**.""",
})

# 12. Pre-warmed sending ramp
ARTICLES.append({
    "title": "🔥 Pre-Warmed Mailboxes – Sending Ramp-Up Schedule & Best Practices",
    "collection": "mailbox-management",
    "filename": "pre-warmed-mailboxes-sending-ramp-up-schedule.mdx",
    "nodes": [
        paragraph(p("Pre-warmed mailboxes have already completed a warmup period, so you can start sending faster. But 'pre-warmed' doesn't mean 'unlimited sending immediately' — here's how to ramp up safely.")),
        hr(),
        heading(3, "What Are Pre-Warmed Mailboxes?"),
        paragraph(p("Pre-warmed Google Workspace mailboxes at Icemail have undergone 5+ weeks of automated email warmup before being handed to you. They already have positive sending history and established reputation.")),
        paragraph(p("Price: "), p("$5/mailbox/month", True), p(" (vs $2.50 for standard mailboxes).")),
        hr(),
        heading(3, "Recommended Sending Ramp-Up Schedule"),
        bullet_list([
            "Week 1: 30–50 cold emails per mailbox per day",
            "Week 2–3: ramp up to 50–70 per day if no deliverability issues",
            "Week 4+: up to 100 per day if inbox placement remains strong",
        ]),
        paragraph(p("Keep warmup enabled throughout:", True), p(" Even while sending cold emails, keep your warmup tool running at 10–20 emails/day. This maintains your positive sending signals.")),
        hr(),
        heading(3, "How to Use Pre-Warmed Mailboxes"),
        bullet_list([
            "Go to Mailboxes in your dashboard — pre-warmed mailboxes appear just like regular ones",
            "Export them to your outreach tool (Instantly, Smartlead, etc.) the same way",
            "Enable warmup in your outreach tool alongside your cold email campaigns",
            "Start at the recommended volume and monitor bounce rates and spam complaints",
        ]),
        hr(),
        heading(3, "Domain Forwarding for Pre-Warmed Domains"),
        paragraph(p("If your pre-warmed mailboxes came with pre-warmed domains, set up domain forwarding to redirect the domain to your main website. Go to Domains → Domain Settings → Domain Forwarding.")),
        hr(),
        heading(3, "Profile Pictures"),
        paragraph(p("Profile pictures improve reply rates. Contact "), p("team@icemail.ai", True), p(" — the team can add professional profile pictures to your pre-warmed mailboxes from the backend.")),
        hr(),
        heading(3, "What To Monitor"),
        bullet_list([
            "Bounce rate: keep below 3%",
            "Spam complaints: keep below 0.1%",
            "Reply rate: should be above 1% for well-targeted campaigns",
            "Inbox placement: use inbox tests to verify emails aren't hitting spam",
        ]),
        hr(),
        paragraph(p("Questions about pre-warmed mailboxes? Email "), p("team@icemail.ai", True), p(".")),
    ],
    "md": """Pre-warmed mailboxes have already completed a warmup period, so you can start sending faster. But 'pre-warmed' doesn't mean 'unlimited sending immediately' — here's how to ramp up safely.

---

### What Are Pre-Warmed Mailboxes?

Pre-warmed Google Workspace mailboxes at Icemail have undergone 5+ weeks of automated email warmup before being handed to you. They already have positive sending history and established reputation.

Price: **$5/mailbox/month** (vs $2.50 for standard mailboxes).

---

### Recommended Sending Ramp-Up Schedule

- Week 1: 30–50 cold emails per mailbox per day
- Week 2–3: ramp up to 50–70 per day if no deliverability issues
- Week 4+: up to 100 per day if inbox placement remains strong

**Keep warmup enabled throughout:** Even while sending cold emails, keep your warmup tool running at 10–20 emails/day. This maintains your positive sending signals.

---

### How to Use Pre-Warmed Mailboxes

- Go to Mailboxes in your dashboard — pre-warmed mailboxes appear just like regular ones
- Export them to your outreach tool (Instantly, Smartlead, etc.) the same way
- Enable warmup in your outreach tool alongside your cold email campaigns
- Start at the recommended volume and monitor bounce rates and spam complaints

---

### Domain Forwarding for Pre-Warmed Domains

If your pre-warmed mailboxes came with pre-warmed domains, set up domain forwarding to redirect the domain to your main website. Go to Domains → Domain Settings → Domain Forwarding.

---

### Profile Pictures

Profile pictures improve reply rates. Contact **team@icemail.ai** — the team can add professional profile pictures to your pre-warmed mailboxes from the backend.

---

### What To Monitor

- Bounce rate: keep below 3%
- Spam complaints: keep below 0.1%
- Reply rate: should be above 1% for well-targeted campaigns
- Inbox placement: use inbox tests to verify emails aren't hitting spam

---

Questions about pre-warmed mailboxes? Email **team@icemail.ai**.""",
})

# 13. DKIM for Microsoft
ARTICLES.append({
    "title": "✉️ DKIM Setup for Microsoft 365 Mailboxes – Setup & Verification",
    "collection": "mailbox-management",
    "filename": "dkim-setup-for-microsoft-365-mailboxes.mdx",
    "nodes": [
        paragraph(p("DKIM (DomainKeys Identified Mail) is a critical email authentication record. For Microsoft 365 mailboxes, setup can take longer than Google — here's what to expect and how to verify.")),
        hr(),
        heading(3, "Is DKIM Set Up Automatically?"),
        paragraph(p("Yes — Icemail configures DKIM automatically for both Google and Microsoft mailboxes. You don't need to set it up manually.")),
        bullet_list([
            "Google Workspace: DKIM is typically configured within a few hours of mailbox activation",
            "Microsoft 365: DKIM can take up to 24–48 hours due to Microsoft's API processing times",
        ]),
        hr(),
        heading(3, "How to Verify Your DKIM Record"),
        bullet_list([
            "Go to Domains in your Icemail dashboard",
            "Click on your domain",
            "Open the DNS Records tab",
            "Look for a TXT record starting with 'v=DKIM1'",
            "You can also verify at mxtoolbox.com/dkim.aspx",
        ]),
        hr(),
        heading(3, "DKIM Is Missing After 24 Hours"),
        paragraph(p("If DKIM hasn't appeared after 24 hours for a Microsoft mailbox:")),
        bullet_list([
            "Contact team@icemail.ai with your domain name",
            "The team can manually add and verify the DKIM record from the Microsoft admin console",
            "This is a known quirk with Microsoft's API — it doesn't affect all domains but does happen",
        ]),
        hr(),
        heading(3, "Why DKIM Matters"),
        bullet_list([
            "Prevents email spoofing — proves emails actually came from your domain",
            "Required by major email providers (Gmail, Outlook) for inbox placement",
            "Missing DKIM significantly increases spam folder rates",
            "Essential for cold email campaigns where deliverability is critical",
        ]),
        hr(),
        heading(3, "DMARC and SPF"),
        paragraph(p("DKIM works alongside SPF and DMARC. All three are configured automatically by Icemail when you connect a domain and assign mailboxes. If any of the three is missing, contact "), p("team@icemail.ai", True), p(".")),
        hr(),
        paragraph(p("DKIM issues? Email "), p("team@icemail.ai", True), p(" with your domain name.")),
    ],
    "md": """DKIM (DomainKeys Identified Mail) is a critical email authentication record. For Microsoft 365 mailboxes, setup can take longer than Google — here's what to expect and how to verify.

---

### Is DKIM Set Up Automatically?

Yes — Icemail configures DKIM automatically for both Google and Microsoft mailboxes. You don't need to set it up manually.

- Google Workspace: DKIM is typically configured within a few hours of mailbox activation
- Microsoft 365: DKIM can take up to 24–48 hours due to Microsoft's API processing times

---

### How to Verify Your DKIM Record

- Go to Domains in your Icemail dashboard
- Click on your domain
- Open the DNS Records tab
- Look for a TXT record starting with 'v=DKIM1'
- You can also verify at mxtoolbox.com/dkim.aspx

---

### DKIM Is Missing After 24 Hours

If DKIM hasn't appeared after 24 hours for a Microsoft mailbox:

- Contact team@icemail.ai with your domain name
- The team can manually add and verify the DKIM record from the Microsoft admin console
- This is a known quirk with Microsoft's API — it doesn't affect all domains but does happen

---

### Why DKIM Matters

- Prevents email spoofing — proves emails actually came from your domain
- Required by major email providers (Gmail, Outlook) for inbox placement
- Missing DKIM significantly increases spam folder rates
- Essential for cold email campaigns where deliverability is critical

---

### DMARC and SPF

DKIM works alongside SPF and DMARC. All three are configured automatically by Icemail when you connect a domain and assign mailboxes. If any of the three is missing, contact **team@icemail.ai**.

---

DKIM issues? Email **team@icemail.ai** with your domain name.""",
})

# 14. DNS records FAQ
ARTICLES.append({
    "title": "🌐 DNS Records FAQ – Timing, Propagation & Common Issues",
    "collection": "domain-management",
    "filename": "dns-records-faq-timing-propagation-common-issues.mdx",
    "nodes": [
        paragraph(p("DNS records can be confusing — when do they get added, how long do they take, and what do you do when something looks wrong? This FAQ answers the most common questions.")),
        hr(),
        heading(3, "When Are DNS Records Added?"),
        paragraph(p("DNS records are added ", True), p("automatically", True), p(" when you assign mailboxes to a domain. You don't add them manually — Icemail handles it.")),
        bullet_list([
            "SPF, DKIM, DMARC, and MX are all configured automatically",
            "Records appear within minutes of mailbox assignment for Cloudflare-connected domains",
            "For non-Cloudflare domains, allow up to 24 hours for propagation",
        ]),
        hr(),
        heading(3, "How Long Does DNS Propagation Take?"),
        bullet_list([
            "Cloudflare-connected domains: almost instant (1–5 minutes)",
            "Standard nameserver transfer: up to 24 hours",
            "Full global propagation: up to 48 hours in some regions",
        ]),
        paragraph(p("Check propagation status at "), p("dnschecker.org", True), p(" — enter your domain and record type to see worldwide propagation.")),
        hr(),
        heading(3, "Common Issues"),
        heading(3, "'Add New Record' Button Is Unresponsive"),
        paragraph(p("Refresh the page. If still unresponsive, contact "), p("team@icemail.ai", True), p(" — the team can add DNS records manually from the backend.")),
        heading(3, "SPF Record Not Showing"),
        paragraph(p("SPF is added after mailbox assignment. If you connected the domain but haven't assigned mailboxes yet, SPF won't appear. Assign at least one mailbox, then wait 15 minutes.")),
        heading(3, "DMARC Not Set Up"),
        paragraph(p("DMARC is configured along with SPF and DKIM. If it's missing 24 hours after mailbox assignment, contact "), p("team@icemail.ai", True), p(".")),
        heading(3, "DNS Records Show But Mailbox Is Still Not Active"),
        paragraph(p("DNS records and mailbox provisioning are separate processes. DNS records can be in place while the mailbox is still being provisioned. Allow the full provisioning window (1–24 hours) for the mailbox to become active.")),
        hr(),
        heading(3, "Checking Your DNS Records in Icemail"),
        bullet_list([
            "Go to Domains in your dashboard",
            "Click on your domain",
            "Open the DNS Records tab",
            "All configured records (SPF, DKIM, DMARC, MX) are listed with their values",
        ]),
        hr(),
        paragraph(p("DNS issues? Email "), p("team@icemail.ai", True), p(" with your domain name and what's missing.")),
    ],
    "md": """DNS records can be confusing — when do they get added, how long do they take, and what do you do when something looks wrong? This FAQ answers the most common questions.

---

### When Are DNS Records Added?

DNS records are added **automatically** when you assign mailboxes to a domain. You don't add them manually — Icemail handles it.

- SPF, DKIM, DMARC, and MX are all configured automatically
- Records appear within minutes of mailbox assignment for Cloudflare-connected domains
- For non-Cloudflare domains, allow up to 24 hours for propagation

---

### How Long Does DNS Propagation Take?

- Cloudflare-connected domains: almost instant (1–5 minutes)
- Standard nameserver transfer: up to 24 hours
- Full global propagation: up to 48 hours in some regions

Check propagation status at **dnschecker.org** — enter your domain and record type to see worldwide propagation.

---

### Common Issues

### 'Add New Record' Button Is Unresponsive

Refresh the page. If still unresponsive, contact **team@icemail.ai** — the team can add DNS records manually from the backend.

### SPF Record Not Showing

SPF is added after mailbox assignment. If you connected the domain but haven't assigned mailboxes yet, SPF won't appear. Assign at least one mailbox, then wait 15 minutes.

### DMARC Not Set Up

DMARC is configured along with SPF and DKIM. If it's missing 24 hours after mailbox assignment, contact **team@icemail.ai**.

### DNS Records Show But Mailbox Is Still Not Active

DNS records and mailbox provisioning are separate processes. DNS records can be in place while the mailbox is still being provisioned. Allow the full provisioning window (1–24 hours) for the mailbox to become active.

---

### Checking Your DNS Records in Icemail

- Go to Domains in your dashboard
- Click on your domain
- Open the DNS Records tab
- All configured records (SPF, DKIM, DMARC, MX) are listed with their values

---

DNS issues? Email **team@icemail.ai** with your domain name and what's missing.""",
})

# 15. Sending limits
ARTICLES.append({
    "title": "📬 Understanding Mailbox Sending Limits & Daily Caps in Icemail",
    "collection": "mailbox-management",
    "filename": "understanding-mailbox-sending-limits.mdx",
    "nodes": [
        paragraph(p("Every mailbox type in Icemail has recommended daily sending limits. Exceeding them risks account flags, spam complaints, and reduced deliverability. Here's what you need to know.")),
        hr(),
        heading(3, "Recommended Daily Limits by Mailbox Type"),
        bullet_list([
            "Google Workspace: 15 cold emails + 15 warmup emails per mailbox per day (1:1 ratio)",
            "Microsoft 365: 15 cold emails + 15 warmup emails per mailbox per day (1:1 ratio)",
            "SMTP (dedicated IP): up to 50 emails per mailbox per day",
            "Azure: 5 cold + 5 warmup per mailbox per day (10 total)",
        ]),
        paragraph(p("Always send cold email and warmup in parallel — the 1:1 ratio is important for maintaining inbox placement.")),
        hr(),
        heading(3, "What Happens If You Exceed Limits?"),
        bullet_list([
            "Google/Microsoft may temporarily flag or throttle the account",
            "Bounce rates increase as receiving servers start rejecting messages",
            "Spam complaint rates rise, which damages domain reputation",
            "Extended over-sending can lead to account suspension",
        ]),
        hr(),
        heading(3, "How to Recover After Hitting Limits"),
        bullet_list([
            "Reduce volume immediately — stop cold outreach for 48–72 hours",
            "Keep warmup running at a lower volume (5–10/day)",
            "Monitor bounce rates and spam complaints",
            "Gradually resume at a lower starting volume",
        ]),
        hr(),
        heading(3, "Scaling Without Exceeding Limits"),
        paragraph(p("The right way to send more email is to add more mailboxes and domains, not to push individual limits:")),
        bullet_list([
            "10 mailboxes × 15 emails/day = 150 cold emails/day",
            "Use 2–3 mailboxes per domain across multiple domains",
            "Calculate your required infrastructure at icemail.ai/cold-email-mailbox-calculator",
        ]),
        hr(),
        heading(3, "Failed Emails in Your Outreach Tool"),
        paragraph(p("If your outreach tool shows failed sends:")),
        bullet_list([
            "Check if you've hit daily sending limits in the tool settings",
            "Verify the mailbox is still connected (re-export if needed)",
            "Don't retry failed emails immediately — wait 24 hours",
            "Contact team@icemail.ai if multiple mailboxes show systematic failures",
        ]),
        hr(),
        paragraph(p("Questions about sending strategy? Email "), p("team@icemail.ai", True), p(".")),
    ],
    "md": """Every mailbox type in Icemail has recommended daily sending limits. Exceeding them risks account flags, spam complaints, and reduced deliverability. Here's what you need to know.

---

### Recommended Daily Limits by Mailbox Type

- Google Workspace: 15 cold emails + 15 warmup emails per mailbox per day (1:1 ratio)
- Microsoft 365: 15 cold emails + 15 warmup emails per mailbox per day (1:1 ratio)
- SMTP (dedicated IP): up to 50 emails per mailbox per day
- Azure: 5 cold + 5 warmup per mailbox per day (10 total)

Always send cold email and warmup in parallel — the 1:1 ratio is important for maintaining inbox placement.

---

### What Happens If You Exceed Limits?

- Google/Microsoft may temporarily flag or throttle the account
- Bounce rates increase as receiving servers start rejecting messages
- Spam complaint rates rise, which damages domain reputation
- Extended over-sending can lead to account suspension

---

### How to Recover After Hitting Limits

- Reduce volume immediately — stop cold outreach for 48–72 hours
- Keep warmup running at a lower volume (5–10/day)
- Monitor bounce rates and spam complaints
- Gradually resume at a lower starting volume

---

### Scaling Without Exceeding Limits

The right way to send more email is to add more mailboxes and domains, not to push individual limits:

- 10 mailboxes × 15 emails/day = 150 cold emails/day
- Use 2–3 mailboxes per domain across multiple domains
- Calculate your required infrastructure at icemail.ai/cold-email-mailbox-calculator

---

### Failed Emails in Your Outreach Tool

If your outreach tool shows failed sends:

- Check if you've hit daily sending limits in the tool settings
- Verify the mailbox is still connected (re-export if needed)
- Don't retry failed emails immediately — wait 24 hours
- Contact team@icemail.ai if multiple mailboxes show systematic failures

---

Questions about sending strategy? Email **team@icemail.ai**.""",
})


def main():
    print(f"Creating {len(ARTICLES)} articles in Gleap...\n")
    created = []

    for art in ARTICLES:
        try:
            article_id = create_article(
                title=art["title"],
                collection_slug=art["collection"],
                filename=art["filename"],
                content_nodes=art["nodes"],
                md_body=art["md"],
            )
            created.append((art["title"], article_id))
        except Exception as e:
            print(f"  ❌ FAILED: {art['title']}: {e}")
        time.sleep(0.5)

    print(f"\n✅ Created {len(created)}/{len(ARTICLES)} articles")
    for title, aid in created:
        print(f"  {aid}: {title[:60]}")


if __name__ == "__main__":
    main()
