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

Two-step process (as of v8, Mike 2026-09-07 directive):

```bash
cd /Users/mike/.openclaw/workspace-bacottibot/entities/dependability/quant
python3 scripts/build_clawrank_features.py   # Step 1: features + event signals
python3 scripts/build_market_dashboard_html.py # Step 2: render HTML
```

**Step 1 (`build_clawrank_features.py`)** pulls:
- 6mo daily bars from yfinance for all 42 tickers
- yfinance `.info` for fundamentals (stocks only; ETFs skip)
- Event signals via `lib/event_signals.py`:
  - News (yfinance news feed, last 30 headlines per ticker)
  - Short interest MoM change (FINRA via yfinance)
  - Institutional ownership % (yfinance)
  - Stocktwits bullish/bearish % (last 30 messages per ticker)
- Computes ClawRank-v0 composite (5 factors × weighted z-score)
- Writes `reports/YYYY-MM-DD-clawrank.json`

**Step 2 (`build_market_dashboard_html.py`)** reads the JSON + raw price data, renders HTML.
Writes TWO files:
- `reports/YYYY-MM-DD-market-dashboard.html` — dated archive (Mike's archive convention)
- `reports/market-dashboard.html` — canonical "latest" (always the freshest build)

Both contain identical content; the canonical path is what `dashboard.dependability.us`
serves after deploy.

Expected output ends with `OK html=... canonical=... rows=42 duration=~1s` on success.

**Failure modes to watch for:**
- yfinance rate-limit / network error → retry once after 30 seconds
- yfinance schema change → check for upstream changes; report and pause
- ImportError → check `lib/clawrank.py` and `scripts/build_clawrank_features.py`
  for syntax errors
- Empty data for one ticker → check that ticker still trades; report and pause
  if more than 5 tickers fail
- **Event signals slow**: each ticker now makes 3-4 external calls (yfinance news,
  institutional_flow, social_sentiment). Build takes 60-120s (was 7-10s).
  If a source returns 429 or times out, `event_signals_for` quietly returns
  None for those fields; check the build output for warnings.

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
ls -la entities/dependability/quant/reports/market-dashboard.html
# File size typically 130-150 KB. If much smaller, investigate.
```

**Verify the live URL** (CF Pages + PIN gate, since 2026-09-07 19:40 ET):

```bash
# Custom domain (after Mike has added the CNAME — see project DEPLOY.md)
curl -sS -o /dev/null -w "HTTP %{http_code}  size=%{size_download}\n" \
  "https://dashboard.dependability.us/"

# Backup URL (always works without DNS setup)
curl -sS -o /dev/null -w "HTTP %{http_code}  size=%{size_download}\n" \
  "https://dependability-dashboard.pages.dev/"
```

**Important:** GET requests return the PIN page (HTTP 200, no auth challenge). To verify
the dashboard actually serves, you need a valid session cookie:

```bash
# 1. Get a session cookie via the PIN submission
COOKIE_JAR=$(mktemp)
PIN="<the PIN from $PROJ/PIN.txt or Mike's password manager>"
ENCODED_PIN=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$PIN")
curl -s -X POST "https://dependability-dashboard.pages.dev/" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -c "$COOKIE_JAR" \
  -d "pin=$ENCODED_PIN" > /dev/null

# 2. Use the cookie to verify dashboard serves
curl -sS -i "https://dependability-dashboard.pages.dev/" \
  -H "Cookie: dash_auth=$(grep dash_auth "$COOKIE_JAR" | awk '{print $NF}')" | head -25
# Expect HTTP 200 + title "Market Dashboard — <today> (v9)"
```

If the dashboard is on CF Pages (since 2026-09-07), the local portal is no longer used.
The python http.server workflow is deprecated.

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
- **Do not change the candidate set silently.** Default behavior:
  re-scan and pick the highest ClawRank stock per sector from the *existing*
  28-name candidate set. Expansion of the candidate set requires explicit
  Mike approval. (Quant-proposed default; pending Mike confirmation — see
  Change log.)
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
- 2026-09-03 v1.1 — retracted unsupported "Mike 2026-09-03 22:39 ET"
  citation flagged by main (anti-pattern #138). Default behavior above is
  quant-proposed and pending Mike confirmation.
- 2026-09-07 v2 — event-aware Sentiment/Catalyst (Mike directive).
  Two-step build now: `build_clawrank_features.py` first (pulls news + institutional
  + social via `lib/event_signals.py`), then `build_market_dashboard_html.py`.
  Sentiment/Catalyst weight 10% → 25%. Dashboard popover shows event signals
  sub-rows. Regime banner at top shows cash market status. Bug fix: sector
  leaders loop had `kr=kr` typo leaking last ETF's row into every popover;
  fixed to `kr=pick`.
- 2026-09-07 v3 — CF Pages + PIN-gate deploy (Mike directive).
  Dashboard now lives at `dashboard.dependability.us`. Local python http.server
  workflow deprecated. Refresh procedure now: `cd projects/market-dashboard &&
  bash scripts/update-content.sh`. Live verification uses CF Pages URL, not
  portal. See project folder README/DEPLOY.md for full procedure.
- 2026-09-07 v3.1 — canonical URL convention (Mike directive).
  `build_market_dashboard_html.py` now writes both `reports/YYYY-MM-DD-market-dashboard.html`
  (archive) and `reports/market-dashboard.html` (always-latest canonical). Title
  includes `(vN)` version badge; `BUILD_VERSION` constant in build script.

- 2026-09-08 v4 — universe expansion 42 → 518 (Mike directive "Are you only
  considering 42 stocks??"). Dynamic universe via `scripts/universe_loader.py`
  + `config/universe.json` (503 SP500 + 93 NASDAQ-100 + 10 VTWO proxy).
  Sector Leaders now returns top 3 per sector (was top 1 — caused NEE-as-XLU-leader
  artifact when only 2 candidates). Caching layers: parquet price (1d),
  sector map (30d), yfinance .info (7d).

- 2026-09-08 v5 — **scoring methodology fix (Mike directive)**.
  Bug: `lib/clawrank.py` percentile-ranked factor scores and final composite,
  so score=100 just meant rank #1 of cross-section (e.g. MU score=100 with
  Val=18.6). Fix: `score_submetric` now converts raw cross-section values to
  0-100 via percentile rank BEFORE the weighted average. `compute_factor`
  and `composite` no longer percentile-rank the result — score is now the
  true weighted average of sub-metric 0-100 scores. New score range is
  roughly 33-71 (was 0-100). MU 100 → 71.3. AB 100 → 49.

- 2026-09-08 v5.1 — **watchlist HTML column bug fix**.
  `build_market_dashboard_html.py:824` wrapped `cr_text` (which already
  contains a complete `<td class="score-cell" ...>`) in another `<td>...</td>`,
  creating nested `<td>` tags. Fixed: row now uses `{cr_text}` directly.
  Verified: `grep -c '<td><td class="score-cell"' reports/market-dashboard.html`
  = 0 after rebuild (was 6).

## Deploy procedure (v5.1+)

**Canonical path** (use this for both content-only refreshes and full deploys):

```bash
cd /Users/mike/.openclaw/workspace-bacottibot/entities/dependability/quant/projects/market-dashboard
source /Users/mike/.openclaw/workspace-bacottibot/.openclaw/tmp/cf-token.env
export CLOUDFLARE_ACCOUNT_ID="56d1b3ebac9ac0438cab8077a1e9a993"
wrangler pages deploy ./public --project-name=dependability-dashboard
```

**Token source** — `~/.openclaw/tmp/cf-token.env` contains a Pages-deploy-scoped
CF API token. **Always check this file before asking Mike for a fresh token.**
If the file is missing or the token has been rotated, ask Mike to drop a new
one there. The PIN.txt token (`5dae85fed...`) is REJECTED by the Pages API
(code 6111 "Invalid format for Authorization header") — do NOT use it.

**Common deploy failure modes** (Mike 2026-09-08 lesson):
- `Authentication failed (status: 400) [code: 9106]` → token rejected.
  Either the token is missing, rotated, or you forgot to `source cf-token.env`.
- `Invalid format for Authorization header` (code 6111) → you're using the
  PIN.txt token instead of cf-token.env.
- HTTP 403 from `dashboard.dependability.us` even after successful deploy →
  Cloudflare Bot Fight Mode in the parent zone is blocking requests with
  non-browser User-Agent. This token has Pages scope but NOT zone scope, so
  the bot-management settings live in a different CF account. Mike must
  disable Bot Fight Mode in that account's dashboard.

**Pre-deploy sanity checks** (avoid the recurring bugs that wasted time):
```bash
# 1. Scoring methodology sanity (catches the percentile-rank regression):
#    top score should be ~50-75, never 100.0 with non-100 components.
python3 -c "
import json
d = json.load(open('reports/2026-09-08-clawrank.json'))
top = sorted(d['tickers'], key=lambda x: -(x.get('clawrank_score') or 0))[0]
print(f'top={top[\"ticker\"]} score={top[\"clawrank_score\"]:.1f}')
assert top['clawrank_score'] < 90, 'BUG: top score is suspiciously high'
"

# 2. Watchlist column sanity (catches the nested-<td> regression):
grep -c '<td><td class="score-cell"' reports/market-dashboard.html
# Must be 0. If >0, watchlist rows are misaligned.
```

- 2026-09-08 v6 (v18 build) — watchlist expansion 7 → 54 tickers + watchlist
  color coding (Mike 2026-09-08 11:15 ET directive).
  - 46 new tickers added to `config/options_watchlist.yaml` with sensible
    defaults (ref_price=live spot, target=+10%, prob=50%, timing=8-16w,
    risk_line=-8%). Mike to detail triggers/risk_meanings per ticker.
  - Sector ETF mapped from yfinance `sector` field via GICS lookup;
    ETF-bucket tickers (commodity/bond/leveraged) get generic purple.
  - Schema v2 addition: `sector_etf` field in YAML drives the color coding.
  - Watchlist ticker cell now has 3px left border in sector color (same
    scheme as sections 1 and 2).
  - Watchlist sector distribution: 14 XLK, 13 ETF (commodity/bond),
    8 XLI, 4 each XLY/XLF/XLC, 2 each XLV/XLU/XLB, 1 each XLRE/XLP.

- 2026-09-08 v5 (v17 build) — sector color coding (Mike 2026-09-08 08:52 ET
  directive). 14-color sector palette (SPY=#94a3b8 slate, QQQ=#60a5fa sky,
  IWM=#fbbf24 amber, XL* as detailed in the dashboard). Ticker cell gets
  3px left border, sector name cell gets colored text. Section 1 uses the
  ETF's own key, Section 2 uses the stock's parent sector ETF. INSM
  added to watchlist (rank 7).

- 2026-09-08 v7 (v19 build) — LITE added + 6-bug sweep (Mike 2026-09-08 11:46 ET
  directive). (1) BRK/B was unscoreable — added `YF_ALIASES` map that translates
  `BRK/B` → `BRK-B` for yfinance, restoring score 49.1. (2) SKHY short-history
  bug — lowered `compute_features_for` minimum closes from 50 to 25 (features
  that need longer history return None gracefully). SKHY now scores 67.1.
  (3) BULL misclassified as ETF — it's Webull Corp, moved to XLK. (4) SKHY
  missing `sector_etf` field — added XLK. (5) Subtitle showed "0 scored stocks"
  — module-level `STOCKS` was stale at render time; re-resolved inside
  `render_html`. (6) Risk line proximity logic was checking `< 3` before `< 0`,
  so below-risk tickers showed "above risk" with negative number — reordered
  to check `< 0` first (broken), then `< 3` (near), else safe. New ticker:
  LITE (Lumentum Holdings, XLK). All 55 watchlist tickers now have scores.

- 2026-09-08 v8 (v20 build) — dashboard top cleanup (Mike 2026-09-08 19:48 ET
  directive: "a little too much going on, certain comments can be removed
  without harming the purpose"). Removed: subtitle line, regime banner,
  entire Snapshot KPI card (6 KPIs), Data-Quality Note card. Replaced:
  disclaimer backtest reference (stale — was from 2026-09-03 pre-v15
  universe + pre-v16 scoring fix) with the actual methodology sentence
  ("sub-metrics percentile-ranked to 0–100, then weighted-averaged").
  Same replacement in Section 3's "Honest read" block, now a one-line
  "transparency / drill-down layer" note. Top of page now goes header →
  disclaimer → Section 1 directly. v20 build verified via removal-marker
  grep (all 6 marker strings absent).

- 2026-09-08 v9 (v21 build) — Section 3 factor table fix (Mike 2026-09-08 20:23
  ET directive: "I only see 5 factors listed there"). ClawRank has 11 factors
  since v15; the table was showing the stale v10 5-factor list. Two bugs:
  (1) loop had hardcoded 5-factor dict instead of loading from clawrank.yaml;
  (2) HTML template had hardcoded `<tbody>` with old rows instead of
  `{' '.join(factor_table_rows)}`. Fix: added module-level
  `_CLAWRANK_FACTORS` loader + `_factor_table_meta()` helper that derives
  label/weight/horizon/inputs per factor from the YAML source of truth;
  replaced template `<tbody>` with dynamic join. Added new "Horizon" column
  (4 horizons across 11 factors); dropped obsolete "# Tickers scored" /
  "Cap" columns. Added 6 new glossary entries for the factors that lacked
  one. v21 build verified via Section-3 row count = 11 (was 5).
