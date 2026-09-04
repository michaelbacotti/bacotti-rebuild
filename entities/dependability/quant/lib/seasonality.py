"""seasonality.py — calendar-driven market behavior signals.

Pure computation, no network calls except historical price pulls.
Provides:
  - Day-of-week drift filter
  - Month-of-year seasonality (1Y lookback)
  - Earnings-event-window PEAD (post-earnings announcement drift)
  - Days-to-event proximity flag

Citations: every function returns structured data with the lookback window used
and computed-on date. Numbers are derived from yfinance price_history, not memory.
"""
from __future__ import annotations
import datetime as dt
import math
from typing import Any

from data_fetcher import price_history


def day_of_week_drift(symbol: str, lookback_years: int = 1) -> dict | None:
    """Compute average daily return by day-of-week for the lookback window.

    Returns dict like {'mon': 0.0012, 'tue': -0.0005, ...}
    or None if data unavailable.
    """
    import pandas as pd
    df = price_history(symbol, period=f"{lookback_years}y", interval="1d")
    if df is None or df.empty or len(df) < 30:
        return None
    df = df.copy()
    df["dow"] = pd.to_datetime(df.index).dayofweek
    df["ret"] = df["Close"].pct_change()
    by_dow = df.groupby("dow")["ret"].agg(["mean", "std", "count"]).to_dict("index")
    # python weekday: Mon=0
    labels = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri"}
    out = {}
    for k, v in by_dow.items():
        out[labels.get(k, str(k))] = {
            "avg_daily_return": v["mean"],
            "std": v["std"],
            "n_obs": int(v["count"]),
        }
    return {"symbol": symbol, "window_days": len(df), "by_dow": out}


def month_of_year_drift(symbol: str, lookback_years: int = 3) -> dict | None:
    """Compute average monthly return for the last `lookback_years` years.

    Returns dict mapping 'YYYY-MM' -> total return for that month.
    Also returns per-month-of-year aggregate across the window.
    """
    import pandas as pd
    df = price_history(symbol, period=f"{lookback_years}y", interval="1d")
    if df is None or df.empty or len(df) < 60:
        return None
    df = df.copy()
    df["year_month"] = pd.to_datetime(df.index).strftime("%Y-%m")
    df["month"] = pd.to_datetime(df.index).month
    monthly_returns = df.groupby("year_month")["Close"].agg(
        first_close=lambda x: x.iloc[0],
        last_close=lambda x: x.iloc[-1],
        n_obs="count",
    )
    monthly_returns["ret"] = (monthly_returns["last_close"] - monthly_returns["first_close"]) / monthly_returns["first_close"]
    by_year_month = monthly_returns["ret"].to_dict()
    # Aggregate by month-of-year
    monthly_returns_df = monthly_returns.reset_index()
    monthly_returns_df["month_num"] = pd.to_datetime(monthly_returns_df["year_month"]).dt.month
    by_month = monthly_returns_df.groupby("month_num")["ret"].agg(["mean", "median", "std", "count"]).to_dict("index")
    month_labels = {1:'jan',2:'feb',3:'mar',4:'apr',5:'may',6:'jun',7:'jul',8:'aug',9:'sep',10:'oct',11:'nov',12:'dec'}
    out_by_month = {}
    for k, v in by_month.items():
        out_by_month[month_labels.get(int(k), str(k))] = {
            "avg_monthly_return": v["mean"],
            "median_monthly_return": v["median"],
            "std": v["std"],
            "n_obs": int(v["count"]),
        }
    return {
        "symbol": symbol,
        "lookback_years": lookback_years,
        "by_year_month": {k: float(v) for k, v in by_year_month.items()},
        "by_month_of_year": out_by_month,
    }


def earnings_window_drift(symbol: str, days: int = 5) -> dict | None:
    """Compute avg cumulative return in the N-day window after each earnings event.

    Uses earningsCalendar dates (or fallback to detecting large-volume days). 
    Returns dict with mean_reaction_5d, hit_rate, n_events.

    Note: yfinance's Ticker.calendar is sparse. We approximate by detecting "earnings-like"
    volume spikes (>2x 20d average volume) and computing post-spike drift.
    """
    import pandas as pd
    df = price_history(symbol, period="2y", interval="1d")
    if df is None or df.empty or len(df) < 100:
        return None
    df = df.copy()
    df["vol_20d_avg"] = df["Volume"].rolling(20).mean()
    df["vol_spike"] = df["Volume"] > 2.0 * df["vol_20d_avg"]
    event_indices = df[df["vol_spike"]].index.tolist()
    if not event_indices:
        return None
    forward_returns = []
    for event_date in event_indices:
        try:
            pos = df.index.get_loc(event_date)
            if isinstance(pos, slice):
                pos = pos.start
            if pos + days >= len(df):
                continue
            start_close = df["Close"].iloc[pos]
            end_close = df["Close"].iloc[pos + days]
            forward_returns.append((end_close - start_close) / start_close)
        except Exception:
            continue
    if not forward_returns:
        return None
    n = len(forward_returns)
    avg_ret = sum(forward_returns) / n
    pos_count = sum(1 for r in forward_returns if r > 0)
    median = sorted(forward_returns)[n // 2]
    # std dev
    var = sum((r - avg_ret) ** 2 for r in forward_returns) / max(1, n - 1)
    std = math.sqrt(var)
    return {
        "symbol": symbol,
        "window_days": days,
        "n_events": n,
        "avg_cumulative_return": avg_ret,
        "median_cumulative_return": median,
        "std": std,
        "positive_hit_rate": pos_count / n,
    }


def days_to_next_event(symbol: str, today: dt.date | None = None) -> dict | None:
    """Days until next earnings, dividend ex-date, etc.

    Returns dict with days_to_earnings, days_to_exdiv, days_to_dividend_pay.
    None if no data.
    """
    from data_fetcher import fundamentals_snapshot
    if today is None:
        today = dt.date.today()
    info = fundamentals_snapshot(symbol)
    if not info:
        return None
    out = {"symbol": symbol, "as_of": today.isoformat()}
    ets = info.get("earningsTimestamp")
    if ets and isinstance(ets, (int, float)):
        try:
            ed = dt.datetime.utcfromtimestamp(int(ets)).date()
            out["days_to_earnings"] = (ed - today).days
            out["next_earnings_date"] = ed.isoformat()
        except Exception:
            pass
    ex = info.get("exDividendDate")
    if ex and isinstance(ex, (int, float)):
        try:
            ed = dt.datetime.utcfromtimestamp(int(ex)).date()
            out["days_to_exdiv"] = (ed - today).days
            out["next_exdiv_date"] = ed.isoformat()
        except Exception:
            pass
    return out


def regime_assessment(symbol: str) -> dict | None:
    """Quick regime read using realized vol + recent price trend.

    Categories (per skills doctrine #6):
      - Calm:     realized_vol < 15%
      - Normal:   15% <= RV < 25%
      - Elevated: 25% <= RV < 40%
      - Stressed: RV >= 40%

    Returns dict with realized_vol (20d, annualized), regime, trend_signal.
    """
    from data_fetcher import realized_volatility, price_history
    rv20 = realized_volatility(symbol, window_days=20)
    rv60 = realized_volatility(symbol, window_days=60)
    if rv20 is None:
        return None
    if rv20 < 0.15:
        regime = "calm"
    elif rv20 < 0.25:
        regime = "normal"
    elif rv20 < 0.40:
        regime = "elevated"
    else:
        regime = "stressed"
    hist = price_history(symbol, period="3mo", interval="1d")
    trend = None
    if hist is not None and not hist.empty and len(hist) >= 50:
        closes = hist["Close"]
        ma20 = closes.rolling(20).mean().iloc[-1]
        ma50 = closes.rolling(50).mean().iloc[-1] if len(closes) >= 50 else ma20
        spot = closes.iloc[-1]
        if spot > ma20 > ma50:
            trend = "uptrend"
        elif spot < ma20 < ma50:
            trend = "downtrend"
        else:
            trend = "range-bound"
    return {
        "symbol": symbol,
        "realized_vol_20d": rv20,
        "realized_vol_60d": rv60,
        "regime": regime,
        "trend_3mo": trend,
        "as_of": dt.datetime.utcnow().isoformat() + "Z",
    }


if __name__ == "__main__":
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "SPY"
    print(f"=== {sym} ===")
    print("day_of_week:", day_of_week_drift(sym))
    print("month_of_year:", month_of_year_drift(sym))
    print("earnings_window:", earnings_window_drift(sym))
    print("days_to_event:", days_to_next_event(sym))
    print("regime:", regime_assessment(sym))
