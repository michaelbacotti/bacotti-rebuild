"""event_signals.py — Real-time event/positioning/social signals per ticker.

Wraps existing data_fetcher.news(), institutional_flow.*, and social_sentiment.*
into a single normalized dict per ticker that can be plugged into ClawRank
as new sub-factors.

Anti-hallucination: every field has a source citation. Missing data → None.
Empty inputs (e.g., ETFs with no sharesShort) handled gracefully.

Output schema per ticker:
  {
    'ticker': 'JPM',
    'news_count_7d': int | None,             # data_fetcher.news() count
    'news_sentiment_avg': float | None,      # -1.0 (bearish) to +1.0 (bullish)
    'short_interest_change_pct': float | None, # MoM change; negative = bullish
    'short_interest_pct_float': float | None,
    'institutional_pct': float | None,        # 0.0 to 1.0
    'insider_pct': float | None,
    'stocktwits_bullish_pct': float | None,
    'stocktwits_bearish_pct': float | None,
    'stocktwits_n': int | None,
    'as_of': ISO timestamp string,
  }
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Any

from data_fetcher import news
from institutional_flow import short_interest_signal, institutional_ownership_signal
from social_sentiment import stocktwits_symbol


# ============================================================
# Keyword-based news sentiment scoring (simple, debuggable)
# ============================================================

_BULLISH_KEYWORDS = {
    "surge", "beat", "beats", "rally", "rallies", "upgraded", "upgrade",
    "breakout", "high", "highs", "gain", "gains", "strong", "strength",
    "bullish", "boom", "soar", "soars", "record", "outperform", "outperforms",
    "raise", "raises", "raised", "growth", "growing", "win", "wins",
    "approve", "approved", "approval", "positive", "optimistic", "buy",
    "buys", "buying", "ath", "all-time high", "expansion", "expand", "expands",
}

_BEARISH_KEYWORDS = {
    "fall", "falls", "falling", "miss", "misses", "downgrade", "downgrades",
    "plunge", "plunges", "low", "lows", "loss", "losses", "weak", "weakness",
    "bearish", "crash", "crashes", "drop", "drops", "dropped", "tumble",
    "tumbles", "concern", "concerns", "warn", "warns", "warning", "fear",
    "sell", "sells", "selling", "layoff", "layoffs", "cut", "cuts", "probe",
    "investigation", "fraud", "lawsuit", "negative", "risk", "risks", "halt",
}


def _score_text(text: str) -> float:
    """Return sentiment score in [-1.0, +1.0] from a single news headline/title."""
    if not text:
        return 0.0
    words = re.findall(r"[a-zA-Z']+", text.lower())
    if not words:
        return 0.0
    bull = sum(1 for w in words if w in _BULLISH_KEYWORDS)
    bear = sum(1 for w in words if w in _BEARISH_KEYWORDS)
    if bull == 0 and bear == 0:
        return 0.0
    return (bull - bear) / max(bull + bear, 1)


def _avg_sentiment(headlines: list) -> float | None:
    """Average sentiment score across headlines. None if no headlines."""
    if not headlines:
        return None
    scores = [_score_text(h) for h in headlines if h]
    if not scores:
        return None
    return sum(scores) / len(scores)


# ============================================================
# Main entry point
# ============================================================

def event_signals_for(
    ticker: str,
    news_limit: int = 30,
    stocktwits_limit: int = 30,
    quiet: bool = True,
) -> dict:
    """Build event/positioning/social signal dict for a ticker.

    Quiet mode (default) suppresses per-ticker errors. Set quiet=False for debug.
    """
    out = {
        "ticker": ticker,
        "news_count_7d": None,
        "news_sentiment_avg": None,
        "short_interest_change_pct": None,
        "short_interest_pct_float": None,
        "institutional_pct": None,
        "insider_pct": None,
        "stocktwits_bullish_pct": None,
        "stocktwits_bearish_pct": None,
        "stocktwits_n": None,
        "as_of": dt.datetime.now(dt.timezone.utc).isoformat(),
    }

    # News (yfinance news feed)
    try:
        news_items = news(ticker, news_limit)
        out["news_count_7d"] = len(news_items)
        headlines = []
        for it in news_items:
            if isinstance(it, dict):
                title = it.get("title") or ""
                summary = it.get("summary") or ""
                if title:
                    headlines.append(title)
                if summary:
                    headlines.append(summary[:200])
        sent = _avg_sentiment(headlines)
        out["news_sentiment_avg"] = sent
    except Exception as e:
        if not quiet:
            print(f"  news fetch failed for {ticker}: {e}")

    # Short interest (only for non-ETFs)
    try:
        si = short_interest_signal(ticker)
        if si:
            out["short_interest_change_pct"] = si.get("mom_change_pct")
            out["short_interest_pct_float"] = si.get("pct_of_float")
    except Exception as e:
        if not quiet:
            print(f"  short_interest fetch failed for {ticker}: {e}")

    # Institutional ownership (only for non-ETFs)
    try:
        io = institutional_ownership_signal(ticker)
        if io:
            out["institutional_pct"] = io.get("institutional_pct")
            out["insider_pct"] = io.get("insider_pct")
    except Exception as e:
        if not quiet:
            print(f"  institutional_ownership fetch failed for {ticker}: {e}")

    # Stocktwits (works for both stocks and ETFs)
    try:
        st = stocktwits_symbol(ticker, limit=stocktwits_limit)
        if st and st.get("n_messages"):
            out["stocktwits_bullish_pct"] = st.get("bullish_pct")
            out["stocktwits_bearish_pct"] = st.get("bearish_pct")
            out["stocktwits_n"] = st.get("n_messages")
    except Exception as e:
        if not quiet:
            print(f"  stocktwits fetch failed for {ticker}: {e}")

    return out


def batch_event_signals(tickers: list[str], quiet: bool = True) -> dict[str, dict]:
    """Build event signals for a list of tickers. Returns dict[ticker] -> signal dict."""
    out = {}
    for t in tickers:
        out[t] = event_signals_for(t, quiet=quiet)
    return out
