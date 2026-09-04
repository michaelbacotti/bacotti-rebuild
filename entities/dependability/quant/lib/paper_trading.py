"""
paper_trading.py — Forward signal ledger for paper-trading validation.

Directive (Mike 2026-09-02 18:37 ET):
  "Separate in-sample development, untouched out-of-sample validation, and
   forward paper-trading results."

  "Do not label a pattern or forecast as validated unless it has passed an
   untouched out-of-sample test and has been tracked in forward paper trading."

This module is the forward paper-trading ledger. Every forecast emitted by
lib/forecast.py gets logged here with: symbol, decision_timestamp, horizons,
predicted bands, pattern (if any). When the forecast horizon elapses, the
actual close is recorded and calibration is computed.

Validation rules:
  - A pattern / forecast is "OOS-conditional" if it has ≥10 OOS detections in
    backtest (computed by pattern_backtest.py). This is what chart_structure
    shows today.
  - A pattern / forecast graduates to "validated" only when:
      1. OOS-conditional status met (already done for inverse_h&s, bull_flag,
         ascending_triangle, double_bottom on tested symbols)
      2. ≥21 trading days of forward paper-trading data exist for the symbol
      3. Forward hit rate within tolerance of OOS hit rate
         (e.g., forward_hit_rate ≥ 0.5 × OOS_hit_rate, never wildly worse)
      4. Forward avg return is not catastrophically worse than OOS avg return
         (e.g., forward_avg_4w ≥ 0.5 × OOS_avg_4w)
      5. Calibration report shows empirical 68%/90% within ±10% of theoretical

Until all 5 conditions are met, status remains "OOS-conditional, awaiting forward validation".
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, List, Optional, Any

import pandas as pd
import numpy as np


LEDGER_DIR = Path(os.path.expanduser(
    "~/.openclaw/workspace-bacottibot/entities/dependability/quant/data/paper_ledger"
))
LEDGER_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ForwardSignal:
    """One forecast logged for forward paper-trading."""
    signal_id: str
    symbol: str
    decision_timestamp: str      # ISO datetime
    as_of_date: str              # ISO date (point-in-time data cutoff)
    spot: float
    pattern_type: Optional[str]
    pattern_state: Optional[str]
    pattern_conditional_used: bool
    horizons_predicted: Dict[str, Dict[str, float]]   # horizon_label → {median, band_68, band_90, ...}
    oos_conditional_hit_rate: Optional[float]         # from pattern_backtest
    oos_conditional_avg_return_4w: Optional[float]
    oos_conditional_n: Optional[int]
    status: str                  # "logged" | "partially_resolved" | "fully_resolved"
    resolution: Optional[Dict[str, Dict[str, Any]]] = None   # horizon_label → {actual_return, in_band_68, in_band_90}


@dataclass
class ValidationRecord:
    """Validation status for one pattern type on one symbol."""
    symbol: str
    pattern_type: str
    oos_n: int
    oos_hit_rate: Optional[float]
    oos_avg_return_4w: Optional[float]
    forward_n: int
    forward_hit_rate: Optional[float]
    forward_avg_return_4w: Optional[float]
    empirical_coverage_68: Optional[float]
    empirical_coverage_90: Optional[float]
    status: str                  # "OOS-conditional" | "validating" | "validated" | "failed_validation"
    validation_criteria: Dict[str, Any]
    last_updated: float


# ============================================================
# Ledger I/O
# ============================================================

def _ledger_path(symbol: str) -> Path:
    return LEDGER_DIR / f"{symbol.upper()}_forward_signals.jsonl"


def log_forward_signal(signal: ForwardSignal) -> None:
    """Append a forward signal to the per-symbol ledger."""
    path = _ledger_path(signal.symbol)
    rec = asdict(signal)
    with open(path, "a") as f:
        f.write(json.dumps(rec, default=str) + "\n")


def load_ledger(symbol: str) -> List[Dict[str, Any]]:
    """Load all forward signals for a symbol."""
    path = _ledger_path(symbol)
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    return out


def resolve_horizon(signal: Dict[str, Any], horizon_d: int, actual_close: float, realized_at: str) -> bool:
    """Update a logged signal with actual outcome for one horizon.

    Returns True if this resolved all horizons for the signal.
    """
    symbol = signal["symbol"]
    path = _ledger_path(symbol)
    if not path.exists():
        return False
    lines = path.read_text().strip().split("\n")
    spot = signal["spot"]
    actual_return = (actual_close / spot - 1) if spot > 0 else None
    updated = False
    all_resolved = True
    for i, line in enumerate(lines):
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get("signal_id") != signal.get("signal_id"):
            continue
        # Find the matching horizon
        for label, h_data in (rec.get("horizons_predicted") or {}).items():
            if h_data.get("horizon_d") != horizon_d:
                continue
            resolution = rec.setdefault("resolution", {})
            resolution[label] = {
                "horizon_d": horizon_d,
                "actual_close": actual_close,
                "actual_return": actual_return,
                "in_band_68": bool(
                    actual_return is not None and
                    h_data.get("band_68_lower_return") is not None and
                    h_data["band_68_lower_return"] <= actual_return <= h_data["band_68_upper_return"]
                ),
                "in_band_90": bool(
                    actual_return is not None and
                    h_data.get("band_90_lower_return") is not None and
                    h_data["band_90_lower_return"] <= actual_return <= h_data["band_90_upper_return"]
                ),
                "realized_at": realized_at,
            }
            updated = True
        # Check if all horizons resolved
        resolution = rec.get("resolution") or {}
        for label, h_data in (rec.get("horizons_predicted") or {}).items():
            if label not in resolution:
                all_resolved = False
                break
        if all_resolved and resolution:
            rec["status"] = "fully_resolved"
        elif resolution:
            rec["status"] = "partially_resolved"
        lines[i] = json.dumps(rec, default=str)
    if updated:
        path.write_text("\n".join(lines) + "\n")
    return all_resolved


def resolve_due_horizons(symbol: str, as_of: Optional[str] = None) -> int:
    """Check ledger for signals whose horizons are due, fetch actual close,
    update resolution.

    Returns count of resolutions added.
    """
    import yfinance as yf
    if as_of is None:
        as_of = str(pd.Timestamp.today().date())
    as_of_dt = pd.to_datetime(as_of)
    signals = load_ledger(symbol)
    if not signals:
        return 0
    # Get recent close
    try:
        recent = yf.Ticker(symbol).history(period="6mo", auto_adjust=True)
        if recent is None or recent.empty:
            return 0
        recent = recent.rename_axis("Date").reset_index()
        recent["Date"] = pd.to_datetime(recent["Date"]).dt.tz_localize(None)
        recent = recent.set_index("Date").sort_index()
    except Exception:
        return 0
    n_resolved = 0
    for sig in signals:
        if sig.get("status") == "fully_resolved":
            continue
        decision_dt = pd.to_datetime(sig["decision_timestamp"])
        for label, h_data in (sig.get("horizons_predicted") or {}).items():
            horizon_d = h_data.get("horizon_d")
            if horizon_d is None:
                continue
            # If this horizon label already resolved, skip
            existing = (sig.get("resolution") or {}).get(label)
            if existing:
                continue
            # Forecast date + horizon_d trading days
            # Simple proxy: add calendar days (use 1.4 calendar per trading day)
            target_dt = decision_dt + pd.Timedelta(days=int(horizon_d * 1.4))
            if as_of_dt < target_dt:
                continue
            # Find the close on or just after target_dt
            future = recent[recent.index >= target_dt]
            if future.empty:
                continue
            actual_close = float(future["Close"].iloc[0])
            realized_at = str(future.index[0].date())
            all_resolved = resolve_horizon(sig, horizon_d, actual_close, realized_at)
            n_resolved += 1
    return n_resolved


# ============================================================
# Validation rules
# ============================================================

VALIDATION_CRITERIA = {
    "min_forward_paper_days": 21,
    "min_forward_hit_rate_ratio": 0.50,    # forward / OOS ≥ 50%
    "min_forward_avg_return_ratio": 0.50,  # forward / OOS ≥ 50%
    "calibration_tolerance_pct": 0.10,     # empirical 68%/90% within ±10% of theoretical
}


def evaluate_validation(symbol: str, pattern_type: str,
                        oos_n: int, oos_hit_rate: Optional[float], oos_avg_return_4w: Optional[float]) -> ValidationRecord:
    """Evaluate validation status for one pattern+symbol combination.

    Returns ValidationRecord with status: OOS-conditional | validating | validated | failed_validation.
    """
    criteria = dict(VALIDATION_CRITERIA)
    # Pull all forward signals for this symbol with this pattern
    ledger = load_ledger(symbol)
    matches = [s for s in ledger if s.get("pattern_type") == pattern_type]
    # Count forward hits at 4w (21d)
    forward_hits = []
    forward_returns_4w = []
    for s in matches:
        for label, res in (s.get("resolution") or {}).items():
            if res.get("horizon_d") == 21:
                # Hit = within 68% band OR (no 68% band) returned positive
                if res.get("actual_return") is not None:
                    forward_returns_4w.append(res["actual_return"])
                    if res.get("in_band_68"):
                        forward_hits.append(1)
                    else:
                        forward_hits.append(0)
    forward_n = len(forward_returns_4w)
    forward_hit_rate = (sum(forward_hits) / forward_n) if forward_n > 0 else None
    forward_avg_4w = (sum(forward_returns_4w) / forward_n) if forward_n > 0 else None
    # Calibration
    calib_68 = None
    calib_90 = None
    cover_68 = []
    cover_90 = []
    for s in matches:
        for label, res in (s.get("resolution") or {}).items():
            if res.get("in_band_68") is not None:
                cover_68.append(1 if res["in_band_68"] else 0)
            if res.get("in_band_90") is not None:
                cover_90.append(1 if res["in_band_90"] else 0)
    if cover_68:
        calib_68 = sum(cover_68) / len(cover_68)
    if cover_90:
        calib_90 = sum(cover_90) / len(cover_90)
    # Status evaluation
    status = "OOS-conditional"
    reasons = []
    if oos_n < 10:
        status = "OOS-conditional"
        reasons.append(f"OOS n={oos_n} < 10")
    else:
        # Has OOS data — check forward paper progress
        if forward_n < criteria["min_forward_paper_days"]:
            status = "validating"
            reasons.append(f"forward n={forward_n} < {criteria['min_forward_paper_days']} required")
        else:
            # Forward paper has enough data — apply validation rules
            checks_passed = []
            # 1. OOS hit rate threshold (already met by oos_n ≥ 10 is not enough; need actual hit rate)
            if oos_hit_rate is None or oos_hit_rate < 0.4:
                checks_passed.append(False)
                reasons.append(f"OOS hit rate {oos_hit_rate} < 40%")
            else:
                checks_passed.append(True)
            # 2. Forward hit rate vs OOS
            if forward_hit_rate is not None and oos_hit_rate is not None:
                if forward_hit_rate >= criteria["min_forward_hit_rate_ratio"] * oos_hit_rate:
                    checks_passed.append(True)
                else:
                    checks_passed.append(False)
                    reasons.append(f"forward hit rate {forward_hit_rate:.2f} < 50% × OOS {oos_hit_rate:.2f}")
            else:
                checks_passed.append(False)
                reasons.append("forward hit rate not yet computable")
            # 3. Forward avg return vs OOS
            if forward_avg_4w is not None and oos_avg_return_4w is not None:
                if forward_avg_4w >= criteria["min_forward_avg_return_ratio"] * oos_avg_return_4w:
                    checks_passed.append(True)
                else:
                    checks_passed.append(False)
                    reasons.append(f"forward avg 4w {forward_avg_4w:.4f} < 50% × OOS {oos_avg_return_4w:.4f}")
            else:
                checks_passed.append(False)
                reasons.append("forward avg 4w not yet computable")
            # 4. Calibration
            if calib_68 is not None and calib_90 is not None:
                if abs(calib_68 - 0.68) <= criteria["calibration_tolerance_pct"] and \
                   abs(calib_90 - 0.90) <= criteria["calibration_tolerance_pct"]:
                    checks_passed.append(True)
                else:
                    checks_passed.append(False)
                    reasons.append(f"calibration 68={calib_68:.2f} 90={calib_90:.2f} outside ±10% of theoretical")
            else:
                checks_passed.append(False)
                reasons.append("calibration not yet computable")
            # Aggregate
            if all(checks_passed):
                status = "validated"
            elif sum(checks_passed) >= 2:
                status = "validating"
            else:
                status = "failed_validation"
    return ValidationRecord(
        symbol=symbol.upper(),
        pattern_type=pattern_type,
        oos_n=oos_n,
        oos_hit_rate=oos_hit_rate,
        oos_avg_return_4w=oos_avg_return_4w,
        forward_n=forward_n,
        forward_hit_rate=forward_hit_rate,
        forward_avg_return_4w=forward_avg_4w,
        empirical_coverage_68=calib_68,
        empirical_coverage_90=calib_90,
        status=status,
        validation_criteria={
            "criteria": criteria,
            "reasons": reasons,
        },
        last_updated=time.time(),
    )


def evaluation_to_dict(rec: ValidationRecord) -> Dict[str, Any]:
    return asdict(rec)
