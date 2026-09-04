"""
backtest_artifacts.py — Versioned artifacts for point-in-time reproducibility.

Directive (Mike 2026-09-02 18:37 ET):
  "Save versioned code, parameters, source/data timestamps, signal ledger,
   trade log, and results files."

Every backtest run produces a versioned artifact bundle:

  artifact_root/
    <run_id>/
      code_version.json       — git hash or static version + module list
      params.json              — frozen parameters used
      source_timestamps.json   — when each data source was fetched
      signal_ledger.jsonl      — one row per signal generated (with timestamp)
      trade_log.jsonl          — one row per trade entry/exit
      results.json             — summary metrics
      splits_dividends.json    — record of any adjustments applied
      delistings.json          — record of delisted symbols handled
      notes.md                 — human-readable run summary

A run is "in-sample" if params are tuned on the same data; "out-of-sample"
if params are frozen and applied to held-out data; "forward-paper" if applied
to data ≥ the latest training cutoff.

This module does not run backtests — it manages the artifact infrastructure
that other modules (pattern_backtest, forecast, paper_trading) write to.
"""
from __future__ import annotations

import json
import os
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Literal


ARTIFACT_ROOT = Path(os.path.expanduser(
    "~/.openclaw/workspace-bacottibot/entities/dependability/quant/data/backtest_runs"
))
ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)


def _sha256_short(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:12]


def new_run_id(prefix: str = "run") -> str:
    """Generate unique run ID. Format: <prefix>_<timestamp>_<hash>."""
    ts = int(time.time() * 1000)
    suffix = _sha256_short(f"{ts}-{prefix}")
    return f"{prefix}_{ts}_{suffix}"


class RunArtifact:
    """One backtest run artifact bundle."""

    def __init__(self, run_id: Optional[str] = None, run_type: Literal["in_sample", "out_of_sample", "forward_paper"] = "out_of_sample"):
        self.run_id = run_id or new_run_id()
        self.run_type = run_type
        self.run_dir = ARTIFACT_ROOT / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.created_at = time.time()
        self._written_files: List[str] = []

    def write_code_version(self, modules: Dict[str, str], static_version: str = "0.1.0") -> str:
        """Write code_version.json: which modules + versions were used."""
        payload = {
            "run_id": self.run_id,
            "static_version": static_version,
            "modules": modules,
            "written_at": self.created_at,
        }
        path = self.run_dir / "code_version.json"
        with open(path, "w") as f:
            json.dump(payload, f, indent=2)
        self._written_files.append(str(path))
        return str(path)

    def write_params(self, params: Dict[str, Any]) -> str:
        path = self.run_dir / "params.json"
        with open(path, "w") as f:
            json.dump(params, f, indent=2, default=str)
        self._written_files.append(str(path))
        return str(path)

    def write_source_timestamps(self, sources: Dict[str, str]) -> str:
        """sources: {"yfinance_AAPL": "2026-09-02T18:42:00Z", ...}"""
        payload = {
            "run_id": self.run_id,
            "sources": sources,
            "written_at": self.created_at,
        }
        path = self.run_dir / "source_timestamps.json"
        with open(path, "w") as f:
            json.dump(payload, f, indent=2)
        self._written_files.append(str(path))
        return str(path)

    def append_signal(self, signal: Dict[str, Any]) -> None:
        """Append one signal to signal_ledger.jsonl."""
        signal = dict(signal)
        signal["logged_at"] = time.time()
        path = self.run_dir / "signal_ledger.jsonl"
        with open(path, "a") as f:
            f.write(json.dumps(signal, default=str) + "\n")
        self._written_files.append(str(path))

    def append_trade(self, trade: Dict[str, Any]) -> None:
        """Append one trade entry/exit to trade_log.jsonl."""
        trade = dict(trade)
        trade["logged_at"] = time.time()
        path = self.run_dir / "trade_log.jsonl"
        with open(path, "a") as f:
            f.write(json.dumps(trade, default=str) + "\n")
        self._written_files.append(str(path))

    def write_results(self, results: Dict[str, Any]) -> str:
        path = self.run_dir / "results.json"
        with open(path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        self._written_files.append(str(path))
        return str(path)

    def write_adjustments(self, splits: List[Dict[str, Any]], dividends: List[Dict[str, Any]]) -> str:
        payload = {
            "splits": splits,
            "dividends": dividends,
            "note": "yfinance auto_adjust=True applies splits/dividends to OHLC by default",
        }
        path = self.run_dir / "splits_dividends.json"
        with open(path, "w") as f:
            json.dump(payload, f, indent=2)
        self._written_files.append(str(path))
        return str(path)

    def write_delistings(self, delistings: List[Dict[str, Any]]) -> str:
        path = self.run_dir / "delistings.json"
        with open(path, "w") as f:
            json.dump(delistings, f, indent=2)
        self._written_files.append(str(path))
        return str(path)

    def write_notes(self, notes_md: str) -> str:
        path = self.run_dir / "notes.md"
        with open(path, "w") as f:
            f.write(notes_md)
        self._written_files.append(str(path))
        return str(path)

    def summary(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "run_type": self.run_type,
            "run_dir": str(self.run_dir),
            "created_at": self.created_at,
            "files": self._written_files,
        }


def list_runs(run_type: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """List all runs (optionally filtered by type)."""
    out: List[Dict[str, Any]] = []
    if not ARTIFACT_ROOT.exists():
        return out
    for d in sorted(ARTIFACT_ROOT.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if not d.is_dir():
            continue
        params_file = d / "params.json"
        if not params_file.exists():
            continue
        try:
            with open(params_file) as f:
                params = json.load(f)
            rt = params.get("run_type", "out_of_sample")
            if run_type and rt != run_type:
                continue
            out.append({
                "run_id": d.name,
                "run_type": rt,
                "params_summary": {k: v for k, v in params.items() if k != "run_type"},
                "modified": d.stat().st_mtime,
            })
        except Exception:
            continue
        if len(out) >= limit:
            break
    return out


def load_run(run_id: str) -> Dict[str, Any]:
    """Load all artifacts from a run."""
    run_dir = ARTIFACT_ROOT / run_id
    if not run_dir.exists():
        return {"error": f"run {run_id} not found"}
    out: Dict[str, Any] = {"run_id": run_id, "files": {}}
    for f in run_dir.iterdir():
        if f.suffix == ".jsonl":
            out["files"][f.name] = f.read_text().strip().split("\n")
        elif f.suffix in (".json", ".md"):
            try:
                out["files"][f.name] = json.loads(f.read_text()) if f.suffix == ".json" else f.read_text()
            except Exception:
                out["files"][f.name] = None
    return out
