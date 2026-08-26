#!/usr/bin/env python3
"""
restore_md_sources.py — Backfill content/morning-analysis/*.md from per-date HTML.

Discovered 2026-08-26: All prior MD source files were 0 bytes — the lobster
pipeline / STEP 2 of the morning cron had been writing empty files for weeks.
The per-date HTML files in website/commentary/YYYY-MM-DD/ were always populated
and shipped to production, so this script extracts the body content from each
HTML and writes it back as a clean MD source for the corresponding date.

Idempotent: skips MD files that already have content. Only backfills empty ones.
"""

import os
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEBSITE_DIR = ROOT / "website"
COMMENTARY_DIR = WEBSITE_DIR / "commentary"
MD_DIR = ROOT / "content" / "morning-analysis"


def html_to_md(html: str) -> str:
    """Extract content from per-date HTML and produce a clean MD file."""
    # Title and date
    title_m = re.search(r'<title>([^<]+)</title>', html)
    raw_title = title_m.group(1).strip() if title_m else "Morning Market Analysis"
    # Strip "— August 25, 2026 | Dependability" suffix from title
    clean_title = re.sub(r'\s*[—|-]\s*\d{4}-\d{2}-\d{2}.*$', '', raw_title)
    clean_title = re.sub(r'\s*[—|-]\s*Dependability.*$', '', clean_title).strip()
    clean_title = re.sub(r'\s*[—|-]\s*$', '', clean_title).strip()

    desc_m = re.search(r'<meta name="description" content="([^"]+)"', html)
    description = desc_m.group(1).strip() if desc_m else ""

    # Date: from the meta description OR from the directory name
    date_m = re.search(r'(\d{4})-(\d{2})-(\d{2})', raw_title)
    iso_date = None
    if date_m:
        iso_date = f"{date_m.group(1)}-{date_m.group(2)}-{date_m.group(3)}"
    # Convert "Wednesday, August 26, 2026" → iso_date fallback via raw_title parse
    if not iso_date:
        months = {"january":1,"february":2,"march":3,"april":4,"may":5,"june":6,
                  "july":7,"august":8,"september":9,"october":10,"november":11,"december":12}
        m = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s+(\d{4})', raw_title, re.IGNORECASE)
        if m:
            iso_date = f"{m.group(3)}-{months[m.group(1).lower()]:02d}-{int(m.group(2)):02d}"
    if not iso_date:
        iso_date = "1970-01-01"

    # Long human date for the H1
    human_date_m = re.search(r'# Morning Market Analysis\s*[—|-]\s*([A-Z][a-z]+,\s+[A-Z][a-z]+\s+\d{1,2},\s+\d{4})', html)
    if not human_date_m:
        human_date_m = re.search(r'<div style="margin-top:12px;font-size:\.875rem;color:#888;text-align:center;">([A-Z][a-z]+\s+\d{1,2},\s+\d{4})</div>', html)
    human_date = human_date_m.group(1).strip() if human_date_m else iso_date

    # Body content from article-body div (use the balanced extractor)
    body_html = _extract_article_body(html)
    body_md = _html_to_md(body_html)

    md = f"""---
title: "{clean_title}"
date: "{iso_date}"
description: "{description}"
author: Dependability Research Desk
---

# Morning Market Analysis — {human_date}

{body_md}

---

*Sources: BLS, BEA, FactSet, Federal Reserve Board calendar, CME FedWatch, CFTC COT data, public.com, CNBC, Reuters.*

*Disclaimer: This research is for informational purposes only and does not constitute investment advice. Options trading involves substantial risk of loss. Past performance is not indicative of future results.*
"""
    return md, iso_date


def _extract_article_body(html: str) -> str:
    """Balanced-div extraction of <div class=\"article-body\"> content."""
    start = html.find('<div class="article-body">')
    if start < 0:
        return ""
    open_end = html.find('>', start)
    if open_end < 0:
        return ""
    cursor = open_end + 1
    depth = 1
    while cursor < len(html) and depth > 0:
        next_open = html.find('<div', cursor)
        next_close = html.find('</div>', cursor)
        if next_close < 0:
            return ""
        if next_open >= 0 and next_open < next_close:
            tag_end = html.find('>', next_open)
            if tag_end < 0:
                return ""
            if html[tag_end - 1] == '/':
                cursor = tag_end + 1
            else:
                depth += 1
                cursor = tag_end + 1
        else:
            depth -= 1
            if depth == 0:
                return html[open_end + 1:next_close]
            cursor = next_close + len('</div>')
    return ""


def _html_to_md(body_html: str) -> str:
    """Convert article-body HTML to MD."""
    # Drop the AdSense divs and topic comments first
    s = body_html
    s = re.sub(r'<div style="margin:2rem 0;[^"]*">.*?</div>\s*<script>\(adsbygoogle[^<]+</script>',
               '', s, flags=re.DOTALL)
    s = re.sub(r'<!-- topic:[^>]*-->', '', s)
    s = re.sub(r'<script>\(adsbygoogle[^<]+</script>', '', s)

    # Headings
    s = re.sub(r'<h2[^>]*>([^<]+)</h2>', r'\n## \1\n', s)
    s = re.sub(r'<h3[^>]*>([^<]+)</h3>', r'\n### \1\n', s)

    # Lists
    s = re.sub(r'<li[^>]*>(.*?)</li>', r'- \1', s, flags=re.DOTALL)
    s = re.sub(r'</?[ou]l[^>]*>', '\n', s)

    # Paragraphs
    s = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', s, flags=re.DOTALL)

    # Bold/italic
    s = re.sub(r'<strong>([^<]+)</strong>', r'**\1**', s)
    s = re.sub(r'<em>([^<]+)</em>', r'*\1*', s)

    # Links: <a href="...">text</a> → [text](...)
    s = re.sub(r'<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>', r'[\2](\1)', s)

    # Strip remaining tags
    s = re.sub(r'<[^>]+>', '', s)

    # HTML entity decoding (basic set)
    s = s.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    s = s.replace('&quot;', '"').replace('&#39;', "'").replace('&nbsp;', ' ')
    s = s.replace('&mdash;', '—').replace('&ndash;', '–').replace('&rsquo;', "'")
    s = s.replace('&ldquo;', '"').replace('&rdquo;', '"').replace('&hellip;', '...')

    # Collapse whitespace
    s = re.sub(r'\n{3,}', '\n\n', s)
    s = re.sub(r'[ \t]+', ' ', s)
    s = re.sub(r' *\n *', '\n', s)

    return s.strip()


def main():
    MD_DIR.mkdir(parents=True, exist_ok=True)
    restored = []
    skipped_existing = []
    missing_html = []

    for entry in sorted(COMMENTARY_DIR.iterdir()):
        if not entry.is_dir():
            continue
        m = re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})', entry.name)
        if not m:
            continue
        try:
            d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            continue

        html_path = entry / "index.html"
        md_path = MD_DIR / f"{entry.name}.md"

        if not html_path.exists() or html_path.stat().st_size == 0:
            missing_html.append(entry.name)
            continue

        md_path.parent.mkdir(parents=True, exist_ok=True)
        if md_path.exists() and md_path.stat().st_size > 0:
            skipped_existing.append(entry.name)
            continue

        try:
            md_text, iso_date = html_to_md(html_path.read_text())
        except Exception as e:
            print(f"  SKIP {entry.name}: parse error: {e}")
            continue

        tmp = md_path.with_suffix(".md.tmp")
        tmp.write_text(md_text)
        os.replace(tmp, md_path)
        restored.append(entry.name)

    print(f"Restored:   {len(restored)}")
    for d in restored:
        print(f"  + {d}")
    print(f"Skipped (had content):  {len(skipped_existing)}")
    for d in skipped_existing:
        print(f"  = {d}")
    print(f"Missing HTML source:    {len(missing_html)}")
    for d in missing_html:
        print(f"  - {d}")


if __name__ == "__main__":
    raise SystemExit(main())
