# Market Dashboard Project

**Project of:** Dependability Holdings, LLC (entity)
**Owned by:** Quant workdesk (`entities/dependability/quant/`)
**Authorized users (current):** Mike Bacotti (`michaelbacotti@gmail.com`) — sole user
**Live URL:** <https://dashboard.dependability.us>
**CF Pages project:** `dependability-dashboard`
**Status:** Active — production

---

## What this is

An interactive single-page market dashboard that scores and ranks 3 benchmarks, 11 sector ETFs, and 28 sector-leader candidates daily. Produces research-only output (no trade placement, no broker access, no key exposure).

The dashboard is the public-facing *delivery layer* for the quant workdesk's ClawRank scoring pipeline. All research logic lives in `entities/dependability/quant/scripts/`; this project folder is just the shipping and packaging layer.

## How it's organized

```
projects/market-dashboard/
├── README.md            ← this file
├── CHANGELOG.md         ← shipped version history
├── DEPLOY.md            ← deploy procedure (build + Wrangler)
├── ACCESS.md            ← authorized users, PIN rotation, security model
├── wrangler.toml        ← CF Pages config (project name, build, env)
├── package.json         ← JS deps (none currently — pure CF runtime)
├── functions/
│   └── _middleware.js   ← Cloudflare Pages Function: PIN gate + cookie session
├── public/
│   └── index.html       ← deploy artifact (copy of canonical dashboard)
├── scripts/
│   ├── build-and-deploy.sh  ← one-shot: build → stage → wrangler pages deploy
│   └── update-content.sh    ← content-only refresh (no config change)
└── .gitignore           ← excludes public/index.html (deploy artifact, regenerable)
```

## Source of truth

The canonical dashboard HTML lives at `entities/dependability/quant/reports/market-dashboard.html` (always latest). This project's `public/index.html` is a deploy-time copy. See `DEPLOY.md` for the build pipeline.

## What this project owns vs doesn't own

**Owns:**
- The `dashboard.dependability.us` URL and CF Pages project
- The PIN-gate Worker logic and access policy
- This folder's contents (docs, deploy scripts, Worker source)

**Does NOT own:**
- The ClawRank scoring logic (lives in `quant/scripts/build_clawrank_features.py`)
- The dashboard HTML template and styling (lives in `quant/scripts/build_market_dashboard_html.py`)
- Sector universe, scoring weights, factor definitions (lives in `quant/config/clawrank.yaml`)
- Anything related to entity website `dependability.us`

## Quick start (for authorized users)

1. Visit <https://dashboard.dependability.us>
2. Enter your PIN (stored in your password manager)
3. Dashboard loads; cookie valid 30 days
4. See `ACCESS.md` for PIN handling rules

## Maintenance

- Daily refresh: run `bash scripts/update-content.sh` from this folder
- Full rebuild + config change: see `DEPLOY.md`
- Add/remove authorized user: see `ACCESS.md`
- Rotate PIN: see `ACCESS.md`

## Related

- `entities/dependability/quant/scripts/build_market_dashboard_html.py` — produces the HTML
- `entities/dependability/quant/scripts/build_clawrank_features.py` — produces ClawRank features
- `entities/dependability/quant/OWNED_FILES.md` — quant workdesk scope
- `entities/dependability/quant/projects/market-dashboard/CHANGELOG.md` — version history
- `entities/dependability/quant/projects/market-dashboard/DEPLOY.md` — deploy procedure
- `entities/dependability/quant/projects/market-dashboard/ACCESS.md` — access policy
