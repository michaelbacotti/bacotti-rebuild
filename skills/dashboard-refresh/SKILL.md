---
name: "dashboard-refresh"
description: "Refresh the Dependability Holdings LLC Market Dashboard (ClawRank-v0) by re-running the build script, re-selecting sector leaders, and verifying the live render. Trigger: Mike says 'refresh the dashboard' or any equivalent request to update the dashboard with current data."
---

# dashboard-refresh — Market Dashboard v5 Refresh Procedure

**Workdesk:** `agent:main:dependability-quant` (📐)
**Status:** LIVE (created 2026-09-03 by dependability-quant)
**Owner entity:** Dependability Holdings LLC
**Scope:** Refresh the `2026-XX-XX-market-dashboard.html` deliverable and verify it renders correctly. **No code changes** unless Mike explicitly requests them.

## What this skill does

1. Re-run the build pipeline (data fetch → ClawRank compute → HTML render)
2. Re-select sector leaders by current ClawRank scores (one highest-scoring
   stock per sector, scanned from the 28-name candidate set)
3. Verify the dashboard renders correctly via HTTP check
4. Report results back

## When to invoke

- Mike says "refresh the dashboard", "make it current", "update the dashboard",
  or any equivalent request
- It's been more than 1 trading day since the last build and Mike wants
  a current snapshot
- A new trading day's close is needed for a research note or meeting

## When NOT to invoke

- Mike asks for a *code change* to the dashboard (different skill: depends on
  the specific change — usually handled inline by dependability-quant)
- Mike asks for a *trade* (out of scope — quant is research-only, doctrine §2)
- Mike asks for *publishing* (out of scope — dependability-quant never publishes
  to public sites; routes to dependability-website-manager instead)

## Inputs

- Today's date (for the output filename)
- The candidate set in `entities/dependability/quant/scripts/build_clawrank_features.py`
  (28 names across 11 sectors; check this is current before refreshing)

## Outputs

- `entities/dependability/quant/reports/YYYY-MM-DD-market-dashboard.html`
  (the rendered dashboard)
- `entities/dependability/quant/reports/YYYY-MM-DD-clawrank.json`
  (structured output for downstream consumers)
- Live portal URL (informational only)

## Procedure

### Step 1 — Pre-flight

Check that the candidate set in `build_clawrank_features.py` is what Mike
expects. The current set:

```
XLK  → MSFT, NVDA, AAPL
XLF  → JPM, BAC, GS
XLE  → XOM, CVX
XLV  → LLY, UNH, JNJ
XLI  → CAT, HON, DE
XLY  → HD, AMZN, TSLA
XLP  → PG, KO, WMT
XLC  → META, GOOGL
XLB  → LIN, FCX
XLRE → AMT, PLD
XLU  → NEE, SO
```

If Mike has asked to add/remove candidates, edit the file first (this is a
configuration change, requires explicit approval per the standing instruction
recorded 2026-09-03).

### Step 2 — Run the build

```bash
cd /Users/mike/.openclaw/workspace-bacottibot/entities/dependability/quant
python3 scripts/build_market_dashboard_html.py
```

Expected output ends with `OK html=... rows=42 duration=~1s` on success.
yfinance is called for all 42 tickers (~6 months of daily bars).

**Failure modes to watch for:**
- yfinance rate-limit / network error → retry once after 30 seconds
- yfinance schema change → check for upstream changes; report and pause
- ImportError → check `lib/clawrank.py` and `scripts/build_clawrank_features.py`
  for syntax errors
- Empty data for one ticker → check that ticker still trades; report and pause
  if more than 5 tickers fail

### Step 3 — Re-select sector leaders (automatic)

The build script's `pick_top_by_sector()` function already does this. For each
sector, it picks the candidate with the highest current ClawRank score. No
manual intervention needed unless the output is surprising (e.g., the same
sector picks a different stock than yesterday, or a sector has no candidate
above ClawRank 30).

### Step 4 — Verify the live render

After the build, confirm the HTML file was produced and is well-formed:

```bash
ls -la entities/dependability/quant/reports/YYYY-MM-DD-market-dashboard.html
# File size typically 130-150 KB. If much smaller, investigate.
```

If a portal is running, curl it to confirm HTTP 200:

```bash
curl -sS -o /dev/null -w "HTTP %{http_code}  size=%{size_download}\n" \
  "http://127.0.0.1:<PORT>/YYYY-MM-DD-market-dashboard.html?openclaw_portal=<TOKEN>"
```

### Step 5 — Spot-check content

Open the dashboard (or curl/scrape it) and confirm:

- Title shows today's date and the "updated HH:MM TZ" timestamp
- Snapshot KPIs show reasonable counts (should sum to 42)
- Sector leaders table shows 11 rows, one per sector, sorted by score
- Glossary section is present (25 entries, with clickable column headers)
- Trend counts make sense (typically 5-15 uptrend, 5-15 downtrend,
  rest transitioning or range)

### Step 6 — Report

Report back to Mike with:

- Build status (success / failure)
- File size and live portal URL (if available)
- Trend distribution (uptrend / downtrend / transitioning / range)
- Label distribution (Research candidate / Watchlist / Avoid)
- The 11 sector leaders with scores
- Any anomalies (e.g., a ticker that changed trend direction, a sector
  that switched its leader, etc.)

## Anti-patterns

- **Do not edit code unless Mike asks.** Refresh = re-run the existing pipeline.
  Code edits are a separate task with a separate scope.
- **Do not skip the live render verification.** A successful build that fails
  to render correctly is a failure, not a success.
- **Do not change the candidate set silently.** Standing instruction:
  re-scan and pick the highest ClawRank stock per sector from the *existing*
  28-name candidate set. Expansion of the candidate set requires explicit
  Mike approval.
- **Do not change the dashboard's tone.** It is research-only output and
  must remain so. No language changes that imply recommendation, sizing,
  or risk budgeting.
- **Do not auto-commit without verifying.** Always verify before `git commit`.

## Related

- `skills/dependability-quant/SKILL.md` — quant workdesk doctrine
- `entities/dependability/quant/scripts/build_market_dashboard_html.py` — the builder
- `entities/dependability/quant/scripts/build_clawrank_features.py` — feature pipeline
- `entities/dependability/quant/lib/clawrank.py` — composite scorer
- `wiki/main/syntheses/dependability-custom-ranking-system.md` — methodology

## Change log

- 2026-09-03 v1 — initial skill created after v5 dashboard ship
