#!/usr/bin/env python3
"""
Gleap Help Center sync tool for icemail.ai.

Usage:
  python gleap_sync.py pull            # Download all articles from Gleap → repo
  python gleap_sync.py push            # Upload changed articles from repo → Gleap
  python gleap_sync.py push --dry-run  # Show what would be pushed without sending
  python gleap_sync.py status          # Show which articles differ from Gleap

Environment variables (or edit DEFAULTS below):
  GLEAP_TOKEN   — Bearer token
  GLEAP_PROJECT — Project ID
"""

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from pathlib import Path

import urllib.request
import urllib.error

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
        raise RuntimeError(f"{method} {path} → {e.code}: {e.read().decode()[:300]}")

def get(path):    return _request("GET", path)
def put(path, b): return _request("PUT", path, b)
def post(path, b): return _request("POST", path, b)
def delete(path): return _request("DELETE", path)

# ── TipTap JSON → Markdown ────────────────────────────────────────────────────

def _inline_text(node):
    """Render a text node with its marks to Markdown."""
    text = node.get("text", "")
    marks = node.get("marks", [])
    link_href = None
    is_bold = is_italic = is_code = False
    for m in marks:
        t = m.get("type")
        if t == "bold":
            is_bold = True
        elif t == "italic":
            is_italic = True
        elif t == "code":
            is_code = True
        elif t == "link":
            link_href = m.get("attrs", {}).get("href", "")
    if is_code:
        text = f"`{text}`"
    else:
        if is_bold:
            text = f"**{text}**"
        if is_italic:
            text = f"_{text}_"
    if link_href:
        text = f"[{text}]({link_href})"
    return text

def _render_inline(content_list):
    """Render an array of inline nodes to a Markdown string."""
    parts = []
    for node in (content_list or []):
        ntype = node.get("type")
        if ntype == "text":
            parts.append(_inline_text(node))
        elif ntype == "emoji":
            parts.append(node.get("attrs", {}).get("emoji", ""))
        elif ntype == "hardBreak":
            parts.append("  \n")
        else:
            # Unknown inline — try to render its children
            parts.append(_render_inline(node.get("content", [])))
    return "".join(parts)

def tiptap_to_markdown(doc):
    """Convert a TipTap doc node to Markdown string."""
    lines = []

    def render_node(node, list_depth=0, ordered=False, item_idx=1):
        ntype = node.get("type")

        if ntype == "paragraph":
            inner = _render_inline(node.get("content", []))
            lines.append(inner)
            lines.append("")

        elif ntype == "heading":
            level = node.get("attrs", {}).get("level", 2)
            inner = _render_inline(node.get("content", []))
            lines.append(f"{'#' * level} {inner}")
            lines.append("")

        elif ntype == "horizontalRule":
            lines.append("---")
            lines.append("")

        elif ntype == "bulletList":
            for child in node.get("content", []):
                render_node(child, list_depth=list_depth, ordered=False)
            if list_depth == 0:
                lines.append("")

        elif ntype == "orderedList":
            for idx, child in enumerate(node.get("content", []), start=1):
                render_node(child, list_depth=list_depth, ordered=True, item_idx=idx)
            if list_depth == 0:
                lines.append("")

        elif ntype == "listItem":
            prefix = "  " * list_depth + ("1." if ordered else "-")
            # First child is usually a paragraph; rest are nested lists
            children = node.get("content", [])
            if children:
                first = children[0]
                if first.get("type") == "paragraph":
                    inner = _render_inline(first.get("content", []))
                    lines.append(f"{prefix} {inner}")
                    for sub in children[1:]:
                        render_node(sub, list_depth=list_depth + 1)
                else:
                    lines.append(f"{prefix}")
                    for sub in children:
                        render_node(sub, list_depth=list_depth + 1)

        elif ntype == "codeBlock":
            lang = node.get("attrs", {}).get("language", "")
            inner = _render_inline(node.get("content", []))
            lines.append(f"```{lang}")
            lines.append(inner)
            lines.append("```")
            lines.append("")

        elif ntype == "blockquote":
            for child in node.get("content", []):
                # Temporarily collect, then prefix with >
                sub_lines = []
                orig = lines[:]
                render_node(child)
                new = lines[len(orig):]
                del lines[len(orig):]
                for l in new:
                    lines.append(f"> {l}" if l else ">")

        elif ntype == "image":
            attrs = node.get("attrs", {})
            src = attrs.get("src", "")
            alt = attrs.get("alt", "")
            lines.append(f"![{alt}]({src})")
            lines.append("")

        elif ntype == "doc":
            for child in node.get("content", []):
                render_node(child)

        else:
            # Fallback: render any content children
            for child in node.get("content", []):
                render_node(child)

    render_node(doc)

    # Clean up: collapse 3+ consecutive blank lines to 2
    result = "\n".join(lines)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()

# ── Markdown → TipTap JSON ────────────────────────────────────────────────────

def _new_id():
    return str(uuid.uuid4())

def _parse_inline(text):
    """Parse inline Markdown into TipTap inline nodes."""
    nodes = []
    # Pattern order matters: code > bold+italic > bold > italic > link > plain
    pattern = re.compile(
        r"(`[^`]+`)"                       # code
        r"|(\*\*\*[^*]+\*\*\*)"           # bold+italic
        r"|(\*\*[^*]+\*\*)"               # bold
        r"|(\*[^*]+\*|_[^_]+_)"           # italic
        r"|(\[([^\]]+)\]\(([^)]+)\))"     # link
    )
    pos = 0
    for m in pattern.finditer(text):
        # Plain text before match
        if m.start() > pos:
            nodes.append({"type": "text", "text": text[pos:m.start()]})
        pos = m.end()

        if m.group(1):  # code
            inner = m.group(1)[1:-1]
            nodes.append({"type": "text", "marks": [{"type": "code"}], "text": inner})
        elif m.group(2):  # bold+italic
            inner = m.group(2)[3:-3]
            nodes.append({"type": "text", "marks": [{"type": "bold"}, {"type": "italic"}], "text": inner})
        elif m.group(3):  # bold
            inner = m.group(3)[2:-2]
            nodes.append({"type": "text", "marks": [{"type": "bold"}], "text": inner})
        elif m.group(4):  # italic
            inner = m.group(4)[1:-1]
            nodes.append({"type": "text", "marks": [{"type": "italic"}], "text": inner})
        elif m.group(5):  # link
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
    """Convert Markdown string to a TipTap doc node."""
    lines = md_text.split("\n")
    content = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]

        # Heading
        hm = re.match(r"^(#{1,6})\s+(.*)", line)
        if hm:
            level = len(hm.group(1))
            content.append(_heading(level, _parse_inline(hm.group(2))))
            i += 1
            continue

        # Horizontal rule
        if re.match(r"^---+\s*$", line):
            content.append({"type": "horizontalRule"})
            i += 1
            continue

        # Fenced code block
        if line.startswith("```"):
            lang = line[3:].strip()
            code_lines = []
            i += 1
            while i < n and not lines[i].startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing ```
            code_text = "\n".join(code_lines)
            content.append({
                "type": "codeBlock",
                "attrs": {"language": lang or None},
                "content": [{"type": "text", "text": code_text}],
            })
            continue

        # Unordered list
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

        # Ordered list
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

        # Blockquote
        if line.startswith("> "):
            bq_lines = []
            while i < n and lines[i].startswith("> "):
                bq_lines.append(lines[i][2:])
                i += 1
            inner_doc = markdown_to_tiptap("\n".join(bq_lines))
            content.append({"type": "blockquote", "content": inner_doc.get("content", [])})
            continue

        # Blank line
        if line.strip() == "":
            i += 1
            continue

        # Paragraph: collect non-blank lines
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
    """Extract plain text from a TipTap doc for the plainContent field."""
    parts = []

    def walk(node):
        t = node.get("type")
        if t == "text":
            parts.append(node.get("text", ""))
        elif t == "emoji":
            parts.append(node.get("attrs", {}).get("emoji", ""))
        elif t == "hardBreak":
            parts.append("\n")
        else:
            for child in node.get("content", []):
                walk(child)
            if t in ("paragraph", "heading", "listItem", "codeBlock", "blockquote"):
                parts.append("\n")

    walk(doc)
    return "".join(parts).strip()

# ── .mdx file helpers ─────────────────────────────────────────────────────────

def _slugify(text):
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_]+", "-", text.strip())
    return text[:60]

def _collection_dir(col):
    slug = _slugify(col["title"].get("en", col["id"]))
    return GLEAP_DIR / slug

def _article_path(col, article):
    col_dir = _collection_dir(col)
    slug = _slugify(article["title"].get("en", article["id"]))
    return col_dir / f"{slug}.mdx"

def _content_hash(md_body):
    return hashlib.md5(md_body.encode()).hexdigest()[:8]

def write_mdx(path, article, md_body, col_id, col_slug):
    path.parent.mkdir(parents=True, exist_ok=True)
    title = article.get("title", {}).get("en", "")
    description = article.get("description", {}).get("en", "")
    gleap_id = article.get("id", article.get("_id", ""))
    is_draft = article.get("isDraft", False)
    frontmatter = {
        "title": title,
        "description": description,
        "gleap_id": gleap_id,
        "gleap_collection": col_id,
        "gleap_collection_slug": col_slug,
        "isDraft": is_draft,
        "content_hash": _content_hash(md_body),
    }
    fm_lines = ["---"]
    for k, v in frontmatter.items():
        if isinstance(v, str):
            # Escape quotes
            escaped = v.replace('"', '\\"')
            fm_lines.append(f'{k}: "{escaped}"')
        else:
            fm_lines.append(f"{k}: {json.dumps(v)}")
    fm_lines.append("---")
    fm_lines.append("")
    path.write_text("\n".join(fm_lines) + "\n" + md_body + "\n")

def read_mdx(path):
    """Return (frontmatter dict, markdown body)."""
    text = path.read_text()
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    fm_text = parts[1].strip()
    body = parts[2].strip()
    fm = {}
    for line in fm_text.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            v = v.strip().strip('"')
            if v.lower() == "true":
                v = True
            elif v.lower() == "false":
                v = False
            fm[k.strip()] = v
    return fm, body

# ── Pull ──────────────────────────────────────────────────────────────────────

def pull():
    print("Pulling from Gleap…")
    collections = get("/v3/helpcenter/collections")
    summary = {"collections": len(collections), "articles": 0, "files": 0}

    # Write collections index
    GLEAP_DIR.mkdir(exist_ok=True)
    col_index = []

    for col in collections:
        col_id = col["id"]
        col_slug = _slugify(col["title"].get("en", col_id))
        col_dir = GLEAP_DIR / col_slug
        col_dir.mkdir(exist_ok=True)
        col_index.append({"id": col_id, "slug": col_slug, "title": col["title"],
                           "description": col.get("description", {}),
                           "iconUrl": col.get("iconUrl", "")})

        print(f"  Collection: {col['title'].get('en', col_id)}")
        articles = get(f"/v3/helpcenter/collections/{col_id}/articles")
        summary["articles"] += len(articles)

        for article in articles:
            art_id = article.get("id", article.get("_id", ""))
            # Fetch full article (list endpoint returns partial data)
            full = get(f"/v3/helpcenter/collections/{col_id}/articles/{art_id}")
            content_doc = full.get("content", {}).get("en", {"type": "doc", "content": []})
            md_body = tiptap_to_markdown(content_doc)
            path = _article_path(col, full)
            write_mdx(path, full, md_body, col_id, col_slug)
            print(f"    ✓ {path.name}")
            summary["files"] += 1

    # Write collections index JSON
    idx_path = GLEAP_DIR / "collections.json"
    idx_path.write_text(json.dumps(col_index, indent=2, ensure_ascii=False))
    print(f"\nDone. {summary['collections']} collections, {summary['articles']} articles → {summary['files']} files")
    print(f"Index: {idx_path}")

# ── Push ──────────────────────────────────────────────────────────────────────

def push(dry_run=False):
    mode = "[DRY RUN] " if dry_run else ""
    print(f"{mode}Pushing to Gleap…")

    mdx_files = list(GLEAP_DIR.rglob("*.mdx"))
    if not mdx_files:
        print("No .mdx files found in gleap/. Run 'pull' first.")
        return

    updated = skipped = created = 0

    for path in sorted(mdx_files):
        fm, body = read_mdx(path)
        gleap_id = fm.get("gleap_id", "")
        col_id = fm.get("gleap_collection", "")
        title = fm.get("title", "")
        description = fm.get("description", "")
        is_draft = fm.get("isDraft", False)
        stored_hash = fm.get("content_hash", "")
        current_hash = _content_hash(body)

        if not gleap_id or not col_id:
            print(f"  SKIP {path.name} (missing gleap_id or gleap_collection)")
            skipped += 1
            continue

        # Check if content changed vs stored hash
        if stored_hash == current_hash:
            # No change in markdown body
            skipped += 1
            continue

        tiptap_doc = markdown_to_tiptap(body)
        plain = _tiptap_plain_text(tiptap_doc)

        payload = {
            "title": {"en": title},
            "description": {"en": description},
            "content": {"en": tiptap_doc},
            "plainContent": {"en": plain},
            "isDraft": is_draft,
        }

        print(f"  {mode}→ {path.name} ({title[:50]})")
        if not dry_run:
            result = put(f"/v3/helpcenter/collections/{col_id}/articles/{gleap_id}", payload)
            # Update hash in file after successful push
            fm["content_hash"] = current_hash
            write_mdx(path, {"title": {"en": title}, "description": {"en": description},
                              "id": gleap_id, "isDraft": is_draft}, body, col_id,
                      fm.get("gleap_collection_slug", ""))
        updated += 1

    print(f"\n{mode}Done. {updated} updated, {skipped} unchanged/skipped.")

# ── Status ─────────────────────────────────────────────────────────────────────

def status():
    mdx_files = list(GLEAP_DIR.rglob("*.mdx"))
    if not mdx_files:
        print("No .mdx files found in gleap/. Run 'pull' first.")
        return
    changed = []
    for path in sorted(mdx_files):
        fm, body = read_mdx(path)
        stored_hash = fm.get("content_hash", "")
        current_hash = _content_hash(body)
        if stored_hash != current_hash:
            changed.append(path)

    if changed:
        print(f"Modified ({len(changed)} files):")
        for p in changed:
            fm, _ = read_mdx(p)
            print(f"  M  {p.relative_to(GLEAP_DIR.parent)}  ({fm.get('title', '')})")
    else:
        print("All files match Gleap. Nothing to push.")

# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Gleap Help Center sync")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("pull", help="Download all articles from Gleap into gleap/")
    push_p = sub.add_parser("push", help="Upload changed articles from gleap/ to Gleap")
    push_p.add_argument("--dry-run", action="store_true", help="Preview changes without sending")
    sub.add_parser("status", help="Show which files differ from Gleap")
    args = parser.parse_args()

    if args.cmd == "pull":
        pull()
    elif args.cmd == "push":
        push(dry_run=args.dry_run)
    elif args.cmd == "status":
        status()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
