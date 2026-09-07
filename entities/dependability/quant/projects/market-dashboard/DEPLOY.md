# Deploy Procedure

## Architecture

```
Local workstation                    Cloudflare
─────────────────                    ──────────
quant/scripts/build_*.py            dependability-dashboard (Pages project)
       │                                    │
       ▼                                    │
reports/market-dashboard.html ───────────►  │
       │                                    ▼
       │                          public/index.html served at
       │                          *.pages.dev + dashboard.dependability.us
       ▼
projects/market-dashboard/
  public/index.html                     ▲
       │                                │  Every request hits
       ▼                                │  functions/_middleware.js
scripts/build-and-deploy.sh ──► wrangler pages deploy   ──► Auth check
                                                           ▼
                                                  Pass → serve public/
                                                  Fail → PIN entry page
```

## Prerequisites

- Node.js + Wrangler (`brew install node` then `npm i -g wrangler`)
- Cloudflare API token with `Pages Write` scope (stored at `~/.openclaw/credentials/cf-pages-deploy-token.json`)
- Account ID: `56d1b3ebac9ac0438cab8077a1e9a993` (env: `CLOUDFLARE_ACCOUNT_ID`)
- Token value: from credential file (env: `CLOUDFLARE_API_TOKEN`)
- Python 3.11+ with the quant venv active (for `build_market_dashboard_html.py`)

## One-time setup (already done in this project)

1. Pages project created: `wrangler pages project create dependability-dashboard --production-branch=main`
2. Custom domain attached: `dashboard.dependability.us` (pending CNAME — see DNS section below)
3. Env vars set on Pages project:
   - `ACCESS_CODE_HASH` — SHA-256 of PIN with fixed salt
   - `SESSION_SECRET` — 32-byte hex, signs session cookies
4. Token rotation policy: see `ACCESS.md`

## Daily refresh — content only

When you just want to push the latest dashboard HTML (most common):

```bash
cd entities/dependability/quant/projects/market-dashboard
bash scripts/update-content.sh
```

What it does:
1. Runs `scripts/build_market_dashboard_html.py` from the quant workdesk
2. Copies `reports/market-dashboard.html` → `public/index.html` here
3. `wrangler pages deploy public --project-name=dependability-dashboard`
4. Returns the deploy URL (you'll see "Uploaded 1 file" in the Wrangler output)

Takes ~90 seconds end-to-end (60s for the build, 30s for Pages upload).

## Full deploy — config + content

When you change `functions/_middleware.js`, `wrangler.toml`, or env vars:

```bash
cd entities/dependability/quant/projects/market-dashboard
bash scripts/build-and-deploy.sh
```

Same as above plus re-applies any `wrangler.toml` changes (Pages picks them up on next deploy).

## DNS — required for `dashboard.dependability.us` to resolve

The Pages custom domain was attached via API but the API token lacks `Zone:Edit` scope, so the CNAME record was not auto-created. Mike adds it manually in the Cloudflare dashboard:

| Field | Value |
|---|---|
| Type | CNAME |
| Name | `dashboard` |
| Target | `dependability-dashboard.pages.dev` |
| Proxy | Proxied (orange cloud ON) |

After saving, wait ~30s for CF to validate. Pages will show `status: active` and HTTPS will provision automatically (Google CA).

## Env vars

| Name | Purpose | How to rotate |
|---|---|---|
| `ACCESS_CODE_HASH` | SHA-256(SALT + PIN), where SALT is hardcoded in `functions/_middleware.js` | Run `scripts/hash-pin.js` with new PIN, then `wrangler pages secret put ACCESS_CODE_HASH --project-name=dependability-dashboard` |
| `SESSION_SECRET` | HMAC key for cookie signing | `wrangler pages secret put SESSION_SECRET --project-name=dependability-dashboard` (invalidates all existing cookies, users re-enter PIN) |

To inspect current env vars: `wrangler pages secret list --project-name=dependability-dashboard`

## Rollback

If a deploy goes wrong:

```bash
# List recent deployments
wrangler pages deployments list --project-name=dependability-dashboard

# Rollback to a specific deployment
wrangler pages deployments rollback <deployment-id> --project-name=dependability-dashboard
```

Or via the CF dashboard: Workers & Pages → dependability-dashboard → Deployments → click a prior deployment → "Rollback to this deploy".

## First-time deploy checklist

- [ ] `wrangler login` (or set `CLOUDFLARE_API_TOKEN` env var)
- [ ] Verify Pages project exists: `wrangler pages project list | grep dependability-dashboard`
- [ ] Verify env vars set: `wrangler pages secret list --project-name=dependability-dashboard`
- [ ] Verify custom domain attached: `wrangler pages domains list --project-name=dependability-dashboard`
- [ ] Run `bash scripts/update-content.sh`
- [ ] Curl test: `curl -i https://dependability-dashboard.pages.dev/` (expect 200 with PIN page, NOT dashboard HTML)
- [ ] Curl test with cookie: visit `https://dashboard.dependability.us` in browser, enter PIN, verify cookie works
