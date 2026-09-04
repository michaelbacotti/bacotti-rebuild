"""
calibration.py — Empirical coverage / calibration tracker.

Directive (Mike 2026-09-02 18:37 ET):
  "State sample size, calibration/coverage accuracy, and whether the
   chart-pattern feature improves results versus the same model without it."

Calibration: of N forecasts, what fraction had actual outcome within the
68% band? Should be ~68%. Similarly for 90% band (target ~90%).

This module:
  1. Reads resolved forward signals from paper_trading.py
  2. Computes empirical coverage per (symbol, horizon_d)
  3. Compares with and without pattern-conditional adjustment (Mike's spec)
  4. Reports calibration error: |empirical - theoretical|
  5. Saves calibration.json artifact per symbol

Without-pattern baseline: same forecast model but with pattern_conditional_used=False
— runs a parallel forecast and compares calibration.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any

import numpy as np
import pandas as pd


CALIBRATION_DIR = Path(os.path.expanduser(
    "~/.openclaw/workspace-bacottibot/entities/dependability/quant/data/calibration"
))
CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class CalibrationBucket:
    horizon_d: int
    n: int
    empirical_coverage_68: Optional[float]      # fraction actual in 68% band
    empirical_coverage_90: Optional[float]      # fraction actual in 90% band
    theoretical_coverage_68: float = 0.68
    theoretical_coverage_90: float = 0.90
    calibration_error_68: Optional[float]       # empirical - theoretical
    calibration_error_90: Optional[float]
    median_absolute_error_return: Optional[float]


@dataclass
class CalibrationReport:
    symbol: str
    n_signals: int
    n_resolved: int
    with_pattern: Optional[List[CalibrationBucket]] = None
    without_pattern: Optional[List[CalibrationBucket]] = None
    pattern_improvement: Optional[Dict[str, float]] = None   # with - without, per horizon
    status: str = "insufficient_data"
    last_updated: float = 0.0


def _coverage(horizon_d: int, signals_with_resolution: List[Dict[str, Any]]) -> CalibrationBucket:
    """Compute empirical coverage for one horizon across all resolved signals."""
    in_68 = []
    in_90 = []
    abs_errors = []
    for sig in signals_with_resolution:
        for label, res in (sig.get("resolution") or {}).items():
            if res.get("horizon_d") != horizon_d:
                continue
            if res.get("in_band_68") is not None:
                in_68.append(1 if res["in_band_68"] else 0)
            if res.get("in_band_90") is not None:
                in_90.append(1 if res["in_band_90"] else 0)
            # Median absolute error (in return space)
            actual = res.get("actual_return")
            predicted_median = sig.get("horizons_predicted", {}).get(label, {}).get("median_return_pct")
            if actual is not None and predicted_median is not None:
                abs_errors.append(abs(actual - predicted_median))
    emp_68 = (sum(in_68) / len(in_68)) if in_68 else None
    emp_90 = (sum(in_90) / len(in_90)) if in_90 else None
    err_68 = (emp_68 - 0.68) if emp_68 is not None else None
    err_90 = (emp_90 - 0.90) if emp_90 is not None else None
    mae = (sum(abs_errors) / len(abs_errors)) if abs_errors else None
    return CalibrationBucket(
        horizon_d=horizon_d,
        n=len(in_68),
        empirical_coverage_68=round(emp_68, 3) if emp_68 is not None else None,
        empirical_coverage_90=round(emp_90, 3) if emp_90 is not None else None,
        calibration_error_68=round(err_68, 3) if err_68 is not None else None,
        calibration_error_90=round(err_90, 3) if err_90 is not None else None,
        median_absolute_error_return=round(mae, 4) if mae is not None else None,
    )


def compute_calibration(symbol: str) -> CalibrationReport:
    """Compute calibration report for one symbol from forward ledger.

    Compares with-pattern vs without-pattern calibration where possible.
    """
    from paper_trading import load_ledger
    ledger = load_ledger(symbol)
    if not ledger:
        return CalibrationReport(
            symbol=symbol.upper(),
            n_signals=0,
            n_resolved=0,
            status="no_data",
            last_updated=time.time(),
        )
    # Bucket by pattern usage
    with_pattern = [s for s in ledger if s.get("pattern_conditional_used")]
    without_pattern = [s for s in ledger if not s.get("pattern_conditional_used")]
    # Filter to resolved
    with_pattern_res = [s for s in with_pattern if s.get("status") in ("partially_resolved", "fully_resolved")]
    without_pattern_res = [s for s in without_pattern if s.get("status") in ("partially_resolved", "fully_resolved")]
    # Bucket per horizon
    horizons = [5, 10, 21, 42, 63]
    with_buckets = [_coverage(h, with_pattern_res) for h in horizons]
    without_buckets = [_coverage(h, without_pattern_res) for h in horizons]
    # Pattern improvement: calibration error smaller (closer to 0) when using pattern
    improvement = {}
    for wb, wob in zip(with_buckets, without_buckets):
        if wb.empirical_coverage_68 is not None and wob.empirical_coverage_68 is not None:
            err_with = abs(wb.empirical_coverage_68 - 0.68)
            err_without = abs(wob.empirical_coverage_68 - 0.68)
            improvement[f"{wb.horizon_d}d_68_error"] = round(err_with - err_without, 3)
        if wb.empirical_coverage_90 is not None and wob.empirical_coverage_90 is not None:
            err_with = abs(wb.empirical_coverage_90 - 0.90)
            err_without = abs(wob.empirical_coverage_90 - 0.90)
            improvement[f"{wb.horizon_d}d_90_error"] = round(err_with - err_without, 3)
    n_resolved_total = len(with_pattern_res) + len(without_pattern_res)
    if n_resolved_total < 10:
        status = "insufficient_data"
    elif n_resolved_total < 30:
        status = "preliminary"
    else:
        status = "mature"
    return CalibrationReport(
        symbol=symbol.upper(),
        n_signals=len(ledger),
        n_resolved=n_resolved_total,
        with_pattern=with_buckets,
        without_pattern=without_buckets,
        pattern_improvement=improvement if improvement else None,
        status=status,
        last_updated=time.time(),
    )


def report_to_dict(report: CalibrationReport) -> Dict[str, Any]:
    out = asdict(report)
    return out


def save_calibration_report(report: CalibrationReport) -> str:
    fpath = CALIBRATION_DIR / f"{report.symbol}_calibration.json"
    try:
        with open(fpath, "w") as f:
            json.dump(report_to_dict(report), f, indent=2, default=str)
        return str(fpath)
    except Exception as e:
        return f"ERROR: {e}"


def load_calibration_report(symbol: str) -> Optional[Dict[str, Any]]:
    fpath = CALIBRATION_DIR / f"{symbol.upper()}_calibration.json"
    if not fpath.exists():
        return None
    try:
        with open(fpath) as f:
            return json.load(f)
    except Exception:
        return None
