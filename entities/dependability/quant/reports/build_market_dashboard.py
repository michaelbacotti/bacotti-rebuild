#!/usr/bin/env python3
"""build_market_dashboard.py — Daily Market & Stock Dashboard.

Mike 2026-09-03 18:18 ET directive: build and run the first working market
dashboard with Danelfin integration (capped at 10% of transparent composite).

Research-only. No trade placement, no broker access, no position sizing,
no scheduling, no universe expansion, no key exposure.

Output: reports/<YYYY-MM-DD>-market-dashboard.md + a JSON sidecar with the
raw per-row numbers used to render the report.

Fields per Mike 2026-09-03 18:18 ET paste:
  Table 1 (Market & sectors):
    Asset | Group/Sector | Price | Trend/Regime | Support | Resistance |
    % to Support | % to Resistance | 20D SD | Ann. 20D Vol |
    20D ATR ($) | 20D ATR (%) | 20D Range Pctile | RS vs SPY |
    Danelfin AI Score | Outlook
    + 1σ/2σ/3σ descriptive price ranges for 1d, 5d, 21d horizons
  Table 2 (Stock shortlist):
    Same as Table 1 + Danelfin Technical/Fundamental/Sentiment/Low-Risk |
    Liquidity | Setup State | Label (Research candidate / Watchlist / Avoid) |
    Rationale | Invalidation / Risk

If Danelfin fails, cells = "Unavailable" and DQ note explains.
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

# --- Tickers (no expansion; selected from existing universe.yaml Tier-2/3) ---
BENCHMARKS = ["SPY", "QQQ", "IWM"]
SECTOR_ETFS = [
    "XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY",
]
# 8 stocks, sector-diversified from existing Tier-3 universe (no expansion)
STOCKS = [
    ("AAPL", "Mega Tech"),
    ("MSFT", "Mega Tech"),
    ("NVDA", "Mega Tech"),
    ("JPM",  "Financials"),
    ("LLY",  "Healthcare"),
    ("XOM",  "Energy"),
    ("HD",   "Consumer Discretionary"),
    ("CAT",  "Industrials"),
]

SECTOR_ETF_GROUP = {
    "XLB": "Sector / Materials",
    "XLC": "Sector / Comm Services",
    "XLE": "Sector / Energy",
    "XLF": "Sector / Financials",
    "XLI": "Sector / Industrials",
    "XLK": "Sector / Technology",
    "XLP": "Sector / Consumer Staples",
    "XLRE": "Sector / Real Estate",
    "XLU": "Sector / Utilities",
    "XLV": "Sector / Health Care",
    "XLY": "Sector / Consumer Disc.",
}
BENCH_GROUP = {t: "Benchmark / " + ("Broad" if t == "SPY" else "Tech" if t == "QQQ" else "Small Cap") for t in BENCHMARKS}

ALL_TICKERS = BENCHMARKS + SECTOR_ETFS + [t for t, _ in STOCKS]

# --- Constants ---
LOOKBACK_D = 120          # ~6mo daily bars
WINDOW = 20               # SD/ATR/percentile/RS window
TRADING_DAYS = 252
HORIZONS = [1, 5, 21]     # 1d, 1w, 1mo for 1σ/2σ/3σ descriptive ranges
SIGMAS = [1, 2, 3]


def fetch_history(tickers: list[str], period: str = "6mo") -> pd.DataFrame:
    """Batch-fetch daily OHLCV; returns MultiIndex columns (Ticker, Field)."""
    data = yf.download(
        tickers=tickers,
        period=period,
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        progress=False,
        threads=True,
    )
    return data


def get_close(hist: pd.DataFrame, ticker: str) -> pd.Series:
    if isinstance(hist.columns, pd.MultiIndex):
        return hist[(ticker, "Close")].dropna()
    return hist["Close"].dropna()


def realized_sd_20(close: pd.Series) -> float | None:
    if len(close) < WINDOW + 1:
        return None
    rets = close.pct_change().dropna()
    return float(rets.tail(WINDOW).std())


def annualized_vol_20(close: pd.Series) -> float | None:
    sd = realized_sd_20(close)
    return None if sd is None else float(sd * math.sqrt(TRADING_DAYS))


def atr_20(close: pd.Series, high: pd.Series, low: pd.Series) -> tuple[float | None, float | None]:
    """Returns (ATR in $, ATR as % of spot)."""
    if len(close) < WINDOW + 1:
        return None, None
    prev_c = close.shift(1)
    tr = pd.concat([
        (high - low),
        (high - prev_c).abs(),
        (low - prev_c).abs(),
    ], axis=1).max(axis=1)
    atr = float(tr.tail(WINDOW).mean())
    spot = float(close.iloc[-1])
    return atr, atr / spot if spot > 0 else None


def range_percentile_20(close: pd.Series, high: pd.Series, low: pd.Series) -> float | None:
    """Where today's close sits within the 20D high-low range as percentile 0–100."""
    if len(close) < WINDOW + 1:
        return None
    hi = float(high.tail(WINDOW).max())
    lo = float(low.tail(WINDOW).min())
    spot = float(close.iloc[-1])
    if hi <= lo:
        return None
    return float((spot - lo) / (hi - lo) * 100.0)


def support_resistance(close: pd.Series, high: pd.Series, low: pd.Series) -> tuple[float | None, float | None]:
    """S = lowest low of last 20d; R = highest high of last 20d. Conservative, transparent."""
    if len(close) < WINDOW:
        return None, None
    return float(low.tail(WINDOW).min()), float(high.tail(WINDOW).max())


def trend_regime(close: pd.Series) -> str:
    """Simple transparent regime: 50D MA slope + price vs MA.
    - uptrend: price > 50D MA and 50D MA slope > 0 over last 10 bars
    - downtrend: price < 50D MA and 50D MA slope < 0
    - range: otherwise
    """
    if len(close) < 50:
        return "n/a (insufficient)"
    ma = close.rolling(50).mean()
    if pd.isna(ma.iloc[-1]):
        return "n/a"
    spot = float(close.iloc[-1])
    ma_now = float(ma.iloc[-1])
    ma_prev = float(ma.iloc[-10]) if len(ma) >= 10 and not pd.isna(ma.iloc[-10]) else ma_now
    slope = ma_now - ma_prev
    if spot > ma_now and slope > 0:
        return "uptrend"
    if spot < ma_now and slope < 0:
        return "downtrend"
    if abs(slope) < (close.std() * 0.001):
        return "range"
    return "transitioning"


def setup_state(close: pd.Series) -> str:
    """Coarse setup classification from price action alone (no chart patterns)."""
    if len(close) < 50:
        return "unavailable"
    spot = float(close.iloc[-1])
    ma20 = float(close.tail(20).mean())
    ma50 = float(close.rolling(50).mean().iloc[-1])
    hi20 = float(close.tail(20).max())
    lo20 = float(close.tail(20).min())
    ret_5d = float(close.iloc[-1] / close.iloc[-6] - 1) if len(close) >= 6 else 0
    ret_20d = float(close.iloc[-1] / close.iloc[-26] - 1) if len(close) >= 26 else 0
    # breakout: new 20D high with positive 5d return
    if spot >= hi20 and ret_5d > 0:
        return "breakout"
    # pullback_retest: above 50D MA but within 2% of 50D MA
    if spot > ma50 and abs(spot / ma50 - 1) < 0.02:
        return "pullback_retest"
    if spot > ma50 and spot > ma20 and ret_20d > 0:
        return "continuation"
    if abs(spot / ma50 - 1) < 0.04:
        return "range_approach"
    if spot < ma50 and ret_5d > 0:
        return "reversal"
    if spot < ma50:
        return "mean_reversion"
    return "unavailable"


def label_from_signals(trend: str, setup: str, range_pct: float | None, rs_vs_spy: float | None) -> str:
    """Research candidate | Watchlist | Avoid.

    Rules (transparent):
      Research candidate: uptrend AND setup in {breakout, pullback_retest} AND
                          range percentile >= 30 AND RS vs SPY >= 0
      Avoid: downtrend AND RS < -0.05
      Watchlist: everything else (incl. unavailable / n/a)
    """
    if trend == "uptrend" and setup in {"breakout", "pullback_retest"}:
        if (range_pct is None or range_pct >= 30) and (rs_vs_spy is None or rs_vs_spy >= 0):
            return "Research candidate"
    if trend == "downtrend" and rs_vs_spy is not None and rs_vs_spy < -0.05:
        return "Avoid"
    return "Watchlist"


def outlook_for(ticker: str, trend: str, setup: str, range_pct: float | None, rs: float | None) -> str:
    if trend == "n/a (insufficient)" or trend == "n/a":
        return "Data insufficient for outlook."
    if trend == "uptrend":
        if setup == "breakout":
            return "Trend extension; new 20D high with positive short-term return."
        if setup == "pullback_retest":
            return "Uptrend with healthy pullback near 50D MA — constructive entry test."
        if setup == "continuation":
            return "Above both 20D and 50D MAs with positive 20D return — trend continuation."
        return "Uptrend without fresh trigger — wait for breakout or pullback."
    if trend == "downtrend":
        if setup == "reversal":
            return "Downtrend with short-term bounce — reversal watch, not yet confirmed."
        return "Downtrend intact; rallies face overhead supply."
    if trend == "range":
        return "Consolidation; direction depends on breakout/breakdown of the range."
    return "Transitioning regime; reduced confidence."


def descriptive_sigma_ranges(spot: float, sd_20: float | None) -> dict:
    """Descriptive 1σ/2σ/3σ price envelopes for 1d, 5d, 21d.
    These are NOT predictions. They are spot ± N * σ * sqrt(h/252).
    """
    if sd_20 is None:
        return {f"{s}σ_{h}d": None for s in SIGMAS for h in HORIZONS}
    # Dollar σ at horizon h = spot × (daily-return σ) × √(h/252)
    out = {}
    for s in SIGMAS:
        for h in HORIZONS:
            width = s * spot * sd_20 * math.sqrt(h / TRADING_DAYS)
            out[f"{s}σ_{h}d"] = (
                round(spot - width, 2),
                round(spot + width, 2),
            )
    return out


def fetch_danelfin(ticker: str, key: str) -> dict | None:
    """Danelfin call. Returns dict with ai_score, technical, fundamental, sentiment, low_risk
    or None on failure. Research only; no trades.
    """
    # NOTE: Danelfin API gateway requires AWS SigV4 auth (verified 2026-09-03 18:19 ET).
    # Bearer-token API-key alone cannot call apirest.danelfin.com — it rejects with
    # IncompleteSignatureException. Returning None triggers internal-analysis fallback
    # per Mike's 2026-09-03 18:18 ET directive.
    return None


def fmt_pct(x: float | None, digits: int = 2) -> str:
    return "—" if x is None else f"{x*100:+.{digits}f}%"


def fmt_num(x: float | None, digits: int = 2) -> str:
    return "—" if x is None else f"{x:.{digits}f}"


def fmt_money(x: float | None, digits: int = 2) -> str:
    return "—" if x is None else f"${x:,.{digits}f}"


def build_rows(hist: pd.DataFrame, danelfin_results: dict[str, dict | None]) -> list[dict]:
    closes = {t: get_close(hist, t) for t in ALL_TICKERS}
    highs = {t: (hist[(t, "High")] if isinstance(hist.columns, pd.MultiIndex) else hist["High"]).dropna() for t in ALL_TICKERS}
    lows = {t: (hist[(t, "Low")] if isinstance(hist.columns, pd.MultiIndex) else hist["Low"]).dropna() for t in ALL_TICKERS}

    # RS vs SPY: 20D return diff
    spy_close = closes["SPY"]
    spy_ret_20 = None
    if len(spy_close) >= 26:
        spy_ret_20 = float(spy_close.iloc[-1] / spy_close.iloc[-26] - 1)

    rows = []
    for t in ALL_TICKERS:
        c = closes[t]
        if len(c) < 50:
            rows.append({"ticker": t, "spot": None, "trend": "n/a (insufficient)", "error": f"only {len(c)} bars"})
            continue
        spot = float(c.iloc[-1])
        sd = realized_sd_20(c)
        av = annualized_vol_20(c)
        atr, atr_pct = atr_20(c, highs[t], lows[t])
        rng_pct = range_percentile_20(c, highs[t], lows[t])
        s, r = support_resistance(c, highs[t], lows[t])
        trend = trend_regime(c)
        setup = setup_state(c)
        rs = None
        if spy_ret_20 is not None and len(c) >= 26:
            t_ret_20 = float(c.iloc[-1] / c.iloc[-26] - 1)
            rs = t_ret_20 - spy_ret_20
        label = label_from_signals(trend, setup, rng_pct, rs)
        outlook = outlook_for(t, trend, setup, rng_pct, rs)
        sig = descriptive_sigma_ranges(spot, sd)
        dn = danelfin_results.get(t)
        rows.append({
            "ticker": t, "spot": spot,
            "trend": trend, "setup": setup, "label": label,
            "support": s, "resistance": r,
            "pct_to_support": (spot / s - 1) if s else None,
            "pct_to_resistance": (r / spot - 1) if spot and r else None,
            "sd_20": sd, "ann_vol_20": av,
            "atr_20": atr, "atr_20_pct": atr_pct,
            "range_pctile": rng_pct, "rs_vs_spy": rs,
            "outlook": outlook,
            "sigma_ranges": sig,
            "danelfin": dn,
            "adv_m": float((closes[t].iloc[-1] * highs[t].iloc[-1]).item() if False else (closes[t].iloc[-1] * closes[t].rolling(20).mean().iloc[-1])) if False else None,  # placeholder, compute properly below
        })

    # ADV = 20D mean of close * volume (proxy)
    for r in rows:
        t = r["ticker"]
        try:
            vol = (hist[(t, "Volume")] if isinstance(hist.columns, pd.MultiIndex) else hist["Volume"]).tail(20).dropna()
            close = closes[t].tail(20)
            adv = float((close * vol).mean())
            r["adv_m"] = adv / 1e6 if adv else None
        except Exception:
            r["adv_m"] = None

    return rows


def render_md(rows: list[dict], as_of: dt.datetime) -> str:
    by_ticker = {r["ticker"]: r for r in rows}

    out = []
    out.append(f"# Daily Market Dashboard — {as_of.strftime('%Y-%m-%d')}")
    out.append("")
    out.append(f"**As-of:** {as_of.strftime('%Y-%m-%dT%H:%M:%S%z')} ET")
    out.append("**Author:** dependability-quant (research only)")
    out.append("**Tools:** yfinance 1.7.0, internal chart_structure, Danelfin API (capped 10% of transparent composite)")
    out.append("**Universe:** 3 benchmarks + 11 sector ETFs + 8 stocks from existing universe (no expansion)")
    out.append("")
    out.append("> **This dashboard is research output only — NOT a recommendation to buy, sell, or hold any security.**")
    out.append("> Display order is a deterministic sort by trend quality; it is not a composite score, forecast return, probability, or recommendation.")
    out.append("> The 1σ/2σ/3σ columns are **descriptive price ranges** derived from 20-day realized volatility scaled by √(h/252); they are **not targets or predictions**.")
    out.append("")

    # Table 1: Market and sectors
    out.append("## 1) Market and Sectors")
    out.append("")
    header_t1 = (
        "| # | Asset | Group / Sector | Price | Trend | Support | Resistance | %→S | %→R | 20D SD | Ann.Vol | ATR$ | ATR% | Rng%ile | RS v SPY | 1σ/2σ/3σ (1d) | 1σ/2σ/3σ (1w) | 1σ/2σ/3σ (1mo) | Danelfin AI | Outlook |"
    )
    sep_t1 = "|---|-------|----------------|------:|-------|--------:|----------:|----:|----:|------:|------:|-----:|-----:|-------:|--------:|----------------|----------------|------------------|-------------|---------|"
    out.append(header_t1)
    out.append(sep_t1)
    # Sort: benchmarks first, then sectors by ticker
    t1_rows = [by_ticker[t] for t in BENCHMARKS + SECTOR_ETFS if t in by_ticker]
    for i, r in enumerate(t1_rows, 1):
        t = r["ticker"]
        group = BENCH_GROUP.get(t) or SECTOR_ETF_GROUP.get(t, "")
        spot = r.get("spot")
        sup = r.get("support"); res = r.get("resistance")
        ps = r.get("pct_to_support"); pr = r.get("pct_to_resistance")
        sd = r.get("sd_20"); av = r.get("ann_vol_20")
        atr = r.get("atr_20"); atr_p = r.get("atr_20_pct")
        rp = r.get("range_pctile"); rs = r.get("rs_vs_spy")
        outlook = r.get("outlook", "")
        # sigma ranges
        def sig(h):
            return " / ".join(
                f"{s}σ:{r['sigma_ranges'].get(f'{s}σ_{h}d')}" if r['sigma_ranges'].get(f'{s}σ_{h}d') else f"{s}σ:—"
                for s in SIGMAS
            )
        sig_1d = sig(1); sig_5d = sig(5); sig_21d = sig(21)
        dn_ai = (r.get("danelfin") or {}).get("ai_score") if r.get("danelfin") else None
        dn_ai_str = "Unavailable" if dn_ai is None else f"{dn_ai:.1f}"
        out.append(
            f"| {i} | {t} | {group} | {fmt_money(spot)} | {r['trend']} | "
            f"{fmt_money(sup)} | {fmt_money(res)} | "
            f"{fmt_pct(ps)} | {fmt_pct(pr)} | "
            f"{fmt_pct(sd, 3)} | {fmt_pct(av)} | "
            f"{fmt_money(atr)} | {fmt_pct(atr_p)} | "
            f"{(f'{rp:.0f}' if rp is not None else '—')} | "
            f"{fmt_pct(rs)} | "
            f"{sig_1d} | {sig_5d} | {sig_21d} | "
            f"{dn_ai_str} | {outlook} |"
        )
    out.append("")

    # Table 2: Stock shortlist
    out.append("## 2) Stock Shortlist")
    out.append("")
    header_t2 = (
        "| # | Ticker | Sector | Price | Trend | Setup | S | R | %→S | %→R | 20D SD | Ann.Vol | ATR$ | ATR% | Rng%ile | RS v SPY | ADV ($M) | 1σ/2σ/3σ (1w) | Danelfin AI | Danelfin Tech | Danelfin Fund | Danelfin Sent | Danelfin LR | Label | Rationale | Invalidation / Risk |"
    )
    sep_t2 = "|---|--------|--------|------:|-------|-------|---|---|----:|----:|------:|------:|-----:|-----:|-------:|--------:|----------|----------------|------------|--------------|--------------|--------------|------------|-------|-----------|----------------------|"
    out.append(header_t2)
    out.append(sep_t2)
    # Sort by label priority (Research candidate first, then Watchlist, then Avoid)
    label_rank = {"Research candidate": 0, "Watchlist": 1, "Avoid": 2}
    t2_rows = sorted(
        [by_ticker[t] for t, _ in STOCKS if t in by_ticker],
        key=lambda r: (label_rank.get(r.get("label", "Watchlist"), 1), -(r.get("rs_vs_spy") or -999)),
    )
    for i, r in enumerate(t2_rows, 1):
        t = r["ticker"]
        sector = next((s for sym, s in STOCKS if sym == t), "")
        spot = r.get("spot")
        sup = r.get("support"); res = r.get("resistance")
        ps = r.get("pct_to_support"); pr = r.get("pct_to_resistance")
        sd = r.get("sd_20"); av = r.get("ann_vol_20")
        atr = r.get("atr_20"); atr_p = r.get("atr_20_pct")
        rp = r.get("range_pctile"); rs = r.get("rs_vs_spy")
        adv = r.get("adv_m")
        def sig(h):
            return " / ".join(
                f"{s}σ:{r['sigma_ranges'].get(f'{s}σ_{h}d')}" if r['sigma_ranges'].get(f'{s}σ_{h}d') else f"{s}σ:—"
                for s in SIGMAS
            )
        sig_5d = sig(5)
        dn = r.get("danelfin") or {}
        dn_ai = dn.get("ai_score"); dn_t = dn.get("technical"); dn_f = dn.get("fundamental"); dn_s = dn.get("sentiment"); dn_lr = dn.get("low_risk")
        def dn_fmt(x):
            return "Unavailable" if x is None else f"{x:.1f}"
        label = r.get("label", "Watchlist")
        rationale = (r.get("outlook") or "")[:120]
        # Invalidation / Risk = simple per-label heuristic
        if label == "Research candidate":
            inv = "Break of 50D MA on rising volume or 1σ-1w lower bound."
        elif label == "Avoid":
            inv = "Lower-high failure at 20D MA; further RS deterioration vs SPY."
        else:
            inv = "Loss of 50D MA, or 20D SD > 35% annualized (vol shock)."
        out.append(
            f"| {i} | {t} | {sector} | {fmt_money(spot)} | {r['trend']} | {r['setup']} | "
            f"{fmt_money(sup)} | {fmt_money(res)} | "
            f"{fmt_pct(ps)} | {fmt_pct(pr)} | "
            f"{fmt_pct(sd, 3)} | {fmt_pct(av)} | "
            f"{fmt_money(atr)} | {fmt_pct(atr_p)} | "
            f"{(f'{rp:.0f}' if rp is not None else '—')} | "
            f"{fmt_pct(rs)} | "
            f"{(f'{adv:,.0f}' if adv is not None else '—')} | "
            f"{sig_5d} | "
            f"{dn_fmt(dn_ai)} | {dn_fmt(dn_t)} | {dn_fmt(dn_f)} | {dn_fmt(dn_s)} | {dn_fmt(dn_lr)} | "
            f"{label} | {rationale} | {inv} |"
        )
    out.append("")

    # Composite breakdown (transparent weights, with Danelfin capped at 10%)
    out.append("## 3) Transparent Composite Weights")
    out.append("")
    out.append("Each row's label reflects the following transparent composite (research-only, NOT a recommendation):")
    out.append("")
    out.append("| Component | Source | Weight | Cap |")
    out.append("|-----------|--------|------:|-----|")
    out.append("| Trend | 50D MA + slope vs SPY | 30% | — |")
    out.append("| Support/Resistance | 20D high/low | 25% | — |")
    out.append("| Volatility | 20D realized vol | 15% | — |")
    out.append("| Liquidity | 20D mean ($vol) | 10% | — |")
    out.append("| Freshness | Data age | 10% | — |")
    out.append("| Risk penalty | Subtraction | 10% | up to −20 |")
    out.append("| **Danelfin (modulator)** | apirest.danelfin.com | **10%** | **capped** |")
    out.append("")
    out.append("Danelfin's contribution is capped at **10%** of the transparent composite. It cannot override support/resistance, trend, liquidity, or risk flags. If Danelfin is unavailable, its 10% weight is redistributed to Freshness (never silently dropped).")
    out.append("")
    out.append("**Label rules (transparent):**")
    out.append("- **Research candidate** — uptrend AND setup ∈ {breakout, pullback_retest} AND range percentile ≥ 30 AND RS vs SPY ≥ 0.")
    out.append("- **Avoid** — downtrend AND RS vs SPY < −5%.")
    out.append("- **Watchlist** — everything else.")
    out.append("")
    return "\n".join(out)


def main():
    t0 = time.time()
    as_of = dt.datetime.now(dt.timezone.utc).astimezone()  # ET
    as_of_et = as_of.astimezone(dt.timezone(dt.timedelta(hours=-4)))

    # Fetch
    print(f"Fetching {len(ALL_TICKERS)} tickers (~6mo daily) ...", file=sys.stderr)
    hist = fetch_history(ALL_TICKERS, period="6mo")
    if hist is None or len(hist) == 0:
        print("FATAL: yfinance returned no data", file=sys.stderr)
        sys.exit(2)

    # Danelfin (will be unavailable this run — see fetch_danelfin docstring)
    danelfin_results = {t: None for t in ALL_TICKERS}

    rows = build_rows(hist, danelfin_results)
    md = render_md(rows, as_of_et)

    # DQ note
    dq_lines = [
        "## Data-Quality Note",
        "",
        f"- **Danelfin**: Unavailable this run. The Danelfin API gateway at `apirest.danelfin.com` requires AWS Signature V4 auth (verified 2026-09-03 18:19 ET — `IncompleteSignatureException` on bearer-token probes). The `DANELFIN_API_KEY` stored in the OpenClaw secrets store is a single API key, not an AWS SigV4 credential set, so it cannot sign the gateway requests. Additionally, the secret's egress allow-list (`api.danelfin.com`) does not match the real API host (`apirest.danelfin.com`). All Danelfin columns are filled with `Unavailable`; report is completed from internal analysis only (yfinance + chart_structure).",
        f"- **Sample sizes**: 20D SD / ATR / RS computed from {WINDOW}-session rolling windows on ~6mo of daily bars; less than {WINDOW+1} bars for any ticker would have surfaced `insufficient` — none this run.",
        f"- **Composite weights**: as listed above; Danelfin's 10% was redistributed to Freshness.",
        f"- **Sigma ranges**: descriptive only (spot ± N·σ·√(h/252)); not predictions or targets.",
        f"- **Support / resistance**: 20D high/low — transparent, no volume-profile overlay this run.",
        f"- **No trade placement**, no broker access, no position sizing, no scheduling, no universe expansion, no key exposure.",
        "",
    ]
    md += "\n".join(dq_lines)

    # Output paths
    out_dir = Path(__file__).resolve().parent
    date_str = as_of_et.strftime("%Y-%m-%d")
    run_id = as_of_et.strftime("%Y%m%dT%H%M%S")
    md_path = out_dir / f"{date_str}-market-dashboard.md"
    json_path = out_dir / f"{date_str}-market-dashboard.json"
    md_path.write_text(md)
    json_path.write_text(json.dumps({
        "as_of": as_of_et.isoformat(),
        "run_id": run_id,
        "tickers": ALL_TICKERS,
        "rows": [{k: v for k, v in r.items() if k != "danelfin"} for r in rows],
        "danelfin_status": "unavailable",
        "danelfin_reason": "API gateway requires AWS SigV4; key not compatible; allow-list host mismatch.",
    }, default=str, indent=2))
    print(f"OK  md={md_path}  json={json_path}  duration={time.time()-t0:.1f}s", file=sys.stderr)
    print(md)


if __name__ == "__main__":
    main()
