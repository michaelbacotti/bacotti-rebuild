---
name: site-publishing-workflow
description: Cross-site publishing doctrine — per-site ownership, cron → session binding, QC handoff. Use when binding publishing crons to sessions, when a publishing cron points at the wrong session, or when Mike asks who owns what site.
---

# Site Publishing Workflow

**Created:** 2026-08-26
**Status:** DRAFT — applies to known workdesk bootstrap gap

## Site ownership table

Each site has:
- A website-manager workdesk session (e.g., `agent:main:dependability-website-manager`) — owns source-of-truth, build scripts, MD sources, cron prompts, content fixes
- A workboard board (e.g., `website-dependability`) — owns findings about that site
- An `OWNED_FILES.md` manifest at the project/entity root

| Site | Domain | Workdesk session | Board | Manifest | Deploy method |
|---|---|---|---|---|---|
| dependability.us | Trading + market analysis | `agent:main:dependability-website-manager` | `website-dependability` | `entities/dependability/OWNED_FILES.md` | git push → `dependability-rebuild` |
| successionholdingllc.com | Succession Holding | `agent:main:succession-website-manager` | `website-succession` | `entities/succession/OWNED_FILES.md` | git push → `succession-rebuild` |
| bacotti.com | Bacotti Inc. brand | `agent:main:bacotti-inc-website-manager` | `website-bacotti-inc` | `entities/bacotti-inc/OWNED_FILES.md` | wrangler (currently broken / 403) |
| houseinc501c3.com | HOUSE Inc. 501c3 | `agent:main:house-inc-website-manager` | `website-house-inc` | `entities/house/OWNED_FILES.md` | git push → `houseinc-rebuild` |
| tredey.com | Trading journal | `agent:main:tredey-website-manager` | `website-tredey` | `projects/tredey/OWNED_FILES.md` | git push → `trading-journal-rebuild` |
| triadive.com | Multi-agent concepts | `agent:main:triadive-website-manager` | `website-triadive` | `projects/triadive/OWNED_FILES.md` | wrangler → `triadive-rebuild` |
| bithues.com | Crypto education | `agent:main:bithues-crypto-website-manager` | `website-bithues-crypto` | `projects/bithues-crypto/OWNED_FILES.md` | wrangler → `crypto-bithues-rebuild` |
| books.bithues.com | Book reviews | `agent:main:bithues-books-website-manager` | `website-bithues-books` | `projects/bithues/OWNED_FILES.md` | git push → `books-bithues-rebuild` |
| spaceorbitals.com | Space content | `agent:main:spaceorbitals-website-manager` | `website-spaceorbitals` | `projects/spaceorbitals/OWNED_FILES.md` | wrangler → `spaceorbitals` (no `-rebuild`) |
| mcn.org | Multi-agent network | `agent:main:mcn-website-manager` | `website-mcn` | `projects/mcn/OWNED_FILES.md` | git push + wrangler |

**As of 2026-08-26:** NONE of these workdesks exist as gateway agents. `agents_list` returns only `main`. All `sessionTarget: "session:agent:main:<workdesk>"` strings are ghost references.

## Cron → session binding rules

1. **Publishing cron** (writes content, deploys) → MUST target the owning website-manager workdesk.
2. **Watchdog cron** (verifies a site, alerts on failure) → targets `agent:main:quality-control`.
3. **Backstop cron** (safety-net for a publishing cron) → targets the same WM as the publishing cron it backs up.
4. **Boot-up cron** (one-shot, primes a session) → `deleteAfterRun: true`, `delivery.mode: "none"`.

## Current cron misrouting (2026-08-26)

All publishing and watchdog crons are misrouted because their target sessions don't exist. They silently fall through to `main`. This is the root cause of:

- **6 weeks of 0-byte MDs on dependability.us** — morning brief cron running as `main` instead of `dependability-website-manager`
- **Triadive weekly dispatch erroring** (`b8e229c6`, consecutiveErrors:2)
- **Tredey morning brief erroring** (`19d34fcb`, "lobster not found")
- **bithues-books newsletter erroring** (`cbb076d8`)
- **Bithues crypto weekly rebuild erroring** (`14b282d5`)

The fix is not in cron prompts. The fix is gateway-level: configure the missing agents.

## What to do when a publishing cron errors

1. **Check `cron get <cronId>`** — see lastRunError
2. **If error mentions "agent not found" or "session not found"** — gateway config gap, route to `brain` board card
3. **If error is from LLM** — fix the prompt, re-test in main, push, then ask WM to take over next run
4. **If error is from a script** — main fixes the script and pushes; mark commit with `OWNED_BY: <workdesk>` marker
5. **NEVER** rewrite a publishing cron to point at `main` to "fix" routing — that entrenches the anti-pattern

## When Mike asks "who owns this site"

Answer in this order:

1. Name the WM workdesk session (`agent:main:<brand>-website-manager`)
2. Confirm whether that session is currently wakeable. **As of 2026-08-26 the answer is NO** for every site. Until configured, `main` handles the work.
3. Link the `OWNED_FILES.md` manifest
4. Note any open workboard cards on the site's board

If Mike says "fix the X on site Y", the answer is:
- The owning WM does the work — IF the WM exists. Otherwise main does it under protest and adds `OWNED_BY: <workdesk>` to commits.

## Anti-pattern #121: routing work to a non-existent workdesk

If you find yourself doing website work in `main` instead of routing to a workdesk because `sessions_send` returns "agent not found", that's the signal. Don't quietly do it. Document and tell Mike.

See `skills/workdesk-bootstrap/SKILL.md` for the bootstrap pattern and gap analysis.