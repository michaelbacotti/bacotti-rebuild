#!/usr/bin/env python3
"""
verify.py — Cross-check claims in a draft against their cited sources.

For each claim in the draft:
1. Re-fetch the cited source URL
2. Compute a similarity/containment score between the claim and source text
3. If the score is below threshold → mark the claim as unverified

Output: memory/autonomous-content/verify-<date>-<topic_slug>.json
Schema:
{
  "topic": "...",
  "verified_at": "...",
  "claims_total": N,
  "claims_verified": K,
  "claims_rejected": J,
  "verification_ratio": K/N,
  "results": [
    {
      "claim": "...",
      "citation_url": "...",
      "citation_tier": 1,
      "verified": true|false,
      "match_score": 0.0-1.0,
      "source_snippet": "..."
    }
  ],
  "decision": "pass|needs_revision|reject"
}
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

# Thresholds: how strict we are about claim-source matching
MIN_MATCH_SCORE = 0.25  # very lenient — claims are often paraphrased
TIER_MIN_SCORES = {1: 0.15, 2: 0.20, 3: 0.30, 4: 0.45}  # higher tier = more lenient
PASS_RATIO = 0.85  # 85% of claims must verify for the article to pass


def fetch_snippet(url: str, max_chars: int = 4000) -> str | None:
    """Re-fetch a URL and return cleaned text, or None on error."""
    try:
        headers = {
            "User-Agent": "OpenClaw-verify/1.0 (anti-hallucination check)",
            "Accept": "text/html,application/xhtml+xml",
        }
        r = requests.get(url, headers=headers, timeout=12, allow_redirects=True)
        if r.status_code != 200:
            return None
        text = re.sub(r"<script[^>]*>.*?</script>", "", r.text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_chars]
    except Exception:
        return None


def classify_tier(url: str) -> int:
    """Quick re-classification of source tier by URL host."""
    host = urlparse(url).netloc.lower()
    if any(s in host or host.endswith(s) for s in
           [".gov", ".edu", "irs.gov", "sec.gov", "federalreserve.gov"]):
        return 1
    if any(s in host for s in ["reuters.com", "ap.org", "bloomberg.com",
                                "wsj.com", "ft.com", "nytimes.com",
                                "wikipedia.org", "nature.com"]):
        return 2
    if any(s in host for s in ["forbes.com", "cnbc.com", "cnn.com", "bbc.com",
                                "theguardian.com", "npr.org", "investopedia.com"]):
        return 3
    return 4


def score_match(claim: str, source_text: str) -> float:
    """Score how well a claim is supported by source text.

    Approach: extract the key tokens from the claim (numbers, named entities,
    distinctive words). How many of those tokens appear in the source?
    """
    if not source_text:
        return 0.0
    claim_lower = claim.lower()
    source_lower = source_text.lower()
    # Extract key tokens: numbers, capitalized words, dollar amounts
    key_tokens = set()
    for m in re.finditer(r"\b\d[\d,.]*\b", claim):
        key_tokens.add(m.group(0))
    for m in re.finditer(r"\$[A-Za-z\d]+|USD|EUR|GBP", claim):
        key_tokens.add(m.group(0))
    for m in re.finditer(r"\b[A-Z][a-z]+\b", claim):
        key_tokens.add(m.group(0).lower())
    # Filter to tokens with ≥3 chars (skip "I", "a", etc.)
    key_tokens = {t for t in key_tokens if len(t) >= 3}
    if not key_tokens:
        # Fallback: check if 50% of claim words appear in source
        claim_words = set(w for w in re.findall(r"\w{4,}", claim_lower))
        if not claim_words:
            return 0.0
        matched = sum(1 for w in claim_words if w in source_lower)
        return matched / len(claim_words)
    matched = sum(1 for t in key_tokens if t in source_lower)
    return matched / len(key_tokens)


def verify_claims(claims: list, sources: list) -> list:
    """Verify each claim against its cited source.

    claims: list of {claim: str, citation: int} (1-indexed)
    sources: list of {url, tier} in same order as citations

    Returns: list of verification results
    """
    results = []
    for c in claims:
        citation_idx = c.get("citation", 1) - 1  # convert 1-indexed → 0-indexed
        if citation_idx < 0 or citation_idx >= len(sources):
            results.append({
                "claim": c["claim"],
                "citation_url": None,
                "verified": False,
                "match_score": 0.0,
                "reason": "citation index out of range",
            })
            continue
        src = sources[citation_idx]
        url = src["url"]
        tier = src.get("tier") or classify_tier(url)
        snippet = fetch_snippet(url)
        if snippet is None:
            results.append({
                "claim": c["claim"],
                "citation_url": url,
                "citation_tier": tier,
                "verified": False,
                "match_score": 0.0,
                "reason": "source fetch failed",
            })
            continue
        score = score_match(c["claim"], snippet)
        threshold = TIER_MIN_SCORES.get(tier, MIN_MATCH_SCORE)
        verified = score >= threshold
        results.append({
            "claim": c["claim"],
            "citation_url": url,
            "citation_tier": tier,
            "verified": verified,
            "match_score": round(score, 3),
            "threshold": threshold,
            "source_snippet": snippet[:300],
        })
    return results


def main():
    ap = argparse.ArgumentParser(description="Verify draft claims against sources")
    ap.add_argument("--draft", required=True, help="Path to draft JSON")
    ap.add_argument("--dossier", required=True, help="Path to research dossier JSON")
    ap.add_argument("--date", help="Override date stamp")
    args = ap.parse_args()

    draft = json.loads(Path(args.draft).read_text())
    dossier = json.loads(Path(args.dossier).read_text())
    claims = draft.get("claims", [])
    sources = dossier.get("sources", [])

    results = verify_claims(claims, sources)
    n_total = len(results)
    n_verified = sum(1 for r in results if r["verified"])
    ratio = n_verified / n_total if n_total > 0 else 0.0
    if ratio >= PASS_RATIO:
        decision = "pass"
    elif ratio >= 0.5:
        decision = "needs_revision"
    else:
        decision = "reject"

    output = {
        "topic": draft.get("topic", ""),
        "verified_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "claims_total": n_total,
        "claims_verified": n_verified,
        "claims_rejected": n_total - n_verified,
        "verification_ratio": round(ratio, 3),
        "decision": decision,
        "results": results,
    }

    date = args.date or datetime.date.today().isoformat()
    slug = re.sub(r"[^a-z0-9]+", "-", draft.get("topic", "").lower()).strip("-")[:50]
    out_file = OUT_DIR / f"verify-{date}-{slug}.json"
    out_file.write_text(json.dumps(output, indent=2))
    print(f"[verify] wrote {out_file}")
    print(json.dumps({
        "claims_total": n_total,
        "claims_verified": n_verified,
        "ratio": round(ratio, 3),
        "decision": decision,
    }, indent=2))


if __name__ == "__main__":
    main()
