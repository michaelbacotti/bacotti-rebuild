#!/usr/bin/env python3
"""
Site Code Audit — orchestrates the full pipeline.

Can be run directly:  python3 scripts/run.py [--scan-only] [--dry-run] [--site <name>]

The Lobster pipeline (scripts/pipeline.py) wraps this for cron use.
"""
import argparse
import json
import sys
import datetime
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from scan_static import scan_static, SITES  # noqa: E402
from scan_live import scan_live  # noqa: E402
from scan_crons import scan_crons  # noqa: E402
from fix import apply_fixes  # noqa: E402
from notify import write_reports  # noqa: E402

WORKSPACE = Path("/Users/mike/.openclaw/workspace-bacottibot")


def main():
    ap = argparse.ArgumentParser(description="Site Code Audit orchestrator")
    ap.add_argument("--scan-only", action="store_true", help="Skip auto-fix step")
    ap.add_argument("--dry-run", action="store_true", help="Show fixes that would be applied")
    ap.add_argument("--site", default=None, help="Audit one site only (e.g. bacotti)")
    args = ap.parse_args()

    started = datetime.datetime.now(datetime.timezone.utc)
    print(f"[code-audit] starting at {started.isoformat()}", flush=True)

    sites = [args.site] if args.site else [s["name"] for s in SITES]
    print(f"[code-audit] scanning {len(sites)} site(s): {sites}", flush=True)

    # Layer 1: static source
    print("[code-audit] phase 1/4: static source scan", flush=True)
    static_findings = scan_static(sites)

    # Layer 2: live HTTP probes
    print("[code-audit] phase 2/4: live HTTP probe", flush=True)
    live_findings = scan_live(sites)

    # Layer 3: cron health
    print("[code-audit] phase 3/4: cron health", flush=True)
    cron_findings = scan_crons()

    all_findings = static_findings + live_findings + cron_findings
    print(f"[code-audit] total findings: {len(all_findings)}", flush=True)

    # Layer 4: auto-fix (if not scan-only)
    fixed = []
    if not args.scan_only and all_findings:
        print("[code-audit] phase 4/4: auto-fix", flush=True)
        fixed = apply_fixes(all_findings, dry_run=args.dry_run)
        print(f"[code-audit] applied {len(fixed)} auto-fix(es)", flush=True)

    # Reports
    print("[code-audit] writing reports", flush=True)
    summary = write_reports(
        findings=all_findings,
        fixed=fixed,
        sites=sites,
        started=started,
    )

    print(
        f"[code-audit] done in "
        f"{(datetime.datetime.now(datetime.timezone.utc) - started).total_seconds():.1f}s"
    )
    print(json.dumps(summary, indent=2))
    return 0 if not any(f.get("severity") == "critical" for f in all_findings) else 1


if __name__ == "__main__":
    sys.exit(main())
