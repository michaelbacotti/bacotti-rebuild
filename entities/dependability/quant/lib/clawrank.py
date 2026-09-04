"""clawrank.py — ClawRank-v0 transparent composite ranking.

Pure-Python module, no I/O. Takes pre-computed feature dicts, returns scores.

Design (see wiki/syntheses/dependability-custom-ranking-system.md):
  5 factors × weighted z-score → raw composite → percentile rank → label.

Why no I/O here: keeps the math testable and reusable. The data layer (yfinance
pulls, info fields) lives in scripts/build_clawrank_table.py. The dashboard
just consumes the JSON output.
"""
from __future__ import annotations

import math
import statistics
from typing import Any, Dict, List, Optional, Tuple

# ----------------------------- helpers -----------------------------

def _safe(value, default=None):
    if value is None:
        return default
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return default
    return value


def _zscore(values: List[Optional[float]], clip: float = 2.0) -> List[float]:
    """Z-score across a cross-section. None inputs map to None output."""
    clean = [v for v in values if v is not None]
    if len(clean) < 2:
        return [0.0 if v is not None else 0.0 for v in values]
    mean = statistics.fmean(clean)
    stdev = statistics.pstdev(clean)
    if stdev == 0:
        return [0.0 if v is not None else 0.0 for v in values]
    out = []
    for v in values:
        if v is None:
            out.append(0.0)  # missing treated as neutral
        else:
            z = (v - mean) / stdev
            out.append(max(-clip, min(clip, z)))
    return out


def _percentile_rank(values: List[float]) -> List[float]:
    """Cross-sectional percentile rank, 0-100. Ties broken by averaging ranks."""
    n = len(values)
    if n == 0:
        return []
    sorted_indices = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[sorted_indices[j + 1]] == values[sorted_indices[i]]:
            j += 1
        avg_rank = (i + j) / 2.0
        for k in range(i, j + 1):
            ranks[sorted_indices[k]] = avg_rank
        i = j + 1
    return [(r / max(n - 1, 1)) * 100.0 for r in ranks]


def _lookup_score(value: Any, lookup: Dict[Any, float], default: float = 50.0) -> Optional[float]:
    if value is None:
        return None
    if value in lookup:
        return lookup[value]
    # try str() match (handles enum-like values from dataframe)
    if str(value) in lookup:
        return lookup[str(value)]
    return default


def _optimal_range_score(value, optimal_low, optimal_max, penalty_below=None, penalty_above=None):
    """Score 0-100 based on whether value falls in an optimal range."""
    if value is None:
        return None
    if optimal_low <= value <= optimal_max:
        return 100.0
    if penalty_below is not None and value < optimal_low:
        # linear decay from 100 at optimal_low down to 0 at penalty_below
        if penalty_below >= optimal_low:
            return 50.0
        span = optimal_low - penalty_below
        return max(0.0, 100.0 * (value - penalty_below) / span)
    if penalty_above is not None and value > optimal_max:
        if penalty_above <= optimal_max:
            return 50.0
        span = penalty_above - optimal_max
        return max(0.0, 100.0 * (penalty_above - value) / span)
    return 50.0


def _sweet_score(value, sweet_low, sweet_high, penalty_above=None, penalty_below=None):
    """Score 100 inside [sweet_low, sweet_high], decay outside toward penalty bounds."""
    if value is None:
        return None
    if sweet_low <= value <= sweet_high:
        return 100.0
    if value < sweet_low:
        if penalty_below is None or penalty_below >= sweet_low:
            return 50.0
        span = sweet_low - penalty_below
        return max(0.0, 100.0 * (value - penalty_below) / span)
    # value > sweet_high
    if penalty_above is None or penalty_above <= sweet_high:
        return 50.0
    span = penalty_above - sweet_high
    return max(0.0, 100.0 * (penalty_above - value) / span)


# ----------------------------- factor scoring -----------------------------

def _factor_score(values: List[Optional[float]], spec: Dict[str, Any], use_higher: bool = True) -> List[float]:
    """Score a sub-metric across the cross-section.

    For directional sub-metrics (e.g., earnings yield, higher = better), values
    are z-scored and rescaled to 0-100 via percentile rank. Direction = lower
    flips the sign before z-scoring.

    For sweet-spot sub-metrics, returns the raw 0-100 score from each ticker's
    individual evaluation, then cross-sectional z-scores those for ranking.
    """
    direction = spec.get("direction", "higher")
    if direction == "sweet":
        # Raw 0-100 per ticker; cross-section rank is implicit in next step
        scored = [_sweet_score(v,
                               sweet_low=spec.get("sweet_low"),
                               sweet_high=spec.get("sweet_high"),
                               penalty_above=spec.get("penalty_above"),
                               penalty_below=spec.get("penalty_below")) for v in values]
    elif direction == "lower":
        scored = [-v if v is not None else None for v in values]
        scored = _zscore(scored, clip=2.0)
    else:  # higher
        scored = _zscore(values, clip=2.0)
    # Convert z-scores to 0-100 percentile-style for the per-factor weighting step
    # Use percentile rank of the z-scores
    zed = _zscore([s for s in scored], clip=2.0)
    return _percentile_rank(zed)


def score_submetric(values: List[Any], spec: Dict[str, Any]) -> List[Optional[float]]:
    """Public: score a single sub-metric given the cross-section of raw values."""
    if spec.get("lookup"):
        return [_lookup_score(v, spec["lookup"]) for v in values]
    if spec.get("direction") == "sweet" and "sweet_low" in spec:
        return [_sweet_score(v,
                             sweet_low=spec.get("sweet_low"),
                             sweet_high=spec.get("sweet_high"),
                             penalty_above=spec.get("penalty_above"),
                             penalty_below=spec.get("penalty_below")) for v in values]
    if "optimal_low" in spec and "optimal_max" in spec:
        return [_optimal_range_score(v,
                                     optimal_low=spec["optimal_low"],
                                     optimal_max=spec["optimal_max"],
                                     penalty_below=spec.get("penalty_below"),
                                     penalty_above=spec.get("penalty_above")) for v in values]
    if spec.get("direction") == "higher" or spec.get("direction") == "lower":
        # Raw cross-section values; convert to 0-100 via percentile rank
        return [float(v) if v is not None else None for v in values]
    return list(values)


def compute_factor(submetric_scores: Dict[str, List[Optional[float]]],
                   submetric_specs: Dict[str, Dict[str, Any]]) -> List[float]:
    """Weighted aggregate of sub-metric 0-100 scores within a factor."""
    # First, transpose to per-ticker: List[Dict[str, Optional[float]]]
    n = None
    for v in submetric_scores.values():
        if v:
            n = len(v); break
    if n is None:
        return []
    per_ticker = [{name: vals[i] for name, vals in submetric_scores.items()} for i in range(n)]

    # Renormalize weights to exclude missing sub-metrics per ticker
    # (default missing_policy = renormalize)
    factor_scores: List[float] = []
    for ticker_sub in per_ticker:
        w_total = 0.0
        score_total = 0.0
        for name, val in ticker_sub.items():
            spec = submetric_specs.get(name, {})
            w = spec.get("weight", 0.0)
            if val is None:
                # missing — skip this sub-metric for this ticker
                continue
            score_total += w * val
            w_total += w
        if w_total == 0:
            factor_scores.append(50.0)  # neutral if all missing
        else:
            factor_scores.append(score_total / w_total)

    # Cross-section: convert factor scores to 0-100 via percentile rank
    return _percentile_rank(factor_scores)


# ----------------------------- composite -----------------------------

def composite(factor_scores: Dict[str, List[float]],
              factor_weights: Dict[str, float]) -> List[float]:
    """Weighted average of factor 0-100 scores → raw composite."""
    names = list(factor_scores.keys())
    if not names:
        return []
    n = len(factor_scores[names[0]])
    raw = []
    for i in range(n):
        total_w = sum(factor_weights.get(name, 0.0) for name in names)
        if total_w == 0:
            raw.append(50.0)
        else:
            raw.append(sum(factor_weights.get(name, 0.0) * factor_scores[name][i] for name in names) / total_w)
    return _percentile_rank(raw)


def label_from(final_scores: List[float], trends: List[str], setups: List[str],
               cfg: Dict[str, Any]) -> List[str]:
    """Apply label rules."""
    rc_min = cfg.get("research_candidate_min", 70)
    av_max = cfg.get("avoid_max", 30)
    require_trend = cfg.get("require_trend_for_research", "uptrend")
    require_setup = set(cfg.get("require_setup_for_research", ["breakout", "pullback_retest"]))
    out = []
    for i, s in enumerate(final_scores):
        if s >= rc_min and (require_trend == "any" or (i < len(trends) and trends[i] == require_trend)) \
                and (i < len(setups) and setups[i] in require_setup):
            out.append("Research candidate")
        elif s <= av_max and i < len(trends) and trends[i] == "downtrend":
            out.append("Avoid")
        else:
            out.append("Watchlist")
    return out


# ----------------------------- top-level -----------------------------

def rank(rows: List[Dict[str, Any]], cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Run ClawRank over a list of per-ticker feature dicts.

    Each row must contain all fields referenced by the factor specs in cfg
    (e.g., `earnings_yield`, `revenue_growth`, `rsi_14`, etc.). Missing
    fields are tolerated — the renormalization policy applies.
    """
    factors = cfg.get("factors", {})
    norm_cfg = cfg.get("normalization", {})
    composite_cfg = cfg.get("composite", {})

    factor_results: Dict[str, List[float]] = {}
    submetric_breakdown: Dict[str, Dict[str, List[Optional[float]]]] = {}

    for factor_name, factor_cfg in factors.items():
        sub_scores: Dict[str, List[Optional[float]]] = {}
        sub_specs: Dict[str, Dict[str, Any]] = {}
        for sm_name, sm_spec in factor_cfg.get("sub_metrics", {}).items():
            field_key = sm_spec.get("field", sm_name)
            vals = [row.get(field_key) for row in rows]
            # Skip if all missing
            if all(v is None for v in vals):
                continue
            # Some metrics need preprocessing
            direction = sm_spec.get("direction", "higher")
            if direction == "lower":
                # invert for cross-sectional comparison: we score on negated values
                # the score_submetric helper doesn't invert; do it here
                inv_vals = [-v if v is not None else None for v in vals]
                scored = score_submetric(inv_vals, {**sm_spec, "direction": "higher"})
            else:
                scored = score_submetric(vals, sm_spec)
            # Floor on raw value for adv_usd_m
            if "floor" in sm_spec:
                scored = [max(sm_spec["floor"], s) if s is not None else None for s in scored]
            sub_scores[sm_name] = scored
            sub_specs[sm_name] = sm_spec
        if not sub_scores:
            continue
        factor_results[factor_name] = compute_factor(sub_scores, sub_specs)
        submetric_breakdown[factor_name] = sub_scores

    raw_composite = composite(factor_results,
                              {name: f["weight"] for name, f in factors.items() if name in factor_results})
    trends = [row.get("trend", "n/a") for row in rows]
    setups = [row.get("setup", "unavailable") for row in rows]
    labels = label_from(raw_composite, trends, setups, composite_cfg)

    # Build output rows
    out_rows = []
    for i, row in enumerate(rows):
        out = dict(row)  # copy
        out["clawrank_score"] = round(raw_composite[i], 1) if i < len(raw_composite) else None
        for fname, scores in factor_results.items():
            out[f"clawrank_{fname}"] = round(scores[i], 1) if i < len(scores) else None
        out["clawrank_label"] = labels[i] if i < len(labels) else "Watchlist"
        # Sub-metric drilldown
        drill = {}
        for fname, sms in submetric_breakdown.items():
            for sm_name, vals in sms.items():
                drill[f"{fname}.{sm_name}"] = vals[i] if i < len(vals) else None
        out["clawrank_breakdown"] = drill
        out_rows.append(out)
    return out_rows


def load_config(path: str) -> Dict[str, Any]:
    """Load YAML config via PyYAML.

    PyYAML ships with Python 3.14+ in this environment; if a host lacks it,
    install with `pip install pyyaml` (no external API dependency added).
    """
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)
