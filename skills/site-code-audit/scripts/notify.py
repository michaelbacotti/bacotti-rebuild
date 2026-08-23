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
