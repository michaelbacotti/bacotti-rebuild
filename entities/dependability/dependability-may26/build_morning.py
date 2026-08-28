#!/usr/bin/env python3
"""
build_morning.py — Dependability.us Morning Brief Index Renderer

Reads the most recent per-date morning-analysis HTML files in
`entities/dependability/website/commentary/YYYY-MM-DD/index.html`
and regenerates `commentary/index.html` with the latest brief featured
as the hero, plus an archive grid of older briefs.

Replaces the prior inline-HTML-construction pattern that left
/commentary/index.html in a broken state with stale hardcoded articles
(Mike 2026-08-26 directive: get the index updated by 6am ET).

Usage:
    python3 build_morning.py

The script writes ONLY to:
  - entities/dependability/website/commentary/index.html

The per-date HTML files (commentary/YYYY-MM-DD/index.html) are
expected to already exist; this script does NOT create them. The
morning cron writes those per-date files first, then calls this
script to regenerate the index.

Idempotent: re-running with no changes produces byte-identical output.
"""

import os
import re
from datetime import date
from pathlib import Path

# Paths
ROOT = Path(__file__).resolve().parent.parent  # entities/dependability/
WEBSITE_DIR = ROOT / "website"
COMMENTARY_DIR = WEBSITE_DIR / "commentary"
INDEX_PATH = COMMENTARY_DIR / "index.html"


# Static template for the commentary index page.
# Uses {{ }} for JS brace literals (so this is a .format() template, not an f-string).
# Field names match the kwargs passed in build_index_html().
HEAD_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
 <meta charset="UTF-8">
 <meta name="viewport" content="width=device-width, initial-scale=1.0">
 <title>Market Commentary — Morning Market Analysis | Dependability Holdings LLC</title>
 <meta name="description" content="Morning Market Analysis is the pre-market brief on dependability.us. Today's brief: {title_xml}">
 <link rel="canonical" href="https://dependability.us/commentary/">
 <meta property="og:type" content="website">
 <meta property="og:image" content="https://dependability.us/og-image.jpg">
 <link rel="icon" type="image/svg+xml" href="/favicon.svg">
 <link rel="manifest" href="/site.webmanifest">
 <link rel="stylesheet" href="/style.css">
 <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-9312870448453345" crossorigin="anonymous"></script>
 <!-- Google tag (gtag.js) — GA4 (Dependability property) -->
 <script async src="https://www.googletagmanager.com/gtag/js?id=G-CR7TV6QRSN"></script>
 <script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', 'G-CR7TV6QRSN');
 </script>
</head>
<body>

 <div id="site-utility"></div>
 <div id="site-nav"></div>

 <main>
 <!-- BANNER_AREA -->
 <div class="page-hero">
 <p class="hero-title">Market Commentary</p>
 <div style="margin-top:12px;font-size:.875rem;color:#888;text-align:center;">Morning analyses, weekly forecasts, and structural reads from the Dependability Research Desk.</div>
</div>

<div class="page-content">
 <p style="font-size:1.0625rem;line-height:1.8;color:#333;text-align:center;max-width:780px;margin:0 auto 32px;"><strong>Morning Market Analysis</strong> is the pre-market brief — a short, focused read on what happened overnight, what to expect at the open, and the key levels and events shaping today's session. It is the quick heads-up before the bell. For the longer recap of the day's price action, S&amp;P 500 levels, and the week-ahead outlook, see the <a href="/forecast/" style="color:#c8001e;font-weight:600;">Afternoon Market Commentary</a> — the more deliberate post-close read built for traders planning out the week.</p>

 <div class="archive-section">
  <h2 class="archive-section__title" style="margin-bottom:20px;border-bottom:2px solid #c8001e;padding-bottom:8px;color:#1a1a1a;text-align:center;">Today's Morning Market Analysis &mdash; {today_long}</h2>
  <div style="background:#fff;border:1px solid #e0e0e0;padding:24px;margin-bottom:28px;">
   <div class="category-label" style="margin-bottom:14px;text-align:center;">PRE-MARKET BRIEF</div>
   <h2 style="margin-bottom:16px;border-bottom:2px solid #c8001e;padding-bottom:8px;text-align:center;">{title}</h2>
   <p style="font-size:.95rem;color:#666;line-height:1.5;margin-bottom:16px;font-style:italic;text-align:center;">{lead}</p>
   <div class="article-body">

{body_inner}
   </div>
  </div>
 </div>

<nav class="article-breadcrumb" aria-label="Breadcrumb">
  <a href="/">Home</a><span class="sep">›</span>
  <a href="/commentary/">Commentary</a><span class="sep">›</span>
  <span aria-current="page">Morning Analyses</span>
</nav>
{prev_link_html}

 <div class="archive-section" style="margin-top:48px;">
  <h2 class="archive-section__title" style="margin-bottom:20px;border-bottom:2px solid #1a1a1a;padding-bottom:8px;color:#1a1a1a;text-align:center;">Recent Morning Analyses</h2>
  <p style="font-size:.9375rem;color:#666;margin-bottom:20px;text-align:center;"><em>Each morning brief is published the same trading day at 5:55 AM ET and lives at <code>/commentary/YYYY-MM-DD/</code>. View <a href="/commentary/archive/" style="color:#c8001e;">the full archive</a> for older analyses.</em></p>
  <div class="archive-grid" style="display:flex;flex-direction:column;gap:0;">
{archive_html}
  </div>
 </div>

 <p style="font-size:0.9375rem;color:#666;margin-top:32px;text-align:center;"><em>Morning Market Analysis is published each weekday at 5:55 AM ET. In-depth commentary is published multiple times per week. Sources include Cboe, FRED, SEC filings, and primary macro data from BLS, BEA, and the Federal Reserve.</em></p>
</div>

<section class="eeat-block" aria-label="About this article">
 <h2>About this article</h2>
 <p><strong>Editor:</strong> The <a href="https://dependability.us/about/">Dependability Holdings LLC</a> Research Desk has tracked derivatives market structure and options positioning since the firm&rsquo;s launch in <time datetime="2019">2019</time>, with a documented methodology and the &ldquo;How we forecast&rdquo; page that anchors every brief on the site.</p>
 <p><strong>Launched:</strong> Dependability went live in <time datetime="2024-03">March 2024</time> as a single weekday morning brief covering S&amp;P 500 levels, VIX dynamics, and what to do with options positions that week. Today it publishes a daily morning analysis and a weekly forecast. The journal of executed trades &mdash; every closed position with timestamp, brokerage reconciliation, and post-mortem &mdash; lives on <a href="https://tredey.com/forecasts/">tredey.com</a>.</p>
 <p><strong>Editorial process:</strong> Each piece distils primary reporting (Cboe options data, OCC positioning, FRED macro series, SEC filings, Federal Reserve releases) into a worked-example frame: <em>what the data says, why it matters, what to do this week</em>. Forecasts are screened against the <a href="/forecast/">forecast archive</a> and cross-checked against at least one confirming primary source before publication. Forecasts that turn out wrong receive a <a href="/archive/">post-mortem</a> within 30 days.</p>
 <p><strong>Corrections policy:</strong> When an article gets a fact wrong, we correct it inline and append a dated correction note at the top of the next morning brief. Send corrections to <a href="mailto:corrections@dependability.us">corrections@dependability.us</a> &mdash; we aim to acknowledge within 48 hours.</p>
 <p><strong>Disclosure:</strong> Dependability Holdings LLC is a research entity, not a registered investment adviser or broker-dealer. Nothing on this site is investment advice or a recommendation to buy, sell, or hold any security. The desk may hold positions mentioned in any article; the journal of closed trades is on <a href="https://tredey.com/forecasts/">tredey.com</a>.</p>
</section>

 </main>

 <div style="margin:2rem 0;padding:.75rem;background:var(--surface);border-radius:var(--radius);text-align:center;">
 <ins class="adsbygoogle" style="display:block" data-ad-client="ca-pub-9312870448453345" data-ad-slot="1216992329" data-ad-format="auto" data-full-width-responsive="true"></ins>
 </div>
 <script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script>

 <div id="site-footer"></div>

 <script src="/nav.js"></script>
 <script src="/footer.js"></script>

</body>
</html>
"""


def find_date_dirs():
    """Find all YYYY-MM-DD directories under commentary/ that have index.html."""
    out = []
    for entry in COMMENTARY_DIR.iterdir():
        if not entry.is_dir():
            continue
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", entry.name)
        if not m:
            continue
        try:
            d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            continue
        idx = entry / "index.html"
        if idx.exists() and idx.stat().st_size > 0:
            out.append((d, idx))
    out.sort(key=lambda x: x[0], reverse=True)
    return out


# Defense-in-depth (added 2026-08-28 from Perplexity audit):
# The morning cron occasionally emits the Sources + Disclaimer pair twice in a
# per-date HTML (once in the MD body, then again at the end of the rendered
# article-body). If we render that HTML into commentary/index.html unchanged,
# the duplication ships to production. detect_and_strip_dup_footer() walks each
# per-date HTML and removes the duplicate pair + any intervening <hr>. Idempotent.
_DUP_SOURCES_RE = re.compile(
    r"<p>\s*<em>\s*Sources:.*?</em>\s*</p>", re.IGNORECASE | re.DOTALL,
)
_DUP_DISCLAIMER_RE = re.compile(
    r"<p>\s*<em>\s*Disclaimer:.*?</em>\s*</p>", re.IGNORECASE | re.DOTALL,
)
_DUP_HR_RE = re.compile(
    r"<hr[^>]*>\s*", re.IGNORECASE,
)


def detect_and_strip_dup_footer(html: str) -> tuple[str, dict]:
    """Strip duplicate Sources + Disclaimer footer blocks from a per-date HTML.

    Strategy: find the FIRST Sources block and FIRST Disclaimer block. Treat
    everything between them (inclusive) as the legitimate "footer run".
    Anything AFTER the legitimate run that contains another Sources or
    Disclaimer block (plus any intervening <hr>) is a duplicate — strip it.

    Idempotent: re-running on already-clean HTML is a no-op.

    Returns (cleaned_html, stats).
    """
    sources_hits = len(_DUP_SOURCES_RE.findall(html))
    disclaimer_hits = len(_DUP_DISCLAIMER_RE.findall(html))
    stats = {
        "sources_before": sources_hits,
        "disclaimer_before": disclaimer_hits,
        "stripped": False,
    }
    if sources_hits <= 1 and disclaimer_hits <= 1:
        return html, stats

    # Find positions of first Sources and first Disclaimer
    first_sources_m = _DUP_SOURCES_RE.search(html)
    first_disclaimer_m = _DUP_DISCLAIMER_RE.search(html)
    if not first_sources_m or not first_disclaimer_m:
        return html, stats

    # Define the "legitimate footer run" as the span from the earlier of the
    # two first-occurrences to the later one. Anything past that point is the
    # duplicate run to strip.
    first_pos = min(first_sources_m.start(), first_disclaimer_m.start())
    last_pos = max(first_sources_m.end(), first_disclaimer_m.end())

    # Find the start of the duplicate run: scan forward from last_pos looking
    # for the next <hr> or next duplicate Sources/Disclaimer block.
    scan = last_pos
    # Skip whitespace
    scan += len(html[last_pos:]) - len(html[last_pos:].lstrip())
    # Match the duplicate region: any <hr> + Sources/Disclaimer blocks + whitespace
    dup_pattern = re.compile(
        r"(?:\s*<hr[^>]*>\s*|\s*<p>\s*<em>\s*(?:Sources|Disclaimer):.*?</em>\s*</p>)+",
        re.IGNORECASE | re.DOTALL,
    )
    dup_match = dup_pattern.match(html, scan)
    if not dup_match:
        return html, stats

    # Strip from the start of the duplicate region to its end.
    cleaned = html[:scan] + html[dup_match.end():]
    sources_after = len(_DUP_SOURCES_RE.findall(cleaned))
    disclaimer_after = len(_DUP_DISCLAIMER_RE.findall(cleaned))
    stats["sources_after"] = sources_after
    stats["disclaimer_after"] = disclaimer_after
    stats["stripped"] = (sources_after != sources_hits or disclaimer_after != disclaimer_hits)
    return cleaned, stats


def dedup_per_date_htmls(dates: list) -> int:
    """Strip duplicate footers from all per-date HTMLs that need it.

    Called by main() before any rendering. Idempotent. Returns the count of
    files that were patched in this run (for logging).
    """
    patched = 0
    for d, path in dates:
        try:
            html = path.read_text()
        except Exception:
            continue
        cleaned, stats = detect_and_strip_dup_footer(html)
        if stats["stripped"]:
            tmp = path.with_suffix(".html.tmp")
            tmp.write_text(cleaned)
            os.replace(tmp, path)
            print(
                f"  dedup: {d.isoformat()} — sources {stats['sources_before']}→{stats.get('sources_after','?')}, "
                f"disclaimer {stats['disclaimer_before']}→{stats.get('disclaimer_after','?')}"
            )
            patched += 1
    return patched


def extract_title(html):
    """Extract the H2 hero title from a per-date article page."""
    m = re.search(r'<h2 style="margin-bottom:16px;[^"]*">(.+?)</h2>', html, re.DOTALL)
    return m.group(1).strip() if m else "Morning Market Analysis"


def extract_lead(html):
    """Extract the italicized lead paragraph."""
    m = re.search(
        r'<p style="font-size:\.95rem;color:#666;line-height:1\.5;margin-bottom:16px;font-style:italic;text-align:center;">(.+?)</p>',
        html, re.DOTALL
    )
    return m.group(1).strip() if m else ""


def extract_body_inner_html(html):
    """
    Extract inner HTML of the article-body div (the brief body, not ads/eeat).

    Walks balanced <div> tags from the opening <div class="article-body"> until
    the matching </div>. Previous regex attempts (matching </div> non-greedy or
    matching <!-- topic: as a sentinel) broke when the body contains ads as
    nested <div style="..."> or topic-comment markers inside the body.
    """
    start_marker = '<div class="article-body">'
    pos = html.find(start_marker)
    if pos < 0:
        return ""

    # Skip past the opening tag's closing '>'.
    open_end = html.find('>', pos)
    if open_end < 0:
        return ""
    cursor = open_end + 1

    depth = 1
    while cursor < len(html) and depth > 0:
        # Look at next <div ...> open vs </div> close.
        next_open = html.find('<div', cursor)
        next_close = html.find('</div>', cursor)
        if next_close < 0:
            return ""  # malformed

        if next_open >= 0 and next_open < next_close:
            # Skip past the opening tag.
            tag_end = html.find('>', next_open)
            if tag_end < 0:
                return ""
            # Skip self-closing div tags (<div ... />): they don't add depth.
            if html[tag_end - 1] == '/':
                cursor = tag_end + 1
            else:
                depth += 1
                cursor = tag_end + 1
        else:
            depth -= 1
            if depth == 0:
                return html[open_end + 1:next_close].strip()
            cursor = next_close + len('</div>')

    return ""


def extract_title_xml(title):
    """Strip HTML tags for use in an HTML attribute (meta description)."""
    s = re.sub(r'<[^>]+>', '', title).strip()
    s = s.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
    return s


def format_human_date(d):
    """Format as 'August 26, 2026'."""
    return d.strftime("%B %-d, %Y")


def build_index_html(dates, today):
    if not dates:
        return "<!-- No morning briefs found. -->", "<!-- No morning briefs found. -->"

    latest_date, latest_path = dates[0]
    latest_html = latest_path.read_text()

    title = extract_title(latest_html)
    lead = extract_lead(latest_html)
    body_inner = extract_body_inner_html(latest_html)
    today_long = format_human_date(latest_date)
    title_xml = extract_title_xml(title)

    # Archive: skip latest (hero), take next 7
    archive = dates[1:8]
    archive_cards = []
    for d, p in archive:
        h = p.read_text()
        t = extract_title(h)
        l = extract_lead(h)
        if len(l) > 200:
            l = l[:197].rstrip() + "..."
        date_iso = d.isoformat()
        archive_cards.append(
            "<div class=\"archive-item\">\n"
            " <div class=\"archive-meta\">\n"
            f"  <a href=\"/commentary/{date_iso}/\" class=\"archive-date\">{date_iso}</a>\n"
            "  <span class=\"category-label\" style=\"color:#c8001e;\">Morning Market Analysis</span>\n"
            " </div>\n"
            f" <h2><a href=\"/commentary/{date_iso}/\">{t}</a></h2>\n"
            f" <p>{l}</p>\n"
            "</div>"
        )
    archive_html = "\n".join(archive_cards) if archive_cards else "<p><em>No prior briefs.</em></p>"

    prev_link_html = ""
    if len(dates) >= 2:
        prev_d = dates[1][0]
        prev_iso = prev_d.isoformat()
        prev_human = format_human_date(prev_d)
        prev_link_html = (
            f'<a href="/commentary/{prev_iso}/" class="article-prev-link">'
            f'<span class="article-prev-link__arrow">←</span>'
            f'<span>Previous: {prev_human}</span></a>'
        )

    return HEAD_TEMPLATE.format(
        title=title,
        title_xml=title_xml,
        lead=lead,
        today_long=today_long,
        body_inner=body_inner,
        archive_html=archive_html,
        prev_link_html=prev_link_html,
    ), latest_date.isoformat()


def main():
    dates = find_date_dirs()
    if not dates:
        print(f"ERROR: No morning briefs found in {COMMENTARY_DIR}")
        return 1

    # Defense-in-depth (2026-08-28): strip any per-date HTML that has duplicate
    # Sources + Disclaimer footer blocks. The morning cron's LLM step
    # occasionally emits these twice; the verify_published.py post-build gate
    # catches it but we'd rather fix it upstream before any rendering.
    patched = dedup_per_date_htmls(dates)
    if patched:
        print(f"Dedup pass: patched {patched} per-date HTML file(s)")

    today = date.today()
    html, featured_iso = build_index_html(dates, today)

    tmp = INDEX_PATH.with_suffix(".html.tmp")
    tmp.write_text(html)
    os.replace(tmp, INDEX_PATH)

    print(f"Wrote commentary/index.html (today={today.isoformat()}, featured={featured_iso}, archive_count={len(dates)-1})")
    for d, _ in dates[:10]:
        print(f"  - {d.isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
