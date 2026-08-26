#!/usr/bin/env python3
"""
build.py — Dependability.us Site Generator

Reads Markdown files from content/articles/ and content/forecasts/ and generates:
  - index.html               (homepage: featured + MARKET COMMENTARY + EDUCATION)
  - articles/<slug>.html     (individual article pages)
  - commentary.html          (all MARKET COMMENTARY articles, sorted by date)
  - education.html           (all EDUCATION articles, sorted by date)
  - strategies.html          (static strategies page)
  - forecast.html           (S&P 500 & VIX forecast — from most-recent forecast MD)

Run: python3 build.py
Output: writes to OUTPUT_DIR (same directory as this script)
"""

import os
import re
from pathlib import Path

ROOT_ARTICLES = ["the-dollars-lever", "inflation-measurement-modern-economy",
                    "oil-paradox-energy-dominance", "tlt-new-bond-regime",
                    "gold-as-a-store-of-value"]

def article_href(slug: str) -> str:
    """Return correct URL for an article slug — /articles/slug/ or /slug/ for root articles.
    Always includes trailing slash to avoid CF Pages 308 redirect."""
    return f"/{slug}/" if slug in ROOT_ARTICLES else f"/articles/{slug}/"


# Image dimensions cache — written by optimize_images.py at build time.
# Maps source PNG filename -> { webp, width, height } for accurate CLS reservation.
_IMG_DIMS_CACHE: dict[str, dict] = {}
_IMG_DIMS_LOADED = False


def load_image_dims() -> dict:
    """Lazy-load image dimensions cache written by optimize_images.py."""
    global _IMG_DIMS_CACHE, _IMG_DIMS_LOADED
    if _IMG_DIMS_LOADED:
        return _IMG_DIMS_CACHE
    cache_path = OUTPUT_DIR / "articles" / ".imgdims.json"
    if cache_path.exists():
        try:
            _IMG_DIMS_CACHE = json.loads(cache_path.read_text())
        except Exception:
            _IMG_DIMS_CACHE = {}
    _IMG_DIMS_LOADED = True
    return _IMG_DIMS_CACHE


def resolve_image(src: str) -> tuple[str, int, int]:
    """Resolve a /articles/... reference to a (webp_src, width, height) triple.

    Falls back to .png if no WebP exists, and to 1200x630 if no dimensions
    are cached. Strips leading '/articles/' before lookup.
    """
    if not src:
        return "", 0, 0
    # Normalize: /articles/2026-06-18-feds-new-era-kevin-warsh.png
    #       ->  2026-06-18-feds-new-era-kevin-warsh.png
    fname = src.rsplit("/", 1)[-1]
    dims = load_image_dims()
    info = dims.get(fname)
    if info:
        # The on-disk file is the WebP variant
        return f"/articles/{info['webp']}", info["width"], info["height"]
    # Fall back: convert .png to .webp optimistically
    if fname.endswith(".png"):
        webp_fname = fname[:-4] + ".webp"
        webp_path = OUTPUT_DIR / "articles" / webp_fname
        if webp_path.exists():
            return f"/articles/{webp_fname}", 1200, 675
    return src, 1200, 630  # last-ditch fallback


def image_tag(src: str, alt: str, is_hero: bool = False) -> str:
    """Render an <img> tag with proper performance attributes.

    - Hero/LCP image: loading=eager + fetchpriority=high + decoding=async.
    - Body image: loading=lazy + decoding=async.
    - Both: explicit width/height matching the actual image (CLS = 0).
    - If src is empty/None, returns '' (no broken <img> tag).
    - WebP is preferred; we point the browser at the smallest variant.
    """
    if not src:
        return ""
    webp_src, w, h = resolve_image(src)
    if not webp_src:
        return ""
    if is_hero:
        perf_attrs = 'loading="eager" fetchpriority="high"'
    else:
        perf_attrs = 'loading="lazy"'
    return (
        f'<img src="{webp_src}" alt="{alt}" width="{w}" height="{h}" '
        f'style="width:100%;height:auto;display:block;" '
        f'decoding="async" {perf_attrs}>'
    )


# ── Config ────────────────────────────────────────────────────────────────────
CONTENT_DIR       = Path(__file__).parent.parent / "content" / "articles"
FORECAST_CONTENT_DIR = Path(__file__).parent.parent / "content" / "forecasts"
BANNER_CONTENT_DIR = Path(__file__).parent.parent / "content" / "banners"
OUTPUT_DIR   = Path(__file__).parent.parent / "website"
TEMPLATE_DIR = Path(__file__).parent

BASE_URL        = "https://dependability.us"
SHARE_BAR_HTML  = """
<div class="share-bar">
  <span class="share-label">Share</span>
  <a class="share-btn share-x" href="#" target="_blank" rel="noopener" aria-label="Share on X">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.744l7.73-8.835L1.254 2.25H8.08l4.259 5.63 5.905-5.63Zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
  </a>
  <a class="share-btn share-facebook" href="#" target="_blank" rel="noopener" aria-label="Share on Facebook">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg>
  </a>
  <a class="share-btn share-linkedin" href="#" target="_blank" rel="noopener" aria-label="Share on LinkedIn">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>
  </a>
  <button class="share-btn share-copy" aria-label="Copy link" onclick="navigator.clipboard.writeText(window.location.href).then(()=>{this.querySelector('.copy-label').textContent='Copied!';setTimeout(()=>{this.querySelector('.copy-label').textContent='Copy'},2000)})">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
    <span class="copy-label">Copy</span>
  </button>
</div>"""

SHARE_BAR_JS    = """
<script>
document.querySelectorAll('.share-x, .share-facebook, .share-linkedin').forEach(function(el) {
  var url = encodeURIComponent(window.location.href);
  var title = encodeURIComponent(document.title);
  if (el.classList.contains('share-x')) el.href = 'https://x.com/intent/tweet?url=' + url + '&text=' + title;
  if (el.classList.contains('share-facebook')) el.href = 'https://www.facebook.com/sharer/sharer.php?u=' + url;
  if (el.classList.contains('share-linkedin')) el.href = 'https://www.linkedin.com/sharing/share-offsite/?url=' + url;
});
</script>"""

ADSENSE_BLOCK = """
<!-- topic: stocks, options, market, investing, S&P 500, VIX, volatility, Federal Reserve, FOMC -->
<div style="margin:2rem 0;padding:.75rem;background:var(--surface);border-radius:var(--radius);text-align:center;">
  <div style="font-size:.75rem;color:#666;margin-bottom:6px;">Advertisement</div>
  <ins class="adsbygoogle" style="display:block" data-ad-client="ca-pub-9312870448453345" data-ad-slot="7590828986" data-ad-format="auto" data-full-width-responsive="true"></ins>
</div>
<script>(adsbygoogle = window.adsbygoogle || []).push({});</script>"""

ADSENSE_BLOCK_SQUARE = """
<!-- topic: stocks, options, market, investing, S&P 500, VIX, volatility, Federal Reserve, FOMC -->
<div style="margin:2rem 0;padding:.75rem;background:var(--surface);border-radius:var(--radius);text-align:center;">
  <div style="font-size:.75rem;color:#666;margin-bottom:6px;">Advertisement</div>
  <ins class="adsbygoogle" style="display:inline-block;width:336px;height:280px" data-ad-client="ca-pub-9312870448453345" data-ad-slot="1328672966"></ins>
</div>
<script>(adsbygoogle = window.adsbygoogle || []).push({});</script>"""

ADSENSE_BLOCK_HORIZONTAL = """
<!-- topic: stocks, options, market, investing, S&P 500, VIX, volatility, Federal Reserve, FOMC -->
<div style="margin:2rem 0;padding:.75rem;background:var(--surface);border-radius:var(--radius);text-align:center;">
  <div style="font-size:.75rem;color:#666;margin-bottom:6px;">Advertisement</div>
  <ins class="adsbygoogle" style="display:block" data-ad-client="ca-pub-9312870448453345" data-ad-slot="1216992329" data-ad-format="auto" data-full-width-responsive="true"></ins>
</div>
<script>(adsbygoogle = window.adsbygoogle || []).push({});</script>"""


def _adsense_topic_from_meta(meta: dict) -> str:
    """Build a short topic-string for AdSense context hints from page frontmatter.

    Returns 3-8 keywords, comma-separated, that describe the page's primary topic.
    Used to inject a hidden HTML comment before each AdSense block, which gives
    the AdSense crawler a topical context hint that tends to lift eCPM.

    Falls back to "stocks, options, market, investing" if no useful metadata.
    """
    if not meta:
        return "stocks, options, market, investing"
    parts: list[str] = []

    # 1. Category (article vs forecast)
    cat = meta.get("category")
    if isinstance(cat, str) and cat.strip():
        parts.append(cat.strip())

    # 2. Tags (up to 4)
    tags = meta.get("tags") or []
    if isinstance(tags, list):
        for t in tags[:4]:
            if isinstance(t, str) and t.strip() and t.strip() not in parts:
                parts.append(t.strip())

    # 3. Tickers (up to 4, mentioned in the page)
    tickers = meta.get("tickers") or []
    if isinstance(tickers, list):
        for t in tickers[:4]:
            if isinstance(t, str) and t.strip() and t.strip() not in parts:
                parts.append(t.strip())

    # 4. Title keywords
    title = meta.get("title", "")
    if isinstance(title, str) and title:
        import re as _re
        clean = _re.sub(r"[^A-Za-z\s]", " ", title)
        title_words = [w for w in clean.split() if len(w) > 3][:3]
        for w in title_words:
            if w.lower() not in (p.lower() for p in parts):
                parts.append(w)

    if not parts:
        return "stocks, options, market, investing"

    return ", ".join(parts[:8])


def inject_adsense_into_body(body_html: str, topic: str = "") -> str:
    """Inject SQUARE ad after first </p> and VERTICAL ad after second </p> in body_html.
    Returns body_html unchanged if fewer than 2 </p> tags exist.

    Optional `topic` string: when provided, an HTML comment `<!-- topic: ... -->`
    is emitted immediately before each injected AdSense block. This is invisible
    to users but gives the AdSense crawler a topical context hint, which tends
    to lift eCPM. If empty, no comment is emitted.
    """
    if not body_html:
        return body_html
    topic_prefix = f"<!-- topic: {topic} -->\n" if topic else ""
    first = body_html.find("</p>")
    if first == -1:
        return body_html
    body_html = body_html[:first + len("</p>")] + "\n" + topic_prefix + ADSENSE_BLOCK_SQUARE + body_html[first + len("</p>"):]
    second = body_html.find("</p>", first + len("</p>") + len(topic_prefix) + len(ADSENSE_BLOCK_SQUARE))
    if second == -1:
        return body_html
    body_html = body_html[:second + len("</p>")] + "\n" + topic_prefix + ADSENSE_BLOCK + body_html[second + len("</p>"):]
    return body_html

# ── Front Matter Parser ─────────────────────────────────────────────────────────
def parse_front_matter(content: str) -> tuple[dict, str]:
    """Return (metadata_dict, body_text) from MD file content."""
    stripped = content.lstrip('\n')
    if not stripped.startswith("---"):
        return {}, content
    end = stripped.find("\n---", 4)
    if end == -1:
        return {}, content
    fm_text = stripped[4:end]
    body    = stripped[end + 4:].lstrip("\n")

    meta = {}
    for line in fm_text.split("\n"):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        colon_idx = line.find(':')
        if colon_idx == -1:
            continue
        key = line[:colon_idx].strip()
        val = line[colon_idx+1:].strip()
        if val in ("null", "None"):
            meta[key] = None
        elif val in ("true", "True"):
            meta[key] = True
        elif val in ("false", "False"):
            meta[key] = False
        elif (val.startswith('"') and val.endswith('"')) or \
             (val.startswith("'") and val.endswith("'")):
            meta[key] = val[1:-1]
        else:
            meta[key] = val
    return meta, body


def slug_from_path(path: Path) -> str:
    return path.stem


# ── MD Body → HTML ─────────────────────────────────────────────────────────────
def md_to_html(body: str) -> str:
    """Convert simple Markdown to HTML paragraph block.
    Supports headers, lists, blockquotes, links, **bold**/*italic*/`code`,
    and pipe-delimited tables (GitHub-flavored)."""
    lines = body.split("\n")
    html_parts = []
    in_ul = False
    in_ol = False
    in_table = False
    table_lines = []

    def wrap_inline(text: str) -> str:
        # Markdown inline links: [text](url) — must run before bold/italic
        # substitution so the [text] inside the link isn't mangled. External
        # URLs (http/https) get target="_blank" rel="noopener"; internal
        # .md paths get rewritten to .html by the post-pass after flush.
        def _inline_link(m):
            link_text = m.group(1)
            link_url = m.group(2)
            extra = ' target="_blank" rel="noopener"' if link_url.startswith(("http://", "https://")) else ""
            return f'<a href="{link_url}"{extra} style="color:#c8a96e;text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:2px;">{link_text}</a>'
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _inline_link, text)
        # Insert a space between consecutive citation links. The MD source
        # pattern [a](url)[b](url) renders as </a><a ...> with no separator,
        # producing concatenated visible text like "mckinseywilliamblair".
        # This defensive pass catches any citation clusters that slip past
        # the source-side spacing convention. (2026-07-10 fix per Mike.)
        text = re.sub(r"</a>(\s*)</a>", r"</a> </a>", text)
        text = re.sub(r"</a>(<a )", r"</a> <a ", text)
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"\*(.+?)\*",      r"<em>\1</em>",         text)
        text = re.sub(r"`(.+?)`",         r"<code>\1</code>",     text)
        return text

    def flush_table():
        nonlocal in_table, table_lines
        if not in_table:
            return ""
        rows = []
        for tl in table_lines:
            tl = tl.strip()
            if not tl.startswith("|"):
                continue
            cells = [c.strip() for c in tl.split("|")]
            if cells and cells[0] == "":
                cells = cells[1:]
            if cells and cells[-1] == "":
                cells = cells[:-1]
            rows.append(cells)
        rows = [
            r for r in rows
            if not all(re.fullmatch(r":?-{3,}:?", c) for c in r if c)
        ]
        in_table = False
        table_lines = []
        if len(rows) < 2:
            return ""
        header = rows[0]
        body_rows = rows[1:]
        # Detect text columns (Notes, Rationale, etc.) — left-align those.
        # Otherwise the first column is left-aligned and the rest are right-aligned
        # (good for numeric / percentage columns).
        TEXT_HEADERS = {
            "notes", "rationale", "commentary", "reason", "driver",
            "catalyst", "thesis", "description", "metric", "sector",
            "industry", "ticker", "name", "label", "firm",
        }
        text_columns = {
            i for i, h in enumerate(header)
            if h.strip().lower() in TEXT_HEADERS
        }
        th_style = "text-align:left;padding:10px 12px;border-bottom:2px solid #c8001e;background:#f9f9f9;font-weight:600;font-size:0.8rem;letter-spacing:0.04em;text-transform:uppercase;"
        out = ['<div style="overflow-x:auto;margin:1.25rem 0;">']
        out.append('<table style="width:100%;border-collapse:collapse;font-size:0.95rem;">')
        out.append("<thead><tr>")
        for cell in header:
            out.append(f'<th style="{th_style}">{wrap_inline(cell)}</th>')
        out.append("</tr></thead>")
        out.append("<tbody>")
        for r in body_rows:
            out.append("<tr>")
            for i, cell in enumerate(r):
                if i == 0 or i in text_columns:
                    cell_style = "padding:10px 12px;border-bottom:1px solid #e0e0e0;text-align:left;"
                    if i == 0:
                        cell_style += "font-weight:500;"
                else:
                    cell_style = "padding:10px 12px;border-bottom:1px solid #e0e0e0;text-align:right;font-variant-numeric:tabular-nums;"
                out.append(f'<td style="{cell_style}">{wrap_inline(cell)}</td>')
            out.append("</tr>")
        out.append("</tbody></table></div>")
        return "\n".join(out)

    for raw in lines:
        line = raw.strip()

        if line in ("---", "----"):
            continue

        # Pipe-delimited table detection: collect contiguous | lines, flush on non-table.
        if line.startswith("|") and line.endswith("|") and line.count("|") >= 2:
            if not in_table:
                in_table = True
                table_lines = []
            table_lines.append(line)
            continue
        else:
            if in_table:
                html_parts.append(flush_table())

        if line.startswith("#### "):
            html_parts.append(f"<h4>{wrap_inline(line[5:])}</h4>")
            continue
        elif line.startswith("### "):
            html_parts.append(f"<h3>{wrap_inline(line[4:])}</h3>")
            continue
        elif line.startswith("## "):
            html_parts.append(f"<h2>{wrap_inline(line[3:])}</h2>")
            continue
        elif line.startswith("# "):
            html_parts.append(f"<h1>{wrap_inline(line[2:])}</h1>")
            continue

        if line.startswith("- ") or line.startswith("* "):
            if not in_ul:
                html_parts.append("<ul>")
                in_ul = True
            html_parts.append(f"  <li>{wrap_inline(line[2:])}</li>")
            continue
        else:
            if in_ul:
                html_parts.append("</ul>")
                in_ul = False

        m = re.match(r"^\d+\.\s+(.*)$", line)
        if m:
            if not in_ol:
                html_parts.append("<ol>")
                in_ol = True
            html_parts.append(f"  <li>{wrap_inline(m.group(1))}</li>")
            continue
        else:
            if in_ol:
                html_parts.append("</ol>")
                in_ol = False

        if line.startswith("> "):
            html_parts.append(f"<blockquote>{wrap_inline(line[2:])}</blockquote>")
            continue

        # Markdown links: [text](url)
        m_link = re.match(r"^\[([^\]]+)\]\(([^)]+)\)", line.strip())
        if m_link:
            link_text = m_link.group(1)
            link_url = m_link.group(2)
            extra = ' target="_blank" rel="noopener"' if link_url.startswith("http") else ""
            html_parts.append(f'<p><a href="{link_url}"{extra}>{link_text}</a></p>')
            continue

        if not line:
            continue

        html_parts.append(f"<p>{wrap_inline(line)}</p>")

    # Flush any trailing table at EOF
    if in_table:
        html_parts.append(flush_table())

    html = "\n".join(html_parts)

    def md_to_html_link(m):
        href = m.group(1)
        rest = m.group(2)
        if href.endswith('.md'):
            href = href[:-3] + '.html'
        return f'href="{href}"{rest}'

    html = re.sub(r'href="([^"]+\.md)"([^>]*?)(?=>|\s)', md_to_html_link, html)

    return html


# ── Load Template ───────────────────────────────────────────────────────────────
def load_template(name: str) -> str:
    p = TEMPLATE_DIR / name
    if p.exists():
        return p.read_text(encoding="utf-8")
    return ""


def wrap_in_template(page_title: str, page_desc: str, main_html: str,
                     active_nav: str = "", canonical_url: str = "",
                     lcp_preload: str = "") -> str:
    tmpl = load_template("_template.html")
    tmpl = tmpl.replace("PAGE TITLE",       page_title,  1)
    tmpl = tmpl.replace("PAGE DESCRIPTION",  page_desc,  1)
    tmpl = tmpl.replace("<!-- PAGE CONTENT GOES HERE -->", main_html, 1)
    if canonical_url:
        safe = canonical_url if canonical_url.startswith('http') else BASE_URL + canonical_url
        tmpl = tmpl.replace("CANONICAL_PLACEHOLDER", safe, 1)
    if lcp_preload:
        tmpl = tmpl.replace(
            "<!-- LCP_PRELOAD -->",
            f'<link rel="preload" as="image" href="{lcp_preload}" fetchpriority="high">',
            1,
        )
    if active_nav:
        tmpl = re.sub(
            rf'href="/{active_nav}"',
            f'href="/{active_nav}" class="active"',
            tmpl
        )
    return tmpl


STYLE_BLOCK = """
<style>
 .share-bar { display: flex; align-items: center; gap: 10px; margin: 40px 0 32px; padding: 16px 0; border-top: 1px solid #e8e4dd; border-bottom: 1px solid #e8e4dd; }
 .share-label { font-size: 11px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: #999; margin-right: 4px; }
 .share-btn { display: inline-flex; align-items: center; gap: 5px; padding: 7px 12px; border-radius: 4px; font-size: 12px; text-decoration: none; border: 1px solid #cc0000; background: transparent; cursor: pointer; font-family: inherit; color: #cc0000; transition: opacity 0.15s; }
 .share-btn:hover { opacity: 0.7; }
 .disclaimer { margin: 2.5rem 0; padding: 1rem 1.25rem; background: #f5f0e8; border-left: 4px solid #cc0000; font-size: 0.875rem; line-height: 1.6; color: #555; }
 .article-body h2 { font-size: 1.5rem; margin-top: 2rem; margin-bottom: 1rem; }
 .article-body h3 { font-size: 1.25rem; margin-top: 1.5rem; margin-bottom: 0.75rem; }
 .article-body p { margin-bottom: 1.25rem; font-size: 1.0625rem; line-height: 1.8; color: #222222; }
 .article-body strong { font-weight: 600; color: #1a1a1a; }
 .article-body blockquote { margin: 1.5rem 0; padding: 1rem 1.25rem; background: #f5f0e8; border-left: 4px solid #c8001e; font-size: 1rem; line-height: 1.6; color: #444; }
 .article-body ul, .article-body ol { margin-bottom: 1.25rem; padding-left: 1.5rem; }
 .article-body li { margin-bottom: 0.5rem; font-size: 1.0625rem; line-height: 1.8; }
 /* E-E-A-T block (baked into every article) — anti-pattern #89 fix */
 .eeat-block { background: #f5f0e8; border: 1px solid #e0dccd; border-left: 4px solid #c8001e; border-radius: 4px; padding: 1.25rem 1.5rem; margin: 1.5rem 0 2rem; font-size: 0.9375rem; line-height: 1.7; color: #333; }
 .eeat-block h2 { font-size: 0.75rem; letter-spacing: 0.1em; text-transform: uppercase; color: #c8001e; margin: 0 0 0.85rem; font-weight: 700; font-family: inherit; }
 .eeat-block p { margin: 0 0 0.7rem; }
 .eeat-block p:last-child { margin-bottom: 0; }
 .eeat-block a { color: #c8001e; text-decoration: underline; text-decoration-thickness: 1px; text-underline-offset: 2px; }
 .eeat-block a:hover { color: #1a1a1a; }
 .eeat-block time { font-weight: 500; }
</style>
"""


# ── E-E-A-T block (baked into every forecast + article page) ────────────────────
# Anti-pattern #89 fix: E-E-A-T must live in the build template so it's
# regenerated on every cron run. Hand-editing HTML alone gets wiped.
# Recipe: named_editor, credentials, launch_date, editorial_process,
# corrections_policy, disclosure (Mike's E-E-A-T standard, 2026-08-23).
DEPENDABILITY_EEAT_BLOCK = """
<section class="eeat-block" aria-label="About this article">
 <h2>About this article</h2>
 <p><strong>Editor:</strong> The <a href="https://dependability.us/about/">Dependability Holdings LLC</a> Research Desk has tracked derivatives market structure and options positioning since the firm's launch in <time datetime="2019">2019</time>, with a documented public position tracker and the &ldquo;How we forecast&rdquo; methodology that anchors every brief on the site.</p>
 <p><strong>Launched:</strong> Dependability went live in <time datetime="2024-03">March 2024</time> as a single weekday morning brief covering S&amp;P 500 levels, VIX dynamics, and what to do with options positions that week. Today it publishes a daily morning analysis, a weekly forecast, and a public <a href="/trade-log/">position tracker</a> for every published position the desk holds in its own portfolio. The journal of executed trades lives on <a href="https://tredey.com/forecasts/">tredey.com</a>.</p>
 <p><strong>Editorial process:</strong> Each piece distils primary reporting (Cboe options data, OCC positioning, FRED macro series, SEC filings, Federal Reserve releases) into a worked-example frame: <em>what the data says, why it matters, what to do this week</em>. Forecasts are screened against the <a href="/forecast/">forecast archive</a> and cross-checked against at least one confirming primary source before publication. Forecasts that turn out wrong receive a <a href="/archive/">post-mortem</a> within 30 days.</p>
 <p><strong>Corrections policy:</strong> When an article gets a fact wrong, we correct it inline and append a dated correction note at the top of the next morning brief. Send corrections to <a href="mailto:corrections@dependability.us">corrections@dependability.us</a> &mdash; we aim to acknowledge within 48 hours.</p>
 <p><strong>Disclosure:</strong> Dependability Holdings LLC is a research entity, not a registered investment adviser or broker-dealer. Nothing on this site is investment advice or a recommendation to buy, sell, or hold any security. The desk may hold positions mentioned in any article; the <a href="/trade-log/">position tracker</a> on this site shows current and historical positions held by the desk, and the journal of closed trades is on <a href="https://tredey.com/forecasts/">tredey.com</a>.</p>
</section>
"""


# ── Article Page HTML ────────────────────────────────────────────────────────────
def article_page_html(slug: str, meta: dict, body_html: str) -> str:
    title   = meta.get("title", slug)
    category = meta.get("category", "MARKET COMMENTARY")
    date    = meta.get("date", "")
    author  = meta.get("author", "Dependability Research Desk")
    desc    = meta.get("description", "")
    # Default to empty (not a fake /articles/{slug}.png) so we never
    # emit a broken <img> tag when an article has no featured image.
    img_src = (meta.get("featured_image") or "").strip()
    if img_src and not img_src.startswith('/') and not img_src.startswith('http'):
        img_src = f"/articles/{img_src}"

    # Format date for display: 2026-05-25 → "May 25, 2026"
    date_display = date
    try:
        from datetime import datetime
        d = datetime.strptime(date, "%Y-%m-%d")
        date_display = d.strftime("%B %d, %Y")
    except Exception:
        pass

    ROOT_ARTICLES = ["the-dollars-lever", "inflation-measurement-modern-economy",
                        "oil-paradox-energy-dominance", "tlt-new-bond-regime",
                        "gold-as-a-store-of-value"]
    if slug in ROOT_ARTICLES:
        canonical_url = f"/{slug}/"
    else:
        canonical_url = f"/articles/{slug}/"
    og_img = img_src if (img_src and img_src.startswith('http')) else f"https://dependability.us/og-image.jpg"

    disclaimer = """
    <div class="disclaimer">
     <strong>Disclaimer:</strong> This research is for informational purposes only and does not constitute investment advice. Options trading involves substantial risk of loss. Past performance is not indicative of future results.
    </div>"""

    # Only render the .article-header-image wrapper if there is an actual image.
    hero_block = ""
    if img_src:
        hero_block = (
            f'    <div class="article-header-image">\n'
            f'     {image_tag(img_src, title, is_hero=True)}\n'
            f'    </div>'
        )

    article_html = f"""
   <div class="article-page">

    <div class="article-header">
     <div class="category-label">{category}</div>
     <h1>{title}</h1>
     <div class="article-meta">{date_display} &nbsp;|&nbsp; {author}</div>
    </div>
{hero_block}
{DEPENDABILITY_EEAT_BLOCK}
    <div class="article-body">

{body_html}

    </div>

{disclaimer}

{SHARE_BAR_HTML}

{SHARE_BAR_JS}

   </div>"""

    # Use _article_template.html for article pages (has share-bar CSS).
    # E-E-A-T CSS lives inside STYLE_BLOCK (above) so it's injected together.
    tmpl = load_template("_article_template.html")
    tmpl = tmpl.replace("</head>", f"{STYLE_BLOCK}</head>\n", 1)
    tmpl = tmpl.replace("PAGE TITLE", f"{title} | Dependability Holdings LLC", 1)
    tmpl = tmpl.replace("PAGE TITLE", f"{title} | Dependability Holdings LLC", 1)  # og:title
    tmpl = tmpl.replace("PAGE DESCRIPTION", desc, 1)
    tmpl = tmpl.replace("PAGE DESCRIPTION", desc, 1)  # og:description
    tmpl = tmpl.replace(
        '<meta property="og:image" content="https://dependability.us/articles/YYYY-MM-DD-SLUG.png">',
        f'<meta property="og:image" content="{og_img}">', 1)
    # Ensure canonical is absolute URL (Google prefers absolute canonicals)
    safe_canonical = canonical_url if canonical_url.startswith('http') else BASE_URL + canonical_url
    tmpl = tmpl.replace("CANONICAL_PLACEHOLDER", safe_canonical, 1)
    tmpl = tmpl.replace("<!-- PAGE CONTENT GOES HERE -->", article_html, 1)
    return tmpl


# ── Homepage Featured Article ────────────────────────────────────────────────────
def featured_article_html(slug: str, meta: dict) -> str:
    title    = meta.get("title", slug)
    category = meta.get("category", "MARKET COMMENTARY")
    date     = meta.get("date", "")
    desc     = meta.get("description", "")
    # No fake default — if the MD has no featured_image, we just don't render one.
    img_src  = (meta.get("featured_image") or "").strip()
    if img_src and not img_src.startswith('/') and not img_src.startswith('http'):
        img_src = f"/articles/{img_src}"

    date_display = date
    try:
        from datetime import datetime
        d = datetime.strptime(date, "%Y-%m-%d")
        date_display = d.strftime("%B %d, %Y")
    except Exception:
        pass

    hero_block = ""
    if img_src:
        hero_block = (
            f'     <div class="article-header-image">\n'
            f'      {image_tag(img_src, title, is_hero=True)}\n'
            f'     </div>'
        )

    return f"""     <div class="category-label">{category}</div>
     <div class="date-text">{date_display}</div>
     <h2><a href="/articles/{slug}/">{title}</a></h2>
{hero_block}
     <p>{desc}</p>
     <a href="/articles/{slug}/" class="accent-link" style="font-weight:600;">Read More &#8594;</a>"""


# ── Article Card ────────────────────────────────────────────────────────────────
def article_card_html(slug: str, meta: dict, is_education: bool = False) -> str:
    title    = meta.get("title", slug)
    category = meta.get("category", "EDUCATION")
    date     = meta.get("date", "")
    desc     = meta.get("description", "")
    extra_cls = " education-card" if is_education else ""

    date_display = date
    try:
        from datetime import datetime
        d = datetime.strptime(date, "%Y-%m-%d")
        date_display = d.strftime("%B %d, %Y")
    except Exception:
        pass

    href = article_href(slug)

    return f"""    <div class="article-card{extra_cls}">
     <div class="date-text">{date_display}</div>
     <h3><a href="{href}">{title}</a></h3>
     <p>{desc}</p>
    </div>"""


# ── Commentary / Education Archive Item ─────────────────────────────────────────
def archive_item_html(slug: str, meta: dict) -> str:
    title    = meta.get("title", slug)
    category = meta.get("category", "MARKET COMMENTARY")
    date     = meta.get("date", "")
    desc     = meta.get("description", "")

    date_display = date
    try:
        from datetime import datetime
        d = datetime.strptime(date, "%Y-%m-%d")
        date_display = d.strftime("%B %d, %Y")
    except Exception:
        pass

    root_articles = ["the-dollars-lever", "inflation-measurement-modern-economy",
                     "oil-paradox-energy-dominance", "tlt-new-bond-regime",
                     "gold-as-a-store-of-value"]
    if slug in root_articles:
        href = f"/{slug}/"
    elif slug.startswith("the-"):
        href = f"/{slug}/"
    else:
        href = f"/articles/{slug}/"

    return f"""
    <div class="resource-card" style="padding:1rem;border-bottom:1px solid var(--color-border);">
     <div style="font-size:.7rem;font-weight:600;color:var(--color-accent);letter-spacing:.05em;text-transform:uppercase;margin-bottom:.25rem;">{category}</div>
     <h3 style="font-size:1rem;margin-bottom:.5rem;"><a href="{href}" style="color:#000;">{title}</a></h3>
     <p style="font-size:.85rem;color:#666;line-height:1.5;">{desc}</p>
     <div style="font-size:.75rem;color:#888;margin-top:.25rem;">{date_display}</div>
    </div>"""


# ── Homepage HTML ───────────────────────────────────────────────────────────────
def _featured_hero_block(slug: str, meta: dict) -> str:
    """Render the hero <img> block (or empty string if no featured image)."""
    img_src = (meta.get("featured_image") or "").strip()
    if img_src and not img_src.startswith('/') and not img_src.startswith('http'):
        img_src = f"/articles/{img_src}"
    if not img_src:
        return ""
    title = meta.get("title", slug)
    return (
        '     <div class="article-header-image">\n'
        f'      {image_tag(img_src, title, is_hero=True)}\n'
        '     </div>'
    )


def build_index(articles: list, forecasts: list = None) -> str:
    """Build index.html with featured article + MARKET COMMENTARY grid + EDUCATION grid.

    `forecasts` is a list of (slug, meta, body) sorted newest-first. If provided,
    the sidebar forecast card is generated from the most-recent non-archived
    forecast. If not provided, a sensible-looking but hardcoded fallback is used
    (kept for backwards-compat / testing only).
    """

    commentary = [a for a in articles if a[1].get("category", "").startswith("MARKET COMMENTARY")]
    education  = [a for a in articles if a[1].get("category", "").startswith("EDUCATION")]

    # Sort by date desc
    commentary.sort(key=lambda x: x[1].get("date", ""), reverse=True)
    education.sort(key=lambda x: x[1].get("date", ""), reverse=True)

    # Featured = most recent MARKET COMMENTARY
    featured_slug, featured_meta, _ = commentary[0] if commentary else (articles[0][0], articles[0][1], "")

    # Featured article: get body for description excerpt (skip leading headings)
    _, featured_meta, featured_body = commentary[0] if commentary else (None, articles[0][1], "")
    # Strip the first ## heading from body so description starts with paragraph text
    body_stripped = re.sub(r'^##?\s[^\n]*\n+', '', featured_body, count=1).strip()
    featured_desc = body_stripped[:350].replace('\n', ' ').strip() + ('...' if len(body_stripped) > 350 else '')

    # Latest sidebar: 4 most recent MARKET COMMENTARY (not the featured one)
    latest_sidebar = [a for a in commentary if a[0] != featured_slug][:4]
    sidebar_items = "\n\n".join(
        f"""     <div class="sidebar-article">
      <div class="date-text">{_format_date(m.get("date",""))}</div>
      <h4><a href="{article_href(s)}">{m.get("title",s)}</a></h4>
      <p style="font-size:.85rem;color:#666;margin:.25rem 0 0;line-height:1.5;">{m.get("description","")}</p>
     </div>"""
        for s, m, _ in latest_sidebar
    )

    # Featured article
    featured_html = featured_article_html(featured_slug, featured_meta)

    # Forecasts & Options Strategies: most recent FORECASTS & OPTIONS STRATEGIES articles
    strategies = [a for a in articles if a[1].get("category") == "FORECASTS & OPTIONS STRATEGIES"]
    strategies.sort(key=lambda x: x[1].get("date", ""), reverse=True)
    strategy_cards = "\n".join(article_card_html(s, m) for s, m, _ in strategies[:3])
    edu_cards = "\n".join(article_card_html(s, m, is_education=True) for s, m, _ in education[:3])

    # Forecast — dynamic from latest non-archived forecast MD (sidebar link)
    if forecasts:
        # forecasts sorted newest-first; pick the first one without archived: true
        live_forecast = next((f for f in forecasts if not f[1].get("archived")), None)
        if live_forecast is None:
            live_forecast = forecasts[0]
        fc_slug, fc_meta, _ = live_forecast
        fc_date = _format_date(fc_meta.get("date", ""))
        fc_title = fc_meta.get("title", "S&P 500 Forecast")
        forecast_item = (
            f"<div class=\"sidebar-article\">\n"
            f"      <div class=\"date-text\">{fc_date}</div>\n"
            f"      <h4><a href=\"/forecast/\">{fc_title}</a></h4>\n"
            f"     </div>"
        )
    else:
        # Fallback — should not normally hit this path
        forecast_item = (
            "<div class=\"sidebar-article\">\n"
            "      <div class=\"date-text\">May 22, 2026</div>\n"
            "      <h4><a href=\"/forecast\">S&amp;P 500 Forecast</a></h4>\n"
            "     </div>"
        )

    main_html = f"""
  <!-- HERO SECTION -->
  <section class="hero-section">
   <div class="hero-grid">

    <!-- Featured Article -->
    <div class="hero-featured">
     <div class="date-text">{_format_date(featured_meta.get("date",""))}</div>
     <h2><a href="/articles/{featured_slug}/">{featured_meta.get("title", featured_slug)}</a></h2>
{_featured_hero_block(featured_slug, featured_meta)}
     <p>{featured_desc}</p>
     <a href="/articles/{featured_slug}/" class="accent-link" style="font-weight:600;">Read More &#8594;</a>
    </div>

    <!-- Sidebar -->
    <div class="hero-sidebar">
     <h3>Latest Market Commentary</h3>

{sidebar_items}

{forecast_item}

    </div>
   </div>
  </section>

{ADSENSE_BLOCK_SQUARE}

  <!-- FORECASTS & OPTIONS STRATEGIES SECTION -->
  <section>
   <div class="section-header">
    <h2>FORECASTS & OPTIONS STRATEGIES</h2>
    <a href="/forecast/" class="explore-link">Explore &#8594;</a>
   </div>
   <div class="card-grid">

{strategy_cards}

   </div>
  </section>

  <!-- EDUCATION SECTION -->
  <section>
   <div class="section-header">
    <h2>EDUCATION</h2>
    <a href="/education/" class="explore-link">Explore &#8594;</a>
   </div>
   <div class="card-grid">

{edu_cards}

   </div>
  </section>
{ADSENSE_BLOCK}
"""

    edu_cards = "\n".join(article_card_html(s, m, is_education=True) for s, m, _ in education[:3])

    # Preload the LCP hero image (the featured article on the homepage).
    lcp_preload_src, _, _ = resolve_image(
        (featured_meta.get("featured_image") or "").strip()
    )

    return wrap_in_template(
        "Market Research & Options Analysis | Dependability Holdings LLC",
        "Independent financial research on S&P 500 trends, VIX dynamics, and options strategies for informed investment decisions.",
        main_html,
        active_nav="",
        canonical_url="/",
        lcp_preload=lcp_preload_src,
    )


def _format_date(date_str: str) -> str:
    if not date_str:
        return ""
    try:
        from datetime import datetime
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return d.strftime("%B %d, %Y")
    except Exception:
        return date_str


# ── Commentary Page ──────────────────────────────────────────────────────────────
def build_commentary(articles: list) -> str:
    commentary = sorted(
        [a for a in articles if a[1].get("category", "").startswith("MARKET COMMENTARY")],
        key=lambda x: x[1].get("date", ""), reverse=True
    )

    archive_items = "\n".join(
        archive_item_html(slug, meta)
        for slug, meta, _ in commentary
    )

    main_html = f"""
  <div class="page-hero">
   <h1>Market Commentary</h1>
   <p>Regular analysis from the Dependability Research Desk — market moves, volatility signals, and macro context for options traders.</p>
  </div>

  <div class="page-content">

   <div class="archive-grid" style="display:flex;flex-direction:column;gap:0;">

{archive_items}

   </div>

{ADSENSE_BLOCK}

   <div class="archive-intro" style="max-width:720px;margin:3rem auto;">
    <p style="font-size:1.0625rem;line-height:1.8;color:#333;">The Dependability Research Desk publishes market commentary on a regular cadence — typically several times per week, and more frequently during high-signal events like Federal Reserve meetings, earnings season, or unexpected macro shifts. Each piece is written for active options traders who want more than headlines: they want context, interpretation, and a framework for how to think about what's happening.</p>
    <p style="font-size:0.9375rem;color:#666;"><em>New commentary is published multiple times per week. Sources include Cboe, FRED, SEC filings, and primary macro data from BLS, BEA, and the Federal Reserve.</em></p>
   </div>

{ADSENSE_BLOCK_SQUARE}
  </div>
"""

    return wrap_in_template(
        "VIX & Market Commentary: Live Analysis | Dependability",
        "Live VIX level, contango analysis, and S&P 500 commentary from the Dependability Research Desk. Updated weekly for active traders.",
        main_html,
        active_nav="commentary",
        canonical_url="/commentary/"
    )


# ── Education Page ──────────────────────────────────────────────────────────────
def build_education(articles: list) -> str:
    education = sorted(
        [a for a in articles if a[1].get("category", "").startswith("EDUCATION")],
        key=lambda x: x[1].get("date", ""), reverse=True
    )

    archive_items = "\n".join(
        archive_item_html(slug, meta)
        for slug, meta, _ in education
    )

    main_html = f"""
  <div class="page-hero">
   <h1>Market Education</h1>
   <p>Build your foundation in derivatives, volatility, market structure, and institutional positioning — the core knowledge that separates informed traders from signal chasers.</p>
  </div>

  <div class="page-content">

   <div id="edu-articles" class="archive-grid" style="display:flex;flex-direction:column;gap:0;">

{archive_items}

   </div>

{ADSENSE_BLOCK}

   <div class="archive-intro" style="max-width:720px;margin:3rem auto;">
    <p style="font-size:1.0625rem;line-height:1.8;color:#333;">Our education content is designed for traders who want to build genuine understanding rather than chase signals. Each piece explains the mechanics behind market phenomena, how options pricing works, and what institutional market participants are doing — and why. Sources include Cboe, OCC, SEC filings, and academic literature.</p>
    <p style="font-size:0.9375rem;color:#666;"><em>New education content is added regularly. A strong foundation in the material here makes our market commentary significantly more actionable.</em></p>
   </div>

{ADSENSE_BLOCK_SQUARE}
  </div>
"""

    return wrap_in_template(
        "Market Education | Dependability Holdings LLC",
        "Build your foundation in derivatives, volatility, market structure, and institutional positioning.",
        main_html,
        active_nav="education",
        canonical_url="/education/"
    )


# ── Load MD Articles ────────────────────────────────────────────────────────────
def load_articles() -> list:
    """Load all MD files from content/articles/. Returns [(slug, meta, body), ...]"""
    articles = []
    if not CONTENT_DIR.exists():
        print(f"WARNING: content/articles/ not found at {CONTENT_DIR}")
        return articles
    for path in sorted(CONTENT_DIR.glob("*.md")):
        slug = slug_from_path(path)
        raw = path.read_text(encoding="utf-8")
        meta, body = parse_front_matter(raw)
        meta.setdefault("title", slug)
        meta.setdefault("slug", slug)
        articles.append((slug, meta, body))
    return articles


# ── Forecast Builder ───────────────────────────────────────────────────────────

def load_forecasts():
    """Load all forecast MD files. Returns sorted newest-first.
    Skips 0-byte stub files (which would wipe existing rendered HTML)."""
    forecasts = []
    if not FORECAST_CONTENT_DIR.exists():
        print(f"WARNING: content/forecasts/ not found at {FORECAST_CONTENT_DIR}")
        return forecasts
    skipped = 0
    for path in sorted(FORECAST_CONTENT_DIR.glob("*.md"), reverse=True):
        raw = path.read_text(encoding="utf-8")
        # Skip 0-byte stub files — they would overwrite rendered HTML with empty content.
        # Anti-pattern #91 (locked 2026-08-25): stub MD files must NOT be processed by build.
        if not raw.strip():
            skipped += 1
            continue
        meta, body = parse_front_matter(raw)
        slug = path.stem
        meta.setdefault("title", slug)
        forecasts.append((slug, meta, body))
    if skipped:
        print(f"  Skipped {skipped} empty forecast stub(s).")
    return forecasts


def parse_table_lines(block: str) -> list:
    """Parse pipe-delimited table rows from a markdown block. Returns list of (col1, col2, col3)."""
    rows = []
    for line in block.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("|-") or line == "|" or line.startswith("<!--"):
            continue
        parts = [p.strip() for p in line.split("|")]
        parts = [p for p in parts if p]
        if len(parts) >= 2:
            rows.append(parts)
    return rows


def parse_forecast_body(body: str) -> dict:
    """Split a forecast MD body into named sections using \n___\n as separator.
    The format is:
      [narrative content]
      ___\n      <!-- SECTION_NAME -->\n      [table content]\n      ___\n      <!-- SECTION_NAME -->\n      [content]\n      ___\n      ### CARD: Name\n      [card content]

    Returns dict with keys: narrative_html, target_grid_html, consensus_html,
                            vix_html, cards_html, narrative_h2.
    """
    # Split on ___ boundaries
    blocks = re.split(r"\n___\n", body)
    # blocks[0] = narrative, then alternating: marker_block, cards_block...

    named = {}
    for block in blocks[1:]:  # skip narrative (index 0)
        # First line is <!-- SECTION_NAME -->
        m = re.match(r"<!--\s*(\w+)\s*-->", block.strip())
        if m:
            key = m.group(1)
            content = block[m.end():].strip()
            named[key] = content
        # If no match, it's the cards block (starts with ### CARD:)

    narrative_raw = blocks[0].strip() if blocks else body

    # Extract h2 title from narrative
    h2_match = re.search(r"<h2>(.*?)</h2>", md_to_html(narrative_raw))
    narrative_h2 = h2_match.group(1) if h2_match else "Market Assessment"
    # Strip the h2 from narrative body so it doesn't duplicate
    narrative_for_html = re.sub(r"^## .+?\n", "", narrative_raw, count=1)

    # Build target grid HTML
    target_rows = parse_table_lines(named.get("TARGET_GRID", ""))
    # Skip header row (Label | Value | Sub)
    target_rows = [r for r in target_rows if r[0].upper() not in ("LABEL", "FIRM", "METRIC")]
    target_cells = ""
    for row in target_rows:
        label = row[0]
        value = row[1] if len(row) > 1 else ""
        sub = row[2] if len(row) > 2 else ""
        is_current = label.upper() == "CURRENT"
        label_color = "#888" if is_current else "#c8001e"
        value_color = "#1a1a1a" if is_current else "#1a7a1a"
        sub_color = "#888" if is_current else "#1a7a1a"
        target_cells += f'''
      <div style="text-align:center;">
       <div style="font-size:0.75rem;letter-spacing:0.08em;text-transform:uppercase;color:{label_color};margin-bottom:6px;">{label}</div>
       <div style="font-size:2rem;font-family:Georgia,serif;font-weight:bold;color:{value_color};">{value}</div>
       <div style="font-size:0.8rem;color:{sub_color};">{sub}</div>
      </div>'''
    # Target date label — derived from frontmatter when available, else a year-filtered
    # narrative scan. The frontmatter is the source of truth and avoids matching
    # historical year references (e.g. "Juneteenth (June 19, 1865)") that may appear
    # in narrative text. The narrative-scan fallback is restricted to plausible
    # current-era years (2024-2099) to be defensive.
    target_date_label = ""
    narrative_first = blocks[0].splitlines()[0] if blocks and blocks[0].splitlines() else ""
    date_match = re.search(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+(202[4-9]|20[3-9]\d)",
        narrative_first + " " + blocks[0],
    )
    target_date_label = date_match.group(0) if date_match else ""

    target_grid_html = f'''
   <div style="background:#f9f9f9;border:1px solid #e0e0e0;border-top:3px solid #c8001e;padding:28px;margin-bottom:32px;">
    <div class="category-label" style="margin-bottom:20px;">S&amp;P 500 PRICE TARGETS — {target_date_label}</div>
    <div style="display:grid;grid-template-columns:repeat({len(target_rows)},1fr);gap:20px;">
{target_cells}
    </div>
   </div>'''

    # Build consensus grid HTML
    consensus_rows = parse_table_lines(named.get("WALL_STREET_CONSENSUS", ""))
    # Filter out header row and footnote lines
    consensus_rows = [
        r for r in consensus_rows
        if r[0].upper() not in ("FIRM", "LABEL", "METRIC") and r[0] not in ("*", "Sources", "Source")
    ]
    consensus_cells = ""
    for row in consensus_rows:
        firm = row[0]
        target_val = row[1] if len(row) > 1 else ""
        change_val = row[2] if len(row) > 2 else ""
        is_consensus = firm == "Consensus Avg"
        target_color = "#1a7a1a" if is_consensus else "#1a1a1a"
        change_color = "#1a7a1a" if is_consensus else "#888"
        consensus_cells += f'''
     <div style="padding:14px 16px;background:#f9f9f9;border:1px solid #e0e0e0;text-align:center;">
      <div style="font-size:0.8rem;color:#888;margin-bottom:4px;">{firm}</div>
      <div style="font-size:1.5rem;font-family:Georgia,serif;font-weight:bold;color:{target_color};">{target_val}</div>
      <div style="font-size:0.8rem;color:{change_color};">{change_val}</div>
     </div>'''
    # Add footnote if present in named block
    consensus_block = named.get("WALL_STREET_CONSENSUS", "")
    footnote_match = re.search(r"(\*[^*]+\*)", consensus_block)
    footnote_html = f'<p style="margin-top:12px;font-size:0.8rem;color:#888;">{footnote_match.group(1)}</p>' if footnote_match else ""
    consensus_html = f'''
   <div style="margin-bottom:28px;">
    <div class="category-label" style="margin-bottom:16px;">WALL STREET CONSENSUS</div>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;">
{consensus_cells}
    </div>
{footnote_html}
   </div>'''

    # Build VIX context HTML
    vix_rows = parse_table_lines(named.get("VOLATILITY_CONTEXT", ""))
    vix_rows = [r for r in vix_rows if r[0].upper() not in ("METRIC", "LABEL", "FIRM")]
    vix_cells = ""
    for row in vix_rows:
        metric = row[0]
        value = row[1] if len(row) > 1 else ""
        note = row[2] if len(row) > 2 else ""
        vix_cells += f'''
     <div>
      <div class="small" style="color:#888888;margin-bottom:4px;">{metric}</div>
      <div style="font-size:1.5rem;font-family:Georgia,serif;font-weight:bold;">{value}</div>
      <div style="font-size:0.8125rem;color:#888888;">{note}</div>
     </div>'''
    vix_html = f'''
   <div style="background:#f9f9f9;border:1px solid #e0e0e0;border-top:3px solid #c8001e;padding:28px;margin-bottom:32px;">
    <div class="category-label" style="margin-bottom:16px;">VOLATILITY CONTEXT</div>
    <div style="display:grid;grid-template-columns:repeat({len(vix_rows)},1fr);gap:24px;">
{vix_cells}
    </div>
   </div>'''

    # Narrative HTML (h2 stripped since we render it separately in the bull-case box)
    narrative_html = md_to_html(narrative_for_html)

    # Cards come from the last block (after the last ___
    # which didn't start with <!--)
    # The block starts with \n### CARD: so we strip leading \n first
    cards_block = ""
    for block in blocks[1:]:
        if not block.strip().startswith("<!--"):
            cards_block = block.strip()
            break
    # Fixed card category labels (order matches the 4 cards)
    CARD_CATEGORIES = ["HOW WE FORECAST", "OPTIONS FRAMEWORK", "MARKET COMMENTARY", "KEY RISKS"]
    cards_html = build_forecast_cards(cards_block, CARD_CATEGORIES)

    return {
        "narrative_html": narrative_html,
        "target_grid_html": target_grid_html,
        "consensus_html": consensus_html,
        "vix_html": vix_html,
        "cards_html": cards_html,
        "narrative_h2": narrative_h2,
    }


def build_forecast_cards(narrative_raw: str, card_categories: list = None) -> str:
    """Extract ### CARD: NAME sections from narrative and render as feature-card HTML.
    card_categories: list of category labels per card (in order), e.g. ['HOW WE FORECAST', 'OPTIONS FRAMEWORK', ...]
    The ### CARD: heading text becomes the h3 title.
    """
    if card_categories is None:
        card_categories = []
    # Split on ### CARD: headings
    parts = re.split(r"^### CARD:\s*(.*)$", narrative_raw, flags=re.MULTILINE)
    if len(parts) < 3:
        return ""
    cards_html = '<div class="feature-grid">\n'
    i = 1
    card_idx = 0
    while i < len(parts) - 1:
        card_title = parts[i].strip()  # This is the h3 title
        card_body_raw = parts[i + 1].strip() if i + 1 < len(parts) else ""
        category_label = card_categories[card_idx] if card_idx < len(card_categories) else card_title.upper()
        card_idx += 1

        # Parse: first line is "**Updated:** DATE" or "**Date:** DATE"
        updated_date = ""
        body_for_md = card_body_raw
        m = re.match(r"\*\*Updated:\*\*\s*(.+?)\s*\n", card_body_raw)
        if m:
            updated_date = m.group(1).strip()
            body_for_md = card_body_raw[m.end():].strip()
        m2 = re.match(r"\*\*Date:\*\*\s*(.+?)\s*\n", card_body_raw)
        if m2 and not updated_date:
            updated_date = m2.group(1).strip()
            body_for_md = card_body_raw[m2.end():].strip()

        body_html = md_to_html(body_for_md)

        card_meta = f'<div class="card-meta">Updated {updated_date}</div>' if updated_date else ""

        # Check for → link
        link_match = re.search(r"→\s*\[(.+?)\]\(([^)]+)\)", body_for_md)
        extra_html = ""
        if link_match:
            link_text = link_match.group(1)
            link_url = link_match.group(2)
            extra_html = f'<a href="{link_url}" class="accent-link" style="font-weight:500;">{link_text} &#8594;</a>'
            # Remove ONLY the <p>...</p> paragraph that starts with → (not the
            # entire range from the first <p> to the closing </p> after →, which
            # is what a lazy DOTALL regex would do — and which ate all preceding
            # paragraphs, including the OptionsStrat inline reference added in
            # June 2026 forecasts). Bug surfaced 2026-06-22 when the Options
            # Framework card rendered only the OptionsStrat sentence.
            body_html = re.sub(r'<p>\s*→\s*.*?</p>\s*', '', body_html, flags=re.DOTALL)

        cards_html += f'''
    <div class="feature-card">
     <div class="category-label">{category_label}</div>
     {card_meta}
     <h3>{card_title}</h3>
{body_html}
{extra_html}
    </div>'''
        i += 2
    cards_html += '\n   </div>'
    return cards_html


def build_archive_cards(forecasts: list) -> str:
    """Build the archive section HTML from archived forecast MDs.

    Layout: 2 rows × 3 columns (max 6 cards) per user preference.
    Older forecasts are accessible via the 'View all archived forecasts' link
    on /archive. Newest-first sort.
    """
    archived = [(s, m, b) for s, m, b in forecasts if m.get("archived")]
    if not archived:
        return ""
    # Limit visible to 6 most-recent (2 rows × 3 cols)
    MAX_VISIBLE_ARCHIVE_CARDS = 6
    archived = archived[:MAX_VISIBLE_ARCHIVE_CARDS]
    cards = ""
    for slug, meta, body in archived:
        title = meta.get("title", slug)
        date_str = meta.get("date", "")
        # Format date: 2026-02-14 → Feb 14, 2026
        date_display = date_str
        try:
            from datetime import datetime
            d = datetime.strptime(date_str, "%Y-%m-%d")
            date_display = d.strftime("%B %d, %Y")
        except Exception:
            pass
        # Parse sections from body (uses ___" separators now)
        blocks = re.split(r"\n___\n", body)
        target_rows = parse_table_lines(blocks[1] if len(blocks) > 1 else "")
        target_rows = [r for r in target_rows if r[0].upper() not in ("LABEL", "FIRM", "METRIC")]

        target_info = ""
        if len(target_rows) >= 4:
            r0, r1, r2, r3 = target_rows[0], target_rows[1], target_rows[2], target_rows[3]
            target_info = (
                f'<p>'
                f'<strong>Current:</strong> {r0[1] if len(r0)>1 else ""} '
                f'&nbsp;|&nbsp; <strong>1-Month:</strong> {r1[1] if len(r1)>1 else ""} '
                f'&nbsp;|&nbsp; <strong>3-Month:</strong> {r2[1] if len(r2)>1 else ""} '
                f'&nbsp;|&nbsp; <strong>Year-End:</strong> {r3[1] if len(r3)>1 else ""}'
                f'</p>'
            )
        # Summary from front matter description
        summary = meta.get("description", "")

        cards += f'''
     <div style="padding:20px;background:#f9f9f9;border:1px solid #e0e0e0;">
      <div style="font-size:0.8rem;color:#888;margin-bottom:6px;">ARCHIVED &middot; {date_display}</div>
      <div style="font-size:1rem;font-weight:bold;color:#1a1a1a;margin-bottom:8px;">{title}</div>
      <div style="font-size:0.875rem;color:#555;line-height:1.6;">
       {target_info}
       <p style="margin-top:8px;">{summary}</p>
      </div>
     </div>'''
    return f'''
  <!-- Archived Forecasts -->
  <div style="margin-top:48px;padding-top:32px;border-top:2px solid #e0e0e0;">
   <div style="max-width:880px;margin:0 auto;text-align:left;">
    <div class="category-label" style="margin-bottom:20px;">&#128193; ARCHIVED FORECASTS</div>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;">
{cards}
    </div>
    <div style="margin-top:16px;text-align:right;">
     <a href="/archive/" style="font-size:0.875rem;color:#c8001e;text-decoration:none;border-bottom:1px solid #c8001e;">View all archived forecasts →</a>
    </div>
   </div>
  </div>'''


def build_forecast_page(latest_forecast: tuple, all_forecasts: list) -> str:
    """Build forecast.html from the most-recent non-archived forecast MD."""
    slug, meta, body = latest_forecast
    sections = parse_forecast_body(body)
    date_str = meta.get("date", "")
    try:
        from datetime import datetime
        date_display = datetime.strptime(date_str, "%Y-%m-%d").strftime("%B %d, %Y")
    except Exception:
        date_display = date_str

    narrative_h2 = sections.get("narrative_h2", "Market Assessment")

    # Previous forecast nav link (next older)
    prev_forecast = all_forecasts[1] if len(all_forecasts) > 1 else None
    prev_link_html = ""
    if prev_forecast:
        prev_slug = prev_forecast[0]
        prev_date_str = prev_forecast[1].get("date", "")
        try:
            from datetime import datetime as dt2
            prev_date_display = dt2.strptime(prev_date_str, "%Y-%m-%d").strftime("%B %d, %Y")
        except Exception:
            prev_date_display = prev_date_str
        prev_link_html = (
            "<div style=\"margin-bottom:20px;text-align:left;\">"
            "<a href=\"/forecast/" + prev_slug + "/\" style=\"font-size:.875rem;color:#c8001e;text-decoration:none;\">"
            "&#8592; Previous forecast: " + prev_date_display + "</a></div>"
        )

    main_html = f'''
  <div class="page-hero">
   <h1>S&P 500 Forecast</h1>
   <p>Data-driven price targets and market outlook — updated regularly as conditions evolve.</p>
   <div style="margin-top:12px;font-size:.875rem;color:#888;text-align:center;">Updated {date_display}</div>
  </div>

{ADSENSE_BLOCK_SQUARE}
  <div class="page-content">

{prev_link_html}

{sections["target_grid_html"]}

   <!-- Bull Case Summary -->
   <div style="background:#fff;border:1px solid #e0e0e0;padding:24px;margin-bottom:28px;">
    <div class="category-label" style="margin-bottom:14px;">BULL CASE RATIONALE</div>
    <h2 style="margin-bottom:16px;border-bottom:2px solid #c8001e;padding-bottom:8px;">{narrative_h2}</h2>
<div class="article-body">
{sections["narrative_html"]}
</div>
   </div>

{sections["consensus_html"]}

{sections["vix_html"]}

{sections["cards_html"]}

  </div>

{build_archive_cards(all_forecasts)}

{ADSENSE_BLOCK}

<div class="disclaimer">
 <strong>Disclaimer:</strong> This research is for informational purposes only and does not constitute investment advice. Options trading involves substantial risk of loss. Past performance is not indicative of future results.
</div>

'''

    tmpl = load_template("_article_template.html")
    tmpl = tmpl.replace("</head>", f"{STYLE_BLOCK}</head>\n", 1)
    tmpl = tmpl.replace("PAGE TITLE", f"S&P 500 Forecast — {date_display} | Dependability Holdings LLC", 1)
    tmpl = tmpl.replace("PAGE DESCRIPTION",
        meta.get("description", f"S&P 500 forecast published {date_display}."), 1)
    tmpl = tmpl.replace("<!-- PAGE CONTENT GOES HERE -->", main_html, 1)
    # Ensure canonical is absolute URL (Google prefers absolute canonicals)
    tmpl = tmpl.replace("CANONICAL_PLACEHOLDER", f"{BASE_URL}/forecast/", 1)
    tmpl = re.sub(r'href="/forecast/"', 'href="/forecast/" class="active"', tmpl)
    return tmpl



def build_forecast_detail_page(forecast: tuple, all_forecasts: list) -> str:
    """Build an individual /forecast/YYYY-MM-DD.html page."""
    slug, meta, body = forecast
    sections = parse_forecast_body(body)
    date_str = meta.get("date", "")
    try:
        from datetime import datetime
        date_display = datetime.strptime(date_str, "%Y-%m-%d").strftime("%B %d, %Y")
    except Exception:
        date_display = date_str

    narrative_h2 = sections.get("narrative_h2", "Market Assessment")

    # Prev = older (higher index in all_forecasts, which is newest-first)
    try:
        idx = [f[0] for f in all_forecasts].index(slug)
    except ValueError:
        idx = -1
    prev_forecast = all_forecasts[idx + 1] if idx + 1 < len(all_forecasts) else None
    next_forecast = all_forecasts[idx - 1] if idx - 1 >= 0 else None

    nav_parts = []
    if prev_forecast:
        pd = prev_forecast[1].get("date", "")
        try:
            from datetime import datetime as dt2
            pd_disp = dt2.strptime(pd, "%Y-%m-%d").strftime("%B %d, %Y")
        except Exception:
            pd_disp = pd
        nav_parts.append(
            f'<a href="/forecast/{prev_forecast[0]}/" class="accent-link" style="font-size:.875rem;">'
            f'&#8592; Previous: {pd_disp}</a>'
        )
    if next_forecast:
        nd = next_forecast[1].get("date", "")
        try:
            from datetime import datetime as dt2
            nd_disp = dt2.strptime(nd, "%Y-%m-%d").strftime("%B %d, %Y")
        except Exception:
            nd_disp = nd
        nav_parts.append(
            f'<a href="/forecast/{next_forecast[0]}/" class="accent-link" style="font-size:.875rem;">'
            f'Next: {nd_disp}&#8594;</a>'
        )
    nav_html = (
        f'<div style="display:flex;justify-content:space-between;margin-bottom:24px;">'
        f'{"".join(nav_parts)}'
        f'</div>'
        if nav_parts else ""
    )

    main_html = f"""
  <div class="page-hero">
   <h1>S&P 500 Forecast</h1>
   <div style="margin-top:12px;font-size:.875rem;color:#888;text-align:center;">Updated {date_display}</div>
  </div>

{ADSENSE_BLOCK_SQUARE}
  <div class="page-content">

{nav_html}

{sections["target_grid_html"]}

   <div style="background:#fff;border:1px solid #e0e0e0;padding:24px;margin-bottom:28px;">
    <div class="category-label" style="margin-bottom:14px;">BULL CASE RATIONALE</div>
    <h2 style="margin-bottom:16px;border-bottom:2px solid #c8001e;padding-bottom:8px;">{narrative_h2}</h2>
    <div class="article-body">
{sections["narrative_html"]}
    </div>
   </div>

{sections["consensus_html"]}

{sections["vix_html"]}

{sections["cards_html"]}

  </div>

{ADSENSE_BLOCK}

<div class="disclaimer">
 <strong>Disclaimer:</strong> This research is for informational purposes only and does not constitute investment advice. Options trading involves substantial risk of loss. Past performance is not indicative of future results.
</div>
"""

    tmpl = load_template("_article_template.html")
    tmpl = tmpl.replace("</head>", f"{STYLE_BLOCK}</head>\n", 1)
    tmpl = tmpl.replace("PAGE TITLE", f"S&P 500 Forecast — {date_display} | Dependability Holdings LLC", 1)
    tmpl = tmpl.replace("PAGE DESCRIPTION",
        meta.get("description", f"S&P 500 forecast published {date_display}."), 1)
    tmpl = tmpl.replace("<!-- PAGE CONTENT GOES HERE -->", main_html, 1)
    # Ensure canonical is absolute URL (Google prefers absolute canonicals)
    forecast_canonical = f"{BASE_URL}/forecast/{slug}/"
    tmpl = tmpl.replace("CANONICAL_PLACEHOLDER", forecast_canonical, 1)
    tmpl = re.sub(r'href="/forecast/"', 'href="/forecast/" class="active"', tmpl)
    return tmpl


def build_archive_page(all_forecasts: list) -> str:
    """Build archive.html listing all archived forecasts, newest-first.
    When MD stubs are empty (skipped by load_forecasts anti-pattern #91),
    scan the output forecast/ directory for existing rendered HTML pages."""
    archived = [f for f in all_forecasts if f[1].get("archived")]
    if not archived:
        archived = all_forecasts[1:]  # everything except the latest

    # If we only have 1 forecast but the output dir has more, scan output dir
    if len(archived) <= 1:
        forecast_output = OUTPUT_DIR / "forecast"
        if forecast_output.exists():
            output_forecasts = []
            for subdir in sorted(forecast_output.iterdir(), reverse=True):
                if not subdir.is_dir():
                    continue
                if subdir.name.startswith("."):
                    continue
                if len(subdir.name) != 10 or subdir.name[4:5] != "-" or subdir.name[7:8] != "-":
                    continue
                slug = subdir.name
                # Skip the latest (already shown as live forecast)
                if all_forecasts and slug == all_forecasts[0][0]:
                    continue
                # Try to read meta from the rendered HTML (has meta description)
                html_path = subdir / "index.html"
                if html_path.exists():
                    html_text = html_path.read_text(encoding="utf-8")
                    # Extract title
                    title_match = re.search(r'<title>([^<]+)</title>', html_text)
                    title = title_match.group(1).replace(" | Dependability Holdings LLC", "") if title_match else slug
                    # Extract description from meta
                    desc_match = re.search(r'<meta name="description" content="([^"]+)"', html_text)
                    description = desc_match.group(1) if desc_match else ""
                    # Extract date from the HTML — look for "Updated" pattern
                    date_match = re.search(r'Updated ([A-Z][a-z]+ [0-9]+, [0-9]{4})', html_text)
                    date_str = ""
                    if date_match:
                        date_str = date_match.group(1)
                        # Convert "August 25, 2026" to "2026-08-25" for meta
                        try:
                            from datetime import datetime
                            dt = datetime.strptime(date_str, "%B %d, %Y")
                            date_str_iso = dt.strftime("%Y-%m-%d")
                        except Exception:
                            date_str_iso = slug
                    else:
                        date_str_iso = slug
                    meta = {"date": date_str_iso, "title": title, "description": description}
                    output_forecasts.append((slug, meta, ""))
            if output_forecasts:
                archived = output_forecasts

    items_html = ""
    from datetime import datetime
    date_display = ""
    for slug, meta, body in archived:
        title = meta.get("title", slug)
        date_str = meta.get("date", "")
        try:
            date_display = datetime.strptime(date_str, "%Y-%m-%d").strftime("%B %d, %Y")
        except Exception:
            date_display = date_str
        summary = meta.get("description", "")

        blocks = re.split(r"\n___\n", body)
        target_rows = parse_table_lines(blocks[1] if len(blocks) > 1 else "")
        target_rows = [r for r in target_rows if r[0].upper() not in ("LABEL", "FIRM", "METRIC")]
        target_info = ""
        if len(target_rows) >= 4:
            r0, r1, r2, r3 = target_rows[0], target_rows[1], target_rows[2], target_rows[3]
            target_info = (
                f'<p style="font-size:0.9rem;color:#555;margin-bottom:10px;">'
                f'<strong>Current:</strong> {r0[1] if len(r0)>1 else ""} '
                f'&nbsp;|&nbsp; <strong>1-Month:</strong> {r1[1] if len(r1)>1 else ""} '
                f'&nbsp;|&nbsp; <strong>3-Month:</strong> {r2[1] if len(r2)>1 else ""} '
                f'&nbsp;|&nbsp; <strong>Year-End:</strong> {r3[1] if len(r3)>1 else ""}'
                f'</p>'
            )

        # "Previous forecast" link = the next older archived forecast
        try:
            idx = [f[0] for f in archived].index(slug)
        except ValueError:
            idx = -1
        older_forecast = archived[idx + 1] if idx + 1 < len(archived) else None
        prev_link_html = ""
        if older_forecast:
            opd = older_forecast[1].get("date", "")
            try:
                from datetime import datetime as dt2
                opd_disp = dt2.strptime(opd, "%Y-%m-%d").strftime("%B %d, %Y")
            except Exception:
                opd_disp = opd
            prev_link_html = (
                f'<div style="margin-top:8px;font-size:.8rem;color:#888;">'
                f'Previous forecast: <a href="/forecast/{older_forecast[0]}/" style="color:#c8001e;">{opd_disp}</a>'
                f'</div>'
            )

        items_html += f"""
    <div style="padding:20px 0;border-bottom:1px solid #e0e0e0;">
     <div style="font-size:0.8rem;color:#888;margin-bottom:6px;">{date_display}</div>
     <div style="font-size:1.25rem;font-weight:bold;color:#1a1a1a;margin-bottom:8px;">{title}</div>
     {target_info}
     <div style="font-size:0.9rem;color:#555;line-height:1.6;margin-bottom:8px;">{summary}</div>
     <div style="font-size:.8rem;"><a href="/forecast/{slug}/" style="color:#c8001e;text-decoration:none;border-bottom:1px solid #c8001e;">View full forecast &#8594;</a></div>
     {prev_link_html}
    </div>"""

    main_html = f"""
  <div class="page-hero">
   <h1>Forecast Archive</h1>
   <p>All historical S&P 500 forecasts — past targets, rationale, and market conditions.</p>
   <div style="margin-top:12px;font-size:.875rem;color:#888;text-align:center;">Updated {date_display}</div>
  </div>
{ADSENSE_BLOCK_SQUARE}
  <div class="page-content">
   <div style="margin-bottom:32px;"><a href="/forecast/">&#8592; Back to current forecast</a></div>
   <div class="archive-list">
{items_html}
{ADSENSE_BLOCK}
   </div>
  </div>
"""

    tmpl = load_template("_article_template.html")
    tmpl = tmpl.replace("PAGE TITLE", "Forecast Archive | Dependability Holdings LLC", 1)
    tmpl = tmpl.replace("PAGE DESCRIPTION", "Historical S&P 500 forecasts and market outlooks from Dependability Holdings LLC.", 1)
    tmpl = tmpl.replace("<!-- PAGE CONTENT GOES HERE -->", main_html, 1)
    # Ensure canonical is absolute URL (Google prefers absolute canonicals)
    tmpl = tmpl.replace("CANONICAL_PLACEHOLDER", f"{BASE_URL}/archive/", 1)
    return tmpl

# ── Main ────────────────────────────────────────────────────────────────────────
def main():
    print(f"Loading articles from {CONTENT_DIR}...")
    articles = load_articles()
    print(f"Found {len(articles)} articles.")

    ROOT_ARTICLES = ["the-dollars-lever", "inflation-measurement-modern-economy",
                        "oil-paradox-energy-dominance", "tlt-new-bond-regime",
                        "gold-as-a-store-of-value"]

    if articles:
        # Write individual article pages
        for slug, meta, body in articles:
            body_html = md_to_html(body)
            body_html = inject_adsense_into_body(body_html, topic=_adsense_topic_from_meta(meta))
            html = article_page_html(slug, meta, body_html)
            if slug in ROOT_ARTICLES:
                out_dir = OUTPUT_DIR / slug
            else:
                out_dir = OUTPUT_DIR / "articles" / slug
            out_dir.mkdir(exist_ok=True)
            (out_dir / "index.html").write_text(html, encoding="utf-8")
            print(f"  Wrote {out_dir.relative_to(OUTPUT_DIR)}/index.html")

    # Write index.html
    # Load forecasts early so the homepage sidebar forecast card is dynamic
    print(f"Loading forecasts from {FORECAST_CONTENT_DIR}...")
    forecasts = load_forecasts()
    print(f"  Found {len(forecasts)} forecast(s).")

    if articles:
        index_html = build_index(articles, forecasts=forecasts)
        (OUTPUT_DIR / "index.html").write_text(index_html, encoding="utf-8")
        print("  Wrote index.html")

        # Write commentary.html
        comm_html = build_commentary(articles)
        (OUTPUT_DIR / "commentary/index.html").write_text(comm_html, encoding="utf-8")
        print("  Wrote commentary/index.html")

        # Write education.html
        edu_html = build_education(articles)
        (OUTPUT_DIR / "education/index.html").write_text(edu_html, encoding="utf-8")
        print("  Wrote education/index.html")

    # Write forecast.html (always — independent of articles)
    if forecasts:
        print(f"  Found {len(forecasts)} forecast(s).")
        latest = next((f for f in forecasts if not f[1].get("archived")), forecasts[0])  # newest non-archived
        forecast_html = build_forecast_page(latest, forecasts)
        (OUTPUT_DIR / "forecast/index.html").write_text(forecast_html, encoding="utf-8")
        print("  Wrote forecast.html")

        # Write individual forecast detail pages
        FORECAST_OUT = OUTPUT_DIR / "forecast"
        FORECAST_OUT.mkdir(exist_ok=True)
        for slug, meta, body in forecasts:
            detail_html = build_forecast_detail_page((slug, meta, body), forecasts)
            (FORECAST_OUT / slug).mkdir(exist_ok=True)
            (FORECAST_OUT / slug / "index.html").write_text(detail_html, encoding="utf-8")
            print(f"  Wrote forecast/{slug}/index.html")

        # Write archive/ (folder/index.html so trailing-slash URL resolves directly without 308)
        archive_html = build_archive_page(forecasts)
        archive_dir = OUTPUT_DIR / "archive"
        archive_dir.mkdir(exist_ok=True)
        (archive_dir / "index.html").write_text(archive_html, encoding="utf-8")
        print("  Wrote archive/index.html")
    else:
        print("  No forecasts found — skipping forecast.html")

    # Generate sitemap.xml
    sitemap_xml = generate_sitemap(articles, forecasts)
    (OUTPUT_DIR / "sitemap.xml").write_text(sitemap_xml, encoding="utf-8")
    print("  Wrote sitemap.xml")

    print("\nBuild complete.")


def generate_sitemap(articles: list, forecasts: list) -> str:
    """Return a valid XML sitemap string for dependability.us.

    Every entry MUST include <lastmod>YYYY-MM-DD</lastmod> derived from each
    item's frontmatter `date` so Googlebot re-crawls updated content. Without
    lastmod, GSC returns "URL is unknown to Google" for newly updated pages
    and Google will not re-crawl on subsequent sitemap submissions (verified
    2026-07-09 via URL Inspection API).
    """
    from datetime import date as _date
    today = _date.today().isoformat()

    # ROOT_ARTICLES = articles that live at /{slug}/ (not /articles/{slug}/)
    ROOT_ARTICLES = ["the-dollars-lever", "inflation-measurement-modern-economy",
                     "oil-paradox-energy-dominance", "tlt-new-bond-regime",
                     "gold-as-a-store-of-value"]

    def _lastmod(meta: dict) -> str:
        d = (meta.get("date") or "").strip()
        if len(d) < 10 or d[4:5] != "-" or d[7:8] != "-":
            return today
        return d[:10]

    # Each entry: (loc, changefreq, priority, lastmod)
    urls = [
        ("/", "weekly", "1.0", today),
        ("/about/", "monthly", "0.8", today),
        ("/commentary/", "weekly", "0.9", today),
        ("/contact/", "monthly", "0.5", today),
        ("/disclaimer/", "monthly", "0.5", today),
        ("/education/", "monthly", "0.7", today),
        ("/forecast/", "weekly", "0.9", today),
        ("/privacy/", "monthly", "0.5", today),
        ("/strategies/", "weekly", "0.9", today),
        ("/archive/", "monthly", "0.7", today),
    ]

    for slug, meta, _ in articles:
        loc = f"/{slug}/" if slug in ROOT_ARTICLES else f"/articles/{slug}/"
        urls.append((loc, "monthly", "0.7", _lastmod(meta)))

    # Include ALL forecast subdirs from output, not just those with valid MD stubs.
    # Empty-stub forecasts still have rendered HTML on disk and need sitemap entries.
    forecast_output = OUTPUT_DIR / "forecast"
    if forecast_output.exists():
        for subdir in sorted(forecast_output.iterdir(), reverse=True):
            if not subdir.is_dir():
                continue
            if subdir.name.startswith("."):
                continue
            # Only include dirs with an index.html
            if not (subdir / "index.html").exists():
                continue
            # Skip non-date dirs (e.g., 'index.html' is a file not a dir, caught above)
            if len(subdir.name) != 10 or subdir.name[4:5] != "-" or subdir.name[7:8] != "-":
                continue
            slug = subdir.name
            # Get lastmod from frontmatter date if available in the MD stub, else from directory mtime
            meta_date = ""
            stub_path = FORECAST_CONTENT_DIR / f"{slug}.md"
            if stub_path.exists():
                stub_text = stub_path.read_text(encoding="utf-8")
                fm_meta, _ = parse_front_matter(stub_text)
                meta_date = _lastmod(fm_meta)
            if not meta_date:
                import time
                meta_date = time.strftime("%Y-%m-%d", time.localtime((subdir / "index.html").stat().st_mtime))
            urls.append((f"/forecast/{slug}/", "monthly", "0.8", meta_date))
    else:
        # Fallback: just use the forecasts list
        for slug, meta, _ in forecasts:
            urls.append((f"/forecast/{slug}/", "monthly", "0.8", _lastmod(meta)))

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, freq, pri, lastmod in urls:
        lines.append(
            f'  <url><loc>https://dependability.us{loc}</loc>'
            f'<lastmod>{lastmod}</lastmod>'
            f'<changefreq>{freq}</changefreq><priority>{pri}</priority></url>'
        )
    lines.append('</urlset>')
    return "\n".join(lines) + "\n"

if __name__ == "__main__":
    main()
