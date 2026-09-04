"""social_sentiment.py — free social sentiment signals.

Sources (no auth required):
  - Stocktwits public API (https://api.stocktwits.com/api/2/streams/symbol/{sym}.json)
  - Reddit public JSON (no auth, rate-limited)
  - Yahoo Finance news (via data_fetcher.news)
  - Web search for named trader handles (Heisenberg, Blurry, etc.)

Each function returns structured data with timestamps; sentiment-scored text
is returned as raw + classification (bullish/bearish/neutral) + numeric score.

Anti-hallucination: never invents social posts. Returns empty list on failure.
"""
from __future__ import annotations
import datetime as dt
import json
import re
import urllib.request
import urllib.parse
from typing import Any


# ============================================================
# Stocktwits
# ============================================================

def stocktwits_symbol(symbol: str, limit: int = 30) -> dict | None:
    """Pull recent Stocktwits messages for a symbol.

    Returns: {symbol, messages: [...], bullish_pct, bearish_pct, n_messages}
    Each message has: id, body (text), user (name), created_at, sentiment (auto-classified).
    """
    url = f"https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json?limit={limit}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "quant-research/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
    except Exception:
        return None
    msgs = data.get("messages", [])
    if not msgs:
        return {"symbol": symbol, "messages": [], "bullish_pct": None, "bearish_pct": None, "n_messages": 0}
    classified = []
    bull, bear, neutral = 0, 0, 0
    for m in msgs:
        body = m.get("body", "")
        sentiment = _classify_text(body)
        if sentiment == "bullish":
            bull += 1
        elif sentiment == "bearish":
            bear += 1
        else:
            neutral += 1
        classified.append({
            "id": m.get("id"),
            "body": body,
            "user": (m.get("user") or {}).get("username"),
            "created_at": m.get("created_at"),
            "sentiment": sentiment,
        })
    n = len(classified)
    return {
        "symbol": symbol,
        "messages": classified,
        "bullish_count": bull,
        "bearish_count": bear,
        "neutral_count": neutral,
        "n_messages": n,
        "bullish_pct": bull / n if n else None,
        "bearish_pct": bear / n if n else None,
        "as_of": dt.datetime.utcnow().isoformat() + "Z",
    }


# ============================================================
# Reddit (r/wallstreetbets, r/options, r/stocks)
# ============================================================

_REDDIT_SUBS = ["wallstreetbets", "options", "stocks", "investing"]

def reddit_symbol(symbol: str, limit_per_sub: int = 25) -> dict | None:
    """Search recent Reddit posts mentioning the symbol across trading subs.

    Primary: praw with stored Reddit OAuth credentials (REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET,
    REDDIT_USER_AGENT). Per main session 2026-09-02 §9, credentials are pending Mike's
    setup of an app at https://www.reddit.com/prefs/apps (free).

    Fallback: public Reddit JSON (returns 403 without OAuth but kept as a fallback for
    debugging).

    Returns: {symbol, posts: [...], bullish_pct, n_posts, source}
    """
    # Try praw first if credentials present
    try:
        import os
        import praw
        cid = os.environ.get("REDDIT_CLIENT_ID")
        csec = os.environ.get("REDDIT_CLIENT_SECRET")
        ua = os.environ.get("REDDIT_USER_AGENT", "quant-research/1.0")
        if cid and csec:
            reddit = praw.Reddit(
                client_id=cid,
                client_secret=csec,
                user_agent=ua,
                check_for_async=False,
            )
            all_posts = []
            for sub_name in _REDDIT_SUBS:
                sub = reddit.subreddit(sub_name)
                query = f"${symbol}"
                try:
                    for s in sub.search(query, sort="new", limit=limit_per_sub):
                        text = (s.title or "") + " " + (s.selftext or "")
                        sentiment = _classify_text(text)
                        all_posts.append({
                            "subreddit": sub_name,
                            "title": s.title,
                            "score": s.score,
                            "num_comments": s.num_comments,
                            "created_utc": s.created_utc,
                            "url": f"https://reddit.com{s.permalink}",
                            "sentiment": sentiment,
                        })
                except Exception:
                    continue
            if all_posts:
                bull = sum(1 for p in all_posts if p["sentiment"] == "bullish")
                bear = sum(1 for p in all_posts if p["sentiment"] == "bearish")
                neutral = len(all_posts) - bull - bear
                n = len(all_posts)
                return {
                    "symbol": symbol, "posts": all_posts,
                    "bullish_count": bull, "bearish_count": bear, "neutral_count": neutral,
                    "n_posts": n,
                    "bullish_pct": bull / n, "bearish_pct": bear / n,
                    "as_of": dt.datetime.utcnow().isoformat() + "Z",
                    "source": "praw_oauth",
                }
    except Exception:
        pass

    # Fallback to public JSON (likely 403)
    all_posts = []
    for sub in _REDDIT_SUBS:
        url = f"https://www.reddit.com/r/{sub}/search.json?q=${urllib.parse.quote(symbol)}&sort=new&limit={limit_per_sub}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "quant-research/1.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read())
        except Exception:
            continue
        children = data.get("data", {}).get("children", [])
        for c in children:
            d = c.get("data", {})
            text = (d.get("title") or "") + " " + (d.get("selftext") or "")
            sentiment = _classify_text(text)
            all_posts.append({
                "subreddit": sub,
                "title": d.get("title"),
                "score": d.get("score"),
                "num_comments": d.get("num_comments"),
                "created_utc": d.get("created_utc"),
                "url": "https://reddit.com" + (d.get("permalink") or ""),
                "sentiment": sentiment,
            })
    if not all_posts:
        return {
            "symbol": symbol, "posts": [],
            "bullish_count": 0, "bearish_count": 0, "neutral_count": 0,
            "n_posts": 0, "bullish_pct": None, "bearish_pct": None,
            "as_of": dt.datetime.utcnow().isoformat() + "Z",
            "note": "No Reddit credentials (REDDIT_CLIENT_ID/SECRET not set) AND public JSON blocked. Set env vars to enable praw.",
            "source": "none",
        }
    bull = sum(1 for p in all_posts if p["sentiment"] == "bullish")
    bear = sum(1 for p in all_posts if p["sentiment"] == "bearish")
    neutral = len(all_posts) - bull - bear
    n = len(all_posts)
    return {
        "symbol": symbol,
        "posts": all_posts,
        "bullish_count": bull,
        "bearish_count": bear,
        "neutral_count": neutral,
        "n_posts": n,
        "bullish_pct": bull / n,
        "bearish_pct": bear / n,
        "as_of": dt.datetime.utcnow().isoformat() + "Z",
        "source": "public_json_fallback",
    }


# ============================================================
# Simple bullish/bearish classifier
# ============================================================

_BULL = re.compile(
    r"\b(bullish|calls|long|moon|🚀|buy|undervalued|breakout|rally|surge|upgrade|beat|raise|strong|buy|squeeze|🚀|ATH|💎|🚀|yes|cope|short squeeze)\b",
    re.IGNORECASE,
)
_BEAR = re.compile(
    r"\b(bearish|puts|short|crash|dump|overvalued|sell|downgrade|miss|weak|lower|fall|decline|capitulate|cope|hedge|puts)\b",
    re.IGNORECASE,
)


def _classify_text(text: str) -> str:
    """Simple keyword-based sentiment classifier. Not ML-grade; robust for short text."""
    if not text:
        return "neutral"
    bull_hits = len(_BULL.findall(text))
    bear_hits = len(_BEAR.findall(text))
    if bull_hits > bear_hits + 1:
        return "bullish"
    if bear_hits > bull_hits + 1:
        return "bearish"
    return "neutral"


# ============================================================
# Named trader / influencer watchlist
# ============================================================

NAMED_TRADERS = {
    "heisenberg": {
        "handle": "Mr_Derivatives",
        "platform": "x.com",
        "scope": "options income + vol plays; technical analysis; both long/short ideas",
        "status": "live_brave_search",
        "method": "brave_search_site:x.com HTTP-only (Mike 2026-09-02 14:21 ET — no browser, ever)",
        "last_checked": None,
    },
    # Mike 2026-09-02 14:25 ET — added Open Source Intel as a tracked account.
    # 1.6M followers, real-time OSINT/news/macro/geopolitics (Iran, Russia, Israel, Fed, treasuries, oil).
    # Cross-asset macro signal: oil/treasury/yields → XLE/XOM/CVX/OXY/TLT/IEF/gold.
    # Feeds into deep_analyze via named_trader_status() — regime layer for any ticker.
    "open_source_intel": {
        "handle": "Osint613",
        "platform": "x.com",
        "scope": "real-time news + OSINT + geopolitics (Iran/Russia/Israel) + macro (Fed/treasuries) + oil (Brent/WTI) — cross-asset macro signals",
        "status": "live_brave_search",
        "method": "brave_search_site:x.com HTTP-only (Mike 2026-09-02 14:25 ET — added as named trader)",
        "followers": "1.6M",
        "signal_type": "macro_cross_asset",  # not a single-ticker trader — feeds regime/macro layer
        "last_checked": None,
    },
    # Mike 2026-09-02 14:18 ET clarification: "Blurry" was a typo for Michael Burry.
    # Burry deleted his X.com account in 2022 — no social feed exists.
    # Replaced with his actual signal sources: SEC 13F (quarterly) + press coverage.
    # Mike's "if Blurry is shorting something" trigger is now served by 13F put positions.
    "michael_burry": {
        "handle": None,
        "platform": "sec_edgar_13f + press",
        "scope": "Scion Asset Management LLC (CIK 0001649339) — quarterly 13F holdings + press",
        "status": "live_sec_edgar",
        "method": "EDGAR 13F-HR filings + Brave press search (Mike 2026-09-02 14:18 ET — Burry clarification)",
        "cik": "0001649339",
        "last_checked": None,
    },
    # Add more on request
}


def named_trader_status() -> dict:
    """Returns current status of named trader monitoring.

    Mike 2026-09-02 14:21 ET — 'you keep opening chrome! stop. if you want to use
    my browser ask, then i'll log in for you. but i rather you use headless'.

    Translation: NO browser process should EVER spawn from this session. Even
    headless Chrome on macOS flashes the Dock icon during launch. The only safe
    path is HTTP-only — Brave search for X.com feeds, SEC EDGAR HTTP for Burry.

    Named traders (HTTP-only feeds):
      - heisenberg (Mr_Derivatives): options/tech analysis
      - open_source_intel (Osint613): macro/geopolitics/oil/Fed
      - michael_burry: SEC 13F + press (quarterly cadence)
    """
    from twitter_scrape import x_handle_status as xstatus, fetch_and_cache
    base = xstatus()
    base["named_traders_detail"] = NAMED_TRADERS
    # Heisenberg feed (options/tech analysis — X.com via Brave HTTP)
    try:
        heisenberg_posts = fetch_and_cache("Mr_Derivatives", max_posts=10)
        base["heisenberg_latest"] = heisenberg_posts[:5]
    except Exception as e:
        base["heisenberg_latest_error"] = str(e)
    # Open Source Intel feed (macro/geopolitics/oil/Fed — X.com via Brave HTTP)
    try:
        osint_posts = fetch_and_cache("Osint613", max_posts=10)
        base["open_source_intel_latest"] = osint_posts[:5]
    except Exception as e:
        base["open_source_intel_error"] = str(e)
    # Burry feed (SEC 13F + press) — Mike's "if Blurry is shorting something" trigger
    try:
        from burry_monitor import burry_status as burry_full
        base["burry_monitor"] = burry_full()
    except Exception as e:
        base["burry_monitor_error"] = str(e)
    return base


# ============================================================
# Aggregate sentiment
# ============================================================

def aggregate_sentiment(symbol: str, use_reddit: bool = True) -> dict | None:
    """Combine Stocktwits + Reddit into one sentiment readout.

    Returns: {symbol, stocktwits: {...}, reddit: {...}, combined_bullish_pct, ...}
    """
    st = stocktwits_symbol(symbol)
    rd = reddit_symbol(symbol) if use_reddit else None
    bull_st = (st or {}).get("bullish_pct") if st else None
    bull_rd = (rd or {}).get("bullish_pct") if rd else None
    pieces = [b for b in [bull_st, bull_rd] if b is not None]
    combined = sum(pieces) / len(pieces) if pieces else None
    return {
        "symbol": symbol,
        "stocktwits": st,
        "reddit": rd,
        "combined_bullish_pct": combined,
        "as_of": dt.datetime.utcnow().isoformat() + "Z",
    }


if __name__ == "__main__":
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    print(f"=== {sym} ===")
    st = stocktwits_symbol(sym)
    if st:
        print(f"Stocktwits: bull={st['bullish_count']} bear={st['bearish_count']} neutral={st['neutral_count']} ({st['n_messages']} total)")
        if st["messages"]:
            print("  Sample (first 3):")
            for m in st["messages"][:3]:
                print(f"    [{m['sentiment']}] @{m['user']}: {m['body'][:80]}")
    print()
    rd = reddit_symbol(sym)
    if rd:
        print(f"Reddit: bull={rd['bullish_count']} bear={rd['bearish_count']} ({rd['n_posts']} total)")
        if rd["posts"]:
            print("  Sample (first 3):")
            for p in rd["posts"][:3]:
                print(f"    [{p['sentiment']}] r/{p['subreddit']} (score={p['score']}): {p['title'][:80]}")
    print()
    print("Named traders:", named_trader_status()["named_traders"])
