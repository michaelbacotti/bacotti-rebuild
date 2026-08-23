---
type: synthesis
title: Cron Pipelines — Per-Site Map
created: 2026-08-23
confidence: 0.92
status: durable
sources:
  - TOOLS.md (Cloudflare Pages deploy section)
  - memory/memory/code-audit-2026-08-23.md
  - skills/site-code-audit/references/quality-standards.md
---

# Cron Pipelines — Per-Site Map

**Last updated:** 2026-08-23 (cron-quality upgrade)

Map of all 8 publishing sites: what cron pipeline drives content, what build.py is, where EEAT_BLOCK lives, and how content gets deployed.

## Two deploy mechanisms (do not confuse)

### Git-push sites (CF Pages auto-deploy on push)

| Site | Git repo | CF Pages project |
|---|---|---|
| dependability.us | `michaelbacotti/dependability-rebuild.git` | `dependability-rebuild` |
| successionholdingllc.com | `michaelbacotti/succession-rebuild.git` | `succession-rebuild` |
| tredey.com | `michaelbacotti/trading-journal-rebuild.git` | `trading-journal-rebuild` |

These repos trigger CF Pages build on `git push origin main`. The commit IS the deploy.

### Wrangler-required sites (manual API upload)

| Site | Wrangler command | CF Pages project |
|---|---|---|
| bacotti.com | `wrangler pages deploy entities/bacotti-inc/website --project-name=bacotti-rebuild` | `bacotti-rebuild` |
| bithues.com | `wrangler pages deploy projects/bithues-crypto/website --project-name=crypto-bithues-rebuild` | `crypto-bithues-rebuild` |
| triadive.com | `wrangler pages deploy projects/triadive/website --project-name=triadive-rebuild` | `triadive-rebuild` |
| spaceorbitals.com | `wrangler pages deploy projects/spaceorbitals/spaceorbitals --project-name=spaceorbitals` ⚠️ no `-rebuild` suffix | `spaceorbitals` |

These projects use direct API upload only — `git push` does NOT trigger deploy. After wrangler upload, wait ~30s for CF Pages edge cache to propagate.

### Required env vars for wrangler

```bash
source /Users/mike/.openclaw/workspace-bacottibot/.openclaw/tmp/cf-token.env
export CLOUDFLARE_ACCOUNT_ID="56d1b3ebac9ac0438cab8077a1e9a993"
```

Both required. Without `CLOUDFLARE_ACCOUNT_ID`, wrangler errors with "Failed to automatically retrieve account IDs for the logged in user."

## Build pipeline (cron-rendered sites)

For sites with `build.py`, content flows:

```
MD source (content/articles/*.md)
  ↓ cron (varies by site)
build.py (renders HTML, interpolates EEAT_BLOCK + SITE_EEAT_BLOCK constant)
  ↓ verify_published.py (post-build gate)
  ↓ (passes →) wrangler pages deploy OR git push
CF Pages edge (live)
```

### Build.py + MD source map

| Site | Build.py | MD source dir | EEAT_BLOCK constant |
|---|---|---|---|
| spaceorbitals | `projects/spaceorbitals/spaceorbitals/build.py` | `projects/spaceorbitals/content/{articles,news,reviews,gear,newsletters}/*.md` | `SPACEORBITALS_EEAT_BLOCK` |
| triadive | `projects/triadive/triadive-build/build.py` | `projects/triadive/content/{articles,pages}/*.md` | `TRIADIVE_EEAT_BLOCK` |
| succession newsletters | `entities/succession/website/build.py` | `entities/succession/website/content/newsletters/*.md` | `SUCCESSION_EEAT_BLOCK` |
| dependability | `entities/dependability/dependability-may26/build.py` | n/a (hand-crafted article templates) | `DEPENDABILITY_EEAT_BLOCK` |
| bithues | `projects/bithues-crypto/bithues-build/build.py` | n/a (newsletter templates) | `EEAT_BLOCK` |
| tredey | `projects/tredey/trading-journal-build/build.py` | n/a (article/forecast templates) | `TREDEY_EEAT_BLOCK` |

### Static (no build.py) sites

- **bacotti.com** — hand-crafted static HTML in `entities/bacotti-inc/website/`
- **wildwood-press** — handled via bacotti ecosystem

## Critical bithues repo disambiguation

- `michaelbacotti/bithues-rebuild.git` → books.bithues.com (books reviews)
- `michaelbacotti/crypto-bithues-rebuild.git` → **bithues.com** (crypto education)
- `michaelbacotti/books-bithues-rebuild.git` → books.bithues.com (alternative books deploy)

The audit script's `sites.py` lists `bithues` as `projects/bithues/website` (books), but **the live bithues.com is the crypto version at `projects/bithues-crypto/website/`**. If editing bithues.com content, edit `projects/bithues-crypto/website/`, not `projects/bithues/website/`. Verify with: `curl -s https://bithues.com/about/ | grep "crypto"`.

## spaceorbitals deploy is two-step

1. Edit MD sources at `projects/spaceorbitals/content/{articles,news,newsletters,gear,reviews}/`
2. Run `python3 projects/spaceorbitals/spaceorbitals/build.py` to regenerate HTML
3. `wrangler pages deploy projects/spaceorbitals/spaceorbitals --project-name=spaceorbitals`

The git repo at `michaelbacotti/spaceorbitals-source.git` tracks MD sources but does NOT auto-deploy to CF Pages. It's just for source version control.

## Verification flow (post-deploy)

After every deploy, run:

```bash
# Confirm E-E-A-T survived (use ?nocache=<random> to bypass CDN)
curl -s "https://<site>/<path>?nocache=$RANDOM" | grep -c "eeat-block"

# Confirm AdSense ins tags present
curl -s "https://<site>/<path>?nocache=$RANDOM" | grep -c "adsbygoogle"

# Confirm canonical URL present
curl -s "https://<site>/<path>?nocache=$RANDOM" | grep -c 'rel="canonical"'

# Re-run verify_published locally for the report
python3 skills/site-code-audit/scripts/verify_published.py --site <key> --quiet
```

## Related

- `wiki/site-quality-standards.md` — quality gate + E-E-A-T recipe
- `TOOLS.md` — raw deploy command cheat sheet (single source of truth)
- `skills/site-code-audit/SKILL.md` — full audit pipeline
