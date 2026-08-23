# Mike's Standing Instructions (do NOT re-ask)

Updated 2026-08-23 after Mike repeated "you don't need my permission to do that" and
"if you find something broken, fix it" and "I have told you this many times."

## Auto-fix rules

1. **Broken links: ALWAYS auto-fix.** If the audit finds broken internal links, fix them
   on the spot. Patterns:
   - Numeric insertion typos (`/articles1/` → `/articles/1/`)
   - First-page fallback (`/articles1/` → `/articles/` when no `/articles/1/` exists)
   - Fuzzy slug match (Jaccard ≥ 0.5 against siblings in same parent dir)
   - Remove dead `<a>` tags where the link target clearly doesn't exist (e.g. `/catalog/`)
   - Skip JS template literals (false positive from static scan over JS-built pages)
2. **Duplicate ad slots: ALWAYS auto-fix.** Keep first occurrence, drop subsequent.
3. **Duplicate H1: ALWAYS auto-fix.** Change second `<h1>` to `<h2>` (or whichever
   appropriate lower rank).
4. **Missing ad units on long pages (1500+w): auto-fix.** Insert an `<ins>` block with
   a placeholder slot (0000000000). Mike swaps in a real slot from AdSense dashboard.
5. **GA4 typos (`G-G-XXXXXX`): auto-fix** (existing fixer).
6. **Missing favicon: auto-fix** via the inject_favicon.py script (existing fixer).

## Do NOT auto-fix

- **Word count, E-E-A-T sections, thin+ads combinations** — these need Mike's writing.
- **Anything that requires removing a *page*** — surface to Mike, do not delete.
- **Anything that requires changing domain/DNS/credentials** — surface to Mike.

## Content writing role

Mike has rescinded his earlier "AI scaffolds, Mike writes" rule for the autonomous
publishing pipeline. Per 2026-08-23 instruction:

> "you are the content writer. you need to create a lobster or graph along with a
> work desk that can research trends and real time news, research a topic, write
> intelligently and insightfully and originally about the topic, proofread it for
> accuracy, ensure no hallucination, then publish it."

This applies to the publishing pipeline. Mike still personally writes strategic content
(e.g. AdSense rewrite per the 4-section recipe). But operational pipeline content
(trends-driven, factual summaries, etc.) is the AI's job.

## Honesty rule about "no hallucination"

I CANNOT guarantee 100% no-hallucination. Any claim I write must be backed by a
retrievable source. For financial/trading content (tredey, dependability), the
pipeline MUST include a human-review gate before publish — autonomous publishing
of trade ideas would cause real harm if I hallucinate numbers. For non-financial
content (general education, fiction-adjacent reviews on bithues), autonomous publish
is acceptable with confidence scoring.

## How to apply these rules

When you see a finding that is auto-fixable per the rules above, run the fixer
immediately. Do not list the finding in a status report and ask "should I fix this?"
Just fix it, commit it, mention it in the next status update.

If you encounter a finding that is NOT auto-fixable per these rules, surface it
clearly: which page, what the issue is, what's needed, what I would do if Mike
gave permission. Do NOT skip the work just because it's not auto-fixable.
