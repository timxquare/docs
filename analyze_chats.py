#!/usr/bin/env python3
"""
Analyze Gleap support chats from last 1 year.
Finds top 30 most asked questions, samples agent answers, and writes analysis to JSON.

Usage: python3 analyze_chats.py
Output: chat_analysis.json
"""

import json
import os
import re
import time
import urllib.request
import urllib.error
from collections import defaultdict, Counter
from pathlib import Path

TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpZCI6IjZhMmY4YjQ3ODYyODU5OWNlNWRjODE0OSIsInByb2plY3RJZCI6IjY4MzVjYzRkYTVkM2E0YjhlNGM4ZTI3NCIsInNlY3JldEFwaUtleSI6IjBoc1RKTmZDeUE0UTBLTEtad3FnZjAydzNIRThqUFVmIiwidXNlclR5cGUiOiJzZXJ2aWNlX2FjY291bnQiLCJpYXQiOjE3ODE1MDA3NDN9"
    ".lyJC8-8g8t106JRjPUU3dDB9t222k9C7HgW0xYoxL80"
)
PROJECT = "6835cc4da5d3a4b8e4c8e274"
API = "https://api.gleap.io"


def api_get(path, retries=3):
    url = f"{API}{path}"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "Authorization": f"Bearer {TOKEN}",
                "project": PROJECT,
            })
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def extract_text_from_tiptap(content):
    """Recursively extract plain text from TipTap/ProseMirror JSON."""
    if not content:
        return ""
    texts = []
    if isinstance(content, dict):
        if content.get("type") == "text":
            texts.append(content.get("text", ""))
        for child in content.get("content", []) or []:
            texts.append(extract_text_from_tiptap(child))
    elif isinstance(content, list):
        for item in content:
            texts.append(extract_text_from_tiptap(item))
    return " ".join(t for t in texts if t)


def get_all_tickets():
    """Fetch all tickets, return list filtered to last 1 year."""
    print("Fetching all tickets...")
    all_tickets = []
    skip = 0
    limit = 100
    total = None

    while True:
        try:
            d = api_get(f"/v3/tickets?limit={limit}&skip={skip}")
        except Exception as e:
            print(f"  Error at skip={skip}: {e}")
            break

        tickets = d.get("tickets", [])
        if total is None:
            total = d.get("totalCount", 0)
            print(f"  Total tickets: {total}")

        all_tickets.extend(tickets)
        print(f"  Fetched {len(all_tickets)}/{total}...", end="\r")

        if len(tickets) < limit:
            break
        skip += limit
        time.sleep(0.1)  # be gentle with the API

    print(f"\n  Done. Got {len(all_tickets)} tickets.")

    # Filter to last 1 year
    from datetime import datetime, timezone, timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=365)
    filtered = []
    for t in all_tickets:
        created = t.get("createdAt", "")
        if created:
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                if dt >= cutoff:
                    filtered.append(t)
            except Exception:
                filtered.append(t)
        else:
            filtered.append(t)

    print(f"  After 1-year filter: {len(filtered)} tickets.")
    return filtered


def get_ticket_messages(ticket_id):
    """Fetch all messages for a ticket."""
    try:
        msgs = api_get(f"/v3/messages?ticket={ticket_id}")
        return msgs if isinstance(msgs, list) else []
    except Exception:
        return []


def parse_conversation(messages):
    """
    Parse messages into customer questions and agent answers.
    Returns list of (role, text) tuples.
    """
    turns = []
    for m in messages:
        mtype = m.get("type", "")
        bot = m.get("bot", False)
        user = m.get("user") or {}

        # Determine role
        if bot or mtype in ("SYSTEM_MESSAGE", "BOT", "BOT_REPLY", "FEEDBACK_UPDATED"):
            role = "bot"
        elif mtype == "SHARED_COMMENT":
            role = "customer"
        elif mtype == "TEXT":
            role = "agent"
        else:
            role = "other"

        # Extract text
        data = m.get("data") or {}
        content = data.get("content") or {}
        text = extract_text_from_tiptap(content)
        if not text:
            # Fallback to other data fields
            for key in ["text", "plainText", "message", "body"]:
                if data.get(key):
                    text = str(data[key])
                    break

        text = text.strip()
        if text and role != "bot" and role != "other":
            turns.append({"role": role, "text": text[:1000]})

    return turns


def normalize_topic(title):
    """Normalize a title to a topic cluster key."""
    if not title:
        return None
    t = title.lower()
    # Remove common prefixes
    t = re.sub(r'^(re:|fw:|fwd:|urgent:?|request:?)\s*', '', t)
    t = re.sub(r'[^\w\s]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


# Topic cluster keywords
TOPIC_CLUSTERS = {
    "mailbox_provisioning": [
        "mailbox not", "mailbox creat", "provision", "creat mailbox", "creat email",
        "adding mailbox", "new mailbox", "mailbox setup", "set up mailbox",
        "mailbox pending", "mailbox active", "mailbox not active"
    ],
    "microsoft_provisioning": [
        "microsoft", "ms365", "office 365", "office365", "m365", "microsoft mailbox",
        "microsoft provision", "azure mailbox"
    ],
    "smtp_errors": [
        "smtp", "smtp error", "smtp disconnect", "smtp fail", "authentication fail",
        "app password", "invalid password", "password error", "smtp setting"
    ],
    "dns_setup": [
        "dns", "spf", "dkim", "dmarc", "dns record", "cname", "txt record",
        "dns verification", "dns propagat", "mx record"
    ],
    "domain_connection": [
        "connect domain", "domain connect", "link domain", "add domain", "domain verif",
        "domain not verif", "domain setup", "nameserver"
    ],
    "domain_purchase": [
        "buy domain", "purchase domain", "domain purchas", "new domain", "domain buy"
    ],
    "billing_payment": [
        "payment", "billing", "invoice", "refund", "charge", "wallet", "credit",
        "pay", "subscription", "renew", "plan"
    ],
    "mailbox_export": [
        "export", "connect to instantly", "connect to smartlead", "connect to reachinbox",
        "instantly", "smartlead", "lemlist", "reply.io", "woodpecker", "export mailbox",
        "integrate", "integration", "third party"
    ],
    "deliverability": [
        "deliverability", "spam", "inbox placement", "land in spam", "inbox", "bounce",
        "blacklist", "reputation", "email reputation", "sender reputation", "warmup",
        "warm up", "warming"
    ],
    "sending_limits": [
        "send limit", "daily limit", "email per day", "sending limit", "how many email",
        "15 email", "max email", "email volume"
    ],
    "domain_forwarding": [
        "domain forward", "redirect", "forward domain", "url redirect", "301 redirect"
    ],
    "tracking_domain": [
        "tracking domain", "custom tracking", "track link", "link tracking", "open tracking"
    ],
    "bulk_mailbox": [
        "bulk mailbox", "bulk create", "csv", "bulk upload", "mass creat",
        "multiple mailbox", "many mailbox"
    ],
    "delete_cancel": [
        "delet mailbox", "cancel", "remov mailbox", "cancel subscription", "cancel plan"
    ],
    "pricing": [
        "pric", "cost", "how much", "pricing", "2.5", "$2.5", "per mailbox"
    ],
    "google_workspace": [
        "google workspace", "google mailbox", "gmail", "google admin", "google account",
        "google login", "google setup"
    ],
    "domain_renewal": [
        "renew domain", "domain expir", "domain renewal", "domain expir"
    ],
    "team_access": [
        "team", "workspace", "member", "invite", "access", "admin", "user manag"
    ],
    "mailbox_error": [
        "error", "not working", "broken", "fail", "issue", "problem", "bug",
        "disconnect", "connection lost"
    ],
    "mailbox_reachinbox": [
        "reachinbox", "reach inbox"
    ],
    "custom_domain": [
        "custom domain", "own domain", "existing domain", "personal domain"
    ],
    "mailbox_login": [
        "login", "log in", "sign in", "access mailbox", "manual login", "credential"
    ],
    "mailbox_forwarding": [
        "email forward", "forward email", "catch all", "catch-all"
    ],
    "bulk_domain": [
        "bulk domain", "many domain", "multiple domain", "domain bulk"
    ],
    "white_label": [
        "white label", "whitelabel", "rebrand", "agency"
    ],
    "pre_warmed": [
        "pre.warm", "prewarm", "warmed", "warm mailbox", "pre-warm"
    ],
    "high_reputation": [
        "high reputation", "reputation domain", "aged domain", "established domain"
    ],
    "general_support": [
        "help", "support", "agent", "human", "talk to", "speak to"
    ],
    "account_setup": [
        "sign up", "account creat", "getting start", "onboard", "first step"
    ],
    "mailbox_schedule": [
        "schedul mailbox", "schedule", "timed", "delay mailbox"
    ]
}


def classify_ticket(title, summary=""):
    """Classify a ticket into a topic cluster."""
    text = (normalize_topic(title) or "") + " " + (normalize_topic(summary) or "")

    scores = defaultdict(int)
    for cluster, keywords in TOPIC_CLUSTERS.items():
        for kw in keywords:
            if kw in text:
                scores[cluster] += 1

    if scores:
        return max(scores, key=scores.get)
    return "other"


def check_customer_acceptance(turns):
    """
    Heuristic: did the customer seem satisfied?
    Look for positive signals in the last customer message.
    """
    positive_words = {"thank", "thanks", "great", "perfect", "ok", "okay", "got it",
                      "understood", "amazing", "awesome", "helpful", "resolve", "sorted",
                      "fixed", "done", "good", "excellent", "appreciate", "yes", "sure"}

    # Get last customer message
    customer_msgs = [t for t in turns if t["role"] == "customer"]
    if not customer_msgs:
        return "no_customer_msg"

    last_msg = customer_msgs[-1]["text"].lower()
    for word in positive_words:
        if word in last_msg:
            return "accepted"

    return "unclear"


def main():
    # 1. Fetch all tickets
    tickets = get_all_tickets()

    # 2. Classify each ticket
    print("\nClassifying tickets by topic...")
    clustered = defaultdict(list)

    for t in tickets:
        title = t.get("title", "") or ""
        summary = t.get("aiSummary", "") or ""
        topic = classify_ticket(title, summary)
        clustered[topic].append(t)

    # 3. Sort by frequency
    sorted_topics = sorted(clustered.items(), key=lambda x: len(x[1]), reverse=True)

    print("\n=== Topic Distribution ===")
    for topic, t_list in sorted_topics[:35]:
        print(f"  {topic}: {len(t_list)} tickets")

    # 4. For top 30 topics, sample conversations with agent replies
    print("\nSampling conversations for top 30 topics...")

    results = []
    for topic, t_list in sorted_topics[:30]:
        # Find tickets with agent replies
        with_replies = [t for t in t_list if t.get("hasAgentReply")]
        sample_tickets = with_replies[:3] if with_replies else t_list[:2]

        sample_conversations = []
        for ticket in sample_tickets:
            ticket_id = ticket.get("id") or ticket.get("_id", "")
            if not ticket_id:
                continue

            print(f"  Getting messages for {ticket_id[:8]}... ({topic})")
            messages = get_ticket_messages(ticket_id)
            turns = parse_conversation(messages)

            # Get customer questions
            customer_msgs = [t["text"] for t in turns if t["role"] == "customer"]
            agent_msgs = [t["text"] for t in turns if t["role"] == "agent"]
            acceptance = check_customer_acceptance(turns)

            sample_conversations.append({
                "ticket_id": ticket_id,
                "title": ticket.get("title", ""),
                "status": ticket.get("status", ""),
                "conversationClosed": ticket.get("conversationClosed", False),
                "customer_questions": customer_msgs[:5],
                "agent_answers": agent_msgs[:5],
                "customer_accepted": acceptance,
            })
            time.sleep(0.15)

        results.append({
            "rank": len(results) + 1,
            "topic": topic,
            "count": len(t_list),
            "sample_titles": [t.get("title", "") for t in t_list if t.get("title")][:5],
            "conversations": sample_conversations,
        })

    # 5. Save to JSON
    output_path = Path(__file__).parent / "chat_analysis.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n✅ Analysis complete. Saved to {output_path}")
    print(f"   Top 30 topics analyzed. {sum(r['count'] for r in results)} tickets covered.")

    return results


if __name__ == "__main__":
    main()
