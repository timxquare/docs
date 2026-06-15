#!/usr/bin/env python3
"""
Creates new Gleap help center collections and articles for Icemail.
"""

import json
import uuid
import urllib.request
import urllib.error
import os
import re

# ── API config ────────────────────────────────────────────────────────────────
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjZhMmY4YjQ3ODYyODU5OWNlNWRjODE0OSIsInByb2plY3RJZCI6IjY4MzVjYzRkYTVkM2E0YjhlNGM4ZTI3NCIsInNlY3JldEFwaUtleSI6IjBoc1RKTmZDeUE0UTBLTEtad3FnZjAydzNIRThqUFVmIiwidXNlclR5cGUiOiJzZXJ2aWNlX2FjY291bnQiLCJpYXQiOjE3ODE1MDA3NDN9.lyJC8-8g8t106JRjPUU3dDB9t222k9C7HgW0xYoxL80"
PROJECT_ID = "6835cc4da5d3a4b8e4c8e274"
BASE_URL = "https://api.gleap.io"
GLEAP_DIR = "/home/user/docs/gleap"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "project": PROJECT_ID,
    "Content-Type": "application/json",
}

# ── TipTap helpers ─────────────────────────────────────────────────────────────

def uid():
    return str(uuid.uuid4())


def para(text_runs, align="left"):
    """text_runs: list of (text, marks_list) where marks_list may be empty or contain 'bold','italic','code'"""
    content = []
    for item in text_runs:
        if isinstance(item, str):
            if item:
                content.append({"type": "text", "text": item})
        else:
            text, marks = item
            node = {"type": "text", "text": text}
            if marks:
                node["marks"] = [{"type": m} for m in marks]
            content.append(node)
    return {
        "type": "paragraph",
        "attrs": {"id": uid(), "class": None, "textAlign": align},
        "content": content if content else [{"type": "text", "text": ""}],
    }


def heading(text, level=2):
    return {
        "type": "heading",
        "attrs": {"id": uid(), "textAlign": "left", "level": level},
        "content": [{"type": "text", "text": text}],
    }


def bullet_list(items):
    """items: list of (text_runs) or list of strings"""
    list_items = []
    for item in items:
        if isinstance(item, str):
            p = para([item])
        else:
            p = para(item)
        list_items.append({"type": "listItem", "content": [p]})
    return {"type": "bulletList", "content": list_items}


def hr():
    return {"type": "horizontalRule"}


def table(headers, rows):
    """Build a TipTap table node."""
    def cell(text, is_header=False):
        cell_type = "tableHeader" if is_header else "tableCell"
        return {
            "type": cell_type,
            "attrs": {"colspan": 1, "rowspan": 1, "colwidth": None},
            "content": [para([text])],
        }

    header_row = {
        "type": "tableRow",
        "content": [cell(h, is_header=True) for h in headers],
    }
    body_rows = []
    for row in rows:
        body_rows.append({
            "type": "tableRow",
            "content": [cell(c) for c in row],
        })
    return {
        "type": "table",
        "content": [header_row] + body_rows,
    }


def doc(*nodes):
    return {"type": "doc", "content": list(nodes)}


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
    return " ".join(p for p in parts if p.strip())


# ── API helpers ────────────────────────────────────────────────────────────────

def api_get(path):
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, headers=HEADERS, method="GET")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def api_post(path, body):
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        print(f"  HTTP {e.code} error: {err_body[:400]}")
        raise


# ── Slug helper ────────────────────────────────────────────────────────────────

def slugify(title):
    s = title.lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


# ── MDX save helper ────────────────────────────────────────────────────────────

def save_mdx(collection_slug, article_id, title, description, content_doc, collection_id, is_draft=False):
    col_dir = os.path.join(GLEAP_DIR, collection_slug)
    os.makedirs(col_dir, exist_ok=True)
    slug = slugify(title) + ".mdx"
    filepath = os.path.join(col_dir, slug)

    # Convert doc to simple markdown-ish plain content for MDX body
    md_lines = []
    for node in content_doc.get("content", []):
        ntype = node.get("type")
        if ntype == "heading":
            level = node["attrs"].get("level", 2)
            text = "".join(c.get("text", "") for c in node.get("content", []))
            md_lines.append("#" * level + " " + text)
            md_lines.append("")
        elif ntype == "paragraph":
            parts = []
            for c in node.get("content", []):
                t = c.get("text", "")
                marks = [m["type"] for m in c.get("marks", [])]
                if "bold" in marks:
                    t = f"**{t}**"
                if "italic" in marks:
                    t = f"*{t}*"
                if "code" in marks:
                    t = f"`{t}`"
                parts.append(t)
            md_lines.append("".join(parts))
            md_lines.append("")
        elif ntype == "bulletList":
            for li in node.get("content", []):
                for p in li.get("content", []):
                    text_parts = []
                    for c in p.get("content", []):
                        t = c.get("text", "")
                        marks = [m["type"] for m in c.get("marks", [])]
                        if "bold" in marks:
                            t = f"**{t}**"
                        text_parts.append(t)
                    md_lines.append("- " + "".join(text_parts))
            md_lines.append("")
        elif ntype == "horizontalRule":
            md_lines.append("---")
            md_lines.append("")
        elif ntype == "table":
            rows = node.get("content", [])
            if rows:
                header_cells = [
                    "".join(c.get("text", "") for c2 in cell.get("content", [{"content": []}]) for c in c2.get("content", []))
                    for cell in rows[0].get("content", [])
                ]
                md_lines.append("| " + " | ".join(header_cells) + " |")
                md_lines.append("| " + " | ".join(["---"] * len(header_cells)) + " |")
                for row in rows[1:]:
                    cells = []
                    for cell in row.get("content", []):
                        cell_text = ""
                        for p2 in cell.get("content", []):
                            for c in p2.get("content", []):
                                cell_text += c.get("text", "")
                        cells.append(cell_text)
                    md_lines.append("| " + " | ".join(cells) + " |")
                md_lines.append("")

    frontmatter = f"""---
title: "{title}"
description: "{description}"
gleap_id: "{article_id}"
gleap_collection: "{collection_id}"
gleap_collection_slug: "{collection_slug}"
isDraft: {str(is_draft).lower()}
---

"""
    body = "\n".join(md_lines)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(frontmatter + body)
    return filepath


# ── Article content definitions ────────────────────────────────────────────────

def build_article_A():
    title = "🔍 Troubleshooting DNS Issues for Connected Domains in Icemail"
    description = "Step-by-step guide for resolving Inactive domain status, NS not pointing to Icemail, DNS propagation delays, and missing SPF/DKIM/DMARC/MX records."
    content = doc(
        para(["When a connected domain shows as "]),
        para([("Inactive", ["bold"]), " in your Icemail dashboard, it usually means one of the following:"]),
        bullet_list([
            "NS (Nameserver) records are not pointing to Icemail",
            "DNS has not yet propagated",
            "SPF, DKIM, DMARC, or MX records are missing",
        ]),
        hr(),
        heading("Step 1: Check Domain Status in Icemail Dashboard", 3),
        para(["Log in to your Icemail dashboard and navigate to the ", ("Domains", ["bold"]), " section."]),
        para(["Look for status labels such as:"]),
        bullet_list([
            [("Inactive", ["bold"]), " — domain not verified yet"],
            [("DNS not propagating", ["bold"]), " — nameservers updated but not resolved globally"],
        ]),
        hr(),
        heading("Step 2: Verify Nameservers Match Exactly", 3),
        para(["Click your domain, then click ", ("Add Nameservers", ["bold"]), " to see the required nameserver values Icemail provides."]),
        para(["Then update those nameservers at your domain registrar:"]),
        bullet_list([
            [("GoDaddy", ["bold"]), ": My Products → Domains → DNS → Nameservers → Change → Enter Custom Nameservers"],
            [("Namecheap", ["bold"]), ": Domain List → Manage → Nameservers → Custom DNS → paste values"],
            [("Cloudflare", ["bold"]), ": Select domain → Overview → scroll to Nameservers section → update to custom"],
        ]),
        para([("Important:", ["bold"]), " The nameservers must match exactly what Icemail displays — copy-paste to avoid typos."]),
        hr(),
        heading("Step 3: Wait for DNS Propagation", 3),
        para(["DNS propagation can take ", ("up to 24–48 hours", ["bold"]), " depending on your registrar and global DNS caches."]),
        para(["To verify propagation status, visit ", ("Whois.com", ["bold"]), " and look up your domain's current nameserver records."]),
        hr(),
        heading("Step 4: Click Verify in Icemail", 3),
        para(["Once propagation is confirmed, return to your Icemail dashboard and click ", ("Verify", ["bold"]), " next to the domain."]),
        hr(),
        heading("✅ Once Verified", 3),
        para(["After successful verification:"]),
        bullet_list([
            "Domain status changes to Active",
            "SPF, DKIM, DMARC, and MX records are all configured automatically",
            "Domain is ready to use for cold outreach campaigns",
        ]),
        hr(),
        para([("Need help?", ["bold"]), " Contact our support team at ", ("team@icemail.ai", ["bold"]), "."]),
    )
    return title, description, content


def build_article_B():
    title = "⚠️ Fixing the 'Workspace Already Exists' Error in Icemail"
    description = "How to resolve the 'Workspace already exists' error when connecting a Google or Microsoft domain to Icemail."
    content = doc(
        para(["When connecting a domain to Icemail, you may encounter a ", ("\"Workspace already exists\"", ["bold"]), " error."]),
        para(["This happens because both Google Workspace and Microsoft 365 allow only ", ("one active workspace per domain", ["bold"]), ". If a workspace was previously created or is still active for that domain, the connection will fail."]),
        hr(),
        heading("Google Workspace Solutions", 3),
        heading("Case 1 – You Previously Created a Google Workspace", 4),
        para(["If you set up a Google Workspace on this domain before:"]),
        bullet_list([
            "Go to Google Admin Console",
            [("Billing", ["bold"]), " → ", ("Subscriptions", ["bold"]), " → find your subscription → ", ("Cancel Subscription", ["bold"])],
            "After canceling, proceed to delete the workspace entirely",
            "Wait 24 hours before reconnecting the domain in Icemail",
        ]),
        para([("Important:", ["bold"]), " Canceling the subscription alone is not enough — the workspace must be fully deleted."]),
        heading("Case 2 – The Domain Was Owned by a Previous Google Account", 4),
        para(["If the domain was previously associated with another Google account:"]),
        bullet_list([
            ["Use the ", ("Google Domain In-Use Recovery Tool", ["bold"]), " to reclaim ownership"],
            "Follow Google's verification steps",
            "Wait several hours after recovery before reconnecting to Icemail",
        ]),
        hr(),
        heading("Microsoft 365 Solution", 3),
        para(["If you previously connected this domain to Microsoft 365:"]),
        bullet_list([
            ["Go to ", ("Microsoft Admin Center", ["bold"])],
            [("Settings", ["bold"]), " → ", ("Domains", ["bold"])],
            ["Select the domain → click ", ("Remove domain", ["bold"])],
            ["Click ", ("Update", ["bold"]), " → ", ("Continue", ["bold"]), " to confirm removal"],
            "Wait before reconnecting the domain in Icemail",
        ]),
        hr(),
        heading("Key Notes", 3),
        bullet_list([
            "Subscription cancellation alone is not sufficient — full deletion is required",
            "Icemail cannot override platform-level restrictions imposed by Google or Microsoft",
            "If the domain had a previous owner, use the appropriate recovery tool before reconnecting",
        ]),
        hr(),
        para([("Need help?", ["bold"]), " Contact our support team at ", ("team@icemail.ai", ["bold"]), "."]),
    )
    return title, description, content


def build_article_C():
    title = "🔄 How to Renew a Domain in Icemail"
    description = "Step-by-step guide to renewing domains purchased through Icemail to ensure uninterrupted cold email outreach."
    content = doc(
        para(["Renewing your domain ensures ", ("uninterrupted cold email outreach", ["bold"]), " and prevents your domain from expiring and becoming unusable."]),
        hr(),
        heading("When Can You Renew?", 3),
        bullet_list([
            [("14 days before expiry", ["bold"]), ": renewal becomes available in your dashboard"],
            [("15-day grace period", ["bold"]), ": after expiry, you can still renew during this window"],
            [("After grace period", ["bold"]), ": expired domains are marked unusable and cannot be renewed"],
            "Only domains purchased through Icemail and within 2 months of expiry are eligible for renewal",
        ]),
        hr(),
        heading("Step 1: Access the Renewals Section", 3),
        para(["Log in to Icemail → go to ", ("Domains", ["bold"]), " → click ", ("Renewals", ["bold"]), " from the sidebar or tab."]),
        para(["Select the domain(s) you want to renew, then click ", ("Renew Domain", ["bold"]), "."]),
        hr(),
        heading("Step 2: Review Renewal Details", 3),
        bullet_list([
            [("Renewal period", ["bold"]), ": fixed at 1 year per renewal"],
            "Review the total cost shown on screen",
            [("Click ", ["bold"]), ("Proceed to Payment", ["bold"]), " when ready"],
        ]),
        hr(),
        heading("Step 3: Complete Payment", 3),
        para(["Choose your payment method:"]),
        bullet_list([
            [("Wallet", ["bold"]), ": use your Icemail wallet balance"],
            [("Stripe", ["bold"]), ": pay securely by card"],
        ]),
        para(["Confirm the payment to complete renewal."]),
        hr(),
        heading("How Renewal Dates Work", 3),
        para(["Renewal time is ", ("added to your existing expiry date", ["bold"]), ", not the date of renewal."]),
        para(["Example: if your domain expires ", ("June 1, 2025", ["bold"]), " and you renew it, the new expiry date will be ", ("June 1, 2026", ["bold"]), "."]),
        hr(),
        para([("Need help?", ["bold"]), " Contact our support team at ", ("team@icemail.ai", ["bold"]), "."]),
    )
    return title, description, content


def build_article_D():
    title = "📋 How to Use Bulk Domain Finder in Icemail"
    description = "Upload a CSV to check availability and purchase up to 100 domains at once using Icemail's Bulk Domain Finder."
    content = doc(
        para(["Bulk Domain Finder lets you upload a CSV of domain names to check their availability and purchase multiple domains in a single workflow — ideal for agencies and outbound teams buying at scale."]),
        hr(),
        heading("Step 1: Open Bulk Domain Finder", 3),
        para(["Navigate to ", ("Domain(s)", ["bold"]), " → ", ("Buy New Domain(s)", ["bold"]), " → ", ("Bulk Domain Finder", ["bold"]), "."]),
        hr(),
        heading("Step 2: Upload Your CSV", 3),
        bullet_list([
            "Click the upload area to upload your prepared CSV file, or",
            [("Download the sample sheet", ["bold"]), " to see the correct format before uploading your own"],
        ]),
        para(["The CSV should contain one domain name per row in the correct column format."]),
        hr(),
        heading("Step 3: Scan Availability", 3),
        para(["Click ", ("Upload All", ["bold"]), " to start scanning. Icemail will check each domain's availability status automatically."]),
        hr(),
        heading("Step 4: Review Your Cart", 3),
        para(["Only ", ("available domains", ["bold"]), " are added to your cart automatically. Unavailable domains are excluded."]),
        para(["Review the cart before proceeding."]),
        hr(),
        heading("Step 5: Complete Payment", 3),
        para(["Choose your payment method:"]),
        bullet_list([
            [("Wallet", ["bold"]), ": use your Icemail wallet balance"],
            [("Stripe", ["bold"]), ": pay securely by card"],
        ]),
        para(["Confirm to complete the purchase."]),
        hr(),
        heading("Constraints & Notes", 3),
        bullet_list([
            [("Maximum 100 domains per CSV", ["bold"]), " upload"],
            "Only available domains are added to the cart — unavailable ones are excluded automatically",
            "Incorrectly formatted CSV files will be rejected — use the sample sheet as a reference",
        ]),
        hr(),
        para([("Best for:", ["bold"]), " Agencies and outbound teams purchasing domains at scale."]),
        hr(),
        para([("Need help?", ["bold"]), " Contact our support team at ", ("team@icemail.ai", ["bold"]), "."]),
    )
    return title, description, content


def build_article_E():
    title = "🤖 How to Use AI Domain Finder in Icemail"
    description = "Use Icemail's AI Domain Finder to discover available, brand-aligned domains for cold outreach based on keywords or an existing domain."
    content = doc(
        para(["AI Domain Finder uses artificial intelligence to discover available domains suited for cold outreach, based on keywords or an existing primary domain. It saves research time and surfaces brand-aligned options faster."]),
        hr(),
        heading("Access AI Domain Finder", 3),
        para(["Navigate to ", ("Domain(s)", ["bold"]), " → ", ("Buy New Domain(s)", ["bold"]), " → ", ("AI Domain Finder", ["bold"]), "."]),
        hr(),
        heading("Step 1: Choose Your Input Method", 3),
        bullet_list([
            [("By Keywords", ["bold"]), ": enter brand or product-related terms (e.g. your company name, niche, or campaign focus)"],
            [("By Primary Domain", ["bold"]), ": enter an existing domain you own + a short brand description for context"],
        ]),
        hr(),
        heading("Step 2: Configure Preferences", 3),
        bullet_list([
            [("TLD preference", ["bold"]), ": choose from .com, .net, .io, and other available extensions"],
            [("Number of suggestions", ["bold"]), ": specify how many domain ideas to generate"],
            [("Quantity to purchase", ["bold"]), ": select how many domains you intend to buy"],
        ]),
        hr(),
        heading("Step 3: Generate Domains", 3),
        para(["Click ", ("Generate", ["bold"]), " and wait ", ("1–2 minutes", ["bold"]), " for the AI to surface available domain suggestions."]),
        hr(),
        heading("Step 4: Review and Add to Cart", 3),
        para(["Browse the generated domains, select the ones that fit your brand, and add them to your cart."]),
        hr(),
        heading("Step 5: Proceed to Payment", 3),
        para(["Click ", ("Proceed to Payment", ["bold"]), " and choose:"]),
        bullet_list([
            [("Stripe", ["bold"]), ": secure card payment"],
            [("Wallet", ["bold"]), ": use Icemail wallet balance"],
        ]),
        para(["Confirm to complete your purchase."]),
        hr(),
        heading("Benefits", 3),
        bullet_list([
            "Saves domain research time significantly",
            "Surfaces brand-aligned options automatically",
            "Faster purchasing at scale vs. manual searching",
        ]),
        hr(),
        para([("Need help?", ["bold"]), " Contact our support team at ", ("team@icemail.ai", ["bold"]), "."]),
    )
    return title, description, content


def build_article_F():
    title = "🔀 How to Move Domains Between Workspaces or Providers in Icemail"
    description = "Move domains across workspaces and switch between Google Workspace or Microsoft 365 within Icemail."
    content = doc(
        para(["Icemail allows you to move domains across workspaces and switch their provider between Google Workspace and Microsoft 365 — all from within the dashboard."]),
        hr(),
        heading("Critical Requirement", 3),
        para([("The domain must not have any active mailboxes.", ["bold"]), " You must delete all mailboxes associated with the domain before initiating a move."]),
        hr(),
        heading("Steps to Move a Domain", 3),
        heading("Step 1: Go to Domains Tab", 4),
        para(["Log in to your Icemail dashboard and navigate to the ", ("Domains", ["bold"]), " tab."]),
        heading("Step 2: Select Domain(s)", 4),
        para(["Use the checkbox to select one or multiple domains you want to move."]),
        heading("Step 3: Select 'Move Domains'", 4),
        para(["From the action menu that appears, click ", ("Move Domains", ["bold"]), "."]),
        heading("Step 4: Choose Target Workspace and Provider", 4),
        para(["Select your:"]),
        bullet_list([
            [("Target workspace", ["bold"]), ": the workspace you want to move the domain to"],
            [("Provider", ["bold"]), ": Google Workspace or Microsoft 365"],
        ]),
        heading("Step 5: Confirm the Move", 4),
        para(["Review the move details and click ", ("Confirm", ["bold"]), " to complete the action."]),
        hr(),
        heading("Troubleshooting", 3),
        para(["If the move is blocked, it is because active mailboxes still exist on the domain."]),
        bullet_list([
            "Delete all mailboxes on the domain first",
            "Then retry the move process",
        ]),
        hr(),
        para([("Need help?", ["bold"]), " Contact our support team at ", ("team@icemail.ai", ["bold"]), "."]),
    )
    return title, description, content


def build_article_G():
    title = "🤖 Creating Mailboxes Using AI Auto-Filling in Icemail"
    description = "Use Icemail's AI Auto-Filling feature to automatically generate realistic mailbox identities for Google Workspace or Microsoft 365."
    content = doc(
        para(["AI Auto-Filling creates realistic mailbox identities automatically, saving time when setting up multiple mailboxes for cold outreach."]),
        hr(),
        heading("Access AI Auto-Filling", 3),
        para(["Navigate to ", ("Mailboxes", ["bold"]), " → ", ("Assigned", ["bold"]), " → ", ("Assign Mailboxes", ["bold"]), " → ", ("Auto-Fill Using AI", ["bold"]), " tab."]),
        para(["Select your platform first: ", ("Google Workspace", ["bold"]), " or ", ("Microsoft 365", ["bold"]), "."]),
        hr(),
        heading("Option 1 – Name-Based Generation", 3),
        bullet_list([
            "Enter the number of mailboxes to create",
            "Provide first and last names to use as a basis",
            "Select the domain(s) to assign mailboxes to",
            "Optionally enable AI profile picture generation, or upload custom pictures",
        ]),
        para(["The AI will generate email usernames, display names, and professional formatting automatically."]),
        hr(),
        heading("Option 2 – Gender & Ethnicity-Based Generation", 3),
        bullet_list([
            "Select gender preference (Male, Female, or Both)",
            "Choose ethnicity for more natural, human-like name generation",
            "Specify the quantity of mailboxes",
        ]),
        para(["The AI generates first names, last names, and email usernames based on your selections."]),
        para(["When both genders are selected, you can adjust the ", ("male-to-female ratio", ["bold"]), " to match your outreach persona mix."]),
        para(["Ideal for cold outreach agencies and growth teams managing multiple personas at scale."]),
        hr(),
        heading("After Generation", 3),
        bullet_list([
            "Review generated names and usernames",
            "Select the assignment domain",
            "Make manual edits if needed before confirming",
            [("Click ", []), ("\"Assign Mailboxes\"", ["bold"]), " to place the order"],
        ]),
        hr(),
        heading("Important Warning", 3),
        para([("Once an order is placed, it cannot be reverted or deleted.", ["bold"]), " Please review all details carefully before confirming."]),
        hr(),
        heading("Additional Notes", 3),
        bullet_list([
            "Works for both single and bulk mailbox creation",
            "Takes approximately 1–2 minutes to provision",
        ]),
        hr(),
        para([("Need help?", ["bold"]), " Contact our support team at ", ("team@icemail.ai", ["bold"]), "."]),
    )
    return title, description, content


def build_article_H():
    title = "🚀 Introducing Icemail – Cold Email Infrastructure, Simplified"
    description = "An overview of Icemail: what it is, what you can do with it, why it stands out, and who it's for."
    content = doc(
        heading("What is Icemail?", 3),
        para(["Icemail is an all-in-one cold email infrastructure platform. It provides ready-to-send Google Workspace and Microsoft 365 mailboxes — plus SMTP and Azure mailboxes — with all deliverability-critical configurations handled automatically."]),
        bullet_list([
            [("Google Workspace", ["bold"]), ": Licensed Google Business Starter, Official Google Partner"],
            [("Microsoft 365", ["bold"]), ": Business Starter accounts, fully provisioned"],
            [("SMTP Mailboxes", ["bold"]), ": dedicated IPs for full control"],
            [("Azure Mailboxes", ["bold"]), ": for high-volume sending"],
            [("US IP Mailboxes", ["bold"]), ": available at $2.50/mailbox/month for Google and Microsoft"],
        ]),
        hr(),
        heading("What You Can Do with Icemail", 3),
        bullet_list([
            "Establish mailboxes rapidly — from domain purchase to ready-to-send in minutes",
            "Auto-configure SPF, DKIM, DMARC, and MX records for every domain",
            "Connect existing domains or purchase new ones directly",
            "Add profile pictures to mailboxes for authenticity",
            "Export mailboxes to leading platforms: ReachInbox, Instantly, Smartlead, Reply.io, and more",
        ]),
        hr(),
        heading("Why Icemail?", 3),
        bullet_list([
            [("Infrastructure Built for Cold Email", ["bold"]), ": handles everything from domain provisioning to mailbox creation, with all DNS records auto-configured"],
            [("Deliverability by Design", ["bold"]), ": Google Workspace on US IPs, Microsoft 365 on Microsoft infrastructure, SMTP with dedicated IPs, Azure for high-volume sending"],
            [("Seamless Export", ["bold"]), ": one-click export to leading cold email platforms"],
            [("Scalable", ["bold"]), ": manages infrastructure for one mailbox or hundreds"],
            [("Transparent Pricing", ["bold"]), ": $2.50/mailbox/month for Google & Microsoft; Azure at $30/domain/month"],
        ]),
        hr(),
        heading("Who Icemail Is For", 3),
        bullet_list([
            "Cold email agencies managing multiple clients and domains",
            "Founders and growth teams building outbound pipelines",
            "B2B marketing professionals running prospecting campaigns",
            "Sales organizations scaling outreach operations",
        ]),
        hr(),
        heading("How Icemail Compares", 3),
        table(
            ["Feature", "Icemail", "Other Providers"],
            [
                ["Setup Time", "Minutes", "24–48 hours"],
                ["Mailbox Types", "Google, Microsoft, SMTP, Azure", "Limited"],
                ["DNS Configuration", "Fully automated", "Manual"],
                ["Sending Tool Integration", "One-click export", "Manual"],
                ["Deliverability", "High", "Medium to low"],
            ]
        ),
        hr(),
        para([("Ready to get started?", ["bold"]), " Contact our support team at ", ("team@icemail.ai", ["bold"]), " or visit ", ("icemail.ai", ["bold"]), "."]),
    )
    return title, description, content


def build_article_I():
    title = "✅ Getting Started with Your Icemail Account"
    description = "Full step-by-step onboarding guide: sign up, workspace setup, domain configuration, mailbox creation, and exporting to outreach tools."
    content = doc(
        para(["Welcome to Icemail! This guide walks you through the complete setup process — from signing up to sending your first cold email."]),
        hr(),
        heading("Step 1: Sign Up", 3),
        bullet_list([
            ["Visit ", ("icemail.ai", ["bold"]), " and click ", ("Get Started", ["bold"])],
            "Choose a plan that matches your needs and complete checkout",
            "Access your dashboard via the link sent to your email",
        ]),
        hr(),
        heading("Step 2: Complete Workspace Onboarding", 3),
        bullet_list([
            ["Name your workspace (e.g. ", ("\"Outreach Team\"", ["bold"]), " or ", ("\"Sales Mailboxes\"", ["bold"]), ")"],
            "Tell us how you found Icemail",
            "Select your role: Founder, Agency Owner, Marketer, Sales Lead, etc.",
            [("Click ", []), ("\"Continue Setup\"", ["bold"]), " to proceed"],
        ]),
        hr(),
        heading("Step 3: Set Up Domains", 3),
        para(["You have two options for adding domains:"]),
        heading("Option A – Buy New Domains", 4),
        bullet_list([
            [("Click ", []), ("Buy Domains", ["bold"]), " → ", ("Next", ["bold"])],
            "Browse available domains across TLDs (.com, .net, .org, .info, and more)",
            "Select your preferred domains and add them to cart",
            "Complete payment via Wallet or Stripe",
        ]),
        para(["Best practices:"]),
        bullet_list([
            [("2–3 mailboxes per domain", ["bold"]), " is recommended for healthy sending"],
            [(".com domains", ["bold"]), " are preferred for maximum deliverability"],
            "Purchased domains appear in your dashboard automatically",
        ]),
        heading("Option B – Connect Existing Domains", 4),
        bullet_list([
            [("Click ", []), ("Connect Domains", ["bold"]), " → ", ("Next", ["bold"])],
            ["Enter your domain name and click ", ("Connect Domain", ["bold"])],
            "Copy the Icemail nameservers shown in your dashboard",
            "Update nameservers at your registrar (Namecheap, GoDaddy, Google Domains, etc.)",
            "DNS propagation can take up to 24 hours",
            [("Click ", []), ("Recheck", ["bold"]), " after propagation to verify status"],
        ]),
        para(["Common issues:"]),
        bullet_list([
            [("Workspace Already Exists", ["bold"]), ": remove existing mailboxes from the domain or contact support"],
            [("NS Records Not Updated", ["bold"]), ": wait 24–48 hours and verify using a DNS checker tool"],
            [("Domain Already Connected", ["bold"]), ": contact support at team@icemail.ai"],
        ]),
        hr(),
        heading("Step 4: Create Mailboxes", 3),
        para(["Once your domains are active:"]),
        bullet_list([
            [("Click ", []), ("Create New Mailbox", ["bold"])],
            "Enter first name, last name, and username",
            "Select the domain to assign the mailbox to",
            [("Click ", []), ("Add New", ["bold"]), " to configure additional mailboxes in bulk"],
            [("Click ", []), ("Assign Mailboxes", ["bold"]), " to confirm"],
        ]),
        para(["The system automatically configures SPF, DKIM, DMARC, and MX records for every mailbox."]),
        hr(),
        heading("Step 5: Export Mailboxes to Outreach Tools", 3),
        bullet_list([
            "Select the mailboxes you want to export",
            [("Click ", []), ("Export Mailboxes", ["bold"])],
            "Choose your platform: ReachInbox, Instantly, Smartlead, and more",
            "Authenticate with the platform",
            "Mailboxes export automatically — no manual configuration needed",
        ]),
        hr(),
        para([("You're all set!", ["bold"]), " Your mailboxes are ready to send cold emails. For questions or assistance, contact us at ", ("team@icemail.ai", ["bold"]), "."]),
    )
    return title, description, content


def build_article_J():
    title = "🏢 Icemail Workspace Setup – Create Workspaces & Manage Team Access"
    description = "How to create workspaces, manage team members, assign roles, and control access in Icemail."
    content = doc(
        para(["A workspace is your central hub for domains, mailboxes, subscriptions, and team members. You can create multiple workspaces for different clients, teams, or projects."]),
        hr(),
        heading("Creating a Workspace", 3),
        bullet_list([
            ["Open the workspace selector dropdown and click ", ("Create Workspace", ["bold"])],
            ["Enter a workspace name (e.g. ", ("\"Outbound Team\"", ["bold"]), ", ", ("\"Client A\"", ["bold"]), ", ", ("\"Sales Ops\"", ["bold"]), ") and proceed"],
            "Select or add contact details",
            "Review and finalize",
        ]),
        para(["Each workspace has its own domains, mailboxes, users, and subscriptions — completely isolated from other workspaces."]),
        hr(),
        heading("Managing Your Workspace", 3),
        para(["Go to ", ("Settings", ["bold"]), " → ", ("Workspace", ["bold"]), " to manage your workspace settings."]),
        para(["From the three-dot menu, you can:"]),
        bullet_list([
            [("Edit Workspace", ["bold"]), ": update the workspace name or contact details"],
            [("Switch Workspace", ["bold"]), ": move between your workspaces"],
            [("Delete Workspace", ["bold"]), ": only available when all mailboxes are removed, all domains are disconnected, and the subscription is canceled"],
        ]),
        hr(),
        heading("Managing Team Members", 3),
        para([("Only Workspace Owners", ["bold"]), " can invite and manage team members."]),
        heading("Adding Team Members", 4),
        bullet_list([
            "Click the user icon with plus sign (top of the workspace panel)",
            "Select the workspace(s) to grant access to",
            "Enter the email address(es) of the users to invite",
            "Assign a role:",
        ]),
        bullet_list([
            [("Viewer", ["bold"]), ": view-only access to the workspace"],
            [("Editor", ["bold"]), ": can manage mailboxes and domains"],
            [("Admin", ["bold"]), ": full access including billing and settings"],
        ]),
        para(["You can invite multiple users and grant access to multiple workspaces in a single step."]),
        heading("After Invitation", 4),
        bullet_list([
            "New users receive an email invite and complete their account setup",
            "Existing Icemail users can log in immediately after the invite is accepted",
        ]),
        heading("Modifying or Removing Access", 4),
        para(["Go to ", ("Settings", ["bold"]), " → ", ("Workspace", ["bold"]), " → ", ("Manage Users", ["bold"]), " to update a team member's role or revoke their access. Changes take effect immediately."]),
        hr(),
        heading("Leaving a Workspace", 3),
        para(["To leave a workspace you're a member of: ", ("Settings", ["bold"]), " → ", ("Workspace", ["bold"]), " → three-dot menu → ", ("Leave Workspace", ["bold"]), " → confirm."]),
        hr(),
        para([("Need help?", ["bold"]), " Contact our support team at ", ("team@icemail.ai", ["bold"]), "."]),
    )
    return title, description, content


def build_article_K():
    title = "⚡ Why Icemail's Automatic DNS Setup Matters"
    description = "How Icemail's automatic DNS configuration works and why it's critical for email deliverability and domain health."
    content = doc(
        para(["DNS (Domain Name System) connects your domains to email services through records like SPF, DKIM, DMARC, MX, A, and CNAME. Poor DNS configuration causes spam placement, verification failures, and sending downtime."]),
        para(["Icemail automatically configures all deliverability-critical DNS records — so you never need to manage technical details manually."]),
        hr(),
        heading("Key Benefits of Automatic DNS", 3),
        bullet_list([
            [("1. Saves Time", ["bold"]), ": no manual DNS entry required — domains configure automatically when added to Icemail"],
            [("2. Reduces Errors", ["bold"]), ": automation prevents missing records or incorrect values that cause deliverability failures"],
            [("3. Easy to Manage", ["bold"]), ": all DNS managed from one dashboard without switching between registrar control panels"],
            [("4. Faster Setup", ["bold"]), ": domains are ready for mailbox creation quickly, minimizing setup delays"],
            [("5. Consistent Configuration", ["bold"]), ": every domain receives identical DNS setup — no gaps when scaling"],
            [("6. Improves Security", ["bold"]), ": proper SPF, DKIM, and DMARC authentication protects against spoofing and phishing"],
            [("7. Ongoing Monitoring", ["bold"]), ": continuous DNS health checks flag issues early, before they impact campaigns"],
            [("8. Scales With You", ["bold"]), ": handles multiple domains without extra effort as you grow"],
            [("9. Multiple Record Support", ["bold"]), ": manages all essential records (SPF, DKIM, DMARC, MX) and allows custom records (A, TXT, CNAME, MX) as needed"],
        ]),
        hr(),
        heading("The Result", 3),
        para(["Automatic DNS setup removes technical complexity, reduces risk, and keeps your domains email-ready and secure — so you can focus on outreach with confidence and strong inbox placement."]),
        hr(),
        para([("Need help?", ["bold"]), " Contact our support team at ", ("team@icemail.ai", ["bold"]), "."]),
    )
    return title, description, content


def build_article_L():
    title = "📧 Cold Emailing Best Practices: A Comprehensive Guide (2025 Edition)"
    description = "A complete guide to cold email success in 2025 — covering technical infrastructure, list building, copywriting, legal compliance, and execution frameworks."
    content = doc(
        para(["Cold emailing remains one of the most effective outreach strategies in 2025 — when executed properly. Success depends on three pillars: technical infrastructure, list quality, and compelling messaging."]),
        hr(),
        heading("What Is Cold Email?", 3),
        para(["Cold emailing is the practice of sending personalized business messages to prospects you haven't previously contacted. The goal is to initiate a dialogue — not make an immediate sale."]),
        para(["Common uses:"]),
        bullet_list([
            "Sales outreach and lead generation",
            "Partnership and collaboration development",
            "Recruitment and talent sourcing",
            "Market research and feedback gathering",
        ]),
        hr(),
        heading("Cold Email vs. Email Marketing", 3),
        table(
            ["Aspect", "Cold Email", "Email Marketing"],
            [
                ["Audience", "New prospects", "Opted-in subscribers"],
                ["Tone", "Direct and personal", "Branded and promotional"],
                ["Format", "Plain text", "Rich HTML formatting"],
                ["Goal", "Start a conversation", "Drive conversions or engagement"],
            ]
        ),
        hr(),
        heading("Legal Compliance", 3),
        bullet_list([
            [("CAN-SPAM (US)", ["bold"]), ": include a valid business address and a clear unsubscribe mechanism"],
            [("GDPR (EU)", ["bold"]), ": ensure you have a lawful basis for contact and provide an opt-out option"],
            "Always be transparent about who you are and make opting out easy",
        ]),
        hr(),
        heading("The 3 Pillars of Cold Email Success", 3),
        heading("Pillar 1 – Technical Infrastructure", 4),
        bullet_list([
            "Configure SPF, DKIM, DMARC, and MX records (Icemail does this automatically for you)",
            "Allow new domains 30–90 days before scaling — or use pre-warmed mailboxes to skip the wait",
            "Start with 10–20 emails/day per mailbox and increase gradually",
            "For Google & Microsoft: target 15 cold + 15 warmup emails/day (1:1 ratio recommended)",
            "Monitor bounce rates and spam complaint rates continuously",
        ]),
        heading("Pillar 2 – List Building", 4),
        bullet_list([
            "Define your Ideal Customer Profile (ICP) by role, seniority, industry, and pain points",
            "Source leads from LinkedIn, company research, and verified data providers",
            "Verify email addresses before sending to reduce bounce rates",
            "Filter out non-matching prospects to keep lists focused",
            "Prioritize quality over volume",
        ]),
        heading("Pillar 3 – Offer & Copy", 4),
        bullet_list([
            "Lead with value — address a genuine problem your prospect faces",
            "Subject lines: spark curiosity, avoid hype and clickbait",
            "Keep emails under 150 words — short, relevant, human",
            "Personalize beyond name insertion: reference company news, role specifics, or shared context",
            "Use 1–3 email sequences with 2–5 day spacing between follow-ups",
        ]),
        hr(),
        heading("Cold Email Execution Framework", 3),
        bullet_list([
            [("Step 1", ["bold"]), ": Set clear objectives (meetings booked, replies, demos scheduled)"],
            [("Step 2", ["bold"]), ": Build and verify prospect lists"],
            [("Step 3", ["bold"]), ": Configure infrastructure (use Icemail for automated DNS and mailbox setup)"],
            [("Step 4", ["bold"]), ": Write concise, value-driven emails"],
            [("Step 5", ["bold"]), ": Send gradually and monitor volume limits"],
            [("Step 6", ["bold"]), ": Follow up 2–3 times with varied messaging"],
            [("Step 7", ["bold"]), ": Track replies, bounces, and opt-outs; adjust accordingly"],
        ]),
        hr(),
        para(["Properly executed cold email campaigns typically produce measurable results within 30–60 days. Consistency and continuous optimization are key."]),
        hr(),
        para([("Need help?", ["bold"]), " Contact our support team at ", ("team@icemail.ai", ["bold"]), "."]),
    )
    return title, description, content


def build_article_M():
    title = "🛡️ Domain Protection & Deliverability Shield in Icemail"
    description = "How Icemail's Deliverability Shield monitors blacklists, DNS security, and domain reputation to protect your cold outreach domains."
    content = doc(
        para(["Icemail's Deliverability Shield protects your outreach domains by continuously monitoring risk factors that affect inbox placement and sender reputation."]),
        hr(),
        heading("What Deliverability Shield Protects", 3),
        bullet_list([
            [("Blacklist Monitoring", ["bold"]), ": get notified immediately if your domain appears on major blocklists"],
            [("DNS Security Monitoring", ["bold"]), ": detects DNS misconfigurations, potential hijacking risks, or suspicious record changes early"],
            [("Deliverability Protection", ["bold"]), ": maintains strong domain reputation for improved inbox placement over time"],
        ]),
        hr(),
        heading("Eligible Domains", 3),
        bullet_list([
            "Domains purchased through Icemail",
            "Domains connected via direct integrations: Namecheap, Name.com, Dynadot, Spaceship, Cloudflare",
        ]),
        hr(),
        heading("Accessing Deliverability Shield", 3),
        para(["Navigate to: ", ("Icemail dashboard", ["bold"]), " → ", ("Deliverability", ["bold"]), " → ", ("Deliverability Shield", ["bold"]), " (left sidebar)."]),
        hr(),
        heading("Activating Protection", 3),
        bullet_list([
            ["Select your domain and click ", ("Activate Deliverability Shield", ["bold"])],
            "Review the pricing details, protection features, and prorated billing information",
            ["Click ", ("Add Shield", ["bold"]), " to confirm"],
            "Complete payment via Stripe (card) or Wallet",
        ]),
        para(["Protection activates immediately after payment is confirmed."]),
        hr(),
        heading("Managing Your Subscription", 3),
        para(["View your protected domains, subscription status, and renewal dates from the ", ("Billing", ["bold"]), " section of your dashboard."]),
        hr(),
        heading("Canceling Protection", 3),
        para(["To cancel Deliverability Shield:"]),
        bullet_list([
            [("Billing", ["bold"]), " → ", ("Deliverability Shield Tab", ["bold"])],
            ["Click the three-dot menu next to the domain → ", ("Cancel Subscription", ["bold"])],
            ["Check the terms checkbox → type ", ("\"Cancel\"", ["bold"]), " in the confirmation field → confirm"],
        ]),
        para([("Note:", ["bold"]), " Protection stops immediately upon cancellation. No further charges will be applied."]),
        hr(),
        para([("Need help?", ["bold"]), " Contact our support team at ", ("team@icemail.ai", ["bold"]), "."]),
    )
    return title, description, content


def build_article_N():
    title = "📊 Inbox Placement Tests in Icemail: Monitor Inbox vs Spam"
    description = "Use Icemail's Inbox Placement Tests to see where your emails land across major providers before sending at scale."
    content = doc(
        para(["Inbox Placement Tests show you exactly where your emails land — inbox, spam, or other folders — across major email providers, before you send at scale."]),
        hr(),
        heading("What Inbox Placement Tests Reveal", 3),
        bullet_list([
            "Precise email placement across Inbox, Spam, or Other folders",
            "Deliverability health metrics broken down by email provider",
            "Performance data to optimize campaigns before scaling",
        ]),
        hr(),
        heading("Test Characteristics", 3),
        bullet_list([
            [("Results within 2–24 hours", ["bold"]), ": timing depends on the test configuration"],
            [("Safe to run anytime", ["bold"]), ": tests do not affect your sender reputation"],
            [("No real contacts receive emails", ["bold"]), ": tests use non-promotional messages sent only to seed inboxes"],
        ]),
        hr(),
        heading("How to Run a Test", 3),
        bullet_list([
            ["Go to the ", ("Deliverability", ["bold"]), " section in your Icemail dashboard"],
            [("Click ", []), ("\"Run Deliverability Test\"", ["bold"])],
            "Configure the test: enter a test name, select mailboxes to test, add email content (optional), and choose test type",
            "Complete payment and confirm",
            "Review results showing placement breakdown across email providers",
        ]),
        hr(),
        heading("Pricing", 3),
        bullet_list([
            [("One-time test", ["bold"]), ": $2.00 per mailbox"],
            [("Monthly subscription", ["bold"]), ": $3.00 per mailbox per month"],
        ]),
        hr(),
        heading("When to Run Tests", 3),
        bullet_list([
            "When setting up new domains or mailboxes for the first time",
            "Before scaling up outreach campaigns",
            "After modifying your email copy significantly",
            "When you notice a decline in open rates or reply rates",
            "Monthly testing is recommended for ongoing deliverability monitoring",
        ]),
        hr(),
        para([("Need help?", ["bold"]), " Contact our support team at ", ("team@icemail.ai", ["bold"]), "."]),
    )
    return title, description, content


def build_article_O():
    title = "⭐ High Reputation Domains in Icemail"
    description = "What High Reputation Domains are, why they improve deliverability, and how to purchase them in Icemail."
    content = doc(
        para(["High Reputation Domains are aged, pre-vetted domains with established digital history. They give you a deliverability head start compared to brand-new domains."]),
        hr(),
        heading("What Are High Reputation Domains?", 3),
        para(["Previously registered domains with existing online history, selected specifically for cold email outreach. Every domain in Icemail's inventory is:"]),
        bullet_list([
            "Checked against major spam and abuse blacklists",
            "Pre-screened for safe sending and naming relevance",
            "Optimized for cold email outreach",
            "Available in brand-aligned naming variations",
        ]),
        hr(),
        heading("Why Use High Reputation Domains?", 3),
        bullet_list([
            [("Better Deliverability", ["bold"]), ": aged domains receive greater trust from inbox providers, leading to more inbox placement vs. spam"],
            [("Clean Reputation", ["bold"]), ": every domain is vetted before listing — you start with a clean, sender-friendly reputation"],
            [("Higher Trust & Credibility", ["bold"]), ": older domains carry stronger sender authority, which can lead to better open and reply rates"],
            [("Built for Cold Outreach", ["bold"]), ": domains are selected specifically for professional structure and outbound relevance"],
        ]),
        hr(),
        heading("Best Practices", 3),
        bullet_list([
            "Warm up mailboxes for at least 2–3 weeks before beginning outreach",
            "Start with 20 or fewer emails per day per mailbox",
            "Spread sending across multiple domains and mailboxes",
            "Always validate your email leads to reduce bounce rates",
            "Avoid sudden spikes in daily sending volume",
            "Personalize emails for better engagement and deliverability signals",
            "Rotate domains across larger campaigns",
        ]),
        hr(),
        heading("How to Purchase", 3),
        bullet_list([
            [("Navigate to ", []), ("Domain", ["bold"]), " → ", ("High Reputation Domain", ["bold"]), " section from the sidebar"],
            "Browse or search available domains aligned with your brand",
            ["Click ", ("Add to Cart", ["bold"]), " for your selected domain(s)"],
            ["Click ", ("View Cart", ["bold"]), " → ", ("Checkout", ["bold"])],
            ["Proceed to Payment via ", ("Stripe", ["bold"]), " or ", ("Wallet", ["bold"])],
        ]),
        hr(),
        heading("Activation Note", 3),
        para(["High Reputation Domains may take ", ("up to 3 hours", ["bold"]), " to become fully active after purchase. Combine with proper warmup, safe sending volumes, and verified leads for best results."]),
        hr(),
        para([("Need help?", ["bold"]), " Contact our support team at ", ("team@icemail.ai", ["bold"]), "."]),
    )
    return title, description, content


def build_article_P():
    title = "🔥 Pre-warmed Mailboxes in Icemail: Complete Guide"
    description = "What pre-warmed mailboxes are, their benefits and limitations, safe usage guidelines, and how to get started in Icemail."
    content = doc(
        para(["Pre-warmed mailboxes are professionally prepared Google Workspace or Microsoft 365 accounts that arrive with established sending history and reputation — ready for outreach faster than standard mailboxes."]),
        hr(),
        heading("What Are Pre-warmed Mailboxes?", 3),
        para(["Mailboxes that are:"]),
        bullet_list([
            "Created in advance and gradually warmed with safe, authentic sending activity",
            "Aged over time to build a natural sending history",
            "Monitored for health and sender reputation",
        ]),
        hr(),
        heading("Key Benefits", 3),
        bullet_list([
            [("Faster Campaign Launches", ["bold"]), ": start outreach without weeks of manual warmup"],
            [("Improved Inbox Placement", ["bold"]), ": established sender reputation means better deliverability from day one"],
            [("Reduced Spam Filtering Risks", ["bold"]), ": sending history reduces the likelihood of early spam filtering"],
            [("Higher Sending Volume Limits", ["bold"]), ": more generous daily limits immediately available"],
            [("Complimentary Deliverability Shield", ["bold"]), ": protection included with every pre-warmed mailbox"],
        ]),
        hr(),
        heading("What's Included", 3),
        bullet_list([
            "Gradual warmup history with realistic sending patterns",
            "Sending behavior simulation and inbox interaction signals",
            "Complete DNS authentication setup (SPF, DKIM, DMARC, MX)",
            "Ongoing health monitoring",
            "No technical setup required on your end",
        ]),
        hr(),
        heading("Important Limitations", 3),
        bullet_list([
            [("12-Month Lifecycle", ["bold"]), ": pre-warmed mailboxes have a non-renewable 12-month lifespan and cannot be extended"],
            [("Username Changes", ["bold"]), ": modifying the email address resets the warmup history — the mailbox will no longer be considered pre-warmed"],
            [("Non-Refundable", ["bold"]), ": once provisioned, pre-warmed mailboxes cannot be refunded"],
            [("Custom Domains", ["bold"]), ": you cannot bring your own domains or convert existing domains — pre-warmed mailboxes are exclusive to Icemail's infrastructure"],
        ]),
        hr(),
        heading("Safe Usage Guidelines", 3),
        bullet_list([
            "Start at 20 emails/day per mailbox and increase gradually over weeks",
            "Keep warmup features active throughout your outreach",
            "Use only verified, clean email lists",
            "Rotate across multiple mailboxes when scaling",
        ]),
        hr(),
        heading("Activation", 3),
        para(["Orders are provisioned ", ("instantly", ["bold"]), " — domains and mailboxes appear in your dashboard immediately with no waiting period."]),
        hr(),
        para([("Need help?", ["bold"]), " Contact our support team at ", ("team@icemail.ai", ["bold"]), "."]),
    )
    return title, description, content


# ── Main logic ─────────────────────────────────────────────────────────────────

def get_existing_collections():
    data = api_get("/v3/helpcenter/collections")
    # May be list or dict with items key
    if isinstance(data, list):
        return data
    return data.get("collections", data.get("items", []))


def create_collection(title_en, description_en):
    body = {
        "title": {"en": title_en},
        "description": {"en": description_en},
        "iconUrl": "",
    }
    return api_post("/v3/helpcenter/collections", body)


def create_article(col_id, title_en, description_en, content_doc):
    plain = plain_text_from_doc(content_doc)
    body = {
        "title": {"en": title_en},
        "description": {"en": description_en},
        "content": {"en": content_doc},
        "plainContent": {"en": plain},
        "isDraft": False,
    }
    return api_post(f"/v3/helpcenter/collections/{col_id}/articles", body)


def main():
    print("=" * 60)
    print("Icemail Gleap Help Center Creator")
    print("=" * 60)

    # ── Step 1: Get existing collections ──────────────────────────
    print("\n[1] Fetching existing collections...")
    existing = get_existing_collections()
    existing_titles = {c["title"].get("en", "").strip().lower(): c for c in existing}
    print(f"    Found {len(existing)} existing collections:")
    for c in existing:
        print(f"      - {c['title'].get('en')} (id: {c['id']})")

    # ── Step 2: Create new collections ────────────────────────────
    new_collections_def = [
        ("Getting Started", "Everything you need to get up and running with Icemail quickly."),
        ("Deliverability Tools", "Monitor inbox placement, protect your domains, and optimize deliverability."),
        ("High Reputation Domains", "Pre-aged, trusted domains with established reputation history for better inbox placement."),
        ("Pre-warmed Domains & Mailboxes", "Launch outreach faster with mailboxes that already have established sending history."),
    ]

    collection_map = {}  # title -> id
    # Pre-populate from existing
    for c in existing:
        collection_map[c["title"].get("en", "")] = c["id"]

    print("\n[2] Creating new collections...")
    created_collections = []
    for title, desc in new_collections_def:
        if title.strip().lower() in existing_titles:
            cid = existing_titles[title.strip().lower()]["id"]
            print(f"    SKIP (exists): {title} (id: {cid})")
            collection_map[title] = cid
        else:
            try:
                result = create_collection(title, desc)
                cid = result.get("_id") or result.get("id")
                collection_map[title] = cid
                created_collections.append((title, cid))
                print(f"    CREATED: {title} (id: {cid})")

                # Update gleap dir collection slug
                col_slug = slugify(title)
                os.makedirs(os.path.join(GLEAP_DIR, col_slug), exist_ok=True)
            except Exception as e:
                print(f"    ERROR creating collection '{title}': {e}")

    # ── Step 3: Define articles ────────────────────────────────────
    # Map: (builder_fn, collection_title_or_id, use_id_directly)
    DOMAIN_MGMT_ID = "6849b63fe92e06806c87c22a"
    MAILBOX_MGMT_ID = "6849b68247ecc2e7b5a14dfa"

    articles = [
        # Domain Management articles
        (build_article_A, DOMAIN_MGMT_ID, "domain-management"),
        (build_article_B, DOMAIN_MGMT_ID, "domain-management"),
        (build_article_C, DOMAIN_MGMT_ID, "domain-management"),
        (build_article_D, DOMAIN_MGMT_ID, "domain-management"),
        (build_article_E, DOMAIN_MGMT_ID, "domain-management"),
        (build_article_F, DOMAIN_MGMT_ID, "domain-management"),
        # Mailbox Management articles
        (build_article_G, MAILBOX_MGMT_ID, "mailbox-management"),
        # Getting Started articles
        (build_article_H, "Getting Started", None),
        (build_article_I, "Getting Started", None),
        (build_article_J, "Getting Started", None),
        (build_article_K, "Getting Started", None),
        (build_article_L, "Getting Started", None),
        # Deliverability Tools articles
        (build_article_M, "Deliverability Tools", None),
        (build_article_N, "Deliverability Tools", None),
        # High Reputation Domains articles
        (build_article_O, "High Reputation Domains", None),
        # Pre-warmed Domains & Mailboxes articles
        (build_article_P, "Pre-warmed Domains & Mailboxes", None),
    ]

    print(f"\n[3] Creating {len(articles)} articles...")
    created_articles = []
    errors = []

    for builder, col_ref, col_slug_override in articles:
        title, description, content = builder()

        # Resolve collection ID
        if col_ref in (DOMAIN_MGMT_ID, MAILBOX_MGMT_ID):
            col_id = col_ref
            col_slug = col_slug_override
        else:
            col_id = collection_map.get(col_ref)
            col_slug = slugify(col_ref) if col_ref else col_slug_override

        if not col_id:
            msg = f"ERROR: Collection '{col_ref}' not found for article '{title}'"
            print(f"    {msg}")
            errors.append(msg)
            continue

        print(f"    Creating: {title[:70]}...")
        try:
            result = create_article(col_id, title, description, content)
            article_id = result.get("_id") or result.get("id")

            # Save MDX
            filepath = save_mdx(col_slug, article_id, title, description, content, col_id)

            print(f"      ✓ Created (id: {article_id})")
            print(f"      ✓ Saved: {filepath}")
            created_articles.append((title, article_id, filepath))
        except Exception as e:
            msg = f"ERROR creating article '{title}': {e}"
            print(f"      {msg}")
            errors.append(msg)

    # ── Summary ────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    print(f"\nCollections created ({len(created_collections)}):")
    for title, cid in created_collections:
        print(f"  - {title} → {cid}")

    print(f"\nArticles created ({len(created_articles)}):")
    for title, aid, fp in created_articles:
        print(f"  - [{aid}] {title}")
        print(f"    → {fp}")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")
    else:
        print("\nNo errors!")

    print("\nDone.")


if __name__ == "__main__":
    main()
