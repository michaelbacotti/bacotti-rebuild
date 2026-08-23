# Site Code Audit — 2026-08-22

**Sites audited:** bacotti, wildwood-press, bithues, bithues-crypto, dependability, spaceorbitals, succession, tredey, triadive
**Findings:** 86 total | **Auto-fixed:** 0 | **Needs attention:** 3

## Severity breakdown

- **critical:** 1
- **high:** 2
- **medium:** 49
- **low:** 34

## 🚨 Needs attention

- `bithues-crypto` **live_unreachable** (critical) — https://bithues-crypto.com: apex fetch failed: error: URLError: <urlopen error [Errno 8] nodename nor servname provided, or not known>
- `bacotti` **live_non_200** (high) — https://www.bacotti.com: www returned HTTP 522
- `tredey` **live_non_200** (high) — https://www.tredey.com: www returned HTTP 522

## 📋 Other findings

### dependability (62)

- `broken_internal_link` (medium) — internal href '/education/rates-options/' does not resolve to a known page or asset
- `broken_internal_link` (medium) — internal href '/articles/tlt-new-bond-regime/' does not resolve to a known page or asset
- `broken_internal_link` (medium) — internal href '/articles/calendar-spreads-and-theta-collection/' does not resolve to a known page or asset
- `broken_internal_link` (medium) — internal href '/articles/calendar-spreads-and-theta-collection/' does not resolve to a known page or asset
- `broken_internal_link` (medium) — internal href '/articles/calendar-spreads-and-theta-collection/' does not resolve to a known page or asset
- `broken_internal_link` (medium) — internal href '/articles/calendar-spreads-and-theta-collection/' does not resolve to a known page or asset
- `duplicate_h1` (low) — 2 <h1> tags on one page (best practice: 1)
- `duplicate_h1` (low) — 2 <h1> tags on one page (best practice: 1)
- `duplicate_h1` (low) — 2 <h1> tags on one page (best practice: 1)
- `duplicate_h1` (low) — 2 <h1> tags on one page (best practice: 1)
- …and 52 more

### spaceorbitals (14)

- `missing_canonical` (medium) — page missing <link rel=canonical>
- `broken_internal_link` (medium) — internal href '/articles/meteor-shower-photography-guide/' does not resolve to a known page or asset
- `broken_internal_link` (medium) — internal href '/articles/astrophotography-basics/' does not resolve to a known page or asset
- `broken_internal_link` (medium) — internal href '/articles/iss/' does not resolve to a known page or asset
- `broken_internal_link` (medium) — internal href '/articles/spacex-reusability-2026/' does not resolve to a known page or asset
- `broken_internal_link` (medium) — internal href '/newsletters/2026-08-17-orbital-daily-tracker-four-launches-seven-days-august-17/' does not resolve to a known page or asset
- `broken_internal_link` (medium) — internal href '/newsletters/2026-08-20-orbital-daily-tracker-saturn-venus-four-planets-tonight/' does not resolve to a known page or asset
- `broken_internal_link` (medium) — internal href '/articles/starlink/' does not resolve to a known page or asset
- `broken_internal_link` (medium) — internal href '/articles/spacex-starship-2026/' does not resolve to a known page or asset
- `broken_internal_link` (medium) — internal href '/newsletters/2026-08-16-weekly-read-when-operations-outrun-policy/' does not resolve to a known page or asset
- …and 4 more

### tredey (3)

- `duplicate_h1` (low) — 2 <h1> tags on one page (best practice: 1)
- `duplicate_h1` (low) — 2 <h1> tags on one page (best practice: 1)
- `missing_canonical` (medium) — page missing <link rel=canonical>

### triadive (4)

- `broken_internal_link` (medium) — internal href '/articles/concepts/what-is-llm/' does not resolve to a known page or asset
- `broken_internal_link` (medium) — internal href '/articles/concepts/cron-skills-loops-lobsters-workboard/' does not resolve to a known page or asset
- `broken_internal_link` (medium) — internal href '/articles/concepts/cron-vs-heartbeat/' does not resolve to a known page or asset
- `broken_internal_link` (medium) — internal href '/articles/concepts/evaluation-safety-governance/' does not resolve to a known page or asset

