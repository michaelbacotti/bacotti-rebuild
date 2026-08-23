# Site Code Audit — 2026-08-23

**Sites audited:** bacotti, wildwood-press, bithues, dependability, spaceorbitals, succession, tredey, triadive
**Findings:** 199 total | **Auto-fixed:** 0 | **Needs attention:** 72

## Severity breakdown

- **critical:** 28
- **high:** 123
- **medium:** 47
- **low:** 1

## 🚨 Needs attention

- `bacotti` **word_count_low** (high) — entities/bacotti-inc/website/about/index.html: 183w (threshold 800w for legal_umbrella)
- `bacotti` **word_count_low** (high) — entities/bacotti-inc/website/contact/index.html: 37w (threshold 800w for legal_umbrella)
- `bithues` **missing_eeat_sections** (high) — projects/bithues/website/about/index.html: /legal/-class page missing E-E-A-T sections: credentials, editorial_process, disclosure
- `bithues` **word_count_low** (high) — projects/bithues/website/articles/2/index.html: 316w (threshold 800w for content_article)
- `bithues` **word_count_low** (high) — projects/bithues/website/articles/3/index.html: 312w (threshold 800w for content_article)
- `bithues` **word_count_low** (high) — projects/bithues/website/articles/4/index.html: 343w (threshold 800w for content_article)
- `bithues` **word_count_low** (high) — projects/bithues/website/articles/5/index.html: 291w (threshold 800w for content_article)
- `bithues` **word_count_low** (high) — projects/bithues/website/articles/6/index.html: 257w (threshold 800w for content_article)
- `bithues` **missing_eeat_sections** (high) — projects/bithues/website/contact/index.html: /legal/-class page missing E-E-A-T sections: credentials, launch_date, editorial_process
- `bithues` **missing_eeat_sections** (high) — projects/bithues/website/privacy/index.html: /legal/-class page missing E-E-A-T sections: credentials, launch_date, editorial_process, disclosure
- `bithues` **missing_eeat_sections** (high) — projects/bithues/website/terms/index.html: /legal/-class page missing E-E-A-T sections: credentials, launch_date, corrections_policy, disclosure
- `dependability` **missing_eeat_sections** (high) — entities/dependability/website/about/index.html: /legal/-class page missing E-E-A-T sections: credentials, editorial_process
- `dependability` **word_count_low** (critical) — entities/dependability/website/articles/forecast-methodology-2026/index.html: 763w (threshold 800w for content_article)
- `dependability` **thin_with_ads** (critical) — entities/dependability/website/articles/forecast-methodology-2026/index.html: page has 3 ad slot(s) but only 763w (AdSense red flag)
- `dependability` **word_count_low** (critical) — entities/dependability/website/articles/index.html: 140w (threshold 800w for content_article)
- `dependability` **thin_with_ads** (critical) — entities/dependability/website/articles/index.html: page has 3 ad slot(s) but only 140w (AdSense red flag)
- `dependability` **word_count_low** (critical) — entities/dependability/website/commentary/2026-07-13/index.html: 497w (threshold 800w for content_article)
- `dependability` **thin_with_ads** (critical) — entities/dependability/website/commentary/2026-07-13/index.html: page has 2 ad slot(s) but only 497w (AdSense red flag)
- `dependability` **word_count_low** (critical) — entities/dependability/website/commentary/2026-07-14/index.html: 564w (threshold 800w for content_article)
- `dependability` **thin_with_ads** (critical) — entities/dependability/website/commentary/2026-07-14/index.html: page has 2 ad slot(s) but only 564w (AdSense red flag)
- `dependability` **word_count_low** (critical) — entities/dependability/website/commentary/2026-07-15/index.html: 665w (threshold 800w for content_article)
- `dependability` **thin_with_ads** (critical) — entities/dependability/website/commentary/2026-07-15/index.html: page has 2 ad slot(s) but only 665w (AdSense red flag)
- `dependability` **word_count_low** (critical) — entities/dependability/website/contact/index.html: 597w (threshold 800w for legal_umbrella)
- `dependability` **thin_with_ads** (critical) — entities/dependability/website/contact/index.html: page has 1 ad slot(s) but only 597w (AdSense red flag)
- `dependability` **missing_eeat_sections** (high) — entities/dependability/website/contact/index.html: /legal/-class page missing E-E-A-T sections: launch_date, editorial_process
- `dependability` **missing_eeat_sections** (high) — entities/dependability/website/disclaimer/index.html: /legal/-class page missing E-E-A-T sections: launch_date, editorial_process, corrections_policy
- `dependability` **word_count_low** (critical) — entities/dependability/website/forecast/2025-11-14/index.html: 504w (threshold 800w for content_article)
- `dependability` **thin_with_ads** (critical) — entities/dependability/website/forecast/2025-11-14/index.html: page has 3 ad slot(s) but only 504w (AdSense red flag)
- `dependability` **word_count_low** (critical) — entities/dependability/website/forecast/2026-02-14/index.html: 631w (threshold 800w for content_article)
- `dependability` **thin_with_ads** (critical) — entities/dependability/website/forecast/2026-02-14/index.html: page has 3 ad slot(s) but only 631w (AdSense red flag)
- `dependability` **missing_eeat_sections** (high) — entities/dependability/website/methodology/index.html: /legal/-class page missing E-E-A-T sections: launch_date
- `dependability` **missing_eeat_sections** (high) — entities/dependability/website/privacy/index.html: /legal/-class page missing E-E-A-T sections: credentials, launch_date, editorial_process
- `dependability` **missing_eeat_sections** (high) — entities/dependability/website/terms/index.html: /legal/-class page missing E-E-A-T sections: credentials, launch_date, editorial_process, corrections_policy
- `dependability` **word_count_low** (critical) — entities/dependability/website/trade-log/index.html: 390w (threshold 800w for content_article)
- `dependability` **thin_with_ads** (critical) — entities/dependability/website/trade-log/index.html: page has 1 ad slot(s) but only 390w (AdSense red flag)
- `spaceorbitals` **word_count_low** (high) — projects/spaceorbitals/spaceorbitals/about/index.html: 22w (threshold 800w for legal_umbrella)
- `spaceorbitals` **word_count_low** (critical) — projects/spaceorbitals/spaceorbitals/articles/hohmann-transfer-explained/index.html: 770w (threshold 800w for content_article)
- `spaceorbitals` **thin_with_ads** (critical) — projects/spaceorbitals/spaceorbitals/articles/hohmann-transfer-explained/index.html: page has 3 ad slot(s) but only 770w (AdSense red flag)
- `spaceorbitals` **word_count_low** (high) — projects/spaceorbitals/spaceorbitals/articles/index.html: 20w (threshold 800w for content_article)
- `spaceorbitals` **word_count_low** (critical) — projects/spaceorbitals/spaceorbitals/articles/leo-economy-2026/index.html: 753w (threshold 800w for content_article)
- `spaceorbitals` **thin_with_ads** (critical) — projects/spaceorbitals/spaceorbitals/articles/leo-economy-2026/index.html: page has 3 ad slot(s) but only 753w (AdSense red flag)
- `spaceorbitals` **word_count_low** (high) — projects/spaceorbitals/spaceorbitals/authors/index.html: 719w (threshold 800w for legal_umbrella)
- `spaceorbitals` **missing_eeat_sections** (high) — projects/spaceorbitals/spaceorbitals/authors/index.html: /legal/-class page missing E-E-A-T sections: launch_date, editorial_process
- `spaceorbitals` **word_count_low** (high) — projects/spaceorbitals/spaceorbitals/contact/index.html: 42w (threshold 800w for legal_umbrella)
- `spaceorbitals` **word_count_low** (high) — projects/spaceorbitals/spaceorbitals/privacy/index.html: 91w (threshold 800w for legal_umbrella)
- `spaceorbitals` **word_count_low** (critical) — projects/spaceorbitals/spaceorbitals/reviews/celestron-nexstar-8se-review/index.html: 782w (threshold 800w for content_article)
- `spaceorbitals` **thin_with_ads** (critical) — projects/spaceorbitals/spaceorbitals/reviews/celestron-nexstar-8se-review/index.html: page has 2 ad slot(s) but only 782w (AdSense red flag)
- `spaceorbitals` **word_count_low** (high) — projects/spaceorbitals/spaceorbitals/reviews/index.html: 16w (threshold 800w for content_article)
- `succession` **missing_eeat_sections** (high) — entities/succession/website/about/index.html: /legal/-class page missing E-E-A-T sections: launch_date
- `succession` **missing_eeat_sections** (high) — entities/succession/website/contact/index.html: /legal/-class page missing E-E-A-T sections: launch_date, editorial_process
- `succession` **missing_eeat_sections** (high) — entities/succession/website/disclaimer/index.html: /legal/-class page missing E-E-A-T sections: launch_date, editorial_process, corrections_policy, disclosure
- `succession` **word_count_low** (critical) — entities/succession/website/privacy/index.html: 785w (threshold 800w for legal_umbrella)
- `succession` **thin_with_ads** (critical) — entities/succession/website/privacy/index.html: page has 2 ad slot(s) but only 785w (AdSense red flag)
- `succession` **missing_eeat_sections** (high) — entities/succession/website/privacy/index.html: /legal/-class page missing E-E-A-T sections: launch_date, editorial_process, corrections_policy, disclosure
- `succession` **missing_eeat_sections** (high) — entities/succession/website/terms/index.html: /legal/-class page missing E-E-A-T sections: launch_date, editorial_process
- `tredey` **missing_eeat_sections** (high) — projects/tredey/website/about/index.html: /legal/-class page missing E-E-A-T sections: launch_date
- `tredey` **missing_eeat_sections** (high) — projects/tredey/website/contact/index.html: /legal/-class page missing E-E-A-T sections: launch_date, editorial_process, disclosure
- `tredey` **missing_eeat_sections** (high) — projects/tredey/website/disclaimer/index.html: /legal/-class page missing E-E-A-T sections: launch_date, editorial_process, corrections_policy
- `tredey` **missing_eeat_sections** (high) — projects/tredey/website/privacy/index.html: /legal/-class page missing E-E-A-T sections: launch_date, editorial_process, disclosure
- `tredey` **missing_eeat_sections** (high) — projects/tredey/website/terms/index.html: /legal/-class page missing E-E-A-T sections: credentials, launch_date, editorial_process
- `triadive` **missing_eeat_sections** (high) — projects/triadive/website/about/index.html: /legal/-class page missing E-E-A-T sections: credentials, launch_date, disclosure
- `triadive` **word_count_low** (high) — projects/triadive/website/articles/field-notes/index.html: 394w (threshold 800w for content_article)
- `triadive` **word_count_low** (high) — projects/triadive/website/articles/lessons/index.html: 283w (threshold 800w for content_article)
- `triadive` **word_count_low** (critical) — projects/triadive/website/articles/workflows/daily-check-in-loop/index.html: 701w (threshold 800w for content_article)
- `triadive` **thin_with_ads** (critical) — projects/triadive/website/articles/workflows/daily-check-in-loop/index.html: page has 1 ad slot(s) but only 701w (AdSense red flag)
- `triadive` **word_count_low** (high) — projects/triadive/website/articles/workflows/index.html: 683w (threshold 800w for content_article)
- `triadive` **word_count_low** (high) — projects/triadive/website/contact/index.html: 621w (threshold 800w for legal_umbrella)
- `triadive` **missing_eeat_sections** (high) — projects/triadive/website/contact/index.html: /legal/-class page missing E-E-A-T sections: credentials, launch_date, editorial_process
- `triadive` **word_count_low** (high) — projects/triadive/website/privacy/index.html: 733w (threshold 800w for legal_umbrella)
- `triadive` **missing_eeat_sections** (high) — projects/triadive/website/privacy/index.html: /legal/-class page missing E-E-A-T sections: credentials, launch_date, editorial_process, corrections_policy, disclosure
- `triadive` **word_count_low** (high) — projects/triadive/website/terms/index.html: 751w (threshold 800w for legal_umbrella)
- `triadive` **missing_eeat_sections** (high) — projects/triadive/website/terms/index.html: /legal/-class page missing E-E-A-T sections: credentials, launch_date, editorial_process

## 📋 Other findings

### bithues (46)

- `broken_internal_link` (medium) — internal href '/articles1/' does not resolve to a known page or asset
- `broken_internal_link` (medium) — internal href '/articles3/' does not resolve to a known page or asset
- `broken_internal_link` (medium) — internal href '/articles4/' does not resolve to a known page or asset
- `broken_internal_link` (medium) — internal href '/articles5/' does not resolve to a known page or asset
- `broken_internal_link` (medium) — internal href '/articles6/' does not resolve to a known page or asset
- `broken_internal_link` (medium) — internal href '/articles1/' does not resolve to a known page or asset
- `broken_internal_link` (medium) — internal href '/articles2/' does not resolve to a known page or asset
- `broken_internal_link` (medium) — internal href '/articles4/' does not resolve to a known page or asset
- `broken_internal_link` (medium) — internal href '/articles5/' does not resolve to a known page or asset
- `broken_internal_link` (medium) — internal href '/articles6/' does not resolve to a known page or asset
- …and 36 more

### dependability (1)

- `duplicate_ad_slot` (high) — page has 1 duplicate ad slot(s); duplicated: ['1328672966']

### spaceorbitals (1)

- `missing_ad_unit` (medium) — 1526w of content but no AdSense ins tag (lost revenue opportunity)

### succession (4)

- `duplicate_ad_slot` (high) — page has 1 duplicate ad slot(s); duplicated: ['7590828986']
- `duplicate_ad_slot` (high) — page has 1 duplicate ad slot(s); duplicated: ['7590828986']
- `duplicate_ad_slot` (high) — page has 3 duplicate ad slot(s); duplicated: ['7590828986']
- `duplicate_ad_slot` (high) — page has 1 duplicate ad slot(s); duplicated: ['7590828986']

### tredey (73)

- `duplicate_ad_slot` (high) — page has 1 duplicate ad slot(s); duplicated: ['1216992329']
- `duplicate_ad_slot` (high) — page has 1 duplicate ad slot(s); duplicated: ['1216992329']
- `duplicate_ad_slot` (high) — page has 1 duplicate ad slot(s); duplicated: ['1216992329']
- `duplicate_ad_slot` (high) — page has 1 duplicate ad slot(s); duplicated: ['1216992329']
- `duplicate_ad_slot` (high) — page has 1 duplicate ad slot(s); duplicated: ['1216992329']
- `duplicate_ad_slot` (high) — page has 1 duplicate ad slot(s); duplicated: ['1216992329']
- `duplicate_ad_slot` (high) — page has 1 duplicate ad slot(s); duplicated: ['1216992329']
- `duplicate_ad_slot` (high) — page has 1 duplicate ad slot(s); duplicated: ['1216992329']
- `duplicate_ad_slot` (high) — page has 1 duplicate ad slot(s); duplicated: ['1216992329']
- `duplicate_ad_slot` (high) — page has 1 duplicate ad slot(s); duplicated: ['1216992329']
- …and 63 more

### triadive (2)

- `missing_ad_unit` (medium) — 2104w of content but no AdSense ins tag (lost revenue opportunity)
- `missing_ad_unit` (medium) — 3565w of content but no AdSense ins tag (lost revenue opportunity)

