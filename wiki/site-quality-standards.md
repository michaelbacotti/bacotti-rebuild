---
type: synthesis
title: Site Quality Standards
created: 2026-08-23
confidence: 0.95
status: durable
sources:
  - memory/memory/code-audit-2026-08-23.md
  - skills/site-code-audit/references/quality-standards.md
  - skills/site-code-audit/references/anti-patterns.md
---

# Site Quality Standards

**Last updated:** 2026-08-23 (cron-quality upgrade)

Mike's binding standards for content quality across all 8 publishing sites (bacotti, bithues, dependability, succession, tredey, triadive, spaceorbitals, wildwood-press). These are enforced by `verify_published.py` post-build and by the autonomous-content-publishing pipeline's draft verify stage.

## Word count thresholds

| Threshold | Action | Why |
|---|---|---|
| **400w** | HARD FAIL — blocks publish | Page too thin to be useful; Google flags as low-quality content |
| **800w** | WARN — minimum acceptable | Covers most long-form content needs with adequate depth |
| **1200w** | PREFERRED — full article length | Best for SEO + reader value; recommended target |

`verify_published.py` flags `word_count_low` (high severity) for any page below 400w, warns at 800w.

## E-E-A-T 6-section recipe (the binding trust signal)

Every page that ranks for commercial / YMYL keywords needs ALL six sections:

1. **named_editor** — Mike Bacotti, founder of <site>
2. **credentials** — relevant expertise with years and bylines
3. **launch_date** — when the site / desk went live
4. **editorial_process** — how each piece is sourced, screened, reviewed
5. **corrections_policy** — how facts get corrected and where to send corrections
6. **disclosure** — not financial / investment / legal advice; positions disclosure if relevant

**Hard rule:** E-E-A-T MUST be wrapped in `<section class="eeat-block">` AND defined as a Python string constant in `build.py` (e.g. `EEAT_BLOCK = "..."`), then interpolated into the render function. This way every cron rebuild regenerates E-E-A-T. See anti-pattern #89.

## AdSense compliance

- Every long page (800w+) needs at least one `<ins class="adsbygoogle">` tag
- Ad slot ID + Ad client ID must be set per site
- `verify_published.py` flags missing `<ins>` as FAIL
- Pages with AdSense but no E-E-A-T get flagged for low-quality content by Google policy

## Canonical URL

- Every page needs `<link rel="canonical" href="...">` with absolute URL
- CF Pages prefers absolute canonicals over relative
- Missing canonical → FAIL

## No duplicate H1 per page

- One `<h1>` per page. Duplicates trigger `duplicate_h1` finding (medium severity).

## Per-site EEAT_BLOCK mapping (canonical)

| Site | Constant | Source file |
|---|---|---|
| bithues.com | `EEAT_BLOCK` | `projects/bithues-crypto/bithues-build/build.py` |
| dependability.us | `DEPENDABILITY_EEAT_BLOCK` | `entities/dependability/dependability-may26/build.py` |
| successionholdingllc.com | `SUCCESSION_EEAT_BLOCK` | `entities/succession/website/build.py` |
| tredey.com | `TREDEY_EEAT_BLOCK` | `projects/tredey/trading-journal-build/build.py` |
| spaceorbitals.com | `SPACEORBITALS_EEAT_BLOCK` | `projects/spaceorbitals/spaceorbitals/build.py` |
| triadive.com | `TRIADIVE_EEAT_BLOCK` | `projects/triadive/triadive-build/build.py` |

When adding a new site, copy the bithues pattern: define the constant, add `.eeat-block` CSS, inject into the main render function.

## Quality gate pipeline

```
autonomous-content draft
    ↓ verify.py (word count + 5-section E-E-A-T at draft stage)
    ↓ (passes →) publish.py
    ↓ build.py (renders HTML from MD source, injects EEAT_BLOCK)
    ↓ verify_published.py (post-build gate)
    ↓ (passes →) wrangler pages deploy OR git push
```

Any FAIL at any stage blocks publish. The verify_published.py gate covers: word count, 6-section E-E-A-T, AdSense, canonical, anti-pattern #89 wipe detection.

## Related

- `wiki/adsense-upgrade-plan.md` — earlier AdSense remediation work
- `skills/site-code-audit/SKILL.md` — full audit + fix pipeline
- `skills/site-code-audit/references/quality-standards.md` — same standards in skill reference form
- `skills/site-code-audit/references/anti-patterns.md` — anti-patterns #89/#91/#92/#93
- `memory/memory/code-audit-2026-08-23.md` — 49→0 audit fix report from earlier today
