#!/usr/bin/env bash
# brain-monitor.sh — Self-healing brain system: detect + restore + alert.
# This is the primary entrypoint called by brain-health-check cron.
# Pipeline: health-check → if missing/too-small → brain-restore → re-verify → log → workboard card.
# Created 2026-08-23 as part of the Brain system.

set -uo pipefail

WORKSPACE="/Users/mike/.openclaw/workspace-bacottibot"
SKILL_DIR="$WORKSPACE/skills/brain"
STATE_DIR="$WORKSPACE/.openclaw/tmp/brain"
DRIFT_LOG="$STATE_DIR/drift-log.jsonl"
RESTORATIONS_LOG="$STATE_DIR/restorations.jsonl"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

mkdir -p "$STATE_DIR"

HEALTH="$SKILL_DIR/scripts/brain-health-check.sh"
RESTORE="$SKILL_DIR/scripts/brain-restore.sh"

# === Step 1: Run health check ===
HEALTH_OUT=$("$HEALTH" 2>&1)
HEALTH_EXIT=$?
echo "$HEALTH_OUT"

# === Step 2: If healthy, exit ===
if [ "$HEALTH_EXIT" -eq 0 ]; then
    exit 0
fi

# === Step 3: Read state file to find which files are missing ===
STATE_FILE="$STATE_DIR/state.json"
if [ -f "$STATE_FILE" ]; then
    MISSING_FILES=$(python3 -c "
import json
with open('$STATE_FILE') as f:
    s = json.load(f)
print(' '.join(s.get('missing_files', [])))
" 2>/dev/null)
else
    MISSING_FILES=""
fi

# === Step 4: Attempt restore for each missing file ===
RESTORED=()
FAILED=()
[ -z "${RESTORED+x}" ] && RESTORED=()  # ensure init
[ -z "${FAILED+x}" ] && FAILED=()

for file in $MISSING_FILES; do
    # Strip JSON quotes
    file="${file//\"/}"
    echo "[$TIMESTAMP] Attempting restore: $file" | tee -a "$RESTORATIONS_LOG"
    if "$RESTORE" "$file" 2>&1 | tee -a "$RESTORATIONS_LOG"; then
        RESTORED+=("$file")
    else
        FAILED+=("$file")
    fi
done

# === Step 5: Re-run health check to verify ===
"$HEALTH" >/dev/null 2>&1
POST_RESTORE_EXIT=$?

# === Step 6: Log drift event ===
# Safe expansion for arrays under set -u: ${arr[@]:-} returns empty when unset.
cat >> "$DRIFT_LOG" <<EOF
{"timestamp":"$TIMESTAMP","missing_detected":"$MISSING_FILES","restored":"${RESTORED[*]:-}","failed":"${FAILED[*]:-}","post_restore_exit":$POST_RESTORE_EXIT}
EOF

# === Step 7: Write needs-attention marker if anything is still broken ===
# This file is drained by the OpenClaw brain-health-followup cron (every 30min, M2.7)
# which creates a workboard card and clears the marker. Pattern: bash detects,
# LLM surfaces to Mike.
NEEDS_ATTENTION="$STATE_DIR/needs-attention.json"
if [ "$POST_RESTORE_EXIT" -ne 0 ]; then
    cat > "$NEEDS_ATTENTION" <<EOF
{
  "timestamp": "$TIMESTAMP",
  "missing_files": "$MISSING_FILES",
  "restored": "${RESTORED[*]:-}",
  "failed": "${FAILED[*]:-}",
  "post_restore_exit": $POST_RESTORE_EXIT,
  "last_drift_line": "$(tail -1 "$DRIFT_LOG" | tr -d '\n')"
}
EOF
fi

# === Step 8: Output summary (kept for legacy callers) ===
echo ""
echo "=== BRAIN SUMMARY ==="
echo "Missing detected: $MISSING_FILES"
RESTORED_STR="${RESTORED[*]:-}"; [ -z "$RESTORED_STR" ] && RESTORED_STR="none"
FAILED_STR="${FAILED[*]:-}"; [ -z "$FAILED_STR" ] && FAILED_STR="none"
echo "Restored: $RESTORED_STR"
echo "Failed: $FAILED_STR"
echo "Post-restore health: $POST_RESTORE_EXIT (0=healthy)"

# Exit code: 0 if everything restored, 2 if anything still failed
if [ "$POST_RESTORE_EXIT" -eq 0 ]; then
    exit 0
else
    exit 2
fi
