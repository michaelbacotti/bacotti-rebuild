"""
lib/outcome_resolver.py
Workstream F.5 — Outcome resolution / forward-observation tracking.

Charter: research-only. No execution, no brokerage creds, no order placement.

For every record in the research ledger (any profile), this module:
  - fetches actuals at the specified horizons (forecast coverage)
  - records MFE / MAE
  - checks S/R / trigger / invalidation levels (when present in payload)
  - appends to the record's `actuals[]` (append-only; never modifies prior entries)

Designed to be called from a cron:
  daily   — refresh today's latest actuals
  on-demand — fill in a specific candidate_id

Outputs:
  data/calibration/<SYMBOL>.json  per-symbol calibration summary
  appends entries to ledger rows via research_ledger.append_actual()

Validation_status lifecycle (per profile §12 of proposal):
  preliminary   -> default; no forward observations
  calibrating   -> ≥ 30 obs accumulating, criteria not yet met
  validated     -> all criteria met
  rejected_by_evidence -> explicitly downgraded
"""

from __future__ import annotations

import json
import math
import statistics
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

CALIBRATION_ROOT = Path(__file__).resolve().parents[1] / "data" / "calibration"

TRADING_DAYS_PER_YEAR = 252
HORIZON_TRADING_DAYS = {
    "1w": 5, "1mo": 21, "2mo": 42, "3mo": 63, "6mo": 126, "1y": 252,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_local() -> datetime:
    return datetime.now().astimezone()


def _iso_local(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _cache_yf_history(symbol: str, period: str = "5y"):
    """Lazy import + cache."""
    try:
        import yfinance as yf  # type: ignore
    except ImportError:
        return None
    try:
        t = yf.Ticker(symbol)
        return t.history(period=period, auto_adjust=True)
    except Exception:
        return None


def _hist_close_at(history, target_date: datetime.date):
    """Return the close at-or-before target_date from a yfinance DataFrame."""
    if history is None or len(history) == 0:
        return None
    target = target_date
    best = None
    for idx, row in history.iterrows():
        d = idx.date() if hasattr(idx, "date") else idx
        if d <= target:
            return float(row["Close"])
    return None  # target is before all data we have


def _mfe_mae(history, as_of_date: datetime.date, horizon_days: int):
    """Compute max-favorable / max-adverse excursion over the horizon window."""
    if history is None or len(history) == 0:
        return None, None, None, None
    end = as_of_date + timedelta(days=int(horizon_days * 365 / 252))
    closes = []
    highs = []
    lows = []
    for idx, row in history.iterrows():
        d = idx.date() if hasattr(idx, "date") else idx
        if as_of_date <= d <= end.date():
            closes.append(float(row["Close"]))
            highs.append(float(row["High"]))
            lows.append(float(row["Low"]))
    if not closes:
        return None, None, None, None
    anchor = closes[0]
    mfe = max(c - anchor for c in closes)
    mae = min(c - anchor for c in closes)
    return anchor, mfe, mae, closes[-1]


# ---------------------------------------------------------------------------
# Coverage computation for a forecast record
# ---------------------------------------------------------------------------

def _coverage_for_forecast(record: dict, as_of_date: datetime.date, hist) -> list[dict]:
    """Compute coverage for each horizon in the forecast artifact.
    Returns a list of actual dicts, one per horizon.
    """
    payload = record.get("payload", {})
    horizons = payload.get("horizons", {})
    artifact_id = record.get("artifacts", {}).get("forecast_artifact")
    actuals: list[dict] = []

    for hname, hdata in horizons.items():
        horizon_days = HORIZON_TRADING_DAYS.get(hname)
        if horizon_days is None:
            continue
        target = as_of_date + timedelta(days=int(horizon_days * 365 / 252))
        anchor, mfe, mae, last = _mfe_mae(hist, as_of_date, horizon_days)
        if anchor is None:
            actuals.append({
                "horizon": hname,
                "resolved_at": _iso_local(_now_local()),
                "anchor_price": None,
                "actual_close": None,
                "in_band_68": None,
                "in_band_90": None,
                "mfe_pct": None,
                "mae_pct": None,
                "note": "history unavailable for horizon window",
            })
            continue

        band_68 = hdata.get("band_68")
        band_90 = hdata.get("band_90")
        in_68 = None
        in_90 = None
        if band_68 and len(band_68) == 2:
            in_68 = bool(band_68[0] <= last <= band_68[1])
        if band_90 and len(band_90) == 2:
            in_90 = bool(band_90[0] <= last <= band_90[1])

        actuals.append({
            "horizon": hname,
            "resolved_at": _iso_local(_now_local()),
            "anchor_price": round(anchor, 4),
            "actual_close": round(last, 4) if last is not None else None,
            "in_band_68": in_68,
            "in_band_90": in_90,
            "mfe_pct": round(mfe / anchor * 100, 3) if mfe is not None else None,
            "mae_pct": round(mae / anchor * 100, 3) if mae is not None else None,
            "artifact_id": artifact_id,
        })
    return actuals


def _coverage_for_sr_levels(record: dict, as_of_date: datetime.date, hist) -> dict:
    """For directionality records, check whether S/R / trigger / invalidation
    levels were reached within ±5 trading days."""
    payload = record.get("payload", {})
    chart = payload.get("chart", {})
    top = chart.get("top_pattern", {}) or {}
    levels = {
        "support": chart.get("support"),
        "resistance": chart.get("resistance"),
        "trigger": top.get("trigger_price"),
        "invalidation": top.get("invalidation"),
    }
    if hist is None or len(hist) == 0:
        return {"levels_checked": levels, "levels_reached": {}}

    end = as_of_date + timedelta(days=21)
    highs = []
    lows = []
    for idx, row in hist.iterrows():
        d = idx.date() if hasattr(idx, "date") else idx
        if as_of_date <= d <= end.date():
            highs.append(float(row["High"]))
            lows.append(float(row["Low"]))

    reached = {}
    for label, level in levels.items():
        if level is None or not highs:
            continue
        # 0.5% penetration tolerance (per chart_structure module convention)
        tol = level * 0.005
        if any(h >= level + tol for h in highs):
            reached[label + "_reached_high"] = True
        if any(l <= level - tol for l in lows):
            reached[label + "_reached_low"] = True
    return {"levels_checked": levels, "levels_reached": reached}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve_record(record: dict) -> list[dict]:
    """Resolve one record. Returns list of actual dicts to append."""
    sym = record.get("symbol")
    if not sym:
        return []

    as_of_ts = record.get("as_of_ts")
    try:
        as_of_dt = datetime.fromisoformat(as_of_ts)
    except (ValueError, TypeError):
        return []
    as_of_date = as_of_dt.date()

    # Skip records older than horizon+buffer
    age_days = (_now_local().date() - as_of_date).days
    max_horizon_days = int(252 * 365 / 252) + 30
    if age_days > max_horizon_days + 5:
        # Too old to still be informative; mark resolved
        return [{"when": _iso_local(_now_local()), "note": "out of forward window", "stale": True}]

    hist = _cache_yf_history(sym, period="5y")
    if hist is None:
        return []

    profile = record.get("profile")
    actuals: list[dict] = []
    if profile == "forecast":
        actuals.extend(_coverage_for_forecast(record, as_of_date, hist))
    elif profile == "directionality":
        sr_check = _coverage_for_sr_levels(record, as_of_date, hist)
        actuals.append({
            "when": _iso_local(_now_local()),
            "horizon": "21d",
            "sr_trigger_invalidation_check": sr_check,
        })
    elif profile == "macro_dashboard":
        # Macros don't get per-record resolved actuals — handled separately
        return []

    return actuals


def resolve_all_open() -> dict:
    """Walk the ledger newest-first; for every open record (no actuals
    covering the current horizon), fetch and append new actuals.

    Returns a summary dict {profile: count_resolved}."""
    from research_ledger import read_recent, append_actual

    counts: dict[str, int] = {}
    rows = read_recent(limit=500)
    for record in rows:
        if record.get("profile") == "macro_dashboard":
            continue
        if record.get("user_action", {}).get("label") in ("closed", "rejected", "outcome_unavailable"):
            continue
        # Idempotency: skip if the latest actual already carries today's resolved_at
        last_actual = record["actuals"][-1] if record.get("actuals") else {}
        last_resolved = last_actual.get("resolved_at") or last_actual.get("when")
        if last_resolved and last_resolved[:10] == _now_local().date().isoformat():
            continue

        actuals = resolve_record(record)
        if actuals:
            for a in actuals:
                append_actual(record["candidate_id"], a)
            counts[record["profile"]] = counts.get(record["profile"], 0) + 1
    return counts


def build_calibration(symbol: str) -> dict:
    """Compute per-symbol calibration summary across all resolved forecast actuals."""
    from research_ledger import read_recent

    rows = read_recent(profile="forecast", limit=500)
    rows = [r for r in rows if r.get("symbol") == symbol]
    by_horizon: dict[str, dict] = {}

    for record in rows:
        for a in record.get("actuals", []):
            h = a.get("horizon")
            if not h or a.get("in_band_68") is None:
                continue
            bucket = by_horizon.setdefault(h, {"n": 0, "in_68": 0, "in_90": 0,
                                                "mfe_pct_list": [], "mae_pct_list": []})
            bucket["n"] += 1
            if a.get("in_band_68"): bucket["in_68"] += 1
            if a.get("in_band_90"): bucket["in_90"] += 1
            if a.get("mfe_pct") is not None:
                bucket["mfe_pct_list"].append(a["mfe_pct"])
            if a.get("mae_pct") is not None:
                bucket["mae_pct_list"].append(a["mae_pct"])

    summary = {"symbol": symbol, "horizons": {}, "validation_status": "preliminary"}
    for h, b in by_horizon.items():
        n = b["n"]
        emp_68 = b["in_68"] / n if n else None
        emp_90 = b["in_90"] / n if n else None
        mae_pct = (sum(b["mae_pct_list"]) / len(b["mae_pct_list"])) if b["mae_pct_list"] else None
        mfe_pct = (sum(b["mfe_pct_list"]) / len(b["mfe_pct_list"])) if b["mfe_pct_list"] else None
        calibrated_68 = emp_68 is not None and abs(emp_68 - 0.68) <= 0.10 and n >= 30
        calibrated_90 = emp_90 is not None and abs(emp_90 - 0.90) <= 0.10 and n >= 30
        calibrated = calibrated_68 and calibrated_90
        summary["horizons"][h] = {
            "n": n,
            "empirical_coverage_68": round(emp_68, 3) if emp_68 is not None else None,
            "empirical_coverage_90": round(emp_90, 3) if emp_90 is not None else None,
            "avg_mfe_pct": round(mfe_pct, 3) if mfe_pct is not None else None,
            "avg_mae_pct": round(mae_pct, 3) if mae_pct is not None else None,
            "calibrated_68": calibrated_68,
            "calibrated_90": calibrated_90,
            "calibrated": calibrated,
        }

    n_total = sum(b["n"] for b in by_horizon.values())
    if n_total >= 30:
        all_calibrated = all(summary["horizons"][h]["calibrated"] for h in summary["horizons"])
        summary["validation_status"] = "validated" if all_calibrated else "calibrating"

    CALIBRATION_ROOT.mkdir(parents=True, exist_ok=True)
    out = CALIBRATION_ROOT / f"{symbol}.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli_resolve():
    import argparse
    ap = argparse.ArgumentParser(description="Resolve open ledger records.")
    ap.add_argument("--symbol", default=None, help="Build calibration for this symbol")
    args = ap.parse_args()
    if args.symbol:
        summary = build_calibration(args.symbol)
        print(json.dumps(summary, indent=2, default=str))
    else:
        counts = resolve_all_open()
        print(json.dumps({"resolved_counts": counts}, indent=2))


if __name__ == "__main__":
    _cli_resolve()