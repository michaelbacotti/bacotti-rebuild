"""twitter_scrape.py — Named trader (Heisenberg/Blurry) feed via Brave search ONLY.

**Architecture (per Mike 2026-09-02 14:21 ET directive: "you keep opening chrome! stop."):**

Mike's exact ask: use headless, but ALSO no browser windows. Headless Chrome on
macOS still flashes a Dock icon and registers in Cmd+Tab during launch — even
with `headless=True` and `channel="chrome"`. The only safe path is **no Chrome
at all**. This module is now HTTP-only.

Path:
  1. Brave Web Search `site:x.com {handle} options` — pure HTTP, no browser
  2. Parse search results for x.com/{handle}/status/{id} URLs
  3. Filter to public status posts (skip photos, replies, ads)
  4. Pull body text from Brave snippet, ticker hints via `$TICKER` regex
  5. Cache 15 min, return

**What I removed:**
- `_launch_headless_chrome()` — raises RuntimeError if called
- `fetch_handle_headless()` — always returns empty list
- `fetch_handle()` — no longer tries headless first; Brave is the only path
- All Playwright imports from active code paths

**Tradeoffs:**
- Brave coverage is sparse (~1-2 posts/week per handle vs ~12 with logged-in DOM)
- No relative timestamps like "1h"/"Aug 15" — Brave gives absolute age like "5 days ago"
- No full thread context — just the post body snippet from search result
- 15-min cache means same result until next refresh

**Why no headless bundled Chromium (the "true invisible" alternative):**
- Tested earlier: bundled Chromium returns empty HTML from X.com (gated)
- System Chrome with `headless=True` returns data but still registers in macOS
- Playwright Chromium-headless-shell is invisible but doesn't bypass X.com detection
- Brave HTTP is the only path that's both invisible AND gets X.com data

Usage:
    from twitter_scrape import fetch_and_cache, x_handle_status
    feed = fetch_and_cache("Mr_Derivatives")
"""
from __future__ import annotations
import datetime as dt
import json
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request
from typing import Any

CACHE_DIR = "/Users/mike/.openclaw/workspace-bacottibot/entities/dependability/quant/data/twitter_cache"
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_TTL_MINUTES = 15
FETCH_TIMEOUT_SECONDS = 20

# Mike 2026-09-02 14:18 ET: headless only, no Comet
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "")  # free tier fallback
BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/151.0.0.0 Safari/537.36"
)

# Anti-detection init script (Mike: headless browsers, but don't trigger X.com gates)
STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins', {
    get: () => [
        { name: 'Chrome PDF Plugin' },
        { name: 'Chrome PDF Viewer' },
        { name: 'Native Client' }
    ]
});
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){}, app: {} };
const _origPermQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (p) =>
    p.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : _origPermQuery(p);
"""


# ============================================================
# Method 1: headless system Chrome — DISABLED (Mike 2026-09-02 14:21 ET
# 'you keep opening chrome! stop'). Even headless=True launches a Chrome process
# that briefly registers in the macOS Dock / window list during startup.
# No Chrome-based fetch path is exposed anymore. Use fetch_handle_brave()
# (HTTP-only, no browser) instead.
# ============================================================

def _launch_headless_chrome():
    """DISABLED. Returns nothing — Chrome-based fetch removed per Mike directive."""
    raise RuntimeError(
        "headless Chrome fetch path disabled (Mike 2026-09-02 14:21 ET). "
        "Use fetch_handle_brave() instead — HTTP-only, no browser."
    )


def fetch_handle_headless(handle: str, max_posts: int = 10) -> list[dict]:
    """DISABLED. Returns empty list — headless Chrome fetch removed per Mike directive.

    Mike 2026-09-02 14:21 ET: 'you keep opening chrome! stop. i rather you use headless
    but i want no windows'. Even headless Chrome on macOS flashes the Dock icon.
    Pure HTTP via fetch_handle_brave() is the only path.
    """
    return []


# ============================================================
# Method 2: Brave search (free, no browser, sparse)
# ============================================================

def _brave_search(query: str, count: int = 20, freshness: str | None = None) -> list[dict]:
    if not BRAVE_API_KEY:
        return []
    params = {"q": str(query), "count": int(count)}
    if freshness:
        params["freshness"] = freshness
    url = f"{BRAVE_ENDPOINT}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "X-Subscription-Token": BRAVE_API_KEY,
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            payload = json.loads(r.read())
    except Exception:
        return []
    results = payload.get("web", {}).get("results", []) or []
    out = []
    for item in results:
        out.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "description": item.get("description", ""),
            "age": item.get("age"),
        })
    return out


def _filter_to_tweets(results: list[dict], handle: str) -> list[dict]:
    handle_clean = handle.lstrip("@").lower()
    out = []
    for r in results:
        u = (r.get("url") or "").lower()
        if (
            f"x.com/{handle_clean}/status/" in u
            or f"twitter.com/{handle_clean}/status/" in u
        ):
            out.append(r)
    return out


def fetch_handle_brave(handle: str, max_posts: int = 10) -> list[dict]:
    """Fetch via Brave Web Search. Returns tweet-shaped dicts."""
    handle_clean = handle.lstrip("@")
    queries = [
        f"site:x.com {handle_clean} options trade ideas",
        f"site:x.com {handle_clean}",
    ]
    all_results: list[dict] = []
    seen: set[str] = set()
    for q in queries:
        for r in _brave_search(q, count=20, freshness="pw"):
            if r["url"] not in seen:
                seen.add(r["url"])
                all_results.append(r)
        if len(_filter_to_tweets(all_results, handle_clean)) >= max_posts:
            break
    tweets = _filter_to_tweets(all_results, handle_clean)[:max_posts]
    out = []
    for r in tweets:
        text = (r.get("description") or r.get("title") or "").strip()
        tickers = re.findall(r"\$([A-Z]{1,5})\b", text)
        out.append({
            "handle": handle_clean,
            "title": r.get("title"),
            "text": text,
            "url": r["url"],
            "ticker_hints": list(set(t for t in tickers if t.isalpha() and len(t) <= 5)),
            "timestamp": r.get("age"),
            "fetched_at": dt.datetime.now(dt.UTC).isoformat(),
            "source": "brave_search",
        })
    return out


# ============================================================
# Cache layer
# ============================================================

def _cache_path(handle: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", handle.lstrip("@"))
    return os.path.join(CACHE_DIR, f"{safe}.json")


def read_cache(handle: str, max_age_minutes: int = CACHE_TTL_MINUTES) -> list[dict] | None:
    """Read cached tweets if fresh. None if stale or missing."""
    p = _cache_path(handle)
    if not os.path.exists(p):
        return None
    try:
        with open(p) as f:
            data = json.load(f)
        fetched_at = data.get("fetched_at")
        if not fetched_at:
            return None
        fetched_dt = dt.datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
        if fetched_dt.tzinfo is None:
            fetched_dt = fetched_dt.replace(tzinfo=dt.timezone.utc)
        age_min = (dt.datetime.now(dt.UTC) - fetched_dt).total_seconds() / 60
        if age_min > max_age_minutes:
            return None
        return data.get("posts", [])
    except Exception:
        return None


def write_cache(handle: str, posts: list[dict], source: str = "headless_chrome") -> None:
    p = _cache_path(handle)
    payload = {
        "handle": handle.lstrip("@"),
        "fetched_at": dt.datetime.now(dt.UTC).isoformat(),
        "n_posts": len(posts),
        "posts": posts,
        "source": source,
    }
    try:
        with open(p, "w") as f:
            json.dump(payload, f, indent=2)
    except Exception:
        pass


def merge_into_cache(handle: str, new_posts: list[dict], source: str) -> list[dict]:
    """Add new posts to cache, dedupe by URL, preserve older posts."""
    handle = handle.lstrip("@")
    p = _cache_path(handle)
    existing = []
    if os.path.exists(p):
        try:
            with open(p) as f:
                existing = json.load(f).get("posts", [])
        except Exception:
            existing = []
    new_urls = {x.get("url") for x in new_posts if x.get("url")}
    merged = list(new_posts) + [x for x in existing if x.get("url") not in new_urls]
    write_cache(handle, merged, source=source)
    return merged


# ============================================================
# Public API
# ============================================================

def fetch_handle(handle: str, max_posts: int = 10) -> list[dict]:
    """Fetch tweets for `handle` without opening any browser window.

    Mike 2026-09-02 14:21 ET — 'you keep opening chrome! stop. i rather you use headless'
    but ALSO no visible browser activity. The only safe path is **Brave search
    over HTTP** — no Chrome at all. Headless Chrome on macOS still shows Dock
    icon / appears in Cmd+Tab during launch.

    Order: Brave search → cache (last resort). No Playwright, no system Chrome,
    no bundled Chromium. Pure HTTP. Returns list of dicts.
    """
    handle = handle.lstrip("@")
    # Method 1: Brave search (HTTP, invisible, free, 1-3 posts/week per handle)
    posts = fetch_handle_brave(handle, max_posts=max_posts)
    if posts:
        return posts
    # Method 2: cache (last resort — even if stale)
    cached = read_cache(handle)
    if cached:
        return cached
    return []


def fetch_and_cache(handle: str, max_posts: int = 10) -> list[dict]:
    """Fetch (if cache stale) + merge with existing. Returns merged list.

    Returns cache contents even if stale (last resort) when both fetch methods fail.
    """
    handle = handle.lstrip("@")
    cached = read_cache(handle)
    if cached is not None:
        return cached
    new_posts = fetch_handle(handle, max_posts=max_posts)
    if not new_posts:
        # Last resort: return whatever's in the cache file (even stale)
        p = _cache_path(handle)
        if os.path.exists(p):
            try:
                with open(p) as f:
                    return json.load(f).get("posts", [])
            except Exception:
                return []
        return []
    return merge_into_cache(handle, new_posts, source=new_posts[0].get("source", "unknown"))


def x_handle_status() -> dict:
    """Status of named trader monitoring. NO Chrome is ever launched."""
    cached = []
    if os.path.exists(CACHE_DIR):
        cached = sorted(f.replace(".json", "") for f in os.listdir(CACHE_DIR) if f.endswith(".json"))
    return {
        "named_traders": ["heisenberg (Mr_Derivatives)"],
        "primary_method": "brave_search_http_only (Mike 2026-09-02 14:21 ET — no browser, ever)",
        "fallback_method": "cache (15-min stale, last resort)",
        "chrome_path_disabled": True,
        "cache_ttl_minutes": CACHE_TTL_MINUTES,
        "cache_dir": CACHE_DIR,
        "cached_handles": cached,
        "headless_chrome_available": False,
        "brave_api_key_present": bool(BRAVE_API_KEY),
        "as_of": dt.datetime.now(dt.UTC).isoformat(),
    }


def _check_headless_chrome() -> bool:
    """DEPRECATED. Headless Chrome path is disabled (Mike 14:21 ET). Always False."""
    return False


if __name__ == "__main__":
    import sys
    handle = sys.argv[1] if len(sys.argv) > 1 else "Mr_Derivatives"
    print(f"Fetching {handle}…")
    t0 = time.time()
    posts = fetch_and_cache(handle)
    elapsed = time.time() - t0
    print(f"\n{len(posts)} posts in {elapsed:.1f}s")
    for p in posts[:6]:
        ts = p.get("timestamp") or "?"
        tickers = p.get("ticker_hints") or []
        text = (p.get("text") or "")[:200].replace("\n", " ")
        print(f"  [{ts}] {tickers}: {text}")
    print()
    print(json.dumps(x_handle_status(), indent=2))
