"""Charts helper for Dependability Quant — produces matplotlib PNGs to entities/dependability/quant/charts/.

Templates:
- price_with_ma: spot price + MA5/MA20/MA50 overlays from daily bars
- iv_term_structure: IV across expirations for a single underlying
- butterfly_payoff: payoff diagram for a long call/put butterfly
- sigma_band: spot with ±1σ/2σ envelope (1M/2M/3M)
- candidate_summary: combined panel for research notes

Every chart uses pure script-derived data. No memory-based numbers.
"""

from __future__ import annotations

import sys
import os
import math
from datetime import date
from pathlib import Path
from typing import Sequence

import matplotlib
matplotlib.use("Agg")  # non-interactive
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter

CHARTS_DIR = Path(__file__).parent.parent / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

DPI = 120
DEFAULT_FIGSIZE = (11, 6)


def _save(fig, name: str) -> Path:
    """Save figure to charts/<name>.png, return path."""
    p = CHARTS_DIR / name
    fig.tight_layout()
    fig.savefig(p, dpi=DPI)
    plt.close(fig)
    return p


def _usd(x, pos=None) -> str:
    if abs(x) >= 1e9:
        return f"${x/1e9:.1f}B"
    if abs(x) >= 1e6:
        return f"${x/1e6:.1f}M"
    if abs(x) >= 1e3:
        return f"${x/1e3:.1f}k"
    return f"${x:.2f}"


def price_with_ma(
    symbol: str,
    closes: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    dates: Sequence,
    ma_windows: tuple[int, ...] = (5, 20, 50),
    current_price: float | None = None,
    title: str | None = None,
) -> Path:
    """Spot price + MA overlays. closes/highs/lows/dates same length."""
    fig, ax = plt.subplots(figsize=DEFAULT_FIGSIZE)
    ax.plot(dates, closes, color="black", linewidth=1.5, label=f"{symbol} close")
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]
    for i, w in enumerate(ma_windows):
        if len(closes) >= w:
            ma = [sum(closes[max(0, i-w+1):i+1]) / min(w, i+1) for i in range(len(closes))]
            ax.plot(dates, ma, color=colors[i % len(colors)], linewidth=1, alpha=0.85, label=f"MA{w}")
    if current_price is not None:
        ax.axhline(current_price, color="gray", linestyle="--", alpha=0.5, label=f"current ${current_price:.2f}")
    ax.set_title(title or f"{symbol} price + MA")
    ax.set_ylabel("Price ($)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.yaxis.set_major_formatter(FuncFormatter(_usd))
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper left", fontsize=8)
    fig.autofmt_xdate()
    return _save(fig, f"{symbol}_price_ma.png")


def iv_term_structure(
    symbol: str,
    expirations: Sequence[str],
    ivs: Sequence[float],
    dtes: Sequence[int],
    spot: float,
    current_atm_iv: float | None = None,
) -> Path:
    """Plot IV vs DTE for a single symbol across multiple expirations."""
    fig, ax = plt.subplots(figsize=DEFAULT_FIGSIZE)
    ax.plot(dtes, [iv * 100 for iv in ivs], "o-", color="#1f77b4", label="ATM IV")
    if current_atm_iv is not None:
        ax.axhline(current_atm_iv * 100, color="gray", linestyle="--", alpha=0.5,
                   label=f"current {current_atm_iv*100:.1f}%")
    for dte, exp, iv in zip(dtes, expirations, ivs):
        ax.annotate(exp, (dte, iv * 100), textcoords="offset points", xytext=(5, 5), fontsize=7)
    ax.set_xlabel("Days to expiration")
    ax.set_ylabel("ATM Implied Volatility (%)")
    ax.set_title(f"{symbol} IV term structure (spot ${spot:.2f})")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper right", fontsize=8)
    return _save(fig, f"{symbol}_iv_term.png")


def butterfly_payoff(
    symbol: str,
    lower: float,
    middle: float,
    upper: float,
    net_debit: float,
    kind: str = "long_call",
    spot: float | None = None,
    strikes_range: tuple[float, float] | None = None,
) -> Path:
    """Long call/put butterfly payoff diagram at expiration."""
    fig, ax = plt.subplots(figsize=DEFAULT_FIGSIZE)
    if strikes_range is None:
        strikes_range = (lower - (middle - lower) * 2, upper + (upper - middle) * 2)
    xs = [strikes_range[0] + (strikes_range[1] - strikes_range[0]) * i / 200 for i in range(201)]
    if kind == "long_call":
        # long 1 lower, short 2 middle, long 1 upper
        wing = middle - lower
        ys = []
        for s in xs:
            p = (max(s - lower, 0) - 2 * max(s - middle, 0) + max(s - upper, 0)) - net_debit
            ys.append(p)
        title = f"{symbol} Long Call Butterfly {lower}/{middle}/{upper} (debit ${net_debit:.2f})"
    elif kind == "long_put":
        wing = middle - lower
        ys = []
        for s in xs:
            p = (max(lower - s, 0) - 2 * max(middle - s, 0) + max(upper - s, 0)) - net_debit
            ys.append(p)
        title = f"{symbol} Long Put Butterfly {lower}/{middle}/{upper} (debit ${net_debit:.2f})"
    else:
        raise ValueError(f"kind must be 'long_call' or 'long_put', got {kind}")
    
    ax.plot(xs, ys, color="#1f77b4", linewidth=2)
    ax.axhline(0, color="black", linewidth=0.5)
    ax.fill_between([s for s, y in zip(xs, ys) if y >= 0], 0, [y for y in ys if y >= 0],
                    color="green", alpha=0.2, label="profit zone")
    ax.fill_between([s for s, y in zip(xs, ys) if y < 0], [y for y in ys if y < 0], 0,
                    color="red", alpha=0.2, label="loss zone")
    ax.axvline(lower, color="gray", linestyle="--", alpha=0.5, label=f"K1={lower}")
    ax.axvline(middle, color="gray", linestyle="--", alpha=0.5, label=f"K2={middle}")
    ax.axvline(upper, color="gray", linestyle="--", alpha=0.5, label=f"K3={upper}")
    if spot is not None:
        ax.axvline(spot, color="red", linewidth=2, label=f"spot={spot:.2f}")
    
    # Mark max gain / max loss
    max_y = max(ys)
    max_x = xs[ys.index(max_y)]
    ax.annotate(f"max gain ${max_y:.0f}", xy=(max_x, max_y), xytext=(10, -10),
                textcoords="offset points", fontsize=9, color="green",
                arrowprops=dict(arrowstyle="->", color="green"))
    min_y = min(ys)
    min_x = xs[ys.index(min_y)]
    ax.annotate(f"max loss ${min_y:.0f}", xy=(min_x, min_y), xytext=(10, 10),
                textcoords="offset points", fontsize=9, color="red",
                arrowprops=dict(arrowstyle="->", color="red"))
    
    ax.set_xlabel("Underlying at expiration")
    ax.set_ylabel("P&L per share ($)")
    ax.set_title(title)
    ax.yaxis.set_major_formatter(FuncFormatter(_usd))
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, alpha=0.3)
    return _save(fig, f"{symbol}_{kind}_butterfly_{lower}_{middle}_{upper}.png")


def sigma_band(
    symbol: str,
    spot: float,
    iv: float,
    horizons: tuple[tuple[str, int], ...] = (("1M", 30), ("2M", 61), ("3M", 91)),
    current_price_path: Sequence[tuple] | None = None,
) -> Path:
    """σ-band visualization: spot with ±1σ/2σ envelope over 1M/2M/3M horizons."""
    fig, ax = plt.subplots(figsize=DEFAULT_FIGSIZE)
    
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c"]
    labels = []
    for (label, days), color in zip(horizons, colors):
        T = days / 365.0
        sigma = spot * iv * math.sqrt(T)
        ax.fill_between([-0.5, 1.5], spot - 2 * sigma, spot + 2 * sigma, color=color, alpha=0.08)
        ax.axhline(spot + sigma, color=color, linestyle=":", alpha=0.6)
        ax.axhline(spot - sigma, color=color, linestyle=":", alpha=0.6)
        labels.append(f"{label}: ${spot-sigma:.2f}-${spot+sigma:.2f} (±{iv*math.sqrt(T)*100:.2f}%)")
        ax.text(1.55, spot + sigma, f"  +1σ {label}", color=color, fontsize=8, va="center")
        ax.text(1.55, spot - sigma, f"  -1σ {label}", color=color, fontsize=8, va="center")
    
    ax.axhline(spot, color="black", linewidth=2, label=f"spot ${spot:.2f}")
    ax.set_xlim(-0.5, 2.5)
    ax.set_ylim(spot * (1 - iv * 2), spot * (1 + iv * 2))
    ax.set_xticks([])
    ax.yaxis.set_major_formatter(FuncFormatter(_usd))
    ax.set_title(f"{symbol} σ-bands (IV {iv*100:.1f}%)")
    ax.legend(["spot", "\u00b11σ / \u00b12σ envelopes (1M/2M/3M)"], loc="lower right", fontsize=8)
    ax.grid(True, alpha=0.3)
    return _save(fig, f"{symbol}_sigma_bands.png")


if __name__ == "__main__":
    # Smoke test: render sigma_bands for SPY with stub data
    print("Charts module loaded. Available functions:")
    print("  - price_with_ma(symbol, closes, highs, lows, dates, ...)")
    print("  - iv_term_structure(symbol, expirations, ivs, dtes, spot, ...)")
    print("  - butterfly_payoff(symbol, lower, middle, upper, net_debit, kind='long_call')")
    print("  - sigma_band(symbol, spot, iv, ...)")
    print(f"Charts dir: {CHARTS_DIR}")
    print()
    # Render a sample sigma_band
    out = sigma_band("SPY", 765.97, 0.109)
    print(f"Wrote sample chart: {out}")
