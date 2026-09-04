#!/usr/bin/env python3
"""build_clawrank_features.py — Pull features per ticker for ClawRank.

Reads yfinance history + info, computes technical + volatility sub-metrics,
joins with the dashboard's existing trend/setup/label data, and emits a
JSON file consumed by clawrank.rank().

Stocks get fundamental metrics from yfinance .info. ETFs skip fundamental
metrics (set to None) and rely on Technical + Setup + Volatility + Sentiment.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

# Local imports
from clawrank import rank, load_config  # noqa: E402

TRADING_DAYS = 252
WINDOW = 20

# Same universe as dashboard
BENCHMARKS = ["SPY", "QQQ", "IWM"]
SECTOR_ETFS = ["XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"]

# --- Sector-leader candidates (per Mike's 2026-09-03 21:42 EDT directive) ---
# For each sector ETF, list 2-3 candidate mega-caps. The dashboard picks the
# highest-ClawRank-scoring candidate per sector for Table 2 ("Stock Shortlist"
# is now "Sector Leaders"). Expanding from 8 hardcoded names to 26 candidates
# so every sector is represented and the table self-selects by score.
SECTOR_LEADERS = {
    "XLK":  ["MSFT", "NVDA", "AAPL"],   # Technology
    "XLF":  ["JPM", "BAC", "GS"],       # Financials
    "XLE":  ["XOM", "CVX"],             # Energy
    "XLV":  ["LLY", "UNH", "JNJ"],      # Health Care
    "XLI":  ["CAT", "HON", "DE"],       # Industrials
    "XLY":  ["HD", "AMZN", "TSLA"],     # Consumer Disc.
    "XLP":  ["PG", "KO", "WMT"],        # Consumer Staples
    "XLC":  ["META", "GOOGL"],          # Comm Services
    "XLB":  ["LIN", "FCX"],             # Materials
    "XLRE": ["AMT", "PLD"],             # Real Estate
    "XLU":  ["NEE", "SO"],              # Utilities
}

# Flatten to (ticker, sector_etf, sector_name) tuples
STOCKS = []
SECTOR_GROUP = {
    "XLB": "Materials", "XLC": "Comm Services", "XLE": "Energy", "XLF": "Financials",
    "XLI": "Industrials", "XLK": "Technology", "XLP": "Consumer Staples",
    "XLRE": "Real Estate", "XLU": "Utilities", "XLV": "Health Care", "XLY": "Consumer Disc.",
}
for etf, candidates in SECTOR_LEADERS.items():
    sector_name = SECTOR_GROUP[etf]
    for ticker in candidates:
        STOCKS.append((ticker, etf, sector_name))

# Legacy list-of-pairs for backward-compat callers (e.g., dashboard Table 2)
# Each entry: (ticker, sector_name)
STOCKS_BY_SECTOR = [(t, sec) for (t, _etf, sec) in STOCKS]

BENCH_GROUP = {"SPY": "Broad Mkt", "QQQ": "Tech", "IWM": "Small Cap"}
ETF_SET = set(BENCHMARKS + SECTOR_ETFS)
ALL_TICKERS = BENCHMARKS + SECTOR_ETFS + [t for t, _, _ in STOCKS]


def pick_top_by_sector(clawrank_data):
    """Given a list of ClawRank rows, return one row per sector ETF — the
    highest-scoring candidate. If no candidate has a score for a sector, skip.
    Result is ordered by sector score descending (best sector first).
    """
    if not clawrank_data:
        return []
    by_ticker = {r["ticker"]: r for r in clawrank_data}
    picks = []
    for etf, candidates in SECTOR_LEADERS.items():
        ranked = [by_ticker[t] for t in candidates if t in by_ticker
                  and by_ticker[t].get("clawrank_score") is not None]
        if not ranked:
            continue
        best = max(ranked, key=lambda r: r.get("clawrank_score") or -1)
        picks.append({
            "sector_etf": etf,
            "sector_name": SECTOR_GROUP[etf],
            "ticker": best["ticker"],
            "all_candidates": [(t, by_ticker.get(t, {}).get("clawrank_score"))
                                for t in candidates if t in by_ticker],
            **best,
        })
    picks.sort(key=lambda r: -(r.get("clawrank_score") or -1))
    return picks


def fetch_history(tickers, period="6mo"):
    return yf.download(tickers=tickers, period=period, interval="1d",
                       group_by="ticker", auto_adjust=False, progress=False, threads=True)


def get_series(hist, ticker, field):
    if isinstance(hist.columns, pd.MultiIndex):
        return hist[(ticker, field)].dropna()
    return hist[field].dropna()


def rsi_14(closes: pd.Series) -> float:
    """Wilder-style RSI(14)."""
    if len(closes) < 15:
        return None
    diff = closes.diff().dropna()
    gains = diff.clip(lower=0)
    losses = (-diff).clip(lower=0)
    # Wilder smoothing via ewm alpha=1/14
    avg_gain = gains.ewm(alpha=1/14, adjust=False).mean().iloc[-1]
    avg_loss = losses.ewm(alpha=1/14, adjust=False).mean().iloc[-1]
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100 - (100 / (1 + rs)))


def max_drawdown_60d(closes: pd.Series) -> float:
    if len(closes) < 60:
        return None
    window = closes.tail(60)
    peak = window.cummax()
    dd = (window / peak - 1)
    return float(dd.min())


def trend_slope(closes: pd.Series, lookback=50) -> float:
    if len(closes) < lookback:
        return None
    recent = closes.tail(lookback).values
    x = np.arange(len(recent))
    y = recent
    slope = np.polyfit(x, y, 1)[0]
    # Normalize by mean price → slope as fraction per day
    return float(slope / np.mean(y))


def compute_features_for(ticker, hist, spy_close, info_cache, use_fundamentals=True):
    """If use_fundamentals=False, skip yfinance.info (avoids look-ahead in backtest)."""
    """Return a flat dict of ClawRank sub-metrics for one ticker."""
    closes = get_series(hist, ticker, "Close")
    highs = get_series(hist, ticker, "High")
    lows = get_series(hist, ticker, "Low")
    vols = get_series(hist, ticker, "Volume")
    if len(closes) < 50:
        return None

    spot = float(closes.iloc[-1])

    # ----- Trend (used for dashboard labels) -----
    # Priority: short-term momentum + price-vs-MA50 + 5d direction. The old
    # rule relied only on MA50 slope (10-day change in MA) which is noisy and
    # misclassified names like META (recent 5-day +3% rally but MA still
    # lagging, so old rule called it "downtrend") and QQQ (mixed signals
    # called "transitioning" when it was really range-bound).
    ma = closes.rolling(50).mean()
    ma_now = float(ma.iloc[-1]) if not pd.isna(ma.iloc[-1]) else None
    ma20 = float(closes.tail(20).mean())
    ret_5d = (closes.iloc[-1] / closes.iloc[-6] - 1) if len(closes) >= 6 else 0
    ret_20d = (closes.iloc[-1] / closes.iloc[-26] - 1) if len(closes) >= 26 else 0
    above_ma50 = ma_now is not None and spot > ma_now
    above_ma20 = spot > ma20
    # Classification logic:
    #   uptrend    — price above both MAs and short-term momentum positive
    #   downtrend  — price below both MAs and short-term momentum negative
    #   range      — price hugging MAs and momentum small in both directions
    #   transitioning — anything else (e.g., above MA50 but below MA20, or
    #                   below MA50 but recent 5d/20d momentum positive)
    if ma_now is None:
        trend = "n/a"
    elif above_ma50 and above_ma20 and ret_5d > -0.005 and ret_20d > 0:
        trend = "uptrend"
    elif not above_ma50 and not above_ma20 and ret_5d < 0.005 and ret_20d < 0:
        trend = "downtrend"
    elif abs(ret_20d) < 0.03 and abs(ret_5d) < 0.01:
        trend = "range"
    else:
        trend = "transitioning"

    ma20 = float(closes.tail(WINDOW).mean())
    ma200 = float(closes.tail(min(200, len(closes))).mean())
    hi20 = float(closes.tail(WINDOW).max())
    lo20 = float(closes.tail(WINDOW).min())
    ret_5d = float(closes.iloc[-1] / closes.iloc[-6] - 1) if len(closes) >= 6 else 0
    ret_20d = float(closes.iloc[-1] / closes.iloc[-26] - 1) if len(closes) >= 26 else 0
    if spot >= hi20 and ret_5d > 0:
        setup = "breakout"
    elif spot > ma_now and abs(spot / ma_now - 1) < 0.02:
        setup = "pullback_retest"
    elif spot > ma_now and spot > ma20 and ret_20d > 0:
        setup = "continuation"
    elif abs(spot / ma_now - 1) < 0.04:
        setup = "range_approach"
    elif spot < ma_now and ret_5d > 0:
        setup = "reversal"
    elif spot < ma_now:
        setup = "mean_reversion"
    else:
        setup = "unavailable"

    sup = float(lows.tail(WINDOW).min())
    res = float(highs.tail(WINDOW).max())
    rng_pctile = (spot - sup) / (res - sup) * 100.0 if res > sup else None
    prev = closes.shift(1)
    tr = pd.concat([(highs - lows), (highs - prev).abs(), (lows - prev).abs()], axis=1).max(axis=1)
    atr_20 = float(tr.tail(WINDOW).mean())
    atr_pct = atr_20 / spot

    # ----- Technical sub-metrics for ClawRank -----
    rs_60d = (float(closes.iloc[-1] / closes.iloc[-min(61, len(closes))] - 1)
              - float(spy_close.iloc[-1] / spy_close.iloc[-min(61, len(spy_close))] - 1)) \
        if len(closes) >= 61 and len(spy_close) >= 61 else None
    rs_20d = (float(closes.iloc[-1] / closes.iloc[-26] - 1)
              - float(spy_close.iloc[-1] / spy_close.iloc[-26] - 1)) \
        if len(closes) >= 26 and len(spy_close) >= 26 else None
    dist_50d_pct = (spot / ma_now - 1) if ma_now else None
    dist_200d_pct = (spot / ma200 - 1) if not np.isnan(ma200) else None
    rsi = rsi_14(closes)
    slope_n = trend_slope(closes)

    # ----- Volatility sub-metrics -----
    rets = closes.pct_change().dropna()
    vol_20d = float(rets.tail(WINDOW).std())
    vol_252d = float(rets.tail(min(252, len(rets))).std()) if len(rets) >= 30 else None
    vol_ratio = (vol_20d / vol_252d) if vol_252d and vol_252d > 0 else None
    spy_vol_20d = float(spy_close.pct_change().dropna().tail(WINDOW).std())
    atr_vs_spy = atr_pct - spy_vol_20d
    max_dd = max_drawdown_60d(closes)

    # ----- Setup sub-metrics (already computed) -----
    dist_to_50d_atr = ((spot - ma_now) / atr_20) if ma_now and atr_20 > 0 else None
    room_to_resist_atr = ((res - spot) / atr_20) if atr_20 > 0 else None

    # ----- Sentiment sub-metrics (liquidity + volume + analyst target) -----
    adv_usd = float((vols * closes).tail(WINDOW).mean())
    adv_usd_m = adv_usd / 1e6
    vol_5d = float(vols.tail(5).mean())
    vol_20d_mean = float(vols.tail(WINDOW).mean())
    vol_ratio_5d_20d = (vol_5d / vol_20d_mean) if vol_20d_mean > 0 else None

    # ----- Fundamentals (yfinance .info, stocks only; skipped in backtest) -----
    fund_metrics = {}
    if use_fundamentals and ticker not in ETF_SET:
        info = info_cache.get(ticker, {})
        if not info:
            try:
                info = yf.Ticker(ticker).info or {}
                info_cache[ticker] = info
            except Exception:
                info = {}
                info_cache[ticker] = info
        eps = info.get("trailingEps")
        fund_metrics["earnings_yield"] = (eps / spot) if eps and eps > 0 else None
        fund_metrics["revenue_growth"] = info.get("revenueGrowth")
        fund_metrics["operating_margin"] = info.get("operatingMargins")
        dte = info.get("debtToEquity")
        fund_metrics["debt_to_equity"] = (dte / 100.0) if dte is not None else None
        fcf = info.get("freeCashflow")
        mcap = info.get("marketCap")
        fund_metrics["fcf_yield"] = (fcf / mcap) if fcf and mcap and mcap > 0 else None
        target = info.get("targetMeanPrice")
        fund_metrics["target_upside_pct"] = ((target / spot) - 1) if target and spot > 0 else None
    # ETFs: leave fundamentals as None

    return {
        "ticker": ticker,
        "trend": trend,
        "setup": setup,
        "spot": spot,
        # Technical
        "rs_60d_vs_spy": rs_60d,
        "rs_20d_vs_spy": rs_20d,
        "dist_50d_ma_pct": dist_50d_pct,
        "dist_200d_ma_pct": dist_200d_pct,
        "rsi_14": rsi,
        "trend_slope_50d": slope_n,
        # Volatility
        "vol_20d_over_252d": vol_ratio,
        "atr_pct_minus_spy": atr_vs_spy,
        "max_dd_60d": max_dd,
        # Setup
        "range_pctile": rng_pctile,
        "dist_to_50d_atr": dist_to_50d_atr,
        "room_to_resist_atr": room_to_resist_atr,
        # Sentiment
        "adv_usd_m": adv_usd_m,
        "vol_5d_over_20d": vol_ratio_5d_20d,
        # Fundamentals (None for ETFs)
        **fund_metrics,
    }


def main():
    t0 = time.time()
    as_of_et = dt.datetime.now(dt.timezone(dt.timedelta(hours=-4)))
    cfg = load_config(str(Path(__file__).resolve().parent.parent / "config" / "clawrank.yaml"))

    print(f"Fetching {len(ALL_TICKERS)} tickers (~6mo daily) ...", file=sys.stderr)
    hist = fetch_history(ALL_TICKERS, period="6mo")
    if hist is None or len(hist) == 0:
        print("FATAL: yfinance returned no data", file=sys.stderr); sys.exit(2)

    spy_close = get_series(hist, "SPY", "Close")

    info_cache: dict = {}
    rows = []
    for t in ALL_TICKERS:
        feats = compute_features_for(t, hist, spy_close, info_cache)
        if feats is not None:
            rows.append(feats)

    # Run ClawRank
    ranked = rank(rows, cfg)

    # Build output JSON
    out = {
        "as_of": as_of_et.isoformat(),
        "universe": len(ranked),
        "factors": {name: f["weight"] for name, f in cfg["factors"].items()},
        "tickers": ranked,
    }

    out_path = Path(__file__).resolve().parent.parent / "reports" / f"{as_of_et.strftime('%Y-%m-%d')}-clawrank.json"
    out_path.write_text(json.dumps(out, indent=2, default=str))

    print(f"OK  json={out_path}  rows={len(ranked)}  duration={time.time()-t0:.1f}s", file=sys.stderr)
    print(f"\n{'Tic':<6} {'Score':<7} {'Fund':<6} {'Tech':<6} {'Vol':<6} {'Set':<6} {'Sent':<6} {'Trend':<14} {'Setup':<18} Label")
    for r in sorted(ranked, key=lambda x: -(x.get("clawrank_score") or 0)):
        print(f"{r['ticker']:<6} {r.get('clawrank_score', 0):<7.1f} "
              f"{r.get('clawrank_fundamental_health', 0):<6.1f} "
              f"{r.get('clawrank_technical_momentum', 0):<6.1f} "
              f"{r.get('clawrank_volatility_regime', 0):<6.1f} "
              f"{r.get('clawrank_setup_quality', 0):<6.1f} "
              f"{r.get('clawrank_sentiment_catalyst', 0):<6.1f} "
              f"{r.get('trend', ''):<14} "
              f"{r.get('setup', ''):<18} "
              f"{r.get('clawrank_label', '')}")


if __name__ == "__main__":
    main()
