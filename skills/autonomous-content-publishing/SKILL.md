---
name: autonomous-content-publishing
description: Autonomous content publishing pipeline (Lobster + workdesk). Discovers trends, researches topics, drafts articles with anti-hallucination guardrails, verifies claims against sources, gates financial content behind human review via workboard, then publishes. Use when Mike wants a site to grow with regular content without him personally writing every article.
---

# Autonomous Content Publishing

**What it does:** Trend discovery → research → draft → verify → review → publish.

**Architecture:** Lobster pipeline (orchestration) + Python scripts (LLM + research) + workboard cards (human review gate).

**Sites supported:** bithues.com, dependability.us, spaceorbitals.com, successionholdingllc.com, tredey.com, triadive.com.

## Pipeline

```
trends.py            →  finds trending topics per site (web search)
research.py          →  deep-research each topic (firecrawl + sources)
draft.py             →  LLM draft with mandatory citations
verify.py            →  cross-check claims against sources (anti-hallucination)
review_gate.py       →  create workboard card → human approves
publish.py           →  commit MD, run build.py, verify live, deploy
```

Each step is a separate script (idempotent, can be re-run independently). The Lobster pipeline glues them together.

## Anti-hallucination rules

Every claim in a generated article MUST cite a primary source URL. The verify step enforces this:

1. `draft.py` outputs article + per-claim citation list (URL + retrieval timestamp)
2. `verify.py` re-fetches each cited URL and confirms the claim matches the source
3. Any claim without a verified citation → rejected, must be rewritten or removed
4. For financial content (tredey, dependability): human review gate (workboard card) is mandatory
5. For non-financial content: confidence score ≥ 0.85 + verified citations = auto-publish

## Human review gate (workboard)

For financial/trading content:

1. `review_gate.py` creates a workboard card with:
   - Title
   - Full article body
   - Citations list (URL + retrieval time + claim-URL match %)
   - Confidence score
   - "Approve & Publish" comment instruction
2. Mike reviews the card, leaves a comment with "approve" or changes
3. Card transitions to "completed" → `publish.py` runs

For non-financial content with confidence ≥ 0.85:

- Skips workboard, publishes directly
- Mike can review via morning digest

## Running the pipeline

```bash
# Run a single article end-to-end (interactive)
python3 skills/autonomous-content-publishing/scripts/orchestrate.py --site dependability --topic "Roth conversion 2026"

# Run full pipeline for all sites (cron-driven)
python3 skills/autonomous-content-publishing/scripts/orchestrate.py --all

# Dry-run (research + draft only, no publish)
python3 skills/autonomous-content-publishing/scripts/orchestrate.py --site dependability --topic "..." --dry-run
```

## Cron integration

Default cadence: 1 article per site per day. Schedule:

```
0 9 * * *   /skills/autonomous-content-publishing/scripts/cron-run.sh
```

The cron:
1. Runs `trends.py` for all sites
2. Picks 1 highest-trend topic per site
3. Runs full pipeline for each
4. Sends a morning digest to Mike (Telegram) with: topic, draft preview, citations, status

## What this skill does NOT do

- Does NOT generate fake citations (verify.py re-fetches)
- Does NOT publish financial content without human review
- Does NOT bypass Mike's editorial voice (drafts are flagged as AI-generated; Mike rewrites if he wants a personal voice)
- Does NOT edit pages manually (it commits MD source → build.py regenerates HTML)

## Files

- `scripts/trends.py` — topic discovery
- `scripts/research.py` — deep research + source capture
- `scripts/draft.py` — LLM draft with citations
- `scripts/verify.py` — claim verification
- `scripts/review_gate.py` — workboard integration
- `scripts/publish.py` — commit + build + verify
- `scripts/orchestrate.py` — top-level runner
- `scripts/cron-run.sh` — cron entry point
- `workflows/content-publish.lobster` — Lobster pipeline definition
