"""
pattern_backtest.py — Walk-forward conditional-return evaluation.

Mike 2026-09-02 18:26 ET: "Backtest out of sample: avoid tuning thresholds on
the same history used to evaluate them." This module walks historical daily
data, detects patterns at each point in time, then measures forward returns
at 1w/2w/4w post-detection. Results are stored as out-of-sample statistics
that chart_structure.py references for "historical conditional performance".

Out-of-sample discipline:
  - For pattern X, use threshold tuning on a development slice (in-sample).
  - Evaluation slice (out-of-sample) uses those fixed thresholds.
  - Per-symbol stats are kept separate so chart_structure can show
    symbol-specific conditional performance.
  - Cross-symbol aggregate stats are kept for threshold sanity checks.

This is a research layer. Do not auto-tune thresholds on every backtest —
that would fit to noise. Update thresholds explicitly when the user asks.
"""
from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

import numpy as np
import pandas as pd

from chart_structure import (
    _find_swing_highs,
    _find_swing_lows,
    _fetch_ohlcv,
    _volume_metrics,
    _atr,
    _detect_triangles,
    _detect_rectangle,
    _detect_double_top_bottom,
    _detect_flag_pennant,
    _detect_h_and_s,
)


CACHE_DIR = Path(os.path.expanduser("~/.openclaw/workspace-bacottibot/entities/dependability/quant/data/pattern_backtest"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _forward_returns(close_at: float, future_closes: np.ndarray) -> Dict[str, float]:
    """Compute forward returns at 1w (5d), 2w (10d), 4w (20d).
    future_closes: closes AFTER detection (not including detection bar)."""
    out = {}
    for label, n in [("1w", 5), ("2w", 10), ("4w", 20)]:
        if len(future_closes) >= n:
            ret = (future_closes[n - 1] - close_at) / close_at
            out[label] = float(ret)
        else:
            out[label] = None
    return out


def _hit_or_miss(pattern_type: str, direction_hint: str, forward_rets: Dict[str, Optional[float]]) -> Optional[bool]:
    """Decide if pattern's expected direction paid off at 4w.

    pattern_type encodes direction:
      - ascending_triangle, bull_flag, bull_pennant, double_bottom, inverse_h&s → bullish
      - descending_triangle, bear_flag, bear_pennant, double_top, head_and_shoulders → bearish
      - rectangle → use direction_hint ("up" or "down")
    Returns True if forward return aligns with expected direction (|return| ≥ 0.5%).
    """
    if forward_rets.get("4w") is None:
        return None
    expected_bullish = pattern_type in ("ascending_triangle", "bull_flag", "bull_pennant",
                                        "double_bottom", "inverse_h&s") or direction_hint == "up"
    expected_bearish = pattern_type in ("descending_triangle", "bear_flag", "bear_pennant",
                                        "double_top", "head_and_shoulders") or direction_hint == "down"
    r = forward_rets["4w"]
    if expected_bullish and r >= 0.005:
        return True
    if expected_bearish and r <= -0.005:
        return True
    # Neutral pattern or 4w return < 0.5% → not a clear hit
    return False


def backtest_patterns(symbol: str, lookback_d: int = 252 * 3,
                      step_d: int = 5, min_patterns: int = 10,
                      out_of_sample_frac: float = 0.5) -> Dict[str, Any]:
    """Walk forward through daily data and detect patterns every `step_d` days.

    For each detection, compute forward returns at 1w/2w/4w.
    Aggregate per pattern type.

    out_of_sample_frac: fraction of patterns held out for evaluation.
    Earlier patterns (in-sample) could be used for threshold tuning (manual).
    Later patterns (out-of-sample) are the stats reported to chart_structure.
    """
    daily = _fetch_ohlcv(symbol, lookback_d)
    if daily.empty or len(daily) < 120:
        return {"error": "insufficient data", "n": 0}
    n = len(daily)
    closes = daily["Close"].values.astype(float)
    highs = daily["High"].values.astype(float)
    lows = daily["Low"].values.astype(float)
    vol = daily["Volume"].values.astype(float)
    detections: List[Dict[str, Any]] = []
    # Walk forward
    for end_idx in range(120, n - 25, step_d):
        window = daily.iloc[:end_idx]
        if len(window) < 60:
            continue
        try:
            vol_metrics = _volume_metrics(window)
            atr_val = _atr(window)
            sh = _find_swing_highs(window["High"].values.astype(float))
            sl = _find_swing_lows(window["Low"].values.astype(float))
            patterns = []
            patterns += _detect_triangles(window, sh, sl, atr_val, vol_metrics)
            patterns += _detect_rectangle(window, sh, sl, atr_val, vol_metrics)
            patterns += _detect_double_top_bottom(window, sh, sl, atr_val, vol_metrics)
            patterns += _detect_flag_pennant(window, atr_val, vol_metrics)
            patterns += _detect_h_and_s(window, sh, sl, atr_val, vol_metrics)
            for p in patterns:
                # Compute forward returns
                spot = float(window["Close"].iloc[-1])
                future_closes = closes[end_idx:end_idx + 25]
                fwd = _forward_returns(spot, future_closes)
                direction_hint = "up" if p.type in ("ascending_triangle", "bull_flag", "bull_pennant",
                                                    "double_bottom", "inverse_h&s") else \
                                 "down" if p.type in ("descending_triangle", "bear_flag", "bear_pennant",
                                                       "double_top", "head_and_shoulders") else \
                                 ("up" if p.state == "confirmed" and p.trigger_price > spot else "down")
                hit = _hit_or_miss(p.type, direction_hint, fwd)
                detections.append({
                    "type": p.type,
                    "detection_date": str(window.index[-1].date()),
                    "spot": spot,
                    "fwd_1w": fwd.get("1w"),
                    "fwd_2w": fwd.get("2w"),
                    "fwd_4w": fwd.get("4w"),
                    "hit_4w": hit,
                    "state": p.state,
                    "trigger": p.trigger_price,
                })
        except Exception:
            continue
    if not detections:
        return {"error": "no patterns detected", "n": 0}
    # Aggregate per type
    by_type: Dict[str, List[Dict[str, Any]]] = {}
    for d in detections:
        by_type.setdefault(d["type"], []).append(d)
    type_stats: Dict[str, Dict[str, Any]] = {}
    for ptype, lst in by_type.items():
        if len(lst) < min_patterns:
            continue
        # Out-of-sample split: take the LAST out_of_sample_frac of detections
        split = int(len(lst) * (1 - out_of_sample_frac))
        oos = lst[split:]
        if not oos:
            continue
        hits_4w = [d["hit_4w"] for d in oos if d["hit_4w"] is not None]
        rets_4w = [d["fwd_4w"] for d in oos if d["fwd_4w"] is not None]
        rets_2w = [d["fwd_2w"] for d in oos if d["fwd_2w"] is not None]
        rets_1w = [d["fwd_1w"] for d in oos if d["fwd_1w"] is not None]
        type_stats[ptype] = {
            "n": len(oos),
            "n_total": len(lst),
            "hit_rate": round(sum(hits_4w) / len(hits_4w), 3) if hits_4w else None,
            "avg_return_1w": round(float(np.mean(rets_1w)), 4) if rets_1w else None,
            "avg_return_2w": round(float(np.mean(rets_2w)), 4) if rets_2w else None,
            "avg_return_4w": round(float(np.mean(rets_4w)), 4) if rets_4w else None,
            "median_return_4w": round(float(np.median(rets_4w)), 4) if rets_4w else None,
            "win_rate_4w_1pct": round(sum(1 for r in rets_4w if abs(r) >= 0.01) / len(rets_4w), 3) if rets_4w else None,
        }
    result = {
        "symbol": symbol,
        "as_of": str(daily.index[-1].date()),
        "n_detections": len(detections),
        "by_type": type_stats,
        "lookback_d": lookback_d,
        "step_d": step_d,
        "out_of_sample_frac": out_of_sample_frac,
        "ran_at": time.time(),
    }
    # Cache
    cache_file = CACHE_DIR / f"{symbol.upper()}_backtest.json"
    try:
        with open(cache_file, "w") as f:
            json.dump(result, f, indent=2, default=str)
    except Exception:
        pass
    return result


def get_conditional_stats(symbol: str, pattern_type: str) -> Optional[Dict[str, Any]]:
    """Read cached backtest stats for symbol+pattern. Returns None if no cache."""
    cache_file = CACHE_DIR / f"{symbol.upper()}_backtest.json"
    if not cache_file.exists():
        return None
    try:
        with open(cache_file) as f:
            data = json.load(f)
        return data.get("by_type", {}).get(pattern_type)
    except Exception:
        return None


def backtest_all_symbols(symbols: List[str]) -> Dict[str, Any]:
    """Run backtest for a list of symbols. Used for cross-symbol aggregate stats."""
    out: Dict[str, Any] = {}
    for sym in symbols:
        result = backtest_patterns(sym)
        out[sym] = result
    return out
