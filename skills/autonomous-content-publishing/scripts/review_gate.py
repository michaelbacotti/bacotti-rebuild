#!/usr/bin/env python3
"""
review_gate.py — Create a workboard card for human review of an article.

For financial content (tredey, dependability, succession) — always requires review.
For non-financial content (bithues, spaceorbitals, triadive) — only if the
verify ratio is below 0.85 OR confidence is below threshold.

The card carries:
  - Title
  - Full article body
  - Verification report (per-claim match scores)
  - "Approve" instruction (Mike comments "approve" → publish.py runs)
"""
import json
import datetime
import argparse
import sys
from pathlib import Path

WORKSPACE = Path("/Users/mike/.openclaw/workspace-bacottibot")


# Sites where human review is mandatory before publishing
HUMAN_REVIEW_REQUIRED = {"tredey", "dependability", "succession"}

# Sites where autonomous publish is OK if verify passes
AUTONOMOUS_PUBLISH_OK = {"bithues", "spaceorbitals", "triadive"}


def should_require_review(site: str, verify_ratio: float, max_tier: int) -> tuple:
    """Decide if this article needs Mike's review before publishing.

    Returns (requires_review, reason).
    """
    if site in HUMAN_REVIEW_REQUIRED:
        return True, f"site {site} is financial/trading; human review mandatory"
    if verify_ratio < 0.85:
        return True, f"verify ratio {verify_ratio:.2f} below 0.85 threshold"
    if max_tier >= 4:
        return True, "all sources are tier 4 (unranked); review required"
    return False, "auto-publish OK"


def build_card_payload(site: str, topic: str, draft_path: Path, verify_path: Path) -> dict:
    """Build the workboard_create payload."""
    draft = json.loads(draft_path.read_text())
    verify = json.loads(verify_path.read_text())

    requires_review, reason = should_require_review(
        site, verify["verification_ratio"],
        max((r.get("citation_tier") or 4) for r in verify["results"]) if verify["results"] else 4,
    )

    body_md = f"""## Article draft: {topic}

**Site:** {site}
**Verify decision:** {verify['decision']}
**Claims:** {verify['claims_verified']}/{verify['claims_total']} verified ({verify['verification_ratio']:.0%})
**Review required:** {requires_review}
**Reason:** {reason}

### Verification details

"""
    for r in verify["results"]:
        status = "✅" if r["verified"] else "❌"
        body_md += f"- {status} ({r.get('match_score', 0):.2f}) {r['claim'][:120]} — {r.get('citation_url', 'no URL')}\n"

    body_md += f"""

### To approve

Comment `approve` on this card. The orchestrator will commit the article and run the build pipeline.

### To revise

Edit the draft file at `{draft_path}` and re-run `verify.py`.

### To reject

Comment `reject`. The draft is deleted and the topic is logged as failed.
"""

    return {
        "title": f"[{site}] {topic} — review needed" if requires_review else f"[{site}] {topic} — auto-approved",
        "notes": body_md,
        "agentId": "main",
        "labels": ["autonomous-content", f"site:{site}"],
        "priority": "high" if requires_review else "normal",
        "tenant": "autonomous-content",
        "boardId": "autonomous-content",
        "skills": ["autonomous-content-publishing"],
        "maxRuntimeSeconds": 86400,
        "idempotencyKey": f"review-{site}-{datetime.date.today().isoformat()}-{topic[:30]}",
    }


def main():
    ap = argparse.ArgumentParser(description="Create workboard card for review")
    ap.add_argument("--site", required=True)
    ap.add_argument("--topic", required=True)
    ap.add_argument("--draft", required=True, help="Path to draft JSON")
    ap.add_argument("--verify", required=True, help="Path to verify JSON")
    ap.add_argument("--emit-only", action="store_true",
                    help="Just print the workboard payload, don't create card")
    args = ap.parse_args()

    payload = build_card_payload(
        site=args.site,
        topic=args.topic,
        draft_path=Path(args.draft),
        verify_path=Path(args.verify),
    )

    if args.emit_only:
        print(json.dumps(payload, indent=2))
        return

    # The orchestrator wires this to workboard_create.
    print(f"[review_gate] would create card:")
    print(f"  title: {payload['title']}")
    print(f"  priority: {payload['priority']}")
    print(f"  labels: {payload['labels']}")
    print(f"\nPass --emit-only to see the full payload.")


if __name__ == "__main__":
    main()
