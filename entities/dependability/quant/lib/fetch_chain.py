"""fetch_chain.py — pull option chain for one symbol via Public.com SDK.

Returns structured contract rows (both legs: calls + puts) as a Python list.
Filtering for liquidity / IV / DTE is downstream — this helper is pure transport.

Anti-pattern guard (doctrine #1): every field comes from the SDK response,
no fabricated values.

Stdlib + venv-only deps (public_api_sdk).
"""
from pathlib import Path
import sys
import os
sys.path.insert(0, str(Path(__file__).parent))
from _env import load_env

from public_api_sdk import (
    PublicApiClient,
    ApiKeyAuthConfig,
    OptionChainRequest,
    OptionExpirationsRequest,
    OrderInstrument,
    InstrumentType,
)


def parse_strike_from_osi(osi_symbol: str) -> int:
    """Parse strike from OSI like 'SPY260925C00500000' → 50000.
    Last 8 chars: 'C00500000' or 'P00500000' = (side)(strike * 1000, zero-padded).
    Multiply-by-1000 because OSI encodes strike in 1/1000ths.
    """
    s = osi_symbol.rstrip()
    return int(s[-8:]) // 1000


def parse_expiry_from_osi(osi_symbol: str) -> str:
    """Parse expiry from OSI 'SPY260925C00500000' → '2026-09-25'.
    Chars 3-9 are YYMMDD.
    """
    yymmdd = osi_symbol[3:9]
    return f"20{yymmdd[0:2]}-{yymmdd[2:4]}-{yymmdd[4:6]}"


def fetch_expirations(symbol: str) -> list[str]:
    """Return sorted list of ISO dates the chain supports for `symbol`."""
    load_env()
    client = PublicApiClient(auth_config=ApiKeyAuthConfig(api_secret_key=os.environ['PUBLIC_COM_SECRET']))
    req = OptionExpirationsRequest(instrument=OrderInstrument(symbol=symbol, type=InstrumentType.EQUITY))
    resp = client.get_option_expirations(
        expirations_request=req,
        account_id=os.environ['PUBLIC_COM_ACCOUNT_ID']
    )
    return sorted(resp.expirations)


def fetch_chain(symbol: str, expiration_date: str) -> dict:
    """Return dict with keys: symbol, expiration, calls, puts.
    Each call/put row is a dict with: side (CALL/PUT), strike (int),
    bid, ask, mid, bid_size, ask_size, last, volume, open_interest,
    delta, gamma, theta, vega, prev_close (if any).

    Symbols with OSI = OptionType ETO ; their greeks come back as Decimal.
    Bid/ask sizes >0. We do NOT call preflight/place_* — research-only.
    """
    load_env()
    client = PublicApiClient(auth_config=ApiKeyAuthConfig(api_secret_key=os.environ['PUBLIC_COM_SECRET']))
    acct = os.environ['PUBLIC_COM_ACCOUNT_ID']

    req = OptionChainRequest(
        instrument=OrderInstrument(symbol=symbol, type=InstrumentType.EQUITY),
        expiration_date=expiration_date,
    )
    resp = client.get_option_chain(option_chain_request=req, account_id=acct)

    def row(side: str, q):
        bid = float(q.bid) if q.bid is not None else None
        ask = float(q.ask) if q.ask is not None else None
        mid = (bid + ask) / 2 if (bid is not None and ask is not None) else None
        last = float(q.last) if q.last is not None else None
        prev_close = float(q.previous_close) if q.previous_close is not None else None
        # greeks: OptionType Greeks object; defensively handle
        delta = gamma = theta = vega = None
        if q.option_details is not None and q.option_details.greeks is not None:
            g = q.option_details.greeks
            delta = float(g.delta) if g.delta is not None else None
            gamma = float(g.gamma) if g.gamma is not None else None
            theta = float(g.theta) if g.theta is not None else None
            vega = float(g.vega) if g.vega is not None else None
        return {
            'side': side,
            'osi': str(q.instrument.symbol).strip(),
            'strike': parse_strike_from_osi(str(q.instrument.symbol)),
            'expiry': parse_expiry_from_osi(str(q.instrument.symbol)),
            'bid': bid,
            'ask': ask,
            'mid': mid,
            'bid_size': q.bid_size if q.bid_size is not None else 0,
            'ask_size': q.ask_size if q.ask_size is not None else 0,
            'last': last,
            'last_timestamp': q.last_timestamp.isoformat() if q.last_timestamp else None,
            'volume': q.volume if q.volume is not None else 0,
            'open_interest': q.open_interest if q.open_interest is not None else 0,
            'prev_close': prev_close,
            'delta': delta,
            'gamma': gamma,
            'theta': theta,
            'vega': vega,
            'bid_ts': q.bid_timestamp.isoformat() if q.bid_timestamp else None,
            'ask_ts': q.ask_timestamp.isoformat() if q.ask_timestamp else None,
        }

    calls = [row('CALL', q) for q in resp.calls]
    puts = [row('PUT', q) for q in resp.puts]
    return {
        'symbol': symbol,
        'expiration': expiration_date,
        'calls': calls,
        'puts': puts,
        'fetched_at': __import__('datetime').datetime.now().astimezone().isoformat(),
    }


if __name__ == '__main__':
    # Smoke print: just count rows. Run from a session that has sourced the env.
    import json
    sym = sys.argv[1] if len(sys.argv) > 1 else 'SPY'
    exp = sys.argv[2] if len(sys.argv) > 2 else None
    if exp is None:
        exps = fetch_expirations(sym)
        print(f"{sym} has {len(exps)} expirations: {exps[0]} .. {exps[-1]}")
        exp = exps[20] if len(exps) > 20 else exps[0]
        print(f"Using expiration: {exp}")
    chain = fetch_chain(sym, exp)
    print(f"calls={len(chain['calls'])}, puts={len(chain['puts'])}")
    print(f"sample call row: {json.dumps(chain['calls'][len(chain['calls'])//2], indent=2, default=str)}")
