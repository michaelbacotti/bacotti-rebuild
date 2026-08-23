"""
scan_static.py — Layer 1: scan source files for bugs.

Findings are emitted as a list of dicts:
    {
        "site": "bacotti",
        "class": "ga4_typo" | "missing_favicon" | "broken_internal_link"
                  | "missing_canonical" | "duplicate_h1" | "build_script_error"
                  | "redirect_dangling" | "manifest_malformed",
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


def _relpath(p: Path) -> str:
    """Try to make the path workspace-relative for nicer display."""
    try:
        return str(p.relative_to(Path.home() / ".openclaw" / "workspace-bacottibot"))
    except ValueError:
        return str(p)


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
                    "auto_fixable": False,
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
