# Dependability — Owned Files Manifest

**Owning workdesk (planned):** `agent:main:dependability-website-manager`
**Owning workboard board:** `website-dependability`
**Domain:** https://dependability.us
**Deploy method:** `git push` to `michaelbacotti/dependability-rebuild.git` (auto-deploys via CF Pages)

**Created:** 2026-08-26
**Status:** workdesk session NOT YET CONFIGURED at gateway level.

## Files you own (website layer — dependability.us)

### Source-of-truth (edit these)
- `entities/dependability/content/morning-analysis/*.md` — morning brief MDs (34 files: 2026-07-13 to 2026-08-26)
- `entities/dependability/dependability-may26/build.py` — site build script
- `entities/dependability/dependability-may26/build_morning.py` — morning brief index builder
- `entities/dependability/dependability-may26/restore_md_sources.py` — backfill empty MDs from HTML (idempotent)
- `entities/dependability/dependability-may26/stub_morning.py` — placeholder brief generator
- `entities/dependability/dependability-may26/_template.html`
- `entities/dependability/dependability-may26/_article_template.html`

### Forecast / article content
- `entities/dependability/website/forecast/**/*.html` — daily/weekly S&P 500 forecast pages (hand-crafted, no MD source)
- `entities/dependability/website/commentary/**/*.html` — morning analysis per-date pages
- `entities/dependability/website/articles/**/*.html` — long-form articles
- `entities/dependability/website/trade-log/**/*.html` — trade log
- `entities/dependability/website/strategies/**/*.html` — strategy articles
- `entities/dependability/website/methodology/**/*.html`
- `entities/dependability/website/macro/**/*.html`
- `entities/dependability/website/sectors/**/*.html`
- `entities/dependability/website/education/**/*.html`
- `entities/dependability/website/signalhouse/**/*.html`

### Site shell
- `entities/dependability/website/_template.html`
- `entities/dependability/website/_article_template.html`
- `entities/dependability/website/_redirects`
- `entities/dependability/website/_adsense.txt`
- `entities/dependability/website/style.css`
- `entities/dependability/website/nav.js`
- `entities/dependability/website/footer.js`
- `entities/dependability/website/sitemap.xml`
- `entities/dependability/website/ads.txt`
- `entities/dependability/website/_SITE-MEMORY.md` — site-specific memory
- `entities/dependability/website/PROJECT_INDEX.md`
- `entities/dependability/website/PROJECT_PLAYBOOK.md`
- `entities/dependability/website/TONE.md`
- `entities/dependability/website/WEBSITE_TEMPLATE.md`

### Crons you own (all currently bound to ghost session)

| Cron ID | Schedule | What it does |
|---|---|---|
| `6437c795-bd62-43a2-9a3d-1f8e8948684e` | Mon-Fri 05:55 ET | Morning brief (pre-market) |
| `34e3fde2-e465-488e-adc4-6cc0224bdc92` | Mon-Fri 06:00 ET | **Backstop** for morning brief (silent on success) |
| `05878b6c-6cb6-46b7-b33b-ceba7e28a686` | Mon-Fri 13:55 ET | Fed Rate decision banner |
| `5b45775c-58e9-4b9c-8d9d-b5f5fc0ca8a9` | Mon-Fri 08:32 ET | Breaking news morning economic data |
| `99ff0c15-3616-4fdb-abce-a3ae1a6b3f3f` | Mon-Fri 17:00 ET | Daily S&P 500 forecast |
| `48a00e94-b19c-4635-aba9-5665d224f878` | Sun 17:00 ET | Weekly S&P 500 forecast |
| `b1695aec-e29a-442f-b936-64c62e53d3d2` | 19:30 daily | Forecast watchdog |
| `67f56636-625c-4c0f-a7ac-97989dbb101a` | 15:30 M-F | Publishing watchdog afternoon |
| `7054398f-***` (id partially obscured) | 09:30 M-F | Publishing watchdog morning |

## Files you do NOT own

- `entities/dependability/notes/` — dependability-xo workdesk
- `entities/dependability/tax/` — dependability-xo workdesk
- `entities/dependability/.forecast-data-verified.json` — dependability-xo workdesk
- `entities/dependability/.openclaw/` — dependability-xo workdesk

**Important:** The **dependability-xo** workdesk owns the **business / accounting** layer (P&L, Quicken, profit-share). The **dependability-website-manager** owns the **website** layer. These are separate workdesks.

## Recent incidents on your site

- **2026-08-26:** Main morning brief cron had been failing silently for 6 weeks (writing 0-byte MDs). Live HTML was fine but the source-of-truth layer was orphaned. Fixed in main session; backstop cron `34e3fde2` now catches future failures. Root cause of 0-byte MDs still under investigation (card `648b070a`).

## Bootstrap status (2026-08-26)

- [ ] Gateway agent `dependability-website-manager` configured
- [ ] WM priming cron created (one-shot at + delivery.mode=none)
- [ ] WM's tools-allow profile set (filesystem + cron + workboard for dependability paths)
- [ ] WM's first workboard card posted: "I am dependability-website-manager, here's my scope"
- [ ] All 9 dependability cron jobs re-bound to WM session

## How to bootstrap the WM at gateway level

The OpenClaw config needs an entry like:

```toml
[agents.dependability-website-manager]
model = "minimax/MiniMax-M2.7"
fallbacks = ["minimax/MiniMax-M3"]
description = "Dependability (dependability.us) website manager. Owns entities/dependability/{content,dependability-may26,website}/. Deploys via git push to dependability-rebuild.git. Does NOT edit other sites or do entity bookkeeping."
```

Once configured and primed, the workdesk owns dependability.us end-to-end. Until then, the main session handles Dependability website fixes.