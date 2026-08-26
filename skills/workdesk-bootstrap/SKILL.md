---
name: workdesk-bootstrap
description: Bootstrap pattern for XO / website-manager workdesks. Documents the gap where session keys exist in MEMORY.md and cron sessionTargets but no gateway agent configurations exist.
---

# Workdesk Bootstrap

**Created:** 2026-08-26
**Status:** DRAFT — applies to a known infrastructure gap

## Problem statement

The XO and website-manager workdesk architecture was specified in MEMORY.md on 2026-08-25. The architecture described:

- 4 XO workdesks (`agent:main:dependability-xo`, `agent:main:bacotti-inc-xo`, `agent:main:succession-xo`, `agent:main:house-inc-xo`)
- 1 cross-entity session (`agent:main:family-office-finance`)
- 8 website-manager workdesks (e.g., `agent:main:dependability-website-manager`, `agent:main:triadive-website-manager`)
- 1 quality-control session (`agent:main:quality-control`)
- 1 memory-librarian session (`agent:main:memory-librarian`)

**The architecture exists on paper but not at the gateway level.** As of 2026-08-26 11:00 ET, `agents_list` returns only `main`. None of the named workdesk agents exist as wakeable entities.

**Consequence:** Every cron with `sessionTarget: "session:agent:main:<workdesk-name>"` is silently falling through to `agent:main` (this dashboard). Every `sessions_send(agentId="<workdesk>")` from main fails with "agent not found".

This is the root cause of:
- 6 weeks of 0-byte MD files on dependability.us (cron fired as main, main's context was wrong for the heavy MD-write step)
- Triadive weekly dispatch cron (b8e229c6) erroring (consecutiveErrors: 2)
- Tredey morning brief cron (19d34fcb) erroring (lastRunError: "lobster not found")
- bithues-books weekly newsletter cron (cbb076d8) erroring

## What the main session SHOULD do when it discovers this

1. **Stop pretending the workdesks exist.** Update MEMORY.md to clearly mark workdesks as "not yet configured at gateway level" until they actually are.
2. **Use existing routes that work.** `workboard_create`, `workboard_list`, `workboard_comment`, `workboard_read`, `cron_get`, `cron_update`. These don't require the workdesk to exist.
3. **Document the gap.** File a workboard card on the `brain` board titled "Workdesk bootstrap required at gateway level" with the list of agents that need configuration.
4. **Tell Mike.** Don't quietly work around the gap. It's a real architecture problem.

## Bootstrap pattern (locked 2026-08-25)

When workdesks were initially designed, the bootstrap pattern was:

1. **Gateway config** — add an entry to the OpenClaw config like:
   ```toml
   [agents.<workdesk-name>]
   model = "minimax/MiniMax-M2.7"
   fallbacks = ["minimax/MiniMax-M3"]
   description = "<scope>"
   ```
2. **Reload gateway config** so the new agent becomes wakeable.
3. **One-shot priming cron** that wakes the new session with explicit ownership info:
   ```python
   cron.add(
       schedule=at("2026-08-25T14:25:00-04:00"),
       sessionTarget=f"session:agent:main:{workdesk_name}",
       payload=agentTurn(message="You are the {workdesk_name} workdesk..."),
       delivery=mode(none),
       deleteAfterRun=true,
   )
   ```
4. **WM/XO primes itself** by reading OWNED_FILES.md, workboard board, recent cron run logs, MEMORY.md. Confirms via workboard card.
5. **Crons get re-bound** to point at the now-real workdesk session.

**Step 1 failed silently** on 2026-08-25 — the cron additions all succeeded (creating `sessionTarget: "session:agent:main:<workdesk>"` strings) but the gateway never had matching agent entries. Result: 14+ crons currently misrouted.

## How to fix the gap (today's plan)

Track 1 (already done, this commit):
- [x] Add `cron_source_integrity` check to nightly site-code-audit. Catches 0-byte MDs going forward.
- [x] Add `OWNED_FILES.md` manifests per WM/XO. Documents scope for whoever configures the workdesk later.
- [x] Add workboard hook so cron-source findings post cards to the owning WM's board (even if the WM doesn't exist yet — the card sits there for whoever wakes up).

Track 2 (requires gateway access — flagged for Mike):
- [ ] Add gateway config entries for 4 XO + 1 family-office-finance + 8 WM + 1 QC + 1 librarian = 15 agent configs.
- [ ] Verify each agent becomes wakeable (call `agents_list`, expect the new ID).
- [ ] Schedule one-shot priming crons (deleteAfterRun=true, delivery.mode=none) for each.
- [ ] Re-bind all crons that target the workdesk session.

Track 3 (after Track 2 — proper routing):
- [ ] WM/XO workdesks take over their respective cron runs
- [ ] Main session routes work via `sessions_send(agentId=<workdesk>, ...)`
- [ ] Workdesk work is no longer done in main

## Anti-pattern #120: silently working around missing workdesks

If `sessions_send(agentId=<workdesk>)` returns "agent not found", that's a **stop signal**, not a permission to do the work in main. The right move is:

1. Document the gap (workboard card + MEMORY.md).
2. If urgent and blocking Mike's work: do the minimum in main, mark it with `OWNED_BY: <workdesk>` markers in commit messages and code comments so future WM knows what they're inheriting.
3. Tell Mike what happened. Don't pretend the WM did the work.

## Reference: which workdesks are not yet configured

| Workdesk | Type | Currently-bound crons | Notes |
|---|---|---|---|
| `agent:main:dependability-xo` | Entity XO | fdd24d1a (GP fee), 9807bbb7 (P&L) | Bookkeeping, Quicken |
| `agent:main:bacotti-inc-xo` | Entity XO | (none) | C-Corp tax, IRS |
| `agent:main:succession-xo` | Entity XO | (none) | 7 property LLCs |
| `agent:main:house-inc-xo` | Entity XO | (none) | 501c3, 990-N |
| `agent:main:family-office-finance` | Cross-entity | (none currently) | Cross-entity profit-share |
| `agent:main:dependability-website-manager` | WM | 6437c795, 34e3fde2, 05878b6c, 5b45775c, 99ff0c15, 48a00e94, b1695aec, 67f56636, 7054398f*** | dependability.us |
| `agent:main:tredey-website-manager` | WM | 19d34fcb (erroring), be4d1e3d, 84891f68 | tredey.com |
| `agent:main:triadive-website-manager` | WM | b8e229c6 (erroring), fa09e7be | triadive.com |
| `agent:main:bithues-crypto-website-manager` | WM | 22efc5fc, 9511d744, 84e240d5, 14b282d5 | bithues.com (crypto) |
| `agent:main:bithues-books-website-manager` | WM | cbb076d8 (erroring) | books.bithues.com |
| `agent:main:spaceorbitals-website-manager` | WM | c33bf1d9, 2ad14011 | spaceorbitals.com |
| `agent:main:succession-website-manager` | WM | b0d46aaf | successionholdingllc.com |
| `agent:main:bacotti-inc-website-manager` | WM | (none — site is broken/403) | bacotti.com |
| `agent:main:house-inc-website-manager` | WM | (none) | houseinc501c3.com |
| `agent:main:mcn-website-manager` | WM | (TBD) | mcn.org |
| `agent:main:quality-control` | Quality | c9b3d8e2, 47d92495 | Cross-site QA |
| `agent:main:memory-librarian` | Librarian | 67ef9aa3 | MEMORY/wiki |

**17 workdesks total. 0 currently configured at gateway level.**