# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup: camera names and locations, SSH hosts and aliases, preferred TTS voices, speaker/room names, device nicknames, anything environment-specific.

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.

## Related

- [Agent workspace](/concepts/agent-workspace)

---

## Cloudflare Pages deploy — by site

**Don't assume "git push" deploys.** Each site has different plumbing. Test before claiming live.

### Sites that auto-deploy on `git push origin main`

- **dependability.us** — push to `michaelbacotti/dependability-rebuild.git`
- **successionholdingllc.com** — push to `michaelbacotti/succession-rebuild.git`
- **tredey.com** — push to `michaelbacotti/trading-journal-rebuild.git`

These repos trigger CF Pages build on push.

### Sites that need `wrangler pages deploy`

- **bacotti.com** — `wrangler pages deploy entities/bacotti-inc/website --project-name=bacotti-rebuild`
- **bithues.com** (crypto) — `wrangler pages deploy projects/bithues-crypto/website --project-name=crypto-bithues-rebuild`
- **triadive.com** — `wrangler pages deploy projects/triadive/website --project-name=triadive-rebuild`
- **spaceorbitals.com** — `wrangler pages deploy projects/spaceorbitals/spaceorbitals --project-name=spaceorbitals` (note: no `-rebuild` suffix!)

These projects use **direct API upload only** — git push does NOT trigger deploy.
After wrangler upload, wait ~30s for CF Pages edge cache to propagate.

### Required env vars for wrangler

```bash
source /Users/mike/.openclaw/workspace-bacottibot/.openclaw/tmp/cf-token.env
export CLOUDFLARE_ACCOUNT_ID="56d1b3ebac9ac0438cab8077a1e9a993"
```

Both are required. Without `CLOUDFLARE_ACCOUNT_ID`, wrangler errors with
"Failed to automatically retrieve account IDs for the logged in user."

### CF Pages project list (for sanity-check before deploying)

```bash
curl -s "https://api.cloudflare.com/client/v4/accounts/56d1b3ebac9ac0438cab8077a1e9a993/pages/projects" \
  -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" | jq '.result[].name'
```

Returns: triadive-rebuild, crypto-bithues-rebuild, bithues-rebuild, trading-journal-rebuild,
succession-rebuild, dependability-rebuild, bacotti-rebuild, **spaceorbitals** (not spaceorbitals-rebuild!),
books-bithues-rebuild, houseinc-rebuild.

### Critical: which bithues repo is which

- `michaelbacotti/bithues-rebuild.git` → books.bithues.com (books reviews)
- `michaelbacotti/crypto-bithues-rebuild.git` → **bithues.com** (crypto education)
- `michaelbacotti/books-bithues-rebuild.git` → books.bithues.com (alternative books deploy)

The audit script's `sites.py` lists `bithues` as `projects/bithues/website` (books) but
**the live bithues.com is the crypto version at `projects/bithues-crypto/website/`**.

If you're fixing bithues.com content, edit `projects/bithues-crypto/website/`, not
`projects/bithues/website/`. Verify with: `curl -s https://bithues.com/about/ | grep "crypto"`.

### spaceorbitals deploy is two-step

1. Edit MD sources at `projects/spaceorbitals/content/{articles,news,newsletters,gear,reviews}/`
2. Run `python3 projects/spaceorbitals/spaceorbitals/build.py` to regenerate HTML
3. `wrangler pages deploy projects/spaceorbitals/spaceorbitals --project-name=spaceorbitals`

The git repo at `michaelbacotti/spaceorbitals-source.git` tracks MD sources but does NOT
auto-deploy to CF Pages. It's just for source version control.

## Anti-pattern #92 reminder

**HTML edits to build.py-generated pages get wiped silently.**

Before ANY HTML edit, run:
```bash
python3 skills/site-code-audit/scripts/check_source.py <file>
```

If it returns `md_source` or `inline_static`, edit the source (MD or build.py), not the HTML.


---

## Quality gate for cron-generated content

After 2026-08-23 upgrades, every cron pipeline that renders HTML from MD source bakes an E-E-A-T block into the build template (anti-pattern #89 wipe fix). Five sites covered:

| Site | Constant | Injection point |
|---|---|---|
| bithues.com | `EEAT_BLOCK` in `projects/bithues-crypto/bithues-build/build.py` | `render_newsletter_article()` |
| dependability.us | `DEPENDABILITY_EEAT_BLOCK` | `article_page_html()` |
| successionholdingllc.com | `SUCCESSION_EEAT_BLOCK` | `render_issue_page()` |
| tredey.com | `TREDEY_EEAT_BLOCK` | `build_article_page()` |
| spaceorbitals.com | `SPACEORBITALS_EEAT_BLOCK` | `render_page()` |

**Verify after rebuild:** `python3 skills/site-code-audit/scripts/verify_published.py --site <key>`

The verifier checks:
- Word count ≥ 400 (FAIL) / ≥ 800 (WARN) / prefer 1200
- 5-section E-E-A-T recipe present (named_editor, credentials, launch_date, editorial_process, corrections_policy, disclosure)
- AdSense `<ins>` tag present
- canonical URL present
- anti-pattern #89: hand-edited E-E-A-T (not in `.eeat-block` wrapper) gets flagged so it doesn't get wiped on next cron

**For autonomous-content pipeline** (`autonomous-content-daily` cron): `publish.py` now calls `verify_built_html()` after build and aborts on failure. So a thin / non-compliant article never reaches production.
