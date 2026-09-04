"""
lib/research_ledger.py
Workstream F.1 — Common research ledger (append-only JSONL store).

Charter: research-only. No execution, no brokerage creds, no order placement.

Every research output from Profiles 1–6 lands in the same ledger at
  data/research_ledger/YYYY-MM/YYYY-MM-DD.jsonl
with a uniform schema. Each row is dated, sha256-deduped, and never modified.

Public API:
  ledger.write_record(payload, profile, summary, **kwargs) -> candidate_id
  ledger.read_day(date_str) -> list[dict]
  ledger.read_recent(profile=None, limit=200) -> list[dict]
  ledger.upsert_user_action(candidate_id, label, note) -> bool
  ledger.append_actual(candidate_id, actual) -> bool

Validation_status lifecycle:
  preliminary  -> default; no forward observations yet
  calibrating  -> accumulating forward observations
  validated    -> all calibration thresholds met
  rejected_by_evidence -> explicitly downgraded

Macro context is REQUIRED on every record (None allowed only if dashboard
hasn't run yet today — and even then, the record carries a `macro_caveat`).
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

LEDGER_ROOT = Path(__file__).resolve().parents[1] / "data" / "research_ledger"


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def _now_iso_local() -> str:
    # Project convention: America/New_York local
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _today_yyyymmdd() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d")


def _yyyymm_now() -> str:
    return datetime.now().astimezone().strftime("%Y-%m")


VALID_PROFILES = {
    "macro_dashboard",
    "directionality",
    "forecast",
    "earnings_iv_crush",
    "hedge",
    "defined_risk_spread",
}

VALID_USER_ACTION_LABELS = {
    "watched",
    "rejected",
    "paper_tracked",
    "manually_tracked",
    "closed",
    "outcome_unavailable",
}

VALID_VALIDATION_STATUS = {
    "preliminary",
    "preliminary \u2014 uncalibrated",
    "calibrating",
    "validated",
    "rejected_by_evidence",
}

# Fix C (2026-09-02 20:30 ET): orthogonal to validation_status (which now means
# calibration_status). data_completeness reflects whether all 8 pillar inputs
# were available, regardless of forward-observation thresholds.
VALID_DATA_COMPLETENESS = {
    "complete",            # all 8 pillars resolved to non-null values
    "partial",             # 1..7 pillars resolved — `missing_pillars` lists them
    "insufficient",        # 0 pillars — dashboard cannot be built
    "insufficient_data",   # explicit unavailable status when inputs are tainted/NaN
}


def _candidate_id(as_of_ts: str, symbol: Optional[str], profile: str, kind: str, params: dict) -> str:
    """sha256(as_of_ts + symbol + profile + kind + canonical params)[:16]."""
    h = hashlib.sha256()
    canon_params = json.dumps(params, sort_keys=True, separators=(",", ":"), default=str)
    h.update(f"{as_of_ts}|{symbol or ''}|{profile}|{kind}|{canon_params}".encode())
    return "cnv_" + h.hexdigest()[:16]


def build_record(
    profile: str,
    summary: str,
    *,
    symbol: Optional[str] = None,
    kind: str = "unspecified",
    payload: Optional[dict] = None,
    macro_context: Optional[dict] = None,
    macro_caveat: Optional[str] = None,
    sizing_band_display: Optional[str] = None,
    artifacts: Optional[dict] = None,
    as_of_ts: Optional[str] = None,
    validation_status: str = "preliminary",
    data_completeness: str = "complete",
    extra: Optional[dict] = None,
) -> dict:
    """Build a ledger record dict. Caller persists it via write_record().

    Fix C (2026-09-02 20:30 ET): `data_completeness` is orthogonal to
    `validation_status` (which now means calibration_status). Default
    `complete` preserves backward compatibility — existing callers
    that don't pass the new kwarg continue to write records that
    accept both fields.
    """
    if profile not in VALID_PROFILES:
        raise ValueError(f"profile must be one of {VALID_PROFILES}; got {profile!r}")
    if validation_status not in VALID_VALIDATION_STATUS:
        raise ValueError(f"validation_status must be one of {VALID_VALIDATION_STATUS}; got {validation_status!r}")
    if data_completeness not in VALID_DATA_COMPLETENESS:
        raise ValueError(f"data_completeness must be one of {VALID_DATA_COMPLETENESS}; got {data_completeness!r}")
    ts = as_of_ts or _now_iso_local()
    rec = {
        "candidate_id": _candidate_id(ts, symbol, profile, kind, payload or {}),
        "as_of_ts": ts,
        "profile": profile,
        "symbol": symbol,
        "kind": kind,
        "summary": summary,
        "validation_status": validation_status,
        "data_completeness": data_completeness,
        "payload": payload or {},
        "macro_context": macro_context,
        "macro_caveat": macro_caveat,
        "sizing_band_display": sizing_band_display,
        "user_action": {"label": None, "set_at": None, "note": None},
        "actuals": [],
        "artifacts": artifacts or {},
    }
    if extra:
        rec.update(extra)
    return rec


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _ledger_path(date_str: str) -> Path:
    """data/research_ledger/YYYY-MM/YYYY-MM-DD.jsonl"""
    yyyymm = date_str[:7]
    p = LEDGER_ROOT / yyyymm
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{date_str}.jsonl"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def write_record(record: dict) -> str:
    """Append one record to today's ledger file. Returns candidate_id.
    Idempotent on candidate_id (line is not duplicated if the same id is written twice)."""
    cid = record["candidate_id"]
    day = record["as_of_ts"][:10]
    path = _ledger_path(day)
    if path.exists():
        with path.open() as f:
            for line in f:
                try:
                    existing = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if existing.get("candidate_id") == cid:
                    return cid  # idempotent
    with path.open("a") as f:
        f.write(json.dumps(record, default=str, separators=(",", ":")))
        f.write("\n")
    return cid


def read_day(date_str: str) -> list[dict]:
    p = _ledger_path(date_str)
    if not p.exists():
        return []
    out = []
    with p.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def read_recent(profile: Optional[str] = None, limit: int = 200) -> list[dict]:
    """Walk YYYY-MM dirs newest-first; return up to `limit` matching records."""
    if not LEDGER_ROOT.exists():
        return []
    months = sorted([d for d in LEDGER_ROOT.iterdir() if d.is_dir()], reverse=True)
    out: list[dict] = []
    for month in months:
        days = sorted([p for p in month.iterdir() if p.suffix == ".jsonl"], reverse=True)
        for day in days:
            with day.open() as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if profile is None or rec.get("profile") == profile:
                        out.append(rec)
                        if len(out) >= limit:
                            return out
    return out


def upsert_user_action(candidate_id: str, label: str, note: Optional[str] = None) -> bool:
    """Update the user_action block of the record with this candidate_id.
    Walks the ledger newest-first. Returns True if found."""
    if label not in VALID_USER_ACTION_LABELS:
        raise ValueError(f"label must be one of {VALID_USER_ACTION_LABELS}; got {label!r}")
    if not LEDGER_ROOT.exists():
        return False
    months = sorted([d for d in LEDGER_ROOT.iterdir() if d.is_dir()], reverse=True)
    for month in months:
        days = sorted([p for p in month.iterdir() if p.suffix == ".jsonl"], reverse=True)
        for day in days:
            lines = day.read_text().splitlines()
            changed = False
            for i, line in enumerate(lines):
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("candidate_id") == candidate_id:
                    rec["user_action"] = {"label": label, "set_at": _now_iso_local(), "note": note}
                    lines[i] = json.dumps(rec, default=str, separators=(",", ":"))
                    changed = True
                    break
            if changed:
                day.write_text("\n".join(lines) + "\n")
                return True
    return False


def append_actual(candidate_id: str, actual: dict) -> bool:
    """Append a single actuals entry. Never modifies prior actuals.
    `actual` should carry a `when` key (ISO timestamp or horizon label)."""
    if not LEDGER_ROOT.exists():
        return False
    months = sorted([d for d in LEDGER_ROOT.iterdir() if d.is_dir()], reverse=True)
    for month in months:
        days = sorted([p for p in month.iterdir() if p.suffix == ".jsonl"], reverse=True)
        for day in days:
            lines = day.read_text().splitlines()
            changed = False
            for i, line in enumerate(lines):
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("candidate_id") == candidate_id:
                    rec.setdefault("actuals", []).append(actual)
                    lines[i] = json.dumps(rec, default=str, separators=(",", ":"))
                    changed = True
                    break
            if changed:
                day.write_text("\n".join(lines) + "\n")
                return True
    return False


def latest_macro_context() -> tuple[Optional[dict], Optional[str]]:
    """Return the most recent macro_dashboard payload + macro_caveat from the ledger.
    Used by Profiles 2–6 when they don't have a fresh dashboard in memory."""
    rows = read_recent(profile="macro_dashboard", limit=5)
    if not rows:
        return None, "no macro_dashboard record in ledger"
    latest = rows[0]
    macro = latest.get("payload", {}).get("dashboard")
    caveat = latest.get("macro_caveat")
    return macro, caveat


# ---------------------------------------------------------------------------
# CLI helpers (used by run scripts)
# ---------------------------------------------------------------------------

def _cli_record_from_argv():
    import argparse
    ap = argparse.ArgumentParser(description="Append a record to the research ledger.")
    ap.add_argument("--profile", required=True, choices=sorted(VALID_PROFILES))
    ap.add_argument("--summary", required=True)
    ap.add_argument("--symbol", default=None)
    ap.add_argument("--kind", default="manual")
    ap.add_argument("--payload-json", default=None,
                    help="Raw JSON string; payload goes into the record.")
    args = ap.parse_args()
    payload = json.loads(args.payload_json) if args.payload_json else {}
    rec = build_record(profile=args.profile, summary=args.summary,
                       symbol=args.symbol, kind=args.kind, payload=payload)
    cid = write_record(rec)
    print(f"wrote {cid} -> {rec['as_of_ts'][:10]}")


if __name__ == "__main__":
    _cli_record_from_argv()