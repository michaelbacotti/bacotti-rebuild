"""
lib/research_memo.py
Workstream F.6 — Compose printable research memos per profile.

Charter: research-only. No execution, no brokerage creds, no order placement.

Templates:
  memo_macro_dashboard(dashboard)          -> Markdown memo for Profile 1
  memo_directionality(symbol, payload, ...) -> Markdown memo for Profile 2
  memo_forecast(symbol, forecast_payload)   -> Markdown table for Profile 3
  memo_candidate_table(symbol, candidates)  -> Markdown table for Profile 6
  memo_hedge(hedge_payload)                 -> Markdown memo for Profile 5
  memo_earnings(earnings_payload)           -> Markdown memo for Profile 4

All memos:
  - Show "aligned / neutral / counter-regime" macro tag for downstream profiles
  - Show regime + bear-risk + confidence from latest macro_dashboard
  - Display size bands as context only (never as score input)
  - Carry validation_status visibly
  - Use Mike's preferred wording: "probability band", "forecast interval"
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

MEMO_ROOT = Path(__file__).resolve().parents[1] / "data" / "memos"

# Default sizing bands (per F.11 §9 — display context only)
DEFAULT_SIZING_BANDS = {
    "short-term": "generally under $500",
    "most":       "generally under $1,000",
    "long-term":  "occasionally $1,000–$5,000 (higher-conviction ideas only)",
}


def _now_local() -> datetime:
    return datetime.now().astimezone()


def _iso(dt: Optional[datetime] = None) -> str:
    return (dt or _now_local()).isoformat(timespec="seconds")


def _macro_tag(macro_context: Optional[dict]) -> str:
    """Classify a downstream thesis as aligned / neutral / counter-regime
    against the most recent macro regime."""
    if not macro_context:
        return "neutral (no macro context)"
    regime = macro_context.get("regime", "unknown")
    bear = macro_context.get("bear_risk_level", "low")
    # Without a directional tag in payload, the memo is informational; flag as neutral
    return f"neutral (regime={regime}, bear_risk={bear})"


def _size_band_text(kind: str) -> str:
    """Display context for sizing bands; never a score input."""
    if kind in ("defined_risk_spread", "earnings_iv_crush"):
        return f"short-term trades: {DEFAULT_SIZING_BANDS['short-term']}; most trades: {DEFAULT_SIZING_BANDS['most']}"
    if kind == "hedge":
        return f"research output only — Mike decides whether to execute; sizing bands apply if Mike acts"
    return f"most trades: {DEFAULT_SIZING_BANDS['most']}; long-term/high-conviction: {DEFAULT_SIZING_BANDS['long-term']}"


def _resolve_macro_context() -> Optional[dict]:
    """Read the latest macro_dashboard payload from the ledger."""
    try:
        from research_ledger import read_recent
        rows = read_recent(profile="macro_dashboard", limit=1)
    except Exception:
        return None
    if not rows:
        return None
    payload = rows[0].get("payload", {})
    dashboard = payload.get("dashboard", payload)
    return {
        "regime": dashboard.get("regime"),
        "bear_risk_level": dashboard.get("bear_risk_level"),
        "bear_risk_score": dashboard.get("bear_risk_score"),
        "composite_score": dashboard.get("composite_score"),
        "confidence": dashboard.get("confidence"),
        "as_of_ts": dashboard.get("as_of_ts"),
        "validation_status": dashboard.get("validation_status"),
    }


# ---------------------------------------------------------------------------
# Profile 1 — Macro dashboard memo
# ---------------------------------------------------------------------------

def memo_macro_dashboard(dashboard: dict) -> str:
    regime = dashboard.get("regime", "unknown")
    bear = dashboard.get("bear_risk_level", "unknown")
    confidence = dashboard.get("confidence", "n/a")
    composite = dashboard.get("composite_score", "n/a")
    val_status = dashboard.get("validation_status", "preliminary")
    # Fix C (2026-09-02 20:30 ET): also show data_completeness explicitly.
    data_completeness = dashboard.get("data_completeness", "complete")
    missing_pillars = dashboard.get("missing_pillars", [])
    posterior = dashboard.get("regime_posterior", {})

    lines: list[str] = []
    lines.append(f"# Macro Regime Dashboard — {dashboard.get('as_of_ts', 'n/a')[:10]}")
    lines.append("")
    lines.append(f"**Regime:** `{regime}`  |  **Bear-risk level:** `{bear}`  |  "
                 f"**Composite score:** `{composite}`  |  **Confidence:** `{confidence}`  |  "
                 f"**Calibration:** `{val_status}`  |  **Data completeness:** `{data_completeness}`")
    if missing_pillars:
        lines.append("")
        lines.append(f"**Missing pillars:** {', '.join(missing_pillars)}")
    lines.append("")
    lines.append("**Regime posterior (probability across 5 regime labels):**")
    for k, v in sorted(posterior.items(), key=lambda x: -x[1]):
        bar = "█" * int(v * 40)
        lines.append(f"  - `{k:>22s}`  {v:.3f}  {bar}")
    lines.append("")

    lines.append("## Eight pillars")
    lines.append("")
    lines.append("| Pillar | State | Score | Confidence | Source TS |")
    lines.append("|---|---|---:|---:|---|")
    for letter in "ABCDEFGH":
        p = dashboard.get("pillars", {}).get(letter, {})
        state = p.get("state", "n/a")
        score = p.get("score", "n/a")
        conf = p.get("confidence", "n/a")
        src_ts = (p.get("source_ts") or "n/a")[:19]
        pillar_name = p.get("pillar", "")
        short = pillar_name.split("_", 1)[1].replace("_", " ") if "_" in pillar_name else pillar_name
        lines.append(f"| {letter} {short} | {state} | {score} | {conf} | {src_ts} |")
    lines.append("")

    lines.append("## Per-pillar evidence and latest readings")
    lines.append("")
    for letter in "ABCDEFGH":
        p = dashboard.get("pillars", {}).get(letter, {})
        if not p:
            continue
        lines.append(f"### {letter} — {p.get('pillar', '?')}")
        lines.append(f"**State:** {p.get('state')}  |  **Lookback:** {p.get('lookback','?')}")
        lines.append(f"**Evidence:** {p.get('evidence','?')}")
        latest = p.get("latest", {}) or {}
        if latest:
            lines.append("")
            lines.append("```")
            for k, v in latest.items():
                lines.append(f"  {k:>22s}: {v}")
            lines.append("```")
        mdw = p.get("missing_data_warning", []) or []
        if mdw:
            lines.append("")
            lines.append(f"**Missing data:** {', '.join(mdw)}")
        lines.append("")

    lines.append("## Disconfirming evidence")
    de = dashboard.get("disconfirming_evidence", []) or []
    if de:
        for x in de:
            lines.append(f"- {x}")
    else:
        lines.append("- (none flagged)")
    lines.append("")

    lines.append("## Upgrade conditions (toward bear_risk_elevated)")
    for x in dashboard.get("upgrade_conditions", []) or []:
        lines.append(f"- {x}")
    lines.append("")
    lines.append("## Downgrade conditions (toward risk_on)")
    for x in dashboard.get("downgrade_conditions", []) or []:
        lines.append(f"- {x}")
    lines.append("")

    lines.append("## Calibration thresholds (per F.3 §2.6)")
    lines.append("```")
    lines.append(json.dumps(dashboard.get("calibration_thresholds", {}), indent=2))
    lines.append("```")
    lines.append("")
    lines.append("---")
    lines.append("*Research output only. Mike decides action.*")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Profile 2 — Directionality memo
# ---------------------------------------------------------------------------

def memo_directionality(
    symbol: str,
    payload: dict,
    macro_context: Optional[dict] = None,
    direction_label: str = "neutral",
    confidence: str = "moderate",
    evidence: Optional[list[str]] = None,
    disconfirming: Optional[list[str]] = None,
    invalidators: Optional[list[str]] = None,
    validation_status: str = "preliminary",
) -> str:
    mc = macro_context or _resolve_macro_context()
    tag = _macro_tag(mc)
    evidence = evidence or []
    disconfirming = disconfirming or []
    invalidators = invalidators or []

    lines = []
    lines.append(f"# Directionality Research Memo — {symbol} — {_iso()[:10]}")
    lines.append("")
    lines.append(f"**Direction:** `{direction_label}`  |  **Confidence:** `{confidence}`  |  "
                 f"**Macro tag:** `{tag}`")
    lines.append(f"**Validation:** `{validation_status}` (per F.3 §3.3)")
    lines.append("")
    lines.append("**Sizing bands (display context only — never a score input):**")
    lines.append(f"  - {_size_band_text('directionality')}")
    lines.append("")

    chart = payload.get("chart", {})
    lines.append("## Chart state")
    if chart:
        lines.append(f"- Trend: {chart.get('trend','?')} | MA alignment: {chart.get('ma_alignment','?')}")
        lines.append(f"- Score: {chart.get('score_total','?')} ({chart.get('score_label','?')})")
        top = chart.get("top_pattern", {}) or {}
        if top:
            lines.append(f"- Top pattern: {top.get('type','?')} | state: {top.get('state','?')}")
            lines.append(f"- Trigger: {top.get('trigger_price','?')} | Support: {chart.get('support','?')} | "
                         f"Resistance: {chart.get('resistance','?')} | Invalidation: {top.get('invalidation','?')}")
    else:
        lines.append("- (no chart payload)")
    lines.append("")

    flow = payload.get("flow", {})
    lines.append("## Flow block")
    if flow:
        for k, v in flow.items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- (no flow payload)")
    lines.append("")

    lines.append("## Supporting evidence")
    if evidence:
        for x in evidence:
            lines.append(f"- {x}")
    else:
        lines.append("- (none provided)")
    lines.append("")

    lines.append("## Disconfirming evidence")
    if disconfirming:
        for x in disconfirming:
            lines.append(f"- {x}")
    else:
        lines.append("- (none provided)")
    lines.append("")

    lines.append("## Macro factors most likely to invalidate the idea")
    if invalidators:
        for x in invalidators:
            lines.append(f"- {x}")
    else:
        lines.append("- (none provided)")
    lines.append("")

    lines.append("## Macro context (from latest dashboard)")
    if mc:
        lines.append(f"- Regime: `{mc.get('regime','?')}` | Bear-risk: `{mc.get('bear_risk_level','?')}` "
                     f"| Confidence: `{mc.get('confidence','?')}`")
        lines.append(f"- Dashboard as of: {mc.get('as_of_ts','?')}")
    else:
        lines.append("- (no macro context)")
    lines.append("")
    lines.append("---")
    lines.append("*Research memo describes candidate. Mike decides action. "
                 "Position sizing bands shown above are display context only.*")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Profile 3 — Forecast interval table
# ---------------------------------------------------------------------------

def memo_forecast(symbol: str, forecast_payload: dict, macro_context: Optional[dict] = None) -> str:
    mc = macro_context or _resolve_macro_context()
    tag = _macro_tag(mc)
    horizons = forecast_payload.get("horizons", {})
    val_status = forecast_payload.get("validation_status", "preliminary")

    lines = []
    lines.append(f"# Forecast Interval Table — {symbol} — {_iso()[:10]}")
    lines.append("")
    lines.append(f"**Macro tag:** `{tag}`  |  **Validation:** `{val_status}`  |  "
                 f"**Blend:** GBM {forecast_payload.get('blend_weights',{}).get('gbm','?')} + "
                 f"IV {forecast_payload.get('blend_weights',{}).get('iv','?')} + "
                 f"Hist {forecast_payload.get('blend_weights',{}).get('hist','?')}")
    lines.append("")
    lines.append("Wording: **probability band** / **forecast interval** (NOT \"probable range\").")
    lines.append("")
    lines.append("| Horizon | Trading days | Median (USD) | Band 68 (USD) | Band 90 (USD) | Method |")
    lines.append("|---|---:|---:|---|---|---|")
    for hname in ("1w", "2w", "1mo", "2mo", "3mo", "6mo", "1y"):
        if hname not in horizons:
            continue
        h = horizons[hname]
        lines.append(f"| {hname} | {h.get('trading_days','?')} | "
                     f"{h.get('median','?')} | "
                     f"[{h.get('band_68',[''])[0]:.2f}, {h.get('band_68',[''])[1]:.2f}] | "
                     f"[{h.get('band_90',[''])[0]:.2f}, {h.get('band_90',[''])[1]:.2f}] | "
                     f"{', '.join(h.get('sources', []))} |")
    lines.append("")
    lines.append("**Macro conditioning:** band-width multiplier scales with bear-risk level "
                 "(see F.3 §1.1).")
    lines.append("")
    lines.append("**Calibration thresholds (per F.3 §4.4):**")
    lines.append("- ≥ 30 resolved forward signals per symbol-horizon")
    lines.append("- |empirical_coverage_68 − 0.68| ≤ 0.10")
    lines.append("- |empirical_coverage_90 − 0.90| ≤ 0.10")
    lines.append("- MAE_return ≤ 0.15 × forecast_band_width")
    lines.append("- All four conditions must hold simultaneously to graduate to `validated`.")
    lines.append("")
    lines.append("---")
    lines.append("*Forecast intervals are research, not instruction. "
                 "Mike decides whether to act on the bands.*")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Profile 6 — Defined-risk spread candidate table
# ---------------------------------------------------------------------------

def memo_candidate_table(
    symbol: str,
    candidates: list[dict],
    macro_context: Optional[dict] = None,
    directional_view: Optional[str] = None,
) -> str:
    mc = macro_context or _resolve_macro_context()
    tag = _macro_tag(mc)

    lines = []
    lines.append(f"# Defined-Risk Spread Candidates — {symbol} — {_iso()[:10]}")
    lines.append("")
    lines.append(f"**Macro tag:** `{tag}`  |  "
                 f"**Directional view (optional):** `{directional_view or 'neutral'}`  |  "
                 f"**Validation:** `preliminary` on every row")
    lines.append("")
    lines.append("**Sizing bands (display context only — never a score input):**")
    lines.append(f"  - short-term trades: {DEFAULT_SIZING_BANDS['short-term']}")
    lines.append(f"  - most trades: {DEFAULT_SIZING_BANDS['most']}")
    lines.append("")
    lines.append("| Kind | DTE | Debit/Credit | Max Gain | Max Loss | Breakevens | POP | Edge | OI sum | Spread % | Liquidity | Notes |")
    lines.append("|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---|---|")
    for c in candidates:
        lines.append(
            f"| {c.get('kind','?')} | {c.get('dte','?')} | "
            f"${c.get('debit', c.get('credit', 0)):.2f} | "
            f"${c.get('max_gain',0):.2f} | ${c.get('max_loss',0):.2f} | "
            f"{c.get('breakevens','?')} | {c.get('pop_estimate','?'):.2f} | "
            f"{c.get('edge_pct','?'):.2f} | {c.get('liquidity_oi_sum','?')} | "
            f"{c.get('spread_pct_of_mid','?'):.2f} | "
            f"{c.get('liquidity_tier','?')} | {c.get('notes','?')} |"
        )
    lines.append("")
    lines.append("**Vetoes (hard gates):**")
    lines.append("- Liquidity: OI < 100 or spread > 7% (excluded, not downgraded)")
    lines.append("- POP < 0.55 (per rules.yaml#candidates.min_pop_pct)")
    lines.append("- Premium edge < 0.10")
    lines.append("- Naked short / straddle / strangle excluded (defined-risk-positive gate)")
    lines.append("- Days-to-earnings < 2")
    lines.append("")
    lines.append("**Counter-regime macro adjustment:**")
    lines.append("- When macro tag is `counter-regime`, premium-edge threshold is raised to 0.15")
    lines.append("- Wider downside/risk bands surface; lower confidence grade")
    lines.append("- Stronger disconfirming-evidence requirement")
    lines.append("")
    lines.append("---")
    lines.append("*Candidate table describes research. Mike decides action.*")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Profile 5 — Hedge memo
# ---------------------------------------------------------------------------

def memo_hedge(symbol: str, hedge_payload: dict, macro_context: Optional[dict] = None) -> str:
    mc = macro_context or _resolve_macro_context()
    lines = []
    lines.append(f"# Hedge Research Memo — {symbol} — {_iso()[:10]}")
    lines.append("")
    lines.append("**Macro context (informational header, never a veto):**")
    if mc:
        lines.append(f"- Regime: `{mc.get('regime','?')}` | Bear-risk: `{mc.get('bear_risk_level','?')}`")
        lines.append(f"- Dashboard as of: {mc.get('as_of_ts','?')}")
    else:
        lines.append("- (no macro context)")
    lines.append("")
    lines.append("**Hedge candidates (research output only):**")
    candidates = hedge_payload.get("candidates", [])
    if not candidates:
        lines.append("- (no candidates surfaced)")
    for c in candidates:
        lines.append(f"- {c.get('kind','?')}: cost=${c.get('cost','?')}, "
                     f"protection=${c.get('protection_dollar','?')}, "
                     f"days_to_expiry={c.get('days_to_expiry','?')}")
    lines.append("")
    lines.append("**Qualitative caveats (always present):**")
    lines.append("- Tail risk: gap-through overnight; defined-risk structures do not protect vs >1σ gap")
    lines.append("- Liquidity at open can be poor; place earlier rather than at the open")
    lines.append("- Hedge is research output only — Mike decides whether to execute")
    lines.append("")
    lines.append("---")
    lines.append("*Research memo describes hedge candidates. Mike decides whether to act.*")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Profile 4 — Earnings memo
# ---------------------------------------------------------------------------

def memo_earnings(symbol: str, earnings_payload: dict, macro_context: Optional[dict] = None) -> str:
    mc = macro_context or _resolve_macro_context()
    lines = []
    lines.append(f"# Earnings / IV-Crush Research Memo — {symbol} — {_iso()[:10]}")
    lines.append("")
    lines.append(f"**Macro tag:** `{_macro_tag(mc)}`")
    lines.append(f"**Validation:** `{earnings_payload.get('validation_status', 'preliminary')}`")
    lines.append("")
    lines.append("**Event facts:**")
    for k, v in (earnings_payload.get("event_facts") or {}).items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("**Market-implied move vs realized history (per F.3 §5.1):**")
    for k, v in (earnings_payload.get("implied_vs_realized") or {}).items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("**Candidate structures (defined-risk only, no naked premium):**")
    for s in earnings_payload.get("structures", []) or []:
        lines.append(f"- {s.get('kind','?')}: max_gain=${s.get('max_gain','?')}, "
                     f"max_loss=${s.get('max_loss','?')}, POP={s.get('pop_estimate','?')}")
    lines.append("")
    lines.append("**Failure analysis (per F.3 §5.1):**")
    for f in earnings_payload.get("failure_analysis", []) or []:
        lines.append(f"- {f}")
    lines.append("")
    lines.append("**Verdict options (Mike chooses):**")
    lines.append("- `watched` / `avoid` / `research further` / `conditional idea`")
    lines.append("")
    lines.append("---")
    lines.append("*Earnings memo describes research. Mike decides whether to act.*")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Save helper
# ---------------------------------------------------------------------------

def save_memo(memo_text: str, profile: str, name: str) -> Path:
    MEMO_ROOT.mkdir(parents=True, exist_ok=True)
    safe_name = name.replace("/", "-").replace(" ", "_")
    path = MEMO_ROOT / f"{profile}_{safe_name}_{_iso()[:10]}.md"
    path.write_text(memo_text)
    return path


if __name__ == "__main__":
    # Self-test
    sample = {
        "as_of_ts": _iso(),
        "regime": "fragile_risk_on",
        "regime_posterior": {"risk_on": 0.18, "fragile_risk_on": 0.42, "transition": 0.21, "risk_off": 0.12, "bear_risk_elevated": 0.07},
        "bear_risk_level": "moderate",
        "bear_risk_score": 0.42,
        "composite_score": 0.054,
        "confidence": 0.62,
        "validation_status": "preliminary",
        "calibration_thresholds": {},
        "pillars": {},
        "disconfirming_evidence": [],
        "upgrade_conditions": [],
        "downgrade_conditions": [],
    }
    print(memo_macro_dashboard(sample))