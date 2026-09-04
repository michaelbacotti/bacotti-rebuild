# Dependability Holdings LLC — Working Notes for Next Meeting

**Subject:** Market Dashboard build + ClawRank-v0 launch (research-only output)
**Prepared:** 2026-09-03 22:45 ET by dependability-quant (📐)
**For next:** Dependability Holdings LLC member / manager meeting
**Status:** Working notes — to be referenced in the meeting narrative

> **Reading guide:** This file is *working notes from the dashboard build session*,
> not minutes of a meeting. It is written so that the Dependability XO can include
> the salient facts in the next meeting's narrative without further research.
> **All factual claims link to artifacts in the workspace or to tool calls.**

---

## 1. What happened

Over the course of 2026-09-03, dependability-quant designed, built, and shipped
**Market Dashboard v5** (an HTML research deliverable, not a publishing artifact)
plus the **ClawRank-v0** composite ranking system that powers it.

**Deliverables committed to git (workspace `dependability-rebuild.git`, branch `main`):**

| Commit | Title | Net effect |
|---|---|---|
| `e5538e2c7` | ClawRank-v0 + backtest + dashboard integration | First end-to-end build |
| `0f626206b` | dashboard v3 — ClawRank first col, hover-popover for factors, favicon | UX layer |
| `046cb42d9` | dashboard v4 — score-only labels + sector leaders + popover fix | Scoring and selection refinement |
| `7aea8914d` | dashboard v5 — timestamp + glossary w/ anchor links + fixed trend logic | Final polish |

**Artifacts:**

- `entities/dependability/quant/reports/2026-09-03-market-dashboard.html`
  (~140 KB, dark+gold theme, 42-row universe)
- `entities/dependability/quant/reports/2026-09-03-clawrank.json`
  (raw structured output, 42 tickers × 5 factors)
- Live portal URL (informational only, not published):
  `http://127.0.0.1:49667/2026-09-03-market-dashboard.html?openclaw_portal=…`

---

## 2. Methodology decisions to record for the record

### 2.1 ClawRank-v0 composite scoring system

Five-factor weighted composite (weights documented in code + wiki synthesis):

| Factor | Weight | Source |
|---|---|---|
| Fundamental Health | 25% | yfinance `.info` (stocks only; ETFs correctly skip) |
| Technical Momentum | 25% | RS-vs-SPY, distance-to-MA, RSI, trend slope |
| Volatility Regime | 15% | 20D realized vs historical, with calm-precedes-breakout logic |
| Setup Quality | 25% | Pattern detection (breakout, pullback, continuation, reversal, range) |
| Sentiment / Catalyst | 10% | ADV$, volume acceleration, analyst price targets |

**Label rule (locked at v5):** score ≥ 70 → "Research candidate"; 30–70 →
"Watchlist"; ≤ 30 → "Avoid." This is a transparency label — **not a trade
recommendation, position-sizing input, or risk-budget allocation.**

**Backtest result (v0 sanity check):** No statistically significant 20-day
forward edge for this universe and time window. The composite is documented
honestly as a *structure-aware labeling layer*, not as a predictive alpha model.

### 2.2 Trend classification (corrected during the session)

**Original rule:** spot-vs-MA50 + 10-day MA50 slope. This produced false
"downtrend" classifications on QQQ and META — both are actually rallying on
the 5-day window, with prices that are pennies below the lagging MA50.

**Corrected rule (Mike-flagged, fixed in v5):** spot-vs-MA50 **and**
spot-vs-MA20 **and** 5-day return **and** 20-day return. Four-signal
agreement reduces single-signal false positives. QQQ and META correctly
classified as "transitioning." LLY still correctly classified as "downtrend"
(below both MAs, both momentum windows negative).

This is a methodologically meaningful correction: the dashboard's primary
state variable was wrong before v5, and a single-line rule change to use
**four agreeing signals** instead of **one lagging slope** is a real
improvement that future revisions should preserve.

### 2.3 Universe expansion

- **Benchmarks (3):** SPY, QQQ, IWM
- **Sector ETFs (11):** XLK, XLF, XLE, XLV, XLI, XLY, XLP, XLC, XLB, XLRE, XLU
- **Sector-leader candidates (28):** MSFT, NVDA, AAPL, JPM, BAC, GS, XOM, CVX, LLY, UNH, JNJ, CAT, HON, DE, HD, AMZN, TSLA, PG, KO, WMT, META, GOOGL, LIN, FCX, AMT, PLD, NEE, SO

Standing instruction from Mike 2026-09-03 22:39 ET: **on each refresh,
re-scan and pick the highest-ClawRank stock per sector from this candidate
set.** If the universe needs to be expanded (e.g., a sector ETF with no
candidate that beats ClawRank 40), that requires explicit approval and an
update to `scripts/build_clawrank_features.py`.

### 2.4 Today's 11 sector leaders (snapshot)

Sorted by ClawRank score descending:

| Sector | Pick | Score | Trend | Label |
|---|---|---|---|---|
| Financials | BAC | 95 | range | Research candidate |
| Consumer Staples | PG | 88 | uptrend | Research candidate |
| Technology | MSFT | 80 | uptrend | Research candidate |
| Health Care | JNJ | 73 | uptrend | Research candidate |
| Energy | CVX | 66 | uptrend | Watchlist |
| Materials | FCX | 58 | transitioning | Watchlist |
| Comm Services | META | 55 | transitioning | Watchlist |
| Real Estate | AMT | 49 | transitioning | Watchlist |
| Industrials | DE | 44 | uptrend | Watchlist |
| Consumer Disc. | TSLA | 39 | transitioning | Watchlist |
| Utilities | NEE | 5 | downtrend | Avoid |

---

## 3. Items the meeting may want to ratify or discuss

1. **Standing refresh instruction.** "Refresh the dashboard" = re-run the
   pipeline, verify live render, and re-select sector leaders by current
   ClawRank scores. No code changes unless explicitly requested. Documented
   in `skills/dashboard-refresh/SKILL.md`.

2. **Methodology scope.** The dashboard is a research-output. It does NOT
   issue trade recommendations, does NOT touch the broker API, does NOT
   size positions. The quant skill (`skills/dependability-quant/SKILL.md`,
   Locked Doctrine §2) makes this explicit.

3. **Backtest honesty.** v0 backtest showed no significant 20-day edge. The
   meeting may want to set a target (e.g., "achieve statistically significant
   alpha at p<0.05 over rolling 60-day windows by year-end 2026") or
   de-prioritize the backtest and focus on the dashboard as a structural
   labeling layer.

4. **Universe cadence.** Quarterly review of the 28-name candidate set —
   any sector whose top pick has been "Avoid" for 2+ consecutive months
   warrants a candidate-set review.

5. **Cost.** Dashboard refresh currently takes ~1 second for the build
   script plus a few seconds for Playwright verification. No external
   API costs (yfinance is free, with rate limits). Cron is NOT yet
   scheduled — the dashboard is built on demand.

---

## 4. Cross-entity coordination notes (for Bacotti Inc. XO)

- Dependability Holdings LLC is the source entity for the dashboard;
  no other entity's books are touched.
- The dashboard does not generate P&L or affect profit-share to
  Bacotti Inc. — it is a research-only output.
- Bacotti Inc. (as 20% member) has visibility into Dependability's
  operations through standard K-1 + monthly reporting, not through
  this dashboard.

---

## 5. Source pointers for the meeting record

- `wiki/main/syntheses/dependability-custom-ranking-system.md` — full
  ClawRank-v0 spec + Danelfin reference comparison + factor weights
- `wiki/main/syntheses/dependability-markets-analysis.md` — existing
  dependability market-analysis doctrine
- `wiki/main/syntheses/dependability-trading-framework.md` — existing
  trading framework
- `skills/dependability-quant/SKILL.md` — quant workdesk doctrine
  (Locked Doctrines 1–13)
- `skills/dashboard-refresh/SKILL.md` — newly created refresh skill
- `entities/dependability/quant/decisions/` — append-only compliance log

---

*End of working notes. These are facts about what was built and why, not
decisions of any meeting. They are written so the next Dependability Holdings
LLC member / manager meeting can include the salient items in its narrative
without further research.*
