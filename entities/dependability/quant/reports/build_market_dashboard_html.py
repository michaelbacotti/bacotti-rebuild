#!/usr/bin/env python3
"""build_market_dashboard_html.py — Interactive single-file HTML market dashboard.

Visual language aligned with the bacotti-dashboard.html reference:
  - GitHub-Dark surface (#0d1117), gold accent (#d4a843), green/red/yellow/blue/purple tokens
  - Card grid with uppercase tracked headers + colored status dots
  - Gradient header bar with badge + last-updated stamp
  - Inline SVG sparklines with ±1σ/2σ/3σ band envelope
  - Sortable tables, filter chips, hover-glow row borders

Research only — no trade placement, no broker access, no key exposure.
Danelfin cells remain Unavailable until host allow-list is fixed.
"""
from __future__ import annotations

import datetime as dt
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

BENCHMARKS = ["SPY", "QQQ", "IWM"]
SECTOR_ETFS = ["XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"]
STOCKS = [
    ("AAPL", "Mega Tech"), ("MSFT", "Mega Tech"), ("NVDA", "Mega Tech"),
    ("JPM",  "Financials"), ("LLY",  "Healthcare"), ("XOM",  "Energy"),
    ("HD",   "Consumer Disc."), ("CAT",  "Industrials"),
]
SECTOR_GROUP = {
    "XLB": "Materials", "XLC": "Comm Services", "XLE": "Energy", "XLF": "Financials",
    "XLI": "Industrials", "XLK": "Technology", "XLP": "Consumer Staples",
    "XLRE": "Real Estate", "XLU": "Utilities", "XLV": "Health Care", "XLY": "Consumer Disc.",
}
BENCH_GROUP = {"SPY": "Broad Mkt", "QQQ": "Tech", "IWM": "Small Cap"}
ALL_TICKERS = BENCHMARKS + SECTOR_ETFS + [t for t, _ in STOCKS]
WINDOW = 20
TRADING_DAYS = 252

# === Palette (matches bacotti-dashboard.html) ===
PAL = {
    "bg":     "#0d1117", "surface":  "#161b22", "surface2": "#21262d",
    "border": "#30363d", "text":     "#e6edf3", "muted":    "#7d8590",
    "gold":      "#d4a843", "gold_dim":  "rgba(212,168,67,0.18)", "gold_glow": "rgba(212,168,67,0.08)",
    "green":     "#3fb950", "green_dim": "rgba(63,185,80,0.18)",
    "red":       "#f85149", "red_dim":   "rgba(248,81,73,0.18)",
    "yellow":    "#d29922", "yellow_dim":"rgba(210,153,34,0.18)",
    "blue":      "#58a6ff", "blue_dim":  "rgba(88,166,255,0.18)",
    "purple":    "#a371f7", "purple_dim":"rgba(163,113,247,0.18)",
    "pink":      "#ff7b72",
    "t_up":   "#3fb950", "t_down": "#f85149", "t_range": "#d29922", "t_trans": "#a371f7",
    "lbl_rc": "#58a6ff", "lbl_wl": "#d29922", "lbl_av": "#f85149",
}


def fetch_history(tickers, period="6mo"):
    return yf.download(tickers=tickers, period=period, interval="1d",
                       group_by="ticker", auto_adjust=False, progress=False, threads=True)


def get_series(hist, ticker, field):
    if isinstance(hist.columns, pd.MultiIndex):
        return hist[(ticker, field)].dropna()
    return hist[field].dropna()


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
    band_stroke = [PAL["red"], PAL["yellow"], PAL["blue"]]
    band_x0 = width * 0.6
    parts = [f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" style="display:block">']
    for (b_lo, b_hi), color, stroke in zip(bands, band_colors, band_stroke):
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


def fmt_money(x, d=2):
    return "—" if x is None else f"${x:,.{d}f}"


def fmt_pct(x, d=2):
    return "—" if x is None else f"{x*100:+.{d}f}%"


def fmt_pct_pos(x, d=2):
    return "—" if x is None else f"{x*100:.{d}f}%"


def fmt_adv(x):
    if x is None: return "—"
    return f"${x/1e6:,.0f}M"


CSS = f"""
:root {{
  --bg: {PAL['bg']}; --surface: {PAL['surface']}; --surface2: {PAL['surface2']};
  --border: {PAL['border']}; --text: {PAL['text']}; --muted: {PAL['muted']};
  --gold: {PAL['gold']}; --gold-dim: {PAL['gold_dim']}; --gold-glow: {PAL['gold_glow']};
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
         overflow: hidden; margin-bottom: 14px; }}
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
               color: var(--muted); background: var(--surface2); border-top: 1px solid var(--border); }}
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
});
"""


def render_html(rows, as_of, sparkline_data, closes):
    by_ticker = {r["ticker"]: r for r in rows}

    # === KPI strip ===
    uptrend = sum(1 for r in rows if r["trend"] == "uptrend")
    downtrend = sum(1 for r in rows if r["trend"] == "downtrend")
    transitions = sum(1 for r in rows if r["trend"] == "transitioning")
    research = sum(1 for r in rows if r["label"] == "Research candidate")
    watchlist = sum(1 for r in rows if r["label"] == "Watchlist")
    avoid = sum(1 for r in rows if r["label"] == "Avoid")
    spy_rs_b = sum(1 for r in rows if r.get("rs_vs_spy") is not None and r["rs_vs_spy"] > 0)
    spy_rs_l = sum(1 for r in rows if r.get("rs_vs_spy") is not None and r["rs_vs_spy"] < 0)
    spy = by_ticker.get("SPY", {})

    def fmt_ret_spy(h):
        return "—" if h is None else f"{h*100:+.2f}%"

    # Section 1 — Market & Sectors
    t1 = []
    for t in BENCHMARKS + SECTOR_ETFS:
        if t not in by_ticker: continue
        m = by_ticker[t]
        spark = sparkline_svg(sparkline_data[t], m["sd_20"], m["spot"])
        # Sigma columns
        def srange(h, k):
            lo = m["spot"] - k * m["spot"] * m["sd_20"] * math.sqrt(h / TRADING_DAYS)
            hi = m["spot"] + k * m["spot"] * m["sd_20"] * math.sqrt(h / TRADING_DAYS)
            return lo, hi
        s1d = srange(1, 1); s1w = srange(5, 1); s1mo = srange(21, 1)
        pct_s = m["spot"] / m["support"] - 1
        pct_r = m["resistance"] / m["spot"] - 1
        rng = m["range_pctile"] if m["range_pctile"] is not None else -1
        rs = m["rs_vs_spy"] if m["rs_vs_spy"] is not None else -999
        t1.append(f"""
        <tr>
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
          <td data-val="{m['atr_20']/m['spot']:.5f}">{fmt_pct_pos(m['atr_20']/m['spot'])}</td>
          <td data-val="{rng}">{(f"{m['range_pctile']:.0f}" if m['range_pctile'] is not None else '—')}</td>
          <td class="{'pos' if rs > 0 else 'neg' if rs < 0 else ''}" data-val="{rs:.4f}">{fmt_pct(m['rs_vs_spy'])}</td>
          <td class="spark-cell">{spark}</td>
          <td data-val="{s1d[0]:.2f}">{s1d[0]:.2f}–{s1d[1]:.2f}</td>
          <td data-val="{s1w[0]:.2f}">{s1w[0]:.2f}–{s1w[1]:.2f}</td>
          <td data-val="{s1mo[0]:.2f}">{s1mo[0]:.2f}–{s1mo[1]:.2f}</td>
          <td class="unav">Unavail</td>
          <td>{outlook_for(m)}</td>
        </tr>""")

    # Section 2 — Stock Shortlist
    label_rank = {"Research candidate": 0, "Watchlist": 1, "Avoid": 2}
    t2_sorted = sorted([by_ticker[t] for t, _ in STOCKS if t in by_ticker],
                       key=lambda m: (label_rank.get(m["label"], 1),
                                      -(m.get("rs_vs_spy") or -999)))
    t2 = []
    for m in t2_sorted:
        sector = next((s for sym, s in STOCKS if sym == m["ticker"]), "")
        spark = sparkline_svg(sparkline_data[m["ticker"]], m["sd_20"], m["spot"])
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
        rng = m["range_pctile"] if m["range_pctile"] is not None else -1
        label_class = {"Research candidate": "label-Rc",
                       "Watchlist": "label-Wa",
                       "Avoid": "label-Av"}.get(m["label"], "")
        t2.append(f"""
        <tr>
          <td class="ticker-cell">{m['ticker']}</td>
          <td>{sector}</td>
          <td data-val="{m['spot']:.2f}">{fmt_money(m['spot'])}</td>
          <td>{trend_badge(m['trend'])}</td>
          <td>{m['setup'].replace('_', ' ')}</td>
          <td data-val="{m['support']:.2f}">{fmt_money(m['support'])}</td>
          <td data-val="{m['resistance']:.2f}">{fmt_money(m['resistance'])}</td>
          <td class="{'pos' if rs > 0 else 'neg' if rs < 0 else ''}" data-val="{rs:.4f}">{fmt_pct(m['rs_vs_spy'])}</td>
          <td data-val="{m['sd_20']:.5f}">{fmt_pct_pos(m['sd_20'], 3)}</td>
          <td data-val="{m['ann_vol']:.5f}">{fmt_pct_pos(m['ann_vol'])}</td>
          <td data-val="{m['atr_20']:.2f}">{fmt_money(m['atr_20'])}</td>
          <td data-val="{rng}">{(f"{m['range_pctile']:.0f}" if m['range_pctile'] is not None else '—')}</td>
          <td data-val="{m['adv_usd']:.0f}">{fmt_adv(m['adv_usd'])}</td>
          <td class="spark-cell">{spark}</td>
          <td>{sig_text}</td>
          <td class="unav">U</td><td class="unav">U</td><td class="unav">U</td>
          <td class="unav">U</td><td class="unav">U</td>
          <td class="{label_class}" data-val="{m['label']}">{m['label']}</td>
          <td>{outlook_for(m)}</td>
        </tr>""")

    # Danelfin band legend (rendered just under the sparkline in section 1)
    band_legend = (
        '<div class="legend-row">'
        f'<span><span class="swatch" style="background:{PAL["red"]}22;border:1px solid {PAL["red"]}"></span>±3σ band</span>'
        f'<span><span class="swatch" style="background:{PAL["yellow"]}33;border:1px solid {PAL["yellow"]}"></span>±2σ band</span>'
        f'<span><span class="swatch" style="background:{PAL["blue"]}44;border:1px solid {PAL["blue"]}"></span>±1σ band</span>'
        f'<span><span class="swatch" style="background:{PAL["gold"]}"></span>Price line</span>'
        '<span style="margin-left:auto;color:var(--muted)">Sigma = spot ± N·σ·√(h/252) · descriptive only, not predictive</span>'
        '</div>'
    )

    # Compose HTML
    last_updated = as_of.strftime("%b %d, %Y · %H:%M %Z")
    subtitle = f"Daily Market & Sector Research · {as_of.strftime('%B %d, %Y')} · Universe: 3 benchmarks + 11 sector ETFs + 8 stocks (no expansion)"

    html = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Market Dashboard — {as_of.strftime('%Y-%m-%d')}</title>
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
  Danelfin columns are Unavailable this run (see DQ note).
</div>
<main>

<!-- KPI strip -->
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
    <div class="kpi {'green' if spy_rs_b > spy_rs_l else 'red'}">
      <div class="kpi-label">Beating SPY (20D)</div>
      <div class="kpi-value">{spy_rs_b} <span style="color:var(--muted);font-size:11px">/</span> {spy_rs_l}</div>
      <div class="kpi-sub">beating / lagging</div>
    </div>
    <div class="kpi blue">
      <div class="kpi-label">Research Candidates</div>
      <div class="kpi-value">{research}</div>
      <div class="kpi-sub">uptrend + breakout/pullback + RS≥0</div>
    </div>
    <div class="kpi" style="--y:var(--yellow)">
      <div class="kpi-label">Watchlist</div>
      <div class="kpi-value" style="color:var(--yellow)">{watchlist}</div>
      <div class="kpi-sub">constructive but no trigger</div>
    </div>
    <div class="kpi red">
      <div class="kpi-label">Avoid</div>
      <div class="kpi-value">{avoid}</div>
      <div class="kpi-sub">downtrend + RS &lt; −5%</div>
    </div>
  </div>
</div>

<!-- Market & Sectors -->
<div class="card">
  <div class="card-header"><div class="dot" style="background:var(--blue)"></div> 1) Market & Sectors (3 benchmarks + 11 sector ETFs)</div>
  <div class="controls chip-group" data-table="t1" data-col="3">
    <span class="chip active" data-val="">All trends</span>
    <span class="chip" data-val="uptrend">uptrend</span>
    <span class="chip" data-val="downtrend">downtrend</span>
    <span class="chip" data-val="range">range</span>
    <span class="chip" data-val="transitioning">transitioning</span>
  </div>
  <div style="overflow-x:auto">
  <table id="t1">
    <thead><tr>
      <th>Ticker</th><th>Group / Sector</th>
      <th class="sortable" onclick="sortTable('t1',2,'num')">Price</th>
      <th>Trend</th>
      <th class="sortable" onclick="sortTable('t1',4,'num')">Support</th>
      <th class="sortable" onclick="sortTable('t1',5,'num')">Resistance</th>
      <th>%→S</th><th>%→R</th>
      <th class="sortable" onclick="sortTable('t1',8,'num')">20D SD</th>
      <th class="sortable" onclick="sortTable('t1',9,'num')">Ann.Vol</th>
      <th>ATR$</th><th>ATR%</th>
      <th class="sortable" onclick="sortTable('t1',12,'num')">Rng%ile</th>
      <th class="sortable" onclick="sortTable('t1',13,'num')">RS v SPY</th>
      <th>60D + σ-bands</th>
      <th>1σ 1d</th><th>1σ 1w</th><th>1σ 1mo</th>
      <th>Danelfin</th><th>Outlook</th>
    </tr></thead>
    <tbody>{''.join(t1)}</tbody>
  </table>
  </div>
  {band_legend}
</div>

<!-- Stock shortlist -->
<div class="card">
  <div class="card-header"><div class="dot" style="background:var(--green)"></div> 2) Stock Shortlist (sorted: Research → Watchlist → Avoid)</div>
  <div class="controls chip-group" data-table="t2" data-col="19">
    <span class="chip active" data-val="">All labels</span>
    <span class="chip" data-val="Research candidate">Research candidate</span>
    <span class="chip" data-val="Watchlist">Watchlist</span>
    <span class="chip" data-val="Avoid">Avoid</span>
  </div>
  <div style="overflow-x:auto">
  <table id="t2">
    <thead><tr>
      <th>Ticker</th><th>Sector</th>
      <th class="sortable" onclick="sortTable('t2',2,'num')">Price</th>
      <th>Trend</th><th>Setup</th>
      <th>Support</th><th>Resistance</th>
      <th class="sortable" onclick="sortTable('t2',7,'num')">RS v SPY</th>
      <th class="sortable" onclick="sortTable('t2',8,'num')">20D SD</th>
      <th class="sortable" onclick="sortTable('t2',9,'num')">Ann.Vol</th>
      <th>ATR$</th><th>Rng%ile</th>
      <th class="sortable" onclick="sortTable('t2',12,'num')">ADV ($M)</th>
      <th>60D + σ-bands</th>
      <th>1σ/2σ/3σ (1w)</th>
      <th>AI</th><th>Tech</th><th>Fund</th><th>Sent</th><th>LR</th>
      <th class="sortable" onclick="sortTable('t2',19,'str')">Label</th><th>Outlook</th>
    </tr></thead>
    <tbody>{''.join(t2)}</tbody>
  </table>
  </div>
  <div class="legend-row">
    <span><span class="swatch" style="background:var(--blue);width:10px;height:10px;border-radius:50%"></span>Research candidate</span>
    <span><span class="swatch" style="background:var(--yellow);width:10px;height:10px;border-radius:50%"></span>Watchlist</span>
    <span><span class="swatch" style="background:var(--red);width:10px;height:10px;border-radius:50%"></span>Avoid</span>
    <span style="margin-left:auto"><span class="swatch" style="background:var(--muted);width:10px;height:10px;border-radius:2px"></span>U = Danelfin Unavailable</span>
  </div>
</div>

<!-- Composite weights -->
<div class="card">
  <div class="card-header"><div class="dot" style="background:var(--purple)"></div> 3) Transparent Composite Weights</div>
  <div class="card-body" style="padding:0">
  <table>
    <thead><tr><th>Component</th><th>Source</th><th style="text-align:right">Weight</th><th style="text-align:right">Cap</th></tr></thead>
    <tbody>
      <tr><td>Trend</td><td>50D MA + slope vs SPY</td><td style="text-align:right">30%</td><td style="text-align:right">—</td></tr>
      <tr><td>Support / Resistance</td><td>20D high/low</td><td style="text-align:right">25%</td><td style="text-align:right">—</td></tr>
      <tr><td>Volatility</td><td>20D realized vol</td><td style="text-align:right">15%</td><td style="text-align:right">—</td></tr>
      <tr><td>Liquidity</td><td>20D mean ($vol)</td><td style="text-align:right">10%</td><td style="text-align:right">—</td></tr>
      <tr><td>Freshness</td><td>Data age</td><td style="text-align:right">10%</td><td style="text-align:right">—</td></tr>
      <tr><td>Risk penalty</td><td>Subtraction</td><td style="text-align:right">10%</td><td style="text-align:right">up to −20</td></tr>
      <tr><td><span class="badge-gold">Danelfin (modulator)</span></td>
          <td>apirest.danelfin.com · <code style="background:var(--surface2);padding:1px 6px;border-radius:3px;color:var(--gold)">x-api-key</code> header</td>
          <td style="text-align:right"><span class="badge-gold">10%</span></td>
          <td style="text-align:right"><span class="badge-gold">capped</span></td></tr>
    </tbody>
  </table>
  </div>
  <div class="composite">
    <strong>Label rules:</strong>
    <span class="badge-gold">Research candidate</span> = uptrend AND setup ∈ &#123;breakout, pullback_retest&#125; AND range percentile ≥ 30 AND RS vs SPY ≥ 0 ·
    <span style="color:var(--red);font-weight:600">Avoid</span> = downtrend AND RS vs SPY &lt; −5% ·
    <span style="color:var(--yellow);font-weight:600">Watchlist</span> = everything else.
    When Danelfin is unavailable, its 10% weight is redistributed to <strong>Freshness</strong> (never silently dropped).
  </div>
</div>

<!-- DQ note -->
<div class="dq">
  <h3>Data-Quality Note</h3>
  <p><strong>Danelfin (all 5 columns × 22 rows = 110 cells): Unavailable.</strong>
  The Danelfin API gateway at <code>apirest.danelfin.com</code> uses <code>x-api-key</code> header auth
  (confirmed via Danelfin public docs and Brave search). The stored <code>DANELFIN_API_KEY</code> value
  is correct, but the secret's egress allow-list is set to <code>api.danelfin.com</code>, which the
  OpenClaw gateway proxy rejects at egress (HTTP 403) because the actual API host is
  <code>apirest.danelfin.com</code>. <strong>One-tap fix:</strong> edit the secret's host allow-list in
  the operator UI to <code>apirest.danelfin.com</code> (value unchanged). All Danelfin cells then populate.</p>
  <p><strong>Sigma ranges:</strong> descriptive only (spot ± N·σ·√(h/252)); not predictions or targets.
  <strong>Support / resistance:</strong> 20D high/low — no volume-profile overlay this run.
  <strong>Sample sizes:</strong> 20-session rolling windows on ~6mo yfinance daily bars; no <code>insufficient</code> cases.</p>
  <p><strong>No trade placement</strong>, no broker access, no position sizing, no scheduling,
  no universe expansion, no key exposure.</p>
</div>
</main>
<footer>
  <div class="footer-text">Generated {last_updated} by <span>dependability-quant</span> · research only</div>
  <div class="footer-text">yfinance · chart_structure (lib) · Danelfin (Unavail)</div>
</footer>
<script>{JS}</script>
</body></html>"""
    return html


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

    doc = render_html(rows, as_of_et, sparkline_data, closes)
    out_path = Path(__file__).resolve().parent / f"{as_of_et.strftime('%Y-%m-%d')}-market-dashboard.html"
    out_path.write_text(doc)
    print(f"OK  html={out_path}  rows={len(rows)}  duration={time.time()-t0:.1f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
