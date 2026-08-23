#!/usr/bin/env python3
"""
trends.py — Topic discovery per site.

For each supported site, runs web searches tuned to that site's topic and returns
a list of trending topics with relevance scores.

Output: memory/autonomous-content/trends-<date>.json
Schema:
{
  "date": "YYYY-MM-DD",
  "topics": [
    {
      "site": "dependability",
      "topic": "Roth conversion ladder 2026",
      "queries": ["Roth conversion 2026", "mega backdoor Roth limits 2026"],
      "relevance_score": 0.85,  # 0.0-1.0
      "rationale": "Search volume + niche fit",
      "first_seen": "ISO timestamp",
      "status": "fresh"  # fresh, in_progress, published
    },
    ...
  ]
}
"""
import json
import datetime
import argparse
import requests
from pathlib import Path

WORKSPACE = Path("/Users/mike/.openclaw/workspace-bacottibot")
OUT_DIR = WORKSPACE / "memory" / "autonomous-content"
OUT_DIR.mkdir(parents=True, exist_ok=True)


SITE_TOPICS = {
    "bithues": {
        "description": "Books, reading, reading maps, lists",
        "queries": [
            "best new books 2026",
            "reading challenge 2026",
            "book recommendations {genre}",
            "reading map curated",
            "books like {book}",
        ],
        "niche_terms": ["book", "read", "novel", "author", "fiction", "non-fiction", "library"],
        "min_words": 600,
        "max_words": 1500,
    },
    "dependability": {
        "description": "Financial planning, retirement, tax, options education",
        "queries": [
            "Roth conversion 2026",
            "IRA contribution limits 2026",
            "options trading strategies {tactic}",
            "covered call income 2026",
            "tax loss harvesting 2026",
            "estate planning 2026",
        ],
        "niche_terms": ["retirement", "tax", "IRA", "estate", "portfolio", "options", "income"],
        "min_words": 800,
        "max_words": 2000,
        "human_review_required": True,
    },
    "spaceorbitals": {
        "description": "Space industry news, orbital mechanics, satellite tech",
        "queries": [
            "SpaceX news {month} {year}",
            "satellite launch {quarter} {year}",
            "Hohmann transfer explained",
            "FCC space debris rules {year}",
            "asteroid mining feasibility",
            "LEO economy {year}",
        ],
        "niche_terms": ["space", "satellite", "orbit", "launch", "rocket", "mission"],
        "min_words": 800,
        "max_words": 1800,
    },
    "succession": {
        "description": "Estate planning, succession, trust management",
        "queries": [
            "estate planning 2026",
            "trust administration 2026",
            "succession planning family business",
            "probate avoidance {year}",
        ],
        "niche_terms": ["estate", "trust", "succession", "probate", "inheritance"],
        "min_words": 800,
        "max_words": 1800,
    },
    "tredey": {
        "description": "Trading journal, options strategies, market analysis",
        "queries": [
            "SPX outlook {date}",
            "VIX term structure {date}",
            "iron condor management",
            "earnings trade {ticker} {quarter}",
        ],
        "niche_terms": ["trade", "option", "volatility", "spread", "SPX", "VIX"],
        "min_words": 800,
        "max_words": 1500,
        "human_review_required": True,
    },
    "triadive": {
        "description": "Workflows, productivity, daily loops, content systems",
        "queries": [
            "weekly review template {year}",
            "GTD weekly checklist",
            "content publishing pipeline",
            "goal tracking system",
        ],
        "niche_terms": ["workflow", "review", "productivity", "system", "checklist"],
        "min_words": 600,
        "max_words": 1200,
    },
}


def brave_search(query: str, count: int = 5) -> list:
    """Run a web search via the Brave Search API.

    Returns a list of {title, url, description} dicts.
    Falls back to empty list if API fails.
    """
    creds_path = WORKSPACE / "credentials" / "brave-search.json"
    if not creds_path.exists():
        return []
    try:
        creds = json.loads(creds_path.read_text())
        api_key = creds.get("api_key")
        if not api_key:
            return []
        headers = {"Accept": "application/json", "X-Subscription-Token": api_key}
        params = {"q": query, "count": count}
        r = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers=headers, params=params, timeout=15,
        )
        r.raise_for_status()
        results = r.json().get("web", {}).get("results", [])
        return [{
            "title": x.get("title", ""),
            "url": x.get("url", ""),
            "description": x.get("description", ""),
        } for x in results]
    except Exception as e:
        print(f"[trends] brave search error for {query!r}: {e}", file=__import__('sys').stderr)
        return []


def score_topic(topic: str, site_config: dict, results: list) -> float:
    """Score a topic's relevance to a site on a 0-1 scale.

    Considers:
    - Number of search results (more = more interest)
    - Niche term overlap (does the topic match the site's niche?)
    - Recency (topics with current-year mentions score higher)
    """
    if not results:
        return 0.0
    base = min(len(results) / 5.0, 1.0) * 0.4
    topic_lower = topic.lower()
    niche_hits = sum(1 for t in site_config["niche_terms"] if t in topic_lower)
    niche_score = min(niche_hits / 2.0, 1.0) * 0.4
    # Recency: check if any result mentions the current year
    year = str(datetime.datetime.now().year)
    recency_hits = sum(1 for r in results if year in (r.get("title", "") + r.get("description", "")))
    recency_score = min(recency_hits / 2.0, 1.0) * 0.2
    return round(base + niche_score + recency_score, 3)


def discover_topics(site: str, max_topics: int = 5) -> list:
    """Discover trending topics for a site."""
    if site not in SITE_TOPICS:
        return []
    cfg = SITE_TOPICS[site]
    candidates = []
    for q_template in cfg["queries"]:
        # Replace placeholders if any
        query = q_template.replace("{year}", str(datetime.datetime.now().year))
        query = query.replace("{month}", datetime.datetime.now().strftime("%B"))
        query = query.replace("{quarter}", f"Q{(datetime.datetime.now().month - 1) // 3 + 1}")
        results = brave_search(query, count=5)
        score = score_topic(query, cfg, results)
        candidates.append({
            "site": site,
            "topic": query,
            "queries": [query],
            "relevance_score": score,
            "first_result": results[0] if results else None,
            "all_results_count": len(results),
            "first_seen": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "status": "fresh",
            "requires_human_review": cfg.get("human_review_required", False),
            "min_words": cfg.get("min_words", 800),
            "max_words": cfg.get("max_words", 1500),
        })
    candidates.sort(key=lambda x: x["relevance_score"], reverse=True)
    return candidates[:max_topics]


def main():
    ap = argparse.ArgumentParser(description="Discover trending topics per site")
    ap.add_argument("--site", help="Single site to query (default: all)")
    ap.add_argument("--max-topics", type=int, default=5, help="Max topics per site")
    ap.add_argument("--date", help="Override date stamp (default: today)")
    args = ap.parse_args()

    date = args.date or datetime.date.today().isoformat()
    sites = [args.site] if args.site else list(SITE_TOPICS.keys())

    all_topics = []
    for site in sites:
        print(f"[trends] discovering topics for {site}...", file=__import__('sys').stderr)
        topics = discover_topics(site, max_topics=args.max_topics)
        all_topics.extend(topics)
        print(f"[trends]   {len(topics)} candidates (top score: {topics[0]['relevance_score'] if topics else 'n/a'})",
              file=__import__('sys').stderr)

    output = {
        "date": date,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "sites_queried": sites,
        "total_candidates": len(all_topics),
        "topics": all_topics,
    }

    out_file = OUT_DIR / f"trends-{date}.json"
    out_file.write_text(json.dumps(output, indent=2))
    print(f"[trends] wrote {out_file}", file=__import__('sys').stderr)
    print(json.dumps({"total_candidates": len(all_topics), "file": str(out_file)}, indent=2))


if __name__ == "__main__":
    main()
