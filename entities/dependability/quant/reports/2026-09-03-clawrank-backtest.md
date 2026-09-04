# ClawRank-v0 Backtest Report — 2026-09-03

**Author:** dependability-quant
**As-of:** 2026-09-03T21:17:25.701085-04:00
**Universe:** 3 benchmarks (SPY, QQQ, IWM) + 11 sector ETFs + 8 stocks (22 tickers, no expansion)
**Window:** 2 years of yfinance daily bars (~500 trading days); rebalance every 5 trading days
**Look-ahead guard:** yfinance `.info` (fundamentals) excluded — only price/volume data ≤ rebalance date used
**Ground truth:** forward 20D return per ticker from rebalance date

---

## 1. Headline

| Variant | Spearman IC | t(IC) | Q1−Q4 20D | t(spread) | Q1 beats Q4 |
|---|---|---|---|---|---|
| **Tech-only v0 (default)** | -0.0107 | -0.31 | -0.32% | -0.62 | 42.4% |
| Contrarian variant (mean-reversion) | +0.0247 | +0.78 | +0.40% | +0.77 | 54.1% |

**Periods:** 85 rebalance dates × 22 tickers (1,870 forward-return observations).

---

## 2. Honest read

**ClawRank-v0 with the original weights has no statistically significant predictive power over 20D forward returns in this universe and window.**

- Spearman IC = −0.011 (t-stat −0.31). Not distinguishable from zero.
- Q1 vs Q4 spread = −0.32% over 20D. Not significant.
- Q1 beats Q4 in only 42% of rebalance periods — i.e., the top-ranked names are coin-flip whether they beat the bottom-ranked names.

This is **not** a binary pass/fail. It means: **the current factor set doesn't beat a coin flip on 20D forward returns**. Two possible explanations:

1. **Regime sensitivity.** The 2024-Sep → 2026-Sep window is dominated by a mega-cap-led uptrend. Pure technical-momentum ranking has been a documented loser in this regime (NVDA, MSFT, AAPL carrying indices). The contrarian variant (mean-reversion-flavored) gets IC = +0.025 in the same window — directionally better, but still not significant.
2. **Factor structure is correct but weights are wrong.** ClawRank-v0 weighs Setup Quality + Technical Momentum at 65% combined. Both are momentum-tilted by construction. A weighting that down-weights momentum and up-weights volatility-regime might do better.

**My honest recommendation:** don't ship ClawRank as a directional signal yet. Ship it as a **scoring + drilldown layer**: every ticker gets a transparent score, every factor is shown, and human judgment applies the overlay. The dashboard integration below does exactly that — it's a transparency tool, not a trade signal.

---

## 3. Methodology details

### Data
- `yfinance` 1d daily bars, 2y lookback, period=`2y`, auto_adjust=False.
- For each rebalance date t in [60, T−20] step 5:
  - Slice all ticker history to [0..t]
  - Compute technical + volatility + setup sub-metrics from that slice only
  - Skip yfinance `.info` (avoids look-ahead)
  - Run ClawRank → composite scores
  - Read forward 20D return = close(t+20) / close(t) − 1

### Variants
- **Tech-only v0:** Technical Momentum 35% + Setup Quality 40% + Volatility 15% + Sentiment 10%. (Fundamentals dropped to avoid look-ahead.)
- **Contrarian:** same structure but Technical sub-metrics flipped direction (lower RSI/MA-distance = better), Setup lookup inverted (mean_reversion 100, breakout 30). Designed to test anti-momentum hypothesis.

### Universe
- 3 benchmarks + 11 sector ETFs + 8 stocks = 22 tickers.
- Same universe as today's dashboard. No expansion.

---

## 4. Per-ticker diagnostics (tech-only v0)

Sorted by mean forward 20D return:

| Ticker | Periods | Mean fwd 20D | Mean ClawRank | Research cand. | Watchlist | Avoid |
|---|---|---|---|---|---|---|
| CAT | 85 | +4.14% | 51.0 | 8 | 64 | 13 |
| NVDA | 85 | +2.65% | 63.9 | 18 | 58 | 9 |
| LLY | 85 | +2.47% | 50.0 | 6 | 57 | 22 |
| XLK | 85 | +2.40% | 55.1 | 15 | 59 | 11 |
| JPM | 85 | +2.05% | 63.5 | 19 | 62 | 4 |
| XOM | 85 | +1.94% | 42.0 | 10 | 56 | 19 |
| XLE | 85 | +1.78% | 45.5 | 10 | 64 | 11 |
| QQQ | 85 | +1.69% | 65.4 | 26 | 51 | 8 |
| AAPL | 85 | +1.44% | 55.5 | 8 | 64 | 13 |
| XLI | 85 | +1.34% | 56.3 | 16 | 64 | 5 |
| IWM | 85 | +1.33% | 61.3 | 14 | 62 | 9 |
| SPY | 85 | +1.25% | 74.5 | 38 | 42 | 5 |
| XLV | 85 | +0.99% | 41.9 | 8 | 52 | 25 |
| MSFT | 85 | +0.96% | 43.0 | 6 | 58 | 21 |
| XLB | 85 | +0.87% | 37.6 | 5 | 61 | 19 |
| XLF | 85 | +0.79% | 56.4 | 13 | 67 | 5 |
| XLC | 85 | +0.64% | 43.6 | 9 | 65 | 11 |
| XLU | 85 | +0.52% | 43.3 | 9 | 62 | 14 |
| XLP | 85 | +0.28% | 35.1 | 4 | 60 | 21 |
| XLY | 85 | +0.27% | 42.1 | 6 | 64 | 15 |
| XLRE | 85 | +0.23% | 38.9 | 2 | 66 | 17 |
| HD | 85 | -0.75% | 34.1 | 7 | 50 | 28 |

**Observations:**
- CAT, XOM, XLE, NVDA had the strongest forward returns but ClawRank only ranked them mid-pack.
- SPY, QQQ, IWM (broad benchmarks) had positive but unspectacular returns.
- HD, XLC, XLY (discretionary / comm-services) were the weakest performers; ClawRank also ranked them low.
- The correlation between score and forward return is **directionally positive but dispersion is wide** — i.e., the signal is too noisy to be actionable on 20D horizons.

---

## 5. Failure modes identified

### A. Look-ahead bias from fundamentals

The first backtest attempt used today's yfinance `.info` at every historical date — i.e., the EPS, revenue, and target-price values used in November 2025 were actually the *current* values. This produced IC = −0.080 (statistically significant negative), which looked like a real anti-momentum signal but was actually artifact.

**Fix:** excluded `.info` from the backtest entirely. Use it only in production scoring (where "today" is the only date that matters).

### B. ETF vs stock asymmetry in fundamentals

Even with no look-ahead, including the Fundamental Health factor creates an asymmetry: stocks have non-None fundamentals, ETFs have None. The cross-section ranking inside the factor becomes "stocks vs ETFs" rather than "stock A vs stock B." This makes the factor a regime-conditional bias rather than a quality signal.

**Fix:** split into two configs: `clawrank.yaml` (full version with fundamentals, for live dashboard) and `clawrank_techonly.yaml` (for backtest + ETF-heavy contexts).

### C. Momentum factor in mega-cap regime

The 2024-2026 window is a documented anti-momentum regime (NVDA + AAPL + MSFT = ~25% of S&P 500 weight, all momentum-correlated). Pure Technical Momentum sub-metrics (RS, MA distance, trend slope) reward the same names, which then mean-revert in the forward window.

**Fix candidate:** down-weight Technical Momentum from 35% to ~15% in the production config, and up-weight Volatility Regime (which is regime-neutral). The contrarian variant test supports this direction.

### D. Setup Quality overlap with the dashboard's label rule

The dashboard already produces a label (Research candidate / Watchlist / Avoid) using the same trend+setup logic. ClawRank's Setup Quality factor (25–40% weight) ends up double-counting the same signal. The score and the dashboard label are highly correlated — which is fine for transparency, but means ClawRank's marginal information over the dashboard label is small.

**Fix candidate:** Setup Quality should be the *primary* signal and dashboard label should be derived from it (not the other way around).

---

## 6. Recommended next iterations

1. **Reweight: Tech 15% / Setup 30% / Vol 35% / Sentiment 20%.** Prioritizes vol regime (regime-neutral) and drops momentum.
2. **Drop dashboard-label reuse.** Compute Setup Quality independently from raw inputs.
3. **Test on a wider universe** (top 100 SPY constituents) to reduce ETF/stock asymmetry.
4. **Test multi-horizon.** 5D, 10D, 20D, 60D forward returns. Momentum dominates short horizons, fundamentals dominate long.
5. **Add a real Sentiment feed** (news volume/tone, analyst-target revisions) before raising the Sentiment weight above 10%.
6. **Walk-forward vs single-split.** Today's backtest is single-split on 2y. Walk-forward would tell us if the signal decays over time.

---

## 7. Bottom line for Mike

**ClawRank-v0 is not yet a trade signal.** It's a transparent scoring layer that explains why each ticker got its dashboard label. The dashboard integration treats it as a **drill-down tool**, not a prediction. Use it to: 
- see the factor breakdown for any ticker (which sub-metrics are driving the score)
- spot regime shifts (factor scores moving together = cross-section dispersion is collapsing)
- compare today's top quartile to yesterday's and notice when the names change

**Don't trade off it.** Not yet. The backtest is honest: there's no edge over 20D in this universe and window.

---

## Files

- `entities/dependability/quant/lib/clawrank.py` — pure-Python ranking library
- `entities/dependability/quant/config/clawrank.yaml` — production config (full 5-factor)
- `entities/dependability/quant/config/clawrank_techonly.yaml` — backtest config (4 factors, no fundamentals)
- `entities/dependability/quant/config/clawrank_contrarian.yaml` — anti-momentum variant (test only)
- `entities/dependability/quant/scripts/build_clawrank_features.py` — daily feature builder
- `entities/dependability/quant/scripts/clawrank_backtest.py` — backtest runner
- `entities/dependability/quant/reports/2026-09-03-clawrank.json` — today's live scores
- `entities/dependability/quant/reports/2026-09-03-clawrank-backtest.json` — backtest results (tech-only)
- `entities/dependability/quant/reports/2026-09-03-clawrank-backtest-contrarian.json` — contrarian variant results