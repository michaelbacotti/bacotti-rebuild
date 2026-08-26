# Dependability XO Workdesk — Owned Files Manifest

**Owning workdesk (planned):** `agent:main:dependability-xo`
**Owning workboard board:** `entity-dependability`
**Entity:** Dependability Holdings LLC (EIN 86-2606053)
**Domain:** NOT a website. This is the executive officer workdesk for the entity's business operations.
**Quicken live source:** `~/Library/Application Support/Quicken/Documents/All Books.quicken` — account 5 (Schwab X652)

**Created:** 2026-08-26
**Status:** workdesk session NOT YET CONFIGURED at gateway level.

## Files you own (business / accounting layer)

### Entity bookkeeping
- `entities/dependability/notes/meetings/*.md` — meeting minutes (formal §704(e) protection)
- `entities/dependability/tax/*.md` — tax notes (realized gain calculations, K-1 prep)
- `entities/dependability/.forecast-data-verified.json` — verified P&L data
- `entities/dependability/.openclaw/*.json` — workdesk state files

### Cross-entity (shared with family-office-finance)
- Profit-share distributions to Bacotti Inc. (quicken acct 5 → acct 20)
- TYPE 1 GP fees ($1,000/mo)
- TYPE 2 formulaic profit share (20% × monthly realized gain)
- TYPE 3 discretionary profit advances

## Cron jobs you own

| Cron ID | Schedule | What it does |
|---|---|---|
| `fdd24d1a-d50c-4b0e-b6d3-4d590d9731c0` | 1st of month 09:00 ET | Monthly TYPE 1 GP fee to Bacotti Inc. |
| `9807bbb7-b70b-4650-bc5f-d68b2573aa92` | 28th 17:00 ET | Monthly P&L + profit-share calculation |

Both bound to ghost session `agent:main:family-office-finance` (currently falls through to main).

## Files you do NOT own

- `entities/dependability/website/` — dependability-website-manager (separate WM)
- `entities/dependability/content/` — dependability-website-manager (separate WM)
- `entities/dependability/dependability-may26/` — dependability-website-manager (separate WM)

**Important separation:** XO owns the business / accounting layer. WM owns the website layer. They are SEPARATE workdesks that should never write to each other's files.

## Bootstrap status (2026-08-26)

- [ ] Gateway agent `dependability-xo` configured
- [ ] XO priming cron created (was attempted 2026-08-25 14:18 ET but cron failed because target session didn't exist)
- [ ] XO's tools-allow profile set (filesystem + cron + workboard + memory_search + sqlite for Quicken)
- [ ] XO's first workboard card posted: "I am dependability-xo, here's my scope"
- [ ] Both Dependability cron jobs re-bound to XO session

## How to bootstrap the XO at gateway level

The OpenClaw config needs an entry like:

```toml
[agents.dependability-xo]
model = "minimax/MiniMax-M2.7"
fallbacks = ["minimax/MiniMax-M3"]
description = "Dependability Holdings LLC executive officer. Owns entities/dependability/{notes,tax}/. Reads Quicken. Does NOT touch websites or other entities' books."
```

Once configured and primed, the XO owns Dependability's business operations end-to-end. Until then, main handles Dependability bookkeeping.