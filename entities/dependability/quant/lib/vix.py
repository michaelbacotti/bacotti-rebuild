"""vix.py — VIX spot quote for regime/trigger checks.

Uses yfinance (already installed in skills/public-com/.venv, v1.4.1).
Returns the most recent close. ~15-min delayed on free tier; acceptable for
cron fires at 10:15 ET (after market open) where we're checking the prior
session's VIX close.

If yfinance is unavailable, returns None (caller treats as 'unknown regime').
"""
from __future__ import annotations
import datetime
from typing import Optional


def get_vix_now() -> Optional[dict]:
    """Return latest VIX close + metadata, or None on failure.

    Output schema:
      {'last': float, 'as_of': ISO-8601 string, 'previous_close': float | None,
       'fetched_at': ISO-8601 string, 'source': 'yfinance:^VIX'}
    """
    try:
        import yfinance as yf
    except ImportError:
        return None
    try:
        t = yf.Ticker("^VIX")
        h = t.history(period="5d")
        if h is None or h.empty:
            return None
        last = float(h['Close'].iloc[-1])
        as_of = h.index[-1].to_pydatetime().isoformat() if hasattr(h.index[-1], 'to_pydatetime') else str(h.index[-1])
        prev = float(h['Close'].iloc[-2]) if len(h) > 1 else None
        return {
            'last': last,
            'as_of': as_of,
            'previous_close': prev,
            'fetched_at': datetime.datetime.now().astimezone().isoformat(),
            'source': 'yfinance:^VIX',
        }
    except Exception:
        return None


def regime_classifier(vix_last: Optional[float]) -> dict:
    """Classify VIX level per typical market-regime heuristics.

    Bands (rough, not doctrine):
      <12  = extremely low / complacent
      12-18 = low / calm
      18-25 = normal
      25-35 = elevated / cautious
      >35  = stressed / defensive

    risk_mode.yaml#auto_suggest_triggers would map these to cautious or flat_research_only.
    """
    if vix_last is None:
        return {'regime': 'unknown', 'band': None, 'auto_suggest_mode': None}
    if vix_last < 12:
        return {'regime': 'extremely_low', 'band': '<12', 'auto_suggest_mode': None}
    elif vix_last < 18:
        return {'regime': 'low', 'band': '12-18', 'auto_suggest_mode': None}
    elif vix_last < 25:
        return {'regime': 'normal', 'band': '18-25', 'auto_suggest_mode': None}
    elif vix_last < 35:
        return {'regime': 'elevated', 'band': '25-35', 'auto_suggest_mode': 'cautious'}
    else:
        return {'regime': 'stressed', 'band': '>35', 'auto_suggest_mode': 'flat_research_only'}


if __name__ == '__main__':
    out = get_vix_now()
    print(f"VIX: {out}")
    if out:
        print(f"Regime: {regime_classifier(out['last'])}")
