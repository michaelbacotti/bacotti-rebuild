"""regime_hmm.py — Hidden Markov Model regime classifier.

**Workstream B (2026-09-02 14:15 ET).** Replaces the simple bucket-based
`regime_assessment` in seasonality.py with a proper 3-state Gaussian HMM.

**Why HMM:**
- Markets exhibit regime persistence (low-vol regimes cluster, high-vol regimes cluster).
- A 3-state Gaussian HMM trained on rolling realized vol + log returns learns:
  - State 0: low-vol drift (grinding up/down)
  - State 1: mid-vol trend (typical market)
  - State 2: high-vol shock (earnings, macro event)
- Decoded state probability at any time is the "regime confidence."

**Training:**
- Pull 2y daily history via yfinance
- Features: 21d realized vol (annualized), 21d log return, 21d absolute return sum
- Fit GaussianHMM(n_components=3, covariance_type="full"), 5 random restarts
- Sort states by mean vol → label as low / mid / high

**Output per symbol:**
- `regime`: low / mid / high
- `regime_confidence`: posterior probability of current state
- `state_probs`: {low: p, mid: p, high: p}
- `regime_duration_days`: days in current state
- `transition_matrix_labeled`: 3x3 P(i→j)
- `diagnostics`: log_likelihood, AIC, BIC, converged, n_obs

Usage:
    from regime_hmm import classify_current_regime
    result = classify_current_regime("AVGO")
"""
from __future__ import annotations
import datetime as dt
import json
import math
import os
from typing import Any

import numpy as np
import pandas as pd

CACHE_DIR = "/Users/mike/.openclaw/workspace-bacottibot/entities/dependability/quant/data/regime_hmm"
os.makedirs(CACHE_DIR, exist_ok=True)

_STATE_NAMES = ["low", "mid", "high"]


def _features_from_prices(prices: pd.Series, window: int = 21) -> pd.DataFrame:
    """HMM feature matrix: rv (21d annualized), log_ret (21d cum), abs_log_ret (21d sum)."""
    log_p = np.log(prices.astype(float))
    log_ret_1d = log_p.diff()
    rv = log_ret_1d.rolling(window).std() * math.sqrt(252)
    cum_ret = log_p - log_p.shift(window)
    abs_sum = log_ret_1d.abs().rolling(window).sum()
    df = pd.concat([rv, cum_ret, abs_sum], axis=1).dropna()
    df.columns = ["rv", "log_ret", "abs_log_ret"]
    return df


def _fit_hmm(X: np.ndarray, *, seed_rvs: list[float] | None = None, n_restarts: int = 5):
    """Fit GaussianHMM with multiple restarts. Optionally seed RV means for reproducibility."""
    from hmmlearn.hmm import GaussianHMM
    best_model = None
    best_ll = -math.inf
    seeds = [42, 7, 13, 21, 99, 33, 77, 123][:n_restarts]

    # When seeding (re-fit), use diag covar to avoid singular full-covar init.
    # When fitting fresh, try full first (richer), then diag as fallback.
    if seed_rvs is not None:
        covar_attempts = ["diag"]
    else:
        covar_attempts = ["full", "diag", "spherical"]

    for covar_type in covar_attempts:
        for seed in seeds:
            try:
                m = GaussianHMM(
                    n_components=3,
                    covariance_type=covar_type,
                    n_iter=300,
                    tol=1e-5,
                    random_state=seed,
                )
                if seed_rvs is not None:
                    m.means_ = np.zeros((3, X.shape[1]))
                    for i in range(3):
                        m.means_[i, 0] = seed_rvs[i]
                        m.means_[i, 1] = 0.0
                        m.means_[i, 2] = float(np.mean(X[:, 2]))
                    if covar_type == "diag":
                        m.covars_ = np.tile(np.var(X, axis=0) + 1e-3, (3, 1))
                    elif covar_type == "spherical":
                        m.covars_ = np.full(3, float(np.mean(np.var(X, axis=0))) + 1e-3)
                    else:
                        # full: use a robust diagonal covar (will be replaced by EM anyway)
                        m.covars_ = np.zeros((3, X.shape[1], X.shape[1]))
                        base = np.diag(np.var(X, axis=0)) + np.eye(X.shape[1]) * 1e-3
                        for i in range(3):
                            m.covars_[i] = base
                    m.transmat_ = np.array([[0.95, 0.04, 0.01], [0.03, 0.94, 0.03], [0.01, 0.04, 0.95]])
                    m.startprob_ = np.array([1/3, 1/3, 1/3])
                    m.init_params = ""
                m.fit(X)
                ll = m.score(X)
                if ll > best_ll and np.isfinite(ll):
                    best_ll = ll
                    best_model = m
            except Exception:
                continue
        if best_model is not None:
            break  # got a fit, no need to try weaker covar types
    return best_model, best_ll


def _build_labeled_result(model, X: np.ndarray) -> dict:
    """Take a fitted model, return labeled result dict."""
    # Sort states by mean RV → assign low/mid/high labels
    order = sorted(range(3), key=lambda i: float(model.means_[i, 0]))
    state_idx_to_label = {order[k]: _STATE_NAMES[k] for k in range(3)}

    state_seq = model.predict(X)
    posteriors = model.predict_proba(X)

    current_idx = int(state_seq[-1])
    current_label = state_idx_to_label[current_idx]
    confidence = float(posteriors[-1, current_idx])
    state_probs = {state_idx_to_label[i]: float(posteriors[-1, i]) for i in range(3)}

    duration = 1
    for s in reversed(state_seq[:-1].tolist()):
        if s == current_idx:
            duration += 1
        else:
            break

    n = len(X)
    k = 3 * 2 + 3 * X.shape[1] + 3 * X.shape[1] * (X.shape[1] + 1) // 2
    log_likelihood = float(model.score(X))
    aic = 2 * k - 2 * log_likelihood
    bic = k * math.log(n) - 2 * log_likelihood

    n_iter = int(getattr(model.monitor_, "iter", 0)) if hasattr(model, "monitor_") else 0
    converged = bool(getattr(model.monitor_, "converged", False)) if hasattr(model, "monitor_") else False

    return {
        "regime": current_label,
        "regime_confidence": confidence,
        "state_probs": state_probs,
        "regime_duration_days": duration,
        "current_rv": float(X[-1, 0]),
        "current_log_ret_21d": float(X[-1, 1]),
        "state_means_rv_labeled": {state_idx_to_label[i]: float(model.means_[i, 0]) for i in range(3)},
        "transition_matrix_labeled": {
            state_idx_to_label[i]: {state_idx_to_label[j]: float(model.transmat_[i, j]) for j in range(3)}
            for i in range(3)
        },
        "diagnostics": {
            "log_likelihood": log_likelihood,
            "aic": float(aic),
            "bic": float(bic),
            "n_iter": n_iter,
            "converged": converged,
            "n_obs": n,
            "fit_at": dt.datetime.now(dt.UTC).isoformat(),
        },
    }


def classify_current_regime(symbol: str, *, window: int = 21, lookback_days: int = 504,
                            force_refit: bool = False, fallback: dict | None = None) -> dict:
    """Classify current regime for a symbol via 3-state Gaussian HMM.

    Returns dict with: regime, regime_confidence, state_probs, regime_duration_days,
    transition_matrix_labeled, diagnostics, as_of, method. Falls back to `fallback`
    (or {"regime": "unknown"}) if HMM fails.
    """
    symbol_u = symbol.upper()
    cache_path = os.path.join(CACHE_DIR, f"{symbol_u}.json")
    cached_meta = None
    seed_rvs = None

    if not force_refit and os.path.exists(cache_path):
        try:
            with open(cache_path) as f:
                cached_meta = json.load(f)
            age_hours = (dt.datetime.now(dt.UTC) -
                         dt.datetime.fromisoformat(cached_meta["fit_at"].replace("Z", "+00:00"))
                         ).total_seconds() / 3600
            if age_hours < 24:
                # Use cached state means in order [low, mid, high]
                seed_rvs = [cached_meta["state_means_rv"][lbl] for lbl in _STATE_NAMES]
        except Exception:
            cached_meta = None

    # Pull prices
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol_u)
        hist = ticker.history(period=f"{max(lookback_days // 252, 2)}y", auto_adjust=True)
        if hist is None or hist.empty or len(hist) < window * 4:
            return fallback or {"symbol": symbol_u, "regime": "unknown", "method": "fallback",
                                 "reason": "insufficient_history"}
    except Exception:
        return fallback or {"symbol": symbol_u, "regime": "unknown", "method": "fallback",
                             "reason": "yfinance_error"}

    feat = _features_from_prices(hist["Close"], window=window)
    if len(feat) < 90:
        return fallback or {"symbol": symbol_u, "regime": "unknown", "method": "fallback",
                             "reason": "too_few_features"}

    X = feat.values
    model, _ = _fit_hmm(X, seed_rvs=seed_rvs, n_restarts=5 if seed_rvs is None else 3)
    if model is None:
        return fallback or {"symbol": symbol_u, "regime": "unknown", "method": "fallback",
                             "reason": "hmm_fit_failed"}

    result = _build_labeled_result(model, X)
    result["symbol"] = symbol_u
    result["as_of"] = str(feat.index[-1].date())
    result["method"] = "gaussian_hmm_3state"

    # Persist diagnostics
    meta = {
        "symbol": symbol_u,
        "fit_at": result["diagnostics"]["fit_at"],
        "n_obs": result["diagnostics"]["n_obs"],
        "log_likelihood": result["diagnostics"]["log_likelihood"],
        "aic": result["diagnostics"]["aic"],
        "bic": result["diagnostics"]["bic"],
        "n_iter": result["diagnostics"]["n_iter"],
        "converged": result["diagnostics"]["converged"],
        "state_labels": {str(i): lbl for i, lbl in enumerate(_STATE_NAMES)},
        "state_means_rv": result["state_means_rv_labeled"],
        "transition_matrix": model.transmat_.tolist(),
        "feature_window": window,
        "lookback_days": lookback_days,
        "data_start": str(feat.index[0].date()),
        "data_end": str(feat.index[-1].date()),
    }
    try:
        with open(cache_path, "w") as f:
            json.dump(meta, f, indent=2)
    except Exception:
        pass

    return result


def main():
    import sys
    symbols = sys.argv[1:] if len(sys.argv) > 1 else ["AVGO", "AAPL", "TSLA", "SPY"]
    for sym in symbols:
        r = classify_current_regime(sym)
        print(f"\n=== {sym} ===")
        if r.get("method") == "fallback":
            print(f"  HMM fallback: {r.get('reason', r)}")
            continue
        print(f"  regime: {r['regime']} (conf={r['regime_confidence']:.2f})")
        print(f"  duration: {r['regime_duration_days']} days")
        print(f"  current_rv: {r['current_rv']*100:.1f}%")
        print(f"  state_probs: {r['state_probs']}")
        print(f"  state means RV: {r['state_means_rv_labeled']}")
        print(f"  AIC: {r['diagnostics']['aic']:.1f}, BIC: {r['diagnostics']['bic']:.1f}, "
              f"n_iter: {r['diagnostics']['n_iter']}, converged: {r['diagnostics']['converged']}")
        print(f"  transition matrix:")
        for src, row in r['transition_matrix_labeled'].items():
            row_str = ", ".join(f"{dst}={p:.3f}" for dst, p in row.items())
            print(f"    {src}: {row_str}")


if __name__ == "__main__":
    main()