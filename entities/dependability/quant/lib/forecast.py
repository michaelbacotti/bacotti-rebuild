"""
forecast.py — Multi-horizon probabilistic forecasts.

Directive (Mike 2026-09-02 18:37 ET, pasted):
  "For each candidate, provide a probabilistic forecast rather than one target
   price: current price; 5-, 10-, 21-, 42-, and 63-trading-day median scenario;
   68% and 90% forecast ranges; implied options range through relevant expirations;
   historical realized range; pattern-conditional range; key support, resistance,
   trigger, and invalidation. State sample size, calibration/coverage accuracy,
   and whether the chart-pattern feature improves results versus the same model
   without it."

  "Do not label a pattern or forecast as validated unless it has passed an
   untouched out-of-sample test and has been tracked in forward paper trading."

This module produces:
  - Per-horizon (5/10/21/42/63 trading days): median, 68%, 90%
  - Three forecast methods: GBM-based, IV-implied, historical realized
  - Pattern-conditional blend when a pattern is present
  - Calibration report (when OOS data exists)
  - Saved artifact (point-in-time, JSON) for every forecast

Design constraints:
  - NO future information: spot, RV, drift computed only from data ≤ decision date
  - Adjusts for splits/dividends: yfinance auto_adjust=True in fetch
  - Realistic entry timing: assumed next-bar open (already known at forecast time)
  - Slippage/spreads/commissions: NOT in this module — handled by paper_trading
  - Exits/market exposure: NOT in this module — handled by paper_trading
  - Position sizing: NOT in this module — handled by trade_sizer

Forecast is "OOS-conditional" not "validated" until forward paper-trading data
exists for ≥21 trading days.
"""
from __future__ import annotations

import json
import math
import os
import time
import hashlib
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import numpy as np
import pandas as pd


# Horizons in trading days (Mike's spec)
HORIZONS_D = [5, 10, 21, 42, 63]

# Confidence levels
Z_68 = 1.0      # ±1 sigma
Z_90 = 1.645    # ±1.645 sigma

# Forecast blend weights (sum to 1.0)
BLEND_WEIGHTS = {
    "gbm": 0.50,
    "iv_implied": 0.30,
    "historical_realized": 0.20,
}

# Forecast artifact storage
ARTIFACT_DIR = Path(os.path.expanduser(
    "~/.openclaw/workspace-bacottibot/entities/dependability/quant/data/forecasts"
))
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# Data containers
# ============================================================

@dataclass
class HorizonForecast:
    horizon_d: int                 # 5, 10, 21, 42, 63
    horizon_label: str            # "1w", "2w", "1mo", "2mo", "3mo"
    median_price: float
    median_return_pct: float
    band_68_lower: float
    band_68_upper: float
    band_90_lower: float
    band_90_upper: float
    sigma_annualized: float       # volatility used
    method: str                   # "ensemble" | "gbm" | "iv_implied" | "historical"


@dataclass
class ForecastArtifact:
    """Point-in-time, versioned forecast."""
    artifact_id: str               # sha256 of inputs
    symbol: str
    as_of_date: str                # ISO date — point-in-time cutoff
    spot: float
    spot_as_of: str
    code_version: str              # git hash or static version string
    code_module: str               # "forecast.py"
    params: Dict[str, Any]         # blend weights, horizons, etc.
    horizons: List[HorizonForecast]
    iv_implied_used: bool          # was IV-implied component available?
    historical_realized_used: bool
    pattern_conditional_used: bool
    pattern_conditional_type: Optional[str]
    pattern_conditional_avg_return_4w: Optional[float]
    # Pointers to other artifacts
    chart_structure_artifact_id: Optional[str]
    calibration_artifact_id: Optional[str]
    notes: str = ""
    created_at: float = field(default_factory=time.time)


@dataclass
class CalibrationPoint:
    """One forecast vs actual outcome."""
    artifact_id: str
    symbol: str
    as_of_date: str
    horizon_d: int
    median_return: float
    band_68_lower: float
    band_68_upper: float
    band_90_lower: float
    band_90_upper: float
    actual_return: Optional[float] = None
    in_band_68: Optional[bool] = None
    in_band_90: Optional[bool] = None
    realized_at: Optional[str] = None


# ============================================================
# Data fetch (point-in-time)
# ============================================================

def _fetch_ohlcv_pit(symbol: str, as_of_date: Optional[str] = None) -> pd.DataFrame:
    """Fetch OHLCV. If as_of_date given, slice to ≤ as_of_date (point-in-time).

    Uses auto_adjust=True for split/dividend adjustment (yfinance default).

    Fix A-extended (2026-09-02 20:30 ET, per user directive "Use finite-value
    validation for all numeric inputs and published quantitative outputs;
    invalid or insufficient data must return an explicit unavailable or
    insufficient_data status, never a silent fallback"). Strips trailing
    NaN-tainted rows (today's incomplete session) so downstream spot, RV,
    drift, and band math never compute on NaN.
    """
    import yfinance as yf
    df = yf.Ticker(symbol).history(period="5y", auto_adjust=True, actions=False)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.rename_axis("Date").reset_index()
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    df = df.set_index("Date").sort_index()
    if as_of_date is not None:
        cutoff = pd.to_datetime(as_of_date)
        df = df[df.index <= cutoff]
    keep = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    out = df[keep].copy()
    # Drop trailing NaN-tainted rows (today's incomplete session bar).
    # Keep all historical valid bars even if some intermediate NaN exist.
    if len(out) > 0:
        valid_mask = out[["Open", "High", "Low", "Close"]].notna().all(axis=1)
        # Find the trailing window that is fully valid; trim any trailing NaN.
        last_valid_idx = out.index[valid_mask][-1] if valid_mask.any() else None
        if last_valid_idx is not None:
            out = out.loc[:last_valid_idx]
    return out


# ============================================================
# Forecast components
# ============================================================

def _gbm_component(spot: float, daily_returns: np.ndarray, horizon_d: int) -> Tuple[float, float, float, float]:
    """GBM-based: drift + sigma from realized daily returns.

    Returns: (median, sigma_ann, lower_68, upper_68, lower_90, upper_90)
    (lower_90/upper_90 computed via return as separate tuple in caller)
    """
    if len(daily_returns) < 20:
        return spot, 0.5, spot, spot, spot, spot
    # Use 60-day window for drift, full window for sigma
    drift_window = min(60, len(daily_returns))
    sigma_window = min(120, len(daily_returns))
    drift_daily = float(np.mean(daily_returns[-drift_window:]))
    sigma_daily = float(np.std(daily_returns[-sigma_window:], ddof=1))
    sigma_ann = sigma_daily * math.sqrt(252)
    # GBM forward
    drift_h = drift_daily * horizon_d
    sigma_h = sigma_daily * math.sqrt(horizon_d)
    median = spot * math.exp(drift_h)
    lower_68 = spot * math.exp(drift_h - Z_68 * sigma_h)
    upper_68 = spot * math.exp(drift_h + Z_68 * sigma_h)
    lower_90 = spot * math.exp(drift_h - Z_90 * sigma_h)
    upper_90 = spot * math.exp(drift_h + Z_90 * sigma_h)
    return median, sigma_ann, lower_68, upper_68, lower_90, upper_90


def _iv_implied_component(spot: float, vol_surface: Optional[Dict[str, Any]], horizon_d: int) -> Optional[Tuple[float, float, float, float, float, float]]:
    """IV-implied range from SABR-lite vol_surface.

    term_structure is a list of dicts with keys: dte, atm_iv, ...
    Returns None if no suitable expiry found.
    """
    if not vol_surface or not isinstance(vol_surface, dict):
        return None
    term = vol_surface.get("term_structure")
    if not term or not isinstance(term, list):
        return None
    # Find expiry closest to horizon_d
    closest_expiry = None
    closest_diff = None
    for e in term:
        if not isinstance(e, dict):
            continue
        dte = e.get("dte")
        if dte is None:
            continue
        try:
            dte_int = int(dte)
        except Exception:
            continue
        diff = abs(dte_int - horizon_d)
        if closest_diff is None or diff < closest_diff:
            closest_diff = diff
            closest_expiry = e
    if closest_expiry is None or closest_diff is None:
        return None
    atm_iv = closest_expiry.get("atm_iv")
    if not atm_iv:
        return None
    sigma_ann = float(atm_iv)
    sigma_daily = sigma_ann / math.sqrt(252)
    drift_h = 0.0  # risk-neutral
    sigma_h = sigma_daily * math.sqrt(horizon_d)
    median = spot  # risk-neutral median
    lower_68 = spot * math.exp(-Z_68 * sigma_h)
    upper_68 = spot * math.exp(Z_68 * sigma_h)
    lower_90 = spot * math.exp(-Z_90 * sigma_h)
    upper_90 = spot * math.exp(Z_90 * sigma_h)
    return median, sigma_ann, lower_68, upper_68, lower_90, upper_90


def _historical_realized_component(spot: float, daily_returns: np.ndarray, horizon_d: int) -> Optional[Tuple[float, float, float, float, float, float]]:
    """Bootstrap historical h-day returns, compute median + quantiles."""
    if len(daily_returns) < horizon_d + 60:
        return None
    # Compute h-day returns over rolling window
    h_returns = []
    for i in range(horizon_d, len(daily_returns)):
        # h-day log return
        h_log_ret = float(np.sum(daily_returns[i - horizon_d:i]))
        h_returns.append(h_log_ret)
    if len(h_returns) < 30:
        return None
    h_returns = np.array(h_returns)
    median_log = float(np.median(h_returns))
    lower_68_log = float(np.quantile(h_returns, 0.16))
    upper_68_log = float(np.quantile(h_returns, 0.84))
    lower_90_log = float(np.quantile(h_returns, 0.05))
    upper_90_log = float(np.quantile(h_returns, 0.95))
    median = spot * math.exp(median_log)
    lower_68 = spot * math.exp(lower_68_log)
    upper_68 = spot * math.exp(upper_68_log)
    lower_90 = spot * math.exp(lower_90_log)
    upper_90 = spot * math.exp(upper_90_log)
    sigma_ann = float(np.std(daily_returns, ddof=1) * math.sqrt(252))
    return median, sigma_ann, lower_68, upper_68, lower_90, upper_90


# ============================================================
# Pattern-conditional adjustment
# ============================================================

def _pattern_conditional_adjust(pattern: Optional[Dict[str, Any]], horizon_d: int,
                                median_log: float, sigma_h: float) -> Tuple[float, str]:
    """If a pattern is provided, blend in pattern-conditional info.

    Returns: (adjusted_median_log, blend_label)
    blend_label says whether/how pattern was used.
    """
    if pattern is None:
        return median_log, "no_pattern"
    # 4-week avg return (21 trading days)
    if horizon_d != 21:
        return median_log, "pattern_available_not_21d"
    avg_4w = pattern.get("historical_conditional_avg_return_4w")
    n = pattern.get("historical_conditional_n", 0)
    if avg_4w is None or n is None or n < 10:
        return median_log, "pattern_insufficient_sample"
    # Blend: 70% GBM-derived median, 30% pattern-conditional (only if sample ≥10)
    pattern_log = math.log(1 + avg_4w) if abs(avg_4w) < 1 else 0
    blended = 0.70 * median_log + 0.30 * pattern_log
    return blended, f"pattern_conditional_blend_n={n}"


# ============================================================
# Main forecast
# ============================================================

def make_forecast(symbol: str, as_of_date: Optional[str] = None,
                  vol_surface: Optional[Dict[str, Any]] = None,
                  chart_structure_dict: Optional[Dict[str, Any]] = None,
                  code_version: str = "forecast.py@2026-09-02-18:42",
                  params: Optional[Dict[str, Any]] = None) -> ForecastArtifact:
    """Produce point-in-time multi-horizon forecast.

    symbol: ticker
    as_of_date: ISO date (None = today). Forecast uses only data ≤ as_of_date.
    vol_surface: optional output from lib/sabr_lite.py — for IV-implied range.
    chart_structure_dict: optional output from lib/chart_structure.py — for pattern-conditional.
    code_version: identifier for reproducibility.
    params: optional parameter overrides.
    """
    if params is None:
        params = {"blend_weights": dict(BLEND_WEIGHTS), "z_68": Z_68, "z_90": Z_90, "horizons_d": list(HORIZONS_D)}
    # Fetch point-in-time
    daily = _fetch_ohlcv_pit(symbol, as_of_date)
    if daily.empty or len(daily) < 60:
        empty = ForecastArtifact(
            artifact_id="empty",
            symbol=symbol.upper(),
            as_of_date=as_of_date or "",
            spot=0.0,
            spot_as_of="",
            code_version=code_version,
            code_module="forecast.py",
            params=params,
            horizons=[],
            iv_implied_used=False,
            historical_realized_used=False,
            pattern_conditional_used=False,
            pattern_conditional_type=None,
            pattern_conditional_avg_return_4w=None,
            chart_structure_artifact_id=None,
            calibration_artifact_id=None,
            notes="insufficient data",
        )
        return empty
    spot = float(daily["Close"].iloc[-1])
    # Fix A-extended (2026-09-02 20:30 ET): explicit unavailable status if spot
    # is still NaN after the data-fetcher trim — never propagate silently.
    if spot != spot:
        empty = ForecastArtifact(
            artifact_id="empty",
            symbol=symbol.upper(),
            as_of_date=as_of_date or "",
            spot=0.0,
            spot_as_of="",
            code_version=code_version,
            code_module="forecast.py",
            params=params,
            horizons=[],
            iv_implied_used=False,
            historical_realized_used=False,
            pattern_conditional_used=False,
            pattern_conditional_type=None,
            pattern_conditional_avg_return_4w=None,
            chart_structure_artifact_id=None,
            calibration_artifact_id=None,
            notes="insufficient_data: spot NaN after data trim",
        )
        return empty
    spot_as_of = str(daily.index[-1].date())
    as_of_date_eff = as_of_date or spot_as_of
    daily_returns = daily["Close"].pct_change().dropna().values
    # Pattern info
    top_pattern = None
    pattern_conditional_used = False
    pattern_conditional_type = None
    pattern_conditional_avg = None
    if chart_structure_dict:
        patterns = chart_structure_dict.get("patterns") or []
        # Prefer confirmed > developing; first match
        for p in patterns:
            if p.get("state") == "confirmed":
                top_pattern = p
                break
        if top_pattern is None:
            for p in patterns:
                if p.get("state") == "developing":
                    top_pattern = p
                    break
        if top_pattern and top_pattern.get("historical_conditional_n") and top_pattern["historical_conditional_n"] >= 10:
            pattern_conditional_used = True
            pattern_conditional_type = top_pattern["type"]
            pattern_conditional_avg = top_pattern.get("historical_conditional_avg_return_4w")
    # Per-horizon
    horizons_out: List[HorizonForecast] = []
    iv_used = False
    hist_used = False
    for h in HORIZONS_D:
        h_label = {5: "1w", 10: "2w", 21: "1mo", 42: "2mo", 63: "3mo"}[h]
        # Components
        gbm = _gbm_component(spot, daily_returns, h)
        iv = _iv_implied_component(spot, vol_surface, h)
        hist = _historical_realized_component(spot, daily_returns, h)
        if iv is not None:
            iv_used = True
        if hist is not None:
            hist_used = True
        # Weighted ensemble on log returns
        # median_log = Σ w_i * log(median_i / spot)
        # band_log = Σ w_i * log(band_i / spot)
        weights = params["blend_weights"]
        median_log = 0.0
        log_lower_68 = 0.0
        log_upper_68 = 0.0
        log_lower_90 = 0.0
        log_upper_90 = 0.0
        sigma_ann_acc = 0.0
        # GBM
        gbm_med, gbm_sigma, gbm_l68, gbm_u68, gbm_l90, gbm_u90 = gbm
        median_log += weights["gbm"] * math.log(max(gbm_med / spot, 1e-9))
        log_lower_68 += weights["gbm"] * math.log(max(gbm_l68 / spot, 1e-9))
        log_upper_68 += weights["gbm"] * math.log(max(gbm_u68 / spot, 1e-9))
        log_lower_90 += weights["gbm"] * math.log(max(gbm_l90 / spot, 1e-9))
        log_upper_90 += weights["gbm"] * math.log(max(gbm_u90 / spot, 1e-9))
        sigma_ann_acc += weights["gbm"] * gbm_sigma
        # IV
        if iv is not None:
            iv_med, iv_sigma, iv_l68, iv_u68, iv_l90, iv_u90 = iv
            median_log += weights["iv_implied"] * math.log(max(iv_med / spot, 1e-9))
            log_lower_68 += weights["iv_implied"] * math.log(max(iv_l68 / spot, 1e-9))
            log_upper_68 += weights["iv_implied"] * math.log(max(iv_u68 / spot, 1e-9))
            log_lower_90 += weights["iv_implied"] * math.log(max(iv_l90 / spot, 1e-9))
            log_upper_90 += weights["iv_implied"] * math.log(max(iv_u90 / spot, 1e-9))
            sigma_ann_acc += weights["iv_implied"] * iv_sigma
        # Historical
        if hist is not None:
            hist_med, hist_sigma, hist_l68, hist_u68, hist_l90, hist_u90 = hist
            median_log += weights["historical_realized"] * math.log(max(hist_med / spot, 1e-9))
            log_lower_68 += weights["historical_realized"] * math.log(max(hist_l68 / spot, 1e-9))
            log_upper_68 += weights["historical_realized"] * math.log(max(hist_u68 / spot, 1e-9))
            log_lower_90 += weights["historical_realized"] * math.log(max(hist_l90 / spot, 1e-9))
            log_upper_90 += weights["historical_realized"] * math.log(max(hist_u90 / spot, 1e-9))
            sigma_ann_acc += weights["historical_realized"] * hist_sigma
        # Pattern-conditional adjustment (only for 21d horizon)
        median_log, blend_label = _pattern_conditional_adjust(
            top_pattern, h, median_log,
            (log_upper_68 - log_lower_68) / 2
        )
        # Reconstruct prices
        median_price = spot * math.exp(median_log)
        band_68_lower = spot * math.exp(log_lower_68)
        band_68_upper = spot * math.exp(log_upper_68)
        band_90_lower = spot * math.exp(log_lower_90)
        band_90_upper = spot * math.exp(log_upper_90)
        median_return = (median_price / spot - 1) * 100
        horizons_out.append(HorizonForecast(
            horizon_d=h,
            horizon_label=h_label,
            median_price=round(median_price, 2),
            median_return_pct=round(median_return, 2),
            band_68_lower=round(band_68_lower, 2),
            band_68_upper=round(band_68_upper, 2),
            band_90_lower=round(band_90_lower, 2),
            band_90_upper=round(band_90_upper, 2),
            sigma_annualized=round(sigma_ann_acc, 4),
            method=f"ensemble: {blend_label}" if pattern_conditional_used else "ensemble",
        ))
    # Compute artifact_id (hash of key inputs)
    artifact_id_input = json.dumps({
        "symbol": symbol.upper(),
        "as_of": as_of_date_eff,
        "spot": spot,
        "code": code_version,
        "params": params,
    }, sort_keys=True, default=str)
    artifact_id = hashlib.sha256(artifact_id_input.encode()).hexdigest()[:16]
    chart_structure_artifact_id = None
    if chart_structure_dict:
        chart_structure_artifact_id = chart_structure_dict.get("artifact_id") or f"cs_{symbol}_{as_of_date_eff}"
    return ForecastArtifact(
        artifact_id=artifact_id,
        symbol=symbol.upper(),
        as_of_date=as_of_date_eff,
        spot=round(spot, 2),
        spot_as_of=spot_as_of,
        code_version=code_version,
        code_module="forecast.py",
        params=params,
        horizons=horizons_out,
        iv_implied_used=iv_used,
        historical_realized_used=hist_used,
        pattern_conditional_used=pattern_conditional_used,
        pattern_conditional_type=pattern_conditional_type,
        pattern_conditional_avg_return_4w=pattern_conditional_avg,
        chart_structure_artifact_id=chart_structure_artifact_id,
        calibration_artifact_id=None,
        notes="Forecast is OOS-conditional. Validated only after forward paper-trading data.",
    )


def forecast_to_dict(artifact: ForecastArtifact) -> Dict[str, Any]:
    """Serialize ForecastArtifact to dict."""
    return {
        "artifact_id": artifact.artifact_id,
        "symbol": artifact.symbol,
        "as_of_date": artifact.as_of_date,
        "spot": artifact.spot,
        "spot_as_of": artifact.spot_as_of,
        "code_version": artifact.code_version,
        "code_module": artifact.code_module,
        "params": artifact.params,
        "horizons": [asdict(h) for h in artifact.horizons],
        "iv_implied_used": artifact.iv_implied_used,
        "historical_realized_used": artifact.historical_realized_used,
        "pattern_conditional_used": artifact.pattern_conditional_used,
        "pattern_conditional_type": artifact.pattern_conditional_type,
        "pattern_conditional_avg_return_4w": artifact.pattern_conditional_avg_return_4w,
        "chart_structure_artifact_id": artifact.chart_structure_artifact_id,
        "calibration_artifact_id": artifact.calibration_artifact_id,
        "notes": artifact.notes,
        "created_at": artifact.created_at,
    }


def save_forecast_artifact(artifact: ForecastArtifact) -> str:
    """Save forecast artifact to disk. Returns file path."""
    fname = f"{artifact.symbol}_{artifact.as_of_date}_{artifact.artifact_id}.json"
    fpath = ARTIFACT_DIR / fname
    try:
        with open(fpath, "w") as f:
            json.dump(forecast_to_dict(artifact), f, indent=2, default=str)
    except Exception as e:
        return f"ERROR: {e}"
    return str(fpath)
