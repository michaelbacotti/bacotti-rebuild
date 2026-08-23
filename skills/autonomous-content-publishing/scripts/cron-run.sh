#!/usr/bin/env bash
# cron-run.sh — Daily entry point for autonomous content pipeline.
# Wired to a cron that runs once per morning per site.
#
# Usage: bash cron-run.sh [--site NAME] [--topic "..."] [--max-topics N] [--dry-run]
#
# Schedule (suggested):
#   0 9 * * *  /Users/mike/.openclaw/workspace-bacottibot/skills/autonomous-content-publishing/scripts/cron-run.sh --all
#
# Pipeline:
#   1. trends    (discover topics)
#   2. research  (deep-dive each topic)
#   3. draft     (LLM prompt emitted for review)
#   4. verify    (cross-check claims)
#   5. review_gate  (workboard card)
#   6. publish   (commit + build)

set -euo pipefail

WORKSPACE="${WORKSPACE:-/Users/mike/.openclaw/workspace-bacottibot}"
SCRIPT_DIR="$WORKSPACE/skills/autonomous-content-publishing/scripts"

SITE=""
TOPIC=""
MAX_TOPICS=1
DRY_RUN="true"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --all)        SITE="all"; shift ;;
    --site)       SITE="$2"; shift 2 ;;
    --topic)      TOPIC="$2"; shift 2 ;;
    --max-topics) MAX_TOPICS="$2"; shift 2 ;;
    --no-dry-run) DRY_RUN="false"; shift ;;
    --dry-run)    DRY_RUN="true"; shift ;;
    *)            echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

DATE=$(date +%Y-%m-%d)
echo "[$DATE] autonomous-content: starting cron run (site=$SITE topic=$TOPIC)"

# Step 1: trends
if [ -z "$TOPIC" ]; then
  if [ "$SITE" = "all" ] || [ -z "$SITE" ]; then
    for s in bithues dependability spaceorbitals tredey succession triadive; do
      python3 "$SCRIPT_DIR/trends.py" --site "$s" --max-topics "$MAX_TOPICS"
    done
  else
    python3 "$SCRIPT_DIR/trends.py" --site "$SITE" --max-topics "$MAX_TOPICS"
  fi
fi

# Step 2-3: orchestrate (research + draft emit-prompt)
ARGS=()
if [ -n "$SITE" ]; then ARGS+=(--site "$SITE"); fi
if [ -n "$TOPIC" ]; then ARGS+=(--topic "$TOPIC"); fi
ARGS+=(--max-sources 3 --word-target 1000)
[ "$DRY_RUN" = "true" ] && ARGS+=(--dry-run)

python3 "$SCRIPT_DIR/orchestrate.py" "${ARGS[@]}"

# Step 7: write digest
DIGEST="$WORKSPACE/memory/autonomous-content/digest-${DATE}.md"
{
  echo "# Autonomous Content Digest — $DATE"
  echo
  echo "## Topics discovered today"
  TRENDS_FILE="$WORKSPACE/memory/autonomous-content/trends-${DATE}.json"
  if [ -f "$TRENDS_FILE" ]; then
    python3 -c "
import json
data = json.load(open('$TRENDS_FILE'))
for t in data.get('topics', [])[:10]:
    print(f\"- [{t['site']}] {t['topic']} (score {t['relevance_score']})\")
"
  fi
  echo
  echo "## Dossiers"
  for f in "$WORKSPACE"/memory/autonomous-content/research-${DATE}-*.json; do
    [ -f "$f" ] && echo "- $f"
  done
  echo
  echo "## Sites requiring human review"
  echo "tredey, dependability, succession — financial content, every article reviewed before publish"
} > "$DIGEST"

echo "[$DATE] autonomous-content: digest at $DIGEST"
echo "[$DATE] autonomous-content: cron run complete"
