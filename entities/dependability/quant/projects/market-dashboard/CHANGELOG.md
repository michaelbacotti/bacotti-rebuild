# Market Dashboard — Changelog

All notable changes to the dashboard project, newest first.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] — 2026-09-07

### Added
- **Live production URL**: `https://dashboard.dependability.us`
- **CF Pages project**: `dependability-dashboard` (account `56d1b3ebac9ac0438cab8077a1e9a993`)
- **PIN-gate Cloudflare Pages Function** at `functions/_middleware.js`
- **Single-PIN auth model** with bcrypt-equivalent (SHA-256 + salt) hash, HMAC-signed session cookies
- **Rate limiting** (5 wrong PIN attempts / 10 min = 15-min IP lockout) — protects against brute force
- **Cookie-based session** (HTTP-only, Secure, SameSite=Strict, 30-day expiry)
- **Documentation suite**:
  - `README.md` — project overview, ownership, what it owns/doesn't own
  - `CHANGELOG.md` — this file
  - `DEPLOY.md` — deploy procedure (local build → Wrangler → CF Pages)
  - `ACCESS.md` — authorized users, PIN rotation policy, security model
- **Deploy scripts**:
  - `scripts/build-and-deploy.sh` — one-shot full deploy
  - `scripts/update-content.sh` — content-only refresh (HTML changes only)

### Security
- PIN is never stored in plain text — `ACCESS_CODE_HASH` env var contains SHA-256(SALT+PIN)
- `SESSION_SECRET` env var (32-byte random hex) signs session cookies via HMAC-SHA256
- No external auth dependencies (no email, no OAuth, no third-party IdP)
- Brute-force protection via IP-based rate limiting in Worker
- Cookie has SameSite=Strict to prevent CSRF

### Known limitations
- IP-based rate limiting uses in-memory state (per Worker isolate). Sufficient for a single-user dashboard, but if you ever scale to multiple users behind different IPs, upgrade to Workers KV
- Single PIN only. Adding family later requires Worker code change (5 lines)
- Custom domain `dashboard.dependability.us` requires Mike to add a CNAME record in the `dependability.us` zone (Pages token lacks Zone:Edit scope)

### Cross-references
- Quant workdesk scope: `entities/dependability/quant/OWNED_FILES.md`
- Build source: `entities/dependability/quant/scripts/build_market_dashboard_html.py`
- This version ships dashboard methodology v9 (benchmark decoupling + event-aware Sentiment/Catalyst)
