"""Earnings calendar adapter for Dependability Quant.

Uses yfinance to fetch upcoming + recent earnings dates for any ticker.
Per doctrine #1, every fact is tool-derived — no memory-based claims about earnings dates.
Per Mike 14:10 ET directive + v2 governance: "consider realtime data and news when considering option spreads."

Usage:
    from lib.earnings_calendar import Calendar
    cal = Calendar(["PANW", "DELL", "AAPL"])
    print(cal.upcoming())   # filters to future earnings dates
    print(cal.upcoming(days=7))  # within 7 days

CLI:
    python3 lib/earnings_calendar.py [TICKER ...] [--days N] [--recent N]
"""

from __future__ import annotations

import sys
import json
import datetime as dt
from dataclasses import dataclass, field
from typing import Any

import yfinance as yf


@dataclass
class EarningsEvent:
    symbol: str
    date: dt.date
    """Earnings date (or release date if confirmed)."""
    eps_estimate: float | None = None
    eps_actual: float | None = None
    revenue_estimate: float | None = None
    revenue_actual: float | None = None
    is_past: bool = False
    source: str = "yfinance.Ticker.calendar"
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "date": self.date.isoformat(),
            "eps_estimate": self.eps_estimate,
            "eps_actual": self.eps_actual,
            "revenue_estimate": self.revenue_estimate,
            "revenue_actual": self.revenue_actual,
            "is_past": self.is_past,
            "source": self.source,
        }


def _to_date(value: Any) -> dt.date | None:
    """yfinance returns earnings dates as pandas Timestamp, ISO string, or datetime."""
    if value is None:
        return None
    if hasattr(value, "date"):
        return value.date()
    if isinstance(value, str):
        try:
            return dt.date.fromisoformat(value.split("T")[0])
        except ValueError:
            return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return None


def fetch_event(symbol: str) -> EarningsEvent | None:
    """Fetch upcoming earnings for a symbol. Returns None if no data."""
    try:
        t = yf.Ticker(symbol)
        cal = t.calendar
        if cal is None:
            return None
        # yfinance returns calendar as dict or DataFrame depending on version
        if hasattr(cal, "to_dict"):
            cal_dict = cal.to_dict()
            flat = {}
            if isinstance(cal_dict, dict):
                for k, v in cal_dict.items():
                    if isinstance(v, dict):
                        flat[k] = next(iter(v.values())) if v else None
                    else:
                        flat[k] = v
        else:
            flat = dict(cal)
        # Earnings Date may be a list (typical) or scalar
        earnings_date_raw = flat.get("Earnings Date")
        if earnings_date_raw is None:
            return None
        if isinstance(earnings_date_raw, list):
            if not earnings_date_raw:
                return None
            earnings_date = _to_date(earnings_date_raw[0])
        else:
            earnings_date = _to_date(earnings_date_raw)
        if earnings_date is None:
            return None
        # Field names vary: 'EPS Estimate', 'Earnings Average', 'Earnings High/Low', etc.
        eps = flat.get("EPS Estimate") or flat.get("Earnings Average")
        rev = flat.get("Revenue Estimate") or flat.get("Revenue Average")
        today = dt.date.today()
        return EarningsEvent(
            symbol=symbol,
            date=earnings_date,
            eps_estimate=eps,
            revenue_estimate=rev,
            is_past=earnings_date < today,
            source=f"yfinance.Ticker('{symbol}').calendar",
        )
    except Exception as e:
        print(f"WARN: {symbol} calendar fetch failed: {e}", file=sys.stderr)
        return None


class Calendar:
    """Multi-symbol earnings calendar."""
    
    def __init__(self, symbols: list[str]):
        self.symbols = list(symbols)
        self.events: list[EarningsEvent] = []
        self._errors: list[tuple[str, str]] = []
        for sym in symbols:
            ev = fetch_event(sym)
            if ev is not None:
                self.events.append(ev)
    
    @property
    def errors(self) -> list[tuple[str, str]]:
        return list(self._errors)
    
    def upcoming(self, days: int | None = None) -> list[EarningsEvent]:
        today = dt.date.today()
        out = [e for e in self.events if not e.is_past and e.date >= today]
        if days is not None:
            cutoff = today + dt.timedelta(days=days)
            out = [e for e in out if e.date <= cutoff]
        return sorted(out, key=lambda e: e.date)
    
    def recent(self, n: int = 5) -> list[EarningsEvent]:
        out = [e for e in self.events if e.is_past]
        return sorted(out, key=lambda e: e.date, reverse=True)[:n]
    
    def all_events(self) -> list[EarningsEvent]:
        return sorted(self.events, key=lambda e: e.date)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "as_of": dt.date.today().isoformat(),
            "symbols_queried": self.symbols,
            "events": [e.to_dict() for e in self.all_events()],
            "errors": [{"symbol": s, "error": err} for s, err in self._errors],
        }


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Earnings calendar adapter (Dependability Quant)")
    p.add_argument("symbols", nargs="*", help="Tickers to query (default: universe.yaml Tier 3)")
    p.add_argument("--days", type=int, default=None, help="Filter to within N days")
    p.add_argument("--recent", type=int, default=5, help="Recent N past events to print")
    p.add_argument("--json", action="store_true", help="Output JSON")
    args = p.parse_args()
    
    if not args.symbols:
        # default to PANW + DELL + SPY
        args.symbols = ["PANW", "DELL", "AAPL", "MSFT", "SPY"]
    
    cal = Calendar(args.symbols)
    
    if args.json:
        print(json.dumps(cal.to_dict(), indent=2, default=str))
    else:
        print(f"\n=== Upcoming earnings (as of {dt.date.today().isoformat()}) ===")
        up = cal.upcoming(days=args.days)
        if not up:
            print("  (none within window)")
        for e in up:
            days_away = (e.date - dt.date.today()).days
            print(f"  {e.symbol:6s} {e.date.isoformat()} ({days_away}d)  EPS est: {e.eps_estimate}")
        
        print(f"\n=== Recent past ({args.recent}) ===")
        recent = cal.recent(args.recent)
        if not recent:
            print("  (none)")
        for e in recent:
            days_ago = (dt.date.today() - e.date).days
            print(f"  {e.symbol:6s} {e.date.isoformat()} ({days_ago}d ago)")
