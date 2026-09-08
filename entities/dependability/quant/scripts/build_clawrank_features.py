#!/usr/bin/env python3
"""build_clawrank_features.py — Pull features per ticker for ClawRank.

Reads yfinance history + info + upgrades/downgrades + earnings history,
joins with earnings_calendar, seasonality, event_signals, macro_dashboard,
and emits a JSON file consumed by clawrank.rank().

v10 (2026-09-07): 10-factor multi-horizon rebuild. New factors:
  - Valuation (PE, fwdPE, PEG, P/B, P/S, EV/EBITDA, FCF yield, earnings yield)
  - Quality+Growth (ROE, ROA, ROIC proxy, op margin, profit margin, rev/earnings growth)
  - Multi-TF returns (1M, 3M, 6M, 12M RS vs SPY; MACD)
  - Earnings Catalyst (days to next, drift, surprise, growth)
  - Analyst/Estimates (target upside, rating, coverage, revisions)
  - Volatility Regime (vol ratio, ATR vs SPY, max DD, IV percentile)
  - Setup Quality (volume profile position added)
  - Positioning (short int, days-to-cover, inst, insider, net flow)
  - Sentiment/Catalyst (event window added)
  - Macro Regime (FRED-fed regime classifier + sector fit)
  - Seasonality (month-of-year drift)

Macro regime classifier runs once (market-wide) and per-ticker sector fit is
derived from defensive/cyclical/neutral classification. Composite weights are
tilted by macro_modifiers in clawrank.yaml.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # for universe_loader

# Local imports
from clawrank import rank, load_config  # noqa: E402
from universe_loader import load_universe, get_cached_info, SECTOR_GROUP  # noqa: E402
from pathlib import Path as _Path
CACHE_DIR = _Path(__file__).resolve().parent.parent / "data" / "cache"

TRADING_DAYS = 252
WINDOW = 20

# Universe: S&P 500 + NASDAQ-100 + VTWO proxy for IWM (loaded dynamically)
BENCHMARKS = ["SPY", "QQQ", "IWM"]
SECTOR_ETFS = ["XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"]
BENCH_GROUP = {"SPY": "Broad Mkt", "QQQ": "Tech", "IWM": "Small Cap"}
ETF_SET = set(BENCHMARKS + SECTOR_ETFS)


def build_stock_universe():
    """Build STOCKS list dynamically from config/universe.json + VTWO holdings.

    Returns: list of (ticker, sector_etf, sector_name)
    """
    universe_list, sector_map, sector_groups = load_universe(verbose=True)
    # Add VTWO proxy tickers for IWM small-cap exposure
    try:
        import yfinance as yf
        vtwo = yf.Ticker('VTWO').funds_data
        if vtwo is not None:
            top = vtwo.top_holdings
            if top is not None and not top.empty:
                vtwo_tickers = [t for t in top.index.tolist() if t not in sector_map]
                for t in vtwo_tickers:
                    meta_path = CACHE_DIR / "sectors" / f"{t}.json"
                    if meta_path.exists():
                        data = json.loads(meta_path.read_text())
                        sector_map[t] = (data["sector_etf"], data["sector_name"])
                        sector_groups.setdefault(data["sector_name"], []).append(t)
                print(f"  VTWO proxy: added {len(vtwo_tickers)} small-caps", flush=True)
    except Exception as e:
        print(f"  VTWO proxy failed (non-fatal): {e}", flush=True)
    # Rebuild universe_list from final sector_map
    final = [(t, sector_map[t][0], sector_map[t][1]) for t in sorted(sector_map.keys())]
    print(f"  Total universe: {len(final)} tickers across {len(sector_groups)} sectors", flush=True)
    return final, sector_groups


# Populated at module load
STOCKS = []
SECTOR_GROUPS_DYNAMIC = {}
SECTOR_ETF_OF = {}


def init_universe():
    global STOCKS, SECTOR_GROUPS_DYNAMIC, SECTOR_ETF_OF
    STOCKS, SECTOR_GROUPS_DYNAMIC = build_stock_universe()
    SECTOR_ETF_OF = {t: etf for (t, etf, _sec) in STOCKS}


STOCKS_BY_SECTOR = []  # populated after init_universe()
ALL_TICKERS = []  # populated after init_universe()

# Sector beta classification — used for macro_sector_fit
# Defensive: rewarded in risk-off / bear-risk-elevated regimes
# Cyclical: penalized in risk-off
# Neutral: roughly market beta
SECTOR_BETA_CLASS = {
    "XLP":  "defensive",
    "XLU":  "defensive",
    "XLV":  "defensive",
    "XLRE": "defensive",
    "XLE":  "cyclical",
    "XLY":  "cyclical",
    "XLF":  "cyclical",
    "XLI":  "cyclical",
    "XLB":  "cyclical",
    "XLK":  "neutral",
    "XLC":  "neutral",
}
# Map stock ticker to its sector ETF for sector_fit (when beta not in info)
# Populated by init_universe() based on dynamic universe.
STOCK_BETA_CLASS = {}
BENCH_BETA_CLASS = {"SPY": "neutral", "QQQ": "neutral", "IWM": "cyclical"}


def pick_top_by_sector(clawrank_data, top_n=3):
    """Return top N tickers per sector (default 3), sorted by ClawRank descending.

    Uses the dynamic STOCKS universe (S&P 500 + NASDAQ-100 + VTWO proxy).
    Falls back to ALL ranked tickers if STOCKS is empty.
    """
    if not clawrank_data:
        return []
    by_ticker = {r["ticker"]: r for r in clawrank_data}

    # Group tickers by sector
    sector_tickers = {}
    if STOCKS:
        for t, etf, sec_name in STOCKS:
            sector_tickers.setdefault((etf, sec_name), []).append(t)
    else:
        # Fallback: infer sector from sector_name field on each row
        for r in clawrank_data:
            sec_name = r.get("sector_name") or "Other"
            etf = r.get("sector_etf") or ""
            sector_tickers.setdefault((etf, sec_name), []).append(r["ticker"])

    picks = []
    for (etf, sec_name), candidates in sector_tickers.items():
        ranked = [by_ticker[t] for t in candidates if t in by_ticker
                  and by_ticker[t].get("clawrank_score") is not None]
        if not ranked:
            continue
        ranked.sort(key=lambda r: -(r.get("clawrank_score") or -1))
        top = ranked[:top_n]
        for rank_idx, row in enumerate(top):
            picks.append({
                "sector_etf": etf,
                "sector_name": sec_name,
                "ticker": row["ticker"],
                "rank_in_sector": rank_idx + 1,
                "sector_candidate_count": len(ranked),
                **row,
            })
    picks.sort(key=lambda r: (-(r.get("clawrank_score") or -1), r.get("sector_name", "")))
    return picks


def fetch_history(tickers, period="2y"):
    return yf.download(tickers=tickers, period=period, interval="1d",
                       group_by="ticker", auto_adjust=False, progress=False, threads=True)


PRICE_CACHE_DIR = CACHE_DIR / "prices"
PRICE_CACHE_TTL_DAYS = 1


def fetch_history_cached(tickers, period="2y"):
    """Fetch 2y price history with per-ticker parquet cache (1-day TTL).

    On rebuilds, only tickers without a fresh cache file trigger network calls.
    Returns a multi-ticker DataFrame (concat of cached + fresh).
    """
    PRICE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    now_ts = time.time()
    ttl_secs = PRICE_CACHE_TTL_DAYS * 86400

    needed = []
    cached_frames = {}
    for t in tickers:
        cache_file = PRICE_CACHE_DIR / f"{t.upper()}_2y.parquet"
        if cache_file.exists() and (now_ts - cache_file.stat().st_mtime) < ttl_secs:
            try:
                df = pd.read_parquet(cache_file)
                if not df.empty:
                    cached_frames[t] = df
                    continue
            except Exception:
                pass
        needed.append(t)

    print(f"  price cache: {len(cached_frames)}/{len(tickers)} fresh, fetching {len(needed)}", file=sys.stderr)

    if needed:
        fresh = yf.download(tickers=needed, period=period, interval="1d",
                            group_by="ticker", auto_adjust=False, progress=False, threads=True)
        if fresh is None or len(fresh) == 0:
            fresh = pd.DataFrame()
        # Write each ticker to its own parquet
        for t in needed:
            try:
                if isinstance(fresh.columns, pd.MultiIndex):
                    if (t, "Close") in fresh.columns:
                        df = fresh[t].dropna(how="all")
                    else:
                        continue
                else:
                    df = fresh.dropna(how="all")
                if not df.empty:
                    cache_file = PRICE_CACHE_DIR / f"{t.upper()}_2y.parquet"
                    df.to_parquet(cache_file)
                    cached_frames[t] = df
            except Exception as e:
                print(f"  cache write failed for {t}: {e}", file=sys.stderr)

    if not cached_frames:
        return pd.DataFrame()

    # Concat all per-ticker frames into a multi-ticker DataFrame matching yf.download output
    cols = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
    pieces = []
    for t, df in cached_frames.items():
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[[c for c in cols if c in df.columns]].copy()
        df.columns = pd.MultiIndex.from_product([[t], df.columns])
        pieces.append(df)
    if not pieces:
        return pd.DataFrame()
    # Align by date index
    result = pd.concat(pieces, axis=1).sort_index()
    return result


def get_series(hist, ticker, field):
    if isinstance(hist.columns, pd.MultiIndex):
        return hist[(ticker, field)].dropna()
    return hist[field].dropna()


def rsi_14(closes: pd.Series) -> float:
    if len(closes) < 15:
        return None
    diff = closes.diff().dropna()
    gains = diff.clip(lower=0)
    losses = (-diff).clip(lower=0)
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
    return float(slope / np.mean(y))


def macd_histogram(closes: pd.Series) -> float:
    """MACD(12,26,9) histogram (latest bar). Positive = bullish momentum."""
    if len(closes) < 35:
        return None
    ema12 = closes.ewm(span=12, adjust=False).mean()
    ema26 = closes.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    return float(hist.iloc[-1])


def multi_tf_returns(closes: pd.Series, spy_close: pd.Series) -> dict:
    """1M/3M/6M/12M returns + RS vs SPY."""
    out = {"ret_1m": None, "ret_3m": None, "ret_6m": None, "ret_12m": None,
           "rs_1m_vs_spy": None, "rs_3m_vs_spy": None, "rs_6m_vs_spy": None, "rs_12m_vs_spy": None}
    n = len(closes)
    if n < 22:
        return out
    spy_n = len(spy_close)

    def _ret(lookback):
        if len(closes) < lookback + 1 or len(spy_close) < lookback + 1:
            return None
        return float(closes.iloc[-1] / closes.iloc[-lookback-1] - 1)
    def _rs(lookback):
        r = _ret(lookback)
        if r is None:
            return None
        spy_r = float(spy_close.iloc[-1] / spy_close.iloc[-lookback-1] - 1)
        return r - spy_r

    out["ret_1m"] = _ret(21); out["rs_1m_vs_spy"] = _rs(21)
    out["ret_3m"] = _ret(63); out["rs_3m_vs_spy"] = _rs(63)
    out["ret_6m"] = _ret(126); out["rs_6m_vs_spy"] = _rs(126)
    out["ret_12m"] = _ret(252); out["rs_12m_vs_spy"] = _rs(252)
    return out


def volume_profile_position(closes: pd.Series, vols: pd.Series, lookback=60, n_bins=20) -> float | None:
    """Where in the 60D volume profile is current price? Returns 0-1 (POC=0.5).

    POC (point of control) is the price with most volume traded.
    Returns price percentile relative to volume-weighted range.
    """
    if len(closes) < lookback or len(vols) < lookback:
        return None
    window_c = closes.tail(lookback)
    window_v = vols.tail(lookback)
    price_min = float(window_c.min())
    price_max = float(window_c.max())
    if price_max <= price_min:
        return None
    bins = np.linspace(price_min, price_max, n_bins + 1)
    vol_by_bin = np.zeros(n_bins)
    for c, v in zip(window_c.values, window_v.values):
        idx = min(int((c - price_min) / (price_max - price_min) * n_bins), n_bins - 1)
        vol_by_bin[idx] += float(v)
    poc_idx = int(np.argmax(vol_by_bin))
    poc_price = (bins[poc_idx] + bins[poc_idx + 1]) / 2
    # Position of current price relative to POC and range
    spot = float(closes.iloc[-1])
    pos = (spot - price_min) / (price_max - price_min)
    return float(pos)


def iv_percentile(symbol: str, hist: pd.DataFrame, window=252) -> float | None:
    """Realized vol percentile vs trailing year. Skip if options data unavailable."""
    # Use realized vol as IV proxy (no paid IV source). Percentile within 60d.
    closes = get_series(hist, symbol, "Close") if isinstance(hist.columns, pd.MultiIndex) else hist["Close"].dropna()
    if len(closes) < 30:
        return None
    rets = closes.pct_change().dropna()
    vol_20 = rets.rolling(20).std() * np.sqrt(252)
    if len(vol_20) < 60:
        return None
    latest = vol_20.iloc[-1]
    past = vol_20.dropna().iloc[-min(window, len(vol_20)):]
    pct = float((past < latest).sum() / len(past))
    return pct


def get_recent_revisions(symbol: str, days: int = 30) -> float | None:
    """Count of upgrades - downgrades over last N days from yfinance upgrades_downgrades.

    Returns positive if net upgrades, negative if net downgrades, magnitude is # events.
    None if data unavailable.
    """
    try:
        t = yf.Ticker(symbol)
        ud = t.upgrades_downgrades
        if ud is None or ud.empty:
            return None
        cutoff = pd.Timestamp.now(tz=None) - pd.Timedelta(days=days)
        recent = ud[ud.index >= cutoff]
        if recent.empty:
            return 0.0
        # ToGrade: 'Buy','Outperform','Hold','Sell','Underperform','Equal-Weight','Market Outperform' etc
        # Action: 'up'/'down'/'main'/'init'/'repeat'
        # Use Action column when available
        if "Action" in recent.columns:
            ups = (recent["Action"] == "up").sum()
            downs = (recent["Action"] == "down").sum()
            return float(int(ups) - int(downs))
        # Fallback: parse ToGrade
        bull_grades = {"Buy", "Strong Buy", "Outperform", "Overweight", "Market Outperform", "Sector Outperform"}
        bear_grades = {"Sell", "Strong Sell", "Underperform", "Underweight", "Market Perform"}
        ups = recent["ToGrade"].isin(bull_grades).sum()
        downs = recent["ToGrade"].isin(bear_grades).sum()
        return float(int(ups) - int(downs))
    except Exception:
        return None


def get_recent_surprise_pct(symbol: str) -> float | None:
    """Most-recent earnings surprise % (positive = beat)."""
    try:
        t = yf.Ticker(symbol)
        eh = t.earnings_history
        if eh is None or eh.empty or "surprisePercent" not in eh.columns:
            return None
        return float(eh["surprisePercent"].iloc[0])
    except Exception:
        return None


def compute_features_for(ticker, hist, spy_close, info_cache, macro_state):
    """Compute all v10 sub-metrics for one ticker. macro_state is dict from
    macro_dashboard.build_dashboard() — same for all tickers."""
    closes = get_series(hist, ticker, "Close")
    highs = get_series(hist, ticker, "High")
    lows = get_series(hist, ticker, "Low")
    vols = get_series(hist, ticker, "Volume")
    if len(closes) < 50:
        return None

    spot = float(closes.iloc[-1])

    # ----- Trend (used for dashboard labels) -----
    ma = closes.rolling(50).mean()
    ma_now = float(ma.iloc[-1]) if not pd.isna(ma.iloc[-1]) else None
    ma20 = float(closes.tail(20).mean())
    ma200 = float(closes.tail(min(200, len(closes))).mean())
    ret_5d = (closes.iloc[-1] / closes.iloc[-6] - 1) if len(closes) >= 6 else 0
    ret_20d = (closes.iloc[-1] / closes.iloc[-26] - 1) if len(closes) >= 26 else 0
    above_ma50 = ma_now is not None and spot > ma_now
    above_ma20 = spot > ma20
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

    hi20 = float(closes.tail(WINDOW).max())
    lo20 = float(closes.tail(WINDOW).min())
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

    # ----- Multi-timeframe returns + RS vs SPY -----
    mtf = multi_tf_returns(closes, spy_close)
    rs_1m, rs_3m, rs_6m, rs_12m = mtf["rs_1m_vs_spy"], mtf["rs_3m_vs_spy"], mtf["rs_6m_vs_spy"], mtf["rs_12m_vs_spy"]

    # ----- Technical (single-TF legacy fields kept for compat) -----
    rs_60d = rs_3m  # alias
    rs_20d = rs_1m
    dist_50d_pct = (spot / ma_now - 1) if ma_now else None
    dist_200d_pct = (spot / ma200 - 1) if not np.isnan(ma200) else None
    rsi = rsi_14(closes)
    slope_n = trend_slope(closes)
    macd_h = macd_histogram(closes)

    # ----- Volatility -----
    rets = closes.pct_change().dropna()
    vol_20d = float(rets.tail(WINDOW).std())
    vol_252d = float(rets.tail(min(252, len(rets))).std()) if len(rets) >= 30 else None
    vol_ratio = (vol_20d / vol_252d) if vol_252d and vol_252d > 0 else None
    spy_vol_20d = float(spy_close.pct_change().dropna().tail(WINDOW).std())
    atr_vs_spy = atr_pct - spy_vol_20d
    max_dd = max_drawdown_60d(closes)
    iv_pct = iv_percentile(ticker, hist)

    # ----- Setup -----
    dist_to_50d_atr = ((spot - ma_now) / atr_20) if ma_now and atr_20 > 0 else None
    room_to_resist_atr = ((res - spot) / atr_20) if atr_20 > 0 else None
    vol_profile_pos = volume_profile_position(closes, vols)

    # ----- Sentiment (liquidity + volume + analyst target) -----
    adv_usd = float((vols * closes).tail(WINDOW).mean())
    adv_usd_m = adv_usd / 1e6
    vol_5d = float(vols.tail(5).mean())
    vol_20d_mean = float(vols.tail(WINDOW).mean())
    vol_ratio_5d_20d = (vol_5d / vol_20d_mean) if vol_20d_mean > 0 else None

    # ----- Macro Regime (market-wide, applied per-ticker via sector_fit) -----
    macro_regime_score = float(macro_state.get("composite_score", 0.0))
    bear_risk = float(macro_state.get("bear_risk_score", 0.0))
    regime_confidence = float(macro_state.get("confidence", 0.5))
    regime_name = macro_state.get("regime", "n/a")
    # Per-ticker sector fit: positive when ticker is defensive in risk-off, negative when cyclical in risk-off
    if ticker in SECTOR_BETA_CLASS:
        beta_class = SECTOR_BETA_CLASS[ticker]
    elif ticker in STOCK_BETA_CLASS:
        beta_class = STOCK_BETA_CLASS[ticker]
    elif ticker in BENCH_BETA_CLASS:
        beta_class = BENCH_BETA_CLASS[ticker]
    else:
        beta_class = "neutral"
    # bear_risk ranges 0..1 (higher = worse). composite_score ranges ~-1..+1.
    # Defensive stocks rewarded when bear_risk is high (negative score multiplier flipped).
    # macro_sector_fit: +1 = perfect fit for current regime, -1 = worst fit.
    if beta_class == "defensive":
        sector_fit = float(bear_risk) - 0.5  # -0.5..+0.5; high bear_risk → positive
    elif beta_class == "cyclical":
        sector_fit = 0.5 - float(bear_risk)  # -0.5..+0.5; high bear_risk → negative
    else:
        sector_fit = 0.0
    credit_stress = float(macro_state.get("pillars", {}).get("D", {}).get("score", 0.0))
    # Negative credit pillar score = stress. Map to positive stress value.
    credit_stress_val = max(0.0, -credit_stress) if credit_stress is not None else None

    # ----- Fundamentals + Estimates (yfinance .info, stocks only) -----
    fund_metrics = {}
    estimate_metrics = {}
    if ticker not in ETF_SET:
        # Use cached .info() (7-day TTL) — avoids 1-3s yfinance call per ticker on rebuilds
        info = info_cache.get(ticker) if isinstance(info_cache, dict) and info_cache.get(ticker) else None
        if not info:
            try:
                info = get_cached_info(ticker, ttl_days=7)
                if isinstance(info_cache, dict):
                    info_cache[ticker] = info
            except Exception:
                info = {}
                if isinstance(info_cache, dict):
                    info_cache[ticker] = info
        # Valuation
        pe = info.get("trailingPE")
        fund_metrics["trailing_pe"] = float(pe) if pe is not None and pe > 0 else None
        fpe = info.get("forwardPE")
        fund_metrics["forward_pe"] = float(fpe) if fpe is not None and fpe > 0 else None
        peg = info.get("pegRatio")
        fund_metrics["peg_ratio"] = float(peg) if peg is not None and peg > 0 else None
        pb = info.get("priceToBook")
        fund_metrics["price_to_book"] = float(pb) if pb is not None and pb > 0 else None
        ps = info.get("priceToSalesTrailing12Months")
        fund_metrics["price_to_sales"] = float(ps) if ps is not None and ps > 0 else None
        ev_eb = info.get("enterpriseToEbitda")
        fund_metrics["ev_to_ebitda"] = float(ev_eb) if ev_eb is not None and ev_eb > 0 else None
        # Quality + Growth
        roe = info.get("returnOnEquity")
        fund_metrics["roe"] = float(roe) if roe is not None else None
        roa = info.get("returnOnAssets")
        fund_metrics["roa"] = float(roa) if roa is not None else None
        fund_metrics["return_on_assets"] = fund_metrics["roa"]
        op_m = info.get("operatingMargins")
        fund_metrics["operating_margin"] = float(op_m) if op_m is not None else None
        p_m = info.get("profitMargins")
        fund_metrics["profit_margin"] = float(p_m) if p_m is not None else None
        rev_g = info.get("revenueGrowth")
        fund_metrics["revenue_growth"] = float(rev_g) if rev_g is not None else None
        earn_g = info.get("earningsGrowth")
        fund_metrics["earnings_growth"] = float(earn_g) if earn_g is not None else None
        dte = info.get("debtToEquity")
        fund_metrics["debt_to_equity"] = (dte / 100.0) if dte is not None else None
        # Cash conversion proxy: operating cash flow / net income (if available)
        ocf = info.get("operatingCashflow")
        ni = info.get("netIncomeToCommon")
        if ocf is not None and ni is not None and ni > 0:
            fund_metrics["cash_conversion"] = float(ocf / ni)
        else:
            fund_metrics["cash_conversion"] = None
        # Earnings yield + FCF yield
        eps = info.get("trailingEps")
        fund_metrics["earnings_yield"] = (eps / spot) if eps and eps > 0 else None
        fcf = info.get("freeCashflow")
        mcap = info.get("marketCap")
        fcf_yield_val = (fcf / mcap) if fcf and mcap and mcap > 0 else None
        fund_metrics["fcf_yield"] = fcf_yield_val
        fund_metrics["fcf_yield_q"] = fcf_yield_val
        # Analyst / Estimates
        target = info.get("targetMeanPrice")
        estimate_metrics["target_upside_pct"] = ((target / spot) - 1) if target and spot > 0 else None
        rating = info.get("recommendationMean")
        estimate_metrics["analyst_rating"] = float(rating) if rating is not None else None
        coverage = info.get("numberOfAnalystOpinions")
        estimate_metrics["analyst_coverage"] = int(coverage) if coverage is not None else None
        # Recent revisions (last 30d) — requires separate yfinance call
        estimate_metrics["recent_revisions"] = get_recent_revisions(ticker)
        # Recent earnings surprise %
        estimate_metrics["recent_surprise_pct"] = get_recent_surprise_pct(ticker)
    else:
        # ETFs: skip fundamentals + estimates
        for k in ["trailing_pe","forward_pe","peg_ratio","price_to_book","price_to_sales",
                  "ev_to_ebitda","roe","roa","return_on_assets","operating_margin","profit_margin",
                  "revenue_growth","earnings_growth","debt_to_equity","cash_conversion",
                  "earnings_yield","fcf_yield","fcf_yield_q"]:
            fund_metrics[k] = None
        for k in ["target_upside_pct","analyst_rating","analyst_coverage","recent_revisions","recent_surprise_pct"]:
            estimate_metrics[k] = None

    # ----- Earnings Catalyst (per ticker, via earnings_calendar.fetch_event) -----
    days_to_earn = None
    try:
        from earnings_calendar import fetch_event
        ev = fetch_event(ticker)
        if ev is not None and ev.date is not None:
            days_to_earn = (ev.date - dt.date.today()).days
    except Exception:
        days_to_earn = None

    # ----- Seasonality (per ticker) -----
    month_drift_val = None
    earn_window_drift_val = None
    try:
        from seasonality import month_of_year_drift, earnings_window_drift
        # month_of_year_drift returns dict keyed by 'by_year_month' + 'by_month_of_year'
        mod = month_of_year_drift(ticker, lookback_years=3)
        if mod:
            current_month = dt.date.today().month
            month_labels = {1:'jan',2:'feb',3:'mar',4:'apr',5:'may',6:'jun',
                            7:'jul',8:'aug',9:'sep',10:'oct',11:'nov',12:'dec'}
            target = month_labels.get(current_month)
            by_month = mod.get("by_month_of_year", {})
            if isinstance(by_month, dict) and target in by_month:
                # avg_monthly_return / median_monthly_return keys
                month_drift_val = float(by_month[target].get("avg_monthly_return", 0))
        ewd = earnings_window_drift(ticker, days=5)
        if ewd:
            earn_window_drift_val = float(ewd.get("avg_cumulative_return", 0))
    except Exception:
        pass

    # ----- Net flow signal (price vs 20d volume trend) -----
    net_flow = None
    try:
        recent_vols = vols.tail(20)
        if len(recent_vols) >= 20:
            # Heuristic: above-avg volume + positive return → inflow
            avg_v = float(recent_vols.tail(10).mean())
            base_v = float(recent_vols.tail(20).mean())
            v_ratio = avg_v / base_v if base_v > 0 else 1.0
            ret_5d_local = ret_5d
            net_flow = float(ret_5d_local * v_ratio * 100)  # scaled
    except Exception:
        pass

    # ----- Event window score (proximity to earnings + macro events) -----
    event_window_score = None
    if days_to_earn is not None:
        if 0 <= days_to_earn <= 7:
            event_window_score = 100.0
        elif 8 <= days_to_earn <= 21:
            event_window_score = 70.0
        elif days_to_earn < 0:
            event_window_score = 80.0  # post-earnings momentum window
        else:
            event_window_score = 30.0

    return {
        "ticker": ticker,
        "trend": trend,
        "setup": setup,
        "spot": spot,
        # Technical (multi-TF + legacy)
        "rs_1m_vs_spy": rs_1m, "rs_3m_vs_spy": rs_3m, "rs_6m_vs_spy": rs_6m, "rs_12m_vs_spy": rs_12m,
        "rs_60d_vs_spy": rs_60d, "rs_20d_vs_spy": rs_20d,
        "dist_50d_ma_pct": dist_50d_pct, "dist_200d_ma_pct": dist_200d_pct,
        "rsi_14": rsi, "trend_slope_50d": slope_n, "macd_histogram": macd_h,
        # Volatility
        "vol_20d_over_252d": vol_ratio, "atr_pct_minus_spy": atr_vs_spy,
        "max_dd_60d": max_dd, "iv_percentile": iv_pct,
        # Setup
        "range_pctile": rng_pctile, "dist_to_50d_atr": dist_to_50d_atr,
        "room_to_resist_atr": room_to_resist_atr, "volume_profile_pos": vol_profile_pos,
        # Sentiment (liquidity / volume)
        "adv_usd_m": adv_usd_m, "vol_5d_over_20d": vol_ratio_5d_20d,
        "net_flow_signal": net_flow,
        # Event signals populated later in main() via event_signals_for()
        "news_count_7d": None, "news_sentiment_avg": None,
        "short_interest_change_pct": None, "short_interest_pct_float": None,
        "institutional_pct": None, "insider_pct": None,
        "stocktwits_bullish_pct": None, "stocktwits_bearish_pct": None,
        "stocktwits_n": None,
        "days_to_cover": None,
        "event_window_score": event_window_score,
        # Earnings catalyst
        "days_to_next_earnings": days_to_earn,
        "earnings_window_drift": earn_window_drift_val,
        # Macro Regime (same for all tickers, but feeds factor)
        "macro_regime_score": macro_regime_score,
        "bear_risk_score": bear_risk,
        "regime_confidence": regime_confidence,
        "macro_sector_fit": sector_fit,
        "credit_stress": credit_stress_val,
        "macro_regime_name": regime_name,
        "macro_beta_class": beta_class,
        # Seasonality
        "month_of_year_drift": month_drift_val,
        # Fundamentals (None for ETFs)
        **fund_metrics,
        # Estimates
        **estimate_metrics,
    }


def apply_macro_modifiers(cfg: dict, macro_state: dict) -> dict:
    """Adjust factor weights by current macro regime. Returns modified cfg copy."""
    import copy
    cfg2 = copy.deepcopy(cfg)
    regime = macro_state.get("regime", "n/a")
    bear = float(macro_state.get("bear_risk_score", 0.0))
    # Defensive regime: bear_risk > 0.4 OR regime in {bear_risk_elevated, risk_off, fragile_risk_on}
    is_defensive = (bear >= 0.4) or regime in ("bear_risk_elevated", "risk_off", "fragile_risk_on")
    is_offensive = (bear <= 0.15) and regime == "risk_on"
    modifiers = cfg.get("composite", {}).get("macro_modifiers", {})
    if is_defensive and "defensive" in modifiers:
        tilt = modifiers["defensive"].get("tilt", {})
        for fname, delta in tilt.items():
            if fname in cfg2.get("factors", {}):
                cfg2["factors"][fname]["weight"] = round(cfg2["factors"][fname]["weight"] + delta, 4)
    if is_offensive and "offensive" in modifiers:
        tilt = modifiers["offensive"].get("tilt", {})
        for fname, delta in tilt.items():
            if fname in cfg2.get("factors", {}):
                cfg2["factors"][fname]["weight"] = round(cfg2["factors"][fname]["weight"] + delta, 4)
    return cfg2


def main():
    t0 = time.time()
    as_of_et = dt.datetime.now(dt.timezone(dt.timedelta(hours=-4)))
    cfg = load_config(str(Path(__file__).resolve().parent.parent / "config" / "clawrank.yaml"))

    # ----- Macro Regime (run once, market-wide) -----
    print("Building macro dashboard (FRED CSV) ...", file=sys.stderr)
    try:
        from macro_dashboard import build_dashboard as build_macro
        macro_state = build_macro()
        print(f"  regime={macro_state.get('regime')}  bear_risk={macro_state.get('bear_risk_score'):.2f}  composite={macro_state.get('composite_score'):.3f}", file=sys.stderr)
    except Exception as e:
        print(f"  macro_dashboard failed: {e}; using neutral defaults", file=sys.stderr)
        macro_state = {"regime": "n/a", "composite_score": 0.0, "bear_risk_score": 0.0,
                       "confidence": 0.5, "pillars": {}}

    # Apply macro modifiers to config weights
    cfg = apply_macro_modifiers(cfg, macro_state)

    # ----- Initialize universe (S&P 500 + NASDAQ-100 + VTWO proxy) -----
    init_universe()
    global STOCKS_BY_SECTOR, ALL_TICKERS
    STOCKS_BY_SECTOR = [(t, sec) for (t, _etf, sec) in STOCKS]
    ALL_TICKERS = BENCHMARKS + SECTOR_ETFS + [t for t, _, _ in STOCKS]
    print(f"Universe ready: {len(STOCKS)} stocks + {len(BENCHMARKS)} benchmarks + {len(SECTOR_ETFS)} sector ETFs = {len(ALL_TICKERS)} total", file=sys.stderr)

    # Populate STOCK_BETA_CLASS from dynamic universe
    global STOCK_BETA_CLASS
    STOCK_BETA_CLASS = {t: SECTOR_BETA_CLASS.get(etf, "neutral") for (t, etf, _sec) in STOCKS}

    # ----- Fetch price history (2y for 12M returns + 200D MA) — cached -----
    print(f"Fetching {len(ALL_TICKERS)} tickers (~2y daily) ...", file=sys.stderr)
    hist = fetch_history_cached(ALL_TICKERS, period="2y")
    if hist is None or len(hist) == 0:
        print("FATAL: yfinance returned no data", file=sys.stderr); sys.exit(2)

    spy_close = get_series(hist, "SPY", "Close")

    rows = []
    # Build ticker -> (sector_etf, sector_name) lookup from STOCKS
    ticker_sector = {t: (etf, sec_name) for (t, etf, sec_name) in STOCKS}
    # ETFs map themselves
    for etf in SECTOR_ETFS:
        ticker_sector[etf] = (etf, SECTOR_GROUP.get(etf, ""))
    for b in BENCHMARKS:
        ticker_sector[b] = (b, BENCH_GROUP.get(b, ""))

    for t in ALL_TICKERS:
        feats = compute_features_for(t, hist, spy_close, {}, macro_state)
        if feats is not None:
            etf, sec_name = ticker_sector.get(t, ("", "Other"))
            feats["sector_etf"] = etf
            feats["sector_name"] = sec_name
            rows.append(feats)

    # ----- Event / positioning / social signals -----
    print(f"Fetching event signals for {len(rows)} tickers ...", file=sys.stderr)
    from event_signals import event_signals_for
    by_ticker = {r["ticker"]: r for r in rows}
    for t in list(by_ticker.keys()):
        try:
            sig = event_signals_for(t, quiet=True)
            for k, v in sig.items():
                if k in ("ticker", "as_of"):
                    continue
                if k in by_ticker[t]:
                    by_ticker[t][k] = v
            # days_to_cover from short_interest
            try:
                from data_fetcher import short_interest
                si = short_interest(t)
                if si:
                    by_ticker[t]["days_to_cover"] = si.get("days_to_cover")
            except Exception:
                pass
        except Exception as e:
            print(f"  event_signals failed for {t}: {e}", file=sys.stderr)

    # ----- Run ClawRank -----
    ranked = rank(rows, cfg)

    # Build output JSON
    out = {
        "as_of": as_of_et.isoformat(),
        "universe": len(ranked),
        "factors": {name: f["weight"] for name, f in cfg["factors"].items()},
        "macro": {
            "regime": macro_state.get("regime"),
            "composite_score": macro_state.get("composite_score"),
            "bear_risk_score": macro_state.get("bear_risk_score"),
            "bear_risk_level": macro_state.get("bear_risk_level"),
            "confidence": macro_state.get("confidence"),
        },
        "tickers": ranked,
    }

    out_path = Path(__file__).resolve().parent.parent / "reports" / f"{as_of_et.strftime('%Y-%m-%d')}-clawrank.json"
    out_path.write_text(json.dumps(out, indent=2, default=str))

    print(f"OK  json={out_path}  rows={len(ranked)}  duration={time.time()-t0:.1f}s", file=sys.stderr)
    # Compact summary
    print(f"\n{'Tic':<6} {'Score':<6} {'Val':<5} {'QG':<5} {'TM':<5} {'EC':<5} {'AE':<5} {'VR':<5} {'SQ':<5} {'Pos':<5} {'SeC':<5} {'MR':<5} {'Sn':<5} {'Trend':<14} {'Setup':<18} Label")
    for r in sorted(ranked, key=lambda x: -(x.get("clawrank_score") or 0)):
        print(f"{r['ticker']:<6} {r.get('clawrank_score', 0):<6.1f} "
              f"{r.get('clawrank_valuation', 0):<5.1f} "
              f"{r.get('clawrank_quality_growth', 0):<5.1f} "
              f"{r.get('clawrank_technical_momentum', 0):<5.1f} "
              f"{r.get('clawrank_earnings_catalyst', 0):<5.1f} "
              f"{r.get('clawrank_analyst_estimates', 0):<5.1f} "
              f"{r.get('clawrank_volatility_regime', 0):<5.1f} "
              f"{r.get('clawrank_setup_quality', 0):<5.1f} "
              f"{r.get('clawrank_positioning', 0):<5.1f} "
              f"{r.get('clawrank_sentiment_catalyst', 0):<5.1f} "
              f"{r.get('clawrank_macro_regime', 0):<5.1f} "
              f"{r.get('clawrank_seasonality', 0):<5.1f} "
              f"{r.get('trend', ''):<14} "
              f"{r.get('setup', ''):<18} "
              f"{r.get('clawrank_label', '')}")


if __name__ == "__main__":
    main()
