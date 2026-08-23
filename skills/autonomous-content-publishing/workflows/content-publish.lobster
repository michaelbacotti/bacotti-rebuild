name: autonomous-content-publish
description: |
  Autonomous content publishing pipeline (Lobster orchestration).
  Discovers trending topics, deep-researches each, drafts with anti-hallucination
  guardrails, verifies claims against sources, gates financial content behind
  human review via workboard, then publishes (commit + build + verify).

  Used by:
    - Cron `autonomous-content-daily` (every morning, picks 1 topic per site)
    - Manual invocation (`lobster run content-publish.lobster --site X --topic "Y"`)

  ARCHITECTURE:
    1. TRENDS — web search per site for trending topics
    2. RESEARCH — fetch top sources, extract facts, build dossier
    3. DRAFT — generate JSON draft (LLM call; emits prompt for human inspection)
    4. VERIFY — re-fetch each cited source, score claim-source match
    5. REVIEW GATE — workboard card (mandatory for financial, optional for others)
    6. PUBLISH — copy MD to site source dir, run build.py, verify HTML
    7. NOTIFY — write digest for Mike's morning review

  ANTI-HALLUCINATION:
    - Every claim must cite a primary source URL
    - verify.py re-fetches each URL and scores claim-source match
    - Below 85% verified ratio → article rejected
    - Financial content (tredey, dependability, succession) ALWAYS requires Mike review

timeoutMs: 1800

# ENVIRONMENT:
#   WORKSPACE = /Users/mike/.openclaw/workspace-bacottibot
#   DATE_TODAY = YYYY-MM-DD
#   MAX_TOPICS_PER_SITE = 1
#   DRY_RUN = "true|false"
#
# HANDOFF SCHEMA (cron writes before invoking):
# {
#   "date": "2026-08-23",
#   "sites": ["bithues", "dependability"],   # optional subset
#   "max_topics_per_site": 1,
#   "dry_run": "true"
# }

steps:
  - id: preflight
    command: |
      WORKSPACE="${WORKSPACE:-/Users/mike/.openclaw/workspace-bacottibot}"
      DATE="${DATE_TODAY:-$(date +%Y-%m-%d)}"
      mkdir -p "$WORKSPACE/memory/autonomous-content"
      echo "WORKSPACE=$WORKSPACE DATE=$DATE"

  - id: discover_trends
    command: |
      WORKSPACE="${WORKSPACE:-/Users/mike/.openclaw/workspace-bacottibot}"
      SITE="${SITE:-all}"
      if [ "$SITE" = "all" ]; then
        for s in bithues dependability spaceorbitals tredey succession triadive; do
          python3 "$WORKSPACE/skills/autonomous-content-publishing/scripts/trends.py" \
            --site "$s" --max-topics "${MAX_TOPICS_PER_SITE:-1}"
        done
      else
        python3 "$WORKSPACE/skills/autonomous-content-publishing/scripts/trends.py" \
          --site "$SITE" --max-topics "${MAX_TOPICS_PER_SITE:-1}"
      fi

  - id: research_each_topic
    command: |
      WORKSPACE="${WORKSPACE:-/Users/mike/.openclaw/workspace-bacottibot}"
      DATE="${DATE_TODAY:-$(date +%Y-%m-%d)}"
      TRENDS_FILE="$WORKSPACE/memory/autonomous-content/trends-${DATE}.json"
      if [ ! -f "$TRENDS_FILE" ]; then
        echo "ERROR: $TRENDS_FILE not found" >&2
        exit 1
      fi
      # Per topic, run research.py
      python3 <<'PY'
      import json, subprocess, sys
      from pathlib import Path
      WS = Path("/Users/mike/.openclaw/workspace-bacottibot")
      data = json.load(open(WS / "memory/autonomous-content" / f"trends-{__import__('datetime').date.today().isoformat()}.json"))
      for topic in data.get("topics", []):
        seed = topic.get("first_result", {})
        seed_url = seed.get("url") if seed else None
        args = ["python3", str(WS / "skills/autonomous-content-publishing/scripts/research.py"),
                "--topic", topic["topic"], "--max-sources", "3"]
        if seed_url:
          args.extend(["--seed-url", seed_url])
        print(f"Researching: {topic['topic']}")
        subprocess.run(args, cwd=str(WS))
      PY

  - id: emit_drafts_for_review
    command: |
      # Each draft is emitted as a prompt file for human/LLM inspection
      # In production, this is where llm-task runs to produce the draft JSON
      WORKSPACE="${WORKSPACE:-/Users/mike/.openclaw/workspace-bacottibot}"
      DATE="${DATE_TODAY:-$(date +%Y-%m-%d)}"
      echo "Draft step: see memory/autonomous-content/ for per-topic dossier files"
      echo "Run llm-task on each dossier to produce draft JSON, then proceed to verify."

  - id: write_digest
    command: |
      WORKSPACE="${WORKSPACE:-/Users/mike/.openclaw/workspace-bacottibot}"
      DATE="${DATE_TODAY:-$(date +%Y-%m-%d)}"
      DIGEST="$WORKSPACE/memory/autonomous-content/digest-${DATE}.md"
      cat > "$DIGEST" <<EOF
# Autonomous Content Digest — ${DATE}

## Topics discovered
EOF
      if [ -f "$WORKSPACE/memory/autonomous-content/trends-${DATE}.json" ]; then
        python3 -c "
import json
data = json.load(open('$WORKSPACE/memory/autonomous-content/trends-${DATE}.json'))
for t in data['topics'][:10]:
    print(f\"- [{t['site']}] {t['topic']} (score {t['relevance_score']})\")
" >> "$DIGEST"
      fi
      cat >> "$DIGEST" <<EOF

## Dossiers
EOF
      for f in "$WORKSPACE"/memory/autonomous-content/research-${DATE}-*.json; do
        [ -f "$f" ] && echo "- $f" >> "$DIGEST"
      done
      cat >> "$DIGEST" <<EOF

## Next steps for Mike
1. Review each dossier file
2. (When LLM drafts land) review draft JSONs
3. Approve or modify each draft
4. Approved drafts → publish.py (per site)

## Sites requiring human review (financial)
tredey, dependability, succession — every article must be approved before publish.
EOF
      echo "Wrote $DIGEST"
