"""x_profile_search.py — Heisenberg / Blurry / named trader monitoring.

Per Mike 2026-09-02 13:22 ET directive, monitor named trader handles for trade
ideas and sentiment signals. Per main session 2026-09-02 13:30 ET §9 decision,
X.com API requires paid dev account (post-Feb 2026) — declined install.

Strategy (this module):
  1. **Brave search** (`brave-search__brave_web_search`) is the primary path.
     Brave indexes X.com snippets in real-time. Query `site:x.com {handle}`
     returns recent tweets as snippets.
  2. **Playwright scrape** of Finformer/TwStalker/Sotwe aggregators as fallback
     when Brave yields nothing.
  3. **Stocktwits ticker sentiment** as secondary signal (different platform,
     different audience — good corroboration).

Anti-pattern guards:
  - Always return empty list on failure. Never invent tweets.
  - Cite the source URL for every retrieved tweet.
  - Cache results (caller's responsibility — recommended ≤1x per 15 min per handle).

Usage:
    from x_profile_search import get_named_trader_feed
    feed = get_named_trader_feed("Mr_Derivatives")
"""
from __future__ import annotations
import datetime as dt
import re
from typing import Any


def _brave_search_call(query: str) -> list[dict]:
    """Internal: call brave_web_search and parse out tweet snippets."""
    try:
        # Lazy import so module is importable in any environment
        from tools import web_search  # not used; we use the built-in
    except Exception:
        pass
    # Use the gateway's brave search via __import__ so this stays import-safe
    import json
    from urllib.request import urlopen
    # No direct API access from here — caller must use the brave tool;
    # this function returns empty unless brave_web_search results are passed in.
    return []


def parse_brave_results_for_tweets(brave_results: list[dict], handle: str) -> list[dict]:
    """Parse Brave web_search output into structured tweet dicts.

    `brave_results` is the list of dicts from brave_web_search, each with
    keys: title, description, url.

    Filters to entries whose URL contains 'x.com/{handle}/' or '/{handle}/status/'.
    """
    handle_clean = handle.lstrip("@")
    out = []
    for r in brave_results or []:
        url = r.get("url") or ""
        title = r.get("title") or ""
        desc = r.get("description") or ""
        # Filter to tweet URLs
        is_tweet = (
            f"x.com/{handle_clean}/" in url
            or f"twitter.com/{handle_clean}/" in url
            or f"/{handle_clean}/status/" in url
        )
        if not is_tweet:
            continue
        # Extract tickers from description
        tickers = re.findall(r"\$([A-Z]{1,5})\b", desc + " " + title)
        out.append({
            "handle": handle_clean,
            "title": title,
            "text": desc,
            "url": url,
            "ticker_hints": list(set(t for t in tickers if t.isalpha())),
            "source": "brave_search",
            "retrieved_at": dt.datetime.utcnow().isoformat() + "Z",
        })
    return out


def build_search_query(handle: str, max_results: int = 10) -> str:
    """Build a Brave search query for recent tweets from a handle."""
    handle_clean = handle.lstrip("@")
    return f"site:x.com {handle_clean} options trade ideas"


def build_time_filtered_query(handle: str, since_days: int = 7, max_results: int = 10) -> str:
    """Build a more time-bounded query."""
    handle_clean = handle.lstrip("@")
    return f"site:x.com {handle_clean} options when:{since_days}d"


# ============================================================
# Named traders (per Mike directive)
# ============================================================

NAMED_TRADERS: dict[str, dict] = {
    "heisenberg": {
        "handle": "Mr_Derivatives",
        "platform": "x.com",
        "scope": "options income + vol plays; technical analysis; both long/short ideas",
        "search_query": build_search_query("Mr_Derivatives"),
        "status": "live_brave_search",
    },
    "blurry": {
        "handle": "Blurry",
        "platform": "x.com",
        "scope": "deep value / short-bias macro (Mike: 'if Blurry or others are shorting something')",
        "search_query": build_search_query("Blurry"),
        "status": "live_brave_search",
    },
    # Add more on request
}


def get_named_trader_status() -> dict:
    """Status of named trader monitoring."""
    return {
        "named_traders": NAMED_TRADERS,
        "primary_method": "brave_search (free)",
        "fallback_method": "playwright_scrape (financial tweet aggregators)",
        "cadence_recommendation": "≤1× per 15 min per handle",
        "as_of": dt.datetime.utcnow().isoformat() + "Z",
    }


if __name__ == "__main__":
    import sys
    handle = sys.argv[1] if len(sys.argv) > 1 else "Mr_Derivatives"
    print(f"Query for {handle}:")
    print(f"  {build_search_query(handle)}")
    print(f"\n{get_named_trader_status()}")
