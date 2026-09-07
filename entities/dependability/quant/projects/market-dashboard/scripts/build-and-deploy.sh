#!/usr/bin/env bash
# build-and-deploy.sh — Full deploy: build dashboard → copy to public/ → wrangler pages deploy
#
# Use this when you've changed:
#   - The dashboard methodology (build_market_dashboard_html.py)
#   - The Worker/PIN gate (functions/_middleware.js)
#   - wrangler.toml
#   - Env vars (run separately via `wrangler pages secret put`)
#
# For content-only refresh (just the HTML changed), use update-content.sh — same flow,
# slightly faster since it skips the env-var check.

set -euo pipefail

# Resolve paths relative to this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
QUANT_DIR="$(dirname "$PROJECT_DIR")"  # entities/dependability/quant/
WORKSPACE_DIR="$(dirname "$QUANT_DIR")"  # entities/dependability/
REPO_ROOT="$(dirname "$WORKSPACE_DIR")"  # bacottibot/

# Inputs
SOURCE_HTML="$QUANT_DIR/reports/market-dashboard.html"
DEST_HTML="$PROJECT_DIR/public/index.html"

# Required env vars
: "${CLOUDFLARE_ACCOUNT_ID:?CLOUDFLARE_ACCOUNT_ID env var required (export it or use the .env file)}"
: "${CLOUDFLARE_API_TOKEN:?CLOUDFLARE_API_TOKEN env var required (export it or use the .env file)}"

PROJECT_NAME="dependability-dashboard"

echo "=== Step 1/4: Build dashboard ==="
cd "$QUANT_DIR"
if [ ! -d "$QUANT_DIR/.venv" ]; then
  echo "ERROR: quant venv not found at $QUANT_DIR/.venv"
  echo "Create it: cd $QUANT_DIR && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi
source "$QUANT_DIR/.venv/bin/activate"
python3 "$QUANT_DIR/scripts/build_market_dashboard_html.py"
echo "Build complete."

echo "=== Step 2/4: Stage HTML ==="
if [ ! -f "$SOURCE_HTML" ]; then
  echo "ERROR: dashboard HTML not found at $SOURCE_HTML"
  exit 1
fi
cp "$SOURCE_HTML" "$DEST_HTML"
echo "Copied: $SOURCE_HTML → $DEST_HTML"
echo "Size: $(wc -c < "$DEST_HTML") bytes"

echo "=== Step 3/4: Check env vars on Pages project ==="
SECRETS=$(wrangler pages secret list --project-name="$PROJECT_NAME" 2>&1 || true)
if ! echo "$SECRETS" | grep -q "ACCESS_CODE_HASH"; then
  echo "WARNING: ACCESS_CODE_HASH not set on Pages project."
  echo "Set it with: wrangler pages secret put ACCESS_CODE_HASH --project-name=$PROJECT_NAME"
fi
if ! echo "$SECRETS" | grep -q "SESSION_SECRET"; then
  echo "WARNING: SESSION_SECRET not set on Pages project."
  echo "Set it with: wrangler pages secret put SESSION_SECRET --project-name=$PROJECT_NAME"
fi

echo "=== Step 4/4: Deploy to CF Pages ==="
cd "$PROJECT_DIR"
wrangler pages deploy "$PROJECT_DIR/public" --project-name="$PROJECT_NAME"

echo ""
echo "=== Deploy complete ==="
echo "Custom domain (after CNAME setup): https://dashboard.dependability.us"
echo "Default Pages URL:                  https://$PROJECT_NAME.pages.dev"
echo ""
echo "Run \`wrangler pages deployment tail --project-name=$PROJECT_NAME\` to watch live logs."
