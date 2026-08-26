#!/usr/bin/env python3
"""
scan_source_integrity.py — Layer 4: cron source-of-truth integrity check.

Catches the failure mode that bit dependability.us on 2026-08-26:
the live HTML site shipped fine, but the cron-managed MD source files
were 0 bytes for ~6 weeks because the LLM step was silently failing.

For each cron-managed MD source file:
  - Verify the file exists and has size > 0
  - Verify it was modified within the cron's expected run window
  - Verify a corresponding HTML page exists in the deployed site

Output findings have auto_fixable=False — fixing source-of-truth drift
requires operator judgment (which source to trust, whether to backfill,
whether to disable the broken cron).

Runs as part of the nightly site-code-audit pipeline (run.py). Can be
invoked standalone:

    python3 scripts/scan_source_integrity.py [--json]

Added 2026-08-26 after the morning brief incident where all 32 prior
MD sources in entities/dependability/content/morning-analysis/ were 0 bytes
but production HTML was fine.
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

WORKSPACE = Path("/Users/mike/.openclaw/workspace-bacottibot")

# Each entry: (cron_id, source_pattern, html_pattern, expected_run_window_minutes, label)
# `source_pattern` and `html_pattern` are glob-like paths relative to WORKSPACE.
# `expected_run_window_minutes` is the window after the cron's expected run time
# during which the source file SHOULD have been updated. After that window, no
# update means the cron likely failed silently.
#
# Each entry should be tagged with the OWNING workdesk so QC can route findings
# to the right session via workboard cards.
SOURCE_INTEGRITY_TARGETS = [
    {
        "label": "Dependability morning brief (MD source)",
        "cron_id": "6437c795-bd62-43a2-9a3d-1f8e8948684e",
        "owner_workdesk": "agent:main:dependability-website-manager",
        "site": "dependability",
        "source_pattern": "entities/dependability/content/morning-analysis/*.md",
        "html_pattern": "entities/dependability/website/commentary/*/index.html",
        "expected_run_window_minutes": 15,  # 5:55 AM ET +/- 15 min
        "expected_run_hour_et": 5,
        "expected_run_minute_et": 55,
        "expected_run_dow": "mon-fri",
    },
    {
        "label": "Triadive weekly dispatch (MD source)",
        "cron_id": "b8e229c6-94ff-4d90-b558-cf1ee8a2c8d3",
        "owner_workdesk": "agent:main:triadive-website-manager",
        "site": "triadive",
        "source_pattern": "projects/triadive/content/dispatches/*.md",
        "html_pattern": "projects/triadive/website/dispatches/*/index.html",
        "expected_run_window_minutes": 60,  # weekly — wider window
        "expected_run_hour_et": 11,
        "expected_run_minute_et": 0,
        "expected_run_dow": "sat",
    },
    {
        "label": "Succession weekly brief (MD source)",
        "cron_id": "b0d46aaf-bd11-4aac-b7c0-9113803bdcd0",
        "owner_workdesk": "agent:main:succession-website-manager",
        "site": "succession",
        "source_pattern": "entities/succession/website/content/newsletters/*.md",
        "html_pattern": "entities/succession/website/newsletters/*/index.html",
        "expected_run_window_minutes": 60,
        "expected_run_hour_et": 5,
        "expected_run_minute_et": 0,
        "expected_run_dow": "mon",
    },
    {
        "label": "SpaceOrbitals orbital originals (MD source)",
        "cron_id": "c33bf1d9-2a05-4b71-8b92-61be539cb0f3",
        "owner_workdesk": "agent:main:spaceorbitals-website-manager",
        "site": "spaceorbitals",
        "source_pattern": "projects/spaceorbitals/content/articles/*.md",
        "html_pattern": "projects/spaceorbitals/spaceorbitals/articles/*/index.html",
        "expected_run_window_minutes": 90,
        "expected_run_hour_et": 9,
        "expected_run_minute_et": 0,
        "expected_run_dow": "sat",
    },
    {
        "label": "Bithues crypto daily feed (MD source)",
        "cron_id": "22efc5fc-a480-4a81-8e7e-7114a2a35e91",
        "owner_workdesk": "agent:main:bithues-crypto-website-manager",
        "site": "bithues-crypto",
        "source_pattern": "projects/bithues-crypto/content/research/_feed.md",
        "html_pattern": "projects/bithues-crypto/website/**/*.html",
        "expected_run_window_minutes": 60,
        "expected_run_hour_et": 6,
        "expected_run_minute_et": 0,
        "expected_run_dow": "mon-fri",
    },
    {
        "label": "Bithues books weekly newsletter (MD source)",
        "cron_id": "cbb076d8-5b80-47f5-b1b1-d695f94b1c56",
        "owner_workdesk": "agent:main:bithues-books-website-manager",
        "site": "bithues-books",
        "source_pattern": "projects/bithues/content/newsletters/*.md",
        "html_pattern": "projects/bithues/website/newsletters/*/index.html",
        "expected_run_window_minutes": 90,
        "expected_run_hour_et": 8,
        "expected_run_minute_et": 0,
        "expected_run_dow": "sat",
    },
    {
        "label": "Tredey morning brief (MD source)",
        "cron_id": "19d34fcb-c653-4562-899e-ba189cdcd486",
        "owner_workdesk": "agent:main:tredey-website-manager",
        "site": "tredey",
        "source_pattern": "projects/tredey/content/articles/*.md",
        "html_pattern": "projects/tredey/website/trade-log/*/index.html",
        "expected_run_window_minutes": 60,
        "expected_run_hour_et": 6,
        "expected_run_minute_et": 0,
        "expected_run_dow": "mon-fri",
    },
]


def _list_jobs() -> list:
    """Get current cron job states for cross-referencing."""
    try:
        out = subprocess.run(
            ["openclaw", "cron", "list", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if out.returncode == 0 and out.stdout.strip():
            data = json.loads(out.stdout)
            return data.get("jobs", data) if isinstance(data, dict) else data
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    return []


def _recent_zero_byte_md(source_pattern: str) -> list:
    """Find MD files matching pattern that are 0 bytes."""
    matches = []
    for path in WORKSPACE.glob(source_pattern):
        if path.is_file() and path.stat().st_size == 0:
            matches.append(path)
    return matches





def _html_for_md(md_path: Path, html_pattern: str) -> Optional[Path]:
    """Look up the deployed HTML page that corresponds to a given MD source.

    For daily briefs (YYYY-MM-DD.md), the HTML lives at:
        commentary/YYYY-MM-DD/index.html
    For feed-style files (_feed.md), any html in the pattern counts.
    """
    try:
        # Special case: feed-style files (no date in stem)
        if md_path.stem.startswith("_") or not md_path.stem[:4].isdigit():
            # Feed file — just check if ANY html in the pattern exists
            html_root = WORKSPACE / html_pattern.split("/*/")[0]
            if not html_root.exists():
                # Try deeper — pattern may have / at start
                return None
            return html_root if any(html_root.rglob("*.html")) else None

        # Date-stamped MD — match by stem
        stem = md_path.stem  # e.g. "2026-08-26"
        html_dir = WORKSPACE / html_pattern.split("/*/")[0]
        candidate = html_dir / stem / "index.html"
        return candidate if candidate.exists() else None
    except Exception:
        return None


def _build_finding(
    target: dict,
    severity: str,
    finding_class: str,
    details: str,
    files: list,
) -> dict:
    return {
        "site": target["site"],
        "class": finding_class,
        "severity": severity,
        "file": target["source_pattern"],
        "details": details,
        "auto_fixable": False,
        "cron_id": target["cron_id"],
        "owner_workdesk": target["owner_workdesk"],
        "label": target["label"],
        "files": [str(f.relative_to(WORKSPACE)) for f in files],
    }


def scan_source_integrity() -> list:
    """Run all source-integrity checks. Returns list of findings."""
    findings = []

    for target in SOURCE_INTEGRITY_TARGETS:
        try:
            # Check 1: any 0-byte MDs in this source dir
            zero_byte = _recent_zero_byte_md(target["source_pattern"])
            if zero_byte:
                findings.append(
                    _build_finding(
                        target,
                        "high",
                        "cron_source_zero_byte",
                        (
                            f"{len(zero_byte)} MD source file(s) are 0 bytes. "
                            "Cron LLM step is failing silently. Production HTML may be intact "
                            "but the source-of-truth layer is broken — auto-fixes will not work."
                        ),
                        zero_byte,
                    )
                )

            # Check 2: most recent MD is older than the cron's expected window.
            # Only flag if today IS a scheduled run day AND the run window has closed
            # AND no MD was written in that window.
            import pytz  # type: ignore
            et = pytz.timezone("America/New_York")
            now_et = datetime.now(et)
            weekday_idx = now_et.weekday()  # 0=Mon, 6=Sun

            dow_map = {
                "mon": {0},
                "tue": {1},
                "wed": {2},
                "thu": {3},
                "fri": {4},
                "sat": {5},
                "sun": {6},
                "mon-fri": {0, 1, 2, 3, 4},
                "mon-sat": {0, 1, 2, 3, 4, 5},
                "sat-sun": {5, 6},
            }
            valid_days = dow_map.get(target["expected_run_dow"], set(range(7)))

            if weekday_idx in valid_days:
                # Today IS a scheduled run day — flag if window closed with no fresh MD
                today_expected = now_et.replace(
                    hour=target["expected_run_hour_et"],
                    minute=target["expected_run_minute_et"],
                    second=0,
                    microsecond=0,
                )
                # If today's expected run time hasn't happened yet (e.g. it's 8 AM and run is at 5:55 PM),
                # window hasn't closed — skip
                threshold = today_expected + timedelta(minutes=target["expected_run_window_minutes"])
                if now_et > threshold:
                    md_files = sorted(WORKSPACE.glob(target["source_pattern"]))
                    if not md_files:
                        # No MDs at all on a run day after window closed — flag
                        findings.append(
                            _build_finding(
                                target,
                                "high",
                                "cron_source_missing",
                                (
                                    f"No MD source files exist on a scheduled run day "
                                    f"({target['expected_run_dow']}) after the run window "
                                    f"(closed at {threshold.strftime('%H:%M ET')}). Cron failed silently."
                                ),
                                [],
                            )
                        )
                    else:
                        most_recent = max(md_files, key=lambda p: p.stat().st_mtime)
                        # Is the most-recent MD from today (within run window)?
                        # The cron was scheduled at `today_expected`. If the MD was updated
                        # AFTER `today_expected`, the cron succeeded. If BEFORE, it didn't.
                        if most_recent.stat().st_mtime < today_expected.timestamp():
                            age_minutes = int(
                                (today_expected.timestamp() - most_recent.stat().st_mtime) / 60
                            )
                            findings.append(
                                _build_finding(
                                    target,
                                    "high",
                                    "cron_source_stale",
                                    (
                                        f"Most recent MD is {age_minutes} min older than the cron's "
                                        f"expected run time ({today_expected.strftime('%H:%M ET')}). "
                                        "Cron failed to update the source for today's run."
                                    ),
                                    [most_recent],
                                )
                            )

            # Check 3: MD has matching HTML page (orphan or duplicate detection).
            # Only meaningful for date-stamped daily briefs (each MD should have a fresh HTML).
            # Evergreen article MDs (Tredey, etc.) are typically rendered once and stay —
            # flagging them as "no html" creates false positives.
            # We detect a "daily brief" pattern by the source-pattern containing * and the
            # MD stem matching YYYY-MM-DD. Anything else is treated as evergreen.
            md_files = sorted(WORKSPACE.glob(target["source_pattern"]))
            for md in md_files:
                if md.stat().st_size == 0:
                    continue  # Already flagged above
                # Only check daily-brief-style stems
                stem = md.stem
                if len(stem) >= 10 and stem[4] == "-" and stem[7] == "-":
                    html = _html_for_md(md, target["html_pattern"])
                    if html is None:
                        findings.append(
                            _build_finding(
                                target,
                                "low",
                                "cron_source_no_html",
                                (
                                    f"Daily brief MD {md.name} has no corresponding HTML page. "
                                    "Build pipeline may have failed to render this file."
                                ),
                                [md],
                            )
                        )

        except Exception as e:
            findings.append(
                {
                    "site": target["site"],
                    "class": "cron_source_check_error",
                    "severity": "medium",
                    "file": target["source_pattern"],
                    "details": f"Source-integrity check errored: {e}",
                    "auto_fixable": False,
                    "cron_id": target["cron_id"],
                    "owner_workdesk": target["owner_workdesk"],
                    "label": target["label"],
                }
            )

    return findings


def main():
    ap = argparse.ArgumentParser(description="Cron source-of-truth integrity scanner")
    ap.add_argument("--json", action="store_true", help="Output JSON only")
    args = ap.parse_args()

    findings = scan_source_integrity()

    if args.json:
        print(json.dumps(findings, indent=2))
    else:
        print(f"[source-integrity] {len(findings)} finding(s)")
        for f in findings:
            print(f"  [{f['severity']:>6}] {f['class']:30} {f['label']}")
            print(f"          {f['details']}")
            if f.get("files"):
                for path in f["files"]:
                    print(f"          file: {path}")
            print(f"          owner: {f['owner_workdesk']}  cron: {f['cron_id']}")

    return 1 if any(f.get("severity") in ("high", "critical") for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())