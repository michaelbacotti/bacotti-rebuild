---
name: "site-code-audit"
description: "Nightly audit of all site source code + live fetches across 8 websites, with safe auto-fix. Catches GA4 tag typos, missing favicons, dead internal links, broken redirects, build script errors, cron failures. Runs as a Lobster pipeline on session:site-qa."
---

# Site Code Audit

**Created:** 2026-08-22
**Status:** Live (nightly 22:30 ET, after sitemap audit)

## What it does

Three layers of coverage, all in one nightly run:

1. **Static source scan** — every Python file in `_build/` and `skills/*/scripts/`, every HTML page on all 8 sites, `_redirects`, `manifest.json`, `wrangler.toml`, sitemap files, `.well-known/*`.
2. **Live HTTP probe** — fetches each site's apex + key URLs with a real browser UA, verifies HTTP 200 / favicon serves / GA4 tag format.
3. **Cron health check** — pulls all cron job statuses, surfaces anything errored >2 days.

Auto-fix policy is conservative: only patches where the fix is mechanical and reversible (no semantic judgment). Anything ambiguous goes to a workboard card.

## What gets auto-fixed (safe + reversible)

| Bug class | Fix |
|---|---|
| `gtag/js?id=G-G-XXXXXXXXXX` (double-G typo) | Strip the second G; commit + push |
| `<head>` missing favicon `<link>` on bacotti-style sites | Run `inject_favicon.py`; commit + push |
| Orphaned favicon PNG (no `<link>` references it) | Tracked but not auto-removed |
| Local `_redirects` references missing target | Tracked, not auto-removed |
| Broken internal `<a href>` (target 404) | Insert `<!-- broken link: ... -->` marker + file workboard card |
| Workspace `manifest.json` exists but is empty/malformed | Tracked, not auto-fixed |

## What gets REPORTED (no auto-fix)

- Cron jobs errored >2 days in a row
- HTML missing canonical / duplicate H1
- Build script import errors or hardcoded paths
- Live site returns 5xx
- Sitemap URLs return non-200
- Any HTML content change (paragraphs, headings)

## Architecture

```
cron (22:30 ET daily, session:site-qa)
    └── runs lobster pipeline: skills/site-code-audit/scripts/pipeline.py
        ├── scan_static.py      (analyzes source files)
        ├── scan_live.py        (HTTP probes)
        ├── scan_crons.py       (checks cron statuses)
        ├── fix.py              (applies safe auto-fixes)
        └── notify.py           (writes JSON + MD reports + workboard cards)
```

The persistent session (`session:site-qa`) lets the audit reference **yesterday's findings** — "this has been broken for 3 days now, escalate" — instead of starting cold each night.

## Outputs

- `memory/memory/code-audit-<date>.json` — structured findings (per-class)
- `memory/memory/code-audit-<date>.md` — human-readable summary
- `memory/.workspace-state.json` — updated `lastCodeAudit` block + `carryoverItems`
- Workboard cards for any fix-applied or escalate-needed items

## Run manually

```bash
# Full audit (scan + auto-fix + report)
python3 skills/site-code-audit/scripts/run.py

# Scan only (no fixes)
python3 skills/site-code-audit/scripts/run.py --scan-only

# Just one site
python3 skills/site-code-audit/scripts/run.py --site bacotti
```

## Reversal / safety

- Every auto-fix is one git commit. Roll back with `git revert <sha>`.
- `--scan-only` mode skips `fix.py` entirely.
- `--dry-run` shows what would be fixed without applying.
- Pipeline checkpoints in `.openclaw/tmp/code-audit-checkpoint.json` allow resume.
