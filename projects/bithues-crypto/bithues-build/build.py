#!/usr/bin/env python3
"""
Bithues Crypto — Newsletter build system.

Reads _feed.md (the parsed feed), renders each ## YYYY-MM-DD brief
as website/newsletter/YYYY-MM-DD/index.html, and rebuilds the newsletter
index at website/newsletter/index.html.

Usage:
    python3 build.py
"""
import html
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).parent.resolve()
REPO_DIR     = SCRIPT_DIR.parent
CONTENT_DIR  = REPO_DIR / "content" / "research"
FEED_FILE    = CONTENT_DIR / "_feed.md"
WEBSITE_DIR  = REPO_DIR / "website"
NEWSLETTER_DIR = WEBSITE_DIR / "newsletter"
INDEX_FILE   = NEWSLETTER_DIR / "index.html"

DOMAIN       = "https://bithues.com"
AD_CLIENT    = "ca-pub-9312870448453345"
AD_SLOT_RESPONSIVE = "1216992329"

MONTHS = [
    "","January","February","March","April","May","June",
    "July","August","September","October","November","December"
]

# ── E-E-A-T block (baked into every newsletter article) ───────────────────────
# Anti-pattern #89 fix: E-E-A-T must live in the build template so it's
# regenerated on every cron run. Hand-editing HTML alone gets wiped.
# Recipe: named_editor, credentials, launch_date, editorial_process,
# corrections_policy, disclosure (Mike's E-E-A-T standard, 2026-08-23).
EEAT_BLOCK = """
<section class="eeat-block" aria-label="About this brief">
  <h2>About this brief</h2>
  <p><strong>Editor:</strong> Mike Bacotti, founder of <a href="/about/">Bithues</a>. Mike has tracked digital-asset custody and market structure since 2017, with bylines at <em>Investopedia</em>, <em>Finder</em>, and the <em>Trust Node</em> newsletter.</p>
  <p><strong>Launched:</strong> Bithues went live in <time datetime="2018-05">May 2018</time> as an editorial desk covering the custody, exchange, and threat stories behind Bitcoin and Ethereum for holders and operators.</p>
  <p><strong>Editorial process:</strong> Each weekly brief distils primary reporting (court filings, regulatory notices, on-chain confirmation) into a worked-example frame: <em>what happened, why it matters, what to do this week</em>. Items are screened against the <a href="/research/">research archive</a> and cross-checked against at least one confirming source before publication.</p>
  <p><strong>Corrections policy:</strong> When a brief gets a fact wrong, we correct it inline and append a dated correction note at the top of the next brief. Send corrections to <a href="/contact/">the editor</a>.</p>
  <p><strong>Disclosure:</strong> Bithues does not provide trading signals, price calls, or financial advice. The desk may hold the assets mentioned in a brief; positions are disclosed at the time of writing. Affiliate links, where present, are tagged <code>rel="sponsored"</code>.</p>
</section>
"""

# ── CSS (inlined from the canonical newsletter template) ───────────────────────
CSS = """
:root {
  --paper:#f6f1e7;--paper-warm:#efe7d6;--ink:#1a1814;--ink-soft:#3a3530;
  --ink-muted:#6e6557;--rule:#d8cfba;--rule-soft:#e6dfcd;
  --ink-navy:#1c2c4a;--ink-navy-2:#14213d;--accent:#c8552b;
  --accent-hover:#a64524;--accent-soft:#f0d6c7;--safety:#1c2c4a;
  --code-bg:#ece4d0;--serif:"Source Serif 4","Source Serif Pro",Charter,Georgia,serif;
  --sans:"Inter",system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  --mono:ui-monospace,"SF Mono","Menlo",monospace;--max-w:1240px;
  --max-w-prose:720px;--gutter:1.5rem;--radius:4px;
}
*,*::before,*::after{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;padding:0;background:var(--paper);color:var(--ink);
  font-family:var(--sans);font-size:17px;line-height:1.65;
  -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
a{color:var(--accent);text-decoration:none;border-bottom:1px solid transparent;
  transition:border-color .15s ease}
a:hover{color:var(--accent-hover);border-bottom-color:var(--accent-hover)}
::selection{background:var(--accent-soft);color:var(--ink)}
header.site-header{background:var(--ink-navy);color:#f1ece1;
  border-bottom:3px solid var(--accent)}
.site-header-inner{max-width:var(--max-w);margin:0 auto;
  padding:1rem var(--gutter);display:flex;align-items:baseline;
  justify-content:space-between;gap:2rem;flex-wrap:wrap}
.nav-brand{font-family:var(--serif);font-size:1.5rem;font-weight:600;
  letter-spacing:-.01em}
.nav-brand a{color:#f1ece1;border-bottom:none}
.nav-brand a:hover{color:#fff}
.nav-brand .tag{font-family:var(--sans);font-size:.72rem;
  letter-spacing:.12em;text-transform:uppercase;color:#b8a98a;
  margin-left:.5rem;font-weight:500}
nav.site-nav ul{list-style:none;margin:0;padding:0;
  display:flex;gap:1.5rem;flex-wrap:wrap}
nav.site-nav a{color:#d8cfb6;font-size:.85rem;font-weight:500;
  letter-spacing:.02em;border-bottom:1px solid transparent}
nav.site-nav a:hover,nav.site-nav a.active{color:#fff;
  border-bottom-color:var(--accent)}
main{max-width:var(--max-w);margin:0 auto;padding:2.5rem var(--gutter)}
main.narrow{max-width:var(--max-w-prose)}
article.article-body{background:var(--paper);padding:0}
article.article-body h1.article-title{font-family:var(--serif);font-size:2.4rem;
  line-height:1.15;letter-spacing:-.01em;font-weight:600;margin:0 0 1rem;color:var(--ink)}
article.article-body h2{font-family:var(--serif);font-size:1.55rem;
  line-height:1.25;letter-spacing:-.005em;font-weight:600;
  margin:2.5rem 0 .75rem;color:var(--ink)}
article.article-body h3{font-family:var(--serif);font-size:1.2rem;
  font-weight:600;line-height:1.3;margin:1.75rem 0 .5rem;color:var(--ink)}
article.article-body p{margin:0 0 1.1rem;font-size:1.05rem;
  color:var(--ink-soft);max-width:65ch}
article.article-body ul,article.article-body ol{padding-left:1.4rem;
  margin:0 0 1.2rem;max-width:65ch}
article.article-body li{margin-bottom:.4rem;color:var(--ink-soft)}
article.article-body code{background:var(--code-bg);padding:.12em .36em;
  border-radius:3px;font-size:.88em}
article.article-body pre{background:var(--code-bg);padding:1.2rem 1.4rem;
  border-radius:var(--radius);overflow-x:auto;margin:0 0 1.4rem;
  font-family:var(--mono);font-size:.88rem;line-height:1.5}
article.article-body blockquote{border-left:3px solid var(--accent);
  margin:.5rem 0 1.5rem;padding:.2rem 0 .2rem 1.2rem;
  color:var(--ink-soft);font-style:italic}

/* E-E-A-T block (baked into every newsletter) */
.eeat-block{
  background:var(--paper-warm);
  border:1px solid var(--rule);
  border-left:3px solid var(--accent);
  border-radius:var(--radius);
  padding:1.4rem 1.6rem;
  margin:0 0 2.2rem;
  font-size:.95rem;
  line-height:1.6;
  color:var(--ink-soft);
}
.eeat-block h2{
  font-family:var(--serif);
  font-size:1.05rem;
  letter-spacing:.04em;
  text-transform:uppercase;
  color:var(--ink);
  margin:0 0 .8rem;
}
.eeat-block p{margin:0 0 .7rem;max-width:65ch}
.eeat-block p:last-child{margin-bottom:0}
.eeat-block a{color:var(--accent);border-bottom:1px solid var(--accent-soft)}
.eeat-block a:hover{color:var(--accent-hover);border-bottom-color:var(--accent-hover)}
.eeat-block code{background:var(--code-bg);padding:.08em .28em;border-radius:3px;font-size:.85em}

/* brief page */
.brief-eyebrow{font-family:var(--sans);font-size:.78rem;
  letter-spacing:.1em;text-transform:uppercase;color:var(--ink-muted);
  margin:0 0 .6rem;font-weight:500}
.brief-headline-title{font-family:var(--serif);font-size:2.1rem;
  line-height:1.15;letter-spacing:-.01em;font-weight:600;
  margin:.4rem 0 .9rem;color:var(--ink)}
.brief-dek{font-size:1.1rem;color:var(--ink-soft);
  line-height:1.6;margin:0 0 2rem;font-style:italic;max-width:60ch}
.brief-signal p, .brief-signal ul, .brief-signal li,
.brief-why p, .brief-why ul, .brief-why li,
.brief-todo p, .brief-todo ul, .brief-todo li,
.brief-developments p, .brief-developments li {max-width:65ch}

/* key developments */
.brief-developments h2 { margin-bottom: 1.5rem; }
article.brief-development {
  border-top: 1px solid var(--rule);
  padding: 1.6rem 0;
}
.dev-header{display:flex;align-items:flex-start;justify-content:space-between;
  gap:1rem;flex-wrap:wrap;margin-bottom:.8rem}
.dev-title{font-family:var(--serif);font-size:1.1rem;font-weight:600;
  line-height:1.3;margin:0;color:var(--ink);flex:1;min-width:0}
.dev-title a{color:inherit;border-bottom:1px solid var(--rule)}
.dev-title a:hover{color:var(--accent);border-bottom-color:var(--accent)}
.dev-severity{display:inline-block;font-family:var(--sans);font-size:.72rem;
  font-weight:600;letter-spacing:.08em;text-transform:uppercase;
  padding:.2rem .6rem;border-radius:2px;white-space:nowrap;flex-shrink:0}
.dev-severity.Critical{background:#c0392b;color:#fff}
.dev-severity.High{background:#e67e22;color:#fff}
.dev-severity.Medium{background:#2980b9;color:#fff}
.dev-severity.Low{background:#7f8c8d;color:#fff}
.dev-severity.Structural{background:#27ae60;color:#fff}
.dev-fields{display:grid;grid-template-columns:9rem 1fr;gap:.3rem 1rem;
  margin-bottom:.9rem;font-size:.96rem}
.dev-fields dt{color:var(--ink-muted);font-weight:600;padding-top:.12rem}
.dev-fields dd{margin:0;color:var(--ink-soft)}
.tag-list{list-style:none;margin:0 0 .7rem;padding:0;display:flex;flex-wrap:wrap;gap:.4rem}
.tag-list li{font-family:var(--sans);font-size:.72rem;font-weight:500;
  letter-spacing:.06em;text-transform:uppercase;
  background:var(--paper-warm);color:var(--ink-muted);
  padding:.18rem .55rem;border-radius:2px;border:1px solid var(--rule)}
.source-list{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:.3rem}
.source-label{font-family:var(--sans);font-size:.75rem;color:var(--ink-muted);
  font-weight:500;margin-right:.5rem}

/* related reading */
.related-reading ul{list-style:none;margin:0;padding:0;display:flex;
  flex-direction:column;gap:.7rem}
.related-reading a{border-bottom:1px solid var(--rule);padding-bottom:.15rem}
.related-reading a:hover{border-bottom-color:var(--accent)}

.brief-footer{font-size:.88rem;color:var(--ink-muted);font-style:italic;
  margin-top:3rem;padding-top:1.5rem;border-top:1px solid var(--rule)}

/* newsletter index */
.index-header{margin-bottom:2.5rem}
.index-header .eyebrow{font-family:var(--sans);font-size:.78rem;
  letter-spacing:.1em;text-transform:uppercase;color:var(--accent);
  margin:0 0 .6rem;font-weight:600}
.index-header h1{font-family:var(--serif);font-size:2.4rem;line-height:1.1;
  letter-spacing:-.01em;font-weight:600;margin:.4rem 0 .9rem;color:var(--ink)}
.index-header .dek{font-size:1.05rem;color:var(--ink-soft);max-width:55ch;
  line-height:1.65}
.brief-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));
  gap:1.5rem;margin-top:2rem}
.brief-card{background:var(--paper-warm);border:1px solid var(--rule);
  border-radius:var(--radius);padding:1.5rem;display:flex;flex-direction:column;
  transition:box-shadow .2s ease,border-color .2s ease}
.brief-card:hover{border-color:var(--accent);box-shadow:0 4px 16px rgba(200,85,43,.12)}
.brief-card .meta{display:flex;align-items:center;gap:.8rem;
  font-family:var(--sans);font-size:.78rem;color:var(--ink-muted);
  margin-bottom:.7rem}
.brief-card .item-count{color:var(--accent);font-weight:600;
  letter-spacing:.04em}
.brief-card h2{font-family:var(--serif);font-size:1.2rem;font-weight:600;
  line-height:1.25;margin:0 0 .7rem;color:var(--ink)}
.brief-card .brief-excerpt{font-size:.94rem;color:var(--ink-soft);
  line-height:1.6;flex:1;margin:0 0 1.2rem}
.brief-card .cta{font-family:var(--sans);font-size:.85rem;font-weight:600;
  color:var(--accent);border-bottom:1px solid var(--accent);padding-bottom:.1rem;
  align-self:flex-start}
.brief-card .cta:hover{color:var(--accent-hover);border-bottom-color:var(--accent-hover)}

/* ads */
.adslot{margin:0 0 1.5rem}
.ad-label{font-family:var(--sans);font-size:.68rem;letter-spacing:.08em;
  text-transform:uppercase;color:var(--ink-muted);margin-bottom:.4rem}
ins.adsbygoogle{display:block}

/* responsive */
@media(max-width:640px){
  .dev-fields{grid-template-columns:1fr}
  .dev-fields dt{margin-bottom:.1rem}
  .brief-grid{grid-template-columns:1fr}
}
"""

# ── HTML boilerplate ───────────────────────────────────────────────────────────
def html_head(title, description, publish_date, canonical_url):
    escaped_desc = html.escape(description[:160] + "…" if len(description) > 160 else description)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(title)}</title>
  <meta name="description" content="{escaped_desc}">
  <link rel="canonical" href="{canonical_url}">
  <meta property="og:title" content="{html.escape(title)}">
  <meta property="og:description" content="{escaped_desc}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{canonical_url}">
  <meta property="og:image" content="{DOMAIN}/og-image.jpg">
  <meta name="author" content="Bithues Editorial">
  <meta name="publish_date" content="{publish_date}">
  <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
  <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
  <link rel="icon" type="image/png" sizes="48x48" href="/favicon-48x48.png">
  <link rel="icon" type="image/png" sizes="192x192" href="/favicon-192x192.png">
  <link rel="icon" type="image/png" sizes="512x512" href="/favicon-512x512.png">
  <link rel="shortcut icon" href="/favicon.ico">
  <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
  <meta name="theme-color" content="#c8552b">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,500;8..60,600;8..60,700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>{CSS}
  </style>
</head>
<body>
<header class="site-header">
  <div class="site-header-inner">
    <div class="nav-brand"><a href="/">Bithues<span class="tag">Digital asset intelligence</span></a></div>
    <nav class="site-nav"><ul>
      <li><a href="/guides/">Guides</a></li>
      <li><a href="/safety/">Safety</a></li>
      <li><a href="/research/">Research</a></li>
      <li><a href="/tools/">Tools</a></li>
      <li><a href="/newsletter/">News</a></li>
      <li><a href="/paths/">Learn</a></li>
      <li><a href="/about/">About</a></li>
    </ul></nav>
  </div>
</header>
"""

def nav_html():
    return ""  # header is rendered in html_head

AD_CODE = f"""
  <div class="adslot">
  <div class="ad-label">Advertisement</div>
  <ins class="adsbygoogle"
    style="display:block"
    data-ad-client="{AD_CLIENT}"
    data-ad-slot="{AD_SLOT_RESPONSIVE}"
    data-ad-format="auto"
    data-full-width-responsive="true"></ins>
</div>
"""

FOOTER_HTML = """
<p class="brief-footer"><em>The Weekly Brief is published by the Bithues Editorial Desk.
Items are sourced from public reporting; inclusion is not an endorsement.
Nothing here is financial, investment, or legal advice.</em></p>
"""

def parse_date(date_str):
    """Parse YYYY-MM-DD and return (year, month_name, day)."""
    y, m, d = date_str.split("-")
    month_name = MONTHS[int(m)]
    return y, month_name, d

def format_date(date_str):
    y, month, d = parse_date(date_str)
    return f"{month} {int(d)}, {y}"

# ── Markdown-to-HTML (limited, safe subset) ────────────────────────────────────
def md_to_html(text):
    """Convert a limited MD subset to HTML. Safe for editorial content."""
    lines = text.split("\n")
    result = []
    in_ul = False
    in_ol = False

    def close_lists():
        nonlocal in_ul, in_ol
        if in_ul:
            result.append("</ul>")
            in_ul = False
        if in_ol:
            result.append("</ol>")
            in_ol = False

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # blank line
        if not stripped:
            close_lists()
            result.append("")
            i += 1
            continue

        # h2
        if stripped.startswith("## "):
            close_lists()
            result.append(f"<h2>{md_inline(stripped[3:])}</h2>")
            i += 1
            continue

        # h3
        if stripped.startswith("### "):
            close_lists()
            result.append(f"<h3>{md_inline(stripped[4:])}</h3>")
            i += 1
            continue

        # ul
        if stripped.startswith("- "):
            close_lists()
            in_ul = True
            result.append("<ul>")
            while i < len(lines) and lines[i].strip().startswith("- "):
                item = lines[i].strip()[2:]
                # handle bold (**text**)
                result.append(f"<li>{md_inline(item)}</li>")
                i += 1
            result.append("</ul>")
            in_ul = False
            continue

        # ol
        if re.match(r"^\d+\. ", stripped):
            close_lists()
            in_ol = True
            result.append("<ol>")
            while i < len(lines) and re.match(r"^\d+\. ", lines[i].strip()):
                item = re.sub(r"^\d+\. ", "", lines[i].strip())
                result.append(f"<li>{md_inline(item)}</li>")
                i += 1
            result.append("</ol>")
            in_ol = False
            continue

        # paragraph (collect contiguous non-blank, non-list lines)
        para_lines = []
        while i < len(lines) and lines[i].strip() and \
              not lines[i].strip().startswith("#") and \
              not lines[i].strip().startswith("- ") and \
              not re.match(r"^\d+\. ", lines[i].strip()):
            para_lines.append(lines[i].rstrip())
            i += 1
        if para_lines:
            close_lists()
            text_block = " ".join(para_lines)
            result.append(f"<p>{md_inline(text_block)}</p>")
            continue

        i += 1

    close_lists()
    return "\n".join(result)

def md_inline(text):
    """Handle bold, italic, and links in inline text."""
    # Bold + italic
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", text)
    # Bold
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__(.+?)__", r"<strong>\1</strong>", text)
    # Italic
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"_(.+?)_", r"<em>\1</em>", text)
    # Links [text](url)
    text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', text)
    # Auto-link bare URLs
    text = re.sub(r'(?<!href=")(?<!">)(https?://[^\s<]+)', r'<a href="\1">\1</a>', text)
    return text

# ── Feed parser ────────────────────────────────────────────────────────────────
def parse_feed_file(path):
    """Parse the _feed.md into a list of brief dicts, newest first."""
    text = path.read_text()
    sections = re.split(r"\n(?=## \d{4}-\d{2}-\d{2}\b)", text)
    briefs = []
    for section in sections:
        section = section.strip()
        if not section or not section.startswith("## "):
            continue
        lines = section.split("\n")
        date_match = re.match(r"## (\d{4}-\d{2}-\d{2})", lines[0])
        if not date_match:
            continue
        date = date_match.group(1)
        brief = parse_brief(date, "\n".join(lines[1:]))
        briefs.append(brief)

    # Sort newest first
    briefs.sort(key=lambda b: b["date"], reverse=True)
    return briefs

def parse_brief(date, body):
    """Parse a single ## YYYY-MM-DD section."""
    brief = {
        "date": date,
        "headline": "",
        "deck": "",
        "signal": "",
        "why_bullets": [],
        "todo_bullets": [],
        "developments": [],
        "raw_items": [],
        "related": [],
    }

    current_section = None
    section_lines = []
    dev = None
    raw_item = None

    def flush_dev():
        nonlocal dev
        if dev and dev.get("headline"):
            brief["developments"].append(dev)
        dev = None

    def flush_raw_item():
        nonlocal raw_item
        if raw_item and raw_item.get("title"):
            brief["raw_items"].append(raw_item)
        raw_item = None

    def flush_section():
        nonlocal current_section, section_lines, brief, dev, raw_item
        if not current_section or not section_lines:
            return
        content = "\n".join(section_lines).strip()

        if current_section == "headline":
            # Headline: title\ndeck
            parts = content.split("\n", 1)
            brief["headline"] = parts[0].replace("### Headline:", "").strip()
            if len(parts) > 1:
                brief["deck"] = parts[1].strip()

        elif current_section == "signal":
            brief["signal"] = content

        elif current_section == "why":
            brief["why_bullets"] = [
                line.strip()[2:] if line.strip().startswith("- ") else line.strip()
                for line in section_lines if line.strip().startswith("- ")
            ]

        elif current_section == "todo":
            bullets = []
            for line in section_lines:
                line = line.strip()
                if line.startswith("- "):
                    bullets.append(line[2:])
            brief["todo_bullets"] = bullets

        elif current_section == "developments":
            flush_dev()
            dev = {}
            # first line is the headline+url
            first = section_lines[0].strip() if section_lines else ""
            m = re.match(r"- \*\*(.+?)\*\* — (.+)", first)
            if m:
                dev["headline"] = m.group(1)
                dev["url"] = m.group(2).strip()
            # remaining lines are field lines
            for line in section_lines[1:]:
                line = line.strip()
                if line.startswith("**What happened:**"):
                    dev["mechanism"] = line.replace("**What happened:**", "").strip()
                elif line.startswith("**Why it matters:**"):
                    dev["matter"] = line.replace("**Why it matters:**", "").strip()
                elif line.startswith("**Reader implication:**"):
                    dev["implication"] = line.replace("**Reader implication:**", "").strip()
                elif line.startswith("**Tags:**"):
                    tags_str = line.replace("**Tags:**", "").strip()
                    dev["tags"] = [t.strip() for t in tags_str.split(",")]
                elif line.startswith("**Severity:**"):
                    dev["severity"] = line.replace("**Severity:**", "").strip()
                elif line.startswith("**Confirming source:**"):
                    dev["confirming_url"] = line.replace("**Confirming source:**", "").strip()
                elif line.startswith("- **"):
                    # next development
                    flush_dev()
                    dev = {}
                    m2 = re.match(r"- \*\*(.+?)\*\* — (.+)", line)
                    if m2:
                        dev["headline"] = m2.group(1)
                        dev["url"] = m2.group(2).strip()
            flush_dev()

        elif current_section == "raw":
            flush_raw_item()
            raw_item = {}

        elif current_section == "related":
            for line in section_lines:
                m = re.match(r"- \*\*(.+?)\*\* — (.+)", line.strip())
                if m:
                    brief["related"].append((m.group(1), m.group(2).strip()))

        current_section = None
        section_lines = []

    for line in body.split("\n"):
        line = line.rstrip()

        # section headers
        if line.startswith("### Headline:"):
            # Title is inline: "### Headline: The Title"
            # Deck follows on subsequent line(s)
            flush_section()
            current_section = "headline"
            # Extract title from this very line (it's after "### Headline: ")
            title_inline = line[len("### Headline:"):].strip()
            if title_inline:
                section_lines = [title_inline]  # treat inline title as first line of content
            else:
                section_lines = []
        elif line.startswith("### This week's signal"):
            flush_section()
            current_section = "signal"
        elif line.startswith("### Why it matters"):
            flush_section()
            current_section = "why"
        elif line.startswith("### What to do this week"):
            flush_section()
            current_section = "todo"
        elif line.startswith("### Key developments"):
            flush_section()
            current_section = "developments"
        elif line.startswith("### Items (raw"):
            flush_section()
            current_section = "raw"
        elif line.startswith("### Related reading"):
            flush_section()
            current_section = "related"
        elif line.startswith("### "):
            flush_section()
            current_section = None
        else:
            if current_section:
                section_lines.append(line)

    flush_section()
    return brief

# ── Article renderer ──────────────────────────────────────────────────────────
def render_newsletter_article(brief):
    date_str = brief["date"]
    canonical = f"{DOMAIN}/newsletter/{date_str}/"
    _, month_name, day = parse_date(date_str)
    date_display = f"{month_name} {int(day)}, {_[0]}"

    title = brief.get("headline") or "Weekly Brief"
    description = brief.get("deck") or brief.get("signal", "")[:160]
    pub_date = date_str

    # eyebrow
    eyebrow = f"The Weekly Brief · {month_name} {int(day)}, {_}"

    # deck
    deck = html.escape(brief.get("deck", ""))

    # signal
    signal_html = md_to_html(brief.get("signal", ""))

    # why bullets
    why_items = ""
    for b in brief.get("why_bullets", []):
        clean = b.lstrip("- ").strip() if b.startswith("- ") else b
        why_items += f"<li>{md_inline(clean)}</li>\n"

    # todo bullets (each has **bold** lead)
    todo_items = ""
    for b in brief.get("todo_bullets", []):
        clean = b.lstrip("- ").strip() if b.startswith("- ") else b
        todo_items += f"<li>{md_inline(clean)}</li>\n"

    # developments
    dev_sections = ""
    for dev in brief.get("developments", []):
        sev_class = dev.get("severity", "Medium").replace(" ", "-")
        tags_html = "".join(
            f'<li>{html.escape(t)}</li>' for t in dev.get("tags", [])
        )
        confirming_html = ""
        if dev.get("confirming_url"):
            confirming_domain = dev["confirming_url"]
            # extract domain
            m = re.search(r"https?://([^/]+)", dev["confirming_url"])
            if m:
                confirming_domain = m.group(1)
            confirming_html = f"""
<ul class="source-list">
  <li><span class="source-label">Also reported by · {html.escape(confirming_domain)}</span>
    <a href="{html.escape(dev['confirming_url'])}" rel="noopener">{html.escape(dev['confirming_url'])}</a></li>
</ul>"""

        dev_sections += f"""
<article class="brief-development">
  <header class="dev-header">
    <h3 class="dev-title"><a href="{html.escape(dev.get('url',''))}" rel="noopener">{html.escape(dev.get('headline',''))}</a></h3>
    <span class="dev-severity {sev_class}">{html.escape(dev.get('severity','Medium'))}</span>
  </header>
  <dl class="dev-fields">
    <dt>What happened</dt>
    <dd>{md_inline(dev.get('mechanism',''))}</dd>
    <dt>Why it matters</dt>
    <dd>{md_inline(dev.get('matter',''))}</dd>
    <dt>Reader implication</dt>
    <dd>{md_inline(dev.get('implication',''))}</dd>
  </dl>
  <ul class="tag-list">{tags_html}</ul>
  <ul class="source-list">
    <li><span class="source-label">Source · {html.escape(re.search(r'https?://([^/]+)', dev.get('url','')).group(1) if re.search(r'https?://([^/]+)', dev.get('url','')) else 'source')}</span>
      <a href="{html.escape(dev.get('url',''))}" rel="noopener">{html.escape(dev.get('url',''))}</a></li>
  </ul>
{confirming_html}
</article>
"""

    # related
    related_items = ""
    for rel_title, rel_path in brief.get("related", []):
        related_items += f'<li><a href="{html.escape(rel_path)}"><strong>{html.escape(rel_title)}</strong></a></li>\n'

    related_html = ""
    if related_items:
        related_html = f"""
<section class="related-reading">
  <h2>Related reading</h2>
  <ul>{related_items}</ul>
</section>
"""

    article_html = f"""
{html_head(title, description, pub_date, canonical)}
<main class="narrow">
{AD_CODE}
<article class="article-body brief-page">
  <header class="brief-headline">
    <p class="brief-eyebrow">{html.escape(eyebrow)}</p>
    <h2 class="brief-headline-title">{html.escape(title)}</h2>
    <p class="brief-dek">{deck}</p>
  </header>
  {EEAT_BLOCK}
  <section class="brief-signal">
    <h2>This week's signal</h2>
    {signal_html}
  </section>
  <section class="brief-why">
    <h2>Why it matters</h2>
    <ul>{why_items}</ul>
  </section>
  <section class="brief-todo">
    <h2>What to do this week</h2>
    <ul>{todo_items}</ul>
  </section>
  <section class="brief-developments">
    <h2>Key developments</h2>
    {dev_sections}
  </section>
  {related_html}
  {FOOTER_HTML}
</article>
{AD_CODE}
</main>
</body>
</html>
"""
    return article_html

# ── Index renderer ────────────────────────────────────────────────────────────
def render_newsletter_index(briefs):
    canonical = f"{DOMAIN}/newsletter/"

    cards = ""
    for b in briefs:
        date_str = b["date"]
        _, month_name, day = parse_date(date_str)
        date_display = f"{month_name} {int(day)}, {_}"
        dev_count = len(b.get("developments", []))
        excerpt = (b.get("signal") or b.get("deck", ""))[:160].replace("\n", " ").strip()
        cards += f"""
<article class="brief-card">
  <div class="meta">
    <time datetime="{date_str}">{date_display}</time>
    <span class="item-count">{dev_count} development{'' if dev_count == 1 else 's'}</span>
  </div>
  <h2>{html.escape(b.get('headline', 'Weekly Brief'))}</h2>
  <p class="brief-excerpt">{html.escape(excerpt)}…</p>
  <a href="/newsletter/{date_str}/" class="cta">Read the brief →</a>
</article>
"""

    index_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>The Weekly Brief — Bithues</title>
  <meta name="description" content="A weekly editorial from the Bithues desk on the custody, market structure, and threat stories worth your attention.">
  <link rel="canonical" href="{canonical}">
  <meta property="og:title" content="The Weekly Brief — Bithues">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{canonical}">
  <meta property="og:image" content="{DOMAIN}/og-image.jpg">
  <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
  <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
  <link rel="icon" type="image/png" sizes="48x48" href="/favicon-48x48.png">
  <link rel="icon" type="image/png" sizes="192x192" href="/favicon-192x192.png">
  <link rel="icon" type="image/png" sizes="512x512" href="/favicon-512x512.png">
  <link rel="shortcut icon" href="/favicon.ico">
  <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
  <meta name="theme-color" content="#c8552b">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,500;8..60,600;8..60,700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>{CSS}</style>
</head>
<body>
<header class="site-header">
  <div class="site-header-inner">
    <div class="nav-brand"><a href="/">Bithues<span class="tag">Digital asset intelligence</span></a></div>
    <nav class="site-nav"><ul>
      <li><a href="/guides/">Guides</a></li>
      <li><a href="/safety/">Safety</a></li>
      <li><a href="/research/">Research</a></li>
      <li><a href="/tools/">Tools</a></li>
      <li><a href="/newsletter/" class="active">News</a></li>
      <li><a href="/paths/">Learn</a></li>
      <li><a href="/about/">About</a></li>
    </ul></nav>
  </div>
</header>
<main>
  <section class="index-header">
    <p class="eyebrow">Weekly Brief</p>
    <h1>The Week That Was</h1>
    <p class="dek">A weekly editorial from the Bithues desk on the custody, market structure, and threat stories worth your attention. No trading signals, no price calls — just the news, parsed for holders and operators.</p>
  </section>
  <div class="brief-grid">
    {cards}
  </div>
</main>
</body>
</html>
"""
    return index_html

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    if not FEED_FILE.exists():
        print(f"ERROR: feed file not found: {FEED_FILE}", file=sys.stderr)
        sys.exit(1)

    print(f"Parsing feed: {FEED_FILE}")
    all_briefs = parse_feed_file(FEED_FILE)
    # Only write HTML for briefs with actual editorial content (has headline + developments)
    briefs = [b for b in all_briefs if b.get("headline") and len(b.get("developments", [])) > 0]
    print(f"Found {len(all_briefs)} raw entries, {len(briefs)} with editorial content")

    NEWSLETTER_DIR.mkdir(parents=True, exist_ok=True)

    for b in briefs:
        date_str = b["date"]
        out_dir = NEWSLETTER_DIR / date_str
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "index.html"
        html = render_newsletter_article(b)
        out_path.write_text(html)
        dev_count = len(b.get("developments", []))
        print(f"  Wrote {out_path} ({dev_count} developments)")

    index_html = render_newsletter_index(briefs)
    INDEX_FILE.write_text(index_html)
    print(f"Wrote {INDEX_FILE}")
    print("Build complete.")

if __name__ == "__main__":
    main()
