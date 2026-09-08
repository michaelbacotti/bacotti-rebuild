#!/usr/bin/env python3
"""universe_loader.py — Load the scored universe from config + cached metadata.

Maps every ticker in the universe to a sector ETF via GICS sector name lookup.
For non-S&P-500 tickers, fetches sector from yfinance .info and caches for 30 days.

Public API:
    load_universe() -> (universe_list, sector_map, sector_groups)
    load_sector_meta(ticker) -> (sector_etf, sector_name) | None
    get_cached_info(ticker, ttl_days=7) -> dict  # cached yfinance .info()
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional, Tuple

import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "universe.json"
CACHE_DIR = ROOT / "data" / "cache"
SECTOR_CACHE = CACHE_DIR / "sectors"
INFO_CACHE = CACHE_DIR / "info"

# GICS Sector name -> Sector ETF
SECTOR_NAME_TO_ETF = {
    "Information Technology": "XLK",
    "Health Care": "XLV",
    "Financials": "XLF",
    "Consumer Discretionary": "XLY",
    "Communication Services": "XLC",
    "Industrials": "XLI",
    "Consumer Staples": "XLP",
    "Energy": "XLE",
    "Utilities": "XLU",
    "Materials": "XLB",
    "Real Estate": "XLRE",
}

SECTOR_GROUP = {
    "XLB": "Materials", "XLC": "Comm Services", "XLE": "Energy", "XLF": "Financials",
    "XLI": "Industrials", "XLK": "Technology", "XLP": "Consumer Staples",
    "XLRE": "Real Estate", "XLU": "Utilities", "XLV": "Health Care", "XLY": "Consumer Disc.",
}

ETF_TO_SECTOR_NAME = {v: k for k, v in SECTOR_NAME_TO_ETF.items()}


def _ensure_dirs():
    for d in (SECTOR_CACHE, INFO_CACHE):
        d.mkdir(parents=True, exist_ok=True)


def _cache_path(cache_dir: Path, key: str) -> Path:
    safe = key.replace("/", "_").replace(".", "_").upper()
    return cache_dir / f"{safe}.json"


def load_sector_meta(ticker: str, use_cache: bool = True, max_age_days: int = 30) -> Optional[Tuple[str, str]]:
    """Return (sector_etf, sector_name) for a ticker, or None if unknown.

    Uses GICS sector for S&P 500 tickers (from config/universe.json sp500_meta).
    For others, fetches from yfinance .info['sector'] and caches for max_age_days.
    """
    _ensure_dirs()
    ticker = ticker.upper()
    cache_file = _cache_path(SECTOR_CACHE, ticker)

    # 1. Check S&P 500 metadata first (always available, no fetch)
    cfg_path = CONFIG_PATH
    if cfg_path.exists():
        cfg = json.loads(cfg_path.read_text())
        meta = cfg.get("sp500_meta", {}).get(ticker)
        if meta and meta.get("sector"):
            sector_name = meta["sector"]
            etf = SECTOR_NAME_TO_ETF.get(sector_name)
            if etf:
                # Write to cache for future fast lookups
                try:
                    cache_file.write_text(json.dumps({
                        "ticker": ticker,
                        "sector_name": sector_name,
                        "sector_etf": etf,
                        "as_of": time.time(),
                    }))
                except Exception:
                    pass
                return (etf, sector_name)

    # 2. Cache check
    cache_file = _cache_path(SECTOR_CACHE, ticker)
    if use_cache and cache_file.exists():
        try:
            age_days = (time.time() - cache_file.stat().st_mtime) / 86400
            if age_days < max_age_days:
                data = json.loads(cache_file.read_text())
                sector_name = data.get("sector_name")
                etf = data.get("sector_etf")
                if etf and sector_name:
                    return (etf, sector_name)
        except Exception:
            pass

    # 3. Fetch from yfinance
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        sector_name = info.get("sector")
        if not sector_name:
            return None
        etf = SECTOR_NAME_TO_ETF.get(sector_name)
        if not etf:
            return None
        cache_file.write_text(json.dumps({
            "ticker": ticker,
            "sector_name": sector_name,
            "sector_etf": etf,
            "as_of": time.time(),
        }))
        return (etf, sector_name)
    except Exception:
        return None


def get_cached_info(ticker: str, ttl_days: int = 7) -> dict:
    """Return yfinance .info dict, cached for ttl_days."""
    _ensure_dirs()
    ticker = ticker.upper()
    cache_file = _cache_path(INFO_CACHE, ticker)
    if cache_file.exists():
        try:
            age_days = (time.time() - cache_file.stat().st_mtime) / 86400
            if age_days < ttl_days:
                return json.loads(cache_file.read_text())
        except Exception:
            pass
    # Fetch fresh
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        info = {}
    try:
        cache_file.write_text(json.dumps(info, default=str))
    except Exception:
        pass
    return info


def load_universe(verbose: bool = True) -> Tuple[list, dict, dict]:
    """Load the full universe from config/universe.json.

    Returns:
        universe_list: [(ticker, sector_etf, sector_name), ...] sorted by (sector, ticker)
        sector_map: {ticker: (sector_etf, sector_name)}
        sector_groups: {sector_name: [ticker, ...]}
    """
    _ensure_dirs()
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Universe config not found: {CONFIG_PATH}")

    cfg = json.loads(CONFIG_PATH.read_text())
    sp500 = cfg.get("core", {}).get("sp500", [])
    nd100 = cfg.get("core", {}).get("nasdaq100", [])

    all_tickers = sorted(set(sp500) | set(nd100))
    if verbose:
        print(f"Universe: {len(sp500)} SP500 + {len(nd100)} NDX ({len(all_tickers)} unique)", flush=True)

    sector_map = {}
    sector_groups = {}

    n_fetched = 0
    n_sp500_meta = 0
    for ticker in all_tickers:
        meta = load_sector_meta(ticker)
        if not meta:
            continue
        etf, sector_name = meta
        sector_map[ticker] = (etf, sector_name)
        sector_groups.setdefault(sector_name, []).append(ticker)
        if ticker in cfg.get("sp500_meta", {}):
            n_sp500_meta += 1
        else:
            n_fetched += 1

    if verbose:
        print(f"  Sectors mapped: {len(sector_map)} ({n_sp500_meta} from SP500 meta, {n_fetched} via yfinance)", flush=True)
        for sec_name in sorted(sector_groups.keys()):
            print(f"    {sec_name:25s}: {len(sector_groups[sec_name]):3d}", flush=True)

    universe_list = [(t, sector_map[t][0], sector_map[t][1]) for t in sorted(sector_map.keys())]
    return universe_list, sector_map, sector_groups


if __name__ == "__main__":
    universe, smap, sgroups = load_universe(verbose=True)
    print(f"\nTotal mapped: {len(universe)}")
    print(f"Sector count: {len(sgroups)}")
