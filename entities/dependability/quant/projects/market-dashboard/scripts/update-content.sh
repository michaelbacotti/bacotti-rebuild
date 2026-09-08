#!/usr/bin/env bash
# update-content.sh — Content-only refresh: rebuild dashboard → wrangler pages deploy.
#
# Use this for the daily refresh (or whenever only the HTML content changes).
# Skips env-var check; assumes config and secrets are already in place.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
QUANT_DIR="$(dirname "$PROJECT_DIR")"

: "${CLOUDFLARE_ACCOUNT_ID:?CLOUDFLARE_ACCOUNT_ID env var required}"
# NOTE: wrangler uses CF_API_TOKEN, not CLOUDFLARE_API_TOKEN. We accept both for ergonomics.
: "${CF_API_TOKEN:=${CLOUDFLARE_API_TOKEN:?CF_API_TOKEN or CLOUDFLARE_API_TOKEN env var required}}"
export CF_API_TOKEN

PROJECT_NAME="dependability-dashboard"
SOURCE_HTML="$QUANT_DIR/reports/market-dashboard.html"
DEST_HTML="$PROJECT_DIR/public/index.html"

echo "=== Build dashboard ==="
cd "$QUANT_DIR"
source "$QUANT_DIR/.venv/bin/activate"
python3 "$QUANT_DIR/scripts/build_market_dashboard_html.py"

echo ""
echo "=== Stage HTML ==="
cp "$SOURCE_HTML" "$DEST_HTML"
echo "Copied: $(wc -c < "$DEST_HTML") bytes"

echo ""
echo "=== Deploy to CF Pages ==="
cd "$PROJECT_DIR"
wrangler pages deploy "$PROJECT_DIR/public" --project-name="$PROJECT_NAME"

echo ""
echo "=== Done ==="
echo "https://dashboard.dependability.us (live once CNAME is set in CF DNS)"
