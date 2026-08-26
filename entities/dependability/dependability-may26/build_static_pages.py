#!/usr/bin/env python3
"""
build_static_pages.py — render MD source-of-truth files in
content/pages/ to HTML in website/{slug}/index.html.

Static pages covered (2026-08-26 roster):
  - about
  - privacy
  - disclaimer
  - methodology
  - terms
  - contact

Source of truth: entities/dependability/content/pages/<slug>.md
Output: entities/dependability/website/<slug>/index.html

Each page is wrapped in _template.html (the same template used for
articles) with the standard EEAT block appended.

Anti-pattern #123 (fabricated credentials) is enforced: this script
REJECTS build if the rendered EEAT block contains any banned string
('Cboe trading floor community', 'Mike Bacotti', 'practitioner-level.*licensed', etc.).

Usage:
    python3 build_static_pages.py                # build all 6
    python3 build_static_pages.py about          # build one
    python3 build_static_pages.py --check        # dry run / verify only
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

THIS_FILE = Path(__file__).resolve()
THIS_DIR = THIS_FILE.parent
ENTITY_DIR = THIS_DIR.parent
PAGES_DIR = ENTITY_DIR / "content" / "pages"
WEBSITE_DIR = ENTITY_DIR / "website"

# Import shared utilities from build.py
sys.path.insert(0, str(THIS_DIR))
from build import (  # noqa: E402  (import after path manipulation)
    wrap_in_template,
    parse_front_matter,
    md_to_html,
    DEPENDABILITY_EEAT_BLOCK,
)

# Static pages covered (locked 2026-08-26)
STATIC_PAGES = [
    "about",
    "privacy",
    "disclaimer",
    "methodology",
    "terms",
    "contact",
]

# Anti-pattern #123 enforcement
BANNED_EEAT_PHRASES = [
    "Cboe trading floor community",
    "Cboe floor community",
    "practitioner-level licensed",
    "practitioner-level.*licensed",
    "Mike Bacotti",
    "Michael Bacotti",
    "complete trade journal covering every position",
    "verifiable against our brokerage statements",
]


def render_static_page(slug: str, dry_run: bool = False) -> tuple[str, str]:
    """Render content/pages/<slug>.md → website/<slug>/index.html.

    Returns (output_path, body_html_preview) on success.
    Raises ValueError on anti-pattern #123 violation.
    """
    md_path = PAGES_DIR / f"{slug}.md"
    if not md_path.exists():
        raise FileNotFoundError(f"MD source not found: {md_path}")

    raw = md_path.read_text(encoding="utf-8")
    meta, body = parse_front_matter(raw)

    title = meta.get("title", slug.replace("-", " ").title())
    description = meta.get("description", "")
    canonical = meta.get("canonical", f"/{slug}/")

    # Map static pages to nav active state
    nav_map = {
        "about": "about",
        "privacy": "about",
        "disclaimer": "about",
        "methodology": "methodology",
        "terms": "about",
        "contact": "contact",
    }
    active_nav = nav_map.get(slug, "")

    # Render body MD → HTML
    body_html = md_to_html(body)

    # Build the page-EEAT block (consistent with articles)
    eeat_html = DEPENDABILITY_EEAT_BLOCK

    # Anti-pattern #123 gate: refuse to ship if either the body or the EEAT
    # block contains a banned phrase.
    full_html = body_html + eeat_html
    for banned in BANNED_EEAT_PHRASES:
        pattern = banned
        if re.search(pattern, full_html, re.IGNORECASE):
            raise ValueError(
                f"Anti-pattern #123 triggered on {slug}.md — "
                f"banned phrase detected: '{banned}'. "
                f"Edit the MD source to remove the false claim, "
                f"or update {THIS_DIR / 'build.py'}'s DEPENDABILITY_EEAT_BLOCK."
            )

    # Build main content: rendered body + a styled wrap section + EEAT box
    main_html = f"""
<section style="padding: 3.5rem 0 2.5rem;">
 <div style="max-width: 760px; margin: 0 auto; padding: 0 1.5rem;">
  <h1 style="font-size: 2.25rem; margin-bottom: 1.5rem; color: #1a1a1a;">{title}</h1>
  <div style="display: grid; gap: 1.5rem;">
   {body_html}
  </div>
 </div>
</section>
{eeat_html}
"""

    # Wrap in standard template
    rendered = wrap_in_template(
        page_title=title,
        page_desc=description,
        main_html=main_html,
        active_nav=active_nav,
        canonical_url=canonical,
    )

    out_path = WEBSITE_DIR / slug / "index.html"
    if not dry_run:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered, encoding="utf-8")

    return (str(out_path), body_html[:200])


def main(argv: list[str]) -> int:
    dry_run = "--check" in argv
    argv = [a for a in argv if a != "--check"]

    targets = STATIC_PAGES if not argv else [a for a in argv if a in STATIC_PAGES]
    if not targets:
        targets = STATIC_PAGES

    print(f"Building {len(targets)} static page(s)...")
    print(f"Source of truth: {PAGES_DIR}/")
    print(f"Output: {WEBSITE_DIR}/{{slug}}/index.html")
    print(f"Mode: {'dry-run' if dry_run else 'write'}")
    print()

    for slug in targets:
        try:
            out_path, _preview = render_static_page(slug, dry_run=dry_run)
            mode = "✓ verified" if dry_run else "✓ wrote"
            print(f"  [{mode}] {slug}  →  {out_path}")
        except ValueError as e:
            print(f"  [✗ BLOCKED] {slug}: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"  [✗ ERROR] {slug}: {e}", file=sys.stderr)
            return 2

    print()
    print(f"Done. {len(targets)} static page(s) {'verified' if dry_run else 'rebuilt'}.")
    print()
    print("Next steps:")
    print("  1. Optional proofreading: curl the live URL and grep")
    print("  2. Commit + push via dependability-rebuild repo (git push origin main)")
    print("  3. CF Pages auto-deploys on push (~30s propagation)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
