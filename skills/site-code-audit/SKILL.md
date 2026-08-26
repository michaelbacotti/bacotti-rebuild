---
name: "site-code-audit"
description: "Site audit + auto-fix + verify_published post-build gate. E-E-A-T recipe, word count, AdSense, canonical, anti-pattern #89 wipe detection. Edit-at-source doctrine."
---

# Site Code Audit

**Created:** 2026-08-22
**Last upgraded:** 2026-08-26 (workdesk-ownership note — see below)
**Status:** Live (nightly 22:30 ET, after sitemap audit)
**Owning workdesk:** `agent:main:quality-control` (locked 2026-08-26 06:39 ET). All crons invoking this skill's pipeline (`c9b3d8e2` site-code-audit-nightly + `47d92495` Nightly Sitemap Audit) are bound to the QC workdesk. Per-site website-managers do NOT run this skill's pipeline — they consume its outputs (workboard cards, daily notes, `memory/.workspace-state.json`) and own site-specific fixes.

## What it does

Three layers of coverage, all in one nightly run:

1. **Static source scan** — every Python file in `_build/` and `skills/*/scripts/`, every HTML page on all 8 sites, `_redirects`, `manifest.json`, `wrangler.toml`, sitemap files, `.well-known/*`.
2. **Live HTTP probe** — fetches each site's apex + key URLs with a real browser UA, verifies HTTP 200 / favicon serves / GA4 tag format.
3. **Cron health check** — pulls all cron job statuses, surfaces anything errored >2 days.

Plus a **post-build gate** (`verify_published.py`) that runs after every cron build and aborts on E-E-A-T / word-count / AdSense / canonical / anti-pattern #89 failures.

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

## Anti-Pattern #92: edit-at-source doctrine (standing rule)

**Rule hierarchy (locked in 2026-08-23):**

1. **NEW content** → MD source files (in `content/articles/`, `content/newsletters/`, etc.)
2. **NEW templates** → `build.py` constants (e.g. `EEAT_BLOCK`, site-wide header)
3. **NEVER edit rendered HTML** — it gets wiped on next cron rebuild

**Why this matters:** the HTML gets regenerated on every build, so any direct HTML edit will be wiped. This has caused at least 3 round-trips in past sessions (the playbook page ad-slot dup, the dup H1 on /reading-maps/, the duplicate `<ins>` blocks). The audit-and-fix workflow MUST classify each file before touching it.

**Anti-pattern #89 specifically:** Hand-edited HTML E-E-A-T gets wiped on cron rebuild. Mitigation: E-E-A-T MUST be wrapped in `<section class="eeat-block">` AND defined as a Python string constant in `build.py`. See `references/anti-patterns.md` for full anti-pattern catalog.

**Pre-flight checklist (going forward):**

```bash
# Step 1 — Before any HTML/MD edit: classify the file
python3 skills/site-code-audit/scripts/check_source.py <path>

# Step 2 — Edit at the SOURCE (MD for content, build.py for templates, HTML for hand_crafted only)

# Step 3 — Rebuild (if edit was at MD or build.py)
python3 <site>/build.py  # full rebuild

# Step 4 — Verify (after build, before deploy)
python3 skills/site-code-audit/scripts/verify_published.py --site <key> --quiet
```

**Sites with active build.py + MD sources:**

| Site | Build.py | MD source dir |
|---|---|---|
| spaceorbitals | `projects/spaceorbitals/spaceorbitals/build.py` | `projects/spaceorbitals/content/{articles,news,reviews,gear,newsletters}/*.md` |
| triadive | `projects/triadive/triadive-build/build.py` | `projects/triadive/content/{articles,pages}/*.md` |
| succession newsletters | `entities/succession/website/build.py` | `entities/succession/website/content/newsletters/*.md` |
| dependability | `entities/dependability/dependability-may26/build.py` | n/a (hand-crafted article templates in build.py) |
| bithues | `projects/bithues-crypto/bithues-build/build.py` | n/a (newsletter templates in build.py) |
| tredey | `projects/tredey/trading-journal-build/build.py` | n/a (article/forecast templates in build.py) |

**When fix_thin.py skips:** pages with `source_type=inline_static` (defined as string literals in build.py) are skipped because they require a more invasive build.py edit. Do them manually or extend fix_thin.py to handle that case.

## Post-build gate: verify_published.py (2026-08-23)

After every cron build, `verify_published.py` runs as a quality gate. Aborts deploy on:

| Check | Threshold | Source |
|---|---|---|
| Word count | FAIL <400, WARN <800, prefer 1200 | `references/quality-standards.md` |
| E-E-A-T recipe | FAIL if any of 6 sections missing | `EEAT_RECIPE` constant |
| E-E-A-T wrapper | FAIL if not in `<section class="eeat-block">` | anti-pattern #89 |
| AdSense `<ins>` | FAIL if missing on 800w+ pages | Google AdSense policy |
| Canonical URL | FAIL if missing or non-absolute | CF Pages best practice |

**Usage:**

```bash
# Single site
python3 skills/site-code-audit/scripts/verify_published.py --site bithues --quiet

# All sites
python3 skills/site-code-audit/scripts/verify_published.py

# Just check E-E-A-T recipe coverage
python3 skills/site-code-audit/scripts/verify_published.py --site triadive --check eeat
```

**Integration points:**

- `skills/autonomous-content-publishing/scripts/publish.py` — calls verify_published after build, aborts on FAIL
- `skills/autonomous-content-publishing/scripts/verify.py` — enforces word count + 5-section E-E-A-T at draft stage

**Per-site EEAT_BLOCK mapping:** see `references/quality-standards.md`.

## Architecture

```
cron (22:30 ET daily, session:site-qa)
    └── runs lobster pipeline: skills/site-code-audit/scripts/pipeline.py
        ├── scan_static.py      (analyzes source files)
        ├── scan_live.py        (HTTP probes)
        ├── scan_crons.py       (checks cron statuses)
        ├── fix.py              (applies safe auto-fixes)
        ├── notify.py           (writes JSON + MD reports + workboard cards)
        └── verify_published.py (post-build E-E-A-T / word-count / AdSense gate)

after every cron build (per-site):
    verify_published.py --site <key>
        └── aborts publish.py on FAIL
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

# Post-build gate (single site)
python3 skills/site-code-audit/scripts/verify_published.py --site bithues --quiet

# Pre-flight before HTML edit
python3 skills/site-code-audit/scripts/check_source.py <file>
```

## References

- `references/quality-standards.md` — Mike's E-E-A-T recipe, word-count policy, per-site EEAT_BLOCK mapping
- `references/anti-patterns.md` — anti-pattern #89 (HTML wipe), #92 (edit-at-source), #91 (deploy method), #93 (verify live)
- `skills/site-publishing-workflow/SKILL.md` — cron → session binding, watchdog ownership, per-site manager table

## Reversal / safety

- Every auto-fix is one git commit. Roll back with `git revert <sha>`.
- `--scan-only` mode skips `fix.py` entirely.
- `--dry-run` shows what would be fixed without applying.
- Pipeline checkpoints in `.openclaw/tmp/code-audit-checkpoint.json` allow resume.
- `verify_published.py` never modifies files — it only reports. Pass/fail drives downstream decisions.
