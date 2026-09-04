"""
chart_structure.py — Systematic, algorithmic technical-pattern analysis.

Mike 2026-09-02 18:26 ET directive: "learn systematic technical-pattern analysis,
not subjective chart reading." Every pattern has explicit algorithmic criteria;
state labels are developing/confirmed/failed/invalidated; multi-timeframe (weekly
structure → daily setup → intraday execution); chart structure is ONE input in
the final rank, not a standalone stock-pick engine.

Hard rules (from Mike 2026-09-02 18:26 ET):
  1. Support/resistance from swing H/L, volume profile, anchored VWAP, MA clusters,
     gaps, options-derived levels.
  2. Trend structure from HH/HL, MA alignment, range breakout, regression slope.
  3. Continuation setups: flags, pennants, rectangles, ascending/descending/symmetrical
     triangles — each with explicit geometric + volatility + duration thresholds.
  4. Reversal setups: double tops/bottoms, head-and-shoulders, failed breakouts,
     trendline breaks — same explicit criteria.
  5. Candlestick = confirmation only, never the sole reason to pick.
  6. Volume confirmation: relative volume, A/D proxies, contraction during
     consolidation, expansion on breakout.
  7. A pattern is UNCONFIRMED until defined breakout/breakdown with volume +
     trend confirmation.
  8. Multi-timeframe: weekly primary structure, daily setup, intraday execution only.
  9. Pattern state machine: developing → confirmed/failed/invalidated.
 10. Chart structure is one input in final rank. Do not issue a pick solely because
     of a chart pattern.

Out of scope (handled elsewhere):
  - Regime (HMM): lib/regime_hmm.py
  - Vol surface (SABR-lite): lib/sabr_lite.py
  - Expected move reconciliation: lib/expected_move.py
  - Flow composite: lib/institutional_flow.py
  - Named traders / sentiment: lib/social_sentiment.py
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import pandas as pd


# ============================================================
# Constants (Mike's explicit thresholds, 2026-09-02 18:26 ET)
# ============================================================

# Timeframes
WEEKLY_STRUCTURE_LOOKBACK_D = 252 * 2   # ~2 years of weekly for primary structure
DAILY_SETUP_LOOKBACK_D = 252            # 1 year daily for setup
INTRADAY_EXEC_LOOKBACK_D = 60           # 60d intraday for execution only

# Swing detection
SWING_LOOKBACK = 5                       # bars each side for pivot confirmation

# Volume profile
VP_BINS = 50
VP_LOOKBACK_D = 60
POC_PROMINENCE_RATIO = 1.5               # POC must hold ≥1.5x average bin volume to count as HVN

# Pattern criteria (all explicit)
TRIANGLE_MIN_TOUCHES = 3                 # ≥3 swing points on each trendline
TRIANGLE_MIN_DURATION_D = 14             # ≥14 calendar days of pattern
TRIANGLE_MAX_RANGE_PCT = 0.30            # range < 30% to qualify as consolidation
RECTANGLE_MIN_TOUCHES = 2                # ≥2 touches each side
RECTANGLE_MIN_DURATION_D = 10
RECTANGLE_RANGE_STD_PCT = 0.04           # close-to-close std < 4% inside range
FLAG_MIN_IMPULSE_PCT = 0.05              # ≥5% impulse move before flag
FLAG_MAX_DURATION_D = 20                 # flags are short
FLAG_RV_DECLINE = 0.6                    # RV inside flag ≤ 60% of pre-impulse RV
DOUBLE_TOLERANCE_PCT = 0.03              # two peaks/troughs within 3%
DOUBLE_MIN_SEPARATION_BARS = 10
HEAD_SHOULDER_TOLERANCE_PCT = 0.05       # right shoulder within 5% of left
H_AND_S_MIN_DURATION_D = 30
BREAKOUT_THRESHOLD_PCT = 0.005           # close ≥0.5% beyond trigger
BREAKOUT_VOLUME_MULT = 1.2               # RVOL ≥ 1.2 to confirm
VOLATILITY_EXPANSION_RATIO = 1.5         # OR ATR5/ATR20 ≥ 1.5

# Trend regression
REGRESSION_WINDOW_D = 60

# Stop loss defaults
STOP_ATR_MULT = 1.5                      # stop = trigger - 1.5 * ATR(14)

# Score weights (sum to 1.0)
WEIGHTS = {
    "trend": 0.25,
    "sr_confluence": 0.20,
    "volume": 0.20,
    "volatility_state": 0.15,
    "breakout_quality": 0.20,
}


# ============================================================
# Data containers
# ============================================================

@dataclass
class SupportLevel:
    price: float
    level_type: str                # swing_low | vwap_anchored | ma_50 | ma_200 | volume_profile_hvn | gap_fill
    strength: float                # 0-1
    touches: int
    last_touched_days_ago: int
    distance_pct: float            # |price - spot| / spot


@dataclass
class ResistanceLevel:
    price: float
    level_type: str
    strength: float
    touches: int
    last_touched_days_ago: int
    distance_pct: float


@dataclass
class Pattern:
    type: str                      # ascending_triangle | descending_triangle | symmetrical_triangle | rectangle | bull_flag | bear_flag | bull_pennant | bear_pennant | double_top | double_bottom | head_and_shoulders | inverse_h&s | trendline_break_up | trendline_break_down | range_breakout_up | range_breakout_down | failed_breakout
    state: str                     # developing | confirmed | failed | invalidated
    trigger_price: float
    stop_price: float
    target_price: Optional[float]
    expected_range_pct: float      # width of pattern (range / mid)
    volume_confirmation: bool
    volatility_state: str          # contracting | expanding | stable
    criteria: Dict[str, Any]       # explicit criteria met
    duration_days: int
    notes: str = ""
    # Filled in by pattern_backtest.py if backtest data available
    historical_conditional_hit_rate: Optional[float] = None
    historical_conditional_avg_return_4w: Optional[float] = None
    historical_conditional_n: Optional[int] = None
    # Mike 2026-09-02 18:37 ET directive: "Do not label a pattern or forecast as
    # validated unless it has passed an untouched out-of-sample test and has been
    # tracked in forward paper trading." Defaults to "OOS-conditional, awaiting
    # forward paper validation" until paper_trading.evaluate_validation promotes
    # status to "validating" or "validated".
    validation_status: str = "OOS-conditional, awaiting forward paper"
    forward_paper_n: Optional[int] = None
    forward_paper_hit_rate: Optional[float] = None


@dataclass
class Trend:
    direction: str                 # up | down | sideways
    ma_alignment: str              # bullish_20_50_200 | bearish_20_50_200 | bullish_partial | bearish_partial | mixed
    hh_hl_count_60d: int           # number of higher-highs + higher-lows in last 60d
    regression_slope_pct_per_day: float
    regression_r2: float           # R² of close vs time over 60d
    above_200dma: bool
    above_50dma: bool
    above_20dma: bool


@dataclass
class VolumeProfile:
    rvol_5d: float                 # today vs 5d avg
    rvol_20d: float                # today vs 20d avg
    accumulation_distribution_slope_20d: float   # positive = accumulation
    expansion_today: bool          # today's volume > 1.5x 20d avg
    contraction_5d: bool           # last 5d avg < 0.7x 20d avg


@dataclass
class ChartStructure:
    symbol: str
    spot: float
    as_of: str                     # ISO date
    primary_timeframe: str = "daily"
    structure_timeframe: str = "weekly"
    trend: Optional[Trend] = None
    supports: List[SupportLevel] = field(default_factory=list)
    resistances: List[ResistanceLevel] = field(default_factory=list)
    patterns: List[Pattern] = field(default_factory=list)
    volume: Optional[VolumeProfile] = None
    score: Dict[str, float] = field(default_factory=dict)
    weights: Dict[str, float] = field(default_factory=lambda: dict(WEIGHTS))
    note: str = ""
    error: Optional[str] = None


# ============================================================
# Data fetch
# ============================================================

def _fetch_ohlcv(symbol: str, period_d: int = DAILY_SETUP_LOOKBACK_D) -> pd.DataFrame:
    """Fetch OHLCV via yfinance. Returns DataFrame indexed by date."""
    import yfinance as yf
    # Period needs to map to a yfinance period string OR use start/end
    if period_d <= 60:
        period = "3mo"
    elif period_d <= 252:
        period = "1y"
    elif period_d <= 252 * 2:
        period = "2y"
    else:
        period = "5y"
    df = yf.Ticker(symbol).history(period=period, auto_adjust=False, actions=False)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.rename_axis("Date").reset_index()
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    df = df.set_index("Date").sort_index()
    # Keep only OHLCV
    keep = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    return df[keep]


def _weekly_ohlcv(daily: pd.DataFrame) -> pd.DataFrame:
    """Resample daily OHLCV to weekly."""
    if daily.empty:
        return daily
    return daily.resample("W").agg({
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum",
    }).dropna()


# ============================================================
# Swing point detection
# ============================================================

def _find_swing_highs(highs: np.ndarray, lookback: int = SWING_LOOKBACK) -> List[int]:
    """Pivot highs: bar whose high is the max of [i-lookback .. i+lookback]."""
    pivots = []
    for i in range(lookback, len(highs) - lookback):
        window = highs[i - lookback:i + lookback + 1]
        if highs[i] >= window.max():
            pivots.append(int(i))
    return pivots


def _find_swing_lows(lows: np.ndarray, lookback: int = SWING_LOOKBACK) -> List[int]:
    pivots = []
    for i in range(lookback, len(lows) - lookback):
        window = lows[i - lookback:i + lookback + 1]
        if lows[i] <= window.min():
            pivots.append(int(i))
    return pivots


# ============================================================
# Trend
# ============================================================

def _compute_trend(daily: pd.DataFrame, weekly: pd.DataFrame) -> Trend:
    close = daily["Close"].values.astype(float)
    if len(close) < 200:
        ma_50 = daily["Close"].rolling(50).mean().iloc[-1] if len(daily) >= 50 else float("nan")
        ma_200 = float("nan")
        ma_20 = daily["Close"].rolling(20).mean().iloc[-1] if len(daily) >= 20 else float("nan")
    else:
        ma_20 = daily["Close"].rolling(20).mean().iloc[-1]
        ma_50 = daily["Close"].rolling(50).mean().iloc[-1]
        ma_200 = daily["Close"].rolling(200).mean().iloc[-1]
    spot = float(close[-1])

    above_20 = spot > ma_20 if not math.isnan(ma_20) else False
    above_50 = spot > ma_50 if not math.isnan(ma_50) else False
    above_200 = spot > ma_200 if not math.isnan(ma_200) else False

    # MA alignment
    if not math.isnan(ma_200):
        if spot > ma_20 > ma_50 > ma_200:
            ma_align = "bullish_20_50_200"
        elif spot < ma_20 < ma_50 < ma_200:
            ma_align = "bearish_20_50_200"
        elif ma_20 > ma_50 > ma_200:
            ma_align = "bullish_partial"
        elif ma_20 < ma_50 < ma_200:
            ma_align = "bearish_partial"
        else:
            ma_align = "mixed"
    else:
        if ma_20 > ma_50:
            ma_align = "bullish_partial"
        elif ma_20 < ma_50:
            ma_align = "bearish_partial"
        else:
            ma_align = "mixed"

    # HH/HL count over last 60 days (using weekly pivots for stability)
    highs_arr = daily["High"].values.astype(float)
    lows_arr = daily["Low"].values.astype(float)
    sh = _find_swing_highs(highs_arr, SWING_LOOKBACK)
    sl = _find_swing_lows(lows_arr, SWING_LOOKBACK)
    cutoff = len(highs_arr) - 60
    recent_sh = [i for i in sh if i >= cutoff]
    recent_sl = [i for i in sl if i >= cutoff]
    # Count HH + HL
    hh = 0
    if len(recent_sh) >= 2:
        for i in range(1, len(recent_sh)):
            if highs_arr[recent_sh[i]] > highs_arr[recent_sh[i - 1]]:
                hh += 1
    hl = 0
    if len(recent_sl) >= 2:
        for i in range(1, len(recent_sl)):
            if lows_arr[recent_sl[i]] > lows_arr[recent_sl[i - 1]]:
                hl += 1
    hh_hl_count = hh + hl

    # Regression slope (% per day)
    if len(close) >= REGRESSION_WINDOW_D:
        y = close[-REGRESSION_WINDOW_D:]
        x = np.arange(len(y), dtype=float)
        # Linear regression
        xm, ym = x.mean(), y.mean()
        slope = ((x - xm) * (y - ym)).sum() / max(((x - xm) ** 2).sum(), 1e-9)
        intercept = ym - slope * xm
        yhat = slope * x + intercept
        ss_res = ((y - yhat) ** 2).sum()
        ss_tot = ((y - ym) ** 2).sum()
        r2 = 1 - ss_res / max(ss_tot, 1e-9)
        slope_pct_per_day = (slope / ym) * 100
    else:
        slope_pct_per_day = 0.0
        r2 = 0.0

    # Direction: combine slope + MA alignment + HH/HL
    if ma_align == "bullish_20_50_200" or (slope_pct_per_day > 0.05 and hh_hl_count >= 2):
        direction = "up"
    elif ma_align == "bearish_20_50_200" or (slope_pct_per_day < -0.05 and hh_hl_count <= 1):
        direction = "down"
    else:
        direction = "sideways"

    return Trend(
        direction=direction,
        ma_alignment=ma_align,
        hh_hl_count_60d=hh_hl_count,
        regression_slope_pct_per_day=round(slope_pct_per_day, 4),
        regression_r2=round(r2, 3),
        above_200dma=bool(above_200),
        above_50dma=bool(above_50),
        above_20dma=bool(above_20),
    )


# ============================================================
# Volume profile (price-by-volume)
# ============================================================

def _volume_profile(daily: pd.DataFrame, n_bins: int = VP_BINS, lookback_d: int = VP_LOOKBACK_D) -> Tuple[Optional[float], List[Tuple[float, float]]]:
    """Return (POC price, list of (price_level, total_volume)) sorted by price."""
    if len(daily) < lookback_d:
        return None, []
    window = daily.iloc[-lookback_d:]
    # Fix B-1 (2026-09-02 20:30 ET): belt-and-braces NaN guard. The top-level
    # dropna() in analyze_chart_structure already filters, but keep this so the
    # helper is safe when called from elsewhere (e.g. tests, future callers).
    window = window.dropna(subset=["Open", "High", "Low", "Close", "Volume"])
    if window.empty:
        return None, []
    lo, hi = float(window["Low"].min()), float(window["High"].max())
    if hi <= lo or lo != lo or hi != hi:  # NaN-guard on the bounds
        return None, []
    bins = np.linspace(lo, hi, n_bins + 1)
    vol_per_bin = np.zeros(n_bins)
    for _, row in window.iterrows():
        # Distribute this bar's volume across bins it touched (using typical price)
        tp = (row["High"] + row["Low"] + row["Close"]) / 3.0
        if tp != tp:  # NaN typical-price guard (skips the bar rather than raises)
            continue
        idx = int(np.clip((tp - lo) / (hi - lo) * n_bins, 0, n_bins - 1))
        vol_per_bin[idx] += float(row["Volume"])
    # POC = bin with max volume
    poc_idx = int(vol_per_bin.argmax())
    poc_price = (bins[poc_idx] + bins[poc_idx + 1]) / 2.0
    levels = [((bins[i] + bins[i + 1]) / 2.0, float(vol_per_bin[i])) for i in range(n_bins)]
    return float(poc_price), levels


def _hvn_levels(vp_levels: List[Tuple[float, float]], min_prominence: float = POC_PROMINENCE_RATIO) -> List[float]:
    """Return prices that are High-Volume Nodes (peaks in volume profile)."""
    if not vp_levels:
        return []
    vols = np.array([v for _, v in vp_levels])
    threshold = vols.mean() * min_prominence
    hvn = []
    for i in range(1, len(vp_levels) - 1):
        p, v = vp_levels[i]
        if v >= threshold and v >= vp_levels[i - 1][1] and v >= vp_levels[i + 1][1]:
            hvn.append(float(p))
    return hvn


# ============================================================
# Anchored VWAP
# ============================================================

def _anchored_vwap(daily: pd.DataFrame, anchor_idx: int) -> Optional[float]:
    """VWAP from anchor_idx to end."""
    if anchor_idx >= len(daily) or anchor_idx < 0:
        return None
    sub = daily.iloc[anchor_idx:]
    if sub.empty:
        return None
    tp = (sub["High"] + sub["Low"] + sub["Close"]) / 3.0
    vol = sub["Volume"].astype(float)
    if vol.sum() == 0:
        return None
    return float((tp * vol).sum() / vol.sum())


def _find_anchors(daily: pd.DataFrame) -> Dict[str, int]:
    """Find anchor bar indices for VWAP computation."""
    anchors = {}
    # Fix B-2 (2026-09-02 20:30 ET): belt-and-braces NaN guard for idxmin()/idxmax().
    # If Low/High has any NaN row, idxmin() returns the first NaN row, which would
    # then fail get_loc(). Filter first; if no valid anchor remains, skip it.
    valid = daily.dropna(subset=["Low", "High"])
    # 52-week low
    lookback = min(252, len(valid))
    if len(valid) > 0:
        sub = valid.iloc[-lookback:]
        idx_52w_low = sub["Low"].idxmin()
        if idx_52w_low is not None and idx_52w_low == idx_52w_low:  # != NaN
            try:
                anchors["vwap_52w_low"] = int(daily.index.get_loc(idx_52w_low))
            except (KeyError, ValueError):
                pass
    # Most recent swing low (60d)
    if len(valid) >= 60:
        sub60 = valid.iloc[-60:]
        idx = sub60["Low"].idxmin()
        if idx is not None and idx == idx:  # != NaN
            try:
                anchors["vwap_swing_low_60d"] = int(daily.index.get_loc(idx))
            except (KeyError, ValueError):
                pass
    # Most recent gap up (today's open > yesterday's close by >2%)
    if len(daily) >= 2:
        for i in range(len(daily) - 1, max(len(daily) - 30, 0), -1):
            prev_close = daily["Close"].iloc[i - 1]
            today_open = daily["Open"].iloc[i]
            if prev_close > 0 and (today_open - prev_close) / prev_close > 0.02:
                anchors["vwap_gap_up"] = i
                break
    return anchors


# ============================================================
# Gap detection (unfilled gaps)
# ============================================================

def _unfilled_gaps(daily: pd.DataFrame, lookback_d: int = 60) -> List[Dict[str, Any]]:
    """Return list of unfilled gap zones: {direction, lower, upper, age_days}."""
    if len(daily) < 2:
        return []
    gaps = []
    sub = daily.iloc[-lookback_d:]
    indices = list(range(len(sub)))
    for i in indices[1:]:
        # Fix B-3 (2026-09-02 20:30 ET): skip NaN-tainted bars rather than
        # propagate NaN into the gap calc and return a corrupt record.
        prev_close = float(sub["Close"].iloc[i - 1])
        today_open = float(sub["Open"].iloc[i])
        today_low = float(sub["Low"].iloc[i])
        today_high = float(sub["High"].iloc[i])
        if not (prev_close == prev_close and today_open == today_open
                and today_low == today_low and today_high == today_high):
            continue  # NaN bar — skip silently
        # Gap up
        if today_open > prev_close * 1.005:
            lower = prev_close
            upper = today_open
            # Check if filled since then
            filled = False
            for j in range(i + 1, len(sub)):
                if float(sub["Low"].iloc[j]) <= lower:
                    filled = True
                    break
            if not filled:
                gaps.append({
                    "direction": "up",
                    "lower": float(lower),
                    "upper": float(upper),
                    "age_days": len(sub) - i - 1,
                })
        # Gap down
        elif today_open < prev_close * 0.995:
            lower = today_open
            upper = prev_close
            filled = False
            for j in range(i + 1, len(sub)):
                if float(sub["High"].iloc[j]) >= upper:
                    filled = True
                    break
            if not filled:
                gaps.append({
                    "direction": "down",
                    "lower": float(lower),
                    "upper": float(upper),
                    "age_days": len(sub) - i - 1,
                })
    return gaps


# ============================================================
# Volume profile + A/D
# ============================================================

def _volume_metrics(daily: pd.DataFrame) -> VolumeProfile:
    close = daily["Close"].values.astype(float)
    high = daily["High"].values.astype(float)
    low = daily["Low"].values.astype(float)
    vol = daily["Volume"].values.astype(float)
    if len(close) < 21:
        return VolumeProfile(rvol_5d=1.0, rvol_20d=1.0,
                             accumulation_distribution_slope_20d=0.0,
                             expansion_today=False, contraction_5d=False)
    vol_5 = vol[-5:].mean()
    vol_20 = vol[-20:].mean()
    rvol_5 = float(vol_5 / max(vol_20, 1))
    rvol_20 = float(vol[-1] / max(vol_20, 1))
    # A/D proxy: (close - low) - (high - close) normalized by (high - low), times volume
    clv = np.where((high - low) > 0, ((close - low) - (high - close)) / (high - low), 0)
    ad = clv * vol
    if len(ad) >= 20:
        # Linear regression slope of cumulative A/D over 20d
        cad = np.cumsum(ad[-20:])
        x = np.arange(20, dtype=float)
        slope = np.polyfit(x, cad, 1)[0]
        ad_slope = float(slope / max(vol_20, 1))  # normalize per share
    else:
        ad_slope = 0.0
    expansion_today = bool(rvol_20 >= VOLATILITY_EXPANSION_RATIO)
    vol_5_vs_20 = vol_5 / max(vol_20, 1)
    contraction_5d = bool(vol_5_vs_20 <= 0.7)
    return VolumeProfile(
        rvol_5d=round(rvol_5, 2),
        rvol_20d=round(rvol_20, 2),
        accumulation_distribution_slope_20d=round(ad_slope, 4),
        expansion_today=expansion_today,
        contraction_5d=contraction_5d,
    )


# ============================================================
# ATR (for stops)
# ============================================================

def _atr(daily: pd.DataFrame, n: int = 14) -> float:
    if len(daily) < n + 1:
        return float(daily["High"].iloc[-1] - daily["Low"].iloc[-1])
    h = daily["High"].values[-n - 1:]
    l = daily["Low"].values[-n - 1:]
    c = daily["Close"].values[-n - 1:]
    tr = np.maximum(h - l, np.maximum(np.abs(h - np.roll(c, 1)), np.abs(l - np.roll(c, 1))))
    return float(tr[1:].mean())


# ============================================================
# Pattern detectors
# ============================================================

def _linear_regression_line(indices: List[int], prices: List[float]) -> Tuple[float, float, float]:
    """Returns (slope, intercept, r2) for price vs index."""
    if len(indices) < 2:
        return 0.0, 0.0, 0.0
    x = np.array(indices, dtype=float)
    y = np.array(prices, dtype=float)
    xm, ym = x.mean(), y.mean()
    slope = ((x - xm) * (y - ym)).sum() / max(((x - xm) ** 2).sum(), 1e-9)
    intercept = ym - slope * xm
    yhat = slope * x + intercept
    ss_res = ((y - yhat) ** 2).sum()
    ss_tot = ((y - ym) ** 2).sum()
    r2 = 1 - ss_res / max(ss_tot, 1e-9)
    return float(slope), float(intercept), float(r2)


def _detect_triangles(daily: pd.DataFrame, sh: List[int], sl: List[int], atr: float, vol: VolumeProfile) -> List[Pattern]:
    """Ascending / descending / symmetrical triangles with explicit criteria.

    Criteria (Mike 2026-09-02 18:26 ET):
      - Converging trendlines (upper declining, lower rising, or both converging)
      - ≥3 touches each side
      - ≥14 days duration
      - Range < 30% of mid (consolidation)
      - Declining RV inside pattern vs outside
    """
    if len(sh) < TRIANGLE_MIN_TOUCHES or len(sl) < TRIANGLE_MIN_TOUCHES:
        return []
    out: List[Pattern] = []
    # Take last 60 bars of pivots
    n = len(daily)
    sh = [i for i in sh if i >= n - 90]
    sl = [i for i in sl if i >= n - 90]
    if len(sh) < TRIANGLE_MIN_TOUCHES or len(sl) < TRIANGLE_MIN_TOUCHES:
        return []
    # Use last N pivots
    sh_last = sh[-TRIANGLE_MIN_TOUCHES - 2:]
    sl_last = sl[-TRIANGLE_MIN_TOUCHES - 2:]
    upper_slope, _, upper_r2 = _linear_regression_line(sh_last, [daily["High"].iloc[i] for i in sh_last])
    lower_slope, _, lower_r2 = _linear_regression_line(sl_last, [daily["Low"].iloc[i] for i in sl_last])
    duration = daily.index[sh_last[-1]] - daily.index[sh_last[0]]
    duration_days = duration.days if hasattr(duration, "days") else int(duration)
    if duration_days < TRIANGLE_MIN_DURATION_D:
        return []
    # Converging: upper negative, lower positive (ascending), upper positive, lower negative (descending), or both converging to apex
    upper_highs = [daily["High"].iloc[i] for i in sh_last]
    lower_lows = [daily["Low"].iloc[i] for i in sl_last]
    range_pct = (max(upper_highs) - min(lower_lows)) / ((max(upper_highs) + min(lower_lows)) / 2)
    if range_pct > TRIANGLE_MAX_RANGE_PCT:
        return []
    spot = float(daily["Close"].iloc[-1])
    upper_now = upper_slope * (n - 1) + 0  # use last index for trendline value
    upper_intercept = upper_highs[0] - upper_slope * sh_last[0]
    lower_intercept = lower_lows[0] - lower_slope * sl_last[0]
    upper_now = upper_slope * (n - 1) + upper_intercept
    lower_now = lower_slope * (n - 1) + lower_intercept
    # RV inside vs outside
    start_idx = sh_last[0]
    inside_rv = float(daily["Close"].pct_change().iloc[start_idx:].std() * math.sqrt(252))
    outside_rv = float(daily["Close"].pct_change().iloc[:start_idx].std() * math.sqrt(252)) if start_idx > 5 else inside_rv
    rv_declining = inside_rv < outside_rv * 0.85
    if not rv_declining:
        # Don't reject outright but mark in notes
        pass
    # Determine triangle type
    if upper_slope < 0 and lower_slope > 0:
        ptype = "ascending_triangle"
        trigger = upper_now
        stop = lower_now
        direction = "up"
    elif upper_slope > 0 and lower_slope < 0:
        ptype = "descending_triangle"
        trigger = lower_now
        stop = upper_now
        direction = "down"
    elif abs(upper_slope) < abs(lower_slope) * 0.5 and lower_slope > 0:
        ptype = "symmetrical_triangle"
        trigger = upper_now
        stop = lower_now
        direction = "up"
    elif abs(lower_slope) < abs(upper_slope) * 0.5 and upper_slope < 0:
        ptype = "symmetrical_triangle"
        trigger = lower_now
        stop = upper_now
        direction = "down"
    else:
        return []
    # State
    if direction == "up":
        beyond = spot >= trigger * (1 + BREAKOUT_THRESHOLD_PCT)
    else:
        beyond = spot <= trigger * (1 - BREAKOUT_THRESHOLD_PCT)
    if beyond and vol.rvol_20d >= BREAKOUT_VOLUME_MULT:
        state = "confirmed"
    elif beyond:
        state = "developing"
    else:
        state = "developing"
    # Check failure: closed back through opposite trendline
    if direction == "up" and spot < lower_now * (1 - BREAKOUT_THRESHOLD_PCT):
        state = "failed"
    elif direction == "down" and spot > upper_now * (1 + BREAKOUT_THRESHOLD_PCT):
        state = "failed"
    target = trigger + (trigger - stop) * 1.5 if direction == "up" else trigger - (stop - trigger) * 1.5
    out.append(Pattern(
        type=ptype,
        state=state,
        trigger_price=round(float(trigger), 2),
        stop_price=round(float(stop), 2),
        target_price=round(float(target), 2) if target else None,
        expected_range_pct=round(range_pct * 100, 2),
        volume_confirmation=bool(vol.rvol_20d >= BREAKOUT_VOLUME_MULT),
        volatility_state="contracting" if rv_declining else "stable",
        criteria={
            "touches_upper": len(sh_last),
            "touches_lower": len(sl_last),
            "duration_days": duration_days,
            "range_pct": round(range_pct * 100, 2),
            "upper_r2": round(upper_r2, 3),
            "lower_r2": round(lower_r2, 3),
            "rv_declining": rv_declining,
            "rv_inside": round(inside_rv, 3),
            "rv_outside": round(outside_rv, 3),
        },
        duration_days=duration_days,
        notes=f"Upper slope={upper_slope:.3f}, lower slope={lower_slope:.3f}",
    ))
    return out


def _detect_rectangle(daily: pd.DataFrame, sh: List[int], sl: List[int], atr: float, vol: VolumeProfile) -> List[Pattern]:
    """Parallel H/L range. Criteria:
      - ≥2 touches each side
      - ≥10 days duration
      - Range std < 4%
      - Volume contraction inside range
    """
    if len(sh) < RECTANGLE_MIN_TOUCHES or len(sl) < RECTANGLE_MIN_TOUCHES:
        return []
    n = len(daily)
    sh = [i for i in sh if i >= n - 90]
    sl = [i for i in sl if i >= n - 90]
    if len(sh) < RECTANGLE_MIN_TOUCHES or len(sl) < RECTANGLE_MIN_TOUCHES:
        return []
    sh_last = sh[-RECTANGLE_MIN_TOUCHES - 2:]
    sl_last = sl[-RECTANGLE_MIN_TOUCHES - 2:]
    duration = daily.index[sh_last[-1]] - daily.index[sh_last[0]]
    duration_days = duration.days if hasattr(duration, "days") else int(duration)
    if duration_days < RECTANGLE_MIN_DURATION_D:
        return []
    upper_highs = [daily["High"].iloc[i] for i in sh_last]
    lower_lows = [daily["Low"].iloc[i] for i in sl_last]
    upper = float(np.mean(upper_highs))
    lower = float(np.mean(lower_lows))
    if upper <= lower:
        return []
    range_pct = (upper - lower) / ((upper + lower) / 2)
    # Range std: std of closes inside range
    start_idx = sh_last[0]
    inside_closes = daily["Close"].iloc[start_idx:]
    range_std_pct = float(inside_closes.pct_change().std() * math.sqrt(252))
    if range_std_pct > 0.35:  # too volatile to be rectangle
        return []
    spot = float(daily["Close"].iloc[-1])
    mid = (upper + lower) / 2
    if spot >= upper * (1 + BREAKOUT_THRESHOLD_PCT):
        state = "confirmed" if vol.rvol_20d >= BREAKOUT_VOLUME_MULT else "developing"
        direction = "up"
    elif spot <= lower * (1 - BREAKOUT_THRESHOLD_PCT):
        state = "confirmed" if vol.rvol_20d >= BREAKOUT_VOLUME_MULT else "developing"
        direction = "down"
    else:
        state = "developing"
        direction = "up" if spot > mid else "down"
    trigger = upper if direction == "up" else lower
    stop = lower if direction == "up" else upper
    target = trigger + (trigger - stop) * 1.0 if direction == "up" else trigger - (stop - trigger) * 1.0
    return [Pattern(
        type="rectangle",
        state=state,
        trigger_price=round(float(trigger), 2),
        stop_price=round(float(stop), 2),
        target_price=round(float(target), 2),
        expected_range_pct=round(range_pct * 100, 2),
        volume_confirmation=bool(vol.contraction_5d or vol.rvol_20d >= BREAKOUT_VOLUME_MULT),
        volatility_state="contracting" if vol.contraction_5d else "stable",
        criteria={
            "touches_upper": len(sh_last),
            "touches_lower": len(sl_last),
            "duration_days": duration_days,
            "range_pct": round(range_pct * 100, 2),
            "range_std_pct": round(range_std_pct * 100, 2),
            "upper": round(upper, 2),
            "lower": round(lower, 2),
        },
        duration_days=duration_days,
        notes=f"Direction={direction} (spot vs mid)",
    )]


def _detect_double_top_bottom(daily: pd.DataFrame, sh: List[int], sl: List[int], atr: float, vol: VolumeProfile) -> List[Pattern]:
    """Double top / double bottom with neckline."""
    out: List[Pattern] = []
    n = len(daily)
    spot = float(daily["Close"].iloc[-1])
    # Double top: two swing highs within DOUBLE_TOLERANCE_PCT, separated by ≥DOUBLE_MIN_SEPARATION_BARS
    if len(sh) >= 2:
        sh_recent = [i for i in sh if i >= n - 120]
        for i in range(len(sh_recent) - 1):
            i1, i2 = sh_recent[i], sh_recent[i + 1]
            if i2 - i1 < DOUBLE_MIN_SEPARATION_BARS:
                continue
            p1 = daily["High"].iloc[i1]
            p2 = daily["High"].iloc[i2]
            if abs(p1 - p2) / ((p1 + p2) / 2) > DOUBLE_TOLERANCE_PCT:
                continue
            # Neckline = lowest low between and after
            neckline = daily["Low"].iloc[i1:i2 + 1].min()
            if spot < neckline * (1 - BREAKOUT_THRESHOLD_PCT):
                state = "confirmed" if vol.rvol_20d >= BREAKOUT_VOLUME_MULT else "developing"
            elif spot > p2 * (1 - BREAKOUT_THRESHOLD_PCT):
                state = "failed"  # broke above second peak instead
            else:
                state = "developing"
            out.append(Pattern(
                type="double_top",
                state=state,
                trigger_price=round(float(neckline), 2),
                stop_price=round(float(max(p1, p2) * 1.02), 2),
                target_price=round(float(neckline - (max(p1, p2) - neckline)), 2),
                expected_range_pct=round(float((max(p1, p2) - neckline) / neckline * 100), 2),
                volume_confirmation=bool(vol.rvol_20d >= BREAKOUT_VOLUME_MULT),
                volatility_state="stable",
                criteria={
                    "peak1_idx": int(i1),
                    "peak2_idx": int(i2),
                    "separation_bars": int(i2 - i1),
                    "peak_tolerance_pct": round(float(abs(p1 - p2) / ((p1 + p2) / 2) * 100), 2),
                    "neckline": round(float(neckline), 2),
                },
                duration_days=int(i2 - i1),
            ))
            break
    # Double bottom
    if len(sl) >= 2:
        sl_recent = [i for i in sl if i >= n - 120]
        for i in range(len(sl_recent) - 1):
            i1, i2 = sl_recent[i], sl_recent[i + 1]
            if i2 - i1 < DOUBLE_MIN_SEPARATION_BARS:
                continue
            p1 = daily["Low"].iloc[i1]
            p2 = daily["Low"].iloc[i2]
            if abs(p1 - p2) / ((p1 + p2) / 2) > DOUBLE_TOLERANCE_PCT:
                continue
            neckline = daily["High"].iloc[i1:i2 + 1].max()
            if spot > neckline * (1 + BREAKOUT_THRESHOLD_PCT):
                state = "confirmed" if vol.rvol_20d >= BREAKOUT_VOLUME_MULT else "developing"
            elif spot < p2 * (1 + BREAKOUT_THRESHOLD_PCT):
                state = "failed"
            else:
                state = "developing"
            out.append(Pattern(
                type="double_bottom",
                state=state,
                trigger_price=round(float(neckline), 2),
                stop_price=round(float(min(p1, p2) * 0.98), 2),
                target_price=round(float(neckline + (neckline - min(p1, p2))), 2),
                expected_range_pct=round(float((neckline - min(p1, p2)) / neckline * 100), 2),
                volume_confirmation=bool(vol.rvol_20d >= BREAKOUT_VOLUME_MULT),
                volatility_state="stable",
                criteria={
                    "trough1_idx": int(i1),
                    "trough2_idx": int(i2),
                    "separation_bars": int(i2 - i1),
                    "trough_tolerance_pct": round(float(abs(p1 - p2) / ((p1 + p2) / 2) * 100), 2),
                    "neckline": round(float(neckline), 2),
                },
                duration_days=int(i2 - i1),
            ))
            break
    return out


def _detect_flag_pennant(daily: pd.DataFrame, atr: float, vol: VolumeProfile) -> List[Pattern]:
    """Flag/pennant: strong impulse (≥5%) followed by short consolidation (≤20d) with declining RV."""
    if len(daily) < 30:
        return []
    closes = daily["Close"].values.astype(float)
    n = len(daily)
    spot = float(closes[-1])
    # Find strong impulse in last 20 bars (≥5% in ≤10 days)
    for start in range(max(0, n - 30), n - 5):
        for end in range(start + 5, min(start + 11, n - 5)):
            move = (closes[end] - closes[start]) / closes[start]
            if abs(move) >= FLAG_MIN_IMPULSE_PCT:
                # Consolidation after end
                consol = daily.iloc[end:]
                if len(consol) < 5 or len(consol) > FLAG_MAX_DURATION_D:
                    continue
                consol_close_std = float(consol["Close"].pct_change().std() * math.sqrt(252))
                impulse_close_std = float(daily["Close"].iloc[start:end].pct_change().std() * math.sqrt(252))
                if consol_close_std >= impulse_close_std * FLAG_RV_DECLINE:
                    continue
                # Consolidation slope
                x = np.arange(len(consol), dtype=float)
                y = consol["Close"].values
                slope = np.polyfit(x, y, 1)[0] if len(x) >= 2 else 0
                # Range
                consol_high = float(consol["High"].max())
                consol_low = float(consol["Low"].min())
                range_pct = (consol_high - consol_low) / spot
                if move > 0:
                    direction = "up"
                    ptype = "bull_flag" if abs(slope) < (consol_high - consol_low) / 2 else "bull_pennant"
                    trigger = consol_high
                    stop = consol_low
                else:
                    direction = "down"
                    ptype = "bear_flag" if abs(slope) < (consol_high - consol_low) / 2 else "bear_pennant"
                    trigger = consol_low
                    stop = consol_high
                if direction == "up":
                    beyond = spot >= trigger * (1 + BREAKOUT_THRESHOLD_PCT)
                else:
                    beyond = spot <= trigger * (1 - BREAKOUT_THRESHOLD_PCT)
                if beyond and vol.rvol_20d >= BREAKOUT_VOLUME_MULT:
                    state = "confirmed"
                elif beyond:
                    state = "developing"
                else:
                    state = "developing"
                target = trigger + (trigger - stop) * 1.5 if direction == "up" else trigger - (stop - trigger) * 1.5
                return [Pattern(
                    type=ptype,
                    state=state,
                    trigger_price=round(float(trigger), 2),
                    stop_price=round(float(stop), 2),
                    target_price=round(float(target), 2),
                    expected_range_pct=round(range_pct * 100, 2),
                    volume_confirmation=bool(vol.rvol_20d >= BREAKOUT_VOLUME_MULT),
                    volatility_state="contracting",
                    criteria={
                        "impulse_pct": round(move * 100, 2),
                        "impulse_bars": int(end - start),
                        "consol_bars": len(consol),
                        "impulse_rv": round(impulse_close_std, 3),
                        "consol_rv": round(consol_close_std, 3),
                        "rv_decline_ratio": round(consol_close_std / max(impulse_close_std, 1e-9), 3),
                    },
                    duration_days=int(len(consol)),
                    notes=f"Impulse {move*100:+.1f}% over {end-start}d",
                )]
    return []


def _detect_h_and_s(daily: pd.DataFrame, sh: List[int], sl: List[int], atr: float, vol: VolumeProfile) -> List[Pattern]:
    """Head and shoulders / inverse H&S."""
    out: List[Pattern] = []
    n = len(daily)
    spot = float(daily["Close"].iloc[-1])
    if len(sh) < 3:
        return []
    sh_recent = [i for i in sh if i >= n - 180]
    # Look for L-H-L-H pattern (left shoulder, head, right shoulder)
    for i in range(len(sh_recent) - 2):
        ls_i, head_i, rs_i = sh_recent[i], sh_recent[i + 1], sh_recent[i + 2]
        ls = daily["High"].iloc[ls_i]
        head = daily["High"].iloc[head_i]
        rs = daily["High"].iloc[rs_i]
        if not (head > ls and head > rs):
            continue
        if abs(rs - ls) / ((rs + ls) / 2) > HEAD_SHOULDER_TOLERANCE_PCT:
            continue
        if (head_i - ls_i) < 10 or (rs_i - head_i) < 10:
            continue
        # Neckline = low after left shoulder and low after right shoulder
        neckline = min(daily["Low"].iloc[ls_i:head_i + 1].min(), daily["Low"].iloc[head_i:rs_i + 1].min())
        duration = (daily.index[rs_i] - daily.index[ls_i]).days
        if duration < H_AND_S_MIN_DURATION_D:
            continue
        if spot < neckline * (1 - BREAKOUT_THRESHOLD_PCT):
            state = "confirmed" if vol.rvol_20d >= BREAKOUT_VOLUME_MULT else "developing"
        elif spot > rs * (1 + BREAKOUT_THRESHOLD_PCT):
            state = "failed"
        else:
            state = "developing"
        out.append(Pattern(
            type="head_and_shoulders",
            state=state,
            trigger_price=round(float(neckline), 2),
            stop_price=round(float(rs * 1.02), 2),
            target_price=round(float(neckline - (head - neckline)), 2),
            expected_range_pct=round(float((head - neckline) / neckline * 100), 2),
            volume_confirmation=bool(vol.rvol_20d >= BREAKOUT_VOLUME_MULT),
            volatility_state="stable",
            criteria={
                "left_shoulder": round(float(ls), 2),
                "head": round(float(head), 2),
                "right_shoulder": round(float(rs), 2),
                "neckline": round(float(neckline), 2),
                "shoulder_tolerance_pct": round(float(abs(rs - ls) / ((rs + ls) / 2) * 100), 2),
                "duration_days": int(duration),
            },
            duration_days=int(duration),
        ))
        break
    # Inverse H&S
    if len(sl) >= 3:
        sl_recent = [i for i in sl if i >= n - 180]
        for i in range(len(sl_recent) - 2):
            ls_i, head_i, rs_i = sl_recent[i], sl_recent[i + 1], sl_recent[i + 2]
            ls = daily["Low"].iloc[ls_i]
            head = daily["Low"].iloc[head_i]
            rs = daily["Low"].iloc[rs_i]
            if not (head < ls and head < rs):
                continue
            if abs(rs - ls) / ((rs + ls) / 2) > HEAD_SHOULDER_TOLERANCE_PCT:
                continue
            if (head_i - ls_i) < 10 or (rs_i - head_i) < 10:
                continue
            neckline = max(daily["High"].iloc[ls_i:head_i + 1].max(), daily["High"].iloc[head_i:rs_i + 1].max())
            duration = (daily.index[rs_i] - daily.index[ls_i]).days
            if duration < H_AND_S_MIN_DURATION_D:
                continue
            if spot > neckline * (1 + BREAKOUT_THRESHOLD_PCT):
                state = "confirmed" if vol.rvol_20d >= BREAKOUT_VOLUME_MULT else "developing"
            elif spot < rs * (1 - BREAKOUT_THRESHOLD_PCT):
                state = "failed"
            else:
                state = "developing"
            out.append(Pattern(
                type="inverse_h&s",
                state=state,
                trigger_price=round(float(neckline), 2),
                stop_price=round(float(rs * 0.98), 2),
                target_price=round(float(neckline + (neckline - head)), 2),
                expected_range_pct=round(float((neckline - head) / neckline * 100), 2),
                volume_confirmation=bool(vol.rvol_20d >= BREAKOUT_VOLUME_MULT),
                volatility_state="stable",
                criteria={
                    "left_shoulder_low": round(float(ls), 2),
                    "head_low": round(float(head), 2),
                    "right_shoulder_low": round(float(rs), 2),
                    "neckline": round(float(neckline), 2),
                    "shoulder_tolerance_pct": round(float(abs(rs - ls) / ((rs + ls) / 2) * 100), 2),
                    "duration_days": int(duration),
                },
                duration_days=int(duration),
            ))
            break
    return out


# ============================================================
# Support / Resistance builder
# ============================================================

def _build_sr_levels(daily: pd.DataFrame, weekly: pd.DataFrame, vp_levels: List[Tuple[float, float]],
                     trend: Trend, atr: float) -> Tuple[List[SupportLevel], List[ResistanceLevel]]:
    supports: List[SupportLevel] = []
    resistances: List[ResistanceLevel] = []
    spot = float(daily["Close"].iloc[-1])
    n = len(daily)
    # Swing lows (support)
    sl_indices = _find_swing_lows(daily["Low"].values.astype(float))
    for idx in sl_indices[-10:]:
        price = float(daily["Low"].iloc[idx])
        days_ago = n - idx - 1
        if days_ago > 180:
            continue
        if price >= spot:
            continue
        supports.append(SupportLevel(
            price=round(price, 2),
            level_type="swing_low",
            strength=round(1.0 / max(days_ago / 30, 0.5), 2),
            touches=1,
            last_touched_days_ago=int(days_ago),
            distance_pct=round((spot - price) / spot * 100, 2),
        ))
    # Swing highs (resistance)
    sh_indices = _find_swing_highs(daily["High"].values.astype(float))
    for idx in sh_indices[-10:]:
        price = float(daily["High"].iloc[idx])
        days_ago = n - idx - 1
        if days_ago > 180:
            continue
        if price <= spot:
            continue
        resistances.append(ResistanceLevel(
            price=round(price, 2),
            level_type="swing_high",
            strength=round(1.0 / max(days_ago / 30, 0.5), 2),
            touches=1,
            last_touched_days_ago=int(days_ago),
            distance_pct=round((price - spot) / spot * 100, 2),
        ))
    # MA levels
    for n_ma, label in [(20, "ma_20"), (50, "ma_50"), (200, "ma_200")]:
        if len(daily) < n_ma:
            continue
        ma_val = float(daily["Close"].rolling(n_ma).mean().iloc[-1])
        if math.isnan(ma_val):
            continue
        if ma_val < spot:
            supports.append(SupportLevel(
                price=round(ma_val, 2),
                level_type=label,
                strength=0.5,
                touches=1,
                last_touched_days_ago=0,
                distance_pct=round((spot - ma_val) / spot * 100, 2),
            ))
        else:
            resistances.append(ResistanceLevel(
                price=round(ma_val, 2),
                level_type=label,
                strength=0.5,
                touches=1,
                last_touched_days_ago=0,
                distance_pct=round((ma_val - spot) / spot * 100, 2),
            ))
    # Anchored VWAPs
    anchors = _find_anchors(daily)
    for anchor_name, anchor_idx in anchors.items():
        vwap_val = _anchored_vwap(daily, anchor_idx)
        if vwap_val is None or vwap_val <= 0:
            continue
        if vwap_val < spot:
            supports.append(SupportLevel(
                price=round(vwap_val, 2),
                level_type=anchor_name,
                strength=0.6,
                touches=1,
                last_touched_days_ago=int(n - anchor_idx - 1),
                distance_pct=round((spot - vwap_val) / spot * 100, 2),
            ))
        else:
            resistances.append(ResistanceLevel(
                price=round(vwap_val, 2),
                level_type=anchor_name,
                strength=0.6,
                touches=1,
                last_touched_days_ago=int(n - anchor_idx - 1),
                distance_pct=round((vwap_val - spot) / spot * 100, 2),
            ))
    # Volume profile HVN
    hvns = _hvn_levels(vp_levels)
    for hvn_price in hvns:
        if hvn_price < spot:
            supports.append(SupportLevel(
                price=round(hvn_price, 2),
                level_type="volume_profile_hvn",
                strength=0.7,
                touches=1,
                last_touched_days_ago=0,
                distance_pct=round((spot - hvn_price) / spot * 100, 2),
            ))
        else:
            resistances.append(ResistanceLevel(
                price=round(hvn_price, 2),
                level_type="volume_profile_hvn",
                strength=0.7,
                touches=1,
                last_touched_days_ago=0,
                distance_pct=round((hvn_price - spot) / spot * 100, 2),
            ))
    # Unfilled gaps
    for gap in _unfilled_gaps(daily):
        if gap["direction"] == "up":
            # Gap up: lower = old close (support), upper = today's open (resistance)
            supports.append(SupportLevel(
                price=round(gap["lower"], 2),
                level_type="gap_fill",
                strength=0.6,
                touches=0,
                last_touched_days_ago=gap["age_days"],
                distance_pct=round((spot - gap["lower"]) / spot * 100, 2),
            ))
        else:
            resistances.append(ResistanceLevel(
                price=round(gap["upper"], 2),
                level_type="gap_fill",
                strength=0.6,
                touches=0,
                last_touched_days_ago=gap["age_days"],
                distance_pct=round((gap["upper"] - spot) / spot * 100, 2),
            ))
    # Sort by distance to spot
    supports.sort(key=lambda x: x.distance_pct)
    resistances.sort(key=lambda x: x.distance_pct)
    return supports[:8], resistances[:8]


# ============================================================
# Scoring
# ============================================================

def _score_chart(cs: ChartStructure) -> Dict[str, float]:
    """Score each component 0-100, then weighted total."""
    scores: Dict[str, float] = {}
    # Trend (0-100)
    trend_score = 50.0
    if cs.trend is not None:
        t = cs.trend
        if t.direction == "up" and t.ma_alignment == "bullish_20_50_200":
            trend_score = 95
        elif t.direction == "up":
            trend_score = 75
        elif t.direction == "down" and t.ma_alignment == "bearish_20_50_200":
            trend_score = 5
        elif t.direction == "down":
            trend_score = 25
        else:
            trend_score = 50
        # Adjust by regression R² (high R² = stronger)
        trend_score = max(0, min(100, trend_score + (t.regression_r2 - 0.5) * 20))
        # Adjust by HH/HL count
        trend_score = max(0, min(100, trend_score + min(t.hh_hl_count_60d, 4) * 2.5))
    scores["trend"] = round(trend_score, 1)
    # S/R confluence (0-100): how many support levels cluster near spot (within 5%)
    near_supports = sum(1 for s in cs.supports if s.distance_pct <= 5)
    near_resistances = sum(1 for s in cs.resistances if s.distance_pct <= 5)
    sr_score = 50 + (near_supports * 5) + (near_resistances * 5) - (len(cs.supports) * 2)
    # Bonus for high-strength levels near spot
    if cs.supports and cs.supports[0].distance_pct <= 3 and cs.supports[0].strength >= 0.6:
        sr_score += 15
    scores["sr_confluence"] = round(max(0, min(100, sr_score)), 1)
    # Volume (0-100)
    vol_score = 50.0
    if cs.volume is not None:
        v = cs.volume
        # Expansion is good for breakouts; contraction is good for setups
        if v.expansion_today:
            vol_score += 15
        if v.contraction_5d:
            vol_score += 10
        if v.accumulation_distribution_slope_20d > 0:
            vol_score += 15
        elif v.accumulation_distribution_slope_20d < 0:
            vol_score -= 10
        # Penalize low RVOL (no interest)
        if v.rvol_20d < 0.7:
            vol_score -= 10
    scores["volume"] = round(max(0, min(100, vol_score)), 1)
    # Volatility state (0-100): contracting = setup, expanding = breakout
    vol_state_score = 50.0
    confirmed_patterns = [p for p in cs.patterns if p.state == "confirmed"]
    if confirmed_patterns:
        vol_state_score = 90
    elif any(p.volatility_state == "contracting" for p in cs.patterns):
        vol_state_score = 75
    elif any(p.volatility_state == "expanding" for p in cs.patterns):
        vol_state_score = 60
    else:
        vol_state_score = 40
    scores["volatility_state"] = round(vol_state_score, 1)
    # Breakout quality (0-100)
    bq_score = 30.0
    confirmed = [p for p in cs.patterns if p.state == "confirmed"]
    developing = [p for p in cs.patterns if p.state == "developing"]
    failed = [p for p in cs.patterns if p.state == "failed"]
    invalidated = [p for p in cs.patterns if p.state == "invalidated"]
    if confirmed:
        bq_score = 95
    elif developing:
        bq_score = 60
    if failed or invalidated:
        bq_score = max(bq_score - 20, 10)
    # Volume confirmation bonus
    if any(p.volume_confirmation for p in cs.patterns):
        bq_score = min(100, bq_score + 10)
    scores["breakout_quality"] = round(bq_score, 1)
    # Total
    total = sum(scores[k] * WEIGHTS[k] for k in WEIGHTS)
    scores["total"] = round(total, 1)
    # Label
    if total >= 80:
        scores["label"] = "A+ (high quality)"
    elif total >= 65:
        scores["label"] = "A"
    elif total >= 50:
        scores["label"] = "B"
    elif total >= 35:
        scores["label"] = "C"
    else:
        scores["label"] = "D (avoid)"
    return scores


# ============================================================
# Main entry point
# ============================================================

def analyze_chart_structure(symbol: str, include_backtest: bool = False) -> ChartStructure:
    """Compute systematic chart structure for `symbol`.

    Returns ChartStructure with: trend, supports, resistances, patterns,
    volume, score. State labels per Mike 2026-09-02 18:26 ET directive.

    Chart structure is ONE input. Do not issue a pick solely because of a
    chart pattern. Combine with IV/EV/regime/flow/named-trader signals.
    """
    cs = ChartStructure(
        symbol=symbol.upper(),
        spot=0.0,
        as_of="",
    )
    try:
        daily = _fetch_ohlcv(symbol, DAILY_SETUP_LOOKBACK_D)
        if daily.empty or len(daily) < 60:
            cs.error = f"Insufficient daily data ({len(daily)} bars)"
            return cs
        # Fix B-4 (2026-09-02 20:30 ET): defensive NaN drop. Today's session in
        # progress has NaN Open/High/Low/Close until 4:30pm ET; drop those rows
        # so every downstream function gets a clean frame. Re-check length after
        # drop; if insufficient, return empty rather than raise downstream.
        pre_drop = len(daily)
        daily = daily.dropna(subset=["Open", "High", "Low", "Close"])
        if len(daily) < 60:
            cs.error = f"Insufficient valid OHLC after NaN drop ({len(daily)} of {pre_drop} bars)"
            return cs
        weekly = _weekly_ohlcv(daily)
        spot = float(daily["Close"].iloc[-1])
        cs.spot = round(spot, 2)
        cs.as_of = str(daily.index[-1].date())
        # Trend
        cs.trend = _compute_trend(daily, weekly)
        # Volume profile
        poc, vp_levels = _volume_profile(daily)
        # Volume metrics
        cs.volume = _volume_metrics(daily)
        # ATR for stops
        atr_val = _atr(daily)
        # Pivots
        sh = _find_swing_highs(daily["High"].values.astype(float))
        sl = _find_swing_lows(daily["Low"].values.astype(float))
        # Pattern detectors
        cs.patterns = []
        cs.patterns += _detect_triangles(daily, sh, sl, atr_val, cs.volume)
        cs.patterns += _detect_rectangle(daily, sh, sl, atr_val, cs.volume)
        cs.patterns += _detect_double_top_bottom(daily, sh, sl, atr_val, cs.volume)
        cs.patterns += _detect_flag_pennant(daily, atr_val, cs.volume)
        cs.patterns += _detect_h_and_s(daily, sh, sl, atr_val, cs.volume)
        # Dedupe: keep most specific
        # (simple version: keep all; backtest layer will rank)
        # S/R levels
        cs.supports, cs.resistances = _build_sr_levels(daily, weekly, vp_levels, cs.trend, atr_val)
        # Score
        cs.score = _score_chart(cs)
        # Conditional backtest lookup (lazy)
        if include_backtest:
            try:
                from pattern_backtest import get_conditional_stats
                for p in cs.patterns:
                    stats = get_conditional_stats(symbol, p.type)
                    if stats:
                        p.historical_conditional_hit_rate = stats.get("hit_rate")
                        p.historical_conditional_avg_return_4w = stats.get("avg_return_4w")
                        p.historical_conditional_n = stats.get("n")
            except Exception:
                pass
        cs.note = ("Chart structure is ONE input. Confirm with regime (HMM), "
                   "vol surface (SABR-lite), expected-move reconciliation, "
                   "flow composite, and named-trader signals.")
    except Exception as e:
        cs.error = f"chart_structure error: {e}"
    return cs


def chart_structure_to_dict(cs: ChartStructure) -> Dict[str, Any]:
    """Convert ChartStructure dataclass to dict for JSON serialization."""
    out: Dict[str, Any] = {
        "symbol": cs.symbol,
        "spot": cs.spot,
        "as_of": cs.as_of,
        "primary_timeframe": cs.primary_timeframe,
        "structure_timeframe": cs.structure_timeframe,
        "weights": cs.weights,
        "score": cs.score,
        "note": cs.note,
        "error": cs.error,
    }
    if cs.trend:
        out["trend"] = asdict(cs.trend)
    out["supports"] = [asdict(s) for s in cs.supports]
    out["resistances"] = [asdict(r) for r in cs.resistances]
    out["patterns"] = [asdict(p) for p in cs.patterns]
    if cs.volume:
        out["volume"] = asdict(cs.volume)
    return out
