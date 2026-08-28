#!/usr/bin/env python3
"""
verify_published.py — Post-publish quality gate for cron-rendered content.

Runs against rendered HTML after a site build. Catches:
- Word count below 800w (warn) / 400w (fail)
- Missing AdSense <ins class="adsbygoogle"> tag
- Missing canonical URL
- Missing 5-section E-E-A-T recipe (anti-pattern #89 wipe check)
- Build-source mismatch (E-E-A-T hand-edited into HTML but build will wipe it)

Used by:
- autonomous-content-publishing publish.py (called after build)
- Cron pipelines that render HTML from MD source
- Manual audit (skills/site-code-audit/scripts/run.py)

Exit codes:
  0 = all checks pass (or warnings only)
  1 = at least one fail
  2 = usage error

Output: machine-readable JSON (--json) or human-readable (default).
"""
import argparse
import json
import re
import sys
from pathlib import Path

WORKSPACE = Path("/Users/mike/.openclaw/workspace-bacottibot")

# Quality thresholds (Mike's standard, 2026-08-23)
MIN_WORDS_FAIL = 400    # below this is a hard fail
MIN_WORDS_WARN = 800    # below this is a warning (1200w preferred)
PREFERRED_WORDS = 1200

# E-E-A-T recipe substrings (at least one must appear in E-E-A-T block).
# Pattern is case-insensitive substring match. Each pattern should tolerate
# intervening HTML tags between words (e.g. <strong>Editor:</strong> Mike).
EEAT_RECIPE = {
    "named_editor":     [r"editor\b[^<>]{0,40}mike\s+bacotti", r"by\s+mike\s+bacotti", r"mike\s+bacotti,\s*founder"],
    "credentials":      [r"custody", r"market structure", r"since\s+20\d{2}", r"bylines?\s+at"],
    "launch_date":      [r"launched\s+in", r"went live", r"\bsince\s+201[78]\b", r"\bsince\s+202[0-6]\b"],
    "editorial_process":[r"editorial process", r"worked-example", r"distil(?:s|ed)?\s+primary"],
    "corrections_policy":[r"corrections?\s+policy", r"correct\s+it\s+inline", r"append\s+a\s+dated\s+correction"],
    "disclosure":       [r"disclosure", r"not\s+financial\s+advice", r"no\s+trading\s+signals"],
}

# Common AdSense patterns
ADSENSE_PATTERNS = [
    r'<ins\s+class="adsbygoogle"',
    r"data-ad-client",
    r"ca-pub-",
    r"googletagmanager\.com",
]

# Per-site HTML roots to scan (relative to WORKSPACE)
SITE_HTML_ROOTS = {
    "bithues":         "projects/bithues-crypto/website",
    "bithues-books":   "projects/bithues/website",
    "dependability":   "entities/dependability/website",
    "triadive":        "projects/triadive/website",
    "tredey":          "projects/tredey/website",
    "succession":      "entities/succession/website",
    "spaceorbitals":   "projects/spaceorbitals/spaceorbitals",
    "wildwood-press":  "projects/wildwood-press/website",
    "bacotti":         "entities/bacotti-inc/website",
}


def strip_html(html: str) -> str:
    """Return plain text from HTML, suitable for word count."""
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-z#0-9]+;", " ", text)
    return text


def count_words(html: str) -> int:
    """Count words in HTML body."""
    text = strip_html(html)
    return len([w for w in re.findall(r"\b[\w'-]+\b", text) if len(w) >= 2])


def has_adsense(html: str) -> bool:
    """Check for AdSense ins tag or equivalent."""
    return any(re.search(p, html, re.IGNORECASE) for p in ADSENSE_PATTERNS)


def has_canonical(html: str) -> bool:
    """Check for canonical link tag."""
    return bool(re.search(
        r'<link[^>]+rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']',
        html, re.IGNORECASE))


def eeat_section_present(html: str) -> dict:
    """Check whether the rendered HTML carries the 5-section E-E-A-T recipe.

    Anti-pattern #89: E-E-A-T lives ONLY in the MD source / build template, not
    hand-edited into the HTML. If E-E-A-T is hand-edited into HTML, the next
    cron run will wipe it. We check both presence AND that the E-E-A-T is in a
    baked section (class .eeat-block), not scattered through the article body.

    Returns:
      {
        "section_present": bool,
        "section_marker": str | None,   # the wrapper class if found
        "recipe_coverage": {key: bool}, # per-key coverage
        "hand_edited_only": bool,        # E-E-A-T exists but NOT in build template
        "warnings": [str]
      }
    """
    # Find the E-E-A-T block wrapper. Include the closing quote so the
    # class value is captured properly.
    section_match = re.search(
        r'<(?:section|aside|div)[^>]+class=["\']([^"\']*\b(?:eeat-block|eeat|about-brief|byline-box)\b[^"\']*)["\']',
        html, re.IGNORECASE,
    )
    section_marker = None
    if section_match:
        section_marker = section_match.group(1)

    # Look at the whole HTML, but if section_marker exists, scope to that section
    if section_match:
        # find the closing tag of the same element type
        tag_match = re.match(r"<(\w+)", section_match.group(0))
        tag = tag_match.group(1) if tag_match else "section"
        # crude matching — find matching close tag (handles simple nesting)
        depth = 1
        pos = section_match.end()
        end_pos = len(html)
        while pos < len(html) and depth > 0:
            next_open = html.find(f"<{tag}", pos)
            next_close = html.find(f"</{tag}>", pos)
            if next_close == -1:
                break
            if next_open != -1 and next_open < next_close:
                depth += 1
                pos = next_open + len(tag) + 1
            else:
                depth -= 1
                pos = next_close + len(tag) + 3
        end_pos = pos
        scope = html[section_match.start():end_pos]
    else:
        scope = html
        section_marker = None

    coverage = {}
    for key, patterns in EEAT_RECIPE.items():
        coverage[key] = any(re.search(p, scope, re.IGNORECASE) for p in patterns)

    present = sum(1 for v in coverage.values() if v)
    warnings = []

    # Anti-pattern #89 check: E-E-A-T must be in the build template, not
    # hand-edited HTML. If we find E-E-A-T markers but NO .eeat-block wrapper,
    # that's the hand-edited case — the next cron will wipe it.
    hand_edited = False
    if present >= 3 and section_marker is None:
        hand_edited = True
        warnings.append(
            "anti-pattern #89: E-E-A-T appears in HTML but is NOT wrapped in "
            ".eeat-block / .eeat / .byline-box — next cron run will wipe it"
        )

    # Recipe coverage warnings
    for key, ok in coverage.items():
        if not ok:
            warnings.append(f"missing E-E-A-T key: {key}")

    return {
        "section_present": section_match is not None,
        "section_marker": section_marker,
        "recipe_coverage": coverage,
        "recipe_present": present,
        "recipe_total": len(EEAT_RECIPE),
        "hand_edited_only": hand_edited,
        "warnings": warnings,
    }


def has_duplicate_footer(html: str) -> dict:
    """Detect duplicate Sources / Disclaimer footer blocks.

    Perplexity audit 2026-08-28: cron agent sometimes writes the Sources +
    Disclaimer pair twice in the body of an article (once in the MD body, once
    in the rendered HTML), separated by an <hr>. This reads as a copy-paste
    error, weakens polish, and looks like a "thin templated" page to AdSense
    and Google helpful-content evaluation.

    Returns:
      {
        "sources_count": int,
        "disclaimer_count": int,
        "duplicate": bool,
      }
    """
    # Count occurrences inside <p>/<em>/plain text — match the rendered block
    # regardless of whether the cron emitted "<em>Sources:" or "<p><em>Sources:"
    sources_count = len(re.findall(r"<em>\s*Sources:", html, re.IGNORECASE))
    disclaimer_count = len(re.findall(r"<em>\s*Disclaimer:", html, re.IGNORECASE))
    duplicate = sources_count > 1 or disclaimer_count > 1
    return {
        "sources_count": sources_count,
        "disclaimer_count": disclaimer_count,
        "duplicate": duplicate,
    }


def verify_file(html_path: Path) -> dict:
    """Verify a single HTML file. Returns a result dict."""
    try:
        html = html_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {
            "file": str(html_path),
            "ok": False,
            "error": f"read failed: {e}",
        }
    try:
        rel_file = str(html_path.relative_to(WORKSPACE))
    except ValueError:
        rel_file = str(html_path)

    words = count_words(html)
    adsense = has_adsense(html)
    canonical = has_canonical(html)
    eeat = eeat_section_present(html)
    footer = has_duplicate_footer(html)

    # Determine severity
    failures = []
    warnings = []

    if words < MIN_WORDS_FAIL:
        failures.append(f"word count {words} < {MIN_WORDS_FAIL} (FAIL threshold)")
    elif words < MIN_WORDS_WARN:
        warnings.append(f"word count {words} < {MIN_WORDS_WARN} (prefer {PREFERRED_WORDS})")

    if not adsense:
        failures.append("missing AdSense <ins> tag")

    if not canonical:
        warnings.append("missing canonical URL")

    # E-E-A-T: warn on hand-edited, fail on recipe coverage gap
    if eeat["hand_edited_only"]:
        failures.append(eeat["warnings"][0] if eeat["warnings"] else "hand-edited E-E-A-T (anti-pattern #89)")

    if eeat["section_present"]:
        missing = [k for k, v in eeat["recipe_coverage"].items() if not v]
        if missing:
            failures.append(f"E-E-A-T block missing keys: {', '.join(missing)}")
    else:
        warnings.append("no E-E-A-T section wrapper found (class .eeat-block)")

    # Anti-pattern: duplicate Sources / Disclaimer footer blocks (added 2026-08-28).
    # Per Perplexity audit: duplicate footer is a copy-paste error that reads as
    # thin templated content. Strip the duplicate before publishing.
    if footer["duplicate"]:
        failures.append(
            f"duplicate Sources/Disclaimer footer "
            f"(Sources={footer['sources_count']}, Disclaimer={footer['disclaimer_count']}) — "
            f"strip duplicate + intervening <hr>; should be exactly 1 of each"
        )

    return {
        "file": rel_file,
        "words": words,
        "adsense": adsense,
        "canonical": canonical,
        "eeat": {
            "section_present": eeat["section_present"],
            "section_marker": eeat["section_marker"],
            "recipe_present": eeat["recipe_present"],
            "recipe_total": eeat["recipe_total"],
        },
        "footer": {
            "sources_count": footer["sources_count"],
            "disclaimer_count": footer["disclaimer_count"],
            "duplicate": footer["duplicate"],
        },
        "warnings": warnings,
        "failures": failures,
        "ok": len(failures) == 0,
    }


def scan_site(site: str, recursive: bool = True, skip_patterns: list[str] | None = None) -> list[dict]:
    """Scan all HTML files in a site's web root."""
    if site not in SITE_HTML_ROOTS:
        raise ValueError(f"unknown site: {site}; known: {list(SITE_HTML_ROOTS)}")
    root = WORKSPACE / SITE_HTML_ROOTS[site]
    if not root.exists():
        raise FileNotFoundError(f"site root not found: {root}")

    skip = re.compile("|".join(skip_patterns or [
        r"^/404", r"/404\.html$", r"/_redirects", r"/_template",
        r"/robots\.txt$", r"/sitemap\.xml$", r"/favicon",
        r"/apple-touch-icon", r"/og-image",
    ]))

    results = []
    pattern = "**/*.html" if recursive else "*.html"
    for html_path in sorted(root.glob(pattern)):
        if html_path.is_dir():
            continue
        rel = "/" + str(html_path.relative_to(root))
        if skip.search(rel):
            continue
        results.append(verify_file(html_path))
    return results


def main():
    ap = argparse.ArgumentParser(description="Verify published HTML quality")
    ap.add_argument("--site", help="Site key (e.g. bithues, triadive)")
    ap.add_argument("--file", help="Single file (relative to workspace)")
    ap.add_argument("--all", action="store_true", help="Scan all known sites")
    ap.add_argument("--json", action="store_true", help="JSON output")
    ap.add_argument("--quiet", action="store_true", help="Only print failures")
    args = ap.parse_args()

    if not (args.site or args.file or args.all):
        ap.error("one of --site, --file, or --all is required")

    results = []
    if args.file:
        p = WORKSPACE / args.file
        results.append(verify_file(p))
    elif args.site:
        results = scan_site(args.site)
    elif args.all:
        for site in SITE_HTML_ROOTS:
            try:
                results.extend(scan_site(site))
            except (FileNotFoundError, ValueError) as e:
                results.append({"site": site, "ok": False, "error": str(e)})

    # Aggregate
    n_files = len(results)
    n_pass = sum(1 for r in results if r.get("ok"))
    n_fail = n_files - n_pass

    summary = {
        "files": n_files,
        "pass": n_pass,
        "fail": n_fail,
        "exit_code": 0 if n_fail == 0 else 1,
        "results": results,
    }

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        if not args.quiet:
            print(f"verify_published: {n_pass}/{n_files} files pass")
        for r in results:
            if r.get("ok") and args.quiet:
                continue
            status = "OK" if r.get("ok") else "FAIL"
            file_str = r.get("file", r.get("site", "?"))
            print(f"[{status}] {file_str}  words={r.get('words','?')}  adsense={r.get('adsense','?')}")
            for w in r.get("warnings", []):
                print(f"  warn: {w}")
            for f in r.get("failures", []):
                print(f"  FAIL: {f}")
            if r.get("error"):
                print(f"  error: {r['error']}")

    sys.exit(summary["exit_code"])


if __name__ == "__main__":
    main()