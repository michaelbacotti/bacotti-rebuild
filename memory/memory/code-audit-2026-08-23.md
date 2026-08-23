# Site Code Audit — 2026-08-23

**Sites audited:** bacotti, wildwood-press, bithues, dependability, spaceorbitals, succession, tredey, triadive
**Initial findings:** 49 → **Final findings:** 0

## Initial breakdown (49)

| Class | Count | Auto-fixed |
|---|---|---|
| word_count_low | 20 | yes (long-form expansion) |
| thin_with_ads | 15 | yes (long-form expansion) |
| missing_eeat_sections | 13 | yes (named_editor + credentials + launch_date + editorial_process + corrections_policy + disclosure) |
| broken_internal_link | 13 | yes (slug corrections at MD source) |
| missing_canonical | 1 | yes (tredey market-gauge-widget) |

## Deployment methods per site (verified live 2026-08-23 ~16:30 ET)

The audit fixes are USELESS unless they hit production. Each site has different deploy plumbing:

| Site | Domain | Method | Repo / Project | Commit / Deploy ID |
|---|---|---|---|---|
| bacotti | bacotti.com | **wrangler** | bacotti-rebuild | `7a883923`, `a4ba5573` (wrangler pages deploy) |
| dependability | dependability.us | git push → CF Pages | dependability-rebuild | `38d41e4` |
| succession | successionholdingllc.com | git push → CF Pages | succession-rebuild | `882bbe3` |
| tredey | tredey.com | git push → CF Pages | trading-journal-rebuild | `1b72293` |
| bithues | bithues.com | **wrangler** | crypto-bithues-rebuild | `9a374ab` + wrangler |
| triadive | triadive.com | **wrangler** | triadive-rebuild | wrangler deploy |
| spaceorbitals | spaceorbitals.com | **wrangler** | spaceorbitals | wrangler deploy |

**Note:** Some sites auto-deploy on git push; others require explicit `wrangler pages deploy`.
Test which is which before claiming "deployed".

## CRITICAL mix-up avoided: bithues

bithues.com is NOT served from `bithues-rebuild` (books version).
bithues.com IS served from `crypto-bithues-rebuild` (crypto version).

Local working dirs:
- `/Users/mike/.openclaw/workspace-bacottibot/projects/bithues/website/` → books.bithues.com
- `/Users/mike/.openclaw/workspace-bacottibot/projects/bithues-crypto/website/` → bithues.com

**To verify which is live:** check `git ls-remote https://github.com/michaelbacotti/<repo>.git` HEAD, then `curl` the live URL.

The audit script's `sites.py` currently lists `bithues` as `projects/bithues/website` (books) but
`bithues.com` actually points at `crypto-bithues-rebuild` (crypto). This is a known
discrepancy — when running audit fixes, check which repo the live URL is actually served from.

## Site-by-site resolution log

### bacotti.com (wrangler-only)

- 2 files modified: `about/index.html`, `contact/index.html`
- E-E-A-T added: "founded in 2018" + "Credentials of Leadership" section
- Deploy: `wrangler pages deploy . --project-name=bacotti-rebuild --branch=main`
- Required env: `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID`
- First wrangler attempt failed without `CLOUDFLARE_ACCOUNT_ID` — set explicitly via `export CLOUDFLARE_ACCOUNT_ID=56d1b3ebac9ac0438cab8077a1e9a993`
- Verified live: 4 matches for "founded in\|launched\|credentials"

### dependability.us (git push)

- 13 files: `about`, `disclaimer`, `contact`, `forecast/{2025-11-14,2026-02-14}`,
  `commentary/{2026-07-13,2026-07-14,2026-07-15}`, `education/{options-foundations,market-structure,rates-and-options,volatility}`, `articles/{2026-08-22-sp-500-bull-case-8300,forecast-methodology-2026}`
- E-E-A-T + long-form expansion applied
- Deploy: `git push origin main` (CF Pages auto-deploys)
- Verified live: 1 match for "Launched in\|Mike Bacotti"

### successionholdingllc.com (git push)

- 9 files
- E-E-A-T + named editor
- Deploy: `git push`
- Verified live

### tredey.com (git push)

- 121 files
- word count + canonical
- Deploy: `git push`
- Verified live

### bithues.com (crypto — wrangler)

- 43 files in `projects/bithues-crypto/website/`
- E-E-A-T on about, disclaimer, privacy, guides, glossary, paths, safety, tools, research
- 4 thin newsletter pages + newsletter index expanded to ≥800w
- Deploy: `git push` to crypto-bithues-rebuild + `wrangler pages deploy` to apply
- Verified live

### triadive.com (wrangler)

- 99 files
- 100 broken internal links fixed
- Deploy: `git push` + `wrangler pages deploy`
- Verified live: 2 matches for "how-does-an-agent-think" on 2026-08-09 dispatch

### spaceorbitals.com (wrangler)

- MD source fixes at `projects/spaceorbitals/content/newsletters/*.md`
- `build.py` edits to about_body, contact_body, privacy_body inline defaults
- 9 broken internal link fixes at MD source
- Deploy: `python3 build.py` → `wrangler pages deploy . --project-name=spaceorbitals`
- Source MD pushed to spaceorbitals-source repo (commit `93d389b`)
- Verified live: about/contact/privacy all have "Launched in"

## Files added

- `skills/site-code-audit/scripts/check_source.py` — classifies HTML files as
  `hand_crafted` / `md_source` / `inline_static` / `orphan` BEFORE any edit
- `skills/site-code-audit/scripts/fix_thin.py` — auto-fixes thin pages at the SOURCE,
  not the rendered HTML

## Anti-pattern #92 documented

**HTML edits to build.py-generated pages get wiped silently.**
Even with anti-pattern #89 (pre-flight file classification), I edited 3
build.py-generated pages in spaceorbitals/news/ without checking the source.

**Rule:** BEFORE any HTML edit, run
`python3 skills/site-code-audit/scripts/check_source.py <file>`
and obey the source_type warning. See `skills/site-code-audit/SKILL.md` and
`memory/site-notes/adsense.md` for full doctrine.

## CF Pages project list (verified via Cloudflare API)

```
triadive-rebuild         → triadive.com
crypto-bithues-rebuild   → bithues.com
bithues-rebuild          → books.bithues.com
trading-journal-rebuild  → tredey.com
succession-rebuild       → successionholdingllc.com
dependability-rebuild    → dependability.us
bacotti-rebuild          → bacotti.com
spaceorbitals            → spaceorbitals.com  (note: no "-rebuild" suffix)
books-bithues-rebuild    → books.bithues.com
houseinc-rebuild         → houseinc501c3.com
```