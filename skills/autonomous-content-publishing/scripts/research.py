#!/usr/bin/env python3
"""
research.py — Deep-research a topic and capture primary sources.

For a given topic, fetches authoritative pages (gov, .edu, primary publishers,
established news orgs) and extracts the key facts. Output is structured as a
list of {claim, source_url, source_text, retrieved_at} so the verifier can
later cross-check.

Output: memory/autonomous-content/research-<date>-<topic_slug>.json
"""
import json
import datetime
import re
import argparse
import requests
from pathlib import Path
from urllib.parse import urlparse

WORKSPACE = Path("/Users/mike/.openclaw/workspace-bacottibot")
OUT_DIR = WORKSPACE / "memory" / "autonomous-content"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# Source authority tiers. Higher = more trusted. The verifier weights sources
# by tier (Tier 1 sources can ground claims, Tier 3 are weak).
SOURCE_TIERS = {
    1: [".gov", ".edu", "irs.gov", "sec.gov", "federalreserve.gov", "bls.gov",
        "census.gov", "uspto.gov", "copyright.gov", "congress.gov"],
    2: ["reuters.com", "ap.org", "bloomberg.com", "wsj.com", "ft.com",
        "nytimes.com", "nature.com", "sciencemag.org", "nejm.org", "thelancet.com",
        "wikipedia.org"],  # Wikipedia is tier 2 — useful but cite the primary
    3: ["forbes.com", "cnbc.com", "cnn.com", "bbc.com", "theguardian.com",
        "npr.org", "washingtonpost.com", "investopedia.com", "kiplinger.com"],
}


def classify_source_tier(url: str) -> int:
    """Return 1, 2, or 3 based on the source URL's authority tier."""
    host = urlparse(url).netloc.lower()
    for tier, suffixes in SOURCE_TIERS.items():
        for s in suffixes:
            if s in host or host.endswith(s):
                return tier
    return 4  # unknown / unranked


def fetch_url(url: str, timeout: int = 15) -> dict | None:
    """Fetch a URL and return {url, status, content_type, text, retrieved_at}.

    Returns None on error.
    """
    try:
        headers = {
            "User-Agent": "OpenClautonomous-research/1.0 (Mike's content pipeline)",
            "Accept": "text/html,application/xhtml+xml",
        }
        r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        ct = r.headers.get("content-type", "")
        if r.status_code != 200 or "text/html" not in ct:
            return {
                "url": url,
                "status": r.status_code,
                "content_type": ct,
                "text": "",
                "retrieved_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "ok": False,
            }
        # Cheap text extraction: strip tags
        text = re.sub(r"<script[^>]*>.*?</script>", "", r.text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return {
            "url": url,
            "status": r.status_code,
            "content_type": ct,
            "text": text[:8000],  # cap so we don't bloat memory
            "retrieved_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "ok": True,
        }
    except Exception as e:
        return {
            "url": url,
            "status": -1,
            "error": str(e)[:200],
            "retrieved_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "ok": False,
        }


def extract_facts(text: str, max_facts: int = 8) -> list:
    """Heuristic fact extraction. Splits text into sentences and picks those
    that look like factual claims (numbers, dates, named entities, definitional
    statements)."""
    if not text:
        return []
    # Strip nav/menu text that's usually at the start of Wikipedia pages
    text = re.sub(r"Jump to content.*?Contribute Help Learn to edit", "", text, flags=re.DOTALL)
    text = re.sub(r"Community portal.*?Donate", "", text, flags=re.DOTALL)
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
    facts = []
    seen = set()
    for sent in sentences:
        sent = sent.strip()
        if len(sent) < 40 or len(sent) > 350:
            continue
        # Skip nav-style sentences
        if any(skip in sent.lower() for skip in ["privacy policy", "terms of use",
                                                    "cookie policy", "navigation menu",
                                                    "search results"]):
            continue
        # Has a number, or looks like a definition
        has_number = bool(re.search(r"\b(\d{4}|\d+%|\$[\d,.]+|\d+\.\d+)\b", sent))
        # Definition-like: starts with a capitalized noun + is/was/founded/published
        looks_definitional = bool(re.search(
            r"^(?:[A-Z][\w\s-]+ (?:is|was|founded|published|developed|created|designed|introduced|released))",
            sent))
        if has_number or looks_definitional:
            # Dedupe near-identical sentences
            key = sent[:80].lower()
            if key in seen:
                continue
            seen.add(key)
            facts.append(sent)
        if len(facts) >= max_facts:
            break
    return facts


def research_topic(topic: str, seed_urls: list | None = None, max_sources: int = 5) -> dict:
    """Deep-research a topic.

    seed_urls: optional list of URLs to start from (e.g. from trends.py output).
    Returns a research dossier with sources, tier rankings, extracted facts.
    """
    print(f"[research] topic: {topic}", file=__import__('sys').stderr)

    sources = []
    if seed_urls:
        for url in seed_urls[:max_sources]:
            print(f"[research]   fetching {url}", file=__import__('sys').stderr)
            data = fetch_url(url)
            if data and data.get("ok"):
                tier = classify_source_tier(url)
                sources.append({
                    "url": url,
                    "tier": tier,
                    "status": data["status"],
                    "retrieved_at": data["retrieved_at"],
                    "facts": extract_facts(data["text"]),
                    "snippet": data["text"][:600],
                })

    return {
        "topic": topic,
        "researched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "sources_count": len(sources),
        "tier_breakdown": {
            f"tier_{t}": sum(1 for s in sources if s["tier"] == t) for t in [1, 2, 3, 4]
        },
        "sources": sources,
        "all_facts": [f for s in sources for f in s["facts"]],
    }


def main():
    ap = argparse.ArgumentParser(description="Deep-research a topic")
    ap.add_argument("--topic", required=True, help="Topic to research")
    ap.add_argument("--seed-url", action="append", help="Seed URL (repeatable)")
    ap.add_argument("--max-sources", type=int, default=5)
    ap.add_argument("--date", help="Override date stamp")
    args = ap.parse_args()

    date = args.date or datetime.date.today().isoformat()
    slug = re.sub(r"[^a-z0-9]+", "-", args.topic.lower()).strip("-")[:50]

    dossier = research_topic(args.topic, seed_urls=args.seed_url, max_sources=args.max_sources)

    out_file = OUT_DIR / f"research-{date}-{slug}.json"
    out_file.write_text(json.dumps(dossier, indent=2))
    print(f"[research] wrote {out_file}", file=__import__('sys').stderr)
    print(json.dumps({
        "sources_count": dossier["sources_count"],
        "tier_breakdown": dossier["tier_breakdown"],
        "facts_count": len(dossier["all_facts"]),
        "file": str(out_file),
    }, indent=2))


if __name__ == "__main__":
    main()
