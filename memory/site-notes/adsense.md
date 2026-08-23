# AdSense Reference — Mike's 5-site portfolio

**Status (2026-08-23):** Approval still pending across the board. Two known blockers, both now resolved:
1. **www→522 on bacotti + tredey** — fixed today by Mike (CF Pages custom domains added)
2. **Low-value-content rejection** on bithues — fixed 2026-07-20 (commit 2b1904e1)

## Rejection history

| Site | Original rejection | Date | Status |
|---|---|---|---|
| bithues.com | "Low value content" | 2026-07-20 | Content expanded to ≥800w across 26 thin+ads pages. Remediation: commit `2b1904e1` |
| dependability.us | Pending approval | — | E-E-A-T recipe applied to /about/ (297→824w). Three thin commentary pages expanded 498→838w. |
| successionholdingllc.com | Pending approval | — | 17 thin articles given 4-section recipe (≥1200w each) |
| spaceorbitals.com | Pending approval | — | /about/ + /authors/ E-E-A-T expansion to 800+w |
| tredey.com | Pending approval | — | /about/ 385→1047w. Position sizing + Dependability Holdings disclosure added. |

**AdSense pub-id:** ca-pub-9312870448453345 (shared across all 5 sites).

## AdSense-specific audit gaps (what the code audit does NOT check)

The current `skills/site-code-audit/` checks HTML hygiene, live probes, GA4 tags, and cron health. It does NOT check:

### 1. Word count thresholds (CRITICAL)

- /about/, /authors/, /legal/, /editorial/ → **800w minimum**
- /articles/, /reviews/, substantive content → **1200w minimum**
- /listing/, /archive/, /index/ → functional, not flagged
- Product pages with 0 ads → word count irrelevant
- **Current state:** 297-385w = clearly flagged. 460-685w = flagged. 800+/1200w = passes.

### 2. E-E-A-T section presence (CRITICAL)

Every /about/, /authors/, /editorial/ must have:
- Named editor/author with credentials (specific person + their background)
- Site launch date
- Editorial process (research → write → review workflow)
- Corrections policy (when discovered + how fixed)
- Disclosure (who operates, relationships)
- What we will NOT do (avoided content types, e.g. no get-rich-quick language)
- Reading list / cited sources

### 3. Thin+ads combination check (CRITICAL)

Pages with `<ins class="adsbygoogle">` AND below word threshold are the actual AdSense red flag, not just thin pages alone. The audit should cross-reference word count vs ad slot presence.

### 4. Legal page dedup pattern (MEDIUM)

Dependability had 6-7 `<ins class="adsbygoogle">` tags per legal page from copy-paste during build. The audit should flag pages with >1 ad ins tag.

### 5. Content freshness signals (MEDIUM)

AdSense rewards recently-updated sites. The audit should track `<lastmod>` dates from sitemap.xml and flag pages not updated in 90+ days.

### 6. Content template compliance (MEDIUM)

- **Bithues reviews** must have 5 sections: "Why this book sits in our collection" + "The argument that earns the reader's attention" + "Where the book is strongest" + "Where the book is weaker" (HONEST critique — E-E-A-T critical) + "Who this book is for" + "How this review approaches the book"
- **Succession articles** must have 4 sections: Worked Example (real numbers) + Common Mistakes (3-4 named pitfalls) + Decision Checklist (5-7 bulleted) + When This Metric Doesn't Apply
- **Children's book reviews** (bithues): skip "argument that earns attention", use sensory/educational framing

### 7. Cross-site consistency of disclosures (LOW)

Succession has jurisdictional/statute citations, dependability has named events (CPI/FOMC/nonfarm), spaceorbitals has named missions/agencies, tredey has named strategies with strikes/expiries, bithues has editorial/argument-based reviews with honest critique sections. Each site's /about/ should reflect the appropriate voice.

### 8. Hard policy items (LOW but non-negotiable)

- No scraped content (Google's #1 AdSense policy violation)
- No copyrighted reproduction
- No adult, gambling, drug, violence content (none of our sites are at risk)
- Privacy policy + terms + contact page required (all 5 have these)

## Word-count expansion patterns (from successful remediation 2026-07-20)

### Bithues reviews (5-section template)
- 320-750w reviews → 874-1145w after expansion
- Children's book reviews (Little Mike) skip "argument that earns attention"
- Use sensory/educational framing, parent/grandparent-appropriate tone

### Succession articles (4-section recipe)
- Each article gains 700-900w from expansion
- Worked Example uses real numbers ($/%/property types)
- Common Mistakes = 3-4 named pitfalls + consequences
- Decision Checklist = 5-7 bulleted items operators use on deals
- When This Metric Doesn't Apply = edge cases

### E-E-A-T expansion for /about/, /authors/, /editorial/
- Bring 387w → 800w+ by adding the 7 sections above

### Legal page dedup
- Dependability /contact/, /disclaimer/, /privacy/ had 6-7 ins tags from copy-paste
- Pattern: keep exactly 1 per page

## Anti-patterns from AdSense remediation work

- **Anti-pattern #88:** nav-referenced pages can be missing even when their directory exists. Always verify HTTP status, not directory presence, when checking nav links.
- **Anti-pattern #89:** bithues-content-publishing build.py regenerates HTML from MD sources — E-E-A-T sections in HTML only get wiped every cron run. **Fixed** by migrating 78 E-E-A-T sections to MD source (commit `e643c702`).
- **Anti-pattern #94:** audit ALL pages produced by build.py, not just the "important" ones — index pages count for AdSense.
- **Anti-pattern #90:** Cross-site content hygiene — each site has unique build/deploy semantics. bithues/tredey/dependability/succession use MD → build.py → HTML with different templates; spaceorbitals uses wrangler (no git remote); bacotti.com and houseinc501c3.com are static HTML. Apply uniform solution to non-uniform systems = wrong for some subset every time.

## Deploy paths (NOT uniform)

| Site | Source of truth | Deploy |
|---|---|---|
| bithues.com | MD at `projects/bithues/content/` | git push to `bithues-rebuild` (CF Pages) |
| dependability.us | MD at `entities/dependability/website/content/` | git push to `dependability-rebuild` |
| successionholdingllc.com | MD at `entities/succession/website/content/` | git push to `succession-rebuild` |
| tredey.com | MD at `projects/tredey/website/content/` | git push to `trading-journal-rebuild` |
| spaceorbitals.com | MD at `projects/spaceorbitals/spaceorbitals/_standards/` | wrangler deploy (NO git remote) |
| bacotti.com | Static HTML at `entities/bacotti-inc/website/` | git push to `bacotti-rebuild` |

**CF Pages propagation:** ~3-4 min for non-cache-busted. Verify at +60s, +180s, +240s.

## Per-site verification rule

When running multi-site remediation, verify each site individually ("Site X audit complete, Site Y upgrade done, Site Z verified live") — not just "7 steps done". The "N steps complete" framing conflated bithues with the other 4 sites on 2026-07-20 and almost missed the bithues fix.

## What actually got AdSense-clean on 2026-07-20

| Site | Commits | Pages |
|---|---|---|
| dependability.us | c624232 + earlier | 14 |
| successionholdingllc.com | f1b665c + d023138 | 6 |
| tredey.com | 7c2310e + 425434c + 43a5972 | 16 |
| spaceorbitals.com | wrangler deploy | 12 |
| bithues.com | 2b1904e1 | 26 |

**Zero thin+ads, zero dup across all 5.** Sitemap audit confirmed all fixes held (bithues 183/185 PASS, dependability 111/111 PASS, succession 47/47 PASS).

## Still-open questions for AdSense

- What was the rejection reason for dependability/succession/spaceorbitals/tredey? (Only bithues had a documented "low value content" rejection)
- Is there traffic data showing organic search visitors before approval? (AdSense often gates on traffic)
- What's the resubmission cadence? (Google suggests 30 days between resubmits after policy violations)
