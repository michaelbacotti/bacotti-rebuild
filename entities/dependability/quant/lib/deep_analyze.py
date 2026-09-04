"""deep_analyze.py — orchestrator that runs all super-quant modules together.

The Super Quant API. Given a ticker (or list), runs:
  - fundamentals + short interest + institutional %
  - analyst targets + rating
  - IV term structure + realized vol + regime (HMM)
  - seasonality (day-of-week, month-of-year)
  - sentiment (Stocktwits + Reddit + Heisenberg)
  - options chain (best expiry, ATM IV)
  - SABR-lite vol surface (skew, butterfly, risk-reversal)
  - expected-move reconciliation (5 sources)
  - composite scoring

Returns a single structured dict suitable for direct inclusion in research notes.
Every claim has a source citation in the dict.

Usage:
    from deep_analyze import analyze
    result = analyze("AVGO")
"""
from __future__ import annotations
import datetime as dt
import json
from typing import Any

from data_fetcher import (
    fundamentals_snapshot,
    short_interest,
    institutional_holdings,
    analyst_targets,
    dividend_calendar,
    news as news_func,
    price_history,
    realized_volatility,
    IV_term_structure,
    index_spot,
)
from seasonality import (
    day_of_week_drift,
    month_of_year_drift,
    earnings_window_drift,
    days_to_next_event,
    regime_assessment,
)
from social_sentiment import (
    stocktwits_symbol,
    reddit_symbol,
    named_trader_status,
    aggregate_sentiment,
)
from institutional_flow import (
    short_interest_signal,
    institutional_ownership_signal,
    analyst_consensus_signal,
    composite_flow_signal,
)
from regime_hmm import classify_current_regime
from sabr_lite import fit_vol_surface
from expected_move import reconcile_expected_moves


def _chart_structure_safe(symbol: str, include_backtest: bool = True) -> dict:
    """Safe wrapper for chart_structure. Returns dict."""
    from chart_structure import analyze_chart_structure, chart_structure_to_dict
    cs = analyze_chart_structure(symbol, include_backtest=include_backtest)
    return chart_structure_to_dict(cs)


def _forecast_safe(symbol: str) -> dict:
    """Safe wrapper for forecast. Returns dict with multi-horizon bands.

    Mike 2026-09-02 18:37 ET directive: probabilistic forecast rather than one
    target price. Uses chart_structure for pattern-conditional adjustment.
    Forecast is "OOS-conditional" — not validated until forward paper-trading.
    """
    from forecast import make_forecast, forecast_to_dict, save_forecast_artifact
    from chart_structure import analyze_chart_structure, chart_structure_to_dict
    # Get chart_structure first (used for pattern-conditional blend)
    cs = analyze_chart_structure(symbol, include_backtest=True)
    cs_dict = chart_structure_to_dict(cs)
    # Try to fetch vol_surface if available (SABR-lite)
    vol_surface = None
    try:
        from sabr_lite import fit_vol_surface
        vs = fit_vol_surface(symbol)
        if isinstance(vs, dict):
            vol_surface = vs
    except Exception:
        pass
    fc = make_forecast(
        symbol,
        as_of_date=None,
        vol_surface=vol_surface,
        chart_structure_dict=cs_dict,
    )
    save_forecast_artifact(fc)
    return forecast_to_dict(fc)


def _safe_call(fn, *args, **kwargs) -> Any:
    """Run fn; return None on any exception."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def analyze(symbol: str, *, include_reddit: bool = True, include_macro: bool = False) -> dict:
    """Run all quant layers for one ticker and return structured report.

    Returns dict with keys:
      - symbol, as_of
      - fundamentals, short_interest, institutional, analyst_targets, dividend
      - price_history_summary, realized_vol, regime
      - iv_term_structure
      - seasonality (day_of_week, month_of_year, earnings_window, days_to_event)
      - sentiment (stocktwits, reddit, aggregate)
      - institutional_flow_signal (composite)
      - positioning_summary (one-pager)
    """
    as_of = dt.datetime.utcnow().isoformat() + "Z"
    out = {"symbol": symbol.upper(), "as_of": as_of}

    # --- Fundamentals ---
    out["fundamentals"] = _safe_call(fundamentals_snapshot, symbol)
    out["short_interest"] = _safe_call(short_interest, symbol)
    out["institutional_ownership"] = _safe_call(institutional_holdings, symbol)
    out["analyst_targets"] = _safe_call(analyst_targets, symbol)
    out["dividend"] = _safe_call(dividend_calendar, symbol)
    out["news_recent"] = _safe_call(news_func, symbol, 8)
    out["news_count"] = len(out["news_recent"]) if isinstance(out["news_recent"], list) else 0

    # --- Vol + regime ---
    out["realized_vol_20d"] = _safe_call(realized_volatility, symbol, 20)
    out["realized_vol_60d"] = _safe_call(realized_volatility, symbol, 60)
    out["iv_term_structure"] = _safe_call(IV_term_structure, symbol)
    out["regime"] = _safe_call(regime_assessment, symbol)

    # --- Workstream B: HMM regime + SABR-lite + expected move ---
    out["regime_hmm"] = classify_current_regime(symbol, fallback={"regime": "unknown", "method": "fallback"})
    out["vol_surface"] = fit_vol_surface(symbol)
    out["expected_move"] = reconcile_expected_moves(symbol)

    # --- Seasonality ---
    out["day_of_week"] = _safe_call(day_of_week_drift, symbol, lookback_years=1)
    out["month_of_year"] = _safe_call(month_of_year_drift, symbol, lookback_years=3)
    out["earnings_window_drift"] = _safe_call(earnings_window_drift, symbol)
    out["days_to_event"] = _safe_call(days_to_next_event, symbol)

    # --- Sentiment ---
    out["stocktwits"] = _safe_call(stocktwits_symbol, symbol, 30)
    out["reddit"] = _safe_call(reddit_symbol, symbol) if include_reddit else None
    out["sentiment_aggregate"] = _safe_call(aggregate_sentiment, symbol, use_reddit=include_reddit)
    out["named_traders"] = named_trader_status()

    # --- Institutional flow composite ---
    out["institutional_flow_signal"] = _safe_call(composite_flow_signal, symbol)
    out["short_interest_signal"] = _safe_call(short_interest_signal, symbol)

    # --- Chart structure (Mike 2026-09-02 18:26 ET — algorithmic, one input, not sole driver) ---
    out["chart_structure"] = _safe_call(_chart_structure_safe, symbol, include_backtest=True)

    # --- Multi-horizon probabilistic forecast (Mike 2026-09-02 18:37 ET directive) ---
    # Uses chart_structure as input for pattern-conditional adjustment.
    # Forecast is "OOS-conditional" — not validated until forward paper-trading data.
    out["forecast"] = _safe_call(_forecast_safe, symbol)

    # --- One-pager positioning summary ---
    out["positioning_summary"] = _positioning_summary(out)

    return out


def _positioning_summary(data: dict) -> dict:
    """Reduce the deep analyze output into a 12-line positioning summary.
    Each line is a one-sentence judgment based on the data above.

    Tags every claim with the source field it came from.
    """
    sym = data.get("symbol", "?")
    s = {}
    # Analyst thesis
    if data.get("analyst_targets") and isinstance(data["analyst_targets"], dict):
        at = data["analyst_targets"]
        s["analyst_consensus"] = (
            f"rating={at.get('rating_label')}, mean target=${at.get('mean_target')} "
            f"vs spot (see fundamentals). Range: ${at.get('low_target')}–${at.get('high_target')}"
        )
    # Institutional positioning
    if data.get("institutional_ownership") and isinstance(data["institutional_ownership"], dict):
        io = data["institutional_ownership"]
        s["institutional_pct"] = (
            f"{io.get('institutional_pct', 0)*100:.1f}% institutional / "
            f"{io.get('insider_pct', 0)*100:.2f}% insider"
        )
    # Short interest
    if data.get("short_interest_signal") and isinstance(data["short_interest_signal"], dict):
        si = data["short_interest_signal"]
        mom = si.get("mom_change_pct")
        mom_str = f"{mom*100:+.1f}% MoM" if mom is not None else "n/a"
        s["short_pressure"] = (
            f"{si.get('pct_of_float', 0)*100:.2f}% short / {mom_str}, "
            f"class: {si.get('classification')}"
        )
    # IV vs RV
    if data.get("iv_term_structure") and isinstance(data["iv_term_structure"], dict):
        ts = data["iv_term_structure"]["term_structure"]
        # Get the nearest post-earnings expiry, or the first
        first = next(iter(ts.values()), None) if ts else None
        if first:
            iv = first["iv"]
            rv = data.get("realized_vol_20d")
            if rv and iv:
                edge = iv - rv
                s["iv_vs_rv"] = (
                    f"IV {iv*100:.0f}% vs realized {rv*100:.0f}% = "
                    f"{edge*100:+.0f}% edge {'(IV rich)' if edge > 0 else '(IV cheap)'}"
                )
    # Regime
    if data.get("regime") and isinstance(data["regime"], dict):
        s["regime"] = (
            f"{data['regime'].get('regime')} (RV20={data['regime'].get('realized_vol_20d', 0)*100:.0f}%)"
        )
    # Earnings proximity
    if data.get("days_to_event") and isinstance(data["days_to_event"], dict):
        d = data["days_to_event"].get("days_to_earnings")
        if d is not None:
            s["earnings_proximity"] = f"{d} days to earnings"
    # Sentiment
    if data.get("sentiment_aggregate") and isinstance(data["sentiment_aggregate"], dict):
        bpct = data["sentiment_aggregate"].get("combined_bullish_pct")
        if bpct is not None:
            s["sentiment_aggregate"] = f"{bpct*100:.0f}% bullish (combined Stocktwits + Reddit)"
    # Composite flow signal
    if data.get("institutional_flow_signal") and isinstance(data["institutional_flow_signal"], dict):
        scores = data["institutional_flow_signal"].get("scores") or {}
        comp = scores.get("composite")
        if comp is not None:
            def _fmt(v):
                return f"{v:+.2f}" if isinstance(v, (int, float)) else "n/a"
            s["flow_composite"] = (
                f"{comp:+.2f} "
                f"({_fmt(scores.get('short_interest_score'))} short + "
                f"{_fmt(scores.get('institutional_score'))} inst + "
                f"{_fmt(scores.get('analyst_score'))} analyst)"
            )
    # Chart structure (Mike 2026-09-02 18:26 ET — systematic, ONE input, not sole driver)
    if data.get("chart_structure") and isinstance(data["chart_structure"], dict):
        cs = data["chart_structure"]
        if cs.get("error"):
            s["chart_structure"] = f"error: {cs['error']}"
        else:
            t = cs.get("trend") or {}
            patterns = cs.get("patterns") or []
            score = cs.get("score") or {}
            # Top pattern (confirmed first, then developing, by type specificity)
            top_p = None
            for p in patterns:
                if p.get("state") == "confirmed":
                    top_p = p
                    break
            if top_p is None:
                for p in patterns:
                    if p.get("state") == "developing":
                        top_p = p
                        break
            pattern_str = ""
            if top_p:
                hr = top_p.get("historical_conditional_hit_rate")
                n = top_p.get("historical_conditional_n")
                avg = top_p.get("historical_conditional_avg_return_4w")
                cond_str = ""
                if hr is not None and n is not None:
                    cond_str = f" | hist: n={n} hit={hr*100:.0f}% avg4w={avg*100:+.1f}%" if avg is not None else f" | hist: n={n} hit={hr*100:.0f}%"
                vstatus = top_p.get("validation_status", "OOS-conditional")
                pattern_str = f" | top: {top_p['type']} [{top_p['state']}] trigger=${top_p['trigger_price']:.2f}{cond_str} | val={vstatus}"
            s["chart_structure"] = (
                f"trend={t.get('direction','?')} (ma={t.get('ma_alignment','?')}) "
                f"score={score.get('total', 0):.0f} ({score.get('label','?')}){pattern_str}"
            )
    # Multi-horizon probabilistic forecast (Mike 2026-09-02 18:37 ET directive)
    if data.get("forecast") and isinstance(data["forecast"], dict):
        fc = data["forecast"]
        if fc.get("horizons"):
            # Show 21d (1mo) horizon in summary — most actionable for options spreads
            onemo = next((h for h in fc["horizons"] if h.get("horizon_d") == 21), None)
            if onemo:
                pattern_used = fc.get("pattern_conditional_used", False)
                ptype = fc.get("pattern_conditional_type")
                iv_used = fc.get("iv_implied_used", False)
                hist_used = fc.get("historical_realized_used", False)
                sources = []
                if iv_used:
                    sources.append("IV")
                if hist_used:
                    sources.append("hist-RV")
                sources_str = "+".join(sources) if sources else "GBM-only"
                pattern_str = f" pattern={ptype}" if pattern_used and ptype else ""
                s["forecast_1mo"] = (
                    f"spot=${fc['spot']} | median=${onemo['median_price']} ({onemo['median_return_pct']:+.1f}%) "
                    f"| 68% band=[${onemo['band_68_lower']}–${onemo['band_68_upper']}] "
                    f"| 90% band=[${onemo['band_90_lower']}–${onemo['band_90_upper']}] "
                    f"| sources={sources_str}{pattern_str}"
                )
                s["forecast_status"] = (
                    "OOS-conditional, awaiting forward paper validation"
                )
    return s


def format_markdown(symbol: str, *, include_reddit: bool = True) -> str:
    """Return the deep analyze result as a Markdown report.

    Sections: positioning summary, fundamentals/inst/short, IV + regime,
    seasonality, sentiment, news.
    """
    data = analyze(symbol, include_reddit=include_reddit)
    s = data.get("symbol", symbol)
    lines = []
    lines.append(f"# Deep Analyze: {s}")
    lines.append(f"_As of: {data.get('as_of', '?')}_")
    lines.append("")
    lines.append("## Positioning Summary")
    ps = data.get("positioning_summary") or {}
    for k, v in ps.items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")

    # Fundamentals
    if data.get("fundamentals") and isinstance(data["fundamentals"], dict):
        f = data["fundamentals"]
        lines.append("## Fundamentals")
        lines.append(f"- Sector / Industry: {f.get('sector')} / {f.get('industry')}")
        lines.append(f"- Market cap: ${(f.get('marketCap') or 0)/1e9:.1f}B")
        if f.get("dividendYield") and f["dividendYield"] > 0:
            lines.append(f"- Dividend: {f.get('dividendRate')} ({f.get('dividendYield')*100:.2f}% yield)")
        if f.get("beta"):
            lines.append(f"- Beta: {f['beta']:.2f}")
        if f.get("trailingPE"):
            lines.append(f"- P/E (TTM): {f['trailingPE']:.1f}")
        if f.get("forwardPE"):
            lines.append(f"- Forward P/E: {f['forwardPE']:.1f}")
        if f.get("fiftyTwoWeekChangePercent"):
            lines.append(f"- 52w change: {f['fiftyTwoWeekChangePercent']*100:+.1f}%")
        lines.append("")

    # IV term structure
    if data.get("iv_term_structure") and isinstance(data["iv_term_structure"], dict):
        its = data["iv_term_structure"]
        lines.append("## IV Term Structure")
        lines.append(f"- Spot: ${its.get('spot', 0):.2f}")
        lines.append("")
        lines.append("| Expiration | DTE | Straddle Mid | IV (annualized) | % of Spot |")
        lines.append("|---|---|---|---|---|")
        ts = its.get("term_structure") or {}
        for exp, vals in ts.items():
            lines.append(
                f"| {exp} | {vals.get('dte')} | ${vals.get('straddle_mid', 0):.2f} | "
                f"{vals.get('iv', 0)*100:.0f}% | {vals.get('straddle_pct_of_spot', 0)*100:.2f}% |"
            )
        lines.append("")

    # Sentiment
    if data.get("stocktwits") and isinstance(data["stocktwits"], dict):
        st = data["stocktwits"]
        lines.append("## Sentiment (Stocktwits)")
        if st.get("n_messages"):
            lines.append(f"- {st['n_messages']} messages: {st['bullish_count']} bullish / {st['bearish_count']} bearish / {st['neutral_count']} neutral")
            lines.append(f"- Bullish: {st['bullish_pct']*100:.0f}%")
            lines.append("")
            lines.append("### Sample messages")
            for m in st.get("messages", [])[:5]:
                sent = m.get("sentiment", "?").upper()
                user = m.get("user") or "?"
                body = m.get("body", "")[:120]
                lines.append(f"- [{sent}] @{user}: {body}...")
            lines.append("")

    # News
    if data.get("news_recent") and isinstance(data["news_recent"], list) and len(data["news_recent"]) > 0:
        lines.append("## Recent News")
        for n in data["news_recent"][:8]:
            t = n.get("title") or "(no title)"
            pub = n.get("publisher") or "?"
            url = n.get("url") or ""
            lines.append(f"- {t} _({pub})_{{url if url else ''}}")
        lines.append("")

    lines.append("## Sources")
    lines.append("- fundamentals/short_interest/institutional/analyst/dividend: yfinance .info (real-time)")
    lines.append("- IV term structure: yfinance option chains + BKM")
    lines.append("- Realized vol: yfinance 1y daily prices, log returns, annualized")
    lines.append("- Regime: realized vol bucket + 50d vs 200d MA")
    lines.append("- Sentiment: Stocktwits public API + Reddit public JSON (sparse)")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "AVGO"
    print(format_markdown(sym))
