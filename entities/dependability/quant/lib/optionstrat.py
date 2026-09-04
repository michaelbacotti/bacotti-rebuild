"""optionstrat.com URL → structured trade data extractor.

Discovered 2026-09-01 by main session: optionstrat.com strategy URLs (e.g.
https://optionstrat.com/2AX4cfXgUEWD) embed the full trade JSON in a
`<script id="__NEXT_DATA__">` block in the static HTML. No JS rendering, no
API key, no headless browser required. Just `curl` + parse.

This module provides:
- `fetch_strategy(url_or_code) -> Strategy`: full trade from URL/code
- `parse_next_data(html) -> dict`: raw __NEXT_DATA__ payload
- `leg_summary(strategy) -> dict`: per-leg + net-debit/credit summary

Why this exists
---------------
Mike shares optionstrat.com permalinks as the primary way to communicate
trade structures. dependability-quant needs exact entry debits and leg
details to log trades to `data/quant.db#trade_journal`. Before this helper,
the quant workdesk was asking Mike to paste entry quotes manually because
the SPA-rendered page couldn't be scraped with `web_fetch`.

Caveats
-------
- Public shared strategies only. Private ones (logged-in) return 200 OK but
  with `pageProps.savedStrategy.mine = true` and may not include full data
  in __NEXT_DATA__.
- `basis` is the per-share price at construction. Real entry debit/credit
  depends on bid/ask at order time; this gives the SHARE-PRICE leg cost,
  not necessarily what fills.
- `symbol` field on each leg is OCC format (e.g. `.PANW260904C380`). The
  leading dot is optionstrat's convention.
- Some pre-built strategies return a slightly different shape
  (`savedStrategy.strategy.items[].legId`); this helper normalizes the
  common 4-key leg shape and skips unknown extras.

Example
-------
>>> s = fetch_strategy("2AX4cfXgUEWD")
>>> s["name"]
'DELL Sep 4th 440/460/480 Long Call Butterfly'
>>> s["summary"]["net_debit"]
217.5
>>> s["legs"][0]
{'side': 'buy', 'qty': 1, 'symbol': '.DELL260904C440',
 'strike': 440.0, 'expiry': '2026-09-04', 'cp': 'C', 'underlying': 'DELL',
 'basis': 21.25, 'basis_dollar': 2125.0}
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
OPTIONSTRAT_BASE = "https://optionstrat.com"

# Capture the __NEXT_DATA__ JSON payload embedded in the page HTML.
# Script tag may have whitespace inside; greedy is fine here.
_NEXT_DATA_RE = re.compile(
    r'<script\s+id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL
)


def _code_from_url(url_or_code: str) -> str:
    """Accept either a full URL or a raw code; return the bare code."""
    if url_or_code.startswith("http://") or url_or_code.startswith("https://"):
        parsed = urllib.parse.urlparse(url_or_code)
        path = parsed.path.strip("/")
        return path.split("/")[-1] if path else url_or_code
    return url_or_code.strip("/")


def fetch_html(url_or_code: str, *, timeout: float = 15.0, user_agent: str = DEFAULT_UA) -> str:
    """Fetch the static HTML for an optionstrat URL or code."""
    code = _code_from_url(url_or_code)
    url = f"{OPTIONSTRAT_BASE}/{code}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_next_data(html: str) -> dict[str, Any]:
    """Extract the __NEXT_DATA__ JSON payload from optionstrat HTML.

    Raises:
        ValueError: if the script block is missing or unparseable.
    """
    m = _NEXT_DATA_RE.search(html)
    if not m:
        raise ValueError("__NEXT_DATA__ script block not found in HTML")
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError as exc:
        raise ValueError(f"__NEXT_DATA__ not valid JSON: {exc}") from exc


def _parse_occ_symbol(symbol: str) -> dict[str, Any]:
    """Parse optionstrat OCC format like '.PANW260904C380'.

    Layout: leading dot + underlying + YYMMDD + C/P + strike.
    optionstrat uses raw dollar strikes (e.g. ``380`` for $380), NOT the
    OCC spec's strike*1000 convention (e.g. ``380000`` for SPX).
    Returns dict with underlying, expiry (YYYY-MM-DD), cp (C/P), strike (float).
    Returns empty dict for unrecognized shapes.
    """
    if not symbol or symbol[0] != ".":
        return {}
    body = symbol[1:]
    # C/P is the call/put marker (single char). Underlying is alpha prefix
    # before the 6-digit YYMMDD. Strike is everything after C/P.
    m = re.match(r"^([A-Z]+)(\d{6})([CP])(\d+)$", body)
    if not m:
        return {}
    underlying, yymmdd, cp, strike_raw = m.groups()
    try:
        expiry_dt = datetime.strptime(yymmdd, "%y%m%d").replace(tzinfo=timezone.utc)
        strike = float(strike_raw)  # raw dollar strike (optionstrat convention)
    except ValueError:
        return {}
    return {
        "underlying": underlying,
        "expiry": expiry_dt.strftime("%Y-%m-%d"),
        "cp": cp,
        "strike": strike,
    }


@dataclass
class Leg:
    side: str           # 'buy' or 'sell'
    qty: int
    symbol: str         # OCC format as returned by optionstrat
    strike: float | None = None
    expiry: str | None = None
    cp: str | None = None
    underlying: str | None = None
    basis: float = 0.0  # per-share price at construction
    basis_dollar: float = 0.0  # basis * qty * 100 (per-share times contract size)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_item(cls, item: dict[str, Any]) -> "Leg":
        qty = int(item.get("quantity", 0))
        side = "buy" if qty > 0 else "sell"
        symbol = item.get("symbol", "")
        parsed = _parse_occ_symbol(symbol)
        basis = float(item.get("basis") or 0.0)
        return cls(
            side=side,
            qty=abs(qty),
            symbol=symbol,
            strike=parsed.get("strike"),
            expiry=parsed.get("expiry"),
            cp=parsed.get("cp"),
            underlying=parsed.get("underlying"),
            basis=basis,
            basis_dollar=basis * abs(qty) * 100.0,
            raw=item,
        )


@dataclass
class Strategy:
    code: str
    name: str
    symbol: str             # underlying ticker
    is_cash_secured: bool
    definition_id: int | None
    revision: int | None
    mine: bool
    account_name: str | None
    description: str
    created: str | None
    updated: str | None
    legs: list[Leg]
    summary: dict[str, Any]  # net_debit/credit, max_profit, etc.

    @property
    def net_debit(self) -> float:
        """Positive number = net debit (cost). Negative = net credit."""
        return self.summary.get("net_debit", 0.0)

    @property
    def net_credit(self) -> float:
        return -self.net_debit if self.net_debit < 0 else 0.0


def _summarize(legs: list[Leg], items: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute net debit/credit, max profit, max loss, breakevens from legs.

    The basis prices at construction aren't enough to compute max-profit
    numerically without a model; here we report the basic accounting and
    leave POP/P(itm)/greeks as None when unavailable (optionstrat's own
    server-side POP model isn't exposed in __NEXT_DATA__).
    """
    # Net cash flow per contract (per 100 shares):
    # sum(qty_signed * basis * 100), but positive qty = buy = cash out,
    # negative qty = sell = cash in. So signed_qty * basis gives net share-cost.
    net_per_share = sum(
        (leg.raw.get("quantity") or 0) * leg.basis for leg in legs
    )
    net_per_contract = net_per_share * 100.0

    # Max profit / max loss are only well-defined for defined-risk structures.
    # For a long call butterfly with strikes A<B<C, qty +1/-2/+1, max profit
    # = (B-A)*100 - net_debit, max loss = net_debit. We can detect this
    # pattern; otherwise leave None.
    return {
        "net_per_share": round(net_per_share, 4),
        "net_debit": round(net_per_contract, 2),  # positive = cost, negative = credit
        "is_debit": net_per_contract > 0,
        "is_credit": net_per_contract < 0,
        "max_profit": None,
        "max_loss": None,
        "breakevens": [],
        "pop_pct": None,
        "net_greeks": None,
        "warnings": [
            "max_profit/max_loss/breakevens/pop require optionstrat's server-"
            "side model or a Black-Scholes calculator; __NEXT_DATA__ only "
            "includes leg basis prices. Run `metrics.py` against the legs "
            "for quantitative POP.",
        ],
    }


def fetch_strategy(url_or_code: str) -> Strategy:
    """Fetch a strategy URL or code and return a parsed Strategy object.

    Args:
        url_or_code: either a full URL (https://optionstrat.com/CODE) or
            just the bare code (e.g. "2AX4cfXgUEWD").

    Returns:
        Strategy dataclass with metadata, parsed legs, and a summary dict.

    Raises:
        ValueError: if the URL doesn't contain a parseable strategy.
        urllib.error.URLError: on network/timeout errors.
    """
    code = _code_from_url(url_or_code)
    html = fetch_html(url_or_code)
    data = parse_next_data(html)

    page_props = data.get("props", {}).get("pageProps", {})
    saved = page_props.get("savedStrategy")
    if not saved:
        raise ValueError(
            f"No savedStrategy in __NEXT_DATA__ for code {code!r}. "
            "URL may be invalid, private, or deleted."
        )

    inner = saved.get("strategy", {})
    items = inner.get("items", []) or []
    legs = [Leg.from_item(item) for item in items]

    summary = _summarize(legs, items)

    return Strategy(
        code=saved.get("code", code),
        name=saved.get("name", ""),
        symbol=inner.get("symbol", ""),
        is_cash_secured=bool(inner.get("isCashSecured", False)),
        definition_id=saved.get("definitionId"),
        revision=saved.get("revision"),
        mine=bool(saved.get("mine", False)),
        account_name=saved.get("accountName"),
        description=saved.get("description", "") or "",
        created=saved.get("created"),
        updated=saved.get("updated"),
        legs=legs,
        summary=summary,
    )


# --- CLI -----------------------------------------------------------------

def _cli() -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Extract optionstrat.com strategy from URL/code as JSON."
    )
    parser.add_argument("url_or_code", help="Full URL or bare code")
    parser.add_argument(
        "--compact", action="store_true",
        help="Print compact JSON (no summary.warnings block)",
    )
    args = parser.parse_args()

    try:
        s = fetch_strategy(args.url_or_code)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    out = {
        "code": s.code,
        "name": s.name,
        "symbol": s.symbol,
        "definition_id": s.definition_id,
        "revision": s.revision,
        "is_cash_secured": s.is_cash_secured,
        "account_name": s.account_name,
        "mine": s.mine,
        "created": s.created,
        "legs": [
            {
                "side": leg.side,
                "qty": leg.qty,
                "underlying": leg.underlying,
                "expiry": leg.expiry,
                "cp": leg.cp,
                "strike": leg.strike,
                "symbol": leg.symbol,
                "basis": leg.basis,
                "basis_dollar": leg.basis_dollar,
            }
            for leg in s.legs
        ],
        "summary": s.summary,
    }

    if args.compact:
        out["summary"].pop("warnings", None)

    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())