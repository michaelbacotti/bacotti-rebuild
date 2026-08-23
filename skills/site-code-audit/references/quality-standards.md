# Mike's Quality Standards for Site Content

**Captured:** 2026-08-23 (cron-quality upgrade)
**Enforced by:** `verify_published.py` (post-build gate)
**Source-aware:** edit at MD/build.py, never at rendered HTML

## Word counts

| Threshold | Action |
|---|---|
| **400w** | HARD FAIL — page too thin to be useful, blocks publish |
| **800w** | WARN — minimum acceptable for long-form |
| **1200w** | PREFERRED — full article length |

Pages below 400w trigger FAIL in `verify_published.py`. Pages below 800w get a WARN.

## E-E-A-T recipe (6-section)

Every page that ranks for commercial / YMYL keywords needs all six:

1. **named_editor** — Mike Bacotti, founder of <site>
2. **credentials** — relevant expertise with years and bylines
3. **launch_date** — when the site / desk went live
4. **editorial_process** — how each piece is sourced, screened, reviewed
5. **corrections_policy** — how facts get corrected and where to send corrections
6. **disclosure** — not financial / investment / legal advice; positions disclosure if relevant

The recipe lives in `verify_published.py` as `EEAT_RECIPE`. E-E-A-T MUST be wrapped in `<section class="eeat-block">` so it's part of the build template (not hand-edited), and survives cron rebuilds.

## AdSense compliance

- Every long page (800w+) needs at least one `<ins class="adsbygoogle">` tag
- Ad slot ID + Ad client ID must be set per site
- `verify_published.py` flags missing `<ins>` as FAIL

## Canonical URL

- Every page needs `<link rel="canonical" href="...">` with absolute URL
- CF Pages prefers absolute canonicals over relative

## AdSense + E-E-A-T interaction

If a page has AdSense but no E-E-A-T, Google policy will flag it for low-quality content. E-E-A-T is the trust signal that justifies the ads.

## Per-site templates (2026-08-23 bake-in)

E-E-A-T block content is site-specific and baked into `build.py` as a Python constant:

| Site | Constant | Source file |
|---|---|---|
| bithues.com | `EEAT_BLOCK` | `projects/bithues-crypto/bithues-build/build.py` |
| dependability.us | `DEPENDABILITY_EEAT_BLOCK` | `entities/dependability/dependability-may26/build.py` |
| successionholdingllc.com | `SUCCESSION_EEAT_BLOCK` | `entities/succession/website/build.py` |
| tredey.com | `TREDEY_EEAT_BLOCK` | `projects/tredey/trading-journal-build/build.py` |
| spaceorbitals.com | `SPACEORBITALS_EEAT_BLOCK` | `projects/spaceorbitals/spaceorbitals/build.py` |
| triadive.com | `TRIADIVE_EEAT_BLOCK` | `projects/triadive/triadive-build/build.py` |

When adding a new site, copy the bithues pattern:
1. Define the constant (`SITE_EEAT_BLOCK = """..."""`)
2. Add `.eeat-block` CSS
3. Inject into the main render function between header and content
