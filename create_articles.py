#!/usr/bin/env python3
"""
Script to create all new articles in Gleap and save as .mdx files.
Run: python3 create_articles.py
"""

import json
import os
import re
import sys
import uuid
import hashlib
import urllib.request
import urllib.error
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

GLEAP_TOKEN = os.environ.get(
    "GLEAP_TOKEN",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpZCI6IjZhMmY4YjQ3ODYyODU5OWNlNWRjODE0OSIsInByb2plY3RJZCI6IjY4MzVjYzRkYTVkM2E0YjhlNGM4ZTI3NCIsInNlY3JldEFwaUtleSI6IjBoc1RKTmZDeUE0UTBLTEtad3FnZjAydzNIRThqUFVmIiwidXNlclR5cGUiOiJzZXJ2aWNlX2FjY291bnQiLCJpYXQiOjE3ODE1MDA3NDN9"
    ".lyJC8-8g8t106JRjPUU3dDB9t222k9C7HgW0xYoxL80",
)
GLEAP_PROJECT = os.environ.get("GLEAP_PROJECT", "6835cc4da5d3a4b8e4c8e274")
GLEAP_API = "https://api.gleap.io"
GLEAP_DIR = Path(__file__).parent / "gleap"

DOMAIN_MGMT_COL = "6849b63fe92e06806c87c22a"
EXPORT_INT_COL  = "6849b6b8e92e06806c8bd279"

# ── HTTP helpers ───────────────────────────────────────────────────────────────

def _headers():
    return {
        "Authorization": f"Bearer {GLEAP_TOKEN}",
        "project": GLEAP_PROJECT,
        "Content-Type": "application/json",
    }

def _request(method, path, body=None):
    url = f"{GLEAP_API}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=_headers(), method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {path} → {e.code}: {e.read().decode()[:500]}")

def api_post(path, b): return _request("POST", path, b)
def api_put(path, b):  return _request("PUT", path, b)

# ── Markdown → TipTap ────────────────────────────────────────────────────────

def _new_id():
    return str(uuid.uuid4())

def _parse_inline(text):
    nodes = []
    pattern = re.compile(
        r"(`[^`]+`)"
        r"|(\*\*\*[^*]+\*\*\*)"
        r"|(\*\*[^*]+\*\*)"
        r"|(\*[^*]+\*|_[^_]+_)"
        r"|(\[([^\]]+)\]\(([^)]+)\))"
    )
    pos = 0
    for m in pattern.finditer(text):
        if m.start() > pos:
            nodes.append({"type": "text", "text": text[pos:m.start()]})
        pos = m.end()
        if m.group(1):
            inner = m.group(1)[1:-1]
            nodes.append({"type": "text", "marks": [{"type": "code"}], "text": inner})
        elif m.group(2):
            inner = m.group(2)[3:-3]
            nodes.append({"type": "text", "marks": [{"type": "bold"}, {"type": "italic"}], "text": inner})
        elif m.group(3):
            inner = m.group(3)[2:-2]
            nodes.append({"type": "text", "marks": [{"type": "bold"}], "text": inner})
        elif m.group(4):
            inner = m.group(4)[1:-1]
            nodes.append({"type": "text", "marks": [{"type": "italic"}], "text": inner})
        elif m.group(5):
            link_text = m.group(6)
            href = m.group(7)
            nodes.append({
                "type": "text",
                "marks": [{"type": "link", "attrs": {"href": href, "target": "_blank",
                                                      "rel": "noopener noreferrer nofollow", "class": None}}],
                "text": link_text,
            })
    if pos < len(text):
        nodes.append({"type": "text", "text": text[pos:]})
    return nodes

def _para(inline_nodes):
    return {"type": "paragraph",
            "attrs": {"id": _new_id(), "class": None, "textAlign": "left"},
            "content": inline_nodes}

def _heading(level, inline_nodes):
    return {"type": "heading",
            "attrs": {"id": _new_id(), "textAlign": "left", "level": level},
            "content": inline_nodes}

def markdown_to_tiptap(md_text):
    lines = md_text.split("\n")
    content = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]

        hm = re.match(r"^(#{1,6})\s+(.*)", line)
        if hm:
            level = len(hm.group(1))
            content.append(_heading(level, _parse_inline(hm.group(2))))
            i += 1
            continue

        if re.match(r"^---+\s*$", line):
            content.append({"type": "horizontalRule"})
            i += 1
            continue

        if line.startswith("```"):
            lang = line[3:].strip()
            code_lines = []
            i += 1
            while i < n and not lines[i].startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1
            code_text = "\n".join(code_lines)
            content.append({
                "type": "codeBlock",
                "attrs": {"language": lang or None},
                "content": [{"type": "text", "text": code_text}],
            })
            continue

        if re.match(r"^[-*+]\s+", line):
            items = []
            while i < n and re.match(r"^[-*+]\s+", lines[i]):
                item_text = re.sub(r"^[-*+]\s+", "", lines[i])
                items.append({
                    "type": "listItem",
                    "content": [_para(_parse_inline(item_text))],
                })
                i += 1
            content.append({"type": "bulletList", "content": items})
            continue

        if re.match(r"^\d+\.\s+", line):
            items = []
            while i < n and re.match(r"^\d+\.\s+", lines[i]):
                item_text = re.sub(r"^\d+\.\s+", "", lines[i])
                items.append({
                    "type": "listItem",
                    "content": [_para(_parse_inline(item_text))],
                })
                i += 1
            content.append({"type": "orderedList", "content": items})
            continue

        if line.startswith("> "):
            bq_lines = []
            while i < n and lines[i].startswith("> "):
                bq_lines.append(lines[i][2:])
                i += 1
            inner_doc = markdown_to_tiptap("\n".join(bq_lines))
            content.append({"type": "blockquote", "content": inner_doc.get("content", [])})
            continue

        if line.strip() == "":
            i += 1
            continue

        para_lines = []
        while i < n and lines[i].strip() != "" and not re.match(r"^#{1,6}\s", lines[i]) \
                and not lines[i].startswith("```") and not re.match(r"^[-*+]\s", lines[i]) \
                and not re.match(r"^\d+\.\s", lines[i]) and not re.match(r"^---+\s*$", lines[i]):
            para_lines.append(lines[i])
            i += 1
        combined = " ".join(para_lines)
        content.append(_para(_parse_inline(combined)))

    return {"type": "doc", "content": content}

def _tiptap_plain_text(doc):
    parts = []
    def walk(node):
        t = node.get("type")
        if t == "text":
            parts.append(node.get("text", ""))
        elif t == "hardBreak":
            parts.append("\n")
        else:
            for child in node.get("content", []):
                walk(child)
            if t in ("paragraph", "heading", "listItem", "codeBlock", "blockquote"):
                parts.append("\n")
    walk(doc)
    return "".join(parts).strip()

# ── .mdx helpers ──────────────────────────────────────────────────────────────

def _slugify(text):
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_]+", "-", text.strip())
    return text[:80]

def _content_hash(md_body):
    return hashlib.md5(md_body.encode()).hexdigest()[:8]

def save_mdx(path, title, description, gleap_id, col_id, col_slug, md_body, is_draft=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    h = _content_hash(md_body)
    fm_lines = [
        "---",
        f'title: "{title}"',
        f'description: "{description}"',
        f'gleap_id: "{gleap_id}"',
        f'gleap_collection: "{col_id}"',
        f'gleap_collection_slug: "{col_slug}"',
        f'isDraft: {json.dumps(is_draft)}',
        f'content_hash: "{h}"',
        "---",
        "",
    ]
    path.write_text("\n".join(fm_lines) + "\n" + md_body + "\n")
    print(f"  Saved: {path}")

# ── Create article in Gleap ───────────────────────────────────────────────────

def create_and_push(title, description, col_id, col_slug, md_body, filename):
    print(f"\nCreating: {title}")
    resp = api_post(f"/v3/helpcenter/collections/{col_id}/articles", {
        "title": {"en": title},
        "isDraft": False,
    })
    gleap_id = resp.get("id") or resp.get("_id") or resp.get("article", {}).get("id", "")
    if not gleap_id:
        print(f"  ERROR: no id in response: {resp}")
        return None
    print(f"  Created with ID: {gleap_id}")

    tiptap_doc = markdown_to_tiptap(md_body)
    plain = _tiptap_plain_text(tiptap_doc)

    payload = {
        "title": {"en": title},
        "description": {"en": description},
        "content": {"en": tiptap_doc},
        "plainContent": {"en": plain},
        "isDraft": False,
    }
    api_put(f"/v3/helpcenter/collections/{col_id}/articles/{gleap_id}", payload)
    print(f"  Content pushed.")

    path = GLEAP_DIR / col_slug / filename
    save_mdx(path, title, description, gleap_id, col_id, col_slug, md_body)
    return gleap_id

# ── Article content ───────────────────────────────────────────────────────────

DOMAIN_FORWARDING_BP = """Redirecting cold email domains to your main website is one of the smartest—and most overlooked—steps in cold email infrastructure. This guide covers everything you need to know about domain forwarding: when to use it, when to avoid it, how to set it up in Icemail, common mistakes, and answers to the most frequently asked questions.

---

### What Is Domain Forwarding?

**Domain forwarding** (also called URL forwarding or domain redirect) automatically sends anyone who visits one domain directly to another. For example, if a prospect types `yourcampaign.io` into their browser, they are instantly redirected to `yourcompany.com`.

In the context of cold email infrastructure, domain forwarding is used so that the secondary "sending domains" you buy for cold outreach don't look like dead ends to prospects or spam filters.

---

### Why Domain Forwarding Matters for Cold Email

When you send cold emails, best practice is to **never send from your primary domain** (e.g., `yourcompany.com`). Instead, you buy secondary domains (e.g., `yourcompany-hq.com`, `getourproduct.io`) and send from those. This protects your primary domain's reputation.

But here's the problem: if a prospect receives an email from `yourcompany-hq.com` and tries to visit that website, they see a blank page or an error. That looks suspicious—both to the human and to spam filters that crawl links.

**Domain forwarding solves this by redirecting secondary domains to your real website.** Your prospect lands on your main site, and your secondary domain looks legitimate.

---

### When TO Use Domain Forwarding

Use domain forwarding in the following situations:

- **You own secondary/alias sending domains** — Any domain you purchased specifically for cold outreach (not your main brand domain) should forward to your main website.
- **You want to protect your primary domain's reputation** — By sending from secondaries that look real, you avoid risking the deliverability of your primary domain.
- **You're running multi-domain outreach campaigns** — When you have 5, 10, or 20+ sending domains, forwarding all of them to your main site keeps your brand consistent.
- **Your prospects may Google your sending domain** — If anyone checks whether your domain is real, they should land on your website.
- **You're setting up brand-new domains** — New domains should have domain forwarding enabled before you start warming them up.

---

### When NOT to Use Domain Forwarding

There are specific scenarios where domain forwarding should **not** be used:

- **Do not forward the domain you are actively sending cold emails from** — Forwarding your sending domain to another domain can create DNS and email delivery conflicts. The forwarding and the email records must coexist correctly; misconfiguration can break your SPF/DKIM alignment.
- **Do not forward your primary brand domain** — Your `yourcompany.com` should remain your main website. Do not forward it anywhere.
- **Do not use domain forwarding as a replacement for proper DNS setup** — You still need SPF, DKIM, and DMARC records on every sending domain. Forwarding is for web traffic only; it does not affect email routing.
- **Do not forward to a domain that itself has deliverability issues** — If your main domain has been blacklisted or has poor reputation, forwarding to it won't help and may raise more flags.

---

### How Domain Forwarding Protects Your Main Domain's Reputation

Your primary domain (`yourcompany.com`) likely has years of good sending history, positive engagement signals, and trusted relationships. Sending cold outreach from it puts all of that at risk.

By building a secondary domain infrastructure:

1. **Cold outreach reputation stays isolated** — Any spam complaints, bounces, or blocklist hits on your secondary domains do not affect your primary domain.
2. **Secondary domains look real thanks to forwarding** — Spam filters check whether a sending domain resolves to a real website. A domain that forwards to a legitimate company site passes these checks.
3. **Your primary domain keeps its Google/Microsoft trust scores** — Gmail and Outlook maintain sender reputation scores per domain. Keeping cold email on secondaries protects your primary score.
4. **If a secondary domain gets flagged, you retire it** — You can simply stop sending from a burned domain and replace it with a fresh one, with zero impact on your main brand.

---

### How to Set Up Domain Forwarding in Icemail – Step by Step

#### **Step 1: Go to the Domains Dashboard**

Log in to your **Icemail** account and click on **"Domains"** in the left-hand navigation menu.

#### **Step 2: Select the Domain to Forward**

Find the secondary sending domain you want to redirect (e.g., `yourcompany-hq.com`). Click on it to open the domain detail panel.

#### **Step 3: Open Domain Settings**

Click **"See More"** to expand the domain sidebar. Then navigate to the **"Domain Settings"** tab.

#### **Step 4: Enter Your Target (Main) Domain**

In the **Domain Forwarding** section, enter the full URL of your main website (e.g., `https://yourcompany.com`).

> _Important: Always include the full protocol (`https://`). Do not enter just `yourcompany.com` without the protocol prefix._

#### **Step 5: Save Your Settings**

Click **"Save."** Domain forwarding is now active for that domain.

All web traffic to your secondary domain will immediately redirect to your main website. No DNS propagation delay is required—the change takes effect almost instantly.

#### **Step 6: Repeat for All Secondary Sending Domains**

Repeat Steps 2–5 for every secondary domain in your Icemail account. Every sending domain should forward to your main website.

---

### Common Mistakes to Avoid

- **Forgetting to set up forwarding on new domains** — When you add new sending domains to Icemail, make sure to configure forwarding before you start sending campaigns. Build it into your domain setup checklist.
- **Forwarding to a URL that returns a 404 or error** — Test every forwarding destination by visiting the secondary domain in a browser. If the redirect is broken, fix it immediately.
- **Using HTTP instead of HTTPS** — Always forward to your HTTPS URL. Forwarding to `http://` is a minor trust signal issue; modern browsers flag non-HTTPS sites.
- **Thinking forwarding replaces email authentication** — Domain forwarding is for web traffic only. You still need SPF, DKIM, and DMARC records on every sending domain to ensure email deliverability. Do not skip DNS authentication setup.
- **Forwarding your primary domain to a secondary** — The direction must always be secondary → primary. Never forward your main domain away from your main website.
- **Setting up forwarding on a domain you no longer use** — If you retire a sending domain, it doesn't hurt to leave forwarding active, but keep your Icemail domain list clean and organized.

---

### Frequently Asked Questions

**Does domain forwarding affect my email deliverability?**

Domain forwarding affects web traffic only—it does not route or change email. Your SPF, DKIM, and DMARC records handle email authentication independently. However, having a domain that resolves to a real website (via forwarding) is a positive signal for spam filters that check domain legitimacy.

**How long does it take for domain forwarding to activate?**

In Icemail, domain forwarding takes effect almost immediately after saving. No DNS changes are required on your end—Icemail handles the redirect at the infrastructure level.

**Should I forward all my sending domains?**

Yes. Every secondary domain you use for cold outreach should forward to your main website. This applies whether the domain is actively sending, warming up, or parked.

**Can I forward to a specific page instead of my homepage?**

Yes. Instead of `https://yourcompany.com`, you can enter `https://yourcompany.com/about` or any other specific page URL as the forwarding destination.

**Do I need to set up forwarding for Google Workspace and Microsoft 365 domains separately?**

No. Domain forwarding in Icemail applies to the domain itself, regardless of which mailbox type (Google, Microsoft, SMTP, or Azure) is set up on it. You configure it once per domain.

**What happens to email if I set up domain forwarding?**

Nothing. Domain forwarding in Icemail only handles HTTP/web traffic. Your email DNS records (MX, SPF, DKIM, DMARC) are completely unaffected.

**My secondary domain has no website—does that hurt deliverability?**

Without forwarding, a secondary domain with no website looks like a dead domain, which can be a negative signal for spam filters. Setting up forwarding to your main website makes the domain look active and legitimate, which is better for deliverability.

---

### Related Articles

- [How to Set Up Domain Forwarding in Icemail](#)
- [Understanding Domain Forwarding, DMARC, Forwarding Email, and Catch-All Email](#)
- [How to Set Up DMARC Email in Icemail](#)
- [Setting Up Email Forwarding for Google & Microsoft Workspaces](#)
- [How to Set Up Catch-All Email in Icemail](#)

---

### Need Help?

Have questions about domain forwarding or your cold email infrastructure setup? Our team is here to help.

Email us anytime at [**team@icemail.ai**](mailto:team@icemail.ai)

---
"""

CUSTOM_TRACKING_DOMAIN_BP = """Your custom tracking domain is one of the most important (and most overlooked) deliverability settings in cold email. Using a generic tracking domain shared with thousands of other senders is a deliverability liability. This guide covers everything you need to know: what a custom tracking domain is, why it matters, how to set one up, best practices, common mistakes, and how it impacts your inbox placement.

---

### What Is a Custom Tracking Domain?

When you send a cold email with link tracking or open tracking enabled, your sending platform replaces links in your email with tracking URLs. Those tracking URLs contain a domain name—the **tracking domain**.

By default, many platforms use a **generic shared tracking domain** (e.g., `trk.genericplatform.com`) that is used by thousands of senders simultaneously. If any of those senders get flagged for spam, the shared tracking domain gets blacklisted—and your emails suffer the consequences, even if your own outreach is perfectly clean.

A **custom tracking domain** is a domain (or subdomain) that belongs exclusively to you, used only for tracking your own emails. It looks like:

> `track.yourdomain.com`

This subdomain points to the tracking server via a CNAME DNS record, but it displays your branded domain name in every link in your emails.

---

### Generic Tracking Domain vs. Custom Tracking Domain

- **Generic tracking domain**: Shared with thousands of senders. One bad actor's spam complaints affect your deliverability. No brand consistency. Higher spam filter suspicion.
- **Custom tracking domain**: Yours alone. Your reputation stays isolated. Your links show your brand. Better inbox placement.

---

### Why You Need a Custom Tracking Domain

#### 1. Reputation Isolation

A shared tracking domain accumulates reputation signals from all its users. When spam filters see `trk.genericplatform.com` in email links, they apply the aggregate reputation of all senders using that domain—not just yours. A custom tracking domain carries only your sending history.

#### 2. Better Inbox Placement

Spam filters analyze the domains embedded in email links. A custom tracking domain that matches (or closely matches) your sending domain is a positive signal. Generic or mismatched tracking domains are frequently flagged.

#### 3. Brand Consistency

Every link in your cold emails passes through your tracking domain. Using `track.yourcompany.com` instead of a third-party URL looks more professional and trustworthy to recipients.

#### 4. Avoid Shared Blacklists

If a generic tracking domain gets blacklisted—even temporarily—every email sent through it lands in spam. With your own custom tracking domain, you are insulated from other senders' behavior.

#### 5. Deliverability Visibility

With a custom tracking domain, deliverability issues are traceable to your own sending behavior, making it easier to diagnose and fix problems.

---

### How to Set Up a Custom Tracking Domain

Setting up a custom tracking domain requires creating a CNAME DNS record that points your subdomain to the tracking server. In Icemail, your tracking domain is pre-configured—here is how to verify and use it.

#### **Step 1: Identify Your Tracking Subdomain**

The recommended format is:

> `track.yourdomain.com`

Choose a subdomain that is short, clean, and clearly associated with your brand. Common choices:
- `track.yourdomain.com`
- `click.yourdomain.com`
- `t.yourdomain.com`
- `links.yourdomain.com`

#### **Step 2: Add a CNAME Record in Your DNS**

In your domain registrar or DNS provider (e.g., Cloudflare, Namecheap, GoDaddy), add a CNAME record:

- **Type**: CNAME
- **Name/Host**: `track` (or whichever subdomain you chose)
- **Value/Target**: The tracking server hostname provided by Icemail (contact team@icemail.ai for your specific tracking server address)
- **TTL**: 3600 (or Auto)

DNS changes typically propagate within a few minutes to a few hours.

#### **Step 3: Verify Your Custom Tracking Domain in Icemail**

1. Log in to your **Icemail** dashboard.
2. Navigate to the **Mailboxes** section.
3. In the mailbox listing, hover over the **Export Details** icon next to the domain.
4. A tooltip popup will display your active **Custom Tracking Domain**.

This confirms which tracking domain is associated with your mailboxes and campaigns.

#### **Step 4: Configure Your Sending Platform**

In your cold email sending tool (e.g., Instantly, Smartlead, Lemlist, or others), go to the tracking domain settings and enter your custom tracking domain. This ensures all tracked links in your campaigns use your branded subdomain.

---

### Best Practices for Custom Tracking Domains

#### Use a Subdomain, Not Your Primary Domain

Always set up your tracking domain as a **subdomain** (e.g., `track.yourdomain.com`), never as your root domain (`yourdomain.com`). Reasons:

- Your root domain hosts your main website. Pointing it to a tracking server would break your website.
- Subdomains allow you to isolate tracking activity from other web traffic.
- If you need to change tracking servers, you only update the subdomain's CNAME—your main domain is unaffected.

#### Match Your Tracking Domain to Your Sending Domain

For best deliverability, use the same base domain for sending and tracking. If you send from `john@yourcompany-hq.com`, your tracking domain should be `track.yourcompany-hq.com`—not a completely different domain. Mismatched domains can trigger spam filters.

#### Use One Tracking Domain Per Sending Domain

Avoid using one tracking domain across many unrelated sending domains. Keep your tracking reputation tied to the domain it's associated with.

#### Keep Your Tracking Subdomain Clean

Never use your tracking subdomain for any other purpose. Do not host a website on it, do not send emails from it, do not use it for anything other than email link tracking.

#### Don't Reuse Tracking Domains Across Clients

If you manage cold email for multiple clients, each client's domains should have their own tracking subdomains. Cross-contamination of tracking reputation is a real risk when subdomains are shared.

#### Monitor for Blacklisting

Periodically check your custom tracking domain against major blacklists (MX Toolbox, MultiRBL). A blacklisted tracking domain will silently tank your deliverability.

---

### Common Mistakes to Avoid

- **Using a generic or shared tracking domain** — This is the most common mistake. Always use a custom tracking domain on every sending domain.
- **Pointing the root domain to the tracking server** — Use a subdomain. Never point `yourdomain.com` itself to the tracking server.
- **Setting up the CNAME incorrectly** — Verify the CNAME is resolving correctly using a DNS lookup tool before going live. A misconfigured CNAME means broken tracking links.
- **Using the same tracking domain for sending and tracking** — Your sending domain (for MX/email routing) and tracking domain (subdomain for CNAME) should be configured separately. Don't confuse these two distinct roles.
- **Forgetting to configure the tracking domain in your sending tool** — Adding the CNAME to DNS is only half the setup. You must also enter the custom tracking domain in your cold email platform's settings.
- **Using a tracking domain with a bad history** — If you purchase an aged domain to use as a tracking domain, verify it has no prior blacklist history before using it.
- **Ignoring tracking domain reputation over time** — Your tracking domain accumulates its own reputation. Monitor it periodically and replace it if it gets blacklisted.

---

### Impact on Inbox Placement

The impact of a custom tracking domain on inbox placement is significant and measurable:

- **Spam filter link scanning** — Both Gmail and Outlook scan domains embedded in email links. A custom tracking domain that is clean and matches your sending domain passes these checks more reliably than a generic shared domain.
- **Avoiding shared blacklists** — A single blacklisted shared tracking domain can instantly push thousands of senders' emails to spam. A custom domain eliminates this shared risk.
- **Click-through authentication** — Some spam filters check whether link domains match the sending domain. Custom tracking domains that align with your sender domain improve this signal.
- **Long-term reputation building** — A custom tracking domain builds its own positive sending history over time, further strengthening your deliverability as your campaigns mature.

In practical terms: switching from a generic to a custom tracking domain is one of the highest-impact, lowest-effort changes you can make to improve cold email inbox placement.

---

### Frequently Asked Questions

**Does Icemail provide a custom tracking domain for each of my sending domains?**

Yes. Each domain you manage in Icemail comes with tracking infrastructure. Contact [team@icemail.ai](mailto:team@icemail.ai) for your specific tracking server CNAME target, then configure the subdomain in your DNS.

**How do I know which custom tracking domain is active on my mailboxes?**

Go to **Mailboxes** in your Icemail dashboard, hover over the **Export Details** icon next to a domain, and the active tracking domain will appear in the tooltip.

**Should I use link tracking at all in cold email?**

Many cold email practitioners recommend disabling open and link tracking—or using it sparingly—during the early stages of a campaign to maximize deliverability. If you do use tracking, a custom tracking domain is essential. Never use generic tracking in serious cold outreach.

**Can I use the same tracking subdomain across multiple sending domains?**

It's better practice to have a separate tracking subdomain per sending domain. However, if you're running a large operation and need to consolidate, using one clean, dedicated tracking domain across related domains is acceptable—just monitor its reputation carefully.

**What if my custom tracking domain gets blacklisted?**

If your tracking domain gets blacklisted, set up a new tracking subdomain (with a fresh CNAME), update the setting in your sending platform, and retire the blacklisted subdomain. Contact [team@icemail.ai](mailto:team@icemail.ai) for assistance.

---

### Related Articles

- [How to Check Your Custom Tracking Domain & Add Filter Tags in Icemail](#)
- [How to Add DNS Records in Icemail](#)
- [How to Set Up DMARC Email in Icemail](#)
- [Domain Forwarding Best Practices for Cold Email](#)

---

### Need Help?

Not sure how to configure your custom tracking domain or CNAME record? Our team can walk you through the full setup.

Email us anytime at [**team@icemail.ai**](mailto:team@icemail.ai)

---
"""

# ── Export integration articles ───────────────────────────────────────────────

def export_article(tool_name, emoji, description, intro, connection_type, steps, benefits, extra_notes=""):
    """Generate a standardized export integration article."""
    steps_md = ""
    for i, step in enumerate(steps, 1):
        steps_md += f"#### **Step {i}:**\n\n{step}\n\n"

    benefits_md = "\n".join(f"- {b}" for b in benefits)

    notes_section = ""
    if extra_notes:
        notes_section = f"\n> {extra_notes}\n\n"

    return f"""Connecting your Icemail mailboxes to **{tool_name}** lets you run powerful cold email campaigns with your fully provisioned, US-IP mailboxes—without any manual credential entry.

---

### Step-by-Step: Connect Icemail Mailboxes to {tool_name}

{steps_md}{notes_section}---

### Why Connect Icemail to {tool_name}?

{benefits_md}

---

### Need Help?

Running into any issues during setup? Contact our support team anytime at [team@icemail.ai](mailto:team@icemail.ai). We're here to help!

---

### Explore More Integrations

- [Export to Instantly →](#)
- [Export to Smartlead →](#)
- [Export to Lemlist →](#)
- [All Export Guides →](#)

---
"""

ARTICLES = [
    # ── Domain Management ─────────────────────────────────────────────────────
    {
        "title": "Domain Forwarding Best Practices for Cold Email – Why, When & How to Use It in Icemail",
        "description": "Learn when to use domain forwarding, when to avoid it, how it protects your main domain reputation, and how to set it up step-by-step in Icemail.",
        "col_id": DOMAIN_MGMT_COL,
        "col_slug": "domain-management",
        "filename": "domain-forwarding-best-practices-for-cold-email.mdx",
        "body": DOMAIN_FORWARDING_BP,
    },
    {
        "title": "Custom Tracking Domain Best Practices for Cold Email – Complete Guide for Icemail Users",
        "description": "Everything you need to know about custom tracking domains: what they are, why you need one, how to set up the CNAME record, best practices, common mistakes, and impact on inbox placement.",
        "col_id": DOMAIN_MGMT_COL,
        "col_slug": "domain-management",
        "filename": "custom-tracking-domain-best-practices-for-cold-email.mdx",
        "body": CUSTOM_TRACKING_DOMAIN_BP,
    },

    # ── Export Integrations ───────────────────────────────────────────────────
    {
        "title": "Connect Your Icemail Mailboxes to Apollo.io",
        "description": "Step-by-step guide to connecting your Icemail mailboxes to Apollo.io for cold email outreach.",
        "col_id": EXPORT_INT_COL,
        "col_slug": "mailbox-export-integrations",
        "filename": "connect-your-icemail-mailboxes-to-apollo-io.mdx",
        "body": export_article(
            "Apollo.io", "🚀",
            "Connect Icemail to Apollo.io",
            "",
            "SMTP/IMAP",
            [
                "Head to the **Mailbox Dashboard** inside Icemail and **select** the mailboxes you wish to export by checking the boxes next to them.",
                "Click **\"Export Mailboxes\"** at the top of the dashboard.",
                "From the platform list, select **\"Apollo.io\"** (or choose the generic **SMTP/IMAP** option if Apollo is not listed).",
                "Click **\"Export\"** — Icemail will display your mailbox credentials: **SMTP host, SMTP port, IMAP host, IMAP port, email address, and password.**",
                "Log in to your **Apollo.io** account and navigate to **Settings → Mailboxes → Connect Mailbox**.",
                "Select **\"Connect via SMTP\"** and enter the credentials provided by Icemail:\n\n- **Email Address**: your Icemail mailbox address\n- **SMTP Host**: `smtp.gmail.com` (Google) or `smtp.office365.com` (Microsoft)\n- **SMTP Port**: `587` (TLS)\n- **IMAP Host**: `imap.gmail.com` (Google) or `outlook.office365.com` (Microsoft)\n- **IMAP Port**: `993`\n- **Password**: your Icemail mailbox password or app password",
                "Click **\"Save\"** or **\"Connect\"** and wait for Apollo to verify the connection. Once verified, your mailbox will appear as active in Apollo.io.",
            ],
            [
                "Run multi-step email sequences directly from Apollo.io",
                "Leverage Apollo's prospecting database with your Icemail mailboxes",
                "All mailboxes are US IP — fully compatible with Apollo's sending requirements",
                "No manual SMTP configuration required when using Icemail's export flow",
                "Support for both Google Workspace and Microsoft 365 mailboxes",
            ],
            "_Tip: If you have Google Workspace mailboxes from Icemail, use an App Password instead of your regular Google account password. Go to your Google Account → Security → 2-Step Verification → App Passwords to generate one._"
        ),
    },
    {
        "title": "Connect Your Icemail Mailboxes to Mailshake",
        "description": "Step-by-step guide to connecting your Icemail mailboxes to Mailshake for cold email campaigns.",
        "col_id": EXPORT_INT_COL,
        "col_slug": "mailbox-export-integrations",
        "filename": "connect-your-icemail-mailboxes-to-mailshake.mdx",
        "body": export_article(
            "Mailshake", "🤝",
            "Connect Icemail to Mailshake",
            "",
            "SMTP/OAuth",
            [
                "Go to your **Mailbox Dashboard** in Icemail and select the mailboxes you want to export by checking the boxes beside each one.",
                "Click **\"Export Mailboxes\"** at the top right.",
                "Select **\"Mailshake\"** from the platform list, or choose **SMTP/IMAP** if Mailshake is not listed directly.",
                "Note down the credentials shown: **email address, password, SMTP host/port, and IMAP host/port.**",
                "Log in to your **Mailshake** account and go to **Settings → Email Accounts → Add Email Account**.",
                "Choose your connection method:\n\n**For Google Workspace mailboxes**: Select **\"Google\"** and sign in with your Icemail Google mailbox. If prompted, use an App Password.\n\n**For Microsoft 365 mailboxes**: Select **\"Microsoft\"** and sign in with your Icemail Microsoft mailbox.\n\n**For SMTP mailboxes**: Select **\"Other / SMTP\"** and enter:\n- SMTP Host: as provided by Icemail\n- SMTP Port: `587`\n- Username: your mailbox email\n- Password: your mailbox password",
                "Click **\"Save\"** or **\"Connect\"**. Mailshake will verify the connection and add the mailbox to your account.",
                "Repeat for each mailbox you exported from Icemail.",
            ],
            [
                "Send cold email sequences directly through your Icemail mailboxes",
                "US IP addresses on all Icemail mailboxes for maximum deliverability",
                "Compatible with Google Workspace ($2.50/mailbox/month) and Microsoft 365 ($2.50/mailbox/month) mailboxes",
                "Recommended sending: 15 cold emails + 15 warmup emails per day per mailbox",
                "Centralize your outreach workflow in Mailshake",
            ],
        ),
    },
    {
        "title": "Connect Your Icemail Mailboxes to QuickMail",
        "description": "Step-by-step guide to connecting your Icemail mailboxes to QuickMail for automated cold email outreach.",
        "col_id": EXPORT_INT_COL,
        "col_slug": "mailbox-export-integrations",
        "filename": "connect-your-icemail-mailboxes-to-quickmail.mdx",
        "body": export_article(
            "QuickMail", "📬",
            "Connect Icemail to QuickMail",
            "",
            "SMTP/OAuth",
            [
                "Head to the **Mailbox Dashboard** inside Icemail and select the mailboxes you want to export.",
                "Click **\"Export Mailboxes\"** at the top of the dashboard.",
                "Select **\"QuickMail\"** from the platform list, or use **SMTP/IMAP** credentials.",
                "Log in to your **QuickMail** account and go to **Settings → Email Accounts → Add Email Account**.",
                "Choose your connection method:\n\n**For Google Workspace mailboxes**: Select **\"Gmail / Google Workspace\"** and authenticate with your Icemail Google mailbox credentials. Use an App Password if required.\n\n**For Microsoft 365 mailboxes**: Select **\"Outlook / Microsoft 365\"** and sign in with your Icemail Microsoft mailbox.\n\n**For SMTP mailboxes**: Select **\"Custom SMTP\"** and enter the host, port, username, and password provided by Icemail.",
                "QuickMail will test the connection. Once verified, the mailbox appears as **Active** in your account.",
                "Configure your sending limits in QuickMail. Icemail recommends **15 cold emails per day** per mailbox (plus 15 warmup emails via your warmup tool for a 1:1 ratio).",
            ],
            [
                "Run fully automated cold email sequences through QuickMail",
                "Supports Google Workspace, Microsoft 365, and SMTP Icemail mailboxes",
                "All Icemail mailboxes have US IP addresses",
                "QuickMail's inbox rotation pairs well with Icemail's multi-mailbox infrastructure",
                "Recommended: 2-3 Icemail mailboxes per sending domain for best deliverability",
            ],
        ),
    },
    {
        "title": "Connect Your Icemail Mailboxes to Klenty",
        "description": "Step-by-step guide to connecting your Icemail mailboxes to Klenty for sales engagement and cold email outreach.",
        "col_id": EXPORT_INT_COL,
        "col_slug": "mailbox-export-integrations",
        "filename": "connect-your-icemail-mailboxes-to-klenty.mdx",
        "body": export_article(
            "Klenty", "⚙️",
            "Connect Icemail to Klenty",
            "",
            "SMTP/OAuth",
            [
                "Go to the **Mailbox Dashboard** in Icemail and select the mailboxes you want to export.",
                "Click **\"Export Mailboxes\"** at the top of the page.",
                "Choose **\"Klenty\"** from the integration list, or select **SMTP/IMAP** to get your credentials.",
                "Log in to your **Klenty** account and navigate to **Settings → Email Configuration → Add Email Account**.",
                "Select your mailbox type:\n\n**Google Workspace**: Click **\"Connect Gmail\"** and sign in using your Icemail Google mailbox. Grant the requested permissions. If using 2FA, generate an App Password from your Google Account settings.\n\n**Microsoft 365**: Click **\"Connect Outlook\"** and authenticate with your Icemail Microsoft mailbox.\n\n**SMTP**: Click **\"Custom SMTP\"** and provide:\n- SMTP Server: as provided by Icemail\n- SMTP Port: `587` (TLS) or `465` (SSL)\n- Username: your mailbox email address\n- Password: your mailbox password\n- IMAP Server and Port for receiving",
                "Save the configuration. Klenty will verify the connection and add the mailbox.",
                "Set your daily sending limits within Klenty. Icemail recommends a maximum of **15 cold emails per day** per mailbox for Google and Microsoft mailboxes.",
            ],
            [
                "Run cadence-based cold email sequences with your Icemail mailboxes",
                "Compatible with Google Workspace and Microsoft 365 Icemail mailboxes",
                "US IP addresses on all Icemail mailboxes",
                "Klenty's CRM integrations work seamlessly with Icemail-connected mailboxes",
                "Scale outreach safely using multiple mailboxes across your Icemail domains",
            ],
        ),
    },
    {
        "title": "Connect Your Icemail Mailboxes to Saleshandy",
        "description": "Step-by-step guide to connecting your Icemail mailboxes to Saleshandy for cold email campaigns.",
        "col_id": EXPORT_INT_COL,
        "col_slug": "mailbox-export-integrations",
        "filename": "connect-your-icemail-mailboxes-to-saleshandy.mdx",
        "body": export_article(
            "Saleshandy", "📨",
            "Connect Icemail to Saleshandy",
            "",
            "SMTP/OAuth",
            [
                "Head to the **Mailbox Dashboard** inside Icemail and select the mailboxes you wish to connect.",
                "Click **\"Export Mailboxes\"** at the top of the dashboard.",
                "Select **\"Saleshandy\"** from the list, or choose **SMTP/IMAP** to retrieve your credentials.",
                "Log in to your **Saleshandy** account and navigate to **Settings → Email Accounts → Add Email Account**.",
                "Choose your connection method:\n\n**Google Workspace**: Select **\"Gmail\"**, then click **\"Connect with Google\"** and sign in with your Icemail Google mailbox. If you have 2-Step Verification enabled, use an App Password.\n\n**Microsoft 365**: Select **\"Outlook\"**, then **\"Connect with Microsoft\"** and authenticate with your Icemail Microsoft mailbox.\n\n**SMTP**: Select **\"Custom\"** and enter:\n- SMTP Host: as provided by Icemail\n- SMTP Port: `587`\n- IMAP Host: as provided by Icemail\n- IMAP Port: `993`\n- Email: your mailbox address\n- Password: your app password or mailbox password",
                "Saleshandy will test and verify the connection. Once confirmed, the mailbox is ready to use in sequences.",
                "Set the **daily email limit** in Saleshandy to align with Icemail's recommended **15 cold emails per day** per mailbox.",
            ],
            [
                "Run cold email sequences with automated follow-ups through Saleshandy",
                "Compatible with all Icemail mailbox types: Google Workspace, Microsoft 365, and SMTP",
                "US IP addresses on all Icemail mailboxes",
                "Saleshandy's email rotation works well with multiple Icemail mailboxes",
                "Track opens, clicks, and replies directly in Saleshandy",
            ],
        ),
    },
    {
        "title": "Connect Your Icemail Mailboxes to Outreach.io",
        "description": "Step-by-step guide to connecting your Icemail Google or Microsoft mailboxes to Outreach.io via OAuth.",
        "col_id": EXPORT_INT_COL,
        "col_slug": "mailbox-export-integrations",
        "filename": "connect-your-icemail-mailboxes-to-outreach-io.mdx",
        "body": """Connecting your Icemail mailboxes to **Outreach.io** enables enterprise-grade sales engagement with your fully provisioned, US-IP Google Workspace and Microsoft 365 mailboxes.

> _Note: Outreach.io connects via **OAuth** (Google or Microsoft sign-in), not direct SMTP credentials. You will need your Icemail mailbox email address and password to complete OAuth authentication._

---

### Step-by-Step: Connect Icemail Mailboxes to Outreach.io

#### **Step 1:**

Go to your **Mailbox Dashboard** in Icemail and locate the mailboxes you want to connect to Outreach.io. Note down the email addresses and ensure you have the passwords available.

#### **Step 2:**

Log in to your **Outreach.io** account.

#### **Step 3:**

Navigate to **Settings → Mailboxes** (or **Your Profile → Email Settings**, depending on your Outreach version).

#### **Step 4:**

Click **"Connect Mailbox"** or **"Add Email Account."**

#### **Step 5:**

Select your mailbox type:

**For Google Workspace mailboxes (from Icemail):**
- Choose **"Google / Gmail"**
- A Google OAuth window will open
- Sign in with your **Icemail Google Workspace email address and password**
- Grant Outreach the requested permissions
- The mailbox will be connected and verified

**For Microsoft 365 mailboxes (from Icemail):**
- Choose **"Microsoft / Outlook"**
- A Microsoft OAuth window will open
- Sign in with your **Icemail Microsoft 365 email address and password**
- Grant Outreach the requested permissions
- The mailbox will be connected and verified

#### **Step 6:**

Once connected, configure your **sending limits** within Outreach. Icemail recommends a maximum of **15 cold emails per day** per mailbox for Google and Microsoft mailboxes.

#### **Step 7:**

Repeat Steps 4–6 for each additional Icemail mailbox you want to connect.

---

### Why Connect Icemail to Outreach.io?

- Fully licensed Google Workspace and Microsoft 365 mailboxes — no gray-area provisioning
- All Icemail mailboxes have US IP addresses for maximum deliverability
- Google Workspace mailboxes: $2.50/mailbox/month | Microsoft 365: $2.50/mailbox/month
- Recommended: 2-3 mailboxes per domain, 15 cold + 15 warmup emails/day per mailbox
- Outreach's sequencing and analytics work seamlessly with Icemail-provisioned mailboxes

---

### Need Help?

Having trouble with the OAuth connection or mailbox verification? Contact our support team anytime at [team@icemail.ai](mailto:team@icemail.ai).

---

### Explore More Integrations

- [Export to Instantly →](#)
- [Export to Smartlead →](#)
- [Export to Salesloft →](#)
- [All Export Guides →](#)

---
""",
    },
    {
        "title": "Connect Your Icemail Mailboxes to Salesloft",
        "description": "Step-by-step guide to connecting your Icemail Google or Microsoft mailboxes to Salesloft via OAuth.",
        "col_id": EXPORT_INT_COL,
        "col_slug": "mailbox-export-integrations",
        "filename": "connect-your-icemail-mailboxes-to-salesloft.mdx",
        "body": """Connecting your Icemail mailboxes to **Salesloft** gives you access to powerful sales engagement cadences powered by your fully provisioned, US-IP Google Workspace and Microsoft 365 mailboxes.

> _Note: Salesloft connects via **OAuth** (Google or Microsoft sign-in). You will need your Icemail mailbox email address and password to complete the OAuth flow._

---

### Step-by-Step: Connect Icemail Mailboxes to Salesloft

#### **Step 1:**

Identify the Icemail mailboxes you want to connect. Log in to your **Icemail dashboard** and note the email addresses and passwords for those mailboxes.

#### **Step 2:**

Log in to your **Salesloft** account.

#### **Step 3:**

Go to **Settings → Connected Accounts** or **Your Profile → Email Settings** (the exact path may vary by Salesloft version).

#### **Step 4:**

Click **"Connect Email"** or **"Add Email Account."**

#### **Step 5:**

Select your mailbox provider:

**For Google Workspace mailboxes (from Icemail):**
- Select **"Google"**
- Complete the Google OAuth flow using your Icemail Google Workspace email address and password
- Grant Salesloft the necessary permissions
- The mailbox will be linked and verified

**For Microsoft 365 mailboxes (from Icemail):**
- Select **"Microsoft"**
- Complete the Microsoft OAuth flow using your Icemail Microsoft 365 email address and password
- Grant Salesloft the necessary permissions
- The mailbox will be linked and verified

#### **Step 6:**

Configure your **daily sending limits** in Salesloft. Icemail recommends **15 cold emails per day** per mailbox (plus 15 warmup emails via your warmup tool).

#### **Step 7:**

Repeat the process for each additional Icemail mailbox you wish to connect.

---

### Why Connect Icemail to Salesloft?

- Official Google Partner — Licensed Google Business Starter mailboxes
- Microsoft 365 Business Starter mailboxes — fully licensed
- US IP addresses on all Icemail mailboxes
- $2.50/mailbox/month for both Google Workspace and Microsoft 365
- Salesloft's cadences, analytics, and dialer integrate seamlessly with Icemail mailboxes
- Recommended: 2-3 mailboxes per domain for maximum deliverability

---

### Need Help?

Having trouble authenticating or connecting your mailboxes? Our team is here to help.

Email us anytime at [team@icemail.ai](mailto:team@icemail.ai)

---

### Explore More Integrations

- [Export to Outreach.io →](#)
- [Export to Instantly →](#)
- [Export to Smartlead →](#)
- [All Export Guides →](#)

---
""",
    },
    {
        "title": "Connect Your Icemail Mailboxes to HubSpot Sales Hub Sequences",
        "description": "Step-by-step guide to connecting your Icemail Google or Microsoft mailboxes to HubSpot Sales Hub for email sequences.",
        "col_id": EXPORT_INT_COL,
        "col_slug": "mailbox-export-integrations",
        "filename": "connect-your-icemail-mailboxes-to-hubspot-sales-hub.mdx",
        "body": """Connecting your Icemail mailboxes to **HubSpot Sales Hub Sequences** lets you run automated email outreach directly through your licensed, US-IP Google Workspace or Microsoft 365 mailboxes.

> _Note: HubSpot connects email accounts via **OAuth** (Google or Microsoft). You will need your Icemail mailbox email address and password to complete the connection._

---

### Step-by-Step: Connect Icemail Mailboxes to HubSpot Sales Hub

#### **Step 1:**

Identify the Icemail mailboxes you want to use for HubSpot sequences. Log in to your **Icemail dashboard** to access the mailbox email addresses and passwords.

#### **Step 2:**

Log in to your **HubSpot** account.

#### **Step 3:**

Navigate to **Settings (gear icon) → General → Email → Connect personal email** (for individual mailboxes) or use the team inbox settings for shared mailboxes.

#### **Step 4:**

Click **"Connect your personal email"** or **"Connect email account."**

#### **Step 5:**

Choose your provider:

**For Google Workspace mailboxes (from Icemail):**
- Click **"Google / Gmail"**
- Sign in with your Icemail Google Workspace email and password via the Google OAuth window
- Grant HubSpot the requested permissions (calendar, email, contacts)
- Your mailbox will be connected

**For Microsoft 365 mailboxes (from Icemail):**
- Click **"Office 365 / Outlook"**
- Sign in with your Icemail Microsoft 365 email and password via the Microsoft OAuth window
- Grant HubSpot the requested permissions
- Your mailbox will be connected

#### **Step 6:**

Once connected, your email address will appear under **Connected Email** in HubSpot. You can now use it in **Sales Hub Sequences** by navigating to **Sales → Sequences** and selecting the mailbox when enrolling contacts.

#### **Step 7:**

Set responsible sending limits. Icemail recommends **15 cold emails per day** per mailbox for Google and Microsoft mailboxes.

---

### Why Connect Icemail to HubSpot Sales Hub?

- Licensed Google Workspace and Microsoft 365 mailboxes — compatible with HubSpot's OAuth requirements
- US IP addresses on all Icemail mailboxes
- $2.50/mailbox/month for both Google and Microsoft mailboxes
- HubSpot Sequences + Icemail infrastructure = a powerful, compliant cold outreach setup
- Recommended: 2-3 Icemail mailboxes per sending domain

---

### Need Help?

Having trouble with OAuth authentication or HubSpot connection? Our support team is ready to assist.

Email us anytime at [team@icemail.ai](mailto:team@icemail.ai)

---

### Explore More Integrations

- [Export to Outreach.io →](#)
- [Export to Salesloft →](#)
- [Export to Instantly →](#)
- [All Export Guides →](#)

---
""",
    },
    {
        "title": "Connect Your Icemail Mailboxes to Hunter.io Campaigns",
        "description": "Step-by-step guide to connecting your Icemail mailboxes to Hunter.io Campaigns via SMTP.",
        "col_id": EXPORT_INT_COL,
        "col_slug": "mailbox-export-integrations",
        "filename": "connect-your-icemail-mailboxes-to-hunter-io.mdx",
        "body": export_article(
            "Hunter.io Campaigns", "🎯",
            "Connect Icemail to Hunter.io",
            "",
            "SMTP",
            [
                "Go to your **Mailbox Dashboard** in Icemail and select the mailboxes you want to connect.",
                "Click **\"Export Mailboxes\"** at the top. Note your mailbox credentials: **email address, SMTP host, SMTP port, IMAP host, IMAP port, and password.**",
                "Log in to your **Hunter.io** account and navigate to **Campaigns → Settings → Email Accounts**.",
                "Click **\"Connect Email Account\"** or **\"Add Email Account.\"**",
                "Select **\"Other / SMTP\"** as the connection type.",
                "Enter your Icemail mailbox credentials:\n\n- **Email Address**: your Icemail mailbox address\n- **SMTP Server**: `smtp.gmail.com` (Google) or `smtp.office365.com` (Microsoft)\n- **SMTP Port**: `587` (TLS)\n- **IMAP Server**: `imap.gmail.com` (Google) or `outlook.office365.com` (Microsoft)\n- **IMAP Port**: `993`\n- **Password**: your mailbox password (use App Password for Google if 2FA is enabled)",
                "Click **\"Save\"** or **\"Verify Connection.\"** Hunter.io will test the SMTP and IMAP connection. Once verified, the mailbox is ready to use in Campaigns.",
                "Configure your **daily sending limit** to 15 emails per day per mailbox as recommended for Google and Microsoft mailboxes.",
            ],
            [
                "Run Hunter.io email campaigns through your Icemail mailboxes",
                "US IP addresses on all Icemail mailboxes for strong deliverability",
                "Compatible with Google Workspace and Microsoft 365 Icemail mailboxes",
                "Combine Hunter.io's prospect finding with Icemail's cold email infrastructure",
                "Scale outreach across multiple mailboxes and domains",
            ],
            "_Tip: For Google Workspace mailboxes, enable 2-Step Verification and generate an App Password in your Google Account settings. Use the App Password instead of your regular account password when connecting via SMTP._"
        ),
    },
    {
        "title": "Connect Your Icemail Mailboxes to PersistIQ",
        "description": "Step-by-step guide to connecting your Icemail mailboxes to PersistIQ for outbound sales campaigns.",
        "col_id": EXPORT_INT_COL,
        "col_slug": "mailbox-export-integrations",
        "filename": "connect-your-icemail-mailboxes-to-persistiq.mdx",
        "body": export_article(
            "PersistIQ", "📊",
            "Connect Icemail to PersistIQ",
            "",
            "SMTP/OAuth",
            [
                "Go to your **Mailbox Dashboard** in Icemail and select the mailboxes you want to connect to PersistIQ.",
                "Click **\"Export Mailboxes\"** to view your credentials (email, SMTP/IMAP details, password).",
                "Log in to your **PersistIQ** account and navigate to **Settings → Email Account**.",
                "Click **\"Add Email Account\"** or **\"Connect Mailbox.\"**",
                "Choose your connection method:\n\n**For Google Workspace mailboxes**: Select **\"Gmail\"** and authenticate via Google OAuth using your Icemail Google mailbox credentials.\n\n**For Microsoft 365 mailboxes**: Select **\"Outlook\"** and authenticate via Microsoft OAuth using your Icemail Microsoft mailbox credentials.\n\n**For SMTP mailboxes**: Select **\"Custom SMTP\"** and enter:\n- SMTP Host: as provided by Icemail\n- SMTP Port: `587`\n- IMAP Host: as provided by Icemail\n- IMAP Port: `993`\n- Username: your mailbox email\n- Password: your mailbox password",
                "Verify the connection. PersistIQ will send a test email to confirm SMTP is working.",
                "Once verified, the mailbox is available for use in PersistIQ campaigns. Set your daily sending limit to **15 cold emails per mailbox per day.**",
            ],
            [
                "Build and run outbound sales campaigns through PersistIQ",
                "Compatible with Google Workspace and Microsoft 365 Icemail mailboxes",
                "US IP addresses on all Icemail mailboxes",
                "PersistIQ's personalization features work with any Icemail mailbox type",
                "Scale campaigns across multiple Icemail mailboxes for higher volume",
            ],
        ),
    },
    {
        "title": "Connect Your Icemail Mailboxes to Overloop (Prospect.io)",
        "description": "Step-by-step guide to connecting your Icemail mailboxes to Overloop (formerly Prospect.io) for cold email campaigns.",
        "col_id": EXPORT_INT_COL,
        "col_slug": "mailbox-export-integrations",
        "filename": "connect-your-icemail-mailboxes-to-overloop.mdx",
        "body": export_article(
            "Overloop (Prospect.io)", "🔄",
            "Connect Icemail to Overloop",
            "",
            "SMTP/OAuth",
            [
                "Go to your **Mailbox Dashboard** in Icemail and select the mailboxes you want to connect.",
                "Click **\"Export Mailboxes\"** at the top. Note down your credentials.",
                "Log in to your **Overloop** account (app.overloop.com) and go to **Settings → Email Accounts**.",
                "Click **\"Add Email Account\"** or **\"Connect Email.\"**",
                "Select your connection method:\n\n**For Google Workspace mailboxes**: Click **\"Gmail\"** and sign in via Google OAuth with your Icemail Google mailbox. Grant the requested permissions.\n\n**For Microsoft 365 mailboxes**: Click **\"Outlook\"** and sign in via Microsoft OAuth with your Icemail Microsoft 365 mailbox.\n\n**For SMTP mailboxes**: Select **\"SMTP\"** and enter:\n- SMTP Host and Port: as provided by Icemail\n- IMAP Host and Port: as provided by Icemail\n- Email address and password",
                "Overloop will verify the connection. Once confirmed, the mailbox will appear as active.",
                "Configure the **daily sending limit** to **15 cold emails per day** per mailbox per Icemail's recommendation.",
                "Create or edit a campaign in Overloop and assign your connected Icemail mailbox as the sending account.",
            ],
            [
                "Run multi-step cold email campaigns through Overloop",
                "US IP addresses on all Icemail mailboxes",
                "Compatible with Google Workspace and Microsoft 365 mailboxes from Icemail",
                "Overloop's automation and CRM features integrate with your Icemail sending infrastructure",
                "Scale safely with 2-3 Icemail mailboxes per domain",
            ],
        ),
    },
    {
        "title": "Connect Your Icemail Mailboxes to Growbots",
        "description": "Step-by-step guide to connecting your Icemail mailboxes to Growbots for outbound sales automation.",
        "col_id": EXPORT_INT_COL,
        "col_slug": "mailbox-export-integrations",
        "filename": "connect-your-icemail-mailboxes-to-growbots.mdx",
        "body": export_article(
            "Growbots", "🤖",
            "Connect Icemail to Growbots",
            "",
            "SMTP/OAuth",
            [
                "Log in to your **Icemail dashboard** and go to the **Mailbox Dashboard**. Select the mailboxes you want to use with Growbots.",
                "Click **\"Export Mailboxes\"** and note your credentials: email address, SMTP/IMAP host, port, and password.",
                "Log in to your **Growbots** account and navigate to **Settings → Email Accounts → Add Account**.",
                "Choose the connection type:\n\n**For Google Workspace mailboxes**: Select **\"Gmail\"** and authenticate with your Icemail Google Workspace credentials via Google OAuth. Use an App Password if 2FA is enabled.\n\n**For Microsoft 365 mailboxes**: Select **\"Outlook / Office 365\"** and authenticate with your Icemail Microsoft 365 credentials via Microsoft OAuth.\n\n**For SMTP mailboxes**: Select **\"SMTP\"** and enter the credentials provided by Icemail.",
                "Growbots will verify the connection. Once verified, the mailbox is ready to use in outbound campaigns.",
                "Set your **daily email sending limit** to **15 cold emails per mailbox per day** as recommended for Google and Microsoft mailboxes.",
            ],
            [
                "Run Growbots outbound campaigns with your Icemail mailboxes",
                "US IP addresses on all Icemail mailboxes for strong inbox placement",
                "Compatible with Google Workspace and Microsoft 365 mailboxes",
                "Growbots' prospecting database + Icemail's deliverability infrastructure is a powerful combination",
                "Recommended: 2-3 mailboxes per domain, using Icemail's warmup recommendations",
            ],
        ),
    },
    {
        "title": "Connect Your Icemail Mailboxes to La Growth Machine",
        "description": "Step-by-step guide to connecting your Icemail mailboxes to La Growth Machine for multichannel outreach.",
        "col_id": EXPORT_INT_COL,
        "col_slug": "mailbox-export-integrations",
        "filename": "connect-your-icemail-mailboxes-to-la-growth-machine.mdx",
        "body": export_article(
            "La Growth Machine", "🚀",
            "Connect Icemail to La Growth Machine",
            "",
            "SMTP/OAuth",
            [
                "Go to your **Mailbox Dashboard** in Icemail and select the mailboxes you want to connect to La Growth Machine.",
                "Click **\"Export Mailboxes\"** to view your credentials.",
                "Log in to your **La Growth Machine** account (lagrowthmachine.com) and go to **Settings → Identities** or **Email Accounts**.",
                "Click **\"Add Email Account\"** or **\"Connect Email Identity.\"**",
                "Select your connection method:\n\n**For Google Workspace mailboxes**: Click **\"Connect with Google\"** and sign in with your Icemail Google Workspace email address and password. Grant La Growth Machine the required permissions.\n\n**For Microsoft 365 mailboxes**: Click **\"Connect with Microsoft\"** and authenticate with your Icemail Microsoft 365 email and password.\n\n**For SMTP mailboxes**: Select **\"Custom SMTP\"** and enter the SMTP/IMAP credentials provided by Icemail.",
                "La Growth Machine will verify the connection. Once confirmed, the mailbox is ready for use in multichannel sequences.",
                "Configure your **daily email volume** within La Growth Machine to match Icemail's recommendation of **15 cold emails per mailbox per day.**",
            ],
            [
                "Run multichannel outreach (email + LinkedIn) through La Growth Machine with your Icemail mailboxes",
                "US IP addresses on all Icemail mailboxes",
                "Compatible with Google Workspace and Microsoft 365 Icemail mailboxes",
                "La Growth Machine's automation pairs well with Icemail's high-deliverability infrastructure",
                "$2.50/mailbox/month for both Google and Microsoft mailboxes",
            ],
        ),
    },
    {
        "title": "Connect Your Icemail Mailboxes to Amplemarket",
        "description": "Step-by-step guide to connecting your Icemail mailboxes to Amplemarket for AI-powered cold outreach.",
        "col_id": EXPORT_INT_COL,
        "col_slug": "mailbox-export-integrations",
        "filename": "connect-your-icemail-mailboxes-to-amplemarket.mdx",
        "body": export_article(
            "Amplemarket", "📈",
            "Connect Icemail to Amplemarket",
            "",
            "SMTP/OAuth",
            [
                "Go to your **Mailbox Dashboard** in Icemail and select the mailboxes you want to connect to Amplemarket.",
                "Click **\"Export Mailboxes\"** at the top of the page and note your credentials.",
                "Log in to your **Amplemarket** account and navigate to **Settings → Email Accounts** or **Sequences → Email Configuration**.",
                "Click **\"Connect Email Account\"** or **\"Add Mailbox.\"**",
                "Choose your connection method:\n\n**For Google Workspace mailboxes**: Select **\"Gmail / Google Workspace\"** and authenticate via Google OAuth. Sign in with your Icemail Google Workspace credentials and grant the required permissions.\n\n**For Microsoft 365 mailboxes**: Select **\"Outlook / Microsoft 365\"** and authenticate via Microsoft OAuth with your Icemail Microsoft credentials.\n\n**For SMTP**: Select **\"SMTP\"** and enter the credentials shown in your Icemail export.",
                "Amplemarket will verify the connection. Once confirmed, the mailbox appears as active.",
                "Set your daily sending limits in Amplemarket to align with Icemail's recommendation: **15 cold emails per mailbox per day**, plus 15 warmup emails.",
            ],
            [
                "Run AI-powered outreach sequences through Amplemarket with your Icemail mailboxes",
                "US IP addresses on all Icemail mailboxes for strong deliverability",
                "Compatible with Google Workspace and Microsoft 365 mailboxes",
                "Amplemarket's AI personalization + Icemail's infrastructure = high-performance cold outreach",
                "Recommended: 2-3 Icemail mailboxes per domain",
            ],
        ),
    },
    {
        "title": "Connect Your Icemail Mailboxes to Outplay",
        "description": "Step-by-step guide to connecting your Icemail mailboxes to Outplay for multi-channel sales engagement.",
        "col_id": EXPORT_INT_COL,
        "col_slug": "mailbox-export-integrations",
        "filename": "connect-your-icemail-mailboxes-to-outplay.mdx",
        "body": export_article(
            "Outplay", "🎯",
            "Connect Icemail to Outplay",
            "",
            "SMTP/OAuth",
            [
                "Log in to your **Icemail dashboard** and navigate to the **Mailbox Dashboard**. Select the mailboxes you want to connect to Outplay.",
                "Click **\"Export Mailboxes\"** and make note of your credentials.",
                "Log in to your **Outplay** account (outplayhq.com) and go to **Settings → Email Accounts → Add Email Account**.",
                "Select your connection type:\n\n**For Google Workspace mailboxes**: Click **\"Connect Gmail\"** and complete the Google OAuth flow using your Icemail Google Workspace email and password.\n\n**For Microsoft 365 mailboxes**: Click **\"Connect Outlook\"** and complete the Microsoft OAuth flow using your Icemail Microsoft 365 credentials.\n\n**For SMTP mailboxes**: Select **\"Custom SMTP\"** and enter the host, port, username, and password provided by Icemail.",
                "Outplay will verify and confirm the connection.",
                "Set your **sending limit** in Outplay to **15 cold emails per mailbox per day** as recommended.",
            ],
            [
                "Run multi-channel sales engagement sequences through Outplay with your Icemail mailboxes",
                "US IP addresses on all Icemail mailboxes",
                "Compatible with Google Workspace and Microsoft 365 mailboxes from Icemail",
                "Outplay's CRM integrations work with all Icemail mailbox types",
                "Scale outreach safely with multiple Icemail mailboxes per campaign",
            ],
        ),
    },
    {
        "title": "Connect Your Icemail Mailboxes to Expandi",
        "description": "Step-by-step guide to connecting your Icemail mailboxes to Expandi for LinkedIn and email outreach.",
        "col_id": EXPORT_INT_COL,
        "col_slug": "mailbox-export-integrations",
        "filename": "connect-your-icemail-mailboxes-to-expandi.mdx",
        "body": export_article(
            "Expandi", "🔗",
            "Connect Icemail to Expandi",
            "",
            "SMTP",
            [
                "Go to your **Mailbox Dashboard** in Icemail and select the mailboxes you want to use with Expandi.",
                "Click **\"Export Mailboxes\"** and collect the credentials: email address, SMTP host, SMTP port, IMAP host, IMAP port, and password.",
                "Log in to your **Expandi** account (expandi.io) and navigate to **Settings → Email Accounts** or **Campaign Settings → Add Email.**",
                "Click **\"Add Email Account\"** and select **\"Custom SMTP / IMAP.\"**",
                "Enter your Icemail credentials:\n\n- **Email Address**: your Icemail mailbox address\n- **SMTP Host**: `smtp.gmail.com` (Google) or `smtp.office365.com` (Microsoft)\n- **SMTP Port**: `587` (TLS)\n- **IMAP Host**: `imap.gmail.com` (Google) or `outlook.office365.com` (Microsoft)\n- **IMAP Port**: `993`\n- **Password**: your mailbox password (use an App Password for Google if 2FA is enabled)",
                "Click **\"Save\"** or **\"Test Connection.\"** Expandi will verify the SMTP/IMAP settings.",
                "Once connected, assign the mailbox to your Expandi email campaigns and configure a **daily sending limit of 15 cold emails per mailbox.**",
            ],
            [
                "Combine Expandi's LinkedIn automation with Icemail email mailboxes for true multichannel outreach",
                "US IP addresses on all Icemail mailboxes",
                "Compatible with Google Workspace and Microsoft 365 Icemail mailboxes",
                "$2.50/mailbox/month for both Google and Microsoft mailboxes",
                "Recommended: 15 cold emails + 15 warmup emails per mailbox per day",
            ],
            "_Tip: For Google Workspace mailboxes, generate an App Password from your Google Account → Security → 2-Step Verification → App Passwords and use that as the password in Expandi._"
        ),
    },
    {
        "title": "Connect Your Icemail Mailboxes to Mixmax",
        "description": "Step-by-step guide to connecting your Icemail Google or Microsoft mailboxes to Mixmax for email sequences and tracking.",
        "col_id": EXPORT_INT_COL,
        "col_slug": "mailbox-export-integrations",
        "filename": "connect-your-icemail-mailboxes-to-mixmax.mdx",
        "body": """Connecting your Icemail mailboxes to **Mixmax** enables powerful email sequencing, scheduling, and tracking—directly through your licensed Google Workspace or Microsoft 365 mailboxes.

> _Note: Mixmax connects via **OAuth** (Google or Microsoft sign-in). You will need your Icemail mailbox email address and password to complete the OAuth flow._

---

### Step-by-Step: Connect Icemail Mailboxes to Mixmax

#### **Step 1:**

Log in to your **Icemail dashboard** and note the email address and password for the mailbox you want to connect to Mixmax.

#### **Step 2:**

Go to **[mixmax.com](https://mixmax.com)** and sign in (or sign up) to your Mixmax account.

#### **Step 3:**

Mixmax connects directly to your email account during sign-in. When prompted to sign in or connect an email account, select your provider:

**For Google Workspace mailboxes (from Icemail):**
- Click **"Sign in with Google"**
- Enter your **Icemail Google Workspace email address**
- Enter your password (or App Password if 2FA is enabled)
- Grant Mixmax the requested Gmail permissions
- Your mailbox is now connected

**For Microsoft 365 mailboxes (from Icemail):**
- Click **"Sign in with Microsoft"**
- Enter your **Icemail Microsoft 365 email address and password**
- Grant Mixmax the requested Outlook permissions
- Your mailbox is now connected

#### **Step 4:**

Once connected, Mixmax will appear as a sidebar or extension in your Gmail or Outlook interface. You can now create **Sequences** under the Mixmax dashboard using your Icemail mailbox.

#### **Step 5:**

Configure your **sending limits** in Mixmax Sequences. Icemail recommends **15 cold emails per mailbox per day** for Google and Microsoft mailboxes.

---

### Why Connect Icemail to Mixmax?

- Fully licensed Google Workspace and Microsoft 365 mailboxes compatible with Mixmax OAuth
- US IP addresses on all Icemail mailboxes
- $2.50/mailbox/month for both Google Workspace and Microsoft 365
- Mixmax sequences, email tracking, and scheduling work seamlessly with Icemail mailboxes
- Recommended: 2-3 mailboxes per domain, 15 cold + 15 warmup emails/day per mailbox

---

### Need Help?

Having trouble connecting your Icemail mailbox to Mixmax? Our team is happy to assist.

Email us anytime at [team@icemail.ai](mailto:team@icemail.ai)

---

### Explore More Integrations

- [Export to Instantly →](#)
- [Export to Smartlead →](#)
- [Export to HubSpot Sales Hub →](#)
- [All Export Guides →](#)

---
""",
    },
    {
        "title": "Connect Your Icemail Mailboxes to Yesware",
        "description": "Step-by-step guide to connecting your Icemail Google or Microsoft mailboxes to Yesware for email tracking and campaigns.",
        "col_id": EXPORT_INT_COL,
        "col_slug": "mailbox-export-integrations",
        "filename": "connect-your-icemail-mailboxes-to-yesware.mdx",
        "body": """Connecting your Icemail mailboxes to **Yesware** gives you powerful email tracking, templates, and campaigns through your licensed Google Workspace or Microsoft 365 mailboxes.

> _Note: Yesware connects via **OAuth** (Google or Microsoft). You will need your Icemail mailbox email address and password to complete authentication._

---

### Step-by-Step: Connect Icemail Mailboxes to Yesware

#### **Step 1:**

Log in to your **Icemail dashboard** and note the email address and password for the mailbox you want to connect.

#### **Step 2:**

Go to **[yesware.com](https://www.yesware.com)** and log in to your Yesware account. Install the Yesware extension in your browser (Chrome or Outlook) if you haven't already.

#### **Step 3:**

Connect your email account:

**For Google Workspace mailboxes (from Icemail):**
- In Yesware, sign in or connect via **"Sign in with Google"**
- Enter your **Icemail Google Workspace email address and password**
- Grant Yesware access to your Gmail account
- Yesware will appear as a panel within your Gmail interface

**For Microsoft 365 mailboxes (from Icemail):**
- Install the **Yesware for Outlook** add-in from the Microsoft AppSource
- Open Outlook with your Icemail Microsoft 365 account
- Authenticate Yesware with your Outlook account when prompted

#### **Step 4:**

Once connected, use Yesware's **Campaigns** feature under the Yesware dashboard to create email sequences. Select your connected Icemail mailbox as the sending account.

#### **Step 5:**

Set your daily sending limit to **15 cold emails per mailbox per day** as recommended by Icemail.

---

### Why Connect Icemail to Yesware?

- Licensed Google Workspace and Microsoft 365 mailboxes fully compatible with Yesware
- US IP addresses on all Icemail mailboxes
- $2.50/mailbox/month for both Google and Microsoft mailboxes
- Yesware's email tracking and templates work seamlessly with Icemail mailboxes
- Recommended: 2-3 mailboxes per domain for sustainable deliverability

---

### Need Help?

Having trouble connecting your Icemail mailbox to Yesware? We're here to help.

Email us anytime at [team@icemail.ai](mailto:team@icemail.ai)

---

### Explore More Integrations

- [Export to Instantly →](#)
- [Export to Smartlead →](#)
- [Export to Mixmax →](#)
- [All Export Guides →](#)

---
""",
    },
    {
        "title": "Connect Your Icemail Mailboxes to Close CRM",
        "description": "Step-by-step guide to connecting your Icemail mailboxes to Close CRM for email sequences and sales outreach.",
        "col_id": EXPORT_INT_COL,
        "col_slug": "mailbox-export-integrations",
        "filename": "connect-your-icemail-mailboxes-to-close-crm.mdx",
        "body": export_article(
            "Close CRM", "🔒",
            "Connect Icemail to Close CRM",
            "",
            "SMTP/IMAP",
            [
                "Go to your **Mailbox Dashboard** in Icemail and select the mailboxes you want to connect to Close CRM.",
                "Click **\"Export Mailboxes\"** and note your credentials: email address, SMTP host, SMTP port, IMAP host, IMAP port, and password.",
                "Log in to your **Close CRM** account (close.com) and navigate to **Settings → Your Account → Email & Calendar**.",
                "Click **\"Connect Email\"** or **\"Add Email Account.\"**",
                "Choose your connection method:\n\n**For Google Workspace mailboxes**: Select **\"Gmail\"** and authenticate via Google OAuth using your Icemail Google Workspace credentials. If 2FA is enabled, use an App Password.\n\n**For Microsoft 365 mailboxes**: Select **\"Microsoft / Outlook\"** and authenticate via Microsoft OAuth using your Icemail Microsoft 365 credentials.\n\n**For SMTP mailboxes**: Select **\"Custom SMTP / IMAP\"** and enter:\n- SMTP Host and Port: as provided by Icemail\n- IMAP Host and Port: as provided by Icemail\n- Email address and password",
                "Close CRM will verify the SMTP/IMAP connection or OAuth authentication. Once confirmed, the mailbox is connected.",
                "Navigate to **Sequences** in Close CRM and assign your Icemail mailbox as the sending account for your outreach sequences. Set the daily email limit to **15 cold emails per mailbox per day.**",
            ],
            [
                "Run email sequences and outbound sales directly through Close CRM with your Icemail mailboxes",
                "US IP addresses on all Icemail mailboxes",
                "Compatible with Google Workspace and Microsoft 365 mailboxes from Icemail",
                "Close CRM's built-in dialer and sequences integrate seamlessly with Icemail's email infrastructure",
                "$2.50/mailbox/month for both Google Workspace and Microsoft 365",
            ],
        ),
    },
    {
        "title": "Connect Your Icemail Mailboxes to Pipedrive Sales Email Sequences",
        "description": "Step-by-step guide to connecting your Icemail mailboxes to Pipedrive for email syncing and sales engagement.",
        "col_id": EXPORT_INT_COL,
        "col_slug": "mailbox-export-integrations",
        "filename": "connect-your-icemail-mailboxes-to-pipedrive.mdx",
        "body": """Connecting your Icemail mailboxes to **Pipedrive** allows you to sync your cold email activity with your CRM pipeline and use Pipedrive's email and campaigns features with your licensed, US-IP mailboxes.

> _Note: Pipedrive connects email accounts via **OAuth** (Google or Microsoft) or via **SMTP/IMAP** for custom mail servers._

---

### Step-by-Step: Connect Icemail Mailboxes to Pipedrive

#### **Step 1:**

Go to your **Mailbox Dashboard** in Icemail and select the mailboxes you want to connect to Pipedrive. Note your email address and password.

#### **Step 2:**

Log in to your **Pipedrive** account and go to **Personal Preferences (your avatar) → Personal → Email → Add new email account**, or navigate via **Settings → Email Sync**.

#### **Step 3:**

Click **"Add Email Account"** or **"Connect Email."**

#### **Step 4:**

Select your connection method:

**For Google Workspace mailboxes (from Icemail):**
- Click **"Google"**
- Sign in with your Icemail Google Workspace email and password via Google OAuth
- Grant Pipedrive the requested permissions
- Your mailbox will be synced to Pipedrive

**For Microsoft 365 mailboxes (from Icemail):**
- Click **"Microsoft"**
- Sign in with your Icemail Microsoft 365 email and password via Microsoft OAuth
- Grant Pipedrive the requested permissions
- Your mailbox will be synced to Pipedrive

**For SMTP mailboxes (from Icemail):**
- Click **"Other"** or **"Custom SMTP/IMAP"**
- Enter:
  - SMTP Host and Port: as provided by Icemail
  - IMAP Host and Port: as provided by Icemail
  - Email address and password

#### **Step 5:**

Once connected, your Icemail mailbox emails will sync with Pipedrive. You can send emails, track opens and clicks, and use **Pipedrive Campaigns** directly from your connected mailbox.

#### **Step 6:**

If using Pipedrive Campaigns (email sequence feature), navigate to **Campaigns → Email Campaigns** and select your Icemail mailbox as the sending account. Set your daily limit to **15 cold emails per mailbox per day.**

---

### Why Connect Icemail to Pipedrive?

- Sync your cold email outreach directly with your Pipedrive CRM pipeline
- Licensed Google Workspace and Microsoft 365 mailboxes — compatible with Pipedrive's OAuth requirements
- US IP addresses on all Icemail mailboxes
- $2.50/mailbox/month for both Google and Microsoft mailboxes
- Recommended: 2-3 mailboxes per domain, 15 cold + 15 warmup emails/day per mailbox
- Track all email activity against deals and contacts in Pipedrive

---

### Need Help?

Having trouble connecting your Icemail mailbox to Pipedrive? Our support team is ready to assist.

Email us anytime at [team@icemail.ai](mailto:team@icemail.ai)

---

### Explore More Integrations

- [Export to Close CRM →](#)
- [Export to Outreach.io →](#)
- [Export to Salesloft →](#)
- [All Export Guides →](#)

---
""",
    },
]

# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Creating {len(ARTICLES)} articles in Gleap...\n")
    results = []

    for article in ARTICLES:
        try:
            gleap_id = create_and_push(
                title=article["title"],
                description=article["description"],
                col_id=article["col_id"],
                col_slug=article["col_slug"],
                md_body=article["body"],
                filename=article["filename"],
            )
            results.append({"title": article["title"], "id": gleap_id, "status": "OK"})
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({"title": article["title"], "id": None, "status": f"ERROR: {e}"})

    print("\n\n=== Summary ===")
    for r in results:
        status = "✓" if r["id"] else "✗"
        print(f"  {status} {r['title'][:70]} → {r['id'] or r['status']}")
