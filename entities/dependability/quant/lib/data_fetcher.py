"""data_fetcher.py — single source of free market data for quant research.

Pulls from yfinance, Public.com scripts, and web sources. No paid API dependencies.

Every function returns structured data with explicit timestamps. Anti-hallucination:
- Every claim in a downstream report that comes from this module must cite
  the function name + invocation timestamp.
- If the underlying source returns None/empty, the function returns None/[] —
  never synthesize.

Use:
    from data_fetcher import (
        fundamentals_snapshot,        # yfinance .info
        short_interest,               # yfinance short interest
        institutional_holdings,       # yfinance heldPercentInstitutions
        analyst_targets,             # yfinance target prices
        price_history,               # yfinance .history
        dividend_calendar,           # yfinance ex-dividend + dividend rate
        earnings_calendar_today,     # uses lib/earnings_calendar.py
        options_chain_full,          # lib/fetch_chain.py
        IV_term_structure,           # per-expiry ATM IV
    )
"""
from __future__ import annotations
import datetime as dt
from typing import Any
import yfinance as yf

# ============================================================
# Single-ticker snapshot
# ============================================================

def fundamentals_snapshot(symbol: str) -> dict | None:
    """Pull yfinance .info for a symbol. Returns dict or None on failure.

    Key fields available (free):
      - beta, marketCap, trailingPE, forwardPE, pegRatio, priceToBook
      - heldPercentInsiders, heldPercentInstitutions
      - sharesShort, shortRatio, shortPercentOfFloat
      - earningsTimestamp, earningsGrowth, epsForward, epsTrailingTwelveMonths
      - recommendationKey, recommendationMean (1=strong buy, 5=strong sell)
      - targetMeanPrice, targetHighPrice, targetLowPrice
      - dividendRate, dividendYield, exDividendDate, lastDividendValue
      - fiftyDayAverageChangePercent, fiftyTwoWeekChangePercent
      - sector, industry
    """
    try:
        t = yf.Ticker(symbol)
        return t.info or None
    except Exception:
        return None


def short_interest(symbol: str) -> dict | None:
    """Extract short interest data from yfinance.

    Returns dict with: shares_short, shares_short_prior_month, days_to_cover (shortRatio),
    pct_of_float, change_pct (current vs prior). None if unavailable.
    """
    info = fundamentals_snapshot(symbol)
    if not info:
        return None
    short_now = info.get("sharesShort")
    short_prior = info.get("sharesShortPriorMonth")
    if short_now is None:
        return None
    change = None
    if short_now is not None and short_prior and short_prior > 0:
        change = (short_now - short_prior) / short_prior
    return {
        "symbol": symbol,
        "shares_short": short_now,
        "shares_short_prior_month": short_prior,
        "pct_of_float": info.get("shortPercentOfFloat"),
        "days_to_cover": info.get("shortRatio"),
        "change_pct_mom": change,
        "as_of": info.get("dateShortInterest"),  # epoch seconds (Finra report date)
    }


def institutional_holdings(symbol: str) -> dict | None:
    """Extract institutional + insider ownership percentages.

    Returns dict or None.
    """
    info = fundamentals_snapshot(symbol)
    if not info:
        return None
    inst = info.get("heldPercentInstitutions")
    insider = info.get("heldPercentInsiders")
    if inst is None and insider is None:
        return None
    return {
        "symbol": symbol,
        "institutional_pct": inst,
        "insider_pct": insider,
        "market_cap": info.get("marketCap"),
        "shares_outstanding": info.get("sharesOutstanding"),
        "as_of": dt.datetime.utcnow().isoformat() + "Z",
    }


def analyst_targets(symbol: str) -> dict | None:
    """Analyst consensus targets and ratings.

    Returns dict with mean/high/low targets, recommendationMean (1-5 scale),
    and earnings call timestamp.
    """
    info = fundamentals_snapshot(symbol)
    if not info:
        return None
    return {
        "symbol": symbol,
        "mean_target": info.get("targetMeanPrice"),
        "high_target": info.get("targetHighPrice"),
        "low_target": info.get("targetLowPrice"),
        "mean_rating": info.get("recommendationMean"),  # 1.0 (strong buy) - 5.0 (strong sell)
        "rating_label": info.get("recommendationKey"),  # 'buy', 'hold', 'sell'
        "earnings_call_timestamp": info.get("earningsCallTimestamp"),
        "earnings_call_range": (
            f"{info.get('earningsTimestampStart')} - {info.get('earningsTimestampEnd')}"
            if info.get("earningsTimestampStart") else None
        ),
        "as_of": dt.datetime.utcnow().isoformat() + "Z",
    }


def price_history(symbol: str, period: str = "3mo", interval: str = "1d") -> Any:
    """OHLCV history from yfinance. period: '1mo','3mo','6mo','1y','2y','5y','10y','ytd','max'.
    interval: '1d','1h','15m','5m','1m' etc.

    Returns a pandas DataFrame with index = DatetimeIndex (tz-aware), columns = Open/High/Low/Close/Volume.
    """
    try:
        t = yf.Ticker(symbol)
        return t.history(period=period, interval=interval)
    except Exception:
        return None


def dividend_calendar(symbol: str) -> dict | None:
    """Dividend info from yfinance.

    Returns dict with dividend_rate, dividend_yield, ex_dividend_date, last_div_value,
    last_div_date. None if no dividends.
    """
    info = fundamentals_snapshot(symbol)
    if not info:
        return None
    rate = info.get("dividendRate")
    if rate is None or rate == 0:
        return None
    return {
        "symbol": symbol,
        "dividend_rate_annual": rate,
        "dividend_yield_pct": info.get("dividendYield"),
        "ex_dividend_date_epoch": info.get("exDividendDate"),
        "last_dividend_value": info.get("lastDividendValue"),
        "last_dividend_date_epoch": info.get("lastDividendDate"),
        "as_of": dt.datetime.utcnow().isoformat() + "Z",
    }


def news(symbol: str, max_items: int = 10) -> list[dict]:
    """Recent news for a symbol from yfinance.

    Returns list of dicts with id/title/publisher/published/link/content.
    Empty list on failure.
    """
    try:
        t = yf.Ticker(symbol)
        items = t.news or []
        out = []
        for raw in items[:max_items]:
            # yfinance 1.7+ wraps content
            content = raw.get("content", raw) if isinstance(raw, dict) else {}
            title = content.get("title") if isinstance(content, dict) else None
            if not title and isinstance(raw, dict):
                title = raw.get("title")
            pub = content.get("provider") if isinstance(content, dict) else None
            if pub and isinstance(pub, dict):
                pub = pub.get("displayName")
            published = content.get("pubDate") if isinstance(content, dict) else None
            link = content.get("canonicalUrl") if isinstance(content, dict) else None
            if link and isinstance(link, dict):
                link = link.get("url")
            summary = content.get("summary") if isinstance(content, dict) else None
            out.append({
                "id": raw.get("id"),
                "title": title,
                "publisher": pub,
                "published_epoch": published,
                "url": link,
                "summary": summary,
            })
        return out
    except Exception:
        return []


# ============================================================
# Technical / vol history
# ============================================================

def realized_volatility(symbol: str, window_days: int = 20, period: str = "1y") -> float | None:
    """Annualized realized vol over the last `window_days` trading days.

    Uses log returns. Standard formula: sigma * sqrt(252).
    Returns None when fewer than 2 valid returns can be computed
    (empty history, all-NaN history, non-positive prices, NaN-tainted bars
    that leave an insufficient valid window). NaN-tolerant: bars with NaN
    Close are skipped; today's incomplete session is naturally excluded when
    its Close is NaN. Fix A 2026-09-02 20:30 ET.
    """
    import math
    df = price_history(symbol, period=period, interval="1d")
    if df is None or df.empty or len(df) < window_days + 1:
        return None
    closes = df["Close"].tail(window_days + 1).tolist()
    if len(closes) < window_days + 1:
        return None
    log_returns = []
    for i in range(1, len(closes)):
        p_prev, p_curr = closes[i - 1], closes[i]
        # both bars must be finite AND positive (NaN check + non-positive guard)
        if (
            isinstance(p_prev, (int, float))
            and isinstance(p_curr, (int, float))
            and p_prev == p_prev  # != NaN
            and p_curr == p_curr
            and p_prev > 0
            and p_curr > 0
        ):
            log_returns.append(math.log(p_curr / p_prev))
    if len(log_returns) < 2:
        return None  # insufficient valid returns
    mean = sum(log_returns) / len(log_returns)
    variance = sum((r - mean) ** 2 for r in log_returns) / (len(log_returns) - 1)
    if variance != variance or variance < 0:  # NaN / negative-variance guard
        return None
    daily_sigma = math.sqrt(variance)
    annualized = daily_sigma * math.sqrt(252)
    # Final sanity: must be finite and within a sane range [0, 5.0] (500% annualized)
    if annualized != annualized or annualized < 0 or annualized > 5.0:
        return None
    return annualized


def IV_term_structure(symbol: str, expirations: list[str] | None = None) -> dict | None:
    """Compute IV term structure: ATM IV for each expiration.

    Returns dict mapping expiration -> {iv, dte, straddle_mid, straddle_pct_of_spot}
    or None if data unavailable.
    """
    try:
        import math
        t = yf.Ticker(symbol)
        if expirations is None:
            expirations = list(t.options)[:8]
        hist = t.history(period="1d")
        if hist.empty:
            return None
        spot = float(hist["Close"].iloc[-1])
        struct = {}
        for exp in expirations:
            try:
                chain = t.option_chain(exp)
                calls, puts = chain.calls, chain.puts
                if calls.empty or puts.empty:
                    continue
                atm_call_idx = (calls["strike"] - spot).abs().idxmin()
                atm_put_idx = (puts["strike"] - spot).abs().idxmin()
                ac = calls.iloc[atm_call_idx]
                ap = puts.iloc[atm_put_idx]
                cm = (float(ac["bid"]) + float(ac["ask"])) / 2
                pm = (float(ap["bid"]) + float(ap["ask"])) / 2
                if cm <= 0 or pm <= 0:
                    continue
                straddle = cm + pm
                exp_dt = dt.datetime.strptime(exp, "%Y-%m-%d").date()
                dte = max(1, (exp_dt - dt.date.today()).days)
                # BKM: IV ≈ (straddle_mid / spot) * sqrt(365 / dte) [annualized]
                iv = (straddle / spot) * math.sqrt(365 / dte)
                struct[exp] = {
                    "dte": dte,
                    "iv": iv,
                    "straddle_mid": straddle,
                    "straddle_pct_of_spot": straddle / spot,
                }
            except Exception:
                continue
        return {"symbol": symbol, "spot": spot, "term_structure": struct}
    except Exception:
        return None


# ============================================================
# Market-wide / aggregate
# ============================================================

def index_spot(symbol: str) -> float | None:
    """Spot for an index ETF (SPY, QQQ, IWM, DIA, etc.) — yfinance."""
    try:
        h = yf.Ticker(symbol).history(period="1d")
        if h.empty:
            return None
        return float(h["Close"].iloc[-1])
    except Exception:
        return None


# ============================================================
# Sector / industry
# ============================================================

def sector_industry(symbol: str) -> dict | None:
    """Sector + industry for a symbol."""
    info = fundamentals_snapshot(symbol)
    if not info:
        return None
    sec = info.get("sector")
    ind = info.get("industry")
    if not (sec or ind):
        return None
    return {"symbol": symbol, "sector": sec, "industry": ind}


def describe(timestamp_only: bool = False) -> str:
    """Self-describe this module for reports."""
    return "data_fetcher.py — free market data via yfinance (fundamentals/short interest/institutional/analyst/IV term/realized vol/news)"


if __name__ == "__main__":
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    print(f"=== {sym} ===")
    print("fundamentals_snapshot:", list((fundamentals_snapshot(sym) or {}).keys())[:10])
    si = short_interest(sym)
    print("short_interest:", si)
    ih = institutional_holdings(sym)
    print("institutional_holdings:", ih)
    at = analyst_targets(sym)
    print("analyst_targets:", at)
    rv = realized_volatility(sym, 20)
    print(f"realized_vol(20d): {rv:.4f}" if rv else "no rv")
    its = IV_term_structure(sym)
    print("IV_term_structure:", its)
    print("news:", len(news(sym)))
