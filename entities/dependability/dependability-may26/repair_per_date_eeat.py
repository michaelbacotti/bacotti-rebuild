#!/usr/bin/env python3
"""
repair_per_date_eeat.py — Patch the EEAT block on existing per-date commentary
HTML files in website/commentary/YYYY-MM-DD/index.html.

The morning cron historically inline-wrote per-date HTML pages, embedding the
EEAT block from the cron prompt at the time of writing. When the EEAT source
of truth in build_morning.py changes, the per-date pages are not regenerated
automatically. This script does a targeted string replacement on each
per-date page to swap in the new EEAT block.

Idempotent: re-running on already-patched pages is a no-op (no change).

Usage:
    python3 repair_per_date_eeat.py            # all per-date pages
    python3 repair_per_date_eeat.py 2026-08-26  # one date
    python3 repair_per_date_eeat.py --dry-run  # verify, don't write
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

THIS_FILE = Path(__file__).resolve()
THIS_DIR = THIS_FILE.parent
ENTITY_DIR = THIS_DIR.parent
WEBSITE_DIR = ENTITY_DIR / "website"
COMMENTARY_DIR = WEBSITE_DIR / "commentary"

# OLD EEAT block (the wrong text with "complete trade journal" and "verifiable
# against our brokerage statements"). Capture as raw text to do an exact
# string replace.

OLD_EEAT_LINES = [
    '<section class="eeat-block" aria-label="About this article">',
    ' <h2>About this article</h2>',
    ' <p><strong>Editor:</strong> The <a href="https://dependability.us/about/">Dependability Holdings LLC</a> Research Desk has tracked derivatives market structure and options positioning since the firm&rsquo;s launch in <time datetime="2019">2019</time>, with a documented public trade-log and the &ldquo;How we forecast&rdquo; methodology that anchors every brief on the site.</p>',
    ' <p><strong>Launched:</strong> Dependability went live in <time datetime="2024-03">March 2024</time> as a single weekday morning brief covering S&amp;P 500 levels, VIX dynamics, and what to do with options positions that week. It now publishes a daily morning analysis, weekly forecast, and a complete trade journal covering every position the desk has placed since launch.</p>',
    ' <p><strong>Editorial process:</strong> Each piece distils primary reporting (Cboe options data, OCC positioning, FRED macro series, SEC filings, Federal Reserve releases) into a worked-example frame: <em>what the data says, why it matters, what to do this week</em>. Forecasts are screened against the <a href="/forecast/">forecast archive</a> and cross-checked against at least one confirming primary source before publication. Forecasts that turn out wrong receive a <a href="/archive/">post-mortem</a> within 30 days.</p>',
    ' <p><strong>Corrections policy:</strong> When an article gets a fact wrong, we correct it inline and append a dated correction note at the top of the next morning brief. Send corrections to <a href="mailto:corrections@dependability.us">corrections@dependability.us</a> &mdash; we aim to acknowledge within 48 hours.</p>',
    ' <p><strong>Disclosure:</strong> Dependability Holdings LLC is a research entity, not a registered investment adviser or broker-dealer. Nothing on this site is investment advice or a recommendation to buy, sell, or hold any security. The desk may hold positions mentioned in any article; the <a href="/trade-log/">trade log</a> is the public record of those positions, with each entry timestamped and verifiable against our brokerage statements.</p>',
    '</section>',
]

# NEW EEAT block (the corrected text). Comes from build_morning.py — the
# canonical source of truth.
# This must match the corrected content in build_morning.py.
NEW_EEAT_BLOCK = """<section class="eeat-block" aria-label="About this article">
 <h2>About this article</h2>
 <p><strong>Editor:</strong> The <a href="https://dependability.us/about/">Dependability Holdings LLC</a> Research Desk has tracked derivatives market structure and options positioning since the firm&rsquo;s launch in <time datetime="2019">2019</time>, with a documented public position tracker and the &ldquo;How we forecast&rdquo; methodology that anchors every brief on the site.</p>
 <p><strong>Launched:</strong> Dependability went live in <time datetime="2024-03">March 2024</time> as a single weekday morning brief covering S&amp;P 500 levels, VIX dynamics, and what to do with options positions that week. Today it publishes a daily morning analysis, a weekly forecast, and a public <a href="/trade-log/">position tracker</a> for every published position the desk holds in its own portfolio. The journal of executed trades lives on <a href="https://tredey.com/forecasts/">tredey.com</a>.</p>
 <p><strong>Editorial process:</strong> Each piece distils primary reporting (Cboe options data, OCC positioning, FRED macro series, SEC filings, Federal Reserve releases) into a worked-example frame: <em>what the data says, why it matters, what to do this week</em>. Forecasts are screened against the <a href="/forecast/">forecast archive</a> and cross-checked against at least one confirming primary source before publication. Forecasts that turn out wrong receive a <a href="/archive/">post-mortem</a> within 30 days.</p>
 <p><strong>Corrections policy:</strong> When an article gets a fact wrong, we correct it inline and append a dated correction note at the top of the next morning brief. Send corrections to <a href="mailto:corrections@dependability.us">corrections@dependability.us</a> &mdash; we aim to acknowledge within 48 hours.</p>
 <p><strong>Disclosure:</strong> Dependability Holdings LLC is a research entity, not a registered investment adviser or broker-dealer. Nothing on this site is investment advice or a recommendation to buy, sell, or hold any security. The desk may hold positions mentioned in any article; the <a href="/trade-log/">position tracker</a> on this site shows current and historical positions held by the desk, and the journal of closed trades is on <a href="https://tredey.com/forecasts/">tredey.com</a>.</p>
</section>"""


def patch_file(path: Path, dry_run: bool = False) -> tuple[bool, int]:
    """Patch one per-date commentary HTML. Returns (changed, hits)."""
    if not path.exists():
        return (False, 0)

    html = path.read_text(encoding="utf-8")

    # Check if OLD EEAT block is present
    # Use a multi-line match — match the whole block as a substring
    old_block_re = re.compile(
        r'<section class="eeat-block" aria-label="About this article">'
        r'.*?verifiable against our brokerage statements\.</p>'
        r'\s*</section>',
        re.DOTALL,
    )

    matches = list(old_block_re.finditer(html))
    if not matches:
        return (False, 0)

    # Replace ALL occurrences (one per page, but defensive)
    new_html = old_block_re.sub(NEW_EEAT_BLOCK, html)
    changed = (new_html != html)
    if changed and not dry_run:
        path.write_text(new_html, encoding="utf-8")
    return (changed, len(matches))


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv
    argv = [a for a in argv if a != "--dry-run"]

    target_dates = None
    if argv:
        target_dates = [
            a for a in argv
            if re.match(r"\d{4}-\d{2}-\d{2}$", a)
        ]

    if target_dates:
        targets = [COMMENTARY_DIR / d / "index.html" for d in target_dates]
    else:
        if not COMMENTARY_DIR.exists():
            print(f"ERROR: {COMMENTARY_DIR} not found")
            return 1
        targets = sorted(COMMENTARY_DIR.glob("????-??-??/index.html"))

    if not targets:
        print("No per-date commentary HTML files found.")
        return 0

    print(f"Mode: {'dry-run' if dry_run else 'patch'}")
    print(f"Found {len(targets)} per-date commentary page(s)")
    print()

    total_changed = 0
    for path in targets:
        if not path.exists():
            print(f"  [skip] {path.name} (file not found)")
            continue
        date_iso = path.parent.name
        changed, hits = patch_file(path, dry_run=dry_run)
        if changed:
            action = "would patch" if dry_run else "patched"
            print(f"  [{action}] commentary/{date_iso}/index.html  ({hits} EEAT block hit(s))")
            total_changed += 1
        else:
            if hits == 0:
                print(f"  [no change needed] commentary/{date_iso}/index.html  (no OLD EEAT block found)")
            else:
                print(f"  [already clean] commentary/{date_iso}/index.html")

    print()
    if dry_run:
        print(f"Dry run: {total_changed} pages would be patched. Re-run without --dry-run to apply.")
    else:
        print(f"Done. {total_changed} page(s) patched.")
        print()
        print("Next steps:")
        print("  cd /Users/mike/.openclaw/workspace-bacottibot/entities/dependability/website")
        print("  git add commentary/")
        print("  git commit -m 'Update per-date commentary EEAT blocks: replace false trade-journal + brokerage claim with position-tracker + tredey.com reference (Anti-Pattern #123, Mike 2026-08-26 14:11 ET)'")
        print("  git push origin main")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
