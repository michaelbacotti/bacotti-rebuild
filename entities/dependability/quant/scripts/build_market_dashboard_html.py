#!/usr/bin/env python3
"""build_market_dashboard_html.py — Interactive single-file HTML market dashboard.

v10 (2026-09-07): 10-factor multi-horizon ClawRank (P/E, fwdPE, valuation, quality, earnings, macro, seasonality).
Event-aware Sentiment/Catalyst (news + institutional + social). Single canonical
URL (`market-dashboard.html`) plus dated archive (`YYYY-MM-DD-market-dashboard.html`).
v3 (2026-09-03): ClawRank score moved to first column. Hover the score to see
the 5-factor breakdown (Fund / Tech / Vol / Setup / Sent) + label rule that
fired. Eliminates 5 redundant factor columns from the Stock Shortlist.
Adds an SVG favicon embedded as data URI (gold "C" on dark rounded square).

Visual language aligned with bacotti-dashboard.html (GitHub-Dark + gold).
Research only — no trade placement, no broker access, no key exposure.
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
import yaml
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_clawrank_features import (  # noqa: E402
    fetch_history, get_series, compute_features_for, ALL_TICKERS, ETF_SET,
    BENCHMARKS, SECTOR_ETFS, STOCKS, SECTOR_GROUP, BENCH_GROUP,
    pick_top_by_sector,
)
from clawrank import rank, load_config  # noqa: E402

WINDOW = 20
TRADING_DAYS = 252
# Bump on every shipped dashboard methodology change.
# Surfaced in <title>, <h1>, and HTTP cache header. Last 5 versions in wiki.
BUILD_VERSION = "v15"

PAL = {
    "bg":     "#0d1117", "surface":  "#161b22", "surface2": "#21262d",
    "border": "#30363d", "text":     "#e6edf3", "muted":    "#7d8590",
    "gold":      "#d4a843", "gold_dim":  "rgba(212,168,67,0.18)", "gold_glow": "rgba(212,168,67,0.08)",
    "green":     "#3fb950", "red":       "#f85149", "yellow":    "#d29922",
    "blue":      "#58a6ff", "purple":    "#a371f7", "pink":      "#ff7b72",
    "t_up":   "#3fb950", "t_down": "#f85149", "t_range": "#d29922", "t_trans": "#a371f7",
    "lbl_rc": "#58a6ff", "lbl_wl": "#d29922", "lbl_av": "#f85149",
}


def fetch_history(tickers, period="6mo"):
    return yf.download(tickers=tickers, period=period, interval="1d",
                       group_by="ticker", auto_adjust=False, progress=False, threads=True)


def compute_metrics(closes, highs, lows, vols, spy_close, ticker):
    c = closes[ticker]
    if len(c) < 50:
        return None
    spot = float(c.iloc[-1])
    rets = c.pct_change().dropna()
    sd_20 = float(rets.tail(WINDOW).std())
    av = sd_20 * math.sqrt(TRADING_DAYS)
    prev = c.shift(1)
    tr = pd.concat([(highs[ticker] - lows[ticker]),
                    (highs[ticker] - prev).abs(),
                    (lows[ticker] - prev).abs()], axis=1).max(axis=1)
    atr_20 = float(tr.tail(WINDOW).mean())
    sup = float(lows[ticker].tail(WINDOW).min())
    res = float(highs[ticker].tail(WINDOW).max())
    rng_pct = (spot - sup) / (res - sup) * 100.0 if res > sup else None
    ma = c.rolling(50).mean()
    ma_now = float(ma.iloc[-1]) if not pd.isna(ma.iloc[-1]) else None
    ma_prev = float(ma.iloc[-10]) if len(ma) >= 10 and not pd.isna(ma.iloc[-10]) else ma_now
    # Compute the 20-day return and 5-day return for the new trend logic
    ma20 = float(c.tail(20).mean())
    ret_5d = float(c.iloc[-1] / c.iloc[-6] - 1) if len(c) >= 6 else 0
    ret_20d = float(c.iloc[-1] / c.iloc[-26] - 1) if len(c) >= 26 else 0
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
    ma20 = float(c.tail(WINDOW).mean())
    hi20 = float(c.tail(WINDOW).max())
    lo20 = float(c.tail(WINDOW).min())
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
    rs = None
    if len(spy_close) >= 26 and len(c) >= 26:
        rs = float(c.iloc[-1] / c.iloc[-26] - 1) - float(spy_close.iloc[-1] / spy_close.iloc[-26] - 1)
    if trend == "uptrend" and setup in {"breakout", "pullback_retest"}:
        if (rng_pct is None or rng_pct >= 30) and (rs is None or rs >= 0):
            label = "Research candidate"
        else:
            label = "Watchlist"
    elif trend == "downtrend" and rs is not None and rs < -0.05:
        label = "Avoid"
    else:
        label = "Watchlist"
    adv_usd = float((vols[ticker] * c).tail(WINDOW).mean())
    return {
        "ticker": ticker, "spot": spot, "sd_20": sd_20, "ann_vol": av,
        "atr_20": atr_20, "support": sup, "resistance": res,
        "range_pctile": rng_pct, "rs_vs_spy": rs,
        "trend": trend, "setup": setup, "label": label,
        "ma50": ma_now, "ma20": ma20,
        "ret_5d": ret_5d, "ret_20d": ret_20d,
        "adv_usd": adv_usd,
    }


def regime_for(m):
    """Compute market regime label for benchmarks (SPY/QQQ/IWM).

    Mike 2026-09-07 17:42 ET: decouple benchmark scoring — benchmarks get a
    regime label, not a percentile score.

    Logic (transparent, debuggable):
      - risk-on:    uptrend AND above 50D MA AND 20D return > 0
      - risk-off:   downtrend AND below 50D MA AND 20D return < 0
      - neutral:    everything else (transitioning, mixed signals)

    Inputs are the same fields the trend classifier uses, so the regime
    label is consistent with the trend pill in the dashboard.
    """
    trend = m.get("trend", "n/a")
    spot = m.get("spot")
    ma50 = m.get("ma50")
    ret_20d = m.get("ret_20d")
    if trend == "n/a" or spot is None or ma50 is None or ret_20d is None:
        return "neutral"
    above_ma = spot > ma50
    if trend == "uptrend" and above_ma and ret_20d > 0:
        return "risk-on"
    if trend == "downtrend" and not above_ma and ret_20d < 0:
        return "risk-off"
    return "neutral"


REGIME_STYLE = {
    "risk-on":  ("Rc", "#3fb950", "Trending up; above 50D MA; positive 20D return"),
    "neutral":  ("Wa", "#d29922", "Mixed signals — between risk-on and risk-off"),
    "risk-off": ("Av", "#f85149", "Trending down; below 50D MA; negative 20D return"),
}


def regime_cell_with_popover(regime, m):
    """Render a regime cell for a benchmark (replaces score cell).

    No ClawRank score; just a regime label with the underlying metrics as
    a hover popover so the determination is transparent.
    """
    short_class, color, desc = REGIME_STYLE.get(regime, REGIME_STYLE["neutral"])
    spot = m.get("spot")
    ma50 = m.get("ma50")
    ret_5d = m.get("ret_5d")
    ret_20d = m.get("ret_20d")
    above_ma = (spot > ma50) if (spot is not None and ma50 is not None) else None
    popover = (
        '<div class="popover">'
        '<div class="popover-title">Benchmark Regime</div>'
        f'<div class="popover-row sub"><span class="name">Trend</span><span class="val">{m.get("trend", "—")}</span></div>'
        f'<div class="popover-row sub"><span class="name">Above 50D MA</span><span class="val">{"yes" if above_ma else "no" if above_ma is not None else "—"}</span></div>'
        f'<div class="popover-row sub"><span class="name">20D return</span><span class="val">{(f"{ret_20d:+.2%}") if ret_20d is not None else "—"}</span></div>'
        f'<div class="popover-row sub"><span class="name">5D return</span><span class="val">{(f"{ret_5d:+.2%}") if ret_5d is not None else "—"}</span></div>'
        '<div class="popover-divider"></div>'
        f'<div class="popover-rule">{desc} → <strong>{regime}</strong></div>'
        '<span class="popover-trigger-hint">benchmarks are not scored</span>'
        '</div>'
    )
    return (
        f'<td class="score-cell" data-val="0">'
        f'<span class="score-big" style="color:{color};font-size:14px">{regime}</span>'
        f'{popover}'
        f'</td>'
    )


def outlook_for(m):
    t, s = m["trend"], m["setup"]
    if t == "n/a": return "Data insufficient."
    if t == "uptrend":
        if s == "breakout": return "Trend extension; new 20D high"
        if s == "pullback_retest": return "Uptrend w/ healthy pullback near 50D"
        if s == "continuation": return "Above 20D & 50D MAs"
        return "Uptrend — no fresh trigger"
    if t == "downtrend":
        if s == "reversal": return "Downtrend w/ short-term bounce"
        return "Downtrend — rallies face supply"
    if t == "range": return "Consolidation awaiting breakout"
    return "Transitioning regime"


def sparkline_svg(closes: pd.Series, sd_20, spot, width=180, height=46):
    series = closes.tail(60).reset_index(drop=True)
    if len(series) < 2 or sd_20 is None or sd_20 <= 0:
        return f'<svg width="{width}" height="{height}"></svg>'
    vals = series.values
    lo, hi = float(vals.min()), float(vals.max())
    pad = (hi - lo) * 0.18 if hi > lo else 0.01
    lo, hi = lo - pad, hi + pad
    n = len(vals); step = width / (n - 1)
    def x(i): return i * step
    def y(v): return height - ((v - lo) / (hi - lo)) * (height - 4) - 2
    bands = [(spot - k * spot * sd_20, spot + k * spot * sd_20) for k in (3, 2, 1)]
    band_colors = [f"{PAL['red']}22", f"{PAL['yellow']}33", f"{PAL['blue']}44"]
    band_x0 = width * 0.6
    parts = [f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" style="display:block">']
    for (b_lo, b_hi), color in zip(bands, band_colors):
        if b_hi < lo or b_lo > hi:
            continue
        y_lo = max(0, min(height, y(b_lo)))
        y_hi = max(0, min(height, y(b_hi)))
        parts.append(
            f'<rect x="{band_x0:.1f}" y="{y_lo:.1f}" width="{width-band_x0:.1f}" '
            f'height="{(y_hi - y_lo):.1f}" fill="{color}"/>'
        )
    pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vals))
    parts.append(f'<polyline fill="none" stroke="{PAL["gold"]}" stroke-width="1.4" points="{pts}"/>')
    parts.append(f'<line x1="{band_x0:.1f}" y1="0" x2="{band_x0:.1f}" y2="{height}" '
                 f'stroke="{PAL["border"]}" stroke-dasharray="2,2" stroke-width="0.8"/>')
    parts.append(f'<circle cx="{width-2:.1f}" cy="{y(spot):.1f}" r="3" fill="{PAL["gold"]}" '
                 f'stroke="{PAL["bg"]}" stroke-width="1"/>')
    parts.append('</svg>')
    return "".join(parts)


def trend_badge(t):
    color = {"uptrend": PAL["t_up"], "downtrend": PAL["t_down"],
             "range": PAL["t_range"], "transitioning": PAL["t_trans"],
             "n/a": PAL["muted"]}.get(t, PAL["muted"])
    return f'<span class="trend-pill" style="background:{color}22;color:{color};border:1px solid {color}55">{t}</span>'


def fmt_money(x, d=2): return "—" if x is None else f"${x:,.{d}f}"
def fmt_pct(x, d=2): return "—" if x is None else f"{x*100:+.{d}f}%"
def fmt_pct_pos(x, d=2): return "—" if x is None else f"{x*100:.{d}f}%"
def fmt_adv(x): return "—" if x is None else f"${x/1e6:,.0f}M"


CSS = f"""
:root {{
  --bg: {PAL['bg']}; --surface: {PAL['surface']}; --surface2: {PAL['surface2']};
  --border: {PAL['border']}; --text: {PAL['text']}; --muted: {PAL['muted']};
  --gold: {PAL['gold']}; --gold-dim: {PAL['gold_dim']};
  --green: {PAL['green']}; --red: {PAL['red']}; --yellow: {PAL['yellow']};
  --blue: {PAL['blue']}; --purple: {PAL['purple']};
}}
* {{ box-sizing: border-box; }}
body {{ font: 13px/1.45 -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, sans-serif;
       background: var(--bg); color: var(--text); min-height: 100vh; line-height: 1.5; margin: 0; }}
header {{ background: linear-gradient(135deg, #1a1510 0%, #161b22 100%);
          border-bottom: 1px solid rgba(212,168,67,0.3); padding: 18px 24px;
          display: flex; align-items: center; justify-content: space-between; }}
.header-left h1 {{ font-size: 20px; font-weight: 700; color: var(--gold); letter-spacing: -0.3px; margin: 0; }}
.header-left .subtitle {{ font-size: 11px; color: var(--muted); margin-top: 2px; }}
.header-right {{ display: flex; align-items: center; gap: 16px; }}
.header-badge {{ background: rgba(212,168,67,0.12); border: 1px solid rgba(212,168,67,0.4);
                 border-radius: 20px; padding: 4px 12px; font-size: 10px; color: var(--gold);
                 letter-spacing: 0.5px; font-weight: 600; }}
.header-badge.live {{ background: rgba(63,185,80,0.12); border-color: rgba(63,185,80,0.4); color: var(--green); }}
.last-updated {{ font-size: 10px; color: var(--muted); }}
.regime-banner {{ background: rgba(88,166,255,0.10); color: var(--blue); padding: 10px 24px;
                  font-size: 11.5px; border-bottom: 1px solid rgba(88,166,255,0.25);
                  font-family: var(--mono); }}
.regime-banner strong {{ color: var(--text); margin-right: 4px; }}
.popover-subhead {{ font-size: 10px; color: var(--gold); margin-top: 6px;
                    margin-bottom: 2px; letter-spacing: 0.05em; text-transform: uppercase; }}
.popover-row.sub {{ font-size: 10px; color: var(--muted); }}
.popover-row.sub .name {{ font-weight: 400; }}
.disclaimer {{ background: rgba(210,153,34,0.10); color: var(--yellow); padding: 10px 24px;
              font-size: 11.5px; border-bottom: 1px solid rgba(210,153,34,0.25); }}
.disclaimer strong {{ color: var(--text); }}
main {{ padding: 16px 24px; max-width: 1700px; margin: 0 auto; }}
.card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
         overflow: visible; margin-bottom: 14px; }}
.card-header {{ overflow: hidden; }}
.card-header {{ padding: 10px 14px; border-bottom: 1px solid var(--border);
               display: flex; align-items: center; gap: 8px; font-size: 10px;
               font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.8px; }}
.card-header .dot {{ width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }}
.card-body {{ padding: 4px 0; }}
.controls {{ display: flex; gap: 6px; flex-wrap: wrap; padding: 10px 14px;
            border-bottom: 1px solid var(--border); background: rgba(33,38,45,0.4); }}
.chip {{ padding: 4px 10px; border: 1px solid var(--border); border-radius: 20px;
        background: var(--surface2); color: var(--muted); cursor: pointer; font-size: 11px;
        user-select: none; transition: all 0.15s; font-weight: 600; }}
.chip:hover {{ border-color: var(--gold); color: var(--text); }}
.chip.active {{ background: var(--gold-dim); border-color: var(--gold); color: var(--gold); }}
table {{ width: 100%; border-collapse: collapse; font-size: 11.5px; font-variant-numeric: tabular-nums; }}
th, td {{ padding: 7px 12px; text-align: right; border-bottom: 1px solid rgba(48,54,61,0.5);
         white-space: nowrap; }}
th {{ background: var(--surface); font-weight: 700; color: var(--muted);
     cursor: pointer; user-select: none; font-size: 9.5px; text-transform: uppercase; letter-spacing: 0.6px;
     position: sticky; top: 0; }}
th:first-child, td:first-child, th:nth-child(2), td:nth-child(2) {{ text-align: left; }}
th.sortable:hover {{ color: var(--gold); }}
th.sorted-asc::after {{ content: ' ▲'; color: var(--gold); }}
th.sorted-desc::after {{ content: ' ▼'; color: var(--gold); }}
tr:hover {{ background: rgba(212,168,67,0.04); }}
.ticker-cell {{ font-weight: 700; color: var(--gold); letter-spacing: 0.3px; }}
.trend-pill {{ display: inline-block; padding: 2px 8px; border-radius: 10px;
               font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.4px; }}
.label-Rc {{ color: var(--blue); font-weight: 700; }}
.label-Wa {{ color: var(--yellow); font-weight: 600; }}
.label-Av {{ color: var(--red); font-weight: 700; }}
.spark-cell {{ padding: 4px 8px; width: 184px; }}
.factor-bar {{ display: inline-block; width: 56px; height: 8px; background: var(--surface2);
               border-radius: 4px; position: relative; vertical-align: middle; }}
.factor-bar-fill {{ position: absolute; top: 0; left: 0; height: 100%; border-radius: 4px; }}
.factor-bar-text {{ margin-left: 6px; font-size: 10px; color: var(--muted); }}
.score-cell {{ position: relative; padding: 4px 10px; cursor: help; }}
.score-cell:hover {{ background: rgba(212,168,67,0.10); }}
.score-cell:hover .popover {{ display: block; }}
.score-big {{ font-size: 15px; font-weight: 700; color: var(--gold); }}
.score-label-pill {{ display: block; font-size: 9px; color: var(--muted);
                     text-transform: uppercase; letter-spacing: 0.4px;
                     margin-top: 1px; }}
.score-label-pill.Rc {{ color: var(--blue); }}
.score-label-pill.Wa {{ color: var(--yellow); }}
.score-label-pill.Av {{ color: var(--red); }}
.popover {{ position: absolute; top: calc(100% + 4px); left: 0;
            z-index: 1000; background: var(--surface2); border: 1px solid var(--gold);
            border-radius: 8px; padding: 12px 14px; min-width: 280px;
            display: none; box-shadow: 0 8px 24px rgba(0,0,0,0.5);
            text-align: left; font-size: 11px; color: var(--text); }}
.popover-title {{ font-size: 9px; font-weight: 700; color: var(--gold);
                  text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 8px; }}
.popover-row {{ display: grid; grid-template-columns: 130px 70px 30px;
                align-items: center; gap: 8px; padding: 3px 0;
                font-size: 10.5px; }}
.popover-row .name {{ color: var(--muted); }}
.popover-row .bar {{ width: 70px; height: 6px; background: #0d1117; border-radius: 3px;
                     position: relative; }}
.popover-row .bar-fill {{ position: absolute; top: 0; left: 0; height: 100%;
                          border-radius: 3px; }}
.popover-row .val {{ color: var(--text); font-weight: 600; text-align: right;
                     font-variant-numeric: tabular-nums; }}
.popover-divider {{ height: 1px; background: var(--border); margin: 8px 0; }}
.popover-rule {{ font-size: 10.5px; color: var(--text); font-style: italic; }}
.popover-rule strong {{ color: var(--gold); font-style: normal; }}
.popover-trigger-hint {{ display: block; font-size: 8.5px; color: var(--muted);
                          margin-top: 4px; text-align: center; opacity: 0.6; }}
.score-sub {{ font-size: 9px; color: var(--muted); }}
.unav {{ color: var(--muted); font-style: italic; }}
.pos {{ color: var(--green); }}
.neg {{ color: var(--red); }}

/* Watchlist (Section 2.5) — Mike 2026-09-07 21:03 ET: renamed from "Options Watchlist".
   Mike 2026-09-07 21:44 ET: Ticker col 1, ClawScore col 2 — same as T1/T2.
   Columns: Ticker | ClawScore | Spot | Ref | Target | Move% | Prob | Timing | Risk line | 3mo | Trigger | If risk breaks */
.watchlist-table th, .watchlist-table td {{ font-variant-numeric: tabular-nums; }}
.trigger-cell {{ font-size: 11px; color: var(--text); line-height: 1.4;
                 white-space: normal; word-wrap: break-word; }}
.watchlist-table th:nth-child(1), .watchlist-table td:nth-child(1) {{ text-align: left; width: 60px; }}
.watchlist-table th:nth-child(2), .watchlist-table td:nth-child(2) {{ text-align: center; width: 75px; }}
.watchlist-table th:nth-child(3), .watchlist-table td:nth-child(3) {{ text-align: right; width: 100px; }}
.watchlist-table th:nth-child(4), .watchlist-table td:nth-child(4) {{ text-align: right; width: 70px; }}
.watchlist-table th:nth-child(5), .watchlist-table td:nth-child(5) {{ text-align: right; width: 95px; }}
.watchlist-table th:nth-child(6), .watchlist-table td:nth-child(6) {{ text-align: right; width: 75px; }}
.watchlist-table th:nth-child(7), .watchlist-table td:nth-child(7) {{ text-align: center; width: 60px; }}
.watchlist-table th:nth-child(8), .watchlist-table td:nth-child(8) {{ text-align: left; width: 130px; font-size: 10.5px; white-space: normal; }}
.watchlist-table th:nth-child(9), .watchlist-table td:nth-child(9) {{ text-align: right; width: 100px; }}
.watchlist-table th:nth-child(10), .watchlist-table td:nth-child(10) {{ text-align: right; width: 110px; padding: 4px 8px; }}
.watchlist-table th:nth-child(11), .watchlist-table td:nth-child(11) {{ text-align: left; max-width: 280px; }}
.watchlist-table th:nth-child(12), .watchlist-table td:nth-child(12) {{ text-align: left; max-width: 220px; }}
/* Probability badge — proper pill */
.prob-badge {{ display: inline-block; min-width: 36px; padding: 2px 8px;
               border-radius: 10px; font-size: 11px; font-weight: 700;
               text-align: center; }}
.prob-badge.prob-good {{ background: rgba(63,185,80,0.15); color: var(--green); }}
.prob-badge.prob-mid  {{ background: rgba(210,153,34,0.15); color: var(--yellow); }}
.prob-badge.prob-low  {{ background: rgba(248,81,73,0.15); color: var(--red); }}
/* ClawRank label inside badge cell — small text under the pill */
.cr-label {{ display: block; font-size: 9px; color: var(--muted); margin-top: 2px; line-height: 1.2; }}
/* Risk line sub-text color when safe (>3% above) */
.risk-safe {{ color: var(--green); font-size: 10px; font-weight: 600; }}
.prob-good {{ color: var(--green); font-weight: 700; }}
.prob-mid  {{ color: var(--yellow); font-weight: 700; }}
.prob-low  {{ color: var(--red); font-weight: 700; }}
.risk-near {{ color: var(--yellow); font-weight: 600; }}
.risk-broken {{ color: var(--red); font-weight: 700; background: rgba(248,81,73,0.08); }}
.dq {{ background: rgba(248,81,73,0.06); border: 1px solid rgba(248,81,73,0.25);
      border-radius: 8px; padding: 12px 16px; font-size: 11.5px; color: var(--text); margin-top: 14px; }}
.dq h3 {{ margin: 0 0 8px 0; font-size: 11px; font-weight: 700; color: var(--red);
         text-transform: uppercase; letter-spacing: 0.6px; }}
.dq code {{ background: var(--surface2); padding: 1px 6px; border-radius: 3px;
           color: var(--gold); font-size: 10.5px; }}
.composite {{ font-size: 11px; color: var(--muted); padding: 10px 14px;
              border-top: 1px solid var(--border); background: rgba(33,38,45,0.4); }}
.composite strong {{ color: var(--text); }}
.composite .badge-gold {{ background: var(--gold-dim); color: var(--gold);
                          padding: 1px 6px; border-radius: 4px; font-weight: 600; }}
.kpi-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 8px; padding: 14px; border-bottom: 1px solid var(--border); background: rgba(13,17,23,0.5); }}
.kpi {{ background: var(--surface2); border: 1px solid var(--border); border-radius: 8px;
        padding: 10px 12px; }}
.kpi-label {{ font-size: 9px; color: var(--muted); text-transform: uppercase;
              letter-spacing: 0.6px; margin-bottom: 4px; font-weight: 700; }}
.kpi-value {{ font-size: 16px; font-weight: 700; color: var(--text); }}
.kpi-sub {{ font-size: 9px; color: var(--muted); margin-top: 2px; }}
.kpi.gold .kpi-value {{ color: var(--gold); }}
.kpi.green .kpi-value {{ color: var(--green); }}
.kpi.red .kpi-value {{ color: var(--red); }}
.kpi.blue .kpi-value {{ color: var(--blue); }}
footer {{ max-width: 1700px; margin: 0 auto; padding: 14px 24px 20px;
          display: flex; justify-content: space-between; align-items: center; }}
.footer-text {{ font-size: 10px; color: var(--muted); }}
.footer-text span {{ color: var(--gold); }}
.legend-row {{ display: flex; gap: 14px; padding: 8px 14px; font-size: 10px;
               color: var(--muted); background: var(--surface2); border-top: 1px solid var(--border); flex-wrap: wrap; }}
.legend-row .swatch {{ display: inline-block; width: 10px; height: 10px; border-radius: 2px;
                       margin-right: 4px; vertical-align: middle; }}
.glossary-link {{ color: var(--gold); text-decoration: none; border-bottom: 1px dotted var(--gold); }}
.glossary-link:hover {{ color: var(--text); border-bottom-color: var(--text); }}
.header-glossary-link {{ color: inherit; text-decoration: none; border-bottom: 1px dotted var(--border);
                         display: inline-block; }}
.header-glossary-link:hover {{ color: var(--gold); border-bottom-color: var(--gold); }}
.glossary {{ background: var(--surface); border: 1px solid var(--border);
             border-radius: 10px; padding: 24px 28px; margin: 28px auto; max-width: 1400px; }}
.glossary h2 {{ color: var(--gold); font-size: 18px; margin: 0 0 4px 0; font-weight: 600; }}
.glossary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
                  gap: 18px; margin-top: 18px; }}
.glossary-entry {{ background: var(--surface2); border: 1px solid var(--border);
                   border-radius: 8px; padding: 14px 16px; scroll-margin-top: 20px; }}
.glossary-entry h3 {{ color: var(--gold); font-size: 13px; margin: 0 0 8px 0;
                      border-bottom: 1px solid var(--border); padding-bottom: 6px; }}
.glossary-entry p {{ font-size: 11.5px; line-height: 1.55; color: var(--text); margin: 6px 0; }}
.glossary-entry ul {{ font-size: 11.5px; line-height: 1.55; color: var(--text); margin: 6px 0; padding-left: 18px; }}
.glossary-entry code {{ background: #0d1117; color: var(--green); padding: 1px 5px;
                         border-radius: 3px; font-size: 10.5px; }}
.glossary-entry em {{ color: var(--muted); font-style: italic; }}
.back-link {{ display: inline-block; color: var(--muted); font-size: 11px;
              margin-right: 6px; text-decoration: none; }}
.back-link:hover {{ color: var(--gold); }}
.glossary-entry:target {{ border-color: var(--gold); background: rgba(212, 168, 67, 0.05); }}
"""

JS = """
function sortTable(tableId, colIdx, type) {
  const tbl = document.getElementById(tableId);
  const tbody = tbl.querySelector('tbody');
  const rows = Array.from(tbody.querySelectorAll('tr'));
  const ths = tbl.querySelectorAll('th');
  const cur = ths[colIdx];
  const asc = !cur.classList.contains('sorted-asc');
  ths.forEach(th => th.classList.remove('sorted-asc', 'sorted-desc'));
  cur.classList.add(asc ? 'sorted-asc' : 'sorted-desc');
  rows.sort((a, b) => {
    let av = a.children[colIdx].dataset.val;
    let bv = b.children[colIdx].dataset.val;
    if (av === undefined || av === '') av = a.children[colIdx].textContent.trim();
    if (bv === undefined || bv === '') bv = b.children[colIdx].textContent.trim();
    if (type === 'num') {
      av = parseFloat(av); bv = parseFloat(bv);
      if (isNaN(av)) av = asc ? 1e18 : -1e18;
      if (isNaN(bv)) bv = asc ? 1e18 : -1e18;
      return asc ? av - bv : bv - av;
    }
    return asc ? String(av).localeCompare(String(bv))
               : String(bv).localeCompare(String(av));
  });
  rows.forEach(r => tbody.appendChild(r));
}
document.addEventListener('DOMContentLoaded', () => {
  // --- Chip filter groups (trend / label) ---
  document.querySelectorAll('.chip-group').forEach(group => {
    const tableId = group.dataset.table;
    const col = parseInt(group.dataset.col);
    let active = [];
    group.querySelectorAll('.chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const val = chip.dataset.val;
        if (val === '') {
          active = [];
          group.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
          chip.classList.add('active');
        } else {
          group.querySelector('.chip[data-val=""]').classList.remove('active');
          if (chip.classList.toggle('active')) active.push(val);
          else active = active.filter(a => a !== val);
        }
        const tbl = document.getElementById(tableId);
        tbl.querySelectorAll('tbody tr').forEach(r => {
          const v = r.children[col].textContent.trim();
          r.style.display = (!active.length || active.includes(v)) ? '' : 'none';
        });
      });
    });
  });

  // --- Viewport-aware popover positioning ---
  // .card has overflow:visible so popovers can escape; CSS anchors them
  // by default to the LEFT. We add flip classes when the cell is near the
  // right edge (anchor right) or bottom edge (anchor above).
  function positionPopover(pop) {
    const cell = pop.closest('.score-cell');
    if (!cell) return;
    const rect = cell.getBoundingClientRect();
    const vw = window.innerWidth, vh = window.innerHeight;
    // First measure (popover must be visible for accurate size)
    pop.style.left = '0px';
    pop.style.top = '0px';
    pop.style.visibility = 'hidden';
    pop.style.display = 'block';
    const pw = pop.offsetWidth, ph = pop.offsetHeight;
    pop.style.visibility = '';
    // Horizontal: prefer to anchor at cell.left; flip right if it would overflow
    let left = rect.left;
    if (left + pw > vw - 8) {
      // Anchor right edge of popover to right edge of cell
      left = rect.right - pw;
      if (left < 8) left = 8;  // also clamp
    }
    // Vertical: prefer below; flip above if it would overflow bottom
    let top = rect.bottom + 6;
    if (top + ph > vh - 8) {
      top = rect.top - ph - 6;
      if (top < 8) top = 8;
    }
    pop.style.position = 'fixed';
    pop.style.left = left + 'px';
    pop.style.top = top + 'px';
  }
  let activePop = null;
  document.querySelectorAll('.score-cell').forEach(cell => {
    const pop = cell.querySelector('.popover');
    if (!pop) return;
    let hideTimer = null;
    cell.addEventListener('mouseenter', () => {
      if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
      if (activePop && activePop !== pop) activePop.style.display = 'none';
      positionPopover(pop);
      activePop = pop;
    });
    cell.addEventListener('mouseleave', () => {
      hideTimer = setTimeout(() => {
        pop.style.display = 'none';
        if (activePop === pop) activePop = null;
      }, 120);
    });
    pop.addEventListener('mouseenter', () => {
      if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
    });
    pop.addEventListener('mouseleave', () => {
      hideTimer = setTimeout(() => {
        pop.style.display = 'none';
        if (activePop === pop) activePop = null;
      }, 120);
    });
  });
  // Reposition on scroll/resize
  window.addEventListener('scroll', () => { if (activePop) positionPopover(activePop); }, true);
  window.addEventListener('resize', () => { if (activePop) positionPopover(activePop); });
});
"""


def factor_bar(value, max_val=100.0, height=8, width=56):
    """Render a horizontal factor-bar with score."""
    if value is None:
        return '<span class="unav">—</span>'
    pct = max(0, min(100, (value / max_val) * 100))
    color = PAL["gold"] if pct >= 70 else (PAL["blue"] if pct >= 40 else (PAL["yellow"] if pct >= 20 else PAL["red"]))
    return (
        f'<span class="factor-bar"><span class="factor-bar-fill" '
        f'style="width:{pct:.0f}%;background:{color};"></span></span>'
        f'<span class="factor-bar-text">{value:.0f}</span>'
    )


# SVG favicon embedded as data URI.
# Gold serif "C" on dark rounded square — matches the dashboard's gold/dark theme.
# Slight inner glow on the C from a vertical gradient.
FAVICON_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>"
    "<defs>"
    "<linearGradient id='bg' x1='0' y1='0' x2='0' y2='1'>"
    "<stop offset='0' stop-color='#161b22'/>"
    "<stop offset='1' stop-color='#0d1117'/>"
    "</linearGradient>"
    "<linearGradient id='cg' x1='0' y1='0' x2='0' y2='1'>"
    "<stop offset='0' stop-color='#e6c25a'/>"
    "<stop offset='1' stop-color='#b88f33'/>"
    "</linearGradient>"
    "</defs>"
    "<rect width='64' height='64' rx='12' fill='url(#bg)' stroke='#d4a843' stroke-width='1.5'/>"
    "<path d='M 50 22 Q 38 10 24 16 Q 8 22 8 34 Q 8 46 22 50 Q 38 54 50 42' "
    "stroke='url(#cg)' stroke-width='7' fill='none' stroke-linecap='round'/>"
    "<circle cx='50' cy='22' r='3.5' fill='#3fb950'/>"
    "</svg>"
)
import urllib.parse as _up
FAVICON_HREF = "data:image/svg+xml;utf8," + _up.quote(FAVICON_SVG)


def score_cell_with_popover(score, label, factors, trend, setup, kr=None):
    """First-column cell: score + hover-popover with 10 factor bars + label rule."""
    if score is None:
        return '<td class="score-cell" data-val="-1"><span class="unav">—</span></td>'
    # Determine label pill style + class
    short = "Wa"
    if label == "Research candidate": short = "Rc"
    elif label == "Avoid": short = "Av"
    elif label == "Watchlist": short = "Wa"
    # Build factor rows (10 of them in v10 — multi-horizon)
    f_rows = []
    factor_defs = [
        ("Valuation",            factors.get("valuation"), 12),
        ("Quality + Growth",     factors.get("quality_growth"), 12),
        ("Technical Momentum",   factors.get("technical_momentum"), 11),
        ("Earnings Catalyst",    factors.get("earnings_catalyst"), 10),
        ("Analyst / Estimates",  factors.get("analyst_estimates"), 8),
        ("Volatility Regime",    factors.get("volatility_regime"), 8),
        ("Setup Quality",        factors.get("setup_quality"), 10),
        ("Positioning",          factors.get("positioning"), 10),
        ("Sentiment / Catalyst", factors.get("sentiment_catalyst"), 10),
        ("Macro Regime",         factors.get("macro_regime"), 9),
        ("Seasonality",          factors.get("seasonality"), 5),
    ]
    # Event/positioning/social sub-factors (Mike 2026-09-07 directive)
    sub_event_rows = []
    if kr:
        nc = kr.get("news_count_7d")
        ns = kr.get("news_sentiment_avg")
        si = kr.get("short_interest_change_pct")
        ip = kr.get("institutional_pct")
        st_b = kr.get("stocktwits_bullish_pct")
        if nc is not None or ns is not None or si is not None or ip is not None or st_b is not None:
            sub_event_rows.append('<div class="popover-subhead">Event signals</div>')
        def ev(name, val, fmt="{:.2f}"):
            if val is None:
                txt = "—"
            else:
                txt = fmt.format(val)
            return f'<div class="popover-row sub"><span class="name">{name}</span><span class="val">{txt}</span></div>'
        if nc is not None:
            sub_event_rows.append(ev("News (7d count)", nc, "{:d}"))
        if ns is not None:
            sub_event_rows.append(ev("News sentiment", ns, "{:+.2f}"))
        if si is not None:
            sub_event_rows.append(ev("Short interest ΔMoM", si, "{:+.1%}"))
        if ip is not None:
            sub_event_rows.append(ev("Institutional %", ip, "{:.1%}"))
        if st_b is not None:
            sub_event_rows.append(ev("Stocktwits bullish %", st_b, "{:.1%}"))
    for name, val, weight in factor_defs:
        if val is None:
            f_rows.append(
                f'<div class="popover-row"><span class="name">{name}</span>'
                f'<span class="bar"></span><span class="val">—</span></div>'
            )
            continue
        pct = max(0, min(100, val))
        color = PAL["gold"] if pct >= 70 else (PAL["blue"] if pct >= 40 else (PAL["yellow"] if pct >= 20 else PAL["red"]))
        f_rows.append(
            f'<div class="popover-row"><span class="name">{name} <span style="color:var(--muted);font-size:9px">({weight}%)</span></span>'
            f'<span class="bar"><span class="bar-fill" style="width:{pct:.0f}%;background:{color};"></span></span>'
            f'<span class="val">{val:.0f}</span></div>'
        )
    # Label rule explanation
    if label == "Research candidate":
        rule = f'<strong>Score {score:.0f}</strong> ≥ 70 &nbsp;+&nbsp; trend = {trend} &nbsp;+&nbsp; setup = {setup.replace("_", " ")} &nbsp;→&nbsp; Research candidate'
    elif label == "Avoid":
        rule = f'<strong>Score {score:.0f}</strong> ≤ 30 &nbsp;+&nbsp; trend = {trend} &nbsp;→&nbsp; Avoid'
    else:
        rule = f'<strong>Score {score:.0f}</strong> &nbsp;+&nbsp; trend = {trend} &nbsp;→&nbsp; Watchlist'
    popover_html = (
        '<div class="popover">'
        '<div class="popover-title">ClawRank Breakdown</div>'
        + "".join(f_rows) +
        '<div class="popover-divider"></div>'
        + "".join(sub_event_rows) +
        f'<div class="popover-rule">{rule}</div>'
        '<span class="popover-trigger-hint">hover any score to inspect factors</span>'
        '</div>'
    )
    return (
        f'<td class="score-cell" data-val="{score:.2f}">'
        f'<span class="score-big">{score:.0f}</span>'
        f'<span class="score-label-pill {short}">{label}</span>'
        f'{popover_html}'
        f'</td>'
    )


def render_options_watchlist(watchlist_data, clawrank_by_ticker):
    """Render Section 2.5 — Watchlist (tactical trade candidates).

    Mike 2026-09-07 20:43 ET: a curated set of tactical trade picks with
    target price, probability, timing window, and risk line. Originally
    scoped to long-call butterflies; renamed "Watchlist" on 21:03 ET per Mike
    since the same list can carry cash-secured puts, verticals, etc.

    Columns (Mike 2026-09-07 21:44 ET: Ticker col 1, ClawScore col 2 — consistent with T1/T2):
        Ticker | ClawScore | Spot | Ref | Target | Move% | Prob | Timing | Risk line | 3mo | Trigger | If risk breaks

    Color coding:
        - Spot vs ref: green if spot <= ref (room to run), red if spot > ref (chasing)
        - Prob: green >=50%, yellow 35-50%, red <35%
        - Risk line proximity: red if spot within 3% of risk_line (in danger)
    """
    if not watchlist_data or not watchlist_data.get("tickers"):
        return ""

    live_prices = watchlist_data.get("live_prices", {})
    sparklines = watchlist_data.get("sparklines", {})
    tickers = watchlist_data["tickers"]

    rows_html = []
    for t in tickers:
        sym = t["ticker"]
        spot = live_prices.get(sym)
        ref = t["ref_price"]
        target = t["target"]
        prob = t["probability"]
        move_pct = t["move_pct"]
        timing = t["timing"]
        trigger = t["trigger"]
        risk_line = t["risk_line"]
        risk_meaning = t["risk_meaning"]

        # Spot vs ref delta (where current price sits relative to the analysis reference)
        if spot is not None and ref is not None:
            spot_vs_ref = ((spot / ref) - 1.0) * 100
            spot_vs_ref_class = "pos" if spot_vs_ref <= 0 else "neg"
            spot_text = f"${spot:,.2f}"
            # Suppress noisy "0.0%" rounding artifacts
            spot_vs_ref_disp = 0.0 if abs(spot_vs_ref) < 0.05 else spot_vs_ref
            spot_vs_ref_text = f"{spot_vs_ref_disp:+.1f}% vs ref"
        else:
            spot_text = "—"
            spot_vs_ref_text = "no live data"
            spot_vs_ref_class = ""

        # Distance from spot to target (% upside remaining)
        if spot is not None and target is not None:
            upside_num = ((target / spot) - 1.0) * 100
            upside_text = f"+{upside_num:.1f}%"
            upside_class = "pos" if upside_num > 0 else "neg"
        else:
            upside_num = move_pct
            upside_text = f"+{move_pct:.1f}%"  # fall back to ref-based move_pct
            upside_class = ""

        # Probability color coding (badge variant — v12)
        if prob >= 50:
            prob_class, prob_badge = "prob-good", f"{prob}%"
        elif prob >= 35:
            prob_class, prob_badge = "prob-mid", f"{prob}%"
        else:
            prob_class, prob_badge = "prob-low", f"{prob}%"

        # Risk line proximity
        risk_proximity_class = ""
        risk_proximity_text = ""
        risk_proximity_label_class = ""
        if spot is not None and risk_line is not None:
            risk_dist = ((spot / risk_line) - 1.0) * 100
            if risk_dist < 3:
                risk_proximity_class = "risk-near"
                risk_proximity_label_class = "risk-near"
                risk_proximity_text = f"⚠ +{risk_dist:.1f}% above risk"
            elif risk_dist < 0:
                risk_proximity_class = "risk-broken"
                risk_proximity_label_class = "risk-broken"
                risk_proximity_text = f"❌ BROKEN {risk_dist:+.1f}%"
            else:
                risk_proximity_label_class = "risk-safe"
                risk_proximity_text = f"✓ +{risk_dist:.1f}% above risk"

        # Sparkline (3mo)
        spark = ""
        if sym in sparklines:
            closes = sparklines[sym]
            if closes is not None and len(closes) >= 5:
                spark = sparkline_svg(closes, closes.std() / closes.mean() if closes.mean() else 0.02, spot or ref)

        # ClawRank score (always available now — v12 scores watchlist tickers too)
        cr_score = clawrank_by_ticker.get(sym, {}).get("clawrank_score")
        cr_label = clawrank_by_ticker.get(sym, {}).get("clawrank_label", "")
        cr_trend = clawrank_by_ticker.get(sym, {}).get("trend") or "n/a"
        cr_setup = clawrank_by_ticker.get(sym, {}).get("setup") or "n/a"
        if cr_score is not None:
            # Build factors dict from clawrank_by_ticker (rank() emits per-factor 0-100 scores)
            factors = {k.replace("clawrank_", ""): clawrank_by_ticker[sym].get(k) for k in (
                "clawrank_valuation", "clawrank_quality_growth",
                "clawrank_technical_momentum", "clawrank_earnings_catalyst",
                "clawrank_analyst_estimates", "clawrank_volatility_regime",
                "clawrank_setup_quality", "clawrank_positioning",
                "clawrank_sentiment_catalyst", "clawrank_macro_regime",
                "clawrank_seasonality")}
            cr_text = score_cell_with_popover(cr_score, cr_label, factors, cr_trend, cr_setup, kr=clawrank_by_ticker[sym])
        else:
            cr_text = '<span style="color:var(--muted)">—</span>'

        rows_html.append(f"""
        <tr>
          <td class="ticker-cell">{sym}</td>
          {cr_text}
          <td data-val="{spot or 0:.2f}" class="{spot_vs_ref_class}">{spot_text}<br><span style="font-size:10px;color:var(--muted)">{spot_vs_ref_text}</span></td>
          <td data-val="{ref:.2f}">${ref:,.2f}</td>
          <td data-val="{target:.2f}">${target:,.2f}<br><span class="{upside_class}" style="font-size:10px">{upside_text}</span></td>
          <td class="{'pos' if upside_num > 0 else 'neg'}" data-val="{upside_num:.4f}">+{upside_num:.1f}%</td>
          <td><span class="prob-badge {prob_class}">{prob_badge}</span></td>
          <td>{timing}</td>
          <td data-val="{risk_line:.2f}" class="{risk_proximity_class}">${risk_line:,.2f}<br><span class="{risk_proximity_label_class}" style="font-size:10px">{risk_proximity_text}</span></td>
          <td class="spark-cell">{spark}</td>
          <td class="trigger-cell" title="{trigger}">{trigger}</td>
          <td class="trigger-cell" title="{risk_meaning}">{risk_meaning}</td>
        </tr>""")

    rows_joined = "".join(rows_html)
    count = len(tickers)
    return f"""
  <div class="card">
    <div class="card-header">
      <div class="dot" style="background:var(--purple)"></div>
      2.5) Watchlist — tactical trade candidates ({count} tickers) &mdash;
      <span style="text-transform:none;font-weight:400;color:var(--gold)">curated set with live spot prices, target window, and risk line. Default structure is a long-call butterfly at target; cash-secured puts / verticals use the same scoring framework.</span>
    </div>
    <div style="padding:0 16px 12px; color:var(--muted); font-size:11px;">
      Mike 2026-09-07 20:43 ET directive: "ultimately I may want to open a long call butterfly (when bullish) at a price target in a time period (1 month or 3 month, or others) so this section will help with that." Source: <code>config/options_watchlist.yaml</code>.
    </div>
    <table id="watchlist" class="dash watchlist-table">
      <thead>
        <tr>
          <th><a href="#glossary-ticker" class="header-glossary-link">Ticker</a></th>
          <th class="sortable" onclick="sortTable('watchlist',1,'num')"><a href="#glossary-label-rule" class="header-glossary-link" title="Click to read the ClawRank label rule glossary entry">ClawRank</a></th>
          <th class="sortable" onclick="sortTable('watchlist',2,'num')">Spot (live)</th>
          <th class="sortable" onclick="sortTable('watchlist',3,'num')">Ref</th>
          <th class="sortable" onclick="sortTable('watchlist',4,'num')">Target</th>
          <th class="sortable" onclick="sortTable('watchlist',5,'num')">Move%</th>
          <th class="sortable" onclick="sortTable('watchlist',6,'num')">Prob</th>
          <th>Timing</th>
          <th class="sortable" onclick="sortTable('watchlist',8,'num')">Risk line</th>
          <th>3mo</th>
          <th>Trigger / read-through</th>
          <th>If risk breaks</th>
        </tr>
      </thead>
      <tbody>
        {rows_joined}
      </tbody>
    </table>
    <div style="padding:8px 16px; color:var(--muted); font-size:11px;">
      <strong>Prob colors:</strong> <span class="prob-good">≥50%</span> · <span class="prob-mid">35-50%</span> · <span class="prob-low">&lt;35%</span>.
      <strong>Risk line:</strong> <span class="risk-broken">below = thesis broken</span>, <span class="risk-near">within 3% = danger zone</span>.
      <strong>Long-call butterfly plan:</strong> at spot, buy call at target (long wing) + sell 2 calls at midpoint + buy call at risk_line (short wing). Max loss = net debit. Max profit = midpoint − long − short. Best when spot is between short strikes at expiry.
    </div>
  </div>
  """


def render_html(rows, as_of, sparkline_data, clawrank_data=None, watchlist_data=None):
    by_ticker = {r["ticker"]: r for r in rows}
    clawrank_by_ticker = {r["ticker"]: r for r in (clawrank_data or [])}

    uptrend = sum(1 for r in rows if r["trend"] == "uptrend")
    downtrend = sum(1 for r in rows if r["trend"] == "downtrend")
    transitions = sum(1 for r in rows if r["trend"] == "transitioning")
    # ClawRank label counts EXCLUDE benchmarks (Mike 2026-09-07 — benchmarks get
    # regime labels, not ClawRank labels, so they shouldn't pollute the
    # "scored universe" KPIs).
    research = sum(1 for kr in clawrank_by_ticker.values()
                   if kr.get("ticker") not in BENCH_GROUP and kr.get("clawrank_label") == "Research candidate")
    watchlist = sum(1 for kr in clawrank_by_ticker.values()
                    if kr.get("ticker") not in BENCH_GROUP and kr.get("clawrank_label") == "Watchlist")
    avoid = sum(1 for kr in clawrank_by_ticker.values()
                if kr.get("ticker") not in BENCH_GROUP and kr.get("clawrank_label") == "Avoid")
    # Benchmark regime counts
    regime_count = {"risk-on": 0, "neutral": 0, "risk-off": 0}
    for t in BENCHMARKS:
        m = by_ticker.get(t)
        if m:
            r = regime_for(m)
            regime_count[r] = regime_count.get(r, 0) + 1
    spy = by_ticker.get("SPY", {})

    # Column index legend (Mike 2026-09-07 21:44 ET: Ticker is col 1, ClawScore is col 2 in all 3 tables).
    # Table 1 (Market & Sectors) — 18 cols
    #   0 = Ticker (col 1 — left-anchored)
    #   1 = ClawScore (col 2 — for benchmarks, shows regime pill instead)
    #   2 = Group/Sector
    #   3 = Price
    #   4 = Trend  (chip filter target — chip-group data-col="4")
    #   5..12 = Support, Resistance, %→S, %→R, 20D SD, Ann.Vol, ATR$, Rng%ile
    #   13 = RS v SPY
    #   14 = 60D spark
    #   15, 16 = 1σ 1d, 1σ 1mo
    #   17 = Outlook
    # Table 2 (Stock Shortlist / Sector Leaders) — 12 cols
    #   0 = Ticker (col 1)
    #   1 = ClawScore (col 2)
    #   2 = Sector
    #   3 = Price
    #   4 = Trend  (chip filter target — chip-group data-col="4")
    #   5 = Setup
    #   6, 7, 8 = RS v SPY, 20D SD, ADV
    #   9 = 60D spark
    #   10 = 1σ/2σ/3σ
    #   11 = Outlook
    # Watchlist — 12 cols
    #   0 = Ticker (col 1)
    #   1 = ClawScore (col 2)
    #   2 = Spot (live)
    #   3 = Ref
    #   4 = Target
    #   5 = Move%
    #   6 = Prob
    #   7 = Timing
    #   8 = Risk line
    #   9 = 3mo spark
    #   10 = Trigger / read-through
    #   11 = If risk breaks

    # Section 1 — Market & Sectors
    t1 = []
    for t in BENCHMARKS + SECTOR_ETFS:
        if t not in by_ticker: continue
        m = by_ticker[t]
        spark = sparkline_svg(sparkline_data[t], m["sd_20"], m["spot"])
        s1d = (m["spot"] - 1 * m["spot"] * m["sd_20"] * math.sqrt(1 / TRADING_DAYS),
               m["spot"] + 1 * m["spot"] * m["sd_20"] * math.sqrt(1 / TRADING_DAYS))
        s1mo = (m["spot"] - 1 * m["spot"] * m["sd_20"] * math.sqrt(21 / TRADING_DAYS),
                m["spot"] + 1 * m["spot"] * m["sd_20"] * math.sqrt(21 / TRADING_DAYS))
        pct_s = m["spot"] / m["support"] - 1
        pct_r = m["resistance"] / m["spot"] - 1
        rng = m["range_pctile"] if m["range_pctile"] is not None else -1
        rs = m["rs_vs_spy"] if m["rs_vs_spy"] is not None else -999
        # Benchmarks (SPY/QQQ/IWM) get regime labels, not ClawRank scores (Mike 2026-09-07).
        if t in BENCH_GROUP:
            score_td = regime_cell_with_popover(regime_for(m), m)
        else:
            # ClawRank data (sector ETFs only)
            kr = clawrank_by_ticker.get(t)
            cr_score = kr.get("clawrank_score") if kr else None
            cr_label = kr.get("clawrank_label", "—") if kr else "—"
            factors = {k.replace("clawrank_", ""): kr.get(k) for k in
                       ("clawrank_valuation", "clawrank_quality_growth",
                        "clawrank_technical_momentum", "clawrank_earnings_catalyst",
                        "clawrank_analyst_estimates", "clawrank_volatility_regime",
                        "clawrank_setup_quality", "clawrank_positioning",
                        "clawrank_sentiment_catalyst", "clawrank_macro_regime",
                        "clawrank_seasonality")} if kr else {}
            score_td = score_cell_with_popover(cr_score, cr_label, factors, m["trend"], m["setup"], kr=kr)
        t1.append(f"""
        <tr>
          <td class="ticker-cell">{m['ticker']}</td>
          {score_td}
          <td>{BENCH_GROUP.get(t, SECTOR_GROUP.get(t, ''))}</td>
          <td data-val="{m['spot']:.2f}">{fmt_money(m['spot'])}</td>
          <td>{trend_badge(m['trend'])}</td>
          <td data-val="{m['support']:.2f}">{fmt_money(m['support'])}</td>
          <td data-val="{m['resistance']:.2f}">{fmt_money(m['resistance'])}</td>
          <td class="{'pos' if pct_s > 0 else 'neg'}" data-val="{pct_s:.4f}">{fmt_pct(pct_s)}</td>
          <td class="pos" data-val="{pct_r:.4f}">{fmt_pct(pct_r)}</td>
          <td data-val="{m['sd_20']:.5f}">{fmt_pct_pos(m['sd_20'], 3)}</td>
          <td data-val="{m['ann_vol']:.5f}">{fmt_pct_pos(m['ann_vol'])}</td>
          <td data-val="{m['atr_20']:.2f}">{fmt_money(m['atr_20'])}</td>
          <td data-val="{rng}">{(f"{m['range_pctile']:.0f}" if m['range_pctile'] is not None else '—')}</td>
          <td class="{'pos' if rs > 0 else 'neg' if rs < 0 else ''}" data-val="{rs:.4f}">{fmt_pct(m['rs_vs_spy'])}</td>
          <td class="spark-cell">{spark}</td>
          <td data-val="{s1d[0]:.2f}">{s1d[0]:.2f}–{s1d[1]:.2f}</td>
          <td data-val="{s1mo[0]:.2f}">{s1mo[0]:.2f}–{s1mo[1]:.2f}</td>
          <td>{outlook_for(m)}</td>
        </tr>""")

    # Section 2 — Sector Leaders (one stock per sector, highest ClawRank score)
    # Picks the highest-scoring candidate from each sector's candidate list.
    sector_picks = pick_top_by_sector(list(clawrank_data) if clawrank_data else [])
    t2 = []
    for pick in sector_picks:
        sym = pick["ticker"]
        if sym not in by_ticker: continue
        m = by_ticker[sym]
        spark = sparkline_svg(sparkline_data[sym], m["sd_20"], m["spot"])
        s1w_lo = m["spot"] - 1 * m["spot"] * m["sd_20"] * math.sqrt(5 / TRADING_DAYS)
        s1w_hi = m["spot"] + 1 * m["spot"] * m["sd_20"] * math.sqrt(5 / TRADING_DAYS)
        s2w_lo = m["spot"] - 2 * m["spot"] * m["sd_20"] * math.sqrt(5 / TRADING_DAYS)
        s2w_hi = m["spot"] + 2 * m["spot"] * m["sd_20"] * math.sqrt(5 / TRADING_DAYS)
        s3w_lo = m["spot"] - 3 * m["spot"] * m["sd_20"] * math.sqrt(5 / TRADING_DAYS)
        s3w_hi = m["spot"] + 3 * m["spot"] * m["sd_20"] * math.sqrt(5 / TRADING_DAYS)
        sig_text = (f'1σ:{s1w_lo:.2f}–{s1w_hi:.2f}  '
                    f'2σ:{s2w_lo:.2f}–{s2w_hi:.2f}  '
                    f'3σ:{s3w_lo:.2f}–{s3w_hi:.2f}')
        rs = m["rs_vs_spy"] if m["rs_vs_spy"] is not None else -999
        cr_score = pick.get("clawrank_score")
        cr_label = pick.get("clawrank_label", "—")
        factors = {k.replace("clawrank_", ""): pick.get(k) for k in
                   ("clawrank_valuation", "clawrank_quality_growth",
                    "clawrank_technical_momentum", "clawrank_earnings_catalyst",
                    "clawrank_analyst_estimates", "clawrank_volatility_regime",
                    "clawrank_setup_quality", "clawrank_positioning",
                    "clawrank_sentiment_catalyst", "clawrank_macro_regime",
                    "clawrank_seasonality")}
        score_td = score_cell_with_popover(cr_score, cr_label, factors, m["trend"], m["setup"], kr=pick)
        # Show alternate candidates in the score-cell title attribute
        alts = ", ".join(f"{t}={s:.0f}" if s is not None else f"{t}=—"
                         for t, s in pick.get("all_candidates", []) if t != sym)
        t2.append(f"""
        <tr>
          <td class="ticker-cell">{m['ticker']}</td>
          {score_td}
          <td>{pick['sector_name']} <span style="color:var(--muted);font-size:10px">({pick['sector_etf']})</span></td>
          <td data-val="{m['spot']:.2f}">{fmt_money(m['spot'])}</td>
          <td>{trend_badge(m['trend'])}</td>
          <td>{m['setup'].replace('_', ' ')}</td>
          <td class="{'pos' if rs > 0 else 'neg' if rs < 0 else ''}" data-val="{rs:.4f}">{fmt_pct(m['rs_vs_spy'])}</td>
          <td data-val="{m['sd_20']:.5f}">{fmt_pct_pos(m['sd_20'], 3)}</td>
          <td data-val="{m['adv_usd']/1e6:.0f}">{fmt_adv(m['adv_usd'])}</td>
          <td class="spark-cell">{spark}</td>
          <td>{sig_text}</td>
          <td title="Other sector candidates: {alts}">{outlook_for(m)}</td>
        </tr>""")

    # Section 2.5 — Options Watchlist (Mike 2026-09-07 20:43 ET directive).
    # Curated long-call butterfly candidates with target, probability, timing, risk line.
    options_watchlist_html = render_options_watchlist(watchlist_data, clawrank_by_ticker)

    band_legend = (
        '<div class="legend-row">'
        f'<span><span class="swatch" style="background:{PAL["red"]}22;border:1px solid {PAL["red"]}"></span>±3σ band</span>'
        f'<span><span class="swatch" style="background:{PAL["yellow"]}33;border:1px solid {PAL["yellow"]}"></span>±2σ band</span>'
        f'<span><span class="swatch" style="background:{PAL["blue"]}44;border:1px solid {PAL["blue"]}"></span>±1σ band</span>'
        f'<span><span class="swatch" style="background:{PAL["gold"]}"></span>Price line</span>'
        '<span style="margin-left:auto;color:var(--muted)"><strong>Hover any ClawRank score</strong> to see 5-factor breakdown + label rule · Sigma = spot ± N·σ·√(h/252) descriptive only</span>'
        '</div>'
    )

    last_updated = as_of.strftime("%b %d, %Y · %H:%M %Z")
    subtitle = f"Daily Market & Sector Research · {as_of.strftime('%B %d, %Y')} · Universe: {len(BENCHMARKS)} benchmarks + {len(SECTOR_ETFS)} sector ETFs + {len(STOCKS)} scored stocks (S&P 500 + NASDAQ-100 + VTWO proxy)"

    # ----- Market regime note (Mike 2026-09-07 directive: real-time event awareness) -----
    # Detect US market holidays + cash market open/closed status. Display a banner
    # so the dashboard reflects "what's happening now," not just price action.
    US_FED_HOLIDAYS_2026 = {
        "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
        "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
    }
    as_of_date_str = as_of.strftime("%Y-%m-%d")
    wd = as_of.weekday()
    if wd >= 5:
        cash_status = "CLOSED (weekend)"
    elif as_of_date_str in US_FED_HOLIDAYS_2026:
        cash_status = "CLOSED (US holiday)"
    elif 9 * 60 + 30 <= as_of.hour * 60 + as_of.minute <= 16 * 60:
        cash_status = "OPEN"
    else:
        cash_status = "CLOSED (after hours)"
    regime_html = (
        '<div class="regime-banner">'
        f'<strong>Cash market:</strong> {cash_status} · '
        f'<strong>Event-aware:</strong> news + institutional positioning + social sentiment active · '
        f'<strong>Last build:</strong> {as_of_date_str} {as_of.strftime("%H:%M %Z").strip()}'
        '</div>'
    )

    # ClawRank factor table
    factor_table_rows = []
    factor_names = ["fundamental_health", "technical_momentum", "volatility_regime", "setup_quality", "sentiment_catalyst"]
    factor_labels = {"fundamental_health": "Fundamental Health",
                     "technical_momentum": "Technical Momentum",
                     "volatility_regime": "Volatility Regime",
                     "setup_quality": "Setup Quality",
                     "sentiment_catalyst": "Sentiment / Catalyst"}
    factor_weights = {"fundamental_health": "25%", "technical_momentum": "25%",
                      "volatility_regime": "15%", "setup_quality": "25%", "sentiment_catalyst": "25%"}
    for fn in factor_names:
        factor_table_rows.append(f"""
        <tr>
          <td>{factor_labels[fn]}</td>
          <td>{'yfinance .info (EPS, margin, growth, D/E, FCF, analyst target)' if fn in ['fundamental_health', 'sentiment_catalyst'] else 'Computed from price/volume + dashboard inputs'}</td>
          <td style="text-align:right"><span class="badge-gold">{factor_weights[fn]}</span></td>
          <td style="text-align:right">{factor_table_rows_count(fn)}</td>
        </tr>""")

    html = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Market Dashboard — {as_of.strftime('%Y-%m-%d')} ({BUILD_VERSION})</title>
<meta name="dashboard-version" content="{BUILD_VERSION}">
<link rel="icon" type="image/svg+xml" href="{FAVICON_HREF}">
<style>{CSS}</style>
</head><body>
<header>
  <div class="header-left">
    <h1>Market Dashboard — {as_of.strftime('%B %d, %Y')} <span style="font-size:14px;color:var(--muted);font-weight:400;letter-spacing:0">· updated {as_of.strftime('%H:%M %Z').strip()} · {BUILD_VERSION}</span></h1>
    <div class="subtitle">{subtitle}</div>
  </div>
  <div class="header-right">
    <span class="header-badge live">RESEARCH</span>
    <span class="last-updated">Updated {last_updated}</span>
  </div>
</header>
{regime_html}
<div class="disclaimer">
  <strong>Research output only — NOT a recommendation to buy, sell, or hold any security.</strong>
  Sigma bands and 1w ranges are <strong>descriptive</strong> (spot ± N·σ·√(h/252)), not predictions or targets.
  ClawRank is a transparent scoring layer — <strong>backtest shows no statistically significant 20D predictive edge in this universe &amp; window</strong> (see `2026-09-03-clawrank-backtest.md`).
</div>
<main>

<div class="card">
  <div class="card-header"><div class="dot" style="background:var(--gold)"></div> Snapshot — {len(rows)} instruments ({len(BENCHMARKS)} benchmarks + {len(SECTOR_ETFS)} sector ETFs + {len(STOCKS)} scored stocks)</div>
  <div class="kpi-row">
    <div class="kpi gold">
      <div class="kpi-label">SPY Spot</div>
      <div class="kpi-value">{fmt_money(spy.get('spot', None)) if 'spot' in spy else '—'}</div>
      <div class="kpi-sub">RS baseline</div>
    </div>
    <div class="kpi {'green' if uptrend > downtrend else 'red'}">
      <div class="kpi-label">Uptrend / Downtrend</div>
      <div class="kpi-value">{uptrend} <span style="color:var(--muted);font-size:11px">/</span> {downtrend}</div>
      <div class="kpi-sub">{transitions} transitioning{', ' + str(sum(1 for r in rows if r['trend']=='range')) + ' range' if any(r['trend']=='range' for r in rows) else ''}</div>
    </div>
    <div class="kpi blue">
      <div class="kpi-label">ClawRank Research</div>
      <div class="kpi-value">{research}</div>
      <div class="kpi-sub">composite ≥ 70</div>
    </div>
    <div class="kpi" style="--y:var(--yellow)">
      <div class="kpi-label">Watchlist</div>
      <div class="kpi-value" style="color:var(--yellow)">{watchlist}</div>
      <div class="kpi-sub">composite 30 – 70</div>
    </div>
    <div class="kpi red">
      <div class="kpi-label">ClawRank Avoid</div>
      <div class="kpi-value">{avoid}</div>
      <div class="kpi-sub">composite ≤ 30</div>
    </div>
    <div class="kpi" style="--y:var(--green)">
      <div class="kpi-label">Benchmark Regime</div>
      <div class="kpi-value" style="color:var(--green)">{regime_count["risk-on"]} on <span style="color:var(--muted);font-size:11px">/</span> {regime_count["neutral"]} n <span style="color:var(--muted);font-size:11px">/</span> {regime_count["risk-off"]} off</div>
      <div class="kpi-sub">SPY / QQQ / IWM</div>
    </div>
  </div>
</div>

<div class="card">
  <div class="card-header"><div class="dot" style="background:var(--blue)"></div> 1) Market & Sectors (3 benchmarks + 11 sector ETFs)</div>
  <div class="controls chip-group" data-table="t1" data-col="4">
    <span class="chip active" data-val="">All trends</span>
    <span class="chip" data-val="uptrend">uptrend</span>
    <span class="chip" data-val="downtrend">downtrend</span>
    <span class="chip" data-val="range">range</span>
    <span class="chip" data-val="transitioning">transitioning</span>
  </div>
  <div style="overflow-x:auto">
  <table id="t1">
    <thead><tr>
      <th><a href="#glossary-ticker" class="header-glossary-link">Ticker</a></th>
      <th class="sortable" onclick="sortTable('t1',1,'num')"><a href="#glossary-label-rule" class="header-glossary-link" title="Click to read the ClawRank label rule glossary entry">ClawRank</a></th>
      <th><a href="#glossary-group-sector" class="header-glossary-link">Group / Sector</a></th>
      <th class="sortable" onclick="sortTable('t1',3,'num')"><a href="#glossary-price" class="header-glossary-link">Price</a></th>
      <th><a href="#glossary-trend" class="header-glossary-link">Trend</a></th>
      <th class="sortable" onclick="sortTable('t1',5,'num')"><a href="#glossary-support" class="header-glossary-link">Support</a></th>
      <th class="sortable" onclick="sortTable('t1',6,'num')"><a href="#glossary-resistance" class="header-glossary-link">Resistance</a></th>
      <th><a href="#glossary-pct-to-support" class="header-glossary-link">%→S</a></th>
      <th><a href="#glossary-pct-to-resistance" class="header-glossary-link">%→R</a></th>
      <th class="sortable" onclick="sortTable('t1',9,'num')"><a href="#glossary-20d-sd" class="header-glossary-link">20D SD</a></th>
      <th class="sortable" onclick="sortTable('t1',10,'num')"><a href="#glossary-ann-vol" class="header-glossary-link">Ann.Vol</a></th>
      <th><a href="#glossary-atr" class="header-glossary-link">ATR$</a></th>
      <th class="sortable" onclick="sortTable('t1',12,'num')"><a href="#glossary-rng-percentile" class="header-glossary-link">Rng%ile</a></th>
      <th class="sortable" onclick="sortTable('t1',13,'num')"><a href="#glossary-rs-vs-spy" class="header-glossary-link">RS v SPY</a></th>
      <th><a href="#glossary-sigma-bands" class="header-glossary-link">60D + σ-bands</a></th>
      <th><a href="#glossary-sigma-bands" class="header-glossary-link">1σ 1d</a></th>
      <th><a href="#glossary-sigma-bands" class="header-glossary-link">1σ 1mo</a></th>
      <th><a href="#glossary-outlook" class="header-glossary-link">Outlook</a></th>
    </tr></thead>
    <tbody>{''.join(t1)}</tbody>
  </table>
  </div>
  {band_legend}
</div>

<div class="card">
  <div class="card-header"><div class="dot" style="background:var(--green)"></div> 2) Sector Leaders (top 3 highest-scoring stocks per sector, sorted by ClawRank) — <span style="text-transform:none;font-weight:400;color:var(--gold)">hover any score for 10-factor breakdown</span></div>
  <div class="controls chip-group" data-table="t2" data-col="4">
    <span class="chip active" data-val="">All trends</span>
    <span class="chip" data-val="uptrend">uptrend</span>
    <span class="chip" data-val="downtrend">downtrend</span>
    <span class="chip" data-val="range">range</span>
    <span class="chip" data-val="transitioning">transitioning</span>
  </div>
  <div style="overflow-x:auto">
  <table id="t2">
    <thead><tr>
      <th><a href="#glossary-ticker" class="header-glossary-link">Ticker</a></th>
      <th class="sortable" onclick="sortTable('t2',1,'num')"><a href="#glossary-label-rule" class="header-glossary-link" title="Click to read the ClawRank label rule glossary entry">ClawRank</a></th>
      <th><a href="#glossary-group-sector" class="header-glossary-link">Sector</a></th>
      <th class="sortable" onclick="sortTable('t2',3,'num')"><a href="#glossary-price" class="header-glossary-link">Price</a></th>
      <th><a href="#glossary-trend" class="header-glossary-link">Trend</a></th>
      <th><a href="#glossary-setup-quality" class="header-glossary-link">Setup</a></th>
      <th class="sortable" onclick="sortTable('t2',6,'num')"><a href="#glossary-rs-vs-spy" class="header-glossary-link">RS v SPY</a></th>
      <th class="sortable" onclick="sortTable('t2',7,'num')"><a href="#glossary-20d-sd" class="header-glossary-link">20D SD</a></th>
      <th class="sortable" onclick="sortTable('t2',8,'num')"><a href="#glossary-adv" class="header-glossary-link">ADV ($M)</a></th>
      <th><a href="#glossary-sigma-bands" class="header-glossary-link">60D + σ-bands</a></th>
      <th><a href="#glossary-sigma-bands" class="header-glossary-link">1σ/2σ/3σ (1w)</a></th>
      <th><a href="#glossary-outlook" class="header-glossary-link">Outlook</a></th>
    </tr></thead>
    <tbody>{''.join(t2)}</tbody>
  </table>
  </div>
  <div class="legend-row">
    <span><span class="swatch" style="background:var(--blue);width:10px;height:10px;border-radius:50%"></span>Research candidate (composite ≥70)</span>
    <span><span class="swatch" style="background:var(--yellow);width:10px;height:10px;border-radius:50%"></span>Watchlist (30–70)</span>
    <span><span class="swatch" style="background:var(--red);width:10px;height:10px;border-radius:50%"></span>Avoid (composite ≤30)</span>
    <span style="margin-left:auto;color:var(--muted)">Factor weights: Fund 25% / Tech 25% / Vol 15% / Setup 25% / Sent 10%</span>
  </div>
</div>

{options_watchlist_html}

<div class="card">
  <div class="card-header"><div class="dot" style="background:var(--purple)"></div> 3) ClawRank Composite (transparent, editable in YAML)</div>
  <div class="card-body" style="padding:0">
  <table>
    <thead><tr><th>Factor</th><th>Source</th><th style="text-align:right">Weight</th><th style="text-align:right">Cap</th></tr></thead>
    <tbody>
      <tr><td><a href="#glossary-fundamental-health" class="glossary-link">Fundamental Health</a></td><td>yfinance .info — earnings yield, revenue growth, op margin, D/E, FCF yield (stocks only; ETFs skip)</td><td style="text-align:right"><span class="badge-gold">25%</span></td><td style="text-align:right">—</td></tr>
      <tr><td><a href="#glossary-technical-momentum" class="glossary-link">Technical Momentum</a></td><td>RS vs SPY (20D/60D), MA distances, RSI(14), trend slope</td><td style="text-align:right"><span class="badge-gold">25%</span></td><td style="text-align:right">—</td></tr>
      <tr><td><a href="#glossary-volatility-regime" class="glossary-link">Volatility Regime</a></td><td>20D/252D vol ratio, ATR% vs SPY, 60D max drawdown</td><td style="text-align:right"><span class="badge-gold">15%</span></td><td style="text-align:right">—</td></tr>
      <tr><td><a href="#glossary-setup-quality" class="glossary-link">Setup Quality</a></td><td>Setup type (breakout / pullback / continuation / range / reversal) + range percentile + proximity to MA/resistance</td><td style="text-align:right"><span class="badge-gold">25%</span></td><td style="text-align:right">—</td></tr>
      <tr><td><a href="#glossary-sentiment-catalyst" class="glossary-link">Sentiment / Catalyst</a></td><td>ADV, 5D/20D volume ratio, analyst-target upside (stocks only)</td><td style="text-align:right"><span class="badge-gold">10%</span></td><td style="text-align:right">—</td></tr>
      <tr><td colspan="4" style="font-size:10.5px;color:var(--muted);padding-top:14px">
        <strong>Label rules:</strong>
        <span class="badge-gold">Research candidate</span> = composite ≥ 70
        <span style="color:var(--yellow);font-weight:600">Watchlist</span> = 30 ≤ composite &lt; 70
        <span style="color:var(--red);font-weight:600">Avoid</span> = composite &lt; 30
        <span style="display:block;margin-top:6px;color:var(--muted);font-style:italic">Trend + setup factors are already baked into the composite (via Technical Momentum + Setup Quality) so the label rule is score-only. See <a href="#glossary-label-rule" class="glossary-link">label rule glossary</a>.</span>
      </td></tr>
    </tbody>
  </table>
  </div>
  <div class="composite">
    <strong>Honest read on the backtest (2026-09-03):</strong>
    IC = −0.011 (t-stat −0.31) over 85 rebalance periods × 22 tickers × 2y window. <strong>No statistically significant 20D forward-return edge.</strong>
    ClawRank is shipped as a <strong>transparency / drill-down layer</strong>, not a trade signal. See <code>reports/2026-09-03-clawrank-backtest.md</code>.
  </div>
</div>

<div class="dq">
  <h3>Data-Quality Note</h3>
  <p><strong>Danelfin (per your 2026-09-03 directive):</strong> Removed from the live dashboard. ClawRank replaces it.
  Danelfin remains available as a side-by-side sanity check via the API at <code>apirest.danelfin.com</code>
  (Free tier: 500 calls/month, 10/min — fix the secret's host allow-list to enable). Not pulled automatically today.</p>
  <p><strong>Sigma bands:</strong> descriptive only (spot ± N·σ·√(h/252)); not predictions or targets.
  <strong>Support / Resistance:</strong> 20D high/low. <strong>Fundamentals (Factor 1):</strong> yfinance .info, stocks only —
  ETFs correctly skip this factor. <strong>Sample sizes:</strong> 20-session rolling windows on ~6mo yfinance daily bars.</p>
  <p><strong>No trade placement</strong>, no broker access, no position sizing, no scheduling, no universe expansion.</p>
</div>
</main>
<footer>
  <div class="footer-text">Generated {last_updated} by <span>dependability-quant</span> · research only</div>
  <div class="footer-text">yfinance · chart_structure (lib) · <span>ClawRank-v0</span></div>
</footer>

<aside class="glossary" id="glossary">
  <h2>📖 Glossary &amp; Methodology</h2>
  <p style="color:var(--muted);font-size:11px;margin-top:0">
    Click any <a href="#" class="glossary-link">term</a> in the tables above to jump to its glossary entry.
    Hover any score to see the 5-factor breakdown for that row.
  </p>

  <div class="glossary-grid">
    <div class="glossary-entry" id="glossary-fundamental-health">
      <h3><a href="#" class="back-link" title="Back to top">↑</a> Fundamental Health (Factor 1, 25%)</h3>
      <p><strong>What it measures:</strong> The financial health and valuation of the underlying company.</p>
      <p><strong>Inputs:</strong> From <code>yfinance .info</code>: earnings yield (EPS/price), revenue growth
      (year-over-year), operating margin, debt-to-equity ratio, free-cash-flow yield.</p>
      <p><strong>Who gets scored:</strong> Individual stocks only. ETFs (sector, benchmark) correctly skip
      this factor because they don't have company-level fundamentals — they get a neutral 50.</p>
      <p><strong>What a high score means:</strong> Cheap (high earnings yield), growing, profitable, low debt,
      strong FCF generation.</p>
    </div>

    <div class="glossary-entry" id="glossary-technical-momentum">
      <h3><a href="#" class="back-link" title="Back to top">↑</a> Technical Momentum (Factor 2, 25%)</h3>
      <p><strong>What it measures:</strong> How the price is moving relative to itself and the market.</p>
      <p><strong>Inputs:</strong> Relative Strength vs SPY over 20D and 60D windows, distance from 50-day
      moving average, RSI(14), 50-day trend slope.</p>
      <p><strong>What a high score means:</strong> Outperforming the broad market, price above its 50-day
      MA, RSI in a healthy range (not overbought), and the trend is rolling over to higher highs.</p>
    </div>

    <div class="glossary-entry" id="glossary-volatility-regime">
      <h3><a href="#" class="back-link" title="Back to top">↑</a> Volatility Regime (Factor 3, 15%)</h3>
      <p><strong>What it measures:</strong> The current volatility environment — whether it's elevated,
      compressed, or normal.</p>
      <p><strong>Inputs:</strong> Ratio of 20-day realized volatility to 1-year (252-day) realized volatility,
      Average True Range as a percentage vs SPY's ATR%, and the 60-day maximum drawdown.</p>
      <p><strong>What a high score means:</strong> Volatility is compressed (calm) vs its own history, the
      instrument is less volatile than SPY in absolute terms, and it hasn't suffered a recent drawdown.
      These conditions often precede directional breakouts.</p>
    </div>

    <div class="glossary-entry" id="glossary-setup-quality">
      <h3><a href="#" class="back-link" title="Back to top">↑</a> Setup Quality (Factor 4, 25%)</h3>
      <p><strong>What it measures:</strong> Whether the current price action matches a recognizable,
      tradable chart pattern.</p>
      <p><strong>Setup types:</strong></p>
      <ul>
        <li><strong>Breakout</strong> — price making a new 20-day high with positive 5-day momentum</li>
        <li><strong>Pullback / Retest</strong> — uptrend with price pulling back to MA50 or MA20 (often
        high-probability entry in an uptrend)</li>
        <li><strong>Continuation</strong> — uptrend above both MAs with smaller retracements</li>
        <li><strong>Range approach</strong> — trading sideways, no clear trend; setups still possible at
        range extremes</li>
        <li><strong>Reversal</strong> — downtrend showing first signs of base-building</li>
        <li><strong>Mean reversion</strong> — extreme move likely to revert to the mean</li>
      </ul>
      <p><strong>What a high score means:</strong> Active setup in a direction with momentum alignment;
      or a high range percentile (price near the top of its 20-day range, useful for breakout setups).</p>
    </div>

    <div class="glossary-entry" id="glossary-sentiment-catalyst">
      <h3><a href="#" class="back-link" title="Back to top">↑</a> Sentiment / Catalyst (Factor 5, 10%)</h3>
      <p><strong>What it measures:</strong> Trading activity and consensus expectations.</p>
      <p><strong>Inputs:</strong> Average Daily Volume in dollars, ratio of 5-day average volume to
      20-day average volume (rising volume = interest), and analyst price-target upside (stocks only).</p>
      <p><strong>What a high score means:</strong> Heavy trading activity relative to peers, accelerating
      volume (institutions piling in or distributing), and analyst targets implying upside from current
      price.</p>
    </div>

    <div class="glossary-entry" id="glossary-trend">
      <h3><a href="#" class="back-link" title="Back to top">↑</a> Trend (4-state classification)</h3>
      <p><strong>Uptrend</strong> — price above both MA50 and MA20, 5-day and 20-day momentum positive.</p>
      <p><strong>Downtrend</strong> — price below both MA50 and MA20, 5-day and 20-day momentum negative.</p>
      <p><strong>Range</strong> — price hugging its MAs and 20-day return inside ±3%, 5-day inside ±1%.</p>
      <p><strong>Transitioning</strong> — anything else (mixed signals: above one MA but below the other,
      or recent momentum diverging from the slower trend).</p>
      <p><strong>Examples today:</strong> SPY 765 above MA50 755 but below MA20 769 → <em>transitioning</em>
      (rangebound near the highs, not a clean uptrend). QQQ 709 below both MAs but +7% over 20 days →
      <em>transitioning</em> (bearish MA posture, bullish recent momentum).</p>
    </div>

    <div class="glossary-entry" id="glossary-label-rule">
      <h3><a href="#" class="back-link" title="Back to top">↑</a> Label rule (Research / Watchlist / Avoid)</h3>
      <p><strong>Score-only, not trend-gated.</strong> The ClawRank label is the composite score bucketed:</p>
      <ul>
        <li><span class="badge-gold">Research candidate</span> — composite ≥ 70</li>
        <li><span style="color:var(--yellow);font-weight:600">Watchlist</span> — 30 ≤ composite &lt; 70</li>
        <li><span style="color:var(--red);font-weight:600">Avoid</span> — composite &lt; 30</li>
      </ul>
      <p><strong>Why score-only?</strong> Trend and setup are already inside the composite via the
      Technical Momentum and Setup Quality factors. Gating the label on trend/setup AGAIN would
      double-count and demote fundamentally strong names that happen to be in a transition (e.g.,
      JPM, XLE). The score already reflects the underlying signal.</p>
      <p><strong>Backtest context:</strong> ClawRank's score-based label is a transparency layer — not a
      trade signal. The 2-year backtest showed IC = −0.011 (t-stat −0.31), no significant 20-day
      forward-return edge. See <code>reports/2026-09-03-clawrank-backtest.md</code>.</p>
    </div>

    <div class="glossary-entry" id="glossary-sigma-bands">
      <h3><a href="#" class="back-link" title="Back to top">↑</a> Sigma bands (1σ 1d / 1σ 1mo)</h3>
      <p><strong>What they are:</strong> Descriptive price ranges based on recent realized volatility,
      not predictions or targets.</p>
      <p><strong>Formula:</strong> <code>spot ± 1·σ·√(h/252)</code> where σ is the 20-day rolling daily
      standard deviation (annualized) and h is the holding period in trading days (1 for 1-day, 21 for
      1-month).</p>
      <p><strong>How to read them:</strong> A name with σ = 1%/day has a 1-day 1σ band of roughly ±1%
      around spot, and a 1-month 1σ band of roughly ±4.6%. About 68% of the time, the next-day close
      should land inside that band (assuming returns are normal — they aren't, but it's a useful
      rough guide).</p>
      <p><strong>Not:</strong> Bollinger Bands, options-pricing implied moves, or trade signals.</p>
    </div>

    <div class="glossary-entry" id="glossary-support-resistance">
      <h3><a href="#" class="back-link" title="Back to top">↑</a> Support / Resistance</h3>
      <p>The 20-day low and 20-day high, used as crude short-term support and resistance levels. The
      <strong>%→S</strong> and <strong>%→R</strong> columns show how far the current price is from each
      level.</p>
      <p><strong>Not:</strong> A magic number where price will bounce. These are descriptive, not
      predictive. Use them as orientation, not as entry/exit triggers.</p>
    </div>

    <div class="glossary-entry" id="glossary-rs-vs-spy">
      <h3><a href="#" class="back-link" title="Back to top">↑</a> RS v SPY (Relative Strength)</h3>
      <p>The ratio of the instrument's return to SPY's return over the same window. +5% means the
      instrument outperformed SPY by 5 percentage points over the period. Used to find leadership
      (sectors or stocks that are stronger than the broad market, often where the next big move
      starts).</p>
      <p><strong>Today:</strong> XLE +6.10% (energy leading), XLRE −9.75% (real estate lagging).</p>
    </div>

    <div class="glossary-entry" id="glossary-adv">
      <h3><a href="#" class="back-link" title="Back to top">↑</a> ADV ($M)</h3>
      <p>Average Daily Volume in millions of dollars. Higher = more liquid = easier to enter/exit
      without moving the price. Used as a sentiment/catalyst input (heavier volume = more institutional
      interest).</p>
    </div>

    <div class="glossary-entry" id="glossary-volatility-metrics">
      <h3><a href="#" class="back-link" title="Back to top">↑</a> Volatility metrics</h3>
      <p><strong>20D SD:</strong> 20-day rolling standard deviation of daily returns (annualized).
      Recent realized volatility.</p>
      <p><strong>Ann.Vol:</strong> Annualized volatility computed from the full available history.
      The "normal" volatility for this name.</p>
      <p><strong>ATR$:</strong> Average True Range in dollars. The typical daily high-low range, in
      cash terms. Useful for sizing stops.</p>
      <p><strong>Rng%ile:</strong> Where today's price sits within the 20-day range, as a percentile
      (0 = at the low, 100 = at the high). Values near 100 suggest breakouts; values near 0 suggest
      breakdowns or mean-reversion setups.</p>
    </div>

    <div class="glossary-entry" id="glossary-sector-leaders">
      <h3><a href="#" class="back-link" title="Back to top">↑</a> Sector Leaders (Table 2)</h3>
      <p>For each of the 11 sector ETFs, the table shows the highest-ClawRank-scoring candidate from
      a 2-3 name mega-cap shortlist. Sorted by score descending so the best sector-wide setup is at
      the top.</p>
      <p><strong>Candidate map:</strong> XLK→MSFT/NVDA/AAPL, XLF→JPM/BAC/GS, XLE→XOM/CVX,
      XLV→LLY/UNH/JNJ, XLI→CAT/HON/DE, XLY→HD/AMZN/TSLA, XLP→PG/KO/WMT, XLC→META/GOOGL,
      XLB→LIN/FCX, XLRE→AMT/PLD, XLU→NEE/SO.</p>
      <p><strong>Hover the Outlook column</strong> to see the alternate candidates' scores
      ("Other sector candidates: JPM=90, GS=42") — full transparency on what was considered.</p>
    </div>

    <div class="glossary-entry" id="glossary-price">
      <h3><a href="#" class="back-link" title="Back to top">↑</a> Price</h3>
      <p>The most recent closing price from the daily history. For intraday context this is the prior
      session close (we only pull end-of-day data). Used as the anchor for all σ-band calculations
      and percentage distances.</p>
    </div>

    <div class="glossary-entry" id="glossary-ticker">
      <h3><a href="#" class="back-link" title="Back to top">↑</a> Ticker</h3>
      <p>The exchange ticker symbol. For sector ETFs the underlying index is implied by the symbol
      (XLK = Technology Select Sector SPDR, XLF = Financial Select Sector SPDR, etc.).</p>
    </div>

    <div class="glossary-entry" id="glossary-group-sector">
      <h3><a href="#" class="back-link" title="Back to top">↑</a> Group / Sector</h3>
      <p>Broad classification: "Broad Mkt", "Tech", "Small Cap" for benchmarks; the GICS sector
      name ("Materials", "Financials", "Health Care", etc.) for sector ETFs and stocks. Helps
      quickly identify where each name fits in the market structure.</p>
    </div>

    <div class="glossary-entry" id="glossary-support">
      <h3><a href="#" class="back-link" title="Back to top">↑</a> Support</h3>
      <p>The lowest low over the last 20 trading days. Used as a crude short-term support level. The
      %→S column shows how far above support the current price is. See <a href="#glossary-support-resistance" class="glossary-link">Support / Resistance</a> for caveats.</p>
    </div>

    <div class="glossary-entry" id="glossary-resistance">
      <h3><a href="#" class="back-link" title="Back to top">↑</a> Resistance</h3>
      <p>The highest high over the last 20 trading days. Used as a crude short-term resistance level.
      The %→R column shows how far below resistance the current price is. See <a href="#glossary-support-resistance" class="glossary-link">Support / Resistance</a> for caveats.</p>
    </div>

    <div class="glossary-entry" id="glossary-pct-to-support">
      <h3><a href="#" class="back-link" title="Back to top">↑</a> %→S (percent to support)</h3>
      <p>Percentage distance from the current price to the 20-day low (support), expressed as a
      positive number. A value of +1.86% means the price is 1.86% above the recent low. Higher
      values mean the price has travelled further away from support (often stronger short-term
      momentum); values near 0 mean the price is testing support.</p>
    </div>

    <div class="glossary-entry" id="glossary-pct-to-resistance">
      <h3><a href="#" class="back-link" title="Back to top">↑</a> %→R (percent to resistance)</h3>
      <p>Percentage distance from the current price to the 20-day high (resistance), expressed as a
      positive number. A value of +3.57% means the price would need to rally 3.57% to make a new
      20-day high. Higher values = more upside room before hitting resistance.</p>
    </div>

    <div class="glossary-entry" id="glossary-20d-sd">
      <h3><a href="#" class="back-link" title="Back to top">↑</a> 20D SD (20-day standard deviation)</h3>
      <p>The standard deviation of daily returns over the last 20 trading days, <em>annualized</em>
      (multiplied by √252). This is the "recent realized volatility" — what the name has been
      actually doing lately, not the long-term average. A ClawRank volatility factor (25%) uses
      this directly.</p>
      <p><strong>Today:</strong> SPY 0.46% (extremely calm — broad market compressed),
      SO 1.5%+ (volatile utilities), NVDA 2.0%+ (tech mega-cap with elevated short-term vol).</p>
    </div>

    <div class="glossary-entry" id="glossary-ann-vol">
      <h3><a href="#" class="back-link" title="Back to top">↑</a> Ann.Vol (annualized volatility)</h3>
      <p>Standard deviation of daily returns over the full available history, annualized. This is the
      "normal" volatility for the name — its long-term baseline. Pair this with 20D SD to see if
      the name is currently <em>calmer or more volatile than usual</em>.</p>
      <p><strong>Today:</strong> XLE 21.55% (highest — energy is volatile by nature),
      SPY 7.37% (calmest — broad-market index).</p>
    </div>

    <div class="glossary-entry" id="glossary-atr">
      <h3><a href="#" class="back-link" title="Back to top">↑</a> ATR$ (Average True Range in dollars)</h3>
      <p>14-day Average True Range expressed in dollars per share. The typical daily high-low range.
      Useful for sizing stops: "I'll risk 1× ATR$ per share if I'm wrong". Also useful for options
      premium sanity-checks.</p>
      <p>Example: NVDA at $180 with ATR$ $5.18 means NVDA typically moves about $5 in either
      direction each day.</p>
    </div>

    <div class="glossary-entry" id="glossary-rng-percentile">
      <h3><a href="#" class="back-link" title="Back to top">↑</a> Rng%ile (range percentile)</h3>
      <p>Where today's close sits within the 20-day high/low range, on a 0-100 scale. 100 = at the
      20-day high (potential breakout), 0 = at the 20-day low (potential breakdown or reversal
      setup). Values in the middle indicate choppy, directionless action.</p>
      <p>This is one of the inputs to the <a href="#glossary-setup-quality" class="glossary-link">Setup Quality</a> factor.</p>
    </div>

    <div class="glossary-entry" id="glossary-outlook">
      <h3><a href="#" class="back-link" title="Back to top">↑</a> Outlook</h3>
      <p>A one-line qualitative read combining trend + setup + ClawRank label:</p>
      <ul>
        <li><strong>Bullish continuation</strong> — uptrend + breakout/pullback setup + Research candidate</li>
        <li><strong>Mean reversion candidate</strong> — uptrend that has pulled back to MA, RS still positive</li>
        <li><strong>Range-bound</strong> — flat trend, watch for range extremes</li>
        <li><strong>Caution</strong> — downtrend + low RS, even if score is high</li>
        <li><strong>Avoid</strong> — low score and downtrend</li>
      </ul>
      <p>Not a recommendation — just a structured summary of what the dashboard's quantitative
      factors are saying together.</p>
    </div>

  </div>
</aside>

<footer>
<script>{JS}</script>
</body></html>"""
    return html


def factor_table_rows_count(fn):
    """Just a stub to avoid NameError if factor names change."""
    return "—"


def main():
    t0 = time.time()
    as_of_et = dt.datetime.now(dt.timezone(dt.timedelta(hours=-4)))
    # Initialize universe (populates STOCKS, ALL_TICKERS) — needed when running standalone
    from build_clawrank_features import init_universe, STOCKS as _STOCKS, SECTOR_GROUP as _SG
    if not _STOCKS:
        init_universe()
    # Re-read STOCKS from the module — init_universe() rebinds the module-level name
    import build_clawrank_features as _bcf_mod
    _STOCKS = _bcf_mod.STOCKS
    global ALL_TICKERS
    ALL_TICKERS = BENCHMARKS + SECTOR_ETFS + [t for t, _, _ in _STOCKS]
    print(f"Universe: {len(_STOCKS)} stocks + {len(BENCHMARKS)} benchmarks + {len(SECTOR_ETFS)} ETFs = {len(ALL_TICKERS)} total", file=sys.stderr)
    print(f"Fetching {len(ALL_TICKERS)} tickers (~6mo daily) ...", file=sys.stderr)
    # Try parquet cache first (populated by clawrank build, has 2y data for all 528 tickers)
    from pathlib import Path as _P
    cache_dir = _P(__file__).resolve().parent.parent / "data" / "cache" / "prices"
    hist = pd.DataFrame()
    if cache_dir.exists():
        cached_frames = {}
        for t in ALL_TICKERS:
            cf = cache_dir / f"{t.upper()}_2y.parquet"
            if cf.exists():
                try:
                    df = pd.read_parquet(cf)
                    if not df.empty:
                        cached_frames[t] = df.tail(126)  # ~6mo of trading days
                except Exception:
                    pass
        if cached_frames:
            cols = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
            pieces = []
            for t, df in cached_frames.items():
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df = df[[c for c in cols if c in df.columns]].copy()
                df.columns = pd.MultiIndex.from_product([[t], df.columns])
                pieces.append(df)
            if pieces:
                hist = pd.concat(pieces, axis=1).sort_index()
                print(f"  loaded {len(cached_frames)}/{len(ALL_TICKERS)} from parquet cache (last 6mo)", file=sys.stderr)
    if hist is None or len(hist) == 0:
        # Fallback: fresh yfinance fetch
        print("  parquet cache empty, fetching from yfinance ...", file=sys.stderr)
        hist = fetch_history(ALL_TICKERS, period="6mo")
    if hist is None or len(hist) == 0:
        print("FATAL: yfinance returned no data", file=sys.stderr); sys.exit(2)

    closes = {t: get_series(hist, t, "Close") for t in ALL_TICKERS}
    highs = {t: get_series(hist, t, "High") for t in ALL_TICKERS}
    lows = {t: get_series(hist, t, "Low") for t in ALL_TICKERS}
    vols = {t: get_series(hist, t, "Volume") for t in ALL_TICKERS}
    spy_close = closes["SPY"]

    rows = []
    sparkline_data = {}
    for t in ALL_TICKERS:
        m = compute_metrics(closes, highs, lows, vols, spy_close, t)
        if m is not None:
            rows.append(m)
            sparkline_data[t] = closes[t]

    # Load ClawRank data if available
    clawrank_path = Path(__file__).resolve().parent.parent / "reports" / f"{as_of_et.strftime('%Y-%m-%d')}-clawrank.json"
    clawrank_data = None
    if clawrank_path.exists():
        try:
            clawrank_data = json.load(open(clawrank_path))["tickers"]
            print(f"ClawRank loaded: {len(clawrank_data)} rows", file=sys.stderr)
        except Exception as e:
            print(f"WARN: ClawRank load failed: {e}", file=sys.stderr)
            clawrank_data = None
    else:
        # Compute inline
        print("Computing ClawRank inline ...", file=sys.stderr)
        # Minimal macro_state (matches watchlist fallback below)
        _macro = {"regime": "n/a", "composite_score": 0.0,
                  "bear_risk_score": 0.0, "confidence": 0.5, "pillars": {}}
        info_cache: dict = {}
        feat_rows = []
        for t in ALL_TICKERS:
            feats = compute_features_for(t, hist, spy_close, info_cache, _macro)
            if feats is not None:
                feat_rows.append(feats)
        cfg = load_config(str(Path(__file__).resolve().parent.parent / "config" / "clawrank.yaml"))
        clawrank_data = rank(feat_rows, cfg)
        print(f"ClawRank computed: {len(clawrank_data)} rows", file=sys.stderr)

    # === Options Watchlist (Mike 2026-09-07 20:43 ET, renamed "Watchlist" 21:03 ET) ===
    # Curated tactical trade candidates. Lives in config/options_watchlist.yaml.
    # Pulls live spot prices via yfinance so the "ref vs spot" delta is visible.
    # Also computes ClawRank for any watchlist tickers not in the regular universe
    # (Mike 21:03 ET: "each stock needs a clawscore!") — merged into clawrank_data.
    watchlist_path = Path(__file__).resolve().parent.parent / "config" / "options_watchlist.yaml"
    watchlist_data = {"tickers": [], "live_prices": {}, "sparklines": {}}
    if watchlist_path.exists():
        wl_cfg = yaml.safe_load(open(watchlist_path))
        watchlist_data["tickers"] = sorted(wl_cfg.get("tickers", []), key=lambda t: t.get("rank", 99))
        wl_syms = [t["ticker"] for t in watchlist_data["tickers"]]
        if wl_syms:
            wl_hist = fetch_history(wl_syms, period="3mo")
            if wl_hist is not None and len(wl_hist) > 0:
                for t in wl_syms:
                    closes = get_series(wl_hist, t, "Close")
                    if closes is not None and len(closes) > 0:
                        watchlist_data["live_prices"][t] = float(closes.iloc[-1])
                        watchlist_data["sparklines"][t] = closes
                print(f"Watchlist: {len(watchlist_data['live_prices'])}/{len(wl_syms)} live prices fetched", file=sys.stderr)

            # --- Score watchlist tickers with ClawRank (Mike 21:03 ET directive) ---
            # Tickers already in the regular universe keep their existing score.
            # Tickers missing from the universe (AB, LII, MTN, TTWO, VST) get a fresh
            # 2y history pull + feature compute + rank pass.
            scored_tickers = {r["ticker"] for r in (clawrank_data or [])}
            missing = [t for t in wl_syms if t not in scored_tickers]
            if missing:
                print(f"Scoring {len(missing)} watchlist tickers not in regular universe: {missing}", file=sys.stderr)
                try:
                    # Build a minimal macro_state — same defaults as the inline-fallback path
                    wl_macro_state = {"regime": "n/a", "composite_score": 0.0,
                                      "bear_risk_score": 0.0, "confidence": 0.5, "pillars": {}}
                    wl_hist_2y = None
                    try:
                        wl_hist_2y = fetch_history(missing, period="2y")
                    except Exception as e:
                        print(f"WARN: watchlist 2y fetch failed: {e}", file=sys.stderr)
                    if wl_hist_2y is not None and len(wl_hist_2y) > 0:
                        # Need a spy_close series for relative-strength features
                        wl_spy = None
                        try:
                            if "SPY" in wl_hist_2y.columns.get_level_values(0):
                                wl_spy = wl_hist_2y["SPY"]["Close"].dropna()
                        except Exception:
                            pass
                        if wl_spy is None or len(wl_spy) < 50:
                            wl_spy = spy_close  # fallback to main history's SPY
                        info_cache_wl: dict = {}
                        wl_feat_rows = []
                        for t in missing:
                            feats = compute_features_for(t, wl_hist_2y, wl_spy, info_cache_wl, wl_macro_state)
                            if feats is not None:
                                wl_feat_rows.append(feats)
                        if wl_feat_rows:
                            cfg = load_config(str(Path(__file__).resolve().parent.parent / "config" / "clawrank.yaml"))
                            wl_ranked = rank(wl_feat_rows, cfg)
                            # Merge into clawrank_data so render_options_watchlist picks them up
                            if clawrank_data is None:
                                clawrank_data = wl_ranked
                            else:
                                clawrank_data = list(clawrank_data) + wl_ranked
                            print(f"Watchlist ClawRank scored: {len(wl_ranked)} tickers", file=sys.stderr)
                except Exception as e:
                    print(f"WARN: watchlist ClawRank scoring failed: {e}", file=sys.stderr)
                    import traceback; traceback.print_exc()
    else:
        print(f"WARN: {watchlist_path} not found, skipping watchlist section", file=sys.stderr)

    doc = render_html(rows, as_of_et, sparkline_data, clawrank_data, watchlist_data)
    reports_dir = Path(__file__).resolve().parent.parent / "reports"
    dated_path = reports_dir / f"{as_of_et.strftime('%Y-%m-%d')}-market-dashboard.html"
    canonical_path = reports_dir / "market-dashboard.html"
    # Write both paths: dated archive (audit) + canonical /market-dashboard.html (Mike's stable URL).
    dated_path.write_text(doc)
    canonical_path.write_text(doc)
    print(f"OK  html={dated_path}  canonical={canonical_path}  rows={len(rows)}  duration={time.time()-t0:.1f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
