#!/usr/bin/env python3
"""
Script to create 15 Icemail help articles in Gleap help center.
For each article: POST to create, PUT content, save MDX file.
"""

import json
import os
import requests

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjZhMmY4YjQ3ODYyODU5OWNlNWRjODE0OSIsInByb2plY3RJZCI6IjY4MzVjYzRkYTVkM2E0YjhlNGM4ZTI3NCIsInNlY3JldEFwaUtleSI6IjBoc1RKTmZDeUE0UTBLTEtad3FnZjAydzNIRThqUFVmIiwidXNlclR5cGUiOiJzZXJ2aWNlX2FjY291bnQiLCJpYXQiOjE3ODE1MDA3NDN9.lyJC8-8g8t106JRjPUU3dDB9t222k9C7HgW0xYoxL80"
PROJECT = "6835cc4da5d3a4b8e4c8e274"
BASE_URL = "https://api.gleap.io"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "project": PROJECT,
    "Content-Type": "application/json",
}

COLLECTIONS = {
    "domain-management": "6849b63fe92e06806c87c22a",
    "mailbox-management": "6849b68247ecc2e7b5a14dfa",
    "mailbox-export-integrations": "6849b6b8e92e06806c8bd279",
    "billing-subscription": "6849b6e7c3746dd2eeaefbdf",
    "faqs": "6849b767ed77fcb13166ed6d",
    "getting-started": "6a2f9dacf10a74503708e7c7",
}

DOCS_DIR = "/home/user/docs"


def p(text):
    """Create a paragraph node."""
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def h2(text):
    """Create a heading level 2 node."""
    return {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": text}]}


def h3(text):
    """Create a heading level 3 node."""
    return {"type": "heading", "attrs": {"level": 3}, "content": [{"type": "text", "text": text}]}


def hr():
    """Create a horizontal rule node."""
    return {"type": "horizontalRule"}


def ul(*items):
    """Create a bullet list node from a list of strings."""
    list_items = []
    for item in items:
        list_items.append({
            "type": "listItem",
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": item}]}]
        })
    return {"type": "bulletList", "content": list_items}


def make_doc(content_nodes):
    """Wrap nodes in a TipTap doc."""
    return {"type": "doc", "content": content_nodes}


def save_mdx(path, title, description, gleap_id, collection_slug, collection_id):
    """Save MDX file with frontmatter."""
    full_path = os.path.join(DOCS_DIR, path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    frontmatter = f"""---
title: "{title}"
description: "{description}"
gleap_id: "{gleap_id}"
gleap_collection: "{collection_id}"
gleap_collection_slug: "{collection_slug}"
isDraft: false
---
"""
    with open(full_path, "w") as f:
        f.write(frontmatter)
    print(f"  Saved MDX: {full_path}")


def plain_text_from_doc(tiptap_doc):
    """Extract plain text from a TipTap doc."""
    parts = []
    def extract(node):
        if isinstance(node, dict):
            if node.get("type") == "text":
                parts.append(node.get("text", ""))
            for child in node.get("content", []):
                extract(child)
    extract(tiptap_doc)
    return " ".join(part for part in parts if part.strip())


def create_article(title, collection_slug, mdx_path, description, body_doc):
    """POST to create article, PUT content, save MDX."""
    collection_id = COLLECTIONS[collection_slug]
    print(f"\nCreating: {title}")

    # Step 1: POST to create article (with full content)
    plain = plain_text_from_doc(body_doc)
    post_body = {
        "title": {"en": title},
        "description": {"en": description},
        "content": {"en": body_doc},
        "plainContent": {"en": plain},
        "isDraft": False,
    }
    resp = requests.post(
        f"{BASE_URL}/v3/helpcenter/collections/{collection_id}/articles",
        headers=HEADERS,
        json=post_body,
    )
    if not resp.ok:
        print(f"  ERROR creating article: {resp.status_code} {resp.text[:300]}")
        return None

    data = resp.json()
    gleap_id = data.get("id") or data.get("_id")
    if not gleap_id:
        print(f"  ERROR: no id in response: {data}")
        return None
    print(f"  Created with id: {gleap_id}")

    # Step 3: Save MDX
    save_mdx(mdx_path, title, description, gleap_id, collection_slug, collection_id)
    return gleap_id


# =============================================================================
# ARTICLE DEFINITIONS
# =============================================================================

articles = []

# --- Article 1 ---------------------------------------------------------------
articles.append({
    "title": "Mailboxes Stuck in Processing – Complete Troubleshooting Guide",
    "collection_slug": "mailbox-management",
    "mdx_path": "gleap/mailbox-management/mailboxes-stuck-in-processing-troubleshooting-guide.mdx",
    "description": "Learn why mailboxes get stuck in processing, how long they typically take, and what steps to take if yours hasn't activated.",
    "body": make_doc([
        p("Seeing a \"Processing\" status on your mailboxes? This guide explains what's happening and what to do."),
        hr(),
        h2("What Does \"Processing\" Status Mean?"),
        p("When a mailbox shows \"Processing,\" it means Icemail has submitted the provisioning request to Google or Microsoft and is waiting for their systems to complete the setup. This is normal and expected after ordering mailboxes."),
        hr(),
        h2("How Long Does Processing Take?"),
        h3("Google Mailboxes"),
        ul(
            "Typically 1–4 hours for most mailboxes",
            "Can sometimes take longer due to Google’s provisioning queue",
            "If ordered in bulk, later mailboxes in the batch may take more time",
        ),
        h3("Microsoft Mailboxes"),
        ul(
            "Generally takes longer than Google",
            "Can take 4–24 hours, especially during periods of high demand",
            "Bulk orders of 20+ mailboxes can take up to 24 hours to fully provision",
        ),
        hr(),
        h2("Common Causes of Delayed Processing"),
        h3("Cause #1: DNS Records Not Yet Complete"),
        p("SPF, DKIM, and DMARC records must be set up before mailboxes can finish provisioning. Make sure your domain’s DNS records are all present before expecting mailboxes to activate."),
        h3("Cause #2: High Demand in the Provisioning Queue"),
        p("Google and Microsoft process mailbox provisioning requests in queues. During peak times, your request may be delayed behind other orders."),
        h3("Cause #3: Batch Ordering Delays"),
        p("When you order multiple mailboxes at once, they are provisioned sequentially. The later mailboxes in a batch naturally take longer — this is normal behavior."),
        hr(),
        h2("What You Should Do"),
        ul(
            "Wait at least 4–6 hours before escalating — most mailboxes resolve on their own",
            "For bulk orders (20+ mailboxes), wait up to 24 hours before reaching out",
            "If still stuck after 24 hours, contact team@icemail.ai with your domain name and order details",
        ),
        hr(),
        h2("What You Should NOT Do"),
        ul(
            "Do NOT create more mailboxes on the same domain while others are still processing — this can cause additional delays",
            "Do not delete and re-order stuck mailboxes without first contacting support",
        ),
        hr(),
        h2("Need Help?"),
        p("If your mailboxes have been in processing for more than 24 hours, contact the Icemail team at team@icemail.ai with your domain name and the number of affected mailboxes."),
    ]),
})

# --- Article 2 ---------------------------------------------------------------
articles.append({
    "title": "App Passwords for Google Mailboxes – How They Work & Common Issues",
    "collection_slug": "mailbox-management",
    "mdx_path": "gleap/mailbox-management/app-passwords-for-google-mailboxes-how-they-work.mdx",
    "description": "Understand what app passwords are, how Icemail generates them, where to find them, and how to use them with SMTP/IMAP connections.",
    "body": make_doc([
        p("App passwords are a critical part of how Google mailboxes work in Icemail. This guide explains everything you need to know."),
        hr(),
        h2("What Are App Passwords?"),
        p("App passwords are special passwords generated by Google that allow third-party apps (like outreach tools) to connect to a mailbox via SMTP or IMAP — even when 2-factor authentication is enabled."),
        p("Icemail generates app passwords automatically when your mailbox becomes active. You do not need to create them manually."),
        hr(),
        h2("NEVER Change Your Google Mailbox Password Manually"),
        p("Changing the Google account password manually will immediately invalidate the app password. This will break your SMTP/IMAP connection in any outreach tool connected to that mailbox."),
        p("If you need to reset a connection, use the Icemail dashboard to regenerate the app password instead of changing the Google account password."),
        hr(),
        h2("Where to Find Your App Password"),
        ul(
            "Option 1: Go to Mailboxes in your Icemail dashboard → click on the mailbox → view the app password in mailbox details",
            "Option 2: Export mailboxes as CSV — the app password is included in the CSV export",
        ),
        h3("App Password Is Missing?"),
        p("If your app password is not showing, it usually means the mailbox is still in processing state. Wait for the mailbox to become active, then the app password will appear automatically."),
        hr(),
        h2("SMTP & IMAP Settings for Google Mailboxes"),
        h3("SMTP Settings"),
        ul(
            "SMTP Server: smtp.gmail.com",
            "Port: 587 (TLS) or 465 (SSL)",
            "Username: your full email address (e.g. john@yourdomain.com)",
            "Password: your app password (NOT your Google account password)",
        ),
        h3("IMAP Settings"),
        ul(
            "IMAP Server: imap.gmail.com",
            "Port: 993 (SSL)",
            "Username: your full email address",
            "Password: your app password",
        ),
        hr(),
        h2("Troubleshooting SMTP Disconnections"),
        p("If your outreach tool shows the mailbox as disconnected or SMTP authentication fails:"),
        ul(
            "Try regenerating the app password from the Icemail dashboard",
            "Re-export the mailbox credentials to your outreach tool",
            "If the issue persists, contact team@icemail.ai with your domain name and mailbox email address",
        ),
    ]),
})

# --- Article 3 ---------------------------------------------------------------
articles.append({
    "title": "How to Cancel or Delete Mailboxes in Icemail",
    "collection_slug": "mailbox-management",
    "mdx_path": "gleap/mailbox-management/how-to-cancel-or-delete-mailboxes-in-icemail.mdx",
    "description": "Step-by-step guide to cancelling or deleting mailboxes and domains in Icemail, including billing implications and reactivation policy.",
    "body": make_doc([
        p("This guide covers how to cancel or delete mailboxes and domains in Icemail, what happens to your billing, and what to know about reactivation."),
        hr(),
        h2("How to Delete a Mailbox"),
        ul(
            "Go to Mailboxes in your Icemail dashboard",
            "Select the mailbox you want to delete",
            "Click Delete and confirm",
        ),
        p("Deletion from the UI triggers a soft delete. Full removal from the backend takes 24–48 hours."),
        hr(),
        h2("How Billing Works After Deletion"),
        ul(
            "Deleting a mailbox stops billing in the next billing cycle — you won’t be charged again",
            "Wallet credits are NOT refunded after mailbox deletion (your wallet balance stays for future use)",
            "Stripe processing fees (3–4%) are non-refundable",
        ),
        hr(),
        h2("Cancelling a Domain"),
        p("You can cancel a domain to stop all mailboxes associated with it at once. Go to Domains → select the domain → click Delete/Cancel."),
        hr(),
        h2("Bulk Cancellation"),
        p("If you need to cancel many domains or mailboxes at once, contact team@icemail.ai. The Icemail team can perform bulk deletions from the backend, saving you time."),
        hr(),
        h2("Mailbox Reactivation Policy"),
        ul(
            "Within 7 days of deletion: mailboxes can be reactivated at standard pricing ($2.50/mailbox/month) — contact team@icemail.ai with your domain name",
            "After 7 days: mailboxes are permanently deleted from Google/Microsoft systems and cannot be recovered",
        ),
        p("Plan carefully before deleting mailboxes. Once the 7-day window has passed, recovery is not possible."),
        hr(),
        h2("Need Help?"),
        p("For bulk deletions or any questions about cancellation, contact team@icemail.ai."),
    ]),
})

# --- Article 4 ---------------------------------------------------------------
articles.append({
    "title": "How to Add Team Members & Manage Workspace Access in Icemail",
    "collection_slug": "mailbox-management",
    "mdx_path": "gleap/mailbox-management/how-to-add-team-members-manage-workspace-access.mdx",
    "description": "Learn how to invite team members to your Icemail workspace, manage client access, and handle multiple workspaces.",
    "body": make_doc([
        p("Icemail uses workspaces to organize accounts. This guide explains how to invite team members, manage client access, and work with multiple workspaces."),
        hr(),
        h2("What Is a Workspace?"),
        p("A workspace in Icemail is your account environment — it contains your domains, mailboxes, billing, and settings. All team members invited to a workspace share access to its resources."),
        hr(),
        h2("How to Invite Team Members"),
        ul(
            "Go to Settings in your Icemail dashboard",
            "Click Team",
            "Click Invite Member",
            "Enter the team member’s email address and send the invitation",
        ),
        p("Invited team members will receive an email with instructions to join your workspace."),
        hr(),
        h2("Client Access"),
        p("If you manage mailboxes for clients, here’s how to handle access:"),
        ul(
            "Clients should create their own Icemail account first",
            "Once they have an account, you can invite their email address to your workspace",
            "Alternatively, clients can invite you to their workspace so you can manage it on their behalf",
        ),
        hr(),
        h2("Agency Use Case: Managing Multiple Client Workspaces"),
        p("If you’re an agency managing multiple clients:"),
        ul(
            "Ask each client to invite your Icemail account email to their workspace",
            "You can switch between workspaces from your account without needing separate logins",
            "All your clients’ domains and mailboxes remain in their respective workspaces",
        ),
        hr(),
        h2("Multiple Workspaces"),
        p("You can be a member of multiple workspaces from a single Icemail account. Use the workspace switcher in the dashboard to toggle between them."),
        hr(),
        h2("Two-Factor Authentication (2FA)"),
        h3("2FA on Mailboxes"),
        p("2FA cannot be removed from Icemail-provisioned mailboxes. It is required for security and for the mailbox sync to function correctly. This is a Google/Microsoft requirement."),
        h3("2FA on Your Icemail Account Login"),
        p("Each user manages their own Icemail account 2FA in their account settings. Support cannot disable 2FA on behalf of users."),
    ]),
})

# --- Article 5 ---------------------------------------------------------------
articles.append({
    "title": "Billing FAQ – Renewals, Auto-Renew, Auto Top-Up & Payment Issues",
    "collection_slug": "billing-subscription",
    "mdx_path": "gleap/billing-subscription/billing-faq-renewals-auto-renew-auto-topup.mdx",
    "description": "Answers to common billing questions: auto-renew, auto top-up, payment issues, invoices, and wallet credits.",
    "body": make_doc([
        p("Here are answers to the most common billing questions for Icemail users."),
        hr(),
        h2("What Is Auto-Renew?"),
        p("Auto-renew means your mailboxes automatically renew each month. Unless you manually cancel a mailbox, it will continue to renew and you will be charged each billing cycle."),
        hr(),
        h2("What Is Auto Top-Up?"),
        p("Auto top-up automatically adds funds to your Icemail wallet when your balance drops below a set threshold. This ensures your mailboxes don’t get deactivated due to insufficient balance."),
        p("You can enable, disable, and configure your top-up threshold in Billing settings."),
        hr(),
        h2("Why Was I Charged After Disabling Auto Top-Up?"),
        p("Disabling auto top-up only stops automatic wallet refills. If mailbox auto-renew is still enabled, renewal charges will still be processed when your mailboxes renew. To stop future charges, you must cancel the mailboxes themselves."),
        hr(),
        h2("My Mailboxes Were Deactivated Due to a Pending Renewal"),
        p("If your wallet balance was insufficient at renewal time, mailboxes may be deactivated. To reactivate them:"),
        ul(
            "Add wallet credits in Billing → Add Credits",
            "Your mailboxes should reactivate automatically once sufficient balance is available",
            "If they don’t reactivate within a few hours, contact team@icemail.ai",
        ),
        hr(),
        h2("Getting a Custom Invoice or Payment Link"),
        p("Icemail’s standard payment method is wallet-based. For large orders, custom invoices are available. Contact team@icemail.ai with your order details to arrange a custom payment."),
        hr(),
        h2("About Wallet Credits"),
        ul(
            "Wallet credits are prepaid — add funds and they are used as mailboxes renew",
            "Stripe processing fees (3–4%) are non-refundable",
            "Unused wallet balance is not automatically refunded",
        ),
        hr(),
        h2("How to View and Download Invoices"),
        ul(
            "Go to Billing in your dashboard",
            "Click View Invoice next to the relevant charge",
            "Download the PDF for your records",
        ),
        hr(),
        h2("Duplicate Charges"),
        p("If you believe you have been charged twice for the same item, contact team@icemail.ai immediately with your account email and the details of the duplicate charge."),
    ]),
})

# --- Article 6 ---------------------------------------------------------------
articles.append({
    "title": "How to Export Mailboxes from Icemail – API Method vs CSV Method",
    "collection_slug": "mailbox-export-integrations",
    "mdx_path": "gleap/mailbox-export-integrations/how-to-export-mailboxes-api-vs-csv-method.mdx",
    "description": "Learn the two methods to export Icemail mailboxes to outreach tools — direct integration and CSV — and which method to use.",
    "body": make_doc([
        p("Icemail offers two ways to export your mailboxes to outreach tools. Here’s what you need to know about each method."),
        hr(),
        h2("Method 1: Direct Integration (Recommended)"),
        ul(
            "Go to Mailboxes and select the mailboxes you want to export",
            "Click Export Mailboxes",
            "Choose your outreach platform from the list",
            "Authenticate with OAuth or your platform API key",
            "Done — mailboxes are connected via IMAP over SSL",
        ),
        p("This is the recommended method. It uses a secure OAuth/API connection, keeps mailboxes reliably connected, and is the most stable option for most platforms."),
        hr(),
        h2("Method 2: CSV Export"),
        p("The CSV export downloads a file containing your mailbox credentials (email address, app password, SMTP/IMAP settings)."),
        p("Important: CSV export uses IMAP credentials which can be less reliable than the direct integration method. This method is not recommended for most outreach tools."),
        hr(),
        h2("Using SMTP Credentials Directly"),
        p("For custom tools or platforms not listed in the direct integration menu, use SMTP credentials directly:"),
        ul(
            "SMTP server and port from your mailbox details",
            "Username: full email address",
            "Password: app password",
        ),
        hr(),
        h2("Adding a Custom Client ID"),
        p("Some outreach tools require a Google Admin Client ID to connect. If your tool requires this, contact team@icemail.ai — the team can add a custom Client ID from the backend."),
        hr(),
        h2("Exporting to Multiple Tools"),
        p("You can export the same mailboxes to different outreach platforms simultaneously. There is no restriction on connecting mailboxes to more than one tool."),
        hr(),
        h2("Re-Exporting Disconnected Mailboxes"),
        p("If your mailboxes disconnect from an outreach tool, try re-exporting from the Icemail dashboard using the direct integration method. This will re-establish the connection."),
        hr(),
        h2("Need Help?"),
        p("For export issues or custom integration needs, contact team@icemail.ai."),
    ]),
})

# --- Article 7 ---------------------------------------------------------------
articles.append({
    "title": "Why Is My Domain Forwarding Not Working? – Troubleshooting Guide",
    "collection_slug": "domain-management",
    "mdx_path": "gleap/domain-management/domain-forwarding-not-working-troubleshooting.mdx",
    "description": "Step-by-step troubleshooting for domain forwarding issues in Icemail, including common mistakes and how to fix them.",
    "body": make_doc([
        p("If your domain forwarding isn’t working as expected, work through this checklist to identify and resolve the issue."),
        hr(),
        h2("Check #1: Is the Target URL Correct?"),
        p("Make sure the URL you’ve entered as the forwarding destination includes the full protocol prefix — either https:// or http://. A URL without the protocol (e.g. just \"example.com\") will not work correctly."),
        hr(),
        h2("Check #2: Did You Save the Settings?"),
        p("After entering the forwarding URL, make sure you clicked Save. If you navigated away without saving, the settings were not applied."),
        hr(),
        h2("Check #3: Email Forwarding vs Web Forwarding"),
        p("Domain forwarding in Icemail is for web traffic (HTTP redirects), not email forwarding. If you want to forward emails to a different inbox, that is a separate setting. Make sure you’re configuring the correct type of forwarding."),
        hr(),
        h2("Check #4: Clear Browser Cache"),
        p("Browser caching can cause you to see the old behavior even after forwarding has been updated. Try visiting the domain in an incognito/private window, or clear your browser cache before testing."),
        hr(),
        h2("Check #5: Is the Domain Connected to Icemail?"),
        p("Domain forwarding only works for domains that are fully connected to Icemail (managed via Cloudflare). If your domain hasn’t been connected yet, forwarding won’t function."),
        hr(),
        h2("SSL Certificate Provisioning"),
        p("After setting up domain forwarding, SSL certificate provisioning can take 15–30 minutes. During this time, you may see a browser security warning. Wait for the certificate to be issued before concluding that forwarding is broken."),
        hr(),
        h2("Still Not Working After 1 Hour?"),
        p("If you’ve checked everything above and forwarding still isn’t working after an hour, contact team@icemail.ai with:"),
        ul(
            "The domain name",
            "The destination URL you’re trying to forward to",
            "What you’re seeing when you try to access the domain",
        ),
    ]),
})

# --- Article 8 ---------------------------------------------------------------
articles.append({
    "title": "Understanding 2FA on Icemail Mailboxes – Why It Can’t Be Removed",
    "collection_slug": "mailbox-management",
    "mdx_path": "gleap/mailbox-management/understanding-2fa-on-mailboxes-why-it-cannot-be-removed.mdx",
    "description": "Why 2FA is required on Icemail-provisioned mailboxes, how it works, and how to use your mailbox effectively despite this requirement.",
    "body": make_doc([
        p("Many users ask about 2FA on their Icemail mailboxes. This article explains what it is, why it’s required, and how to work with it."),
        hr(),
        h2("Two Types of 2FA in Icemail"),
        p("There are two different 2FA contexts in Icemail:"),
        ul(
            "2FA on your Icemail dashboard login — this is for your Icemail account and is managed by you",
            "2FA on provisioned mailboxes (Google/Microsoft) — this is part of mailbox setup and cannot be removed",
        ),
        p("This article is about the second type: 2FA on the actual Google or Microsoft mailboxes."),
        hr(),
        h2("Why Is 2FA Required on Mailboxes?"),
        p("Google and Microsoft require 2FA (two-factor authentication) on accounts that use API-based connections and app passwords. Without 2FA:"),
        ul(
            "App passwords cannot be generated",
            "SMTP/IMAP connections will not function reliably",
            "Icemail’s mailbox sync and configuration will break",
        ),
        p("2FA is automatically enabled as part of Icemail’s mailbox setup process. It is not optional."),
        hr(),
        h2("Why Can’t Icemail Remove 2FA?"),
        p("Icemail does not manually control the 2FA setting — it is enforced by Google and Microsoft as a requirement for the API access that powers mailbox management. Disabling it would break the entire mailbox configuration."),
        hr(),
        h2("How to Use Your Mailbox With 2FA Enabled"),
        p("You don’t need to interact with 2FA when using your mailbox for email sending. Simply:"),
        ul(
            "Use the app password (found in your Icemail dashboard or CSV export) for SMTP/IMAP connections",
            "Do NOT use your regular Google account password",
            "Do NOT change your Google account password manually",
        ),
        hr(),
        h2("Managing Your Icemail Dashboard 2FA"),
        p("Your Icemail account login 2FA is separate and managed in your account settings. Each user controls their own Icemail 2FA. Support cannot disable it on your behalf."),
    ]),
})

# --- Article 9 ---------------------------------------------------------------
articles.append({
    "title": "Connecting Domains via Cloudflare Without Changing Nameservers",
    "collection_slug": "domain-management",
    "mdx_path": "gleap/domain-management/connecting-domains-via-cloudflare-without-changing-ns.mdx",
    "description": "How to connect an existing Cloudflare domain to Icemail using the Cloudflare API method, without changing your nameservers.",
    "body": make_doc([
        p("If your domain is already on Cloudflare, you have two options for connecting it to Icemail. This guide explains both options and walks you through the recommended approach."),
        hr(),
        h2("Option A: Cloudflare API Connection (Recommended)"),
        p("This method lets you connect your domain to Icemail without changing nameservers. Icemail uses the Cloudflare API to add DNS records automatically."),
        h3("Steps"),
        ul(
            "Go to Domains in your Icemail dashboard",
            "Click Add Domain",
            "Select Connect Existing Domain",
            "Choose Connect via Cloudflare",
            "Authorize Icemail to access your Cloudflare account",
            "DNS records are added automatically — no further action needed",
        ),
        h3("Benefits"),
        ul(
            "No nameserver changes required",
            "Your existing Cloudflare settings (page rules, WAF, etc.) are preserved",
            "DNS records are added instantly via API",
            "Easiest method if your domain is already on Cloudflare",
        ),
        hr(),
        h2("Option B: Change Nameservers"),
        p("The standard method involves pointing your domain’s nameservers to Icemail/Cloudflare nameservers. This works for any domain registrar but requires changing nameservers, which may affect other DNS configurations."),
        hr(),
        h2("DNS Records That Will Be Added"),
        p("When you connect via Cloudflare, Icemail automatically adds all required DNS records:"),
        ul(
            "SPF record — authorizes sending from Icemail mail servers",
            "DKIM record — signs outgoing emails to verify authenticity",
            "DMARC record — sets policy for email authentication failures",
            "MX records — routes inbound email correctly",
        ),
        p("All records are configured for optimal email deliverability."),
        hr(),
        h2("Need Help Connecting?"),
        p("If you run into any issues during the Cloudflare connection process, contact team@icemail.ai with your domain name."),
    ]),
})

# --- Article 10 --------------------------------------------------------------
articles.append({
    "title": "Mailbox Reactivation Policy – What Happens After Deletion",
    "collection_slug": "billing-subscription",
    "mdx_path": "gleap/billing-subscription/mailbox-reactivation-policy.mdx",
    "description": "Understand the 7-day soft deletion window, how to reactivate mailboxes, and what gets permanently deleted after the window closes.",
    "body": make_doc([
        p("When you delete a mailbox or domain in Icemail, it goes through a soft deletion period before being permanently removed. Here’s what you need to know."),
        hr(),
        h2("Soft Deletion vs Permanent Deletion"),
        p("When you delete a mailbox from the Icemail dashboard, it is not immediately removed from Google or Microsoft systems. Instead, it enters a 7-day soft deletion window."),
        ul(
            "Soft deleted: mailbox is deactivated but data can still be recovered",
            "Permanently deleted: mailbox is fully removed from Google/Microsoft and cannot be recovered",
        ),
        hr(),
        h2("Reactivating Within 7 Days"),
        p("If you change your mind within 7 days of deletion:"),
        ul(
            "Contact team@icemail.ai with the domain name and mailbox email addresses",
            "Standard pricing applies: $2.50/mailbox/month",
            "Reactivation is typically completed within a few hours",
        ),
        hr(),
        h2("After 7 Days: Permanent Deletion"),
        p("After the 7-day window closes, mailboxes are permanently and irrecoverably deleted. This includes:"),
        ul(
            "The Google or Microsoft Workspace licenses",
            "All emails stored in those mailboxes",
            "The mailbox history and configuration",
            "App passwords associated with those mailboxes",
        ),
        p("There is no way to recover mailboxes or their data after permanent deletion."),
        hr(),
        h2("Domain Reactivation"),
        p("The same 7-day policy applies to domains. If you delete a domain and want to reconnect it within 7 days, contact team@icemail.ai. After 7 days, the domain configuration is permanently removed."),
        hr(),
        h2("Best Practice"),
        p("Before deleting mailboxes or domains, export any important data from your outreach tools and make sure you truly want to proceed. If in doubt, contact team@icemail.ai before deleting."),
    ]),
})

# --- Article 11 --------------------------------------------------------------
articles.append({
    "title": "Maximum Mailboxes Per Domain – Limits & Best Practices",
    "collection_slug": "mailbox-management",
    "mdx_path": "gleap/mailbox-management/maximum-mailboxes-per-domain-limits-best-practices.mdx",
    "description": "Learn the mailbox limits per domain for Google, Microsoft, Azure, and SMTP, and best practices for cold email deliverability.",
    "body": make_doc([
        p("How many mailboxes can you have on a single domain? The answer depends on your mailbox type and your deliverability goals."),
        hr(),
        h2("Technical Limits by Mailbox Type"),
        ul(
            "Google Workspace: up to 20 mailboxes per domain (technical maximum)",
            "Microsoft 365: similar limits apply",
            "Azure mailboxes: up to 100 mailboxes per domain",
            "SMTP mailboxes: up to 10 mailboxes per domain",
        ),
        hr(),
        h2("Recommended Limits for Cold Email"),
        p("For cold email deliverability, Icemail strongly recommends:"),
        ul(
            "2–3 mailboxes per domain maximum",
            "Do NOT put all your mailboxes on one domain",
            "Use more domains with fewer mailboxes per domain rather than cramming many mailboxes onto one domain",
        ),
        p("Keeping mailbox density low per domain protects your domain reputation. If one mailbox gets flagged, it’s isolated rather than affecting your entire sending infrastructure."),
        hr(),
        h2("What Happens If You Exceed Limits"),
        p("If you try to add more mailboxes than a domain supports:"),
        ul(
            "New mailboxes will fail to provision",
            "Failed mailboxes will show a \"failed\" status in your dashboard",
            "You will need to use a different domain for additional mailboxes",
        ),
        hr(),
        h2("Best Practice: Scale With More Domains"),
        p("The most reliable way to scale your cold email infrastructure is to add more domains rather than adding more mailboxes per domain. For example:"),
        ul(
            "Instead of 10 mailboxes on 1 domain → use 5 domains with 2 mailboxes each",
            "This distributes sending volume and protects your reputation",
            "It also gives you redundancy if one domain experiences deliverability issues",
        ),
        hr(),
        h2("Questions About Domain Strategy?"),
        p("Contact team@icemail.ai for guidance on structuring your domain and mailbox setup for maximum deliverability."),
    ]),
})

# --- Article 12 --------------------------------------------------------------
articles.append({
    "title": "Pre-Warmed Mailboxes – Sending Ramp-Up Schedule & Best Practices",
    "collection_slug": "mailbox-management",
    "mdx_path": "gleap/mailbox-management/pre-warmed-mailboxes-sending-ramp-up-schedule.mdx",
    "description": "How pre-warmed mailboxes work, the recommended sending ramp-up schedule, and best practices for getting the best deliverability.",
    "body": make_doc([
        p("Pre-warmed mailboxes are ready to use faster than standard new mailboxes, but they still require a proper ramp-up to maintain deliverability."),
        hr(),
        h2("What Does Pre-Warmed Mean?"),
        p("Pre-warmed mailboxes have already completed an initial warmup period before you receive them. This means they have established a sending reputation and are ready to start sending cold emails sooner."),
        p("Pre-warmed Google mailboxes are available at $5/mailbox/month."),
        hr(),
        h2("Recommended Sending Ramp-Up Schedule"),
        p("Even though mailboxes are pre-warmed, you should still ramp up your sending volume gradually:"),
        ul(
            "Week 1: 30–50 cold emails per mailbox per day",
            "Weeks 2–3: Increase to 50–70 emails per day",
            "Week 4 and beyond: Up to 100 emails per day if domain reputation remains strong",
        ),
        p("Jumping to maximum volume immediately — even with pre-warmed mailboxes — risks triggering spam filters."),
        hr(),
        h2("Keep Warmup Running During Campaigns"),
        p("Even after you start sending cold outreach campaigns, keep your warmup tool running at a low volume (10–20 emails per day per mailbox). This ongoing warmup activity helps maintain your sender reputation."),
        hr(),
        h2("Exporting Pre-Warmed Mailboxes"),
        p("Export pre-warmed mailboxes to your outreach tool the same way as standard mailboxes — using the direct integration method in the Icemail dashboard (Mailboxes → Export Mailboxes → choose platform)."),
        hr(),
        h2("Domain Forwarding on Pre-Warmed Domains"),
        p("You can set up domain forwarding on pre-warmed domains just like any other Icemail domain. Go to Domains → click your domain → set up forwarding."),
        hr(),
        h2("Adding Profile Pictures"),
        p("Icemail can add profile pictures to your pre-warmed mailboxes, which improves deliverability and response rates. Contact team@icemail.ai to request profile picture setup."),
        hr(),
        h2("Questions About Pre-Warmed Mailboxes?"),
        p("Contact team@icemail.ai for pricing, availability, and setup assistance."),
    ]),
})

# --- Article 13 --------------------------------------------------------------
articles.append({
    "title": "DKIM Setup for Microsoft 365 Mailboxes – Why It Takes Longer",
    "collection_slug": "mailbox-management",
    "mdx_path": "gleap/mailbox-management/dkim-setup-for-microsoft-365-mailboxes.mdx",
    "description": "Why DKIM setup takes longer for Microsoft 365 mailboxes, how to check your DKIM status, and what to do if it's missing.",
    "body": make_doc([
        p("DKIM is a critical email authentication record that prevents your emails from going to spam. Here’s what to know about DKIM setup timing for Microsoft 365 mailboxes."),
        hr(),
        h2("DKIM for Google Mailboxes"),
        p("For Google Workspace mailboxes, DKIM is automatically configured within a few hours of mailbox activation. No manual steps are required."),
        hr(),
        h2("DKIM for Microsoft 365 Mailboxes"),
        p("Microsoft 365 DKIM setup takes longer due to Microsoft’s API processing times. The DKIM record may not appear immediately after mailbox activation — this is expected."),
        ul(
            "Typical timing: several hours to 24 hours after mailbox activation",
            "During busy periods, it can occasionally take longer",
        ),
        hr(),
        h2("How to Check Your DKIM Status"),
        ul(
            "Go to Domains in your Icemail dashboard",
            "Click on your domain",
            "Select the DNS Records tab",
            "Verify that a DKIM record (starting with selector1._domainkey or similar) is present",
        ),
        hr(),
        h2("What to Do If DKIM Is Missing After 24 Hours"),
        p("If your DKIM record has not appeared after 24 hours:"),
        ul(
            "Contact team@icemail.ai with your domain name",
            "The Icemail team can manually add or trigger the DKIM record from the backend",
        ),
        p("Do not start cold email campaigns without a DKIM record — it will significantly hurt deliverability."),
        hr(),
        h2("Why DKIM Matters"),
        ul(
            "DKIM digitally signs each outgoing email, proving it came from your domain",
            "Without DKIM, emails are more likely to land in spam",
            "DKIM is essential for deliverability alongside SPF and DMARC",
        ),
        hr(),
        h2("Need Help?"),
        p("Contact team@icemail.ai if your DKIM record is missing or you need assistance verifying your DNS setup."),
    ]),
})

# --- Article 14 --------------------------------------------------------------
articles.append({
    "title": "DNS Records FAQ – Timing, Propagation & Common Issues",
    "collection_slug": "domain-management",
    "mdx_path": "gleap/domain-management/dns-records-faq-timing-propagation-common-issues.mdx",
    "description": "Common questions about DNS records in Icemail: when they're added, propagation timing, and how to fix common issues.",
    "body": make_doc([
        p("DNS records are automatically managed by Icemail for all connected domains. Here are answers to the most common questions."),
        hr(),
        h2("When Are DNS Records Added?"),
        p("DNS records are added automatically after you assign mailboxes to a domain. Expected timing:"),
        ul(
            "SPF, DKIM, and DMARC records: added within minutes of mailbox assignment",
            "Full global propagation: up to 24 hours (this is a DNS system limitation, not an Icemail limitation)",
            "Cloudflare-connected domains: records added instantly via API",
        ),
        hr(),
        h2("How to Check Your DNS Records"),
        ul(
            "Go to Domains in your Icemail dashboard",
            "Click on your domain",
            "Select the DNS Records tab to see all records and their status",
        ),
        p("You can also verify global propagation using dnschecker.org — enter your domain and check SPF, DKIM, and DMARC records."),
        hr(),
        h2("Common Issue #1: \"Add New Record\" Button Unresponsive"),
        p("If the button to add a DNS record isn’t responding:"),
        ul(
            "Try refreshing the page",
            "Clear your browser cache and try again",
            "If the issue persists after refreshing, contact team@icemail.ai",
        ),
        hr(),
        h2("Common Issue #2: SPF Record Not Showing"),
        p("The SPF record is added after mailbox assignment is complete. If it’s not showing:"),
        ul(
            "Wait for your mailboxes to finish provisioning",
            "Refresh the DNS Records tab",
            "If mailboxes are active but SPF is still missing after 1 hour, contact team@icemail.ai",
        ),
        hr(),
        h2("Common Issue #3: DMARC Not Set Up"),
        p("DMARC is automatically added for all domains. If it’s missing after 24 hours, contact team@icemail.ai so the team can add it from the backend."),
        hr(),
        h2("Common Issue #4: DNS Propagation Delays"),
        p("DNS changes can take up to 24 hours to propagate globally. If your records are visible in the Icemail dashboard but tools or email testers aren’t seeing them yet:"),
        ul(
            "Use dnschecker.org to check propagation status by region",
            "Wait 24 hours before concluding there’s a problem",
            "If still not propagated after 24 hours, contact team@icemail.ai",
        ),
        hr(),
        h2("Need Help?"),
        p("For any DNS issues, contact team@icemail.ai with your domain name and description of the issue."),
    ]),
})

# --- Article 15 --------------------------------------------------------------
articles.append({
    "title": "Understanding Mailbox Sending Limits & What Happens When You Hit Them",
    "collection_slug": "mailbox-management",
    "mdx_path": "gleap/mailbox-management/understanding-mailbox-sending-limits.mdx",
    "description": "Sending limits for Google, Microsoft, Azure, and SMTP mailboxes, what happens if you exceed them, and how to scale safely.",
    "body": make_doc([
        p("Each mailbox type in Icemail has specific sending limits. Understanding these limits helps you build a scalable, deliverable cold email infrastructure."),
        hr(),
        h2("Sending Limits by Mailbox Type"),
        h3("Google & Microsoft Mailboxes"),
        ul(
            "Cold emails: 15 per mailbox per day",
            "Warmup emails: 15 per mailbox per day (1:1 ratio with cold emails)",
            "Total maximum: 30 emails per mailbox per day",
        ),
        h3("SMTP Mailboxes"),
        ul(
            "50 emails per mailbox per day",
        ),
        h3("Azure Mailboxes"),
        ul(
            "10 emails per mailbox per day total",
            "Recommended split: 5 cold emails + 5 warmup emails",
        ),
        hr(),
        h2("What Happens When You Hit Sending Limits"),
        p("Exceeding sending limits can have serious consequences:"),
        ul(
            "Google or Microsoft may flag your account for unusual sending behavior",
            "Bounce rates increase as sending volume outpaces your reputation",
            "Spam complaint rates rise, hurting future deliverability",
            "In severe cases, the mailbox may be suspended",
        ),
        hr(),
        h2("Recovering From Limit Violations"),
        p("If you’ve sent too many emails from a mailbox:"),
        ul(
            "Reduce volume immediately — stop all cold email sending",
            "Pause cold outreach for at least 48 hours",
            "Continue warmup emails only during the recovery period",
            "Gradually resume cold sending at a lower volume",
        ),
        hr(),
        h2("How to Scale Without Hitting Limits"),
        p("The correct way to scale cold email volume is with more domains and mailboxes, not by pushing individual mailbox limits:"),
        ul(
            "Use 2–3 mailboxes per domain",
            "Add more domains to increase total sending capacity",
            "Example: 100 emails/day = 4 mailboxes x 25 emails each (well within limits)",
        ),
        hr(),
        h2("Handling Failed Emails"),
        p("If emails fail or bounce:"),
        ul(
            "Check your outreach tool’s failed/bounced log to identify affected emails",
            "Do not immediately retry failed emails — this can worsen your reputation",
            "Wait at least 24 hours before retrying, and only retry if the failure was a temporary issue",
        ),
        hr(),
        h2("Questions About Sending Strategy?"),
        p("Contact team@icemail.ai for guidance on structuring your sending infrastructure for scale."),
    ]),
})


# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    print(f"Creating {len(articles)} articles...\n")
    results = []

    for i, art in enumerate(articles, 1):
        print(f"[{i}/{len(articles)}]", end=" ")
        gleap_id = create_article(
            title=art["title"],
            collection_slug=art["collection_slug"],
            mdx_path=art["mdx_path"],
            description=art["description"],
            body_doc=art["body"],
        )
        results.append({"title": art["title"], "gleap_id": gleap_id, "success": gleap_id is not None})

    print("\n\n=== SUMMARY ===")
    for r in results:
        status = "OK" if r["success"] else "FAILED"
        print(f"  [{status}] {r['title']} --> {r.get('gleap_id', 'N/A')}")

    successes = sum(1 for r in results if r["success"])
    print(f"\n{successes}/{len(articles)} articles created successfully.")
