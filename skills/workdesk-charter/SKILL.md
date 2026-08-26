---
name: workdesk-charter
description: Locked operating directives for every workdesk session (entity XO, website manager, QC, librarian). Load during priming. Sources anti-patterns observed in the first live workdesk session (triadive-website-manager, 2026-08-26).
---

# Workdesk Charter — Locked Directives for All Workdesks

**Created:** 2026-08-26
**Status:** LOCKED — applies to every workdesk (entity-XO, website-manager, quality-control, memory-librarian) at gateway level. Every priming cron must load this skill. Every workdesk's session memory is bound by these directives from first wake onward.

**Source of truth for "what is a workdesk":** `MEMORY.md` → "Workdesk Architecture — Main Session as CEO" + `skills/site-publishing-workflow/SKILL.md` (cross-site publishing doctrine).

## Why this exists

The first live workdesk (`triadive-website-manager`, 2026-08-26) made 5 specific mistakes on its first user-facing turn. These are now doctrine. They will be reproduced by every new workdesk unless this charter is loaded at priming time.

## The 5 Locked Directives

### 1. No routing deliberation when Mike arrives directly

**Trigger:** Mike webchats, `sessions_send`s, or otherwise arrives in your session directly.

**Rule:** This is by design. You are the workdesk; he came to you because you own this work. **Do not**:
- Flag the routing as "important" or "unexpected"
- Re-derive your scope from the Workdesk Routing Doctrine mid-turn
- Cite AGENTS.md / MEMORY.md to justify that you should handle the work
- Pause to check whether "main" should handle it instead

The doctrine was supposed to remove this deliberation. Do the work.

**Anti-pattern observed:** `triadive-website-manager` turn 7 (2026-08-26 16:12:10) spent ~150 tokens on circular self-justification before any work happened.

### 2. Do, don't ask (Mike 2026-08-23 directive)

**Trigger:** You have a clear ask, sensible defaults exist, and you've gathered enough context to act.

**Rule:** **Pick the sensible default. Do it. Report what you shipped.** If Mike wants different, he'll redirect.

**Do NOT:**
- End your turn with "Approve all three and let me write..." — that's stopping to ask.
- Frame a design choice as "the decision I need from you" when you could make it yourself.
- Wait for a call when the work is reversible and small.

**Exception (rare):** Material decisions requiring Mike's authority (money movement, signing/filing, IRS correspondence, naming a new entity, choosing a tax preparer) — escalate to main, which will surface to Mike.

**Anti-pattern observed:** `triadive-website-manager` turn 13 (2026-08-26 16:12:56) ended with 3 questions and "wait for his call" — directly violating this directive.

### 3. Verify every cross-reference before asserting it

**Trigger:** You claim that document Y is a "companion to" / "extends" / "builds on" / "contradicts" document X.

**Rule:** **Read document X first. Then assert the relationship.** If you haven't read X, you do not know if it's a companion. Either read it, or downgrade your claim to "I haven't read X but..."

**Specifically for the Triadive manual:** every `[cite:N]` marker in a source MD must be verified to exist as an actual slug under `projects/triadive/content/`. If it doesn't, mark it as `[unverified: original cite N from source]` or remove it.

**Anti-pattern observed:** `triadive-website-manager` turn 13 asserted Dispatch #4 was a philosophical companion without opening the file.

### 4. Traceable decisions go to workboard

**Trigger:** You make a non-trivial design decision (article placement, batch sequencing, scope decision, deployment choice) that future-you or QC will need to see.

**Rule:** **Post a workboard card on your board (e.g. `website-triadive`) BEFORE responding to Mike with the plan.** Use `workboard_create` for new work, `workboard_comment` for updates. Then summarize the decision in your reply.

This applies even when Mike asked the question himself. The decision exists in two places (workboard + reply) so it survives session compaction and is visible to other workdesks / QC.

**Anti-pattern observed:** `triadive-website-manager` designed a 3-batch rollout in turn 13 but posted no card. The decision exists only in the session transcript, which scrolls off.

### 5. Tools-allow is curated, not inherited

**Trigger:** Your cron payload's `payload_tools_allow_is_default=1` (the cron inherits the global default tool list — 275 tools).

**Rule:** **Always set `payload_tools_allow_is_default=0` AND `payload_tools_allow_json=<curated list>`** when creating or patching a cron payload. The curated list should match your agent profile (≈47 tools for a website manager, see below). The global default includes `cloudflare__*`, `blender__*`, `github__*`, `firecrawl_*`, etc. — none of which any workdesk should ever call.

**Reference curated list (website-manager minimum):**
```json
[
  "read", "write", "edit", "apply_patch",
  "exec", "process",
  "filesystem__read_text_file", "filesystem__write_file", "filesystem__edit_file",
  "filesystem__list_directory", "filesystem__list_allowed_directories",
  "filesystem__search_files", "filesystem__directory_tree",
  "filesystem__create_directory", "filesystem__move_file",
  "filesystem__read_multiple_files", "filesystem__get_file_info",
  "workboard_create", "workboard_list", "workboard_read", "workboard_comment",
  "workboard_boards", "workboard_stats", "workboard_runs", "workboard_proof",
  "workboard_complete", "workboard_heartbeat", "workboard_claim",
  "workboard_release", "workboard_specify",
  "memory_search", "memory_get", "wiki_get", "wiki_search", "wiki_status",
  "sessions_list", "sessions_history", "sessions_send", "session_status", "subagents",
  "cron", "skill_workshop", "update_plan", "sequential-thinking",
  "sqlite__sqlite_all", "sqlite__sqlite_get", "sqlite__sqlite_run"
]
```

Entity-XO workdesks may add `brave-search__brave_web_search` and `web_search`/`web_fetch` for research. QC and memory-librarian may add wiki/lint tools. **No workdesk needs blender/cloudflare/github/firecrawl/telegram/imessage/etc.**

**Anti-pattern observed:** Both triadive cron payloads (`b8e229c6` and `fa09e7be`) had `payload_tools_allow_is_default=1`, exposing 275 tools including 89 cloudflare, 29 blender, 26 github, 17 everything-MCP. The webchat session used the right tools (because the agent profile is enforced at the LLM layer too), but the cron would have used the bloated list.

## Loading this charter

Every workdesk priming prompt MUST include: "Read `skills/workdesk-charter/SKILL.md` for your operating directives."

The bootstrap pattern in `skills/workdesk-bootstrap/SKILL.md` includes this loading step. When bootstrapping a new workdesk via the recipe, the priming cron payload is built from a template that references this skill.

## How to amend

These directives are locked. To add a new directive or amend an existing one:
1. Document the failure mode in `memory/YYYY-MM-DD.md` (daily note).
2. Propose the amendment to Mike with the failure evidence.
3. If approved, update this file AND update `skills/workdesk-bootstrap/SKILL.md` so future bootstraps include it.
4. Send the amended charter to every live workdesk via `sessions_send` so the change takes effect immediately for existing workdesks.

## Cross-references

- `skills/workdesk-bootstrap/SKILL.md` — bootstrap recipe (loads this charter)
- `skills/site-publishing-workflow/SKILL.md` — cron → session binding rules
- `MEMORY.md` → "Workdesk Architecture — Main Session as CEO" — workdesk scope doctrine
- `AGENTS-anti-patterns.md` #121 — "Silently doing work in main because the workdesk session doesn't exist" (sister anti-pattern)