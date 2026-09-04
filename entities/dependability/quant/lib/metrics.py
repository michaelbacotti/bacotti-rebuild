"""metrics.py — pure computation helpers for option analysis.

No SDK calls. Operates on structured contract data emitted by fetch_chain.py.

Every metric is derivable from contract rows + spot price; no fabrication.
"""
from __future__ import annotations
from statistics import median

# ---------- ATM detection ----------
def nearest_atm(chain: dict, spot: float) -> tuple[dict, dict]:
    """Return (call_nearest_atm, put_nearest_atm) for strike closest to spot."""
    call_a = min(chain['calls'], key=lambda r: abs(r['strike'] - spot))
    put_a = min(chain['puts'], key=lambda r: abs(r['strike'] - spot))
    return call_a, put_a


# ---------- Bid-ask metrics ----------
def mid(row: dict) -> float | None:
    if row.get('bid') is None or row.get('ask') is None:
        return None
    return (row['bid'] + row['ask']) / 2.0


def bid_ask_pct_of_mid(row: dict) -> float | None:
    """Return (ask - bid) / mid as a fraction. None if any input missing."""
    b, a = row.get('bid'), row.get('ask')
    if b is None or a is None or (a + b) == 0:
        return None
    return (a - b) / ((a + b) / 2.0)


# ---------- Liquidity filter (per rules.yaml#contract_filters) ----------
def passes_liquidity(row: dict, *, tier: str = 'etf') -> bool:
    """Apply contract_filters. Returns True if the contract survives the filter.

    tier in {'index', 'etf', 'stock'}.
    """
    floor = {'index': 500, 'etf': 500, 'stock': 100}.get(tier, 100)
    if row.get('open_interest', 0) < floor:
        return False
    if row.get('open_interest', 0) < 100:  # hard floor per doctrine
        return False
    if row.get('volume', 0) < 50:
        return False
    ba = bid_ask_pct_of_mid(row)
    if ba is None or ba > 0.07:
        return False
    if (row.get('bid') or 0) <= 0:  # exclude zero-bid
        return False
    if (row.get('bid') or 0) >= (row.get('ask') or float('inf')):  # exclude crosses
        return False
    return True


# ---------- Expected move (1σ) from ATM straddle ----------
def expected_move_from_straddle(spot: float, dte: int, atm_call: dict, atm_put: dict) -> dict:
    """Compute 1σ expected move from ATM straddle mid.

    BKM-ish: IV_straddle ≈ (straddle_mid / spot) * sqrt(252 / dte)
    Then ±1σ = spot * IV * sqrt(dte / 252)
    """
    cm = atm_call.get('mid')
    pm = atm_put.get('mid')
    if cm is None or pm is None:
        return {'straddle_mid': None, 'iv_annualized': None, 'move_dollars_1sigma': None,
                'move_pct_1sigma': None, 'error': 'missing mid'}
    if dte <= 0:
        return {'straddle_mid': cm + pm, 'iv_annualized': None,
                'move_dollars_1sigma': None, 'move_pct_1sigma': None, 'error': 'dte<=0'}
    sm = cm + pm
    iv = (sm / spot) * (252.0 / dte) ** 0.5
    move_d = spot * iv * (dte / 252.0) ** 0.5
    move_pct = (move_d / spot) * 100.0
    return {
        'straddle_mid': round(sm, 4),
        'iv_annualized': round(iv, 6),
        'move_dollars_1sigma': round(move_d, 4),
        'move_pct_1sigma': round(move_pct, 4),
    }


# ---------- POP estimation (rough) for vertical spreads ----------
def pop_vertical_credit(short_row: dict) -> float | None:
    """Rough POP for a credit spread = 1 - P(short leg finishes ITM).
    We approximate P(short ITM at expiry) ≈ |short delta|.
    """
    d = short_row.get('delta')
    if d is None:
        return None
    # For credit spreads, short side is short the option, but delta is the
    # position delta. Per-leg spec for short: e.g., short call OTM has positive
    # delta. P(short ITM) ≈ |delta|.
    p_short_itm = abs(d)
    pop = 1.0 - p_short_itm
    return max(0.0, min(1.0, pop))


def pop_vertical_debit(long_row: dict) -> float | None:
    """Rough POP for a debit spread = P(long leg finishes ITM).
    Approximate ≈ |delta| for an OTM long leg (call or put).
    """
    d = long_row.get('delta')
    if d is None:
        return None
    return max(0.0, min(1.0, abs(d)))


# ---------- Spread construction ----------
def vertical_credit(chain_calls, chain_puts, side: str, short_strike: int, long_strike: int, tier: str = 'etf') -> dict | None:
    """Build a vertical credit spread (call credit or put credit).
    side='CALL': short higher call, long lower call. Net = credit.
    side='PUT': short higher put, long lower put. Net = credit.
    """
    if side == 'CALL':
        legs_src = chain_calls
        short_row = next((r for r in legs_src if r['strike'] == short_strike), None)
        long_row = next((r for r in legs_src if r['strike'] == long_strike), None)
    elif side == 'PUT':
        legs_src = chain_puts
        short_row = next((r for r in legs_src if r['strike'] == short_strike), None)
        long_row = next((r for r in legs_src if r['strike'] == long_strike), None)
    else:
        return None
    if short_row is None or long_row is None:
        return None
    short_bid = short_row.get('bid'); long_ask = long_row.get('ask')
    if short_bid is None or long_ask is None:
        return None
    credit = (short_bid - long_ask)
    width = abs(short_strike - long_strike)
    max_loss = width - credit
    max_gain = credit
    pop = pop_vertical_credit(short_row)
    return {
        'kind': f'{side.lower()}_credit',
        'legs': [
            {'side': 'SHORT', 'type': side, 'strike': short_strike, 'bid': short_bid,
             'delta': short_row.get('delta'), 'oi': short_row.get('open_interest')},
            {'side': 'LONG', 'type': side, 'strike': long_strike, 'ask': long_ask,
             'delta': long_row.get('delta'), 'oi': long_row.get('open_interest')},
        ],
        'credit': round(credit, 4),
        'width': width,
        'max_loss': round(max_loss, 4),
        'max_gain': round(max_gain, 4),
        'breakeven': short_strike - credit if side == 'CALL' else short_strike + credit,
        'pop_estimate': round(pop, 4) if pop is not None else None,
        'deltas': (short_row.get('delta'), long_row.get('delta')),
        'short_row': short_row,
        'long_row': long_row,
    }


def vertical_debit(chain_calls, chain_puts, side: str, long_strike: int, short_strike: int, tier: str = 'etf') -> dict | None:
    """Build a vertical debit spread (bull_call or bear_put).
    side='CALL': long lower call, short higher call. Net = debit.
    side='PUT': long higher put, short lower put. Net = debit.

    Returns None if any required leg is missing.
    """
    if side == 'CALL':
        legs_src = chain_calls
        long_row = next((r for r in legs_src if r['strike'] == long_strike), None)
        short_row = next((r for r in legs_src if r['strike'] == short_strike), None)
    elif side == 'PUT':
        legs_src = chain_puts
        long_row = next((r for r in legs_src if r['strike'] == long_strike), None)
        short_row = next((r for r in legs_src if r['strike'] == short_strike), None)
    else:
        return None
    if long_row is None or short_row is None:
        return None
    long_ask = long_row.get('ask'); short_bid = short_row.get('bid')
    if long_ask is None or short_bid is None:
        return None
    debit = long_ask - short_bid
    width = abs(short_strike - long_strike)
    max_loss = debit
    max_gain = width - debit
    pop = pop_vertical_debit(long_row)
    return {
        'kind': f'{"bull_call" if side == "CALL" else "bear_put"}_spread',
        'legs': [
            {'side': 'LONG', 'type': side, 'strike': long_strike, 'ask': long_ask,
             'delta': long_row.get('delta'), 'oi': long_row.get('open_interest')},
            {'side': 'SHORT', 'type': side, 'strike': short_strike, 'bid': short_bid,
             'delta': short_row.get('delta'), 'oi': short_row.get('open_interest')},
        ],
        'debit': round(debit, 4),
        'width': width,
        'max_loss': round(max_loss, 4),
        'max_gain': round(max_gain, 4),
        'breakeven': long_strike + debit if side == 'CALL' else long_strike - debit,
        'pop_estimate': round(pop, 4) if pop is not None else None,
        'deltas': (long_row.get('delta'), short_row.get('delta')),
        'long_row': long_row,
        'short_row': short_row,
    }


def premium_edge(spread: dict) -> float | None:
    """Edge = (max_gain) / (max_loss) — risk-reward ratio.
    >= 0.10 (10%) per rules.yaml#strategies_allowed.normal.
    """
    ml = spread.get('max_loss'); mg = spread.get('max_gain')
    if ml is None or ml <= 0 or mg is None:
        return None
    return mg / ml


# ---------- Long butterfly (Mike preference: low max-loss / high reward if underlying pins near middle strike) ----------
def long_butterfly(chain_calls, chain_puts, side: str, lower_strike: int, middle_strike: int, upper_strike: int) -> dict | None:
    """Build a LONG call-butterfly or LONG put-butterfly.

    Long call butterfly (bullish neutral / mildly bullish):
      BUY 1 lower_strike call (long wing)
      SELL 2 middle_strike calls (body)  — ratio 2:1
      BUY 1 upper_strike call (long wing)

    Mike preference (per directive 2026-08-31 11:59 ET): bullish = call butterfly with strikes
    ABOVE current spot (lower wing above spot, expecting underlying to PIN at the middle strike
    or drift slightly higher — capped gain if it blows through upper wing, but you didn't pay
    for the tail).

    Long put butterfly (bearish neutral / mildly bearish):
      BUY 1 upper_strike put (long wing, higher strike)
      SELL 2 middle_strike puts (body)
      BUY 1 lower_strike put (long wing, lower strike)

    Mike preference: bearish = put butterfly with strikes BELOW current spot
    (so the body sits below current spot — expects underlying to PIN at middle or drift slightly lower).

    Math:
      wing_width = upper_strike - middle_strike  (assumes evenly spaced; validated below)
      debit = lower_long_ask + upper_long_ask - 2 * middle_short_bid
      max_loss = debit  (if underlying finishes outside the wings, all 3 legs expire worthless
                        except the long wings, but those finish ITM... actually if underlying
                        goes far enough beyond, you exercise the in-the-money long wing and sell
                        the body — net is wing-width - debit on the winning side)
      max_gain = wing_width - debit  (achieved if underlying pins EXACTLY at middle strike at expiry)
      breakeven_lower = lower_strike + debit  (call fly lower BE)
      breakeven_upper = middle_strike - debit  (call fly upper BE)

    Returns None if any leg is missing or wings are uneven.
    """
    if side == 'CALL':
        legs_src = chain_calls
        lower_row = next((r for r in legs_src if r['strike'] == lower_strike), None)
        middle_row = next((r for r in legs_src if r['strike'] == middle_strike), None)
        upper_row = next((r for r in legs_src if r['strike'] == upper_strike), None)
    elif side == 'PUT':
        legs_src = chain_puts
        lower_row = next((r for r in legs_src if r['strike'] == lower_strike), None)
        middle_row = next((r for r in legs_src if r['strike'] == middle_strike), None)
        upper_row = next((r for r in legs_src if r['strike'] == upper_strike), None)
    else:
        return None
    if lower_row is None or middle_row is None or upper_row is None:
        return None
    # Verify even wing widths (most brokers standard)
    w_lo = middle_strike - lower_strike
    w_hi = upper_strike - middle_strike
    if w_lo <= 0 or w_hi <= 0 or w_lo != w_hi:
        return None
    wing_width = w_lo
    lower_ask = lower_row.get('ask')
    middle_bid = middle_row.get('bid')
    upper_ask = upper_row.get('ask')
    if lower_ask is None or middle_bid is None or upper_ask is None:
        return None
    # 1 lower long + 2 middle short + 1 upper long — debit side
    # Standard long call butterfly: BUY lower, SELL 2x middle, BUY upper
    # net debit = lower_ask + upper_ask - 2*middle_bid
    debit = lower_ask + upper_ask - (2 * middle_bid)
    if debit is None or debit <= 0:
        return None
    max_loss = debit
    max_gain = wing_width - debit
    if max_gain <= 0:
        return None
    # POP estimate: probability that underlying finishes between lower+debit and upper-debit (the profit zone)
    # Use Black-Scholes lognormal model if iv and dte are provided (PRECISION mode).
    # Fall back to delta-based approximation if not.
    iv = middle_row.get('iv')
    dte = middle_row.get('dte')
    if iv is not None and dte is not None and iv > 0 and dte > 0:
        try:
            import bs
            if side == 'CALL':
                pop = bs.call_butterfly_pop(lower_row.get('spot', 0), lower_strike, middle_strike, upper_strike, debit, iv, dte)
            else:
                pop = bs.put_butterfly_pop(lower_row.get('spot', 0), lower_strike, middle_strike, upper_strike, debit, iv, dte)
        except (ImportError, Exception):
            middle_delta = abs(middle_row.get('delta') or 0)
            pop = max(0.0, min(1.0, 1 - 2 * middle_delta))
    else:
        # Fallback: delta-based approximation
        middle_delta = abs(middle_row.get('delta') or 0)
        pop = max(0.0, min(1.0, 1 - 2 * middle_delta))
    kind = 'long_call_butterfly' if side == 'CALL' else 'long_put_butterfly'
    return {
        'kind': kind,
        'legs': [
            {'side': 'LONG',  'type': side, 'strike': lower_strike,  'role': 'lower_wing', 'price': lower_ask,
             'delta': lower_row.get('delta'),  'oi': lower_row.get('open_interest')},
            {'side': 'SHORT', 'type': side, 'strike': middle_strike, 'role': 'body_short_2x', 'price': middle_bid,
             'delta': middle_row.get('delta'),  'oi': middle_row.get('open_interest'), 'multiplier': 2},
            {'side': 'LONG',  'type': side, 'strike': upper_strike,  'role': 'upper_wing', 'price': upper_ask,
             'delta': upper_row.get('delta'),  'oi': upper_row.get('open_interest')},
        ],
        'debit': round(debit, 4),
        'wing_width': wing_width,
        'max_loss': round(max_loss, 4),
        'max_gain': round(max_gain, 4),
        'breakeven_lower': round(lower_strike + debit, 4),
        'breakeven_upper': round(upper_strike - debit, 4) if side == 'CALL' else round(lower_strike + debit, 4),
        'pin_strike': middle_strike,
        'pop_estimate': round(pop, 4),
        'deltas': (lower_row.get('delta'), middle_row.get('delta'), upper_row.get('delta')),
    }


def butterfly_candidates(chain_calls, chain_puts, spot: float, side: str, wing_pct: float = 0.05, dte: int = 25) -> list[dict]:
    """Generate a list of long butterfly candidates centered near ATM with even wings.

    For CALL butterflies (bullish): center the body ABOVE current spot per Mike preference.
      middle_strike = round_to_nearest_strike_above(spot) (ATM or first OTM strike up)
      lower_strike = middle_strike - wing_width
      upper_strike = middle_strike + wing_width

    For PUT butterflies (bearish): center the body BELOW current spot per Mike preference.
      middle_strike = round_to_nearest_strike_below(spot)
      lower_strike = middle_strike - wing_width
      upper_strike = middle_strike + wing_width

    wing_pct = 0.05 means wing width = 5% of spot on each side (so body sits 5% OTM in Mike's preferred direction).

    Returns list of butterfly dicts (could be empty if no valid strikes in chain).
    """
    # Combine strikes from the chosen side and sort
    if side == 'CALL':
        strikes = sorted({r['strike'] for r in chain_calls})
    else:
        strikes = sorted({r['strike'] for r in chain_puts})
    if not strikes:
        return []
    # Compute wing_width in dollars
    wing_width = max(1.0, round(spot * wing_pct / 2))  # half-wing; doubled = full wing
    # We'll try a small grid of body-center strikes near spot
    cands = []
    # Try every strike as the body center, walking outward from spot
    candidates_middle = []
    if side == 'CALL':
        # Bullish: prefer strikes >= spot (Mike's preference — strike above current)
        for s in strikes:
            if s >= spot * 0.998:  # ATM or above
                candidates_middle.append(s)
    else:
        # Bearish: prefer strikes <= spot
        for s in strikes:
            if s <= spot * 1.002:
                candidates_middle.append(s)
    for mid in candidates_middle:
        lo = mid - wing_width
        hi = mid + wing_width
        # Need exactly lo, mid, hi in strikes
        if lo not in strikes or mid not in strikes or hi not in strikes:
            continue
        fly = long_butterfly(chain_calls, chain_puts, side, lo, mid, hi)
        if fly is None or fly.get('max_gain', 0) <= 0:
            continue
        cands.append(fly)
        if len(cands) >= 3:  # cap per symbol/side
            break
    return cands


def butterfly_at_target(chain_calls, chain_puts, spot: float, side: str, pin_target: float,
                         wing_dollars: float = None, wing_pct: float = None) -> dict | None:
    """Build a long butterfly pinned at a specific target strike (e.g. MA20, or spot ± N×σ).

    Unlike butterfly_candidates() which walks from spot outward using fixed wing_pct, this
    pins the body to a TARGET strike and computes the wing width separately.

    pin_target: the strike you want the underlying to land at (e.g. 270 for AMZN if MA20=265.72).
    side: 'CALL' (bullish — pin above spot) or 'PUT' (bearish — pin below spot). Caller is
          responsible for picking a sensible side given pin vs spot relationship.
    wing_dollars: explicit dollar width on each side (e.g. 5 = 5-wide wings, body $5 above/below).
                  If None, derived from wing_pct of spot.
    wing_pct: alternative to wing_dollars; wing width = round(spot * wing_pct).

    Returns a single fly dict or None if no valid strikes / missing legs.
    """
    if side == 'CALL':
        strikes = sorted({r['strike'] for r in chain_calls})
    else:
        strikes = sorted({r['strike'] for r in chain_puts})
    if not strikes:
        return None

    # Round pin_target to nearest available strike
    pin_strike = min(strikes, key=lambda s: abs(s - pin_target))
    pin_actual = pin_strike  # nearest available

    # Determine wing width
    if wing_dollars is None:
        if wing_pct is None:
            wing_pct = 0.05  # default 5%
        wing_dollars = max(1, round(spot * wing_pct / 2))  # half-wing dollars

    lower_strike = pin_strike - wing_dollars
    upper_strike = pin_strike + wing_dollars

    # Sanity: all three strikes must exist in the chain
    if lower_strike not in strikes or pin_strike not in strikes or upper_strike not in strikes:
        # Try halving wing_dollars until all 3 exist, down to $1 minimum
        for attempt in range(10):
            wing_dollars = max(1, wing_dollars // 2)
            lower_strike = pin_strike - wing_dollars
            upper_strike = pin_strike + wing_dollars
            if lower_strike in strikes and pin_strike in strikes and upper_strike in strikes:
                break
        else:
            return None

    fly = long_butterfly(chain_calls, chain_puts, side, lower_strike, pin_strike, upper_strike)
    if fly is not None:
        fly['pin_target_requested'] = pin_target
        fly['pin_strike_actual'] = pin_strike
        fly['pin_offset_from_target'] = pin_strike - pin_target
        fly['wing_width_dollars'] = wing_dollars
        fly['pin_offset_from_spot_pct'] = round((pin_strike - spot) / spot * 100, 2)
    return fly
