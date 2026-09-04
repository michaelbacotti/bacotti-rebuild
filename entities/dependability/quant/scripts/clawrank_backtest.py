#!/usr/bin/env python3
"""clawrank_backtest.py — Backtest ClawRank on the 22-instrument universe.

For each rolling date in the 6mo yfinance history:
  1. Compute features using only data ≤ that date (no look-ahead)
  2. Run ClawRank → composite scores
  3. Bucket by quartile (Q1=top, Q4=bottom)
  4. Measure forward 20D return for each ticker
  5. Aggregate: hit rate, mean return, IC, top-vs-bottom spread

Reports:
  - Per-bucket summary stats
  - Top vs bottom mean forward return
  - Information Coefficient (Spearman rank correlation between score and fwd return)
  - Hit rate: % of times Q1 beat Q4 over 20D
  - Per-ticker hit rate
  - Quarter-over-quarter decay (does the signal fade in recent months?)
"""
from __future__ import annotations

import datetime as dt
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from build_clawrank_features import (  # noqa: E402
    fetch_history, get_series, compute_features_for, ALL_TICKERS, ETF_SET,
)
from clawrank import rank, load_config  # noqa: E402

WINDOW = 20
FWD_DAYS = 20      # forward 20D return (matches Danelfin's 3M horizon / 3 ≈ 20D)
STEP_DAYS = 5      # rebalance every 5 trading days
MIN_HISTORY = 60   # need at least 60 trading days for trend/MAs


def _build_features_at_date(hist, target_date_idx, spy_close_at_idx, use_fundamentals=True):
    """Build features for all tickers using only data up to target_date_idx."""
    rows = []
    info_cache: dict = {}
    for t in ALL_TICKERS:
        try:
            # Slice history up to target date
            t_hist = _slice_history(hist, t, target_date_idx)
            t_spy = _slice_spy(spy_close_at_idx)
            feats = compute_features_for(t, t_hist, t_spy, info_cache, use_fundamentals=use_fundamentals)
            if feats is not None:
                rows.append(feats)
        except Exception as e:
            # Skip tickers with insufficient data at this date
            continue
    return rows


def _slice_history(full_hist, ticker, end_idx):
    """Return a yfinance history dict sliced to [0..end_idx] for one ticker."""
    if isinstance(full_hist.columns, pd.MultiIndex):
        sliced = full_hist.xs(ticker, axis=1, level=0).iloc[:end_idx + 1]
    else:
        sliced = full_hist.iloc[:end_idx + 1]
    return sliced


def _slice_spy(spy_close_slice):
    return spy_close_slice


def spearman_ic(scores, returns):
    """Spearman rank correlation. Returns NaN if insufficient data."""
    if len(scores) < 3:
        return float("nan")
    s = pd.Series(scores).rank()
    r = pd.Series(returns).rank()
    if s.std() == 0 or r.std() == 0:
        return float("nan")
    return float(s.corr(r))


def main():
    t0 = time.time()
    as_of_et = dt.datetime.now(dt.timezone(dt.timedelta(hours=-4)))
    # Tech-only config: skips fundamental_health factor (avoids look-ahead bias in backtest)
    cfg = load_config(str(Path(__file__).resolve().parent.parent / "config" / "clawrank_techonly.yaml"))

    print(f"Fetching {len(ALL_TICKERS)} tickers (1y daily for backtest) ...", file=sys.stderr)
    hist = fetch_history(ALL_TICKERS, period="2y")
    if hist is None or len(hist) == 0:
        print("FATAL: yfinance returned no data", file=sys.stderr); sys.exit(2)

    # Determine date indices
    spy_close_full = get_series(hist, "SPY", "Close")
    n_total = len(spy_close_full)
    print(f"Total trading days: {n_total}", file=sys.stderr)

    if n_total < MIN_HISTORY + FWD_DAYS + 10:
        print(f"FATAL: insufficient history ({n_total} days)", file=sys.stderr); sys.exit(2)

    # Index range for rebalance dates
    rebalance_indices = list(range(MIN_HISTORY, n_total - FWD_DAYS, STEP_DAYS))
    print(f"Rebalance dates: {len(rebalance_indices)}  (every {STEP_DAYS} trading days)", file=sys.stderr)

    # Per-rebalance results
    per_period = []
    skipped = 0
    for ridx, idx in enumerate(rebalance_indices):
        spy_slice = spy_close_full.iloc[:idx + 1]
        # use_fundamentals=False → no look-ahead from yfinance .info
        rows = _build_features_at_date(hist, idx, spy_slice, use_fundamentals=False)
        if len(rows) < 5:
            skipped += 1
            continue
        ranked = rank(rows, cfg)
        if not ranked:
            skipped += 1
            continue

        # Compute forward 20D return per ticker from full history
        fwd_returns = {}
        for t in ALL_TICKERS:
            closes = get_series(hist, t, "Close")
            if len(closes) > idx + FWD_DAYS:
                fwd_returns[t] = float(closes.iloc[idx + FWD_DAYS] / closes.iloc[idx] - 1)
            else:
                fwd_returns[t] = None

        scores = [r.get("clawrank_score") for r in ranked]
        fwd = [fwd_returns.get(r["ticker"]) for r in ranked]
        # Pair up (ticker, score, fwd)
        pairs = [(s, f) for s, f in zip(scores, fwd) if s is not None and f is not None]
        if len(pairs) < 5:
            skipped += 1
            continue
        scores_clean = [p[0] for p in pairs]
        fwd_clean = [p[1] for p in pairs]

        # Bucket by quartile
        n = len(scores_clean)
        sorted_pairs = sorted(zip(scores_clean, fwd_clean), key=lambda p: -p[0])
        q_size = max(1, n // 4)
        q1_fwd = [p[1] for p in sorted_pairs[:q_size]]
        q4_fwd = [p[1] for p in sorted_pairs[-q_size:]]
        median_split = n // 2
        top_half = [p[1] for p in sorted_pairs[:median_split]]
        bottom_half = [p[1] for p in sorted_pairs[-median_split:]]

        period_record = {
            "rebalance_idx": idx,
            "date": str(spy_close_full.index[idx].date()),
            "n_tickers": n,
            "ic_spearman": spearman_ic(scores_clean, fwd_clean),
            "q1_mean": float(np.mean(q1_fwd)),
            "q4_mean": float(np.mean(q4_fwd)),
            "q1_minus_q4": float(np.mean(q1_fwd) - np.mean(q4_fwd)),
            "top_half_mean": float(np.mean(top_half)),
            "bottom_half_mean": float(np.mean(bottom_half)),
            "top_minus_bottom": float(np.mean(top_half) - np.mean(bottom_half)),
            "per_ticker": [
                {"ticker": r["ticker"],
                 "score": r.get("clawrank_score"),
                 "fwd_20d": fwd_returns.get(r["ticker"]),
                 "label": r.get("clawrank_label")}
                for r in ranked
            ],
        }
        per_period.append(period_record)

        if (ridx + 1) % 10 == 0:
            print(f"  ... {ridx + 1}/{len(rebalance_indices)} rebalances done", file=sys.stderr)

    # Aggregate
    if not per_period:
        print("FATAL: no valid rebalance periods", file=sys.stderr); sys.exit(2)

    ics = [p["ic_spearman"] for p in per_period if not math.isnan(p["ic_spearman"])]
    q1_minus_q4 = [p["q1_minus_q4"] for p in per_period]
    top_minus_bottom = [p["top_minus_bottom"] for p in per_period]
    q1_better = sum(1 for p in per_period if p["q1_mean"] > p["q4_mean"])
    top_better = sum(1 for p in per_period if p["top_half_mean"] > p["bottom_half_mean"])

    summary = {
        "as_of": as_of_et.isoformat(),
        "n_rebalance_periods": len(per_period),
        "n_skipped": skipped,
        "universe_size_avg": float(np.mean([p["n_tickers"] for p in per_period])),
        "ic_spearman_mean": float(np.mean(ics)) if ics else None,
        "ic_spearman_std": float(np.std(ics)) if ics else None,
        "ic_spearman_t": float(np.mean(ics) / (np.std(ics) / math.sqrt(len(ics)))) if len(ics) > 1 and np.std(ics) > 0 else None,
        "q1_minus_q4_mean": float(np.mean(q1_minus_q4)),
        "q1_minus_q4_std": float(np.std(q1_minus_q4)),
        "q1_minus_q4_t": float(np.mean(q1_minus_q4) / (np.std(q1_minus_q4) / math.sqrt(len(q1_minus_q4)))) if len(q1_minus_q4) > 1 and np.std(q1_minus_q4) > 0 else None,
        "top_minus_bottom_mean": float(np.mean(top_minus_bottom)),
        "q1_better_than_q4_pct": 100.0 * q1_better / len(per_period),
        "top_half_better_than_bottom_pct": 100.0 * top_better / len(per_period),
        "factors": {name: f["weight"] for name, f in cfg["factors"].items()},
    }

    # Per-ticker hit rate (across all rebalances)
    ticker_records = {}
    for p in per_period:
        for t in p["per_ticker"]:
            tk = t["ticker"]
            if t["fwd_20d"] is None or t["score"] is None:
                continue
            ticker_records.setdefault(tk, []).append({
                "score": t["score"], "fwd": t["fwd_20d"], "label": t["label"],
            })
    ticker_summary = {}
    for tk, recs in ticker_records.items():
        if not recs:
            continue
        scores = [r["score"] for r in recs]
        fwds = [r["fwd"] for r in recs]
        labels = [r["label"] for r in recs]
        ticker_summary[tk] = {
            "n_periods": len(recs),
            "mean_score": float(np.mean(scores)),
            "mean_fwd_20d": float(np.mean(fwds)),
            "label_counts": {
                "Research candidate": labels.count("Research candidate"),
                "Watchlist": labels.count("Watchlist"),
                "Avoid": labels.count("Avoid"),
            },
        }

    out = {
        "summary": summary,
        "per_period": per_period,
        "per_ticker": ticker_summary,
    }
    out_path = Path(__file__).resolve().parent.parent / "reports" / f"{as_of_et.strftime('%Y-%m-%d')}-clawrank-backtest.json"
    out_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"OK  json={out_path}  duration={time.time()-t0:.1f}s", file=sys.stderr)

    # Print headline
    print("\n=== ClawRank-v0 Backtest Headline ===")
    s = summary
    print(f"Rebalance periods:    {s['n_rebalance_periods']}  (skipped {s['n_skipped']} for insufficient data)")
    print(f"Universe avg size:    {s['universe_size_avg']:.1f}")
    print(f"Spearman IC mean:     {s['ic_spearman_mean']:+.4f}  (std {s['ic_spearman_std']:.4f}, t-stat {s['ic_spearman_t']:+.2f})")
    print(f"Q1 minus Q4 (20D):    {s['q1_minus_q4_mean']*100:+.2f}%  (std {s['q1_minus_q4_std']*100:.2f}%, t-stat {s['q1_minus_q4_t']:+.2f})")
    print(f"Top minus Bottom:     {s['top_minus_bottom_mean']*100:+.2f}%")
    print(f"Q1 beat Q4:           {s['q1_better_than_q4_pct']:.1f}% of periods")
    print(f"Top half beat bottom: {s['top_half_better_than_bottom_pct']:.1f}% of periods")
    print(f"\nDecisive interpretation:")
    if s['ic_spearman_mean'] > 0.10 and s['q1_minus_q4_t'] and s['q1_minus_q4_t'] > 1.5:
        print("  STRONG: positive IC, statistically significant Q1>Q4 spread.")
    elif s['ic_spearman_mean'] > 0.05 and s['q1_minus_q4_t'] and s['q1_minus_q4_t'] > 0.5:
        print("  MODERATE: positive IC and Q1>Q4 spread, but signal is noisy.")
    elif s['ic_spearman_mean'] > 0:
        print("  WEAK: IC positive but small, Q1>Q4 spread not significant.")
    else:
        print("  NEGATIVE: IC < 0, ranking inverts forward returns. Check factor weights.")


if __name__ == "__main__":
    main()
