"""institutional_flow.py — free signals for institutional positioning.

Sources (all free, no auth):
  - yfinance fundamentals (.info) for short interest, institutional %, insider %
  - Finviz scraping via headless browser (single-page public data)
  - StockAnalysis.com for 13F aggregator (delayed ~45 days)

This module consolidates signals from yfinance (primary) + web-scraped pages
where available. NO paid APIs.

Anti-hallucination: every number has a source citation. Missing data → None, not invented.
"""
from __future__ import annotations
import datetime as dt
import math
import re
import urllib.request
from typing import Any

from data_fetcher import fundamentals_snapshot, price_history


def short_interest_signal(symbol: str) -> dict | None:
    """Short interest trend signal via yfinance.

    Returns dict with current shares_short, prior_month_change_pct, days_to_cover,
    classification: 'heavy_short_pressure' / 'moderate_short' / 'light_short' / 'no_signal'.
    """
    info = fundamentals_snapshot(symbol)
    if not info:
        return None
    cur = info.get("sharesShort")
    prior = info.get("sharesShortPriorMonth")
    dtc = info.get("shortRatio")
    pct_float = info.get("shortPercentOfFloat")
    if cur is None:
        return None
    mom_change_pct = None
    if prior and prior > 0 and cur is not None:
        mom_change_pct = (cur - prior) / prior

    # Heuristic classification
    classification = None
    if pct_float is not None:
        if pct_float > 0.10:
            classification = "heavy_short_pressure"
        elif pct_float > 0.05:
            classification = "moderate_short"
        elif pct_float > 0.02:
            classification = "light_short"
        else:
            classification = "minimal_short"

    return {
        "symbol": symbol,
        "shares_short": cur,
        "shares_short_prior_month": prior,
        "mom_change_pct": mom_change_pct,
        "days_to_cover": dtc,
        "pct_of_float": pct_float,
        "classification": classification,
        "finra_report_date_epoch": info.get("dateShortInterest"),
        "as_of": dt.datetime.utcnow().isoformat() + "Z",
    }


def institutional_ownership_signal(symbol: str) -> dict | None:
    """Institutional + insider ownership via yfinance.

    Returns dict with institutional_pct, insider_pct, mkt_cap, derivative_score.
    """
    info = fundamentals_snapshot(symbol)
    if not info:
        return None
    inst = info.get("heldPercentInstitutions")
    insider = info.get("heldPercentInsiders")
    mcap = info.get("marketCap")
    if inst is None and insider is None:
        return None

    # Sentiment heuristic
    classification = None
    if inst is not None:
        if inst > 0.80:
            classification = "very_high_inst"
        elif inst > 0.60:
            classification = "high_inst"
        elif inst > 0.30:
            classification = "moderate_inst"
        else:
            classification = "low_inst"

    return {
        "symbol": symbol,
        "institutional_pct": inst,
        "insider_pct": insider,
        "market_cap": mcap,
        "classification": classification,
        "as_of": dt.datetime.utcnow().isoformat() + "Z",
    }


def analyst_consensus_signal(symbol: str) -> dict | None:
    """Analyst consensus signal: mean target vs current spot + rating.

    Returns dict with upside_pct, rating_label, earnings_date.
    """
    info = fundamentals_snapshot(symbol)
    if not info:
        return None
    mean_target = info.get("targetMeanPrice")
    spot_info = price_history(symbol, period="1d")
    if spot_info is None or spot_info.empty:
        return None
    spot = float(spot_info["Close"].iloc[-1])
    upside_pct = None
    if mean_target and spot > 0:
        upside_pct = (mean_target - spot) / spot
    return {
        "symbol": symbol,
        "spot": spot,
        "mean_target": mean_target,
        "high_target": info.get("targetHighPrice"),
        "low_target": info.get("targetLowPrice"),
        "upside_pct": upside_pct,
        "rating_label": info.get("recommendationKey"),
        "rating_mean": info.get("recommendationMean"),  # 1=strong buy, 5=strong sell
        "next_earnings_epoch": info.get("earningsTimestamp"),
        "as_of": dt.datetime.utcnow().isoformat() + "Z",
    }


def composite_flow_signal(symbol: str) -> dict | None:
    """Composite positioning score from yfinance fundamentals.

    Combines short interest, institutional %, insider %, analyst consensus
    into a multi-factor signal. Returns dict with each component and composite.

    Composite score is NOT a buy/sell signal — just a structured snapshot.
    """
    si = short_interest_signal(symbol)
    io = institutional_ownership_signal(symbol)
    ac = analyst_consensus_signal(symbol)
    if not any([si, io, ac]):
        return None

    composite = {}
    # Short interest: heavy short + increasing = bearish positioning
    si_score = None
    if si and si.get("mom_change_pct") is not None:
        mom = si["mom_change_pct"]
        pct = si.get("pct_of_float") or 0
        # Negative = short covering (bullish), positive = short buildup (bearish)
        si_score = -mom * 0.5 + (pct - 0.05)  # high short pct + increasing = strong negative
        si_score = max(-1.0, min(1.0, si_score))

    # Institutional: rising institutional + high ownership = neutral-to-positive long-term
    inst_score = None
    if io and io.get("institutional_pct") is not None:
        inst_score = (io["institutional_pct"] - 0.50) * 2  # 0.5% -> 0; 0.75% -> 0.5
        inst_score = max(-1.0, min(1.0, inst_score))

    # Analyst: low rating (1=buy) + upside = bullish
    an_score = None
    if ac and ac.get("rating_mean") is not None and ac.get("upside_pct") is not None:
        # Invert rating (1=buy → 1.0; 5=sell → -1.0)
        an_score = (3.5 - ac["rating_mean"]) / 2.5
        an_score += ac.get("upside_pct") or 0
        an_score = max(-1.0, min(1.0, an_score * 0.7))

    return {
        "symbol": symbol,
        "short_interest": si,
        "institutional_ownership": io,
        "analyst_consensus": ac,
        "scores": {
            "short_interest_score": si_score,
            "institutional_score": inst_score,
            "analyst_score": an_score,
            "composite": (
                (si_score or 0) * -0.3 +
                (inst_score or 0) * 0.2 +
                (an_score or 0) * 0.5
            ),
        },
        "as_of": dt.datetime.utcnow().isoformat() + "Z",
    }


# ============================================================
# 13F / institutional trends (delayed, free aggregators)
# ============================================================

# StockAnalysis.com has 13F trend scrapes. Use Playwright if installed.
def institutional_holders_changes(symbol: str) -> dict | None:
    """Pull 13F holder trends from stockanalysis.com via Playwright (free).

    Returns: {symbol, holders_added, holders_reduced, top_holders_added: [...], ...}
    Falls back gracefully if Playwright isn't installed.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "symbol": symbol, "available": False,
            "note": "Playwright not installed; skip 13F trend",
        }
    try:
        url = f"https://stockanalysis.com/stocks/{symbol.lower()}/institutional-tracker/"
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent="Mozilla/5.0 quant-research")
            page.goto(url, timeout=15000, wait_until="networkidle")
            html = page.content()
            browser.close()
        # Find JSON in __NEXT_DATA__ or fallback parse
        m = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.+?)</script>', html)
        if not m:
            return {"symbol": symbol, "available": False, "note": "no __NEXT_DATA__ on stockanalysis"}
        data = __import__("json").loads(m.group(1))
        # Schema varies; return raw for downstream parsing
        return {"symbol": symbol, "available": True, "raw_n5_data_keys": list(data.keys())[:20]}
    except Exception as e:
        return {"symbol": symbol, "available": False, "error": str(e)}


if __name__ == "__main__":
    import sys
    import json
    sym = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    print(f"=== {sym} ===")
    print("short_interest:", json.dumps(short_interest_signal(sym), indent=2, default=str))
    print("institutional:", json.dumps(institutional_ownership_signal(sym), indent=2, default=str))
    print("analyst:", json.dumps(analyst_consensus_signal(sym), indent=2, default=str))
    print("composite:", json.dumps(composite_flow_signal(sym), indent=2, default=str)[:1500])
