"""Black-Scholes probability helpers for option structure POP estimation."""

import math
from typing import Optional


def _norm_cdf(x: float) -> float:
    """Standard normal CDF using math.erfc (no scipy needed for portability)."""
    return 0.5 * math.erfc(-x / math.sqrt(2))


def lognormal_pop_in_range(
    spot: float,
    lower_target: float,
    upper_target: float,
    iv_annualized: float,
    dte_days: int,
) -> float:
    """
    P(lower_target <= S_T <= upper_target) under geometric Brownian motion
    with constant vol iv_annualized over dte_days calendar days.

    Uses d2 of each boundary relative to spot:
        d2 = [ln(S/K) - 0.5*sigma^2*T] / (sigma * sqrt(T))

    POP = N(d2_upper) - N(d2_lower)
    where N is standard normal CDF.

    This is the risk-neutral probability that the underlying lands in the
    profit zone at expiry. For long call butterflies with strikes (L, M, U)
    and debit D, the profit zone is (L+D, U-D) [i.e., M-D +/- D from middle].
    """
    if iv_annualized <= 0 or dte_days <= 0 or spot <= 0:
        return 0.0
    T = dte_days / 365.0
    sigma = iv_annualized
    vol = sigma * math.sqrt(T)

    if vol <= 0:
        return 0.0

    # d2 for lower bound
    if lower_target <= 0:
        d2_lower = -1e9
    else:
        d2_lower = (math.log(spot / lower_target) - 0.5 * sigma * sigma * T) / vol

    # d2 for upper bound
    if upper_target <= 0:
        d2_upper = -1e9
    else:
        d2_upper = (math.log(spot / upper_target) - 0.5 * sigma * sigma * T) / vol

    pop = _norm_cdf(d2_lower) - _norm_cdf(d2_upper)
    return max(0.0, min(1.0, pop))


def call_butterfly_pop(
    spot: float,
    lower_strike: float,
    middle_strike: float,
    upper_strike: float,
    debit: float,
    iv_annualized: float,
    dte_days: int,
) -> float:
    """POP for long CALL butterfly. Profit zone = (lower+debit, upper-debit)."""
    lower_target = lower_strike + debit
    upper_target = upper_strike - debit
    if upper_target <= lower_target:
        return 0.0
    return lognormal_pop_in_range(spot, lower_target, upper_target, iv_annualized, dte_days)


def put_butterfly_pop(
    spot: float,
    lower_strike: float,
    middle_strike: float,
    upper_strike: float,
    debit: float,
    iv_annualized: float,
    dte_days: int,
) -> float:
    """POP for long PUT butterfly. Profit zone = (lower+debit, upper-debit) too (symmetric)."""
    return call_butterfly_pop(spot, lower_strike, middle_strike, upper_strike, debit, iv_annualized, dte_days)
