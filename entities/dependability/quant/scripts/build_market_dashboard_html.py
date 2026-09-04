#!/usr/bin/env python3
"""build_market_dashboard_html.py — Interactive single-file HTML market dashboard.

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
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from build_clawrank_features import (  # noqa: E402
    fetch_history, get_series, compute_features_for, ALL_TICKERS, ETF_SET,
    BENCHMARKS, SECTOR_ETFS, STOCKS, SECTOR_GROUP, BENCH_GROUP,
    SECTOR_LEADERS, pick_top_by_sector,
)
from clawrank import rank, load_config  # noqa: E402

WINDOW = 20
TRADING_DAYS = 252

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
    slope = (ma_now - ma_prev) if ma_now is not None else 0
    if ma_now is None:
        trend = "n/a"
    elif spot > ma_now and slope > 0:
        trend = "uptrend"
    elif spot < ma_now and slope < 0:
        trend = "downtrend"
    elif abs(slope) < (c.std() * 0.001):
        trend = "range"
    else:
        trend = "transitioning"
    ma20 = float(c.tail(WINDOW).mean())
    hi20 = float(c.tail(WINDOW).max())
    lo20 = float(c.tail(WINDOW).min())
    ret_5d = float(c.iloc[-1] / c.iloc[-6] - 1) if len(c) >= 6 else 0
    ret_20d = float(c.iloc[-1] / c.iloc[-26] - 1) if len(c) >= 26 else 0
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


def score_cell_with_popover(score, label, factors, trend, setup):
    """First-column cell: score + hover-popover with 5 factor bars + label rule."""
    if score is None:
        return '<td class="score-cell" data-val="-1"><span class="unav">—</span></td>'
    # Determine label pill style + class
    short = "Wa"
    if label == "Research candidate": short = "Rc"
    elif label == "Avoid": short = "Av"
    elif label == "Watchlist": short = "Wa"
    # Build factor rows (5 of them)
    f_rows = []
    factor_defs = [
        ("Fundamental Health", factors.get("fundamental_health"), 25),
        ("Technical Momentum", factors.get("technical_momentum"), 25),
        ("Volatility Regime",   factors.get("volatility_regime"), 15),
        ("Setup Quality",        factors.get("setup_quality"), 25),
        ("Sentiment / Catalyst", factors.get("sentiment_catalyst"), 10),
    ]
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


def render_html(rows, as_of, sparkline_data, clawrank_data=None):
    by_ticker = {r["ticker"]: r for r in rows}
    clawrank_by_ticker = {r["ticker"]: r for r in (clawrank_data or [])}

    uptrend = sum(1 for r in rows if r["trend"] == "uptrend")
    downtrend = sum(1 for r in rows if r["trend"] == "downtrend")
    transitions = sum(1 for r in rows if r["trend"] == "transitioning")
    research = sum(1 for kr in clawrank_by_ticker.values() if kr.get("clawrank_label") == "Research candidate")
    watchlist = sum(1 for kr in clawrank_by_ticker.values() if kr.get("clawrank_label") == "Watchlist")
    avoid = sum(1 for kr in clawrank_by_ticker.values() if kr.get("clawrank_label") == "Avoid")
    spy = by_ticker.get("SPY", {})

    # Column index legend (kept consistent for chip filter + sort handlers):
    # Table 1 (Market & Sectors) — 19 cols
    #   0 = ClawRank Score (first col)
    #   1 = Ticker
    #   2 = Group/Sector
    #   3 = Price  (chip-filtered here? no — Trend is col 4 below)
    #   4 = Trend  (chip filter target)
    #   5..14 = Support, Resistance, %→S, %→R, 20D SD, Ann.Vol, ATR$, Rng%ile, RS v SPY, 60D spark
    #   15, 16 = 1σ 1d, 1σ 1mo
    #   17 = Outlook
    # Table 2 (Stock Shortlist) — 14 cols
    #   0 = ClawRank Score (first col)
    #   1 = Ticker
    #   2 = Sector
    #   3 = Price
    #   4 = Trend
    #   5 = Setup
    #   6, 7, 8 = RS v SPY, 20D SD, ADV
    #   9 = 60D spark
    #   10 = 1σ/2σ/3σ
    #   11 = Outlook

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
        # ClawRank data
        kr = clawrank_by_ticker.get(t)
        cr_score = kr.get("clawrank_score") if kr else None
        cr_label = kr.get("clawrank_label", "—") if kr else "—"
        factors = {k.replace("clawrank_", ""): kr.get(k) for k in
                   ("clawrank_fundamental_health", "clawrank_technical_momentum",
                    "clawrank_volatility_regime", "clawrank_setup_quality",
                    "clawrank_sentiment_catalyst")} if kr else {}
        score_td = score_cell_with_popover(cr_score, cr_label, factors, m["trend"], m["setup"])
        t1.append(f"""
        <tr>
          {score_td}
          <td class="ticker-cell">{m['ticker']}</td>
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
                   ("clawrank_fundamental_health", "clawrank_technical_momentum",
                    "clawrank_volatility_regime", "clawrank_setup_quality",
                    "clawrank_sentiment_catalyst")}
        score_td = score_cell_with_popover(cr_score, cr_label, factors, m["trend"], m["setup"])
        # Show alternate candidates in the score-cell title attribute
        alts = ", ".join(f"{t}={s:.0f}" if s is not None else f"{t}=—"
                         for t, s in pick.get("all_candidates", []) if t != sym)
        t2.append(f"""
        <tr>
          {score_td}
          <td class="ticker-cell">{m['ticker']}</td>
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
    subtitle = f"Daily Market & Sector Research · {as_of.strftime('%B %d, %Y')} · Universe: 3 benchmarks + 11 sector ETFs + 8 stocks (no expansion)"

    # ClawRank factor table
    factor_table_rows = []
    factor_names = ["fundamental_health", "technical_momentum", "volatility_regime", "setup_quality", "sentiment_catalyst"]
    factor_labels = {"fundamental_health": "Fundamental Health",
                     "technical_momentum": "Technical Momentum",
                     "volatility_regime": "Volatility Regime",
                     "setup_quality": "Setup Quality",
                     "sentiment_catalyst": "Sentiment / Catalyst"}
    factor_weights = {"fundamental_health": "25%", "technical_momentum": "25%",
                      "volatility_regime": "15%", "setup_quality": "25%", "sentiment_catalyst": "10%"}
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
<title>Market Dashboard — {as_of.strftime('%Y-%m-%d')}</title>
<link rel="icon" type="image/svg+xml" href="{FAVICON_HREF}">
<style>{CSS}</style>
</head><body>
<header>
  <div class="header-left">
    <h1>Market Dashboard — {as_of.strftime('%B %d, %Y')}</h1>
    <div class="subtitle">{subtitle}</div>
  </div>
  <div class="header-right">
    <span class="header-badge live">RESEARCH</span>
    <span class="last-updated">Updated {last_updated}</span>
  </div>
</header>
<div class="disclaimer">
  <strong>Research output only — NOT a recommendation to buy, sell, or hold any security.</strong>
  Sigma bands and 1w ranges are <strong>descriptive</strong> (spot ± N·σ·√(h/252)), not predictions or targets.
  ClawRank is a transparent scoring layer — <strong>backtest shows no statistically significant 20D predictive edge in this universe &amp; window</strong> (see `2026-09-03-clawrank-backtest.md`).
</div>
<main>

<div class="card">
  <div class="card-header"><div class="dot" style="background:var(--gold)"></div> Snapshot — 22 instruments</div>
  <div class="kpi-row">
    <div class="kpi gold">
      <div class="kpi-label">SPY Spot</div>
      <div class="kpi-value">{fmt_money(spy.get('spot', None)) if 'spot' in spy else '—'}</div>
      <div class="kpi-sub">RS baseline</div>
    </div>
    <div class="kpi {'green' if uptrend > downtrend else 'red'}">
      <div class="kpi-label">Uptrend / Downtrend</div>
      <div class="kpi-value">{uptrend} <span style="color:var(--muted);font-size:11px">/</span> {downtrend}</div>
      <div class="kpi-sub">{transitions} transitioning</div>
    </div>
    <div class="kpi blue">
      <div class="kpi-label">ClawRank Research</div>
      <div class="kpi-value">{research}</div>
      <div class="kpi-sub">composite ≥70 + good setup</div>
    </div>
    <div class="kpi" style="--y:var(--yellow)">
      <div class="kpi-label">Watchlist</div>
      <div class="kpi-value" style="color:var(--yellow)">{watchlist}</div>
      <div class="kpi-sub">composite 30–70</div>
    </div>
    <div class="kpi red">
      <div class="kpi-label">ClawRank Avoid</div>
      <div class="kpi-value">{avoid}</div>
      <div class="kpi-sub">composite ≤30 + downtrend</div>
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
      <th class="sortable" onclick="sortTable('t1',0,'num')">ClawRank</th>
      <th>Ticker</th><th>Group / Sector</th>
      <th class="sortable" onclick="sortTable('t1',3,'num')">Price</th>
      <th>Trend</th>
      <th class="sortable" onclick="sortTable('t1',5,'num')">Support</th>
      <th class="sortable" onclick="sortTable('t1',6,'num')">Resistance</th>
      <th>%→S</th><th>%→R</th>
      <th class="sortable" onclick="sortTable('t1',9,'num')">20D SD</th>
      <th class="sortable" onclick="sortTable('t1',10,'num')">Ann.Vol</th>
      <th>ATR$</th>
      <th class="sortable" onclick="sortTable('t1',12,'num')">Rng%ile</th>
      <th class="sortable" onclick="sortTable('t1',13,'num')">RS v SPY</th>
      <th>60D + σ-bands</th>
      <th>1σ 1d</th><th>1σ 1mo</th>
      <th>Outlook</th>
    </tr></thead>
    <tbody>{''.join(t1)}</tbody>
  </table>
  </div>
  {band_legend}
</div>

<div class="card">
  <div class="card-header"><div class="dot" style="background:var(--green)"></div> 2) Sector Leaders (one highest-scoring stock per sector, sorted by ClawRank) — <span style="text-transform:none;font-weight:400;color:var(--gold)">hover any score for 5-factor breakdown</span></div>
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
      <th class="sortable" onclick="sortTable('t2',0,'num')">ClawRank</th>
      <th>Ticker</th><th>Sector</th>
      <th class="sortable" onclick="sortTable('t2',3,'num')">Price</th>
      <th>Trend</th><th>Setup</th>
      <th class="sortable" onclick="sortTable('t2',6,'num')">RS v SPY</th>
      <th class="sortable" onclick="sortTable('t2',7,'num')">20D SD</th>
      <th class="sortable" onclick="sortTable('t2',8,'num')">ADV ($M)</th>
      <th>60D + σ-bands</th>
      <th>1σ/2σ/3σ (1w)</th>
      <th>Outlook</th>
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

<div class="card">
  <div class="card-header"><div class="dot" style="background:var(--purple)"></div> 3) ClawRank Composite (transparent, editable in YAML)</div>
  <div class="card-body" style="padding:0">
  <table>
    <thead><tr><th>Factor</th><th>Source</th><th style="text-align:right">Weight</th><th style="text-align:right">Cap</th></tr></thead>
    <tbody>
      <tr><td>Fundamental Health</td><td>yfinance .info — earnings yield, revenue growth, op margin, D/E, FCF yield</td><td style="text-align:right"><span class="badge-gold">25%</span></td><td style="text-align:right">—</td></tr>
      <tr><td>Technical Momentum</td><td>RS vs SPY (20D/60D), MA distances, RSI(14), trend slope</td><td style="text-align:right"><span class="badge-gold">25%</span></td><td style="text-align:right">—</td></tr>
      <tr><td>Volatility Regime</td><td>20D/252D vol ratio, ATR% vs SPY, 60D max drawdown</td><td style="text-align:right"><span class="badge-gold">15%</span></td><td style="text-align:right">—</td></tr>
      <tr><td>Setup Quality</td><td>Dashboard setup type + range percentile + proximity to MA/resistance</td><td style="text-align:right"><span class="badge-gold">25%</span></td><td style="text-align:right">—</td></tr>
      <tr><td>Sentiment / Catalyst</td><td>ADV, 5D/20D volume ratio, analyst-target upside (stocks only)</td><td style="text-align:right"><span class="badge-gold">10%</span></td><td style="text-align:right">—</td></tr>
      <tr><td colspan="4" style="font-size:10.5px;color:var(--muted);padding-top:14px">
        <strong>Label rules:</strong>
        <span class="badge-gold">Research candidate</span> = composite ≥ 70 AND trend = uptrend AND setup ∈ &#123;breakout, pullback_retest&#125;
        <span style="color:var(--red);font-weight:600">Avoid</span> = composite ≤ 30 AND trend = downtrend
        <span style="color:var(--yellow);font-weight:600">Watchlist</span> = everything else
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
<script>{JS}</script>
</body></html>"""
    return html


def factor_table_rows_count(fn):
    """Just a stub to avoid NameError if factor names change."""
    return "—"


def main():
    t0 = time.time()
    as_of_et = dt.datetime.now(dt.timezone(dt.timedelta(hours=-4)))
    print(f"Fetching {len(ALL_TICKERS)} tickers (~6mo daily) ...", file=sys.stderr)
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
        info_cache: dict = {}
        feat_rows = []
        for t in ALL_TICKERS:
            feats = compute_features_for(t, hist, spy_close, info_cache)
            if feats is not None:
                feat_rows.append(feats)
        cfg = load_config(str(Path(__file__).resolve().parent.parent / "config" / "clawrank.yaml"))
        clawrank_data = rank(feat_rows, cfg)
        print(f"ClawRank computed: {len(clawrank_data)} rows", file=sys.stderr)

    doc = render_html(rows, as_of_et, sparkline_data, clawrank_data)
    out_path = Path(__file__).resolve().parent.parent / "reports" / f"{as_of_et.strftime('%Y-%m-%d')}-market-dashboard.html"
    out_path.write_text(doc)
    print(f"OK  html={out_path}  rows={len(rows)}  duration={time.time()-t0:.1f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
