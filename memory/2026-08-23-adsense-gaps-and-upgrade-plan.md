# 2026-08-23 09:42 ET — AdSense Gaps Analysis + Content Upgrade Plan

**Trigger:** Mike asked three things:
1. "I have AdSense access and already told you the feedback — check your conversations."
2. "Look for gaps in the audits — what isn't being checked?"
3. "Plan to upgrade sites to high-value content using crons, loops/graphs/lobsters."

## 1. AdSense facts I should have remembered

You're right. The facts exist but they're scattered. I just created `memory/site-notes/adsense.md` to consolidate them. Key facts:

**Rejection history:**
- bithues.com: rejected 2026-07-20 for **"low value content"** — fixed by commit `2b1904e1` (22 thin+ads pages expanded to ≥800w using the 5-section review template)
- Other 4 sites: pending approval, no documented rejection reason

**AdSense pub-id:** ca-pub-9312870448453345 (shared across all 5)

**AdSense-clean status (per 2026-07-20 sitemap audit):**
- bithues 183/185 PASS
- dependability 111/111 PASS  
- succession 47/47 PASS
- tredey + spaceorbitals: cleaned but no separate sitemap audit count shown

**Word-count thresholds (the actual AdSense signal):**
- 297-385w = clearly flagged
- 460-685w = flagged
- 800w+ for /about/, /authors/, /legal/, /editorial/
- 1200w+ for articles/reviews
- Listing/archives = functional, not flagged
- Product pages with 0 ads = word count irrelevant

**E-E-A-T recipe for /about/, /authors/, /editorial/:**
named editor/author with credentials + site launch date + editorial process (research → write → review) + corrections policy + disclosure + what we will NOT do + reading list / cited sources. Passes 824w minimum on dependability /about/.

**Expansion patterns:**
- **Bithues reviews (5-section template):** "Why this book sits in our collection" + "The argument that earns the reader's attention" + "Where the book is strongest" + "Where the book is weaker" (HONEST critique — E-E-A-T critical) + "Who this book is for" + "How this review approaches the book". Brings 320-750w → 874-1145w.
- **Succession articles (4-section recipe):** Worked Example + Common Mistakes + Decision Checklist + When This Metric Doesn't Apply. Add 700-900w per article.
- **Children's book reviews (bithues):** skip "argument that earns attention", use sensory/educational framing.
- **Legal page dedup pattern:** 6-7 `<ins class="adsbygoogle">` tags per page from copy-paste. Keep 1 per page.

## 2. Audit gaps — what the current site-code-audit does NOT check

Confirmed by reading `skills/site-code-audit/scripts/scan_static.py` (281 lines). It checks:
- ✅ duplicate_h1
- ✅ missing_canonical
- ✅ broken_internal_link
- ✅ ga4_typo
- ✅ missing_favicon
- ✅ build_script_error

It does **NOT** check any of the AdSense-relevant signals:

| Gap | Severity | What it misses |
|---|---|---|
| **Word count per page** | CRITICAL | Pages below 800w / 1200w threshold — direct AdSense red flag |
| **Thin+ads combination** | CRITICAL | Page below word threshold AND has `<ins class="adsbygoogle">` — the actual blocker |
| **Ad slot dedup** | HIGH | Pages with >1 ad ins tag from copy-paste — flagged by Google as policy issue |
| **E-E-A-T section presence** | HIGH | Pages missing named editor/credentials/corrections policy/etc. |
| **Content freshness / lastmod** | MEDIUM | Pages not updated in 90+ days — AdSense rewards recent updates |
| **Template compliance** | MEDIUM | Bithues reviews missing 5 sections; succession articles missing 4 sections |
| **Cross-site consistency** | LOW | Disclosure patterns vary per site — should be uniform |
| **AdSense pub-id presence** | LOW | Pages missing ca-pub-9312870448453345 = no revenue |

**This is the real reason bugs persisted for months.** The audit catches HTML hygiene but not the AdSense content signals Google reviewers actually look at.

## 3. Plan to upgrade sites to high-value content

Three tracks, in order of value:

### Track A: Extend the site-code-audit to cover AdSense signals (immediate)

Add new findings classes to `scan_static.py`:

1. **`word_count_low`** — extract `<main>` or `<article>` text content, count words
   - `<800` for /about/, /authors/, /legal/, /editorial/, /methodology/, /disclaimer/, /privacy/, /terms/
   - `<1200` for /articles/, /reviews/, /forecasts/, /commentary/, /newsletters/
   - Severity: critical if page also has adsbygoogle (thin+ads combo), high otherwise
   
2. **`thin_with_ads`** — page below word threshold AND has `<ins class="adsbygoogle">`
   - Severity: critical (this is the actual AdSense red flag)
   - Auto-fixable: NO (requires content expansion)
   
3. **`duplicate_ad_slot`** — page has >1 `<ins class="adsbygoogle">` for same data-ad-slot
   - Severity: high
   - Auto-fixable: YES (mechanical dedup)
   
4. **`missing_eeat_sections`** — /about/, /authors/, /editorial/ missing any of: named editor, credentials, corrections policy, disclosure
   - Severity: high
   - Auto-fixable: NO (requires human content)
   
5. **`content_stale`** — page lastmod in sitemap.xml >90 days ago AND page has ads
   - Severity: medium
   - Auto-fixable: NO
   
6. **`missing_ad_unit`** — page has substantial content (>1200w) but no `<ins class="adsbygoogle">`
   - Severity: medium (lost revenue opportunity)
   - Auto-fixable: NO (requires judgment on ad placement)

**Effort:** ~150 lines of Python in `scan_static.py`. Can ship today.

### Track B: Content-velocity monitoring (this week)

New `skills/content-velocity/` skill:

1. **Daily:** track words added/updated per site (delta from yesterday's git diff of MD sources)
2. **Daily:** track publish count per site (cron completion events vs target)
3. **Weekly:** report per-site content velocity (articles/week, words/week, last publish date)
4. **Alert:** if any site's velocity drops below threshold for 3 consecutive days → workboard card

**Cron wiring:**
- `site-content-velocity-daily` — 11pm ET, after publishing pipeline finishes
- Session target: `session:site-qa` (the persistent session we're creating tonight)
- Lobster pipeline at `workflows/publish/content-velocity.lobster`

**Why this matters:** AdSense rewards sites that publish regularly. If bithues stops publishing for 2 weeks, AdSense reviewers notice. Velocity monitoring catches this before they do.

### Track C: Content upgrade via crons (this week + ongoing)

#### C.1 Weekly E-E-A-T audit cron

`site-eeat-audit-weekly` — Sunday 9pm ET
- Scans every /about/, /authors/, /editorial/, /methodology/, /disclaimer/, /privacy/, /terms/ across all 5 sites
- Flags pages below 800w
- Flags pages missing E-E-A-T sections
- Output: workboard card per site with specific pages to upgrade

#### C.2 Weekly thin+ads audit cron

`site-thin-ads-audit-weekly` — Sunday 10pm ET
- Scans every page that has `<ins class="adsbygoogle">`
- Checks word count against threshold
- Flags thin+ads combinations
- Output: workboard card per site

#### C.3 Content expansion crons (long-running, not every site)

Only for sites where E-E-A-T expansion is needed. NOT a daily cron — a one-shot per site:
- Pick 5-10 thin pages per site
- Expand to 1200w+ using the 4-section (succession) or 5-section (bithues) recipe
- One-shot cron, deletes after run

**Critical caveat:** I should NOT auto-write content. The E-E-A-T recipe requires real knowledge of the topic. Auto-expansion would produce thin content with more words — exactly what AdSense penalizes. These crons should:
- Surface pages needing expansion (workboard cards)
- Provide the recipe to follow
- WAIT for Mike (or a writer) to actually write the content

#### C.4 Bithues review pipeline extension

Current bithues cron generates one review per day via `b131e6f9`. Add a sibling cron:
- `bithues-review-expansion-weekly` — Sunday 2am ET
- Picks 5 existing reviews under 800w
- Flags for re-expansion with the 5-section template
- Outputs workboard card

## 4. Loop / graph / lobster strategy

The site-code-audit lobster pipeline (`workflows/publish/site-qa.lobster`) currently has 9 steps. Extend it to 12:

```
Step 10: adsense_signals  (Track A above — word count, thin+ads, E-E-A-T, dedup)
Step 11: content_velocity (Track B — daily delta from yesterday)
Step 12: weekly_upgrade_queue (Track C.1/C.2 — Sunday 9-10pm surface cards)
```

Three new lobsters to write:
- `workflows/publish/adsense-audit.lobster` — runs the AdSense-signal scan as a standalone or as Step 10 of site-qa
- `workflows/publish/content-velocity.lobster` — runs the velocity monitor
- `workflows/publish/eeat-upgrade-queue.lobster` — runs weekly, surfaces workboard cards

All three reuse the existing approval_gate pattern from site-qa.lobster.

## 5. What I am NOT proposing (and why)

- **NOT auto-generating content** — would produce low-quality text that makes the AdSense problem worse
- **NOT auto-submitting AdSense applications** — Mike's call when to resubmit (Google suggests 30-day cadence after rejections)
- **NOT modifying the existing content crons** — they work; don't break them
- **NOT touching _archive/** — frozen state

## 6. Open questions for Mike

1. **What was the rejection reason for dependability/succession/spaceorbitals/tredey?** (Only bithues had a documented reason)
2. **Do you have GSC organic traffic data for these sites?** (AdSense often gates on traffic)
3. **What's your preferred cadence for AdSense resubmissions?**
4. **Are you actively writing new content, or is it 100% cron-generated?** (Affects whether velocity drops are fixable)

## 7. Immediate next steps (today, if Mike approves)

1. Add 6 new finding classes to `skills/site-code-audit/scripts/scan_static.py` (~150 lines)
2. Run audit; expect to surface ~30-50 thin+ads combinations across the 5 sites
3. Create 1 workboard card per site listing specific pages needing expansion
4. Write `memory/skills/content-velocity/SKILL.md` for Track B
5. Wire `site-eeat-audit-weekly` and `site-thin-ads-audit-weekly` crons
6. Extend site-qa.lobster with Steps 10/11/12
