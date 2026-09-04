"""burry_monitor.py — Michael Burry / Scion Asset Management signal feed.

**Architecture (per Mike 2026-09-02 14:18 ET directive: "before i ment Michael Burry"):**

Mike clarified: "Blurry" was a typo for **Michael Burry** (Scion Asset Management,
The Big Short). Burry deleted his X.com account in 2022 and is famously
anti-social-media — no live tweet feed exists. The `Blurry*` X.com handles I
tested earlier were dead ends.

This module monitors Burry's **actual signal sources** (all free, all official):

1. **SEC EDGAR 13F filings** for Scion Asset Management, LLC (CIK 0001649339)
   - Quarterly holdings (Form 13F-HR)
   - Shows long puts, long calls, equity longs
   - 45-day filing lag (Q3 2025 holdings → filed 2025-11-03)
   - Note: Scion's most recent 13F is Q3 2025 (filed 2025-11-03). Either AUM
     fell below the $100M threshold (no filing required), Burry moved capital
     to private vehicles, or filings are pending. Module gracefully handles
     missing quarters.

2. **Press coverage** via Brave search for "Michael Burry" latest quotes/positions
   - Catches interviews, op-eds, public appearances
   - Useful for real-time sentiment when Burry speaks (rare but high-impact)

3. **SEC EDGAR full-text search** for any Scion filings (catches non-13F activity
   like Form 4 insider trades if Burry takes personal positions)

**Cache TTL:**
- 13F filings: 24h (they don't change intra-quarter)
- Press coverage: 4h (Burry makes news every few weeks)
- Submissions index: 12h

**Tradeoffs:**
- 13F data is 45 days stale by the time it's filed
- Burry's actual positioning may be in undisclosed private vehicles
- Press coverage is real-time but Burry rarely speaks
- No engagement/like data (not on social media)

**Trade signals (Mike-relevant):**
- New positions: brand-new conviction calls (most actionable)
- Position increases: thesis reinforcing
- Decreases / exits: thesis fading or taking profits
- Top holdings: current biggest bets (conviction indicators)
- Put options: bearish bets — Mike's "if Blurry is shorting something" trigger

Usage:
    from burry_monitor import fetch_scion_13f, fetch_burry_press, burry_status
    holdings = fetch_scion_13f()  # latest 13F holdings
    press = fetch_burry_press()  # recent press coverage
    full = burry_status()  # combined view
"""
from __future__ import annotations
import datetime as dt
import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

CACHE_DIR = "/Users/mike/.openclaw/workspace-bacottibot/entities/dependability/quant/data/burry_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "")
BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
SEC_UA = "dependability-quant research@bacotti.com"

# Scion Asset Management, LLC CIK on EDGAR
SCION_CIK = "0001649339"
SCION_NAME = "Scion Asset Management, LLC"

# CUSIP → ticker map for top names (manual fallback; not all CUSIPs needed since
# names like "PALANTIR TECHNOLOGIES INC" are clear)
CUSIP_TO_TICKER = {
    # Q3 2025 holdings — verified from infotable.xml
    "116794207": "BRKR",   # BRUKER CORP, 6.375 PREF SER A
    "406216101": "HAL",    # HALLIBURTON CO, COM
    "550021109": "LULU",   # LULULEMON ATHLETICA INC, COM
    "60855R100": "MOH",    # MOLINA HEALTHCARE INC, COM
    "67066G104": "NVDA",   # NVIDIA CORPORATION, COM
    "69608A108": "PLTR",   # PALANTIR TECHNOLOGIES INC, CL A
    "717081103": "PFE",    # PFIZER INC, COM
    "78442P106": "SLM",    # SLM CORP, COM
}


def _http_get(url: str, *, timeout: int = 15) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": SEC_UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception:
        return None


def _http_get_json(url: str) -> Any:
    body = _http_get(url)
    if not body:
        return None
    try:
        return json.loads(body)
    except Exception:
        return None


# ============================================================
# 13F filings
# ============================================================

def _latest_13f_accession(cik: str = SCION_CIK) -> dict | None:
    """Find the most recent 13F-HR filing for a CIK. Returns {filing_date, period, accession}."""
    cache_path = os.path.join(CACHE_DIR, "latest_13f.json")
    # Cache for 12h since filings only update quarterly + 45 days
    if os.path.exists(cache_path):
        try:
            with open(cache_path) as f:
                cached = json.load(f)
            ts = dt.datetime.fromisoformat(cached.get("fetched_at", "1970-01-01"))
            if (dt.datetime.now() - ts).total_seconds() < 12 * 3600:
                return cached.get("filing")
        except Exception:
            pass

    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    d = _http_get_json(url)
    if not d:
        return None
    recent = d.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accs = recent.get("accessionNumber", [])
    report_dates = recent.get("reportDate", [])
    primary_docs = recent.get("primaryDocument", [])

    for f, dt_, acc, rd, doc in zip(forms, dates, accs, report_dates, primary_docs):
        if f == "13F-HR":
            filing = {
                "filing_date": dt_,
                "period_of_report": rd,
                "accession": acc,
                "primary_doc": doc,
                "filing_index": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=13F&dateb=&owner=include&count=10",
            }
            try:
                with open(cache_path, "w") as f_out:
                    json.dump({"fetched_at": dt.datetime.now().isoformat(), "filing": filing}, f_out)
            except Exception:
                pass
            return filing
    return None


def _fetch_infotable_xml(cik: str, accession: str) -> bytes | None:
    """Fetch the infotable.xml (holdings table) for a 13F filing."""
    cache_path = os.path.join(CACHE_DIR, f"infotable_{accession}.xml")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "rb") as f:
                return f.read()
        except Exception:
            pass
    acc_clean = accession.replace("-", "")
    url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_clean}/infotable.xml"
    body = _http_get(url)
    if not body:
        return None
    try:
        with open(cache_path, "wb") as f:
            f.write(body)
    except Exception:
        pass
    return body


def _parse_infotable(xml_bytes: bytes) -> list[dict]:
    """Parse SEC 13F infotable.xml into structured holdings."""
    ns = {"n1": "http://www.sec.gov/edgar/document/thirteenf/informationtable"}
    try:
        root = ET.fromstring(xml_bytes)
    except Exception:
        return []
    holdings = []
    for entry in root.findall(".//n1:infoTable", ns):
        def t(tag):
            el = entry.find(f"n1:{tag}", ns)
            return el.text.strip() if (el is not None and el.text) else None
        cusip = t("cusip") or ""
        name = t("nameOfIssuer") or ""
        title = t("titleOfClass") or ""
        value_str = t("value") or "0"
        # SEC 13F infotable value field is reported in dollars (not thousands, contrary to spec docs).
        # Verified by summing all entries: 1,381,198,076 matches the 13F cover-page total exactly.
        value = int(value_str)
        shares_str = entry.find(".//n1:sshPrnamt", ns)
        shares = int((shares_str.text or "0").replace(",", "")) if shares_str is not None and shares_str.text else 0
        put_call_el = entry.find("n1:putCall", ns)
        put_call = put_call_el.text.strip() if put_call_el is not None and put_call_el.text else None
        ticker = CUSIP_TO_TICKER.get(cusip)
        # Tickers for unknown CUSIPs — first word heuristic
        if not ticker and name:
            # Crude ticker extraction: BRUKER → BRKR, HALLIBURTON → HAL, etc.
            # Skip — better to show name + CUSIP and let caller look up if needed
            ticker = None
        holdings.append({
            "issuer": name,
            "class": title,
            "cusip": cusip,
            "ticker": ticker,
            "value_usd": value,
            "shares": shares,
            "put_call": put_call,  # "Put", "Call", or None for long
            "direction": (
                "bearish_call" if put_call == "Put"
                else "bullish_call" if put_call == "Call"
                else "long"
            ),
        })
    # Sort by value descending
    holdings.sort(key=lambda h: h["value_usd"], reverse=True)
    return holdings


def fetch_scion_13f() -> dict:
    """Fetch Scion Asset Management's most recent 13F filing + holdings.

    Returns dict with keys: filing_date, period_of_report, accession, holdings (list),
    total_value, top_holding, biggest_short. Empty values on failure.
    """
    filing = _latest_13f_accession()
    if not filing:
        return {"error": "no 13F filing found", "fetched_at": dt.datetime.now(dt.UTC).isoformat()}
    xml_bytes = _fetch_infotable_xml(SCION_CIK, filing["accession"])
    if not xml_bytes:
        return {"error": "could not fetch infotable", "filing": filing}
    holdings = _parse_infotable(xml_bytes)
    total_value = sum(h["value_usd"] for h in holdings)
    puts = [h for h in holdings if h["put_call"] == "Put"]
    calls = [h for h in holdings if h["put_call"] == "Call"]
    longs = [h for h in holdings if h["put_call"] is None]
    return {
        "fetched_at": dt.datetime.now(dt.UTC).isoformat(),
        "filing_date": filing["filing_date"],
        "period_of_report": filing["period_of_report"],
        "accession": filing["accession"],
        "filing_url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={SCION_CIK}&type=13F",
        "n_holdings": len(holdings),
        "total_value_usd": total_value,
        "n_puts": len(puts),
        "n_calls": len(calls),
        "n_longs": len(longs),
        "top_holding": holdings[0] if holdings else None,
        "biggest_put": max(puts, key=lambda h: h["value_usd"]) if puts else None,
        "biggest_call": max(calls, key=lambda h: h["value_usd"]) if calls else None,
        "holdings": holdings,
    }


# ============================================================
# Press coverage
# ============================================================

def _brave_search(query: str, count: int = 15, freshness: str | None = "month") -> list[dict]:
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
    out = []
    for item in payload.get("web", {}).get("results", []) or []:
        out.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "description": item.get("description", ""),
            "age": item.get("age"),
            "source": (item.get("profile") or {}).get("name"),
        })
    return out


def fetch_burry_press(max_articles: int = 10) -> list[dict]:
    """Recent press coverage of Michael Burry via Brave search.

    Catches interviews, op-eds, position changes reported in financial press.
    """
    cache_path = os.path.join(CACHE_DIR, "press.json")
    # Cache 4h
    if os.path.exists(cache_path):
        try:
            with open(cache_path) as f:
                cached = json.load(f)
            ts = dt.datetime.fromisoformat(cached.get("fetched_at", "1970-01-01"))
            if (dt.datetime.now() - ts).total_seconds() < 4 * 3600:
                return cached.get("articles", [])
        except Exception:
            pass

    queries = [
        '"Michael Burry" Scion position interview 2026',
        '"Michael Burry" 13F latest portfolio 2026',
        '"Michael Burry" stocks short sell buy',
        'Michael Burry Scion Asset Management recent',
    ]
    seen_urls: set[str] = set()
    articles = []
    for q in queries:
        for r in _brave_search(q, count=15, freshness="month"):
            if r["url"] in seen_urls:
                continue
            seen_urls.add(r["url"])
            text = (r.get("description") or "") + " " + (r.get("title") or "")
            tickers = re.findall(r"\$([A-Z]{1,5})\b|\b([A-Z]{2,5})\b(?=\s+(?:stock|position|put|call|short|long))", text)
            ticker_hints = []
            for tup in tickers:
                t = tup[0] or tup[1]
                if t and t.isalpha() and 2 <= len(t) <= 5:
                    ticker_hints.append(t)
            articles.append({
                "title": r.get("title"),
                "url": r["url"],
                "text": r.get("description"),
                "source": r.get("source"),
                "age": r.get("age"),
                "ticker_hints": sorted(set(ticker_hints))[:5],
                "fetched_at": dt.datetime.now(dt.UTC).isoformat(),
                "source_type": "brave_search_press",
            })
            if len(articles) >= max_articles:
                break
        if len(articles) >= max_articles:
            break

    try:
        with open(cache_path, "w") as f:
            json.dump({
                "fetched_at": dt.datetime.now().isoformat(),
                "n_articles": len(articles),
                "articles": articles,
            }, f, indent=2)
    except Exception:
        pass
    return articles


# ============================================================
# Combined view
# ============================================================

def burry_status() -> dict:
    """Combined Burry signal feed for named_trader_status() integration."""
    thirteen_f = fetch_scion_13f()
    press = fetch_burry_press()
    return {
        "named_trader": "michael_burry",
        "scope": "Scion Asset Management LLC (CIK 0001649339) — quarterly 13F + press",
        "primary_signal": "13F quarterly holdings",
        "secondary_signal": "press coverage (Burry rarely speaks)",
        "social_media": "deleted Twitter/X 2022 — no public feed",
        "thirteen_f_summary": {
            "filing_date": thirteen_f.get("filing_date"),
            "period_of_report": thirteen_f.get("period_of_report"),
            "n_holdings": thirteen_f.get("n_holdings"),
            "total_value_usd": thirteen_f.get("total_value_usd"),
            "n_puts": thirteen_f.get("n_puts"),
            "n_calls": thirteen_f.get("n_calls"),
            "n_longs": thirteen_f.get("n_longs"),
            "top_holding": (
                f"{thirteen_f['top_holding']['ticker'] or thirteen_f['top_holding']['issuer']} "
                f"${thirteen_f['top_holding']['value_usd']/1e6:.1f}M "
                f"{thirteen_f['top_holding']['direction']}"
            ) if thirteen_f.get("top_holding") else None,
            "biggest_put": (
                f"{thirteen_f['biggest_put']['ticker'] or thirteen_f['biggest_put']['issuer']} "
                f"${thirteen_f['biggest_put']['value_usd']/1e6:.1f}M"
            ) if thirteen_f.get("biggest_put") else None,
        },
        "thirteen_f_holdings": thirteen_f.get("holdings", []),
        "press_count": len(press),
        "press_latest": press[:5],
        "cache_dir": CACHE_DIR,
        "as_of": dt.datetime.now(dt.UTC).isoformat(),
    }


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "13f"
    if target == "13f":
        result = fetch_scion_13f()
        print(json.dumps(result, indent=2, default=str))
    elif target == "press":
        result = fetch_burry_press()
        print(json.dumps(result, indent=2, default=str))
    elif target == "status":
        result = burry_status()
        # Print summary, not full holdings
        summary = {k: v for k, v in result.items() if k != "thirteen_f_holdings"}
        print(json.dumps(summary, indent=2, default=str))
        print("\n=== Holdings ===")
        for h in result.get("thirteen_f_holdings", []):
            print(f"  {h['ticker'] or h['issuer']:30s} ${h['value_usd']/1e6:7.1f}M  {h['shares']:>10,} sh  {h['direction']}")  # noqa: F841
        print(f"\n=== Press ({result['press_count']} articles) ===")
        for a in result.get("press_latest", []):
            print(f"  [{a.get('age')}] {a.get('source','?')}: {a.get('title','')[:80]}")
    else:
        print(f"unknown target: {target}")
        print("usage: burry_monitor.py [13f|press|status]")
