"""
lib/macro_dashboard.py
Workstream F.3 — Profile 1: Macro Regime and Market-Risk Dashboard.

Charter: research-only. No execution, no brokerage creds, no order placement.

Outputs:
  data/macro_dashboard/YYYY-MM-DD.json  (raw dashboard)
  + appends a `macro_dashboard` record to the research ledger at
    data/research_ledger/YYYY-MM/YYYY-MM-DD.jsonl

Eight pillars (per F.3 §2):
  A  Equity trend + breadth
  B  Volatility + options positioning
  C  Rates + curve
  D  Credit + financial conditions  (FRED CSV; no API key)
  E  Economic growth               (FRED CSV; no API key)
  F  Valuation + liquidity         (FRED WALCL/M2SL; yfinance for prices)
  G  Cross-asset confirmation      (yfinance)
  H  Event risk                    (manual calendar flagging)

Per-pillar output carries:
  state:           improving | neutral | deteriorating | unavailable | conflicted
  source_ts:       ISO timestamp of latest input
  lookback:        "60d" / "1y" / "5y" / etc
  latest:          raw readings
  trend:           → / ↑ / ↓ / ↑↑ / ↓↓ vs lookback
  change_lookback: delta vs lookback
  confidence:      0..1
  missing_data_warning: list[str]
  evidence:        human-readable summary
  score:           -1..+1 (normalized pillar score)

Regime labels:
  risk_on | fragile_risk_on | transition | risk_off | bear_risk_elevated

Bear-risk level (independent of regime):
  low | moderate | elevated | high
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
import statistics
import urllib.request
import urllib.error

# Optional FRED API key from .openclaw/tmp/fred.env (chmod 600, gitignored)
# Used for higher rate limits via api.stlouisfed.org JSON endpoint.
# CSV fallback below works without a key.
def _load_fred_key() -> str | None:
    env_path = Path(__file__).resolve().parents[2] / ".openclaw" / "tmp" / "fred.env"
    if env_path.exists():
        try:
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line.startswith("FRED_API_KEY="):
                    return line.split("=", 1)[1].strip()
        except Exception:
            pass
    return os.environ.get("FRED_API_KEY")
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

# Defer heavy imports inside functions to keep startup fast and isolate failures.

MACRO_DASHBOARD_ROOT = Path(__file__).resolve().parents[1] / "data" / "macro_dashboard"

REGIMES = ["risk_on", "fragile_risk_on", "transition", "risk_off", "bear_risk_elevated"]
BEAR_RISK_LEVELS = ["low", "moderate", "elevated", "high"]

DEFAULT_PILLAR_WEIGHTS = {
    "A": 0.18,  # Equity trend + breadth
    "B": 0.14,  # Volatility + options positioning
    "C": 0.14,  # Rates + curve
    "D": 0.18,  # Credit + financial conditions
    "E": 0.12,  # Economic growth
    "F": 0.10,  # Valuation + liquidity
    "G": 0.10,  # Cross-asset confirmation
    "H": 0.04,  # Event risk
}

# Mapping from continuous bear-risk score (0..1) to band
BEAR_RISK_BANDS = [
    (0.20, "low"),
    (0.45, "moderate"),
    (0.65, "elevated"),
    (1.01, "high"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_local() -> datetime:
    return datetime.now().astimezone()


def _iso_local(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _safe_get(d: dict, *keys, default=None):
    for k in keys:
        if d is None:
            return default
        d = d.get(k) if isinstance(d, dict) else None
    return d if d is not None else default


def _zscore(latest: float, history: list[float]) -> float:
    """z-score of `latest` vs `history`; clamped to [-3, 3]. Filters NaN/inf."""
    cleaned = [x for x in history if isinstance(x, (int, float)) and math.isfinite(x)]
    if len(cleaned) < 2 or not math.isfinite(latest):
        return 0.0
    mu = statistics.mean(cleaned)
    sd = statistics.pstdev(cleaned)
    if sd == 0 or not math.isfinite(sd):
        return 0.0
    z = (latest - mu) / sd
    if not math.isfinite(z):
        return 0.0
    return max(-3.0, min(3.0, z))


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _trend_arrow(delta: float, scale: float) -> str:
    """Return a 5-level arrow glyph."""
    if delta >  scale * 1.0: return "↑↑"
    if delta >  scale * 0.3: return "↑"
    if delta < -scale * 1.0: return "↓↓"
    if delta < -scale * 0.3: return "↓"
    return "→"


# ---------------------------------------------------------------------------
# FRED CSV fetcher (no API key)
# ---------------------------------------------------------------------------

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
FRED_API_URL = "https://api.stlouisfed.org/fred/series/observations?series_id={series}&file_type=json&api_key={key}"
FRED_HTTP_TIMEOUT = 12

FRED_CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "fred_cache"


def fetch_fred_series(series: str, lookback_days: int = 365 * 5) -> list[dict]:
    """Returns a list of {date: 'YYYY-MM-DD', value: float} newest-first.

    Cache: data/fred_cache/<series>.json with 24h TTL.
    Uses FRED API JSON endpoint when FRED_API_KEY is available (higher rate
    limits); otherwise falls back to public CSV endpoint.
    """
    FRED_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = FRED_CACHE_DIR / f"{series}.json"
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text())
            cached_ts = datetime.fromisoformat(cached["fetched_at"])
            if _now_local() - cached_ts < timedelta(hours=24):
                return cached["data"]
        except (json.JSONDecodeError, KeyError, ValueError):
            pass

    api_key = _load_fred_key()
    raw = ""
    if api_key:
        url = FRED_API_URL.format(series=series, key=api_key)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "dependability-quant research@bacotti.com"})
            with urllib.request.urlopen(req, timeout=FRED_HTTP_TIMEOUT) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="replace"))
            for obs in payload.get("observations", []):
                raw += f"{obs.get('date','')},{obs.get('value','')}\n"
            raw = "DATE," + series + "\n" + raw  # synthesize CSV header so the parser below works
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, KeyError):
            raw = ""

    if not raw:
        url = FRED_CSV_URL.format(series=series)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "dependability-quant research@bacotti.com"})
            with urllib.request.urlopen(req, timeout=FRED_HTTP_TIMEOUT) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(f"FRED fetch failed for {series}: {exc}") from exc

    rows: list[dict] = []
    reader = csv.DictReader(io.StringIO(raw))
    cutoff = _now_local().date() - timedelta(days=lookback_days)
    for row in reader:
        try:
            # FRED CSV uses 'observation_date' as the date column header.
            date_str = row.get("observation_date") or row.get("DATE") or row.get("date") or ""
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
            v = row.get(series) or row.get("VALUE") or row.get("value") or ""
            v = v.strip()
            if v in ("", ".", "NA"):
                continue
            val = float(v)
        except (ValueError, KeyError):
            continue
        if d < cutoff:
            continue
        rows.append({"date": d.isoformat(), "value": val})
    rows.sort(key=lambda r: r["date"], reverse=True)

    cache_path.write_text(json.dumps({"fetched_at": _now_local().isoformat(), "data": rows}))
    return rows


# ---------------------------------------------------------------------------
# yfinance wrapper
# ---------------------------------------------------------------------------

def fetch_yf_history(symbol: str, period: str = "1y") -> list[dict]:
    """Returns list of {date: 'YYYY-MM-DD', close: float} newest-first.
    Uses yfinance.Ticker.history(). Returns [] on failure.
    """
    try:
        import yfinance as yf  # type: ignore
    except ImportError:
        return []
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period=period, auto_adjust=True)
    except Exception:
        return []
    if hist is None or len(hist) == 0:
        return []
    out: list[dict] = []
    for idx, row in hist.iterrows():
        try:
            d = idx.date() if hasattr(idx, "date") else idx
            out.append({"date": d.isoformat(), "close": float(row["Close"])})
        except Exception:
            continue
    out.sort(key=lambda r: r["date"], reverse=True)
    return out


def fetch_yf_last(symbol: str) -> Optional[dict]:
    rows = fetch_yf_history(symbol, period="5d")
    return rows[0] if rows else None


# ---------------------------------------------------------------------------
# Pillar computations
# ---------------------------------------------------------------------------

def _pct_below_or_above(latest: float, history: list[float], lookback: int = 60) -> dict:
    """Simple momentum and percentile helpers."""
    if not history:
        return {}
    last_n = history[:lookback]
    if len(last_n) < 2:
        return {}
    delta = (last_n[0]["close"] - last_n[-1]["close"]) / last_n[-1]["close"] if last_n[-1]["close"] else 0.0
    closes = [r["close"] for r in last_n]
    z = _zscore(last_n[0]["close"], closes)
    return {"delta": delta, "z_lookback": z}


def _ma_distance(history: list[float], ma_window: int = 200) -> Optional[float]:
    if len(history) < ma_window:
        return None
    closes = [r["close"] for r in history[:ma_window]]
    return (history[0]["close"] - statistics.mean(closes)) / statistics.mean(closes)


def _pct_above_ma(symbol_universe_close: list[dict], ma: int = 200) -> Optional[float]:
    """symbol_universe_close: list of {date, close}."""
    closes = [r["close"] for r in symbol_universe_close if r.get("close") is not None]
    if len(closes) < ma:
        return None
    avg = statistics.mean(closes[:ma])
    return (closes[0] - avg) / avg


def pillar_A_equity_trend_breadth() -> dict:
    spx = fetch_yf_history("^GSPC", period="2y")
    ndx = fetch_yf_history("^IXIC", period="2y")
    rut = fetch_yf_history("^RUT", period="2y")
    spy = fetch_yf_history("SPY", period="2y")
    rsp = fetch_yf_history("RSP", period="2y")  # equal-weight S&P
    missing = []
    if not spx: missing.append("^GSPC")
    if not ndx: missing.append("^IXIC")
    if not rut: missing.append("^RUT")
    if not spy: missing.append("SPY")
    if not rsp: missing.append("RSP")

    if missing:
        return {"pillar": "A_equity_trend_breadth", "state": "unavailable",
                "missing_data_warning": missing,
                "score": 0.0, "confidence": 0.0, "evidence": "missing inputs"}

    spx_ma200 = _ma_distance(spx, 200)
    ndx_ma200 = _ma_distance(ndx, 200)
    rut_ma200 = _ma_distance(rut, 200)
    spx_1m = _pct_below_or_above(spx[0]["close"], spx, 21)["delta"]
    spx_3m = _pct_below_or_above(spx[0]["close"], spx, 63)["delta"]
    # EW/CW ratio leadership
    spy_3m = _pct_below_or_above(spy[0]["close"], spy, 63)["delta"]
    rsp_3m = _pct_below_or_above(rsp[0]["close"], rsp, 63)["delta"]
    ew_vs_cw = rsp_3m - spy_3m

    components = []
    if spx_ma200 is not None:
        components.append(_clamp(spx_ma200 * 4, -1, 1))
    if ndx_ma200 is not None:
        components.append(_clamp(ndx_ma200 * 4, -1, 1))
    if rut_ma200 is not None:
        components.append(_clamp(rut_ma200 * 4, -1, 1))
    components.append(_clamp(ew_vs_cw * 4, -1, 1))
    components.append(_clamp(spx_3m * 4, -1, 1))

    score = statistics.mean(components) if components else 0.0
    if score > 0.20:
        state = "improving"
    elif score < -0.20:
        state = "deteriorating"
    else:
        state = "neutral"

    return {
        "pillar": "A_equity_trend_breadth",
        "state": state,
        "source_ts": spx[0]["date"] + "T16:00:00-04:00",
        "lookback": "200d MA + 1m / 3m momentum + EW/CW leadership",
        "latest": {
            "SPX": round(spx[0]["close"], 2),
            "NDX": round(ndx[0]["close"], 2),
            "RUT": round(rut[0]["close"], 2),
            "SPX_above_200d": round(spx_ma200 * 100, 2) if spx_ma200 is not None else None,
            "NDX_above_200d": round(ndx_ma200 * 100, 2) if ndx_ma200 is not None else None,
            "RUT_above_200d": round(rut_ma200 * 100, 2) if rut_ma200 is not None else None,
            "SPX_1m_pct": round(spx_1m * 100, 2),
            "SPX_3m_pct": round(spx_3m * 100, 2),
            "EW_minus_CW_3m_pp": round(ew_vs_cw * 100, 2),
        },
        "trend": _trend_arrow(score, 0.20),
        "change_lookback": f"score Δ vs 60d ago: {round(score, 3)}",
        "confidence": 0.85 if not missing else 0.5,
        "missing_data_warning": missing,
        "evidence": (
            f"SPX {spx[0]['close']:.0f} ({round(spx_ma200*100,1)}% above 200-DMA); "
            f"NDX {ndx[0]['close']:.0f} ({round(ndx_ma200*100,1)}% above 200-DMA); "
            f"RUT {rut[0]['close']:.0f} ({round(rut_ma200*100,1)}% above 200-DMA); "
            f"EW−CW spread 3m: {round(ew_vs_cw*100,1)}pp"
        ),
        "score": round(score, 3),
    }


def pillar_B_vol_positioning() -> dict:
    vix = fetch_yf_last("^VIX")
    vix9d = fetch_yf_last("^VIX9D")
    vix3m = fetch_yf_last("^VIX3M")
    vix6m = fetch_yf_last("^VIX6M")
    vvix = fetch_yf_last("^VVIX")
    skew = fetch_yf_last("^SKEW")
    spx = fetch_yf_history("^GSPC", period="1y")

    missing = []
    if not vix: missing.append("^VIX")
    if not vvix: missing.append("^VVIX")
    if not skew: missing.append("^SKEW")

    if missing:
        return {"pillar": "B_vol_positioning", "state": "unavailable",
                "missing_data_warning": missing,
                "score": 0.0, "confidence": 0.0, "evidence": "missing inputs"}

    vix_v = vix["close"]
    v9d = vix9d["close"] if vix9d else None
    v3m = vix3m["close"] if vix3m else None
    v6m = vix6m["close"] if vix6m else None

    # Term structure shape
    if v3m:
        ts_3m = (v3m - vix_v) / vix_v
    else:
        ts_3m = None
    if v9d:
        ts_9d = (vix_v - v9d) / v9d
    else:
        ts_9d = None

    # RV vs IV gap (RV20 vs VIX)
    rv20 = None
    if spx and len(spx) >= 22:
        closes = [r["close"] for r in spx[:22]]
        rets = [math.log(closes[i] / closes[i + 1]) for i in range(len(closes) - 1)]
        rv20 = statistics.pstdev(rets) * math.sqrt(252)

    iv_minus_rv = ((vix_v / 100) - rv20) if rv20 is not None else None

    # VVIX/SKEW context
    vvix_v = vvix["close"]
    skew_v = skew["close"]

    components = []
    # VIX level (lower VIX = supportive)
    components.append(_clamp((20 - vix_v) / 15, -1, 1))
    # Term structure (backwardation = stress; contango = calm)
    if ts_3m is not None:
        components.append(_clamp(ts_3m * 5, -1, 1))
    # IV - RV gap (large positive = complacency; large negative = fear)
    if iv_minus_rv is not None:
        components.append(_clamp(-iv_minus_rv * 10, -1, 1))
    # SKEW (high = tail hedging demand)
    components.append(_clamp((145 - skew_v) / 30, -1, 1))
    # VVIX (high = vol-of-vol elevated)
    components.append(_clamp((95 - vvix_v) / 25, -1, 1))

    score = statistics.mean(components) if components else 0.0
    if score > 0.20:
        state = "improving"
    elif score < -0.20:
        state = "deteriorating"
    else:
        state = "neutral"

    latest = {
        "VIX": round(vix_v, 2),
        "VVIX": round(vvix_v, 2),
        "SKEW": round(skew_v, 2),
        "VIX_9d": round(v9d, 2) if v9d else None,
        "VIX_3m": round(v3m, 2) if v3m else None,
        "VIX_6m": round(v6m, 2) if v6m else None,
        "RV20_annualized": round(rv20 * 100, 2) if rv20 is not None else None,
        "IV_minus_RV_pp": round(iv_minus_rv * 100, 2) if iv_minus_rv is not None else None,
    }

    return {
        "pillar": "B_vol_positioning",
        "state": state,
        "source_ts": vix["date"] + "T16:00:00-04:00",
        "lookback": "RV20 (1y window) + term structure + VVIX/SKEW",
        "latest": latest,
        "trend": _trend_arrow(-score, 0.20),  # higher VIX is worse
        "change_lookback": f"VIX {vix_v:.2f}; SKEW {skew_v:.0f}",
        "confidence": 0.80 if not missing else 0.5,
        "missing_data_warning": missing,
        "evidence": (
            f"VIX {vix_v:.1f}, VVIX {vvix_v:.0f}, SKEW {skew_v:.0f}; "
            + (f"3m term structure {round(ts_3m*100,1)}%; " if ts_3m is not None else "term structure partial; ")
            + (f"IV−RV {round(iv_minus_rv*100,1)}pp" if iv_minus_rv is not None else "RV n/a")
        ),
        "score": round(score, 3),
    }


def pillar_C_rates_curve() -> dict:
    tnx = fetch_yf_last("^TNX")
    fvx = fetch_yf_last("^FVX")
    tyx = fetch_yf_last("^TYX")
    irx = fetch_yf_last("^IRX")
    dfii10 = fetch_fred_series("DFII10") if True else []
    real10 = dfii10[0]["value"] / 100 if dfii10 else None

    missing = []
    if not tnx: missing.append("^TNX")
    if not fvx: missing.append("^FVX")
    if not tyx: missing.append("^TYX")
    if not irx: missing.append("^IRX")
    if not dfii10: missing.append("FRED:DFII10")

    if missing and (not tnx or not fvx):
        return {"pillar": "C_rates_curve", "state": "unavailable",
                "missing_data_warning": missing, "score": 0.0,
                "confidence": 0.0, "evidence": "missing core rate inputs"}

    tnx_v = tnx["close"] if tnx else None
    fvx_v = fvx["close"] if fvx else None
    tyx_v = tyx["close"] if tyx else None
    irx_v = irx["close"] if irx else None

    spread_2s10s = (tnx_v - fvx_v) / 100 if (tnx_v and fvx_v) else None  # in fraction
    spread_10y3m = (tnx_v - irx_v) / 100 if (tnx_v and irx_v) else None

    # Historical 2s10s context
    hist_spread = fetch_fred_series("T10Y2Y")
    z_2s10s = _zscore(spread_2s10s * 100, [r["value"] for r in hist_spread]) if (hist_spread and spread_2s10s is not None) else 0.0

    components = []
    # Positive 2s10s supports risk-on
    if spread_2s10s is not None:
        components.append(_clamp(spread_2s10s * 6, -1, 1))
    # 10Y-3M un-inverted supports risk-on
    if spread_10y3m is not None:
        components.append(_clamp(spread_10y3m * 4, -1, 1))
    # Real yields high = headwind for equities
    if real10 is not None:
        components.append(_clamp((0.02 - real10) * 30, -1, 1))
    # Curve 2s10s z-score
    components.append(_clamp(z_2s10s / 2, -1, 1))
    # Nominal rate level (high nominal = headwind)
    if tnx_v is not None:
        components.append(_clamp((4.5 - tnx_v) / 2, -1, 1))

    score = statistics.mean(components) if components else 0.0
    if score > 0.20:
        state = "improving"
    elif score < -0.20:
        state = "deteriorating"
    else:
        state = "neutral"

    return {
        "pillar": "C_rates_curve",
        "state": state,
        "source_ts": tnx["date"] + "T16:00:00-04:00" if tnx else _iso_local(_now_local()),
        "lookback": "Spot curve + 5y FRED z-score (T10Y2Y)",
        "latest": {
            "UST_10Y_pct": round(tnx_v, 3) if tnx_v is not None else None,
            "UST_5Y_pct": round(fvx_v, 3) if fvx_v is not None else None,
            "UST_30Y_pct": round(tyx_v, 3) if tyx_v is not None else None,
            "UST_13W_pct": round(irx_v, 3) if irx_v is not None else None,
            "Real10Y_pct": round(real10 * 100, 2) if real10 is not None else None,
            "2s10s_pct": round(spread_2s10s * 100, 2) if spread_2s10s is not None else None,
            "10Y3M_pct": round(spread_10y3m * 100, 2) if spread_10y3m is not None else None,
        },
        "trend": _trend_arrow(score, 0.20),
        "change_lookback": f"2s10s z={round(z_2s10s,2)}",
        "confidence": 0.80 if not missing else 0.5,
        "missing_data_warning": missing,
        "evidence": (
            f"10Y {tnx_v:.2f}%, 2Y {fvx_v:.2f}%, 30Y {tyx_v:.2f}%, 13W {irx_v:.2f}%; "
            f"real 10Y {round(real10*100,1) if real10 is not None else 'n/a'}%; "
            f"2s10s {round(spread_2s10s*100,1) if spread_2s10s is not None else 'n/a'}bp; "
            f"10Y-3M {round(spread_10y3m*100,1) if spread_10y3m is not None else 'n/a'}bp"
        ),
        "score": round(score, 3),
    }


def pillar_D_credit_financials() -> dict:
    hy = fetch_fred_series("BAMLH0A0HYM2")  # HY OAS, daily
    ig = fetch_fred_series("BAMLC0A0CM")    # IG OAS, daily
    nfci = fetch_fred_series("NFCI")        # weekly
    stlfsi = fetch_fred_series("STLFSI4")    # weekly

    missing = []
    if not hy: missing.append("FRED:BAMLH0A0HYM2")
    if not ig: missing.append("FRED:BAMLC0A0CM")
    if not nfci: missing.append("FRED:NFCI")
    if not stlfsi: missing.append("FRED:STLFSI4")

    if not hy and not nfci:
        return {"pillar": "D_credit_financials", "state": "unavailable",
                "missing_data_warning": missing, "score": 0.0,
                "confidence": 0.0, "evidence": "FRED unreachable"}

    hy_v = hy[0]["value"] if hy else None
    ig_v = ig[0]["value"] if ig else None
    nfci_v = nfci[0]["value"] if nfci else None
    stlfsi_v = stlfsi[0]["value"] if stlfsi else None

    components = []
    if hy_v is not None:
        hist = [r["value"] for r in hy]
        z = _zscore(hy_v, hist)
        components.append(_clamp(-z / 2, -1, 1))
    if nfci_v is not None:
        # NFCI positive = tight; negative = loose
        components.append(_clamp(-nfci_v * 5, -1, 1))
    if stlfsi_v is not None:
        hist = [r["value"] for r in stlfsi]
        z = _zscore(stlfsi_v, hist)
        components.append(_clamp(-z / 2, -1, 1))

    score = statistics.mean(components) if components else 0.0
    if score > 0.20:
        state = "improving"
    elif score < -0.20:
        state = "deteriorating"
    else:
        state = "neutral"

    return {
        "pillar": "D_credit_financials",
        "state": state,
        "source_ts": (hy[0]["date"] if hy else nfci[0]["date"] if nfci else _iso_local(_now_local())) + "T16:00:00-04:00",
        "lookback": "5y daily/weekly history",
        "latest": {
            "HY_OAS_bp": round(hy_v, 1) if hy_v is not None else None,
            "IG_OAS_bp": round(ig_v, 1) if ig_v is not None else None,
            "NFCI": round(nfci_v, 3) if nfci_v is not None else None,
            "STLFSI4": round(stlfsi_v, 3) if stlfsi_v is not None else None,
        },
        "trend": _trend_arrow(score, 0.20),
        "change_lookback": f"HY Δ60d {round((hy_v - hy[60]['value']) if (hy and len(hy) > 60) else 0, 1)}bp",
        "confidence": 0.85 if not missing else 0.5,
        "missing_data_warning": missing,
        "evidence": (
            f"HY OAS {round(hy_v,0) if hy_v is not None else 'n/a'}bp, "
            f"IG OAS {round(ig_v,0) if ig_v is not None else 'n/a'}bp, "
            f"NFCI {round(nfci_v,2) if nfci_v is not None else 'n/a'}, "
            f"STLFSI {round(stlfsi_v,2) if stlfsi_v is not None else 'n/a'}"
        ),
        "score": round(score, 3),
    }


def pillar_E_economic_growth() -> dict:
    payroll = fetch_fred_series("PAYEMS")  # monthly
    unrate = fetch_fred_series("UNRATE")  # monthly
    icsa = fetch_fred_series("ICSA")      # weekly
    indpro = fetch_fred_series("INDPRO")  # monthly
    housing = fetch_fred_series("HOUST")  # monthly
    retail = fetch_fred_series("RSAFS")   # monthly

    missing = []
    if not payroll: missing.append("FRED:PAYEMS")
    if not unrate: missing.append("FRED:UNRATE")
    if not icsa: missing.append("FRED:ICSA")

    if missing and (not payroll and not icsa):
        return {"pillar": "E_economic_growth", "state": "unavailable",
                "missing_data_warning": missing, "score": 0.0,
                "confidence": 0.0, "evidence": "FRED unreachable"}

    pay_v = payroll[0]["value"] if payroll else None
    unrate_v = unrate[0]["value"] if unrate else None
    icsa_v = icsa[0]["value"] if icsa else None
    indpro_v = indpro[0]["value"] if indpro else None
    housing_v = housing[0]["value"] if housing else None
    retail_v = retail[0]["value"] if retail else None

    components = []
    if payroll and len(payroll) >= 4:
        delta = (payroll[0]["value"] - payroll[3]["value"]) / 1000  # in thousands
        # 3-month payroll delta: +200k supportive, 0 neutral, -100k weak
        components.append(_clamp(delta / 250, -1, 1))
    if unrate_v is not None:
        components.append(_clamp((4.5 - unrate_v) / 1.5, -1, 1))
    if icsa_v is not None:
        # Initial claims < 250k supportive, > 350k weak
        components.append(_clamp((300 - icsa_v) / 100, -1, 1))
    if indpro and len(indpro) >= 4:
        delta = (indpro[0]["value"] - indpro[3]["value"]) / indpro[3]["value"] if indpro[3]["value"] else 0
        components.append(_clamp(delta * 50, -1, 1))

    score = statistics.mean(components) if components else 0.0
    if score > 0.20:
        state = "improving"
    elif score < -0.20:
        state = "deteriorating"
    else:
        state = "neutral"

    return {
        "pillar": "E_economic_growth",
        "state": state,
        "source_ts": (payroll[0]["date"] if payroll else icsa[0]["date"] if icsa else _iso_local(_now_local())) + "T16:00:00-04:00",
        "lookback": "3-month deltas + spot levels",
        "latest": {
            "Nonfarm_payrolls_k": round(pay_v, 1) if pay_v is not None else None,
            "UNRATE_pct": round(unrate_v, 1) if unrate_v is not None else None,
            "ICSA_k": round(icsa_v, 1) if icsa_v is not None else None,
            "INDPRO_idx": round(indpro_v, 2) if indpro_v is not None else None,
            "HOUST_k": round(housing_v, 1) if housing_v is not None else None,
            "RSAFS_M": round(retail_v, 1) if retail_v is not None else None,
            "earnings_revisions_source": "MISSING — no clean free FRED series for AAII breadth or IBES revisions; see §11"
        },
        "trend": _trend_arrow(score, 0.20),
        "change_lookback": "3m payroll / claims delta",
        "confidence": 0.75 if not missing else 0.5,
        "missing_data_warning": missing + ["earnings_revisions (no clean free source)"],
        "evidence": (
            f"Nonfarm payrolls {round(pay_v/1000,1) if pay_v is not None else 'n/a'}M; "
            f"unemployment {round(unrate_v,1) if unrate_v is not None else 'n/a'}%; "
            f"initial claims {round(icsa_v,0) if icsa_v is not None else 'n/a'}k; "
            f"industrial production {round(indpro_v,2) if indpro_v is not None else 'n/a'}"
        ),
        "score": round(score, 3),
    }


def pillar_F_valuation_liquidity() -> dict:
    walcl = fetch_fred_series("WALCL")
    m2 = fetch_fred_series("M2SL")
    spx = fetch_yf_history("^GSPC", period="3y")

    missing = []
    if not walcl: missing.append("FRED:WALCL")
    if not m2: missing.append("FRED:M2SL")
    if not spx: missing.append("^GSPC")

    if missing and (not walcl or not spx):
        return {"pillar": "F_valuation_liquidity", "state": "unavailable",
                "missing_data_warning": missing, "score": 0.0,
                "confidence": 0.0, "evidence": "missing inputs"}

    walcl_v = walcl[0]["value"] if walcl else None
    m2_v = m2[0]["value"] if m2 else None

    components = []
    # WALCL YoY change (positive = liquidity expansion)
    if walcl and len(walcl) >= 52:
        yoy = (walcl[0]["value"] - walcl[52]["value"]) / walcl[52]["value"] if walcl[52]["value"] else 0
        components.append(_clamp(yoy * 10, -1, 1))
    # M2 YoY change
    if m2 and len(m2) >= 13:
        yoy = (m2[0]["value"] - m2[12]["value"]) / m2[12]["value"] if m2[12]["value"] else 0
        components.append(_clamp(yoy * 10, -1, 1))
    # SPX valuation: distance from 200-DMA as a *proxy* for valuation stretch
    spx_ma200 = _ma_distance(spx, 200)
    if spx_ma200 is not None:
        # > 15% above MA = stretched; < -10% = cheap
        components.append(_clamp((0.05 - spx_ma200) * 4, -1, 1))

    score = statistics.mean(components) if components else 0.0
    if score > 0.20:
        state = "improving"
    elif score < -0.20:
        state = "deteriorating"
    else:
        state = "neutral"

    return {
        "pillar": "F_valuation_liquidity",
        "state": state,
        "source_ts": (walcl[0]["date"] if walcl else _iso_local(_now_local())) + "T16:00:00-04:00",
        "lookback": "5y history; YoY changes; SPX distance from 200-DMA",
        "latest": {
            "Fed_BS_WALCL_M": round(walcl_v / 1e6, 3) if walcl_v is not None else None,
            "M2_M": round(m2_v / 1e3, 2) if m2_v is not None else None,
            "SPX_above_200d_pct": round(spx_ma200 * 100, 2) if spx_ma200 is not None else None,
        },
        "trend": _trend_arrow(score, 0.20),
        "change_lookback": f"WALCL YoY change",
        "confidence": 0.70 if not missing else 0.5,
        "missing_data_warning": missing + [
            "Forward PE (^SP500PER not on free yfinance tier); replaced by SPX 200-DMA distance as proxy"
        ],
        "evidence": (
            f"Fed balance sheet ${round(walcl_v/1e6,2) if walcl_v is not None else 'n/a'}T; "
            f"M2 ${round(m2_v/1e3,1) if m2_v is not None else 'n/a'}T; "
            f"SPX {round(spx_ma200*100,1) if spx_ma200 is not None else 'n/a'}% above 200-DMA (proxy for stretch)"
        ),
        "score": round(score, 3),
    }


def pillar_G_cross_asset() -> dict:
    tlt = fetch_yf_history("TLT", period="3mo")
    ief = fetch_yf_history("IEF", period="3mo")
    bil = fetch_yf_history("BIL", period="3mo")
    shy = fetch_yf_history("SHY", period="3mo")
    dxy = fetch_yf_last("DX-Y.NYB")
    gold = fetch_yf_last("GC=F")
    oil = fetch_yf_last("CL=F")
    copper = fetch_yf_last("HG=F")
    xly = fetch_yf_history("XLY", period="3mo")
    xlp = fetch_yf_history("XLP", period="3mo")
    xli = fetch_yf_history("XLI", period="3mo")
    xlu = fetch_yf_history("XLU", period="3mo")
    iwm = fetch_yf_history("IWM", period="3mo")
    spy = fetch_yf_history("SPY", period="3mo")

    missing = []
    for sym, data in [("TLT", tlt), ("IEF", ief), ("BIL", bil), ("SHY", shy),
                      ("GC=F", gold), ("CL=F", oil), ("DX-Y.NYB", dxy)]:
        if not data: missing.append(sym)

    if missing and (not tlt or not gold):
        return {"pillar": "G_cross_asset", "state": "unavailable",
                "missing_data_warning": missing, "score": 0.0,
                "confidence": 0.0, "evidence": "missing inputs"}

    components = []
    # TLT 3m return (positive = duration working = often risk-off supportive)
    if tlt and len(tlt) >= 63:
        ret_3m = (tlt[0]["close"] - tlt[62]["close"]) / tlt[62]["close"]
        components.append(_clamp(ret_3m * 4, -1, 1))
    # Gold 3m return (positive = fear / inflation hedge demand)
    if gold and len(tlt) >= 63:
        # need gold history
        gold_hist = fetch_yf_history("GC=F", period="3mo")
        if gold_hist and len(gold_hist) >= 63:
            ret_3m = (gold_hist[0]["close"] - gold_hist[62]["close"]) / gold_hist[62]["close"]
            components.append(_clamp(ret_3m * 4, -1, 1))
    # Oil 3m
    oil_hist = fetch_yf_history("CL=F", period="3mo")
    if oil_hist and len(oil_hist) >= 63:
        ret_3m = (oil_hist[0]["close"] - oil_hist[62]["close"]) / oil_hist[62]["close"]
        components.append(_clamp(ret_3m * 3, -1, 1))
    # Cyclical/defensive ratio
    if xly and xlp and len(xly) >= 63 and len(xlp) >= 63:
        r_xly = (xly[0]["close"] - xly[62]["close"]) / xly[62]["close"]
        r_xlp = (xlp[0]["close"] - xlp[62]["close"]) / xlp[62]["close"]
        components.append(_clamp((r_xly - r_xlp) * 6, -1, 1))
    # Small-cap vs large-cap
    if iwm and spy and len(iwm) >= 63 and len(spy) >= 63:
        r_iwm = (iwm[0]["close"] - iwm[62]["close"]) / iwm[62]["close"]
        r_spy = (spy[0]["close"] - spy[62]["close"]) / spy[62]["close"]
        components.append(_clamp((r_iwm - r_spy) * 6, -1, 1))

    score = statistics.mean(components) if components else 0.0
    if score > 0.20:
        state = "improving"
    elif score < -0.20:
        state = "deteriorating"
    else:
        state = "neutral"

    tlt_v = tlt[0]["close"] if tlt else None
    bil_v = bil[0]["close"] if bil else None
    return {
        "pillar": "G_cross_asset",
        "state": state,
        "source_ts": (tlt[0]["date"] if tlt else _iso_local(_now_local())) + "T16:00:00-04:00",
        "lookback": "3m returns across duration / dollar / commodities / sector rotation",
        "latest": {
            "TLT": round(tlt_v, 2) if tlt_v is not None else None,
            "BIL": round(bil_v, 2) if bil_v is not None else None,
            "Gold": round(gold["close"], 2) if gold else None,
            "Oil": round(oil["close"], 2) if oil else None,
            "Copper": round(copper["close"], 4) if copper else None,
            "DXY": round(dxy["close"], 2) if dxy else None,
            "XLY_3m_pct": round((xly[0]["close"] - xly[62]["close"]) / xly[62]["close"] * 100, 2) if xly and len(xly) >= 63 else None,
            "XLP_3m_pct": round((xlp[0]["close"] - xlp[62]["close"]) / xlp[62]["close"] * 100, 2) if xlp and len(xlp) >= 63 else None,
            "IWM_3m_pct": round((iwm[0]["close"] - iwm[62]["close"]) / iwm[62]["close"] * 100, 2) if iwm and len(iwm) >= 63 else None,
            "SPY_3m_pct": round((spy[0]["close"] - spy[62]["close"]) / spy[62]["close"] * 100, 2) if spy and len(spy) >= 63 else None,
        },
        "trend": _trend_arrow(score, 0.20),
        "change_lookback": "3m rotation",
        "confidence": 0.80 if not missing else 0.5,
        "missing_data_warning": missing,
        "evidence": (
            f"TLT {round(tlt_v,1) if tlt_v else 'n/a'}; BIL {round(bil_v,2) if bil_v else 'n/a'} (reserve ref); "
            f"Gold ${round(gold['close'],0) if gold else 'n/a'}; Oil ${round(oil['close'],1) if oil else 'n/a'}; "
            f"DXY {round(dxy['close'],1) if dxy else 'n/a'}"
        ),
        "score": round(score, 3),
    }


def pillar_H_event_risk() -> dict:
    """Event risk — manual calendar flagging. Today is 2026-09-02."""
    # Manual: 2026 calendar highlights from FRED release schedule + known events.
    # This pillar is intentionally lightweight and informationally labeled.
    today = _now_local().date()
    upcoming = [
        {"date": "2026-09-11", "kind": "macro_event", "label": "CPI release (Aug)", "impact": "high"},
        {"date": "2026-09-17", "kind": "central_bank", "label": "FOMC rate decision + press conference", "impact": "high"},
        {"date": "2026-09-12", "kind": "earnings_concentration", "label": "AVGO / ORCL / CRM earnings (single-stock concentration risk)", "impact": "high"},
        {"date": "2026-10-03", "kind": "macro_event", "label": "Nonfarm payrolls (Sep)", "impact": "medium"},
        {"date": "2026-10-10", "kind": "macro_event", "label": "CPI release (Sep)", "impact": "high"},
    ]

    days_to_next = None
    next_event = None
    for ev in sorted(upcoming, key=lambda e: e["date"]):
        d = datetime.strptime(ev["date"], "%Y-%m-%d").date()
        if d >= today:
            days_to_next = (d - today).days
            next_event = ev
            break

    # Component: events within 7 days pull score negative
    soon = [ev for ev in upcoming
            if 0 <= (datetime.strptime(ev["date"], "%Y-%m-%d").date() - today).days <= 7]
    high_impact_soon = sum(1 for ev in soon if ev.get("impact") == "high")

    score = _clamp(-0.15 * high_impact_soon, -1, 0)
    if score < -0.05:
        state = "deteriorating"
    else:
        state = "neutral"

    return {
        "pillar": "H_event_risk",
        "state": state,
        "source_ts": _iso_local(_now_local()),
        "lookback": "rolling 30d calendar",
        "latest": {
            "next_event": next_event,
            "days_to_next": days_to_next,
            "high_impact_within_7d": high_impact_soon,
        },
        "trend": "→",
        "change_lookback": "n/a (calendar)",
        "confidence": 0.5,
        "missing_data_warning": ["Earnings calendar: not auto-populated; requires manual update"],
        "evidence": (
            f"Next event: {next_event['label'] if next_event else 'none'} on "
            f"{next_event['date'] if next_event else 'n/a'} "
            f"({days_to_next if days_to_next is not None else 'n/a'}d out)"
        ),
        "score": round(score, 3),
    }


PILLAR_FUNCS = {
    "A": pillar_A_equity_trend_breadth,
    "B": pillar_B_vol_positioning,
    "C": pillar_C_rates_curve,
    "D": pillar_D_credit_financials,
    "E": pillar_E_economic_growth,
    "F": pillar_F_valuation_liquidity,
    "G": pillar_G_cross_asset,
    "H": pillar_H_event_risk,
}


# ---------------------------------------------------------------------------
# Regime classifier
# ---------------------------------------------------------------------------

def _classify_regime(pillars: dict) -> dict:
    """Soft posterior over 5 regimes + bear-risk level.
    Simple rule-based posterior with calibrated priors; documented in §2.2.
    """
    # Pull individual scores
    s = {k: pillars.get(k, {}).get("score", 0.0) for k in PILLAR_FUNCS}

    # Weighted composite (matches PILLAR_WEIGHTS)
    composite = sum(DEFAULT_PILLAR_WEIGHTS[k] * s[k] for k in DEFAULT_PILLAR_WEIGHTS)

    # Posterior over regimes — calibrated via offsets per regime
    # Linear features → softmax
    logits = {
        "risk_on":             1.6 * s["A"] + 0.9 * s["D"] + 0.8 * s["E"] + 0.5 * s["G"] + 0.4 * s["B"],
        "fragile_risk_on":     0.8 * s["A"] - 0.5 * s["D"] - 0.5 * s["F"] + 0.3 * s["E"] - 0.2 * s["G"],
        "transition":          -0.3 * abs(s["A"]) - 0.3 * abs(s["D"]) + 0.4 * s["H"] - 0.2,
        "risk_off":            -1.0 * s["A"] - 1.0 * s["D"] - 0.7 * s["B"] - 0.5 * s["G"],
        "bear_risk_elevated":  -1.3 * s["A"] - 1.3 * s["D"] - 1.0 * s["B"] - 0.8 * s["E"] - 0.5 * s["G"],
    }
    mx = max(logits.values())
    exps = {k: math.exp(v - mx) for k, v in logits.items()}
    z = sum(exps.values())
    posterior = {k: exps[k] / z for k in exps}
    chosen = max(posterior, key=posterior.get)

    # Bear-risk level: independent of regime; based on D + E + VIX
    bear_components = []
    if "D" in pillars: bear_components.append(max(0, -pillars["D"].get("score", 0)))
    if "E" in pillars: bear_components.append(max(0, -pillars["E"].get("score", 0)))
    if "B" in pillars:
        # VIX > 22 increases bear-risk
        latest = pillars["B"].get("latest", {})
        vix = latest.get("VIX")
        if vix is not None:
            bear_components.append(_clamp((vix - 14) / 20, 0, 1))
    bear_score = statistics.mean(bear_components) if bear_components else 0.0
    bear_level = "low"
    for thr, label in BEAR_RISK_BANDS:
        if bear_score < thr:
            bear_level = label
            break

    # Disconfirming evidence (pillars opposing chosen regime)
    disconfirming = []
    if chosen in ("bear_risk_elevated", "risk_off"):
        if s["D"] > 0.1: disconfirming.append("Pillar D credit/NFCI argues risk_on")
        if s["E"] > 0.1: disconfirming.append("Pillar E growth argues risk_on")
    elif chosen in ("risk_on", "fragile_risk_on"):
        if s["A"] < -0.2: disconfirming.append("Pillar A equity breadth deteriorating")
        if s["D"] < -0.2: disconfirming.append("Pillar D credit deteriorating")
        if s["B"] < -0.2: disconfirming.append("Pillar B volatility / positioning deteriorating")

    upgrade_conditions = [
        "HY OAS breaches 450bp with NFCI rising above 0",
        "10Y breaches 4.8% with SPX losing 200-DMA breadth below 50%",
        "VIX spot > 22 with 9d/30d in backwardation for 5+ days",
    ]
    downgrade_conditions = [
        "NFCI > 0 with credit spreads tightening",
        "Breadth recovers above 70% of S&P above 200-DMA with VIX < 13",
    ]

    return {
        "regime": chosen,
        "regime_posterior": {k: round(v, 3) for k, v in posterior.items()},
        "composite_score": round(composite, 3),
        "bear_risk_score": round(bear_score, 3),
        "bear_risk_level": bear_level,
        "confidence": round(1 - _entropy_normalized(posterior), 3),
        "disconfirming_evidence": disconfirming,
        "upgrade_conditions": upgrade_conditions,
        "downgrade_conditions": downgrade_conditions,
    }


def _entropy_normalized(p: dict) -> float:
    """Normalized entropy in [0, 1]; 0 = certain, 1 = uniform."""
    n = len(p)
    if n <= 1:
        return 0.0
    h = -sum(v * math.log(max(v, 1e-12)) for v in p.values())
    return h / math.log(n)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_dashboard() -> dict:
    pillars = {k: func() for k, func in PILLAR_FUNCS.items()}
    classified = _classify_regime(pillars)

    # Validation honesty
    available_count = sum(1 for p in pillars.values() if p.get("state") != "unavailable")
    missing_pillars = sorted(
        k for k, p in pillars.items()
        if p.get("state") == "unavailable"
    )
    valid_status = "preliminary" if available_count < 6 else "calibrating"

    # Fix C (2026-09-02 20:30 ET): orthogonal data_completeness dimension.
    # Reflects whether inputs were available, separate from forward-observation
    # thresholds. `insufficient` if no pillars resolved; `partial` if some are
    # missing; `complete` if all 8 are non-null.
    if available_count == 0:
        data_completeness = "insufficient"
    elif missing_pillars:
        data_completeness = "partial"
    else:
        data_completeness = "complete"

    return {
        "as_of_ts": _iso_local(_now_local()),
        "regime": classified["regime"],
        "regime_posterior": classified["regime_posterior"],
        "bear_risk_score": classified["bear_risk_score"],
        "bear_risk_level": classified["bear_risk_level"],
        "composite_score": classified["composite_score"],
        "confidence": classified["confidence"],
        "pillars": pillars,
        "disconfirming_evidence": classified["disconfirming_evidence"],
        "upgrade_conditions": classified["upgrade_conditions"],
        "downgrade_conditions": classified["downgrade_conditions"],
        "validation_status": valid_status,  # calibration_status semantic
        "data_completeness": data_completeness,
        "missing_pillars": missing_pillars,
        "calibration_thresholds": {
            "to_calibrating": "≥ 30 daily observations",
            "to_validated": "≥ 30 days + regime-transition hit-rate > 50% vs naïve baseline + bear-risk level predictive of ≥ +1.5σ realized vol events at ≥ 60%",
        },
        "schema_version": "macro_dashboard.v2",
    }


def save_dashboard(dashboard: dict) -> Path:
    """Save the dashboard to data/macro_dashboard/YYYY-MM-DD.json.
    Also appends a `macro_dashboard` row to the research ledger.
    """
    MACRO_DASHBOARD_ROOT.mkdir(parents=True, exist_ok=True)
    day = dashboard["as_of_ts"][:10]
    path = MACRO_DASHBOARD_ROOT / f"{day}.json"
    path.write_text(json.dumps(dashboard, indent=2, default=str))

    # Append to ledger
    try:
        from research_ledger import build_record, write_record
        rec = build_record(
            profile="macro_dashboard",
            summary=f"regime={dashboard['regime']}; bear_risk={dashboard['bear_risk_level']}; "
                    f"confidence={dashboard['confidence']}",
            kind="daily_dashboard",
            payload={"dashboard": dashboard},
            artifacts={"dashboard_file": str(path.relative_to(path.parents[2]))},
            validation_status=dashboard["validation_status"],
            data_completeness=dashboard["data_completeness"],
            macro_context={
                "regime": dashboard["regime"],
                "bear_risk_level": dashboard["bear_risk_level"],
                "as_of_ts": dashboard["as_of_ts"],
                "data_completeness": dashboard["data_completeness"],
                "missing_pillars": dashboard.get("missing_pillars", []),
            },
        )
        write_record(rec)
    except Exception as exc:
        # Don't crash the dashboard run if ledger write fails
        print(f"[macro_dashboard] ledger append failed: {exc}")

    return path


def main() -> int:
    d = build_dashboard()
    path = save_dashboard(d)
    print(f"saved {path}")
    print(f"regime = {d['regime']}")
    print(f"bear_risk_level = {d['bear_risk_level']}")
    print(f"validation_status = {d['validation_status']}")
    print(f"data_completeness = {d['data_completeness']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())