#!/usr/bin/env bash
# hash-pin.sh — Generate SHA-256 hash of an access code with the project's salt.
#
# Usage: bash scripts/hash-pin.sh '<your-pin-here>'
#   Outputs the hash on a single line, ready to paste into wrangler secret put.
#
# The salt is hardcoded in functions/_middleware.js (SALT constant).
# This script must use the same salt for the hash to verify correctly.

set -euo pipefail

SALT='dep-dash-v1-2026-09-07-mb-only'

if [ $# -ne 1 ]; then
  echo "Usage: $0 '<access-code>'" >&2
  echo "" >&2
  echo "  Generates SHA-256(SALT + code) for use with the dashboard PIN gate." >&2
  echo "  The salt is: $SALT" >&2
  echo "  Must match SALT in functions/_middleware.js." >&2
  exit 1
fi

CODE="$1"
HASH=$(printf '%s' "${SALT}${CODE}" | shasum -a 256 | awk '{print $1}')

echo "$HASH"
