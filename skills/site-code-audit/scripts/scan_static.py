"""
scan_static.py — Layer 1: scan source files for bugs.

Findings are emitted as a list of dicts:
    {
        "site": "bacotti",
        "class": "ga4_typo" | "missing_favicon" | "broken_internal_link"
                  | "missing_canonical" | "duplicate_h1" | "build_script_error"
                  | "redirect_dangling" | "manifest_malformed"
                  | "word_count_low" | "thin_with_ads" | "duplicate_ad_slot"
                  | "missing_eeat_sections" | "content_stale" | "missing_ad_unit",
        "severity": "critical" | "high" | "medium" | "low",
        "file": "<relative path>",
        "details": "...",
        "auto_fixable": True | False,
        "fix_class": "ga4_typo" | "inject_favicon" | ...  # for fix.py routing
    }
"""
import re
from pathlib import Path

from sites import SITES, all_html_files, is_in_archive

# GA4 measurement IDs: correct = G-XXXXXXXXXX (10 alphanumeric chars).
# Common typo: G-G-XXXXXXXXXX (double G). GA silently rejects these.
GA4_RE = re.compile(r'id=(G-G-[A-Z0-9]+)|gtag\([\'"]config[\'"],\s*[\'"]?(G-G-[A-Z0-9]+)')
GA4_CORRECT_RE = re.compile(r'\bG-[A-Z0-9]{8,12}\b')
GA4_TYPO_RE = re.compile(r'\bG-G-[A-Z0-9]+\b')

# Favicon link patterns
FAVICON_LINK_RE = re.compile(r'<link\s+rel="(?:icon|shortcut icon|apple-touch-icon)"')

# Canonical link
CANONICAL_RE = re.compile(r'<link\s+rel="canonical"\s+href="([^"]+)"')

# H1 (for duplicate detection)
H1_RE = re.compile(r'<h1\b[^>]*>(.*?)</h1>', re.DOTALL | re.IGNORECASE)

# Internal links to other HTML pages on the same site
INTERNAL_HREF_RE = re.compile(r'href="(/[^"#?]*)"')

# AdSense signal patterns (Track A from memory/2026-08-23-adsense-gaps-and-upgrade-plan.md)
AD_INSLOT_RE = re.compile(r'<ins\s+class="adsbygoogle"', re.IGNORECASE)
AD_DATA_SLOT_RE = re.compile(r'data-ad-slot="(\d+)"')

# Page-type word-count thresholds (AdSense)
# Per memory/archive/2026-07-monthly-highlights.md:
# - 297-385w = clearly flagged by AdSense
# - 460-685w = flagged
# - 800w+ = passes (target for /about/, /authors/, /legal/, /methodology/)
# - 1200w+ = strongly passes (target for /articles/, /reviews/, substantive content)
# - Listing/archives/product pages (no ads): word count irrelevant
WORDCOUNT_THRESHOLDS = {
    "legal_umbrella": 800,   # /about/, /authors/, /editorial/, /legal/, /methodology/, /disclaimer/, /privacy/, /terms/, /contact/
    "content_article": 800,  # /articles/, /reviews/, /forecasts/, /commentary/, /newsletters/, /trade-log/ — passes at 800w
}
LEGAL_PATH_PATTERNS = [
    r'/about/?$', r'/authors/?$', r'/editorial/?$', r'/legal/?$',
    r'/methodology/?$', r'/disclaimer/?$', r'/privacy/?$',
    r'/terms/?$', r'/contact/?$',
]
CONTENT_PATH_PATTERNS = [
    r'/articles/', r'/reviews/', r'/forecasts/', r'/commentary/',
    r'/newsletters/', r'/trade-log/', r'/forecast/',
    r'/playbook/', r'/education/', r'/strategies/',
    r'/insights/', r'/news/', r'/stories/',
]

# E-E-A-T required section patterns (look for these phrases in page text)
EEAT_SECTION_PATTERNS = {
    "named_editor":       [r'\b(editor|author|founder|writer)\b.*\b(name|who|is)\b', r'\bby\s+[A-Z][a-z]+\s+[A-Z][a-z]+', r'(Editor in Chief|Founder|Lead Writer|Editor)'],
    "credentials":        [r'\b(degree|PhD|MBA|JD|CPA|credential|certified|licensed|experience in)\b'],
    "launch_date":        [r'\blaunched?\s+(in|on)\b', r'\b(since|founded)\s+\d{4}\b', r'\b20\d{2}\s*[-–]\s*20\d{2}\b'],
    "editorial_process":  [r'\b(editorial process|how we (write|research|review)|research → write → review|review process)\b'],
    "corrections_policy": [r'\bcorrection', r'\b(wrong|fix)(s|ed)?\b.*\bpolicy', r'\bwhen (we|discovered)\s+(a|an)\s+error\b'],
    "disclosure":         [r'\b(disclos|conflict|affiliat|relationship|sponsored)\b', r'\bDependability Holdings\b', r'\bBacotti (Enterprises|Inc)\b'],
}


def _relpath(p: Path) -> str:
    """Try to make the path workspace-relative for nicer display."""
    try:
        return str(p.relative_to(Path.home() / ".openclaw" / "workspace-bacottibot"))
    except ValueError:
        return str(p)


def _extract_visible_text(html: str) -> str:
    """Strip scripts/styles/HTML tags, return visible body text only.

    Used for word count. Not perfect (won't handle nested tags inside <main>),
    but consistent enough for the AdSense thin-page heuristic.
    """
    # Remove script and style blocks entirely
    text = re.sub(r'<script\b[^>]*>.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style\b[^>]*>.*?</style>', ' ', text, flags=re.DOTALL | re.IGNORECASE)
    # Remove HTML comments
    text = re.sub(r'<!--.*?-->', ' ', text, flags=re.DOTALL)
    # Remove SVG inline content (decorative, not content)
    text = re.sub(r'<svg\b[^>]*>.*?</svg>', ' ', text, flags=re.DOTALL | re.IGNORECASE)
    # Strip all remaining tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Decode common HTML entities
    text = (text.replace('&nbsp;', ' ').replace('&amp;', '&')
                .replace('&lt;', '<').replace('&gt;', '>')
                .replace('&quot;', '"').replace('&#39;', "'"))
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _count_words(text: str) -> int:
    """Count words in plain text. Splits on whitespace."""
    if not text:
        return 0
    return len([w for w in text.split(' ') if w])


def _classify_page_type(rel_path: str) -> str:
    """Return 'legal_umbrella', 'content_article', or 'other' based on URL path.

    'other' (e.g. product pages with 0 ads, listing/archives) is not flagged.
    Strips .html extension before matching so both 'about/index.html' and
    '/about/' are recognized.
    """
    # Normalize: strip .html, trailing slash, normalize to URL-style path
    normalized = rel_path.replace("index.html", "").replace(".html", "")
    if not normalized.endswith("/"):
        normalized += "/"
    # Match the URL-style path against patterns
    for pat in LEGAL_PATH_PATTERNS:
        if re.search(pat, "/" + normalized.lstrip("/"), re.IGNORECASE):
            return "legal_umbrella"
    for pat in CONTENT_PATH_PATTERNS:
        if re.search(pat, "/" + normalized.lstrip("/"), re.IGNORECASE):
            return "content_article"
    return "other"


def _has_ads(html: str) -> int:
    """Count ad slot ins tags on the page."""
    return len(AD_INSLOT_RE.findall(html))


def _unique_ad_slots(html: str) -> set:
    """Return set of unique data-ad-slot values on the page."""
    return set(AD_DATA_SLOT_RE.findall(html))


def _check_eeat_sections(html: str, page_type: str) -> list:
    """Return list of E-E-A-T section names that are MISSING from /about/-class pages.

    Only runs on legal_umbrella pages (/about/, /authors/, /editorial/,
    /methodology/, /disclaimer/, /privacy/, /terms/, /contact/).
    """
    if page_type != "legal_umbrella":
        return []
    text = _extract_visible_text(html).lower()
    missing = []
    for section_name, patterns in EEAT_SECTION_PATTERNS.items():
        if not any(re.search(pat, text, re.IGNORECASE) for pat in patterns):
            missing.append(section_name)
    return missing


def _scan_html_for_site(site) -> list:
    findings = []
    html_files = all_html_files(site)
    if not html_files:
        return findings

    # Build a set of all internal link targets (so we can check for broken links).
    all_pages = set()
    for h in html_files:
        rel = h.relative_to(site["source_dir"])
        # Normalize: index.html → /path/
        rel_str = "/" + str(rel).replace("index.html", "").replace(".html", "")
        if not rel_str.endswith("/"):
            rel_str += "/"
        all_pages.add(rel_str)
        all_pages.add("/" + str(rel))

    for h in html_files:
        # Skip archived content — frozen snapshots, not live work
        if is_in_archive(h):
            continue
        rel = _relpath(h)
        try:
            html = h.read_text(encoding="utf-8")
        except Exception as e:
            findings.append(
                {
                    "site": site["name"],
                    "class": "html_read_error",
                    "severity": "high",
                    "file": rel,
                    "details": f"could not read: {e}",
                    "auto_fixable": False,
                }
            )
            continue

        # GA4 typo (would have caught the 2026-08-17 incident)
        for m in GA4_TYPO_RE.finditer(html):
            findings.append(
                {
                    "site": site["name"],
                    "class": "ga4_typo",
                    "severity": "critical",
                    "file": rel,
                    "details": f"GA4 ID has typo: '{m.group(0)}' (expected format G-XXXXXXXXXX)",
                    "auto_fixable": True,
                    "fix_class": "ga4_typo",
                    "typo_value": m.group(0),
                }
            )

        # Missing favicon on a site that should have one
        if site["favicon_paths"] and not FAVICON_LINK_RE.search(html):
            findings.append(
                {
                    "site": site["name"],
                    "class": "missing_favicon",
                    "severity": "medium",
                    "file": rel,
                    "details": "HTML head missing favicon <link> tags",
                    "auto_fixable": True,
                    "fix_class": "inject_favicon",
                }
            )

        # Missing canonical
        if not CANONICAL_RE.search(html):
            findings.append(
                {
                    "site": site["name"],
                    "class": "missing_canonical",
                    "severity": "medium",
                    "file": rel,
                    "details": "page missing <link rel=canonical>",
                    "auto_fixable": False,
                }
            )

        # Duplicate H1
        h1s = H1_RE.findall(html)
        if len(h1s) > 1:
            findings.append(
                {
                    "site": site["name"],
                    "class": "duplicate_h1",
                    "severity": "low",
                    "file": rel,
                    "details": f"{len(h1s)} <h1> tags on one page (best practice: 1)",
                    "auto_fixable": False,
                }
            )

        # Broken internal links (target doesn't exist as a page)
        # NOTE: false positives are noisy here because:
        #  - Static assets (.css, .png, .js, .ico) may not be in source dir
        #    (CF Pages CDN serves them from upload bundle)
        #  - Build-script-generated pages may not match source dir structure
        # We only flag as "broken" if the target clearly looks like an HTML
        # page (no extension or .html) AND doesn't match any known page.
        for m in INTERNAL_HREF_RE.finditer(html):
            target = m.group(1)
            if target.startswith("//") or target.startswith("/_"):
                continue
            # Skip JS template-literal hrefs (e.g. '/reviews/' + b.slug + '.html')
            # These are concatenated at runtime, not real broken links.
            if any(tok in target for tok in ("' +", "+ '", '${', "{{", "}}")):
                continue
            # Strip query/hash
            target = target.split("#")[0].split("?")[0]
            if not target:
                continue
            # Skip assets by extension (.css, .png, .jpg, .svg, .js, .ico, .json, .xml)
            # These are bundled assets, not pages — false positives if missing
            # in source dir. CF Pages serves them from the upload bundle.
            last_segment = target.rsplit("/", 1)[-1]
            if "." in last_segment and not last_segment.endswith(".html"):
                continue
            # Skip anchor-only or same-page links
            normalized = target if target.endswith("/") else target + "/"
            normalized_no_slash = target.rstrip("/")
            if normalized in all_pages or normalized_no_slash in all_pages:
                continue
            # Skip targets that exist on disk (asset files, data files)
            possible_file = site["source_dir"] / target.lstrip("/")
            if possible_file.exists():
                continue
            # Looks like a real missing page
            findings.append(
                {
                    "site": site["name"],
                    "class": "broken_internal_link",
                    "severity": "medium",
                    "file": rel,
                    "details": f"internal href '{target}' does not resolve to a known page or asset",
                    "auto_fixable": True,
                    "fix_class": "broken_internal_link",
                    "broken_href": target,
                }
            )

    # Missing favicon assets
    if site["favicon_paths"]:
        for fp in site["favicon_paths"]:
            asset_path = site["source_dir"] / fp
            if not asset_path.exists():
                findings.append(
                    {
                        "site": site["name"],
                        "class": "missing_favicon_asset",
                        "severity": "medium",
                        "file": str(site["source_dir"].name) + "/" + fp,
                        "details": f"favicon asset referenced by site but missing on disk",
                        "auto_fixable": False,
                    }
                )

    # _redirects sanity (CF Pages / Netlify style)
    redirects = site["source_dir"] / "_redirects"
    if redirects.exists():
        text = redirects.read_text()
        for i, line in enumerate(text.splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = re.split(r'\s+', line)
            if len(parts) < 2:
                findings.append(
                    {
                        "site": site["name"],
                        "class": "redirect_malformed",
                        "severity": "low",
                        "file": "_redirects",
                        "details": f"line {i}: '{line}' has <2 tokens",
                        "auto_fixable": False,
                    }
                )

    # ===========================================================
    # Track A: AdSense content signals (memory/2026-08-23-adsense-gaps-and-upgrade-plan.md)
    # ===========================================================

    # Re-scan HTML files for AdSense signals — using already-read files is faster
    # (we'd otherwise re-open every file). Build per-page cache during the
    # initial scan instead. Here we re-read since the structure is simpler
    # and the cache lives above in `html` per loop iteration.
    # For simplicity, do a second pass keyed off html_files list + html-read cache.
    # (Implementation note: nested loop below is O(N) over already-loaded pages.)
    for h in html_files:
        if is_in_archive(h):
            continue
        rel = _relpath(h)
        try:
            html_for_adsense = h.read_text(encoding="utf-8")
        except Exception:
            continue

        # Page type classification
        page_type = _classify_page_type(rel)

        # Has ads? (checked even when page_type == "other" — duplicate slots are
        # bugs regardless of page type)
        ad_count = _has_ads(html_for_adsense)
        has_ads = ad_count > 0
        unique_slots = _unique_ad_slots(html_for_adsense)

        # Finding: duplicate_ad_slot (BUG regardless of page type)
        # NOTE: dependability articles intentionally use 3 distinct slots
        # (top/middle/bottom) — that's layout, not copy-paste dup. Only flag
        # when the SAME data-ad-slot appears more than once on a page.
        if has_ads:
            duplicate_slot_count = ad_count - len(unique_slots)
            if duplicate_slot_count > 0:
                slot_repeat = {}
                for m in AD_DATA_SLOT_RE.finditer(html_for_adsense):
                    s = m.group(1)
                    slot_repeat[s] = slot_repeat.get(s, 0) + 1
                duplicated = sorted([s for s, c in slot_repeat.items() if c > 1])
                findings.append(
                    {
                        "site": site["name"],
                        "class": "duplicate_ad_slot",
                        "severity": "high",
                        "file": rel,
                        "details": f"page has {duplicate_slot_count} duplicate ad slot(s); duplicated: {duplicated}",
                        "auto_fixable": True,
                        "fix_class": "dedup_ad_slots",
                        "ad_count": ad_count,
                        "unique_slots": sorted(unique_slots),
                        "duplicated_slots": duplicated,
                    }
                )

        # Skip word-count/E-E-A-T checks for non-classified pages (listing/archives)
        if page_type == "other":
            continue

        # Word count
        text = _extract_visible_text(html_for_adsense)
        word_count = _count_words(text)
        threshold = WORDCOUNT_THRESHOLDS[page_type]

        # Finding 1: word_count_low
        if word_count < threshold:
            severity = "critical" if has_ads else "high"
            findings.append(
                {
                    "site": site["name"],
                    "class": "word_count_low",
                    "severity": severity,
                    "file": rel,
                    "details": f"{word_count}w (threshold {threshold}w for {page_type})",
                    "auto_fixable": False,
                    "word_count": word_count,
                    "threshold": threshold,
                    "page_type": page_type,
                }
            )

        # Finding 2: thin_with_ads (THE AdSense red flag)
        if word_count < threshold and has_ads:
            findings.append(
                {
                    "site": site["name"],
                    "class": "thin_with_ads",
                    "severity": "critical",
                    "file": rel,
                    "details": f"page has {ad_count} ad slot(s) but only {word_count}w (AdSense red flag)",
                    "auto_fixable": False,
                    "word_count": word_count,
                    "threshold": threshold,
                    "ad_count": ad_count,
                }
            )

        # Finding 4: missing_eeat_sections (legal_umbrella pages only)
        if page_type == "legal_umbrella":
            missing = _check_eeat_sections(html_for_adsense, page_type)
            if missing and word_count >= 400:  # only flag pages that have content but missing sections
                findings.append(
                    {
                        "site": site["name"],
                        "class": "missing_eeat_sections",
                        "severity": "high",
                        "file": rel,
                        "details": f"/legal/-class page missing E-E-A-T sections: {', '.join(missing)}",
                        "auto_fixable": False,
                        "missing_sections": missing,
                        "word_count": word_count,
                    }
                )

        # Finding 5: missing_ad_unit (substantial content but no ads = lost revenue)
        if not has_ads and word_count >= 1500:
            findings.append(
                {
                    "site": site["name"],
                    "class": "missing_ad_unit",
                    "severity": "medium",
                    "file": rel,
                    "details": f"{word_count}w of content but no AdSense ins tag (lost revenue opportunity)",
                    "auto_fixable": True,
                    "fix_class": "missing_ad_unit",
                    "word_count": word_count,
                }
            )

    return findings


def _scan_python_for_site(site) -> list:
    """Static analysis of Python files in _build/ or scripts/."""
    findings = []
    src = site.get("source_dir")
    if not src or not src.exists():
        return findings

    py_files = list(src.rglob("_build/*.py")) + list(src.rglob("scripts/*.py"))
    py_files = [p for p in py_files if ".venv" not in p.parts and "node_modules" not in p.parts]

    for p in py_files:
        rel = _relpath(p)
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        try:
            compile(text, str(p), "exec")
        except SyntaxError as e:
            findings.append(
                {
                    "site": site["name"],
                    "class": "python_syntax_error",
                    "severity": "critical",
                    "file": rel,
                    "details": f"{e.msg} at line {e.lineno}",
                    "auto_fixable": False,
                }
            )

        # Hardcoded absolute paths to old locations
        if "/Users/mike/.openclaw/workspace-bacottibot/" in text:
            # Allow it if the file IS a build script that needs the workspace root
            if "_build" not in str(p) and "scripts" not in str(p):
                findings.append(
                    {
                        "site": site["name"],
                        "class": "hardcoded_path",
                        "severity": "low",
                        "file": rel,
                        "details": "hardcoded workspace path; should use Path(__file__).parent",
                        "auto_fixable": False,
                    }
                )

    return findings


def scan_static(site_names: list | None = None) -> list:
    """Main entry point."""
    findings = []
    targets = site_names or [s["name"] for s in SITES]
    for site in SITES:
        if site["name"] not in targets:
            continue
        findings.extend(_scan_html_for_site(site))
        findings.extend(_scan_python_for_site(site))
    return findings
