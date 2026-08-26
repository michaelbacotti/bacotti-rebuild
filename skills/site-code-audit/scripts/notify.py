"""
notify.py — write JSON + Markdown reports, update workspace state, create workboard cards.
"""
import json
import datetime
from pathlib import Path
from collections import Counter, defaultdict

WORKSPACE = Path("/Users/mike/.openclaw/workspace-bacottibot")
MEMORY_DIR = WORKSPACE / "memory" / "memory"
STATE_FILE = WORKSPACE / "memory" / ".workspace-state.json"


class _SafeEncoder(json.JSONEncoder):
    """Coerce PosixPath/Path → str, datetimes → isoformat, anything else → str."""
    def default(self, obj):
        if isinstance(obj, (Path,)):
            return str(obj)
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        return repr(obj)


def _today():
    return datetime.date.today().isoformat()


def write_reports(findings: list, fixed: list, sites: list, started: datetime) -> dict:
    today = _today()
    summary = {
        "date": today,
        "started_at": started.isoformat(),
        "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "sites_audited": sites,
        "total_findings": len(findings),
        "by_severity": dict(Counter(f.get("severity", "unknown") for f in findings)),
        "by_class": dict(Counter(f.get("class", "unknown") for f in findings)),
        "auto_fixed": len(fixed),
        "needs_attention": [
            f for f in findings
            if not f.get("auto_fixable") and f.get("severity") in ("critical", "high")
        ],
    }

    # JSON report
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    json_path = MEMORY_DIR / f"code-audit-{today}.json"
    json_path.write_text(
        json.dumps(
            {
                "summary": summary,
                "findings": findings,
                "fixed": fixed,
            },
            indent=2,
            cls=_SafeEncoder,
        )
    )

    # Markdown summary
    md = _render_md(summary, findings, fixed)
    md_path = MEMORY_DIR / f"code-audit-{today}.md"
    md_path.write_text(md)

    # Update workspace-state.json
    _update_state(summary, findings)

    return summary


def _render_md(summary, findings, fixed) -> str:
    lines = [
        f"# Site Code Audit — {summary['date']}",
        "",
        f"**Sites audited:** {', '.join(summary['sites_audited'])}",
        f"**Findings:** {summary['total_findings']} total | "
        f"**Auto-fixed:** {summary['auto_fixed']} | "
        f"**Needs attention:** {len(summary['needs_attention'])}",
        "",
        "## Severity breakdown",
        "",
    ]
    for sev in ("critical", "high", "medium", "low"):
        n = summary["by_severity"].get(sev, 0)
        if n:
            lines.append(f"- **{sev}:** {n}")

    if summary["needs_attention"]:
        lines.extend(["", "## 🚨 Needs attention", ""])
        for f in summary["needs_attention"]:
            lines.append(
                f"- `{f.get('site')}` **{f.get('class')}** ({f.get('severity')}) — "
                f"{f.get('file')}: {f.get('details')}"
            )

    if fixed:
        lines.extend(["", "## 🔧 Auto-fixed", ""])
        for fx in fixed:
            lines.append(
                f"- `{fx.get('fix_class')}` on `{fx.get('file')}`"
                + (f" — {fx.get('after')}" if fx.get("after") else "")
            )

    # Group remaining findings by site
    by_site = defaultdict(list)
    for f in findings:
        if f in summary["needs_attention"] or any(
            fx.get("file") == f.get("file") for fx in fixed
        ):
            continue
        by_site[f.get("site", "?")].append(f)

    if by_site:
        lines.extend(["", "## 📋 Other findings", ""])
        for site, items in sorted(by_site.items()):
            lines.append(f"### {site} ({len(items)})")
            lines.append("")
            for f in items[:10]:  # cap per-site
                lines.append(
                    f"- `{f.get('class')}` ({f.get('severity')}) — {f.get('details')}"
                )
            if len(items) > 10:
                lines.append(f"- …and {len(items) - 10} more")
            lines.append("")

    return "\n".join(lines) + "\n"


def _update_state(summary, findings):
    if not STATE_FILE.exists():
        return
    try:
        state = json.loads(STATE_FILE.read_text())
    except Exception:
        return
    state["lastUpdated"] = summary["completed_at"]
    state["lastCodeAudit"] = {
        "date": summary["date"],
        "total": summary["total_findings"],
        "by_severity": summary["by_severity"],
        "auto_fixed": summary["auto_fixed"],
        "needs_attention_count": len(summary["needs_attention"]),
    }

    # Roll forward carryoverItems: remove resolved, add new high/critical
    existing_ids = {item.get("id") for item in state.get("carryoverItems", [])}
    new_ids = set()
    for f in findings:
        if f.get("severity") not in ("critical", "high") or not f.get("auto_fixable"):
            continue
        # Synthesize an id
        f_id = f"code-audit-{f.get('site')}-{f.get('class')}-{f.get('file', '')[:40]}"
        new_ids.add(f_id)
        if f_id in existing_ids:
            continue
        state.setdefault("carryoverItems", []).append(
            {
                "id": f_id,
                "site": f.get("site"),
                "firstSeen": summary["date"],
                "severity": f.get("severity"),
                "status": "open",
                "class": f.get("class"),
                "file": f.get("file"),
                "description": f.get("details"),
            }
        )

    # Drop resolved
    state["carryoverItems"] = [
        item for item in state.get("carryoverItems", [])
        if item.get("id") in new_ids or item.get("status") == "escalated"
    ]

    STATE_FILE.write_text(json.dumps(state, indent=2))


def create_workboard_cards_for_cron_findings(findings: list) -> list:
    """For each high/critical cron-source finding, create a workboard card
    on the owning website-manager's board.

    Cards include: severity, source path, cron_id, suggested next step.
    Returns list of card IDs created.
    """
    import os
    import subprocess
    cards = []
    for f in findings:
        if f.get("class") not in (
            "cron_source_stale",
            "cron_source_missing",
            "cron_source_zero_byte",
        ):
            continue
        if f.get("severity") not in ("critical", "high"):
            continue
        owner = f.get("owner_workdesk", "")
        if not owner:
            continue

        # Map owner workdesk → board id (board ids use website-* prefix)
        # e.g. agent:main:dependability-website-manager → website-dependability
        site_key = (
            owner.replace("agent:main:", "")
            .replace("-website-manager", "")
            .replace("-xo", "")
        )
        board_id = f"website-{site_key}"

        title = f"[{f.get('severity', '?')}] {f.get('label', 'cron-source')}: {f.get('details', '')[:120]}"
        body = (
            f"**Source path:** `{f.get('file', '?')}`\n"
            f"**Cron ID:** `{f.get('cron_id', '?')}`\n"
            f"**Class:** `{f.get('class', '?')}`\n"
            f"**Severity:** `{f.get('severity', '?')}`\n"
            f"**Details:** {f.get('details', '')}\n\n"
            f"**Files:**\n" + "\n".join(f"- `{p}`" for p in f.get("files", [])) + "\n\n"
            f"**Suggested next step:**\n"
            f"1. Check the cron's last run status — was it FailoverError, timeout, or empty-output?\n"
            f"2. Read MEMORY.md → 'Open To-Dos' for prior incidents on this cron\n"
            f"3. If MD source is 0 bytes, run `restore_md_sources.py` (if applicable) or manually backfill\n"
            f"4. If pipeline is broken, fix the prompt and disable the broken cron until the next rebuild\n\n"
            f"Auto-created by site-code-audit nightly scan (2026-08-26). "
            f"Owner: {owner}. Route via workboard card."
        )

        # Use the OpenClaw workboard_create CLI since this script is called from cron
        try:
            # Try the API directly if available
            cmd = [
                "openclaw", "workboard", "create",
                "--title", title,
                "--notes", body,
                "--board-id", board_id,
                "--priority", "high" if f.get("severity") == "high" else "urgent",
                "--agent-id", owner.replace("agent:main:", "main:").replace("-website-manager", "-website-manager"),
            ]
            env = os.environ.copy()
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env)
            if res.returncode == 0:
                cards.append(title)
            else:
                cards.append(f"FAILED: {res.stderr[:200]}")
        except Exception as e:
            cards.append(f"ERROR: {e}")
    return cards
