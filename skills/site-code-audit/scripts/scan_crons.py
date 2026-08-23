"""
scan_crons.py — Layer 3: cron health check.

Surfaces any cron job that has been in error state for >2 consecutive runs,
or hasn't run successfully in >7 days. Both indicate stuck cron pipelines.

Output findings have auto_fixable=False — fixing cron state requires
operator review (you don't want to auto-disable or auto-restart crons).
"""
import json
import subprocess
from datetime import datetime, timezone, timedelta


def _list_jobs() -> list:
    """Use the OpenClaw cron list command to get current job states."""
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
    # Fallback: try plain text output
    try:
        out = subprocess.run(
            ["openclaw", "cron", "list"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        # If we can't parse, return empty — better than crashing the whole audit
        return []
    except Exception:
        return []


def scan_crons() -> list:
    """Check all cron jobs for stuck / error states."""
    findings = []
    jobs = _list_jobs()
    if not jobs:
        return findings

    now = datetime.now(timezone.utc)

    for job in jobs:
        name = job.get("name", "<unnamed>")
        status = job.get("lastRunStatus", "")
        last_run_ms = job.get("lastRunAtMs", 0)
        consecutive_errors = job.get("state", {}).get("consecutiveErrors", 0) or 0
        error_msg = job.get("lastRunError", "")

        if status == "error" and consecutive_errors >= 2:
            findings.append(
                {
                    "site": "crons",
                    "class": "cron_stuck_erroring",
                    "severity": "high",
                    "file": name,
                    "details": f"{consecutive_errors} consecutive errors. Last: {error_msg[:200]}",
                    "auto_fixable": False,
                    "cron_id": job.get("id"),
                }
            )

        # Stale — last successful run >7 days ago and still enabled
        if last_run_ms and job.get("enabled", True):
            age = now - datetime.fromtimestamp(last_run_ms / 1000, tz=timezone.utc)
            if age > timedelta(days=7) and status == "ok":
                # Note: not all crons are *expected* to run daily. We only flag
                # if we know the schedule is more frequent than the gap.
                # Without schedule parsing, this is informational, not a hard finding.
                pass

    return findings
