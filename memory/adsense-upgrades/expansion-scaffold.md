# Content Expansion Scaffold

**For:** Mike (you write, I scaffold)
**Used by:** all 24 thin+ads pages + 48 word_count_low findings
**AdSense threshold:** 800w content articles, 800w legal_umbrella, 600w landing
**Why this works:** AdSense "low value content" rejection is about reviewer confidence. Reviewers don't count words — they skim for *signals of expertise*. The 4 sections below are the signals that flip a "low value" page into "high value."

---

## The 4-Section Recipe (target ~800w total per article)

### Section 1: Worked Example (200-300w)

**What it is:** One specific case from real life / real data, walked through step by step.

**Why reviewers want it:** Proof you actually know this domain, not just paraphrasing.

**Template:**
```markdown
## Worked Example: [Specific case name, ideally with a number]

On [date], [asset/topic] did [specific thing]. Here's what happened and what we
learned:

- Setup: [concrete numbers/conditions — 2-3 lines]
- Decision: [what you did or what the market did — 2-3 lines]
- Outcome: [result, with numbers — 2-3 lines]
- Why it matters: [one sentence tying back to the article's main point]

Generic: "I traded it and made money" — fails the test.
Specific: "On 2026-07-14, SPX closed at 5,483 with VIX at 14.2 (95th-percentile
low for 2026). The bull-put spread I opened 5 DTE at 5300/5310 collected $1.85
and expired worthless. The signal: term structure backwardation + below-median
realized vol over the prior 30 sessions." — passes.
```

### Section 2: Common Mistakes (200-300w)

**What it is:** 3-5 things people actually get wrong about this topic, with the failure mode named.

**Why reviewers want it:** Shows you've seen the failure modes (real experience), not just the textbook answer.

**Template:**
```markdown
## Common Mistakes

- **Mistake 1: [Name]**
  - What it looks like: [the wrong behavior]
  - Why it fails: [consequence]
  - How to avoid: [concrete check or rule]

- **Mistake 2: [Name]**
  - ...
```

### Section 3: Decision Checklist (150-200w)

**What it is:** A bulleted list of pre-commit checks. Actionable, not aspirational.

**Why reviewers want it:** This is what differentiates a real operating manual from a content article.

**Template:**
```markdown
## Decision Checklist

Before [the action this article is about], confirm:

- [ ] [Condition that must be true]
- [ ] [Data point to verify]
- [ ] [Risk to size]
- [ ] [Time horizon to honor]
- [ ] [Exit trigger to pre-commit]
```

### Section 4: When This Doesn't Apply (100-150w)

**What it is:** Honest scoping — when the article's advice is wrong for the reader.

**Why reviewers want it:** Shows you understand the limits of your own advice. This is the #1 E-E-A-T signal.

**Template:**
```markdown
## When This Doesn't Apply

- If [condition A], see [alternative article or approach] instead.
- If [condition B], the [recommendation in this article] flips — [explain how].
- If [condition C], this is the wrong framework entirely — [point to the right one].
```

---

## How to use this for each thin page

1. **Find your page in `scripts/adsense-upgrade-report.py --date 2026-08-23` output** (look under the `thin_with_ads` section per site).
2. **Open the source `.md` file** (HTML is generated from MD on most sites). Edit the MD.
3. **Pick the smallest 4-section combo that hits your word target:**
   - Need <50 more words: skip section 4, expand section 1 (Worked Example) with a 2nd data point.
   - Need 100-200 more words: add sections 3 + 4.
   - Need 200+ more words: full 4 sections.
4. **Run the build script** (per-site — most are `python3 _build/build.py` or `python3 build.py` in the site root).
5. **Re-run the audit** (`python3 skills/site-code-audit/scripts/run.py --site <name>`) to confirm.

---

## E-E-A-T sections for legal_umbrella pages (separate task)

For `/about/`, `/contact/`, `/legal/`, `/privacy/` etc. (25 pages flagged), you need:

1. **Editorial Process** — who writes/reviews, what's the bar
2. **Launch Date** — when the site launched, when this article was first published, when last updated
3. **Credentials** — author's background, expertise signals, links to bios
4. **Corrections Policy** — how errors are reported and fixed

These go BEFORE the existing content (top of page), usually in a sidebar or callout box.

Template for the "About this site" block:

```markdown
## About this site

- **Launched:** [YYYY-MM-DD]
- **Last reviewed:** [YYYY-MM-DD]
- **Editorial process:** [1-2 sentences — who writes, who reviews, what's the bar]
- **Corrections:** [1 sentence — how readers report errors, how quickly you fix]
- **Author credentials:** [1-2 sentences — background, domain expertise]
```

---

## Automation: when this scaffold runs

I will **not auto-generate any text**. The scaffold exists so you can:

1. Open a page from the report
2. Copy the template
3. Fill in real numbers, real cases, real conditions
4. Drop it into the .md source
5. Build + re-audit

If you want a tool to remind you which pages need which sections, that's a Lobster/cron I can build — but the *content* itself has to come from you.

---
*Generated 2026-08-23 as part of AdSense audit followup. See `wiki/adsense-upgrade-plan.md` for the full plan and `memory/site-notes/adsense.md` for thresholds.*
