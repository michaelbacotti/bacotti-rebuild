"""scan.py — orchestrator: pull chains for the universe, apply v1 rules, surface candidates.

Pipeline per underlying:
  1. fetch_expirations(symbol) -> list of ISO dates
  2. pick nearest expiration within normal-mode DTE window [20, 60]
  3. fetch_chain(symbol, expiration)
  4. compute spot (use mid of deepest-OI ATM call+put)
  5. expected_move_from_straddle(spot, dte, atm_call, atm_put)
  6. filter rows for liquidity per contract_filters
  7. for each plausible vertical spread within max_width:
     - construct spread
     - check POP >= 55%
     - check premium_edge >= 10%
     - score by (edge, liquidity) and emit if in top-N

Output: structured JSON of universe scan + candidate list.

Research-only: no place_* calls. Surfaced candidates are recommendations only.
"""
from __future__ import annotations
import sys
import os
import json
import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from _env import load_env
from fetch_chain import fetch_expirations, fetch_chain
from public_api_sdk import PublicApiClient, ApiKeyAuthConfig

import metrics as M
import vix as vix_mod


# Universe (per universe.yaml v1, schema locked 2026-08-31 10:47 ET)
# Tier-1 → Tier-2 proxy mapping per Mike 2026-08-31 11:50 ET directive ("Option C: Map Tier-1 → ETF proxies.
# This will be research, I can convert to indexes if I want to trade.")
# The scan resolves each Tier-1 symbol through PROXY_MAPPING and reports the underlying as a "tier=etf, source=tier1_proxy"
# record (not "tier=index") — research output uses ETF pricing. Mike retains Tier-1 entries for when
# Tradier/Alpaca direct index access becomes available.
PROXY_MAPPING = {
    'SPX': 'SPY',
    'XSP': 'SPY',
    'NDX': 'QQQ',
    'RUT': 'IWM',
    'DJX': 'DIA',  # DIA is the Dow 30 ETF proxy (not in original ETF list, but liquid)
}
# Add DIA to ETF set if proxy mapping references it
UNIVERSE_INDEXES_CANONICAL = ['SPX', 'XSP', 'RUT', 'NDX', 'DJX']
UNIVERSE_ETFS = ['SPY', 'QQQ', 'IWM', 'TLT', 'XLRE', 'XLB']
# When proxy mapping is active, the effective ETFs to scan = UNIVERSE_ETFS ∪ set(PROXY_MAPPING.values())
EFFECTIVE_ETFS = list(dict.fromkeys(UNIVERSE_ETFS + list(set(PROXY_MAPPING.values()))))  # preserve order, dedupe
# Tier-3 stocks — single-name options. For v3, scan a representative subset to keep
# runtime reasonable; tier='stock' reduces liquidity floor per rules.yaml (100 vs 500).
EFFECTIVE_STOCKS = [
    'AAPL', 'MSFT', 'NVDA', 'AMZN', 'META',        # mega-tech (6 stocks)
    'GOOGL', 'AMD',
    'JPM', 'BAC',                                    # financials
    'LLY', 'UNH',                                    # healthcare
    'WMT', 'HD',                                     # consumer
    'XOM', 'CVX',                                    # energy
    'CAT', 'BA',                                     # industrial
    'NFLX',                                          # communication
]

# Mike 2026-08-31 12:16 ET directive: 'avoid DIA'
# DIA returned 0 candidates in v3 (chain empty for 25-DTE window).
# Drop DIA from the effective ETF scan list.
EFFECTIVE_ETFS = [s for s in EFFECTIVE_ETFS if s != 'DIA']
# Also remove from proxy_mapping (DJX → ? Mike did not specify a replacement;
# keeping DJX entry in universe.yaml but with no proxy means scan simply skips it)
PROXY_MAPPING.pop('DJX', None)
TIER_OF = {**{s: 'etf' for s in EFFECTIVE_ETFS},
           **{s: 'stock' for s in EFFECTIVE_STOCKS}}

# Display labels — for reporting clarity, we keep the canonical Tier-1 name
DISPLAY_LABEL = {}
for canonical, proxy in PROXY_MAPPING.items():
    DISPLAY_LABEL[proxy] = f'{canonical} (proxied via {proxy})'

# v1 rules (per rules.yaml + risk_mode.yaml)
RISK_MODE = 'normal'                  # current_mode per risk_mode.yaml v1
DTE_MIN, DTE_MAX = 20, 60
MIN_POP = 0.55
MIN_EDGE = 0.10
N_CANDIDATES_TARGET = 3               # aim for 3 candidates today (conservative)


def get_quote(symbol: str, tier: str) -> tuple[float, dict]:
    """Use get_quotes SDK for spot price; returns (spot, quote_dict)."""
    load_env()
    client = PublicApiClient(auth_config=ApiKeyAuthConfig(api_secret_key=os.environ['PUBLIC_COM_SECRET']))
    acct = os.environ['PUBLIC_COM_ACCOUNT_ID']
    from public_api_sdk import OrderInstrument, InstrumentType
    oi = OrderInstrument(symbol=symbol, type=InstrumentType.EQUITY)
    resp = client.get_quotes(instruments=[oi], account_id=acct)
    if not resp:
        raise RuntimeError(f"no quote returned for {symbol}")
    q = resp[0]
    bid = float(q.bid) if q.bid is not None else None
    ask = float(q.ask) if q.ask is not None else None
    if bid is None or ask is None or (bid + ask) == 0:
        raise RuntimeError(f"missing bid/ask for {symbol}")
    spot = (bid + ask) / 2.0
    qd = {
        'last': float(q.last) if q.last is not None else None,
        'bid': bid,
        'ask': ask,
        'mid': spot,
        'bid_ts': q.bid_timestamp.isoformat() if q.bid_timestamp else None,
        'ask_ts': q.ask_timestamp.isoformat() if q.ask_timestamp else None,
        'volume': q.volume if q.volume is not None else None,
    }
    return spot, qd


def pick_dte_window_expiration(expirations: list[str]) -> tuple[str, int] | None:
    """Pick the first expiration whose DTE is within [DTE_MIN, DTE_MAX] (closest to DTE_MIN)."""
    today = datetime.date.today()
    for exp_iso in sorted(expirations):
        d = datetime.date.fromisoformat(exp_iso)
        dte = (d - today).days
        if DTE_MIN <= dte <= DTE_MAX:
            return exp_iso, dte
    return None


def safe_round(x, n=4):
    if x is None:
        return None
    try:
        return round(float(x), n)
    except Exception:
        return None


def scan_one(symbol: str, tier: str) -> dict:
    """Run scan over one symbol. Returns structured record."""
    # Determine if this is a Tier-1 proxied symbol (label it for reporting)
    proxy_origin = None
    for canonical, proxy in PROXY_MAPPING.items():
        if symbol == proxy and canonical in UNIVERSE_INDEXES_CANONICAL:
            proxy_origin = canonical
            break

    record = {
        'symbol': symbol,
        'tier': tier,
        'proxy_origin': proxy_origin,  # None if not a proxy; canonical Tier-1 name if so
        'display_label': DISPLAY_LABEL.get(symbol),
        'status': 'pending',
        'errors': [],
        'spot': None,
        'expiration_chosen': None,
        'dte_chosen': None,
        'expected_move': None,
        'liquidity_pass_count': None,
        'candidates': [],
        'rejections': [],
    }
    try:
        spot, quote = get_quote(symbol, tier)
        record['spot'] = safe_round(spot)
        record['quote'] = quote
    except Exception as e:
        record['status'] = 'failed'
        record['errors'].append(f'quote: {e}')
        return record
    try:
        exps = fetch_expirations(symbol)
    except Exception as e:
        record['status'] = 'failed'
        record['errors'].append(f'expirations: {e}')
        return record
    picked = pick_dte_window_expiration(exps)
    if picked is None:
        record['status'] = 'skipped'
        record['rejections'].append(f'no expiration in DTE window [{DTE_MIN},{DTE_MAX}]; available range {exps[0]}..{exps[-1]}')
        return record
    exp, dte = picked
    record['expiration_chosen'] = exp
    record['dte_chosen'] = dte
    try:
        chain = fetch_chain(symbol, exp)
    except Exception as e:
        record['status'] = 'failed'
        record['errors'].append(f'chain: {e}')
        return record

    # ATM expected move
    atm_call, atm_put = M.nearest_atm(chain, spot)
    record['atm_call_strike'] = atm_call['strike']
    record['atm_put_strike'] = atm_put['strike']
    em = M.expected_move_from_straddle(spot, dte, atm_call, atm_put)
    record['expected_move'] = em

    # Liquidity-filtered survivors
    calls_survivors = [r for r in chain['calls'] if M.passes_liquidity(r, tier=tier)]
    puts_survivors = [r for r in chain['puts'] if M.passes_liquidity(r, tier=tier)]
    record['liquidity_pass_count'] = {'calls': len(calls_survivors), 'puts': len(puts_survivors),
                                       'raw_calls': len(chain['calls']), 'raw_puts': len(chain['puts'])}

    # Build candidate spreads (only for survivors within max_width)
    max_width_dollars = spot * 0.05
    candidates = []

    # Build debit call spread candidates (bull_call)
    if tier != 'stock' or True:  # apply to all tiers per v1
        sorted_calls = sorted(calls_survivors, key=lambda r: r['strike'])
        for long_c, short_c in zip(sorted_calls, sorted_calls[1:]):
            width = short_c['strike'] - long_c['strike']
            if width <= 0 or width > max_width_dollars:
                continue
            sp = M.vertical_debit(chain['calls'], chain['puts'], 'CALL',
                                  long_strike=long_c['strike'], short_strike=short_c['strike'])
            if sp is None:
                continue
            edge = M.premium_edge(sp)
            pop = sp.get('pop_estimate')
            if pop is None or pop < MIN_POP:
                record['rejections'].append(f'CALL debit {long_c["strike"]}/{short_c["strike"]} POP={pop} below {MIN_POP}')
                continue
            if edge is None or edge < MIN_EDGE:
                record['rejections'].append(f'CALL debit {long_c["strike"]}/{short_c["strike"]} edge={edge} below {MIN_EDGE}')
                continue
            candidates.append({**sp, 'side_label': 'bull_call_spread', 'edge': safe_round(edge, 4),
                               'liquidity_score': (long_c.get('open_interest', 0) + short_c.get('open_interest', 0)),
                               'pop': pop})

        # bear_put: long higher put, short lower put
        sorted_puts = sorted(puts_survivors, key=lambda r: r['strike'], reverse=True)
        for long_p, short_p in zip(sorted_puts, sorted_puts[1:]):
            width = long_p['strike'] - short_p['strike']
            if width <= 0 or width > max_width_dollars:
                continue
            sp = M.vertical_debit(chain['puts'], chain['calls'], 'PUT',
                                  long_strike=long_p['strike'], short_strike=short_p['strike'])
            if sp is None:
                continue
            edge = M.premium_edge(sp)
            pop = sp.get('pop_estimate')
            if pop is None or pop < MIN_POP:
                record['rejections'].append(f'PUT debit {short_p["strike"]}/{long_p["strike"]} POP={pop} below {MIN_POP}')
                continue
            if edge is None or edge < MIN_EDGE:
                record['rejections'].append(f'PUT debit {short_p["strike"]}/{long_p["strike"]} edge={edge} below {MIN_EDGE}')
                continue
            candidates.append({**sp, 'side_label': 'bear_put_spread', 'edge': safe_round(edge, 4),
                               'liquidity_score': (long_p.get('open_interest', 0) + short_p.get('open_interest', 0)),
                               'pop': pop})

        # put_credit (vertical_credit put): short higher put, long lower put
        sorted_puts_asc = sorted(puts_survivors, key=lambda r: r['strike'])
        for short_p, long_p in zip(sorted_puts_asc, sorted_puts_asc[1:]):
            width = short_p['strike'] - long_p['strike']
            if width <= 0 or width > max_width_dollars:
                continue
            sp = M.vertical_credit(chain['calls'], chain['puts'], 'PUT',
                                   short_strike=short_p['strike'], long_strike=long_p['strike'])
            if sp is None:
                continue
            edge = M.premium_edge(sp)
            pop = sp.get('pop_estimate')
            if pop is None or pop < MIN_POP:
                record['rejections'].append(f'PUT credit {short_p["strike"]}/{long_p["strike"]} POP={pop} below {MIN_POP}')
                continue
            if edge is None or edge < MIN_EDGE:
                record['rejections'].append(f'PUT credit {short_p["strike"]}/{long_p["strike"]} edge={edge} below {MIN_EDGE}')
                continue
            candidates.append({**sp, 'side_label': 'put_credit_spread', 'edge': safe_round(edge, 4),
                               'liquidity_score': (short_p.get('open_interest', 0) + long_p.get('open_interest', 0)),
                               'pop': pop})

        # call_credit: short lower call, long higher call (downside bullish)
        # Note: v1 strategy menu includes vertical_credit generically.
        # For bull-call-credit we'd short a lower call + long a higher call (this is a bearish call-credit),
        # but the more idiomatic call-credit is bear_call_spread (short lower, long higher).
        # Per v1 menu: vertical_credit = either put credit OR call credit.
        # Bear call credit: short the lower call, long the higher call. Net = credit.
        sorted_calls_asc = sorted(calls_survivors, key=lambda r: r['strike'])
        for short_c, long_c in zip(sorted_calls_asc, sorted_calls_asc[1:]):
            width = long_c['strike'] - short_c['strike']
            if width <= 0 or width > max_width_dollars:
                continue
            sp = M.vertical_credit(chain['calls'], chain['puts'], 'CALL',
                                   short_strike=short_c['strike'], long_strike=long_c['strike'])
            if sp is None:
                continue
            edge = M.premium_edge(sp)
            pop = sp.get('pop_estimate')
            if pop is None or pop < MIN_POP:
                record['rejections'].append(f'CALL credit {short_c["strike"]}/{long_c["strike"]} POP={pop} below {MIN_POP}')
                continue
            if edge is None or edge < MIN_EDGE:
                record['rejections'].append(f'CALL credit {short_c["strike"]}/{long_c["strike"]} edge={edge} below {MIN_EDGE}')
                continue
            candidates.append({**sp, 'side_label': 'call_credit_spread', 'edge': safe_round(edge, 4),
                               'liquidity_score': (short_c.get('open_interest', 0) + long_c.get('open_interest', 0)),
                               'pop': pop})

    # Score: edge first, then liquidity_score as tie-breaker
    candidates.sort(key=lambda c: (c['edge'], c['liquidity_score']), reverse=True)
    candidates = candidates[:N_CANDIDATES_TARGET]

    # Mike 2026-08-31 12:16 ET directive: cap each position max_loss <= $1,000 total.
    # This means max_loss_per_contract * 100 * contracts <= $1,000.
    # Practical: size to contracts = floor(1000 / (max_loss_per_contract * 100)).
    # Candidates where even 1 contract exceeds $1,000 are excluded.
    candidates = [c for c in candidates if c.get('max_loss', 999) * 100 <= 1000]
    # Also exclude penny-debit structures (max_loss <= $0.10/ct) — these are unrealistic
    # candidates where the "EV" comes from squeezing pennies, not real edge.
    candidates = [c for c in candidates if c.get('max_loss', 999) >= 0.10]
    # Cap contracts at 50 max per trade (sanity check; even at $20/ct max loss, 50 ct = $1k cap)
    # Add position-sizing info
    for c in candidates:
        max_loss_ct = c.get('max_loss', 0) * 100
        contracts = max(1, min(50, int(1000 / max_loss_ct))) if max_loss_ct > 0 else 0
        c['position_sizing'] = {
            'contracts': contracts,
            'max_loss_per_contract': round(max_loss_ct, 2),
            'position_max_loss': round(contracts * max_loss_ct, 2),
            'position_max_gain': round(contracts * c.get('max_gain', 0) * 100, 2),
            'position_ev': round(contracts * (c.get('pop', 0) * c.get('max_gain', 0) - (1 - c.get('pop', 0)) * c.get('max_loss', 0)) * 100, 2),
        }
    # Strip out very large row dicts for the report; keep essentials.
    surfaced = []
    for c in candidates:
        surfaced.append({
            'side_label': c['side_label'],
            'legs': [{k: v for k, v in leg.items() if k not in ('short_row', 'long_row')} for leg in c['legs']],
            'credit_or_debit': c.get('credit') if c.get('credit') is not None else c.get('debit'),
            'width': c.get('width'),
            'max_loss': c.get('max_loss'),
            'max_gain': c.get('max_gain'),
            'breakeven': c.get('breakeven'),
            'pop': c.get('pop'),
            'edge': c.get('edge'),
            'liquidity_score_sum_oi': c.get('liquidity_score'),
            'deltas': c.get('deltas'),
            'position_sizing': c.get('position_sizing', {}),
        })
    record['candidates'] = surfaced

    # ---- Butterfly scan (Mike preference) ----
    # Bullish: long call butterfly with body ABOVE spot
    # Bearish: long put butterfly with body BELOW spot
    butterflies = []
    for side in ('CALL', 'PUT'):
        flies = M.butterfly_candidates(chain['calls'], chain['puts'], spot, side,
                                       wing_pct=0.05, dte=dte)
        for f in flies:
            pop = f.get('pop_estimate', 0)
            edge = M.premium_edge(f)
            if pop < MIN_POP or (edge is None) or edge < MIN_EDGE:
                continue
            ev = pop * f['max_gain'] - (1 - pop) * f['max_loss']
            butterflies.append({
                'kind': f['kind'],
                'legs': f['legs'],
                'debit': f['debit'],
                'wing_width': f['wing_width'],
                'max_loss': f['max_loss'],
                'max_gain': f['max_gain'],
                'breakeven_lower': f['breakeven_lower'],
                'breakeven_upper': f.get('breakeven_upper'),
                'pin_strike': f['pin_strike'],
                'pop_estimate': pop,
                'edge': edge,
                'ev_per_share': round(ev, 4),
                'ev_per_contract': round(ev * 100, 2),
            })
    # Sort butterflies by EV per contract
    butterflies.sort(key=lambda b: b.get('ev_per_contract', -9999), reverse=True)
    butterflies = butterflies[:2]  # cap at 2 butterflies per symbol
    # Mike 2026-08-31 12:16 ET directive: cap each position max_loss <= $1,000 total.
    butterflies = [b for b in butterflies if b.get('max_loss', 999) * 100 <= 1000]
    # Same penny-debit filter as verticals
    butterflies = [b for b in butterflies if b.get('max_loss', 0) >= 0.50]
    for b in butterflies:
        max_loss_ct = b.get('max_loss', 0) * 100
        contracts = max(1, min(50, int(1000 / max_loss_ct))) if max_loss_ct > 0 else 0
        b['position_sizing'] = {
            'contracts': contracts,
            'max_loss_per_contract': round(max_loss_ct, 2),
            'position_max_loss': round(contracts * max_loss_ct, 2),
            'position_max_gain': round(contracts * b.get('wing_width', 0) * 100, 2),  # max gain at pin
            'position_ev': round(contracts * b.get('ev_per_contract', 0), 2),
        }
    record['butterflies'] = butterflies

    record['status'] = 'ok'
    return record


def main():
    scan_start = datetime.datetime.now().astimezone()
    # Tier-1 resolves through proxies; Tier-2 scanned directly. Dedupe so SPY isn't scanned twice.
    proxy_resolved = list(PROXY_MAPPING.values())
    direct_etfs = EFFECTIVE_ETFS
    # Effective scan set = union of (proxied Tier-1) ∪ (direct Tier-2) ∪ (Tier-3 stocks), preserving order
    scan_set = list(dict.fromkeys(proxy_resolved + direct_etfs + EFFECTIVE_STOCKS))
    symbols = scan_set
    results = []
    for sym in symbols:
        tier = TIER_OF.get(sym, 'etf')
        results.append(scan_one(sym, tier))
    out = {
        'scan_started_iso': scan_start.isoformat(),
        'scan_finished_iso': datetime.datetime.now().astimezone().isoformat(),
        'risk_mode': RISK_MODE,
        'proxy_mapping_active': True,
        'proxy_mapping_detail': PROXY_MAPPING,
        'rules_in_effect': {
            'DTE_window': [DTE_MIN, DTE_MAX],
            'min_pop': MIN_POP,
            'min_edge': MIN_EDGE,
            'max_width_pct_of_spot': 0.05,
            'liquidity_tiers': {'index_min_oi': 500, 'etf_min_oi': 500, 'stock_min_oi': 100},
            'strategy_menu_normal': ['bull_call_spread', 'bear_put_spread', 'vertical_credit'],
        },
        'universe_size': len(symbols),
        'results': results,
    }
    # Regime check via VIX (per risk_mode.yaml#auto_suggest_triggers)
    try:
        vix = vix_mod.get_vix_now()
        if vix:
            rc = vix_mod.regime_classifier(vix['last'])
            out['vix'] = vix
            out['regime'] = rc
            if rc['auto_suggest_mode']:
                out['auto_suggest'] = f"VIX {vix['last']} → suggested mode: {rc['auto_suggest_mode']} (pending Mike approval per governance)"
    except Exception as e:
        out['vix_error'] = str(e)

    # ---- σ-band tables (Mike 2026-08-31 11:59 ET: 'price targets for week/month/quarter/year, include std and %') ----
    # Use annualized IV from each underlying's ATM straddle to compute σ bands for various tenors.
    # These are math outputs (not price targets / forecasts). The market is pricing these moves.
    tenors = {
        '1W': 5,
        '1M': 21,
        '1Q': 63,
        '1Y': 252,
    }
    sigma_table = []
    for r in out['results']:
        if r.get('status') != 'ok':
            continue
        em = r.get('expected_move', {})
        iv = em.get('iv_annualized')
        spot = r.get('spot')
        if not iv or not spot:
            continue
        row = {
            'symbol': r['symbol'],
            'proxy_origin': r.get('proxy_origin'),
            'spot': spot,
            'iv_annualized': iv,
        }
        for tenor_name, dte in tenors.items():
            move_1sigma = spot * iv * (dte / 252.0) ** 0.5
            row[f'{tenor_name}_move_dollars_1sigma'] = round(move_1sigma, 2)
            row[f'{tenor_name}_move_pct_1sigma'] = round((move_1sigma / spot) * 100, 2)
            row[f'{tenor_name}_band_low'] = round(spot - move_1sigma, 2)
            row[f'{tenor_name}_band_high'] = round(spot + move_1sigma, 2)
            # 2σ band (≈95% probability over the period assuming normality)
            move_2sigma = move_1sigma * 2
            row[f'{tenor_name}_band_low_2sigma'] = round(spot - move_2sigma, 2)
            row[f'{tenor_name}_band_high_2sigma'] = round(spot + move_2sigma, 2)
        sigma_table.append(row)
    out['sigma_bands'] = sigma_table

    # Summary stats for the run
    out['summary'] = {
        'symbols_scanned': len(results),
        'symbols_failed': sum(1 for r in results if r['status'] == 'failed'),
        'symbols_skipped': sum(1 for r in results if r['status'] == 'skipped'),
        'symbols_ok': sum(1 for r in results if r['status'] == 'ok'),
        'total_vertical_candidates': sum(len(r['candidates']) for r in results),
        'total_butterfly_candidates': sum(len(r.get('butterflies', [])) for r in results),
        'positive_ev_verticals': sum(1 for r in results for c in r['candidates']
                                      if (c['pop'] * c['max_gain'] - (1 - c['pop']) * c['max_loss']) > 0),
        'positive_ev_butterflies': sum(1 for r in results for b in r.get('butterflies', [])
                                        if b.get('ev_per_share', 0) > 0),
    }
    out_path = Path('/Users/mike/.openclaw/workspace-bacottibot/entities/dependability/quant/data/scan_2026-08-31.json')
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"wrote scan to {out_path}")
    print(json.dumps({
        'symbols_scanned': len(results),
        'symbols_failed': sum(1 for r in results if r['status'] == 'failed'),
        'symbols_skipped': sum(1 for r in results if r['status'] == 'skipped'),
        'total_candidates': sum(len(r['candidates']) for r in results),
        'total_rejections': sum(len(r['rejections']) for r in results),
    }, indent=2))


if __name__ == '__main__':
    main()
