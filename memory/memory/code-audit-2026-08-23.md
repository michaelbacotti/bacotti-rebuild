# Site Code Audit — 2026-08-23

**Sites audited:** bacotti, wildwood-press, dependability, spaceorbitals, succession, tredey, triadive
**Findings:** 192 total | **Auto-fixed:** 0 | **Needs attention:** 111

## Severity breakdown

- **critical:** 76
- **high:** 113
- **medium:** 3

## 🚨 Needs attention

- `bacotti` **word_count_low** (high) — entities/bacotti-inc/website/about/index.html: 183w (threshold 800w for legal_umbrella)
- `bacotti` **word_count_low** (high) — entities/bacotti-inc/website/contact/index.html: 37w (threshold 800w for legal_umbrella)
- `dependability` **missing_eeat_sections** (high) — entities/dependability/website/about/index.html: /legal/-class page missing E-E-A-T sections: credentials, editorial_process
- `dependability` **word_count_low** (critical) — entities/dependability/website/articles/forecast-methodology-2026/index.html: 763w (threshold 1200w for content_article)
- `dependability` **thin_with_ads** (critical) — entities/dependability/website/articles/forecast-methodology-2026/index.html: page has 3 ad slot(s) but only 763w (AdSense red flag)
- `dependability` **word_count_low** (critical) — entities/dependability/website/articles/index.html: 140w (threshold 1200w for content_article)
- `dependability` **thin_with_ads** (critical) — entities/dependability/website/articles/index.html: page has 3 ad slot(s) but only 140w (AdSense red flag)
- `dependability` **word_count_low** (critical) — entities/dependability/website/commentary/2026-07-13/index.html: 497w (threshold 1200w for content_article)
- `dependability` **thin_with_ads** (critical) — entities/dependability/website/commentary/2026-07-13/index.html: page has 2 ad slot(s) but only 497w (AdSense red flag)
- `dependability` **word_count_low** (critical) — entities/dependability/website/commentary/2026-07-14/index.html: 564w (threshold 1200w for content_article)
- `dependability` **thin_with_ads** (critical) — entities/dependability/website/commentary/2026-07-14/index.html: page has 2 ad slot(s) but only 564w (AdSense red flag)
- `dependability` **word_count_low** (critical) — entities/dependability/website/commentary/2026-07-15/index.html: 665w (threshold 1200w for content_article)
- `dependability` **thin_with_ads** (critical) — entities/dependability/website/commentary/2026-07-15/index.html: page has 2 ad slot(s) but only 665w (AdSense red flag)
- `dependability` **word_count_low** (critical) — entities/dependability/website/commentary/2026-07-16/index.html: 1042w (threshold 1200w for content_article)
- `dependability` **thin_with_ads** (critical) — entities/dependability/website/commentary/2026-07-16/index.html: page has 2 ad slot(s) but only 1042w (AdSense red flag)
- `dependability` **word_count_low** (critical) — entities/dependability/website/commentary/2026-08-21/index.html: 1122w (threshold 1200w for content_article)
- `dependability` **thin_with_ads** (critical) — entities/dependability/website/commentary/2026-08-21/index.html: page has 2 ad slot(s) but only 1122w (AdSense red flag)
- `dependability` **word_count_low** (critical) — entities/dependability/website/contact/index.html: 597w (threshold 800w for legal_umbrella)
- `dependability` **thin_with_ads** (critical) — entities/dependability/website/contact/index.html: page has 1 ad slot(s) but only 597w (AdSense red flag)
- `dependability` **missing_eeat_sections** (high) — entities/dependability/website/contact/index.html: /legal/-class page missing E-E-A-T sections: launch_date, editorial_process
- `dependability` **missing_eeat_sections** (high) — entities/dependability/website/disclaimer/index.html: /legal/-class page missing E-E-A-T sections: launch_date, editorial_process, corrections_policy
- `dependability` **word_count_low** (critical) — entities/dependability/website/forecast/2025-11-14/index.html: 504w (threshold 1200w for content_article)
- `dependability` **thin_with_ads** (critical) — entities/dependability/website/forecast/2025-11-14/index.html: page has 3 ad slot(s) but only 504w (AdSense red flag)
- `dependability` **word_count_low** (critical) — entities/dependability/website/forecast/2026-02-14/index.html: 631w (threshold 1200w for content_article)
- `dependability` **thin_with_ads** (critical) — entities/dependability/website/forecast/2026-02-14/index.html: page has 3 ad slot(s) but only 631w (AdSense red flag)
- `dependability` **missing_eeat_sections** (high) — entities/dependability/website/methodology/index.html: /legal/-class page missing E-E-A-T sections: launch_date
- `dependability` **missing_eeat_sections** (high) — entities/dependability/website/privacy/index.html: /legal/-class page missing E-E-A-T sections: credentials, launch_date, editorial_process
- `dependability` **missing_eeat_sections** (high) — entities/dependability/website/terms/index.html: /legal/-class page missing E-E-A-T sections: credentials, launch_date, editorial_process, corrections_policy
- `dependability` **word_count_low** (critical) — entities/dependability/website/trade-log/index.html: 390w (threshold 1200w for content_article)
- `dependability` **thin_with_ads** (critical) — entities/dependability/website/trade-log/index.html: page has 1 ad slot(s) but only 390w (AdSense red flag)
- `spaceorbitals` **word_count_low** (high) — projects/spaceorbitals/spaceorbitals/about/index.html: 22w (threshold 800w for legal_umbrella)
- `spaceorbitals` **word_count_low** (critical) — projects/spaceorbitals/spaceorbitals/articles/getting-into-astrophotography-2026/index.html: 935w (threshold 1200w for content_article)
- `spaceorbitals` **thin_with_ads** (critical) — projects/spaceorbitals/spaceorbitals/articles/getting-into-astrophotography-2026/index.html: page has 3 ad slot(s) but only 935w (AdSense red flag)
- `spaceorbitals` **word_count_low** (critical) — projects/spaceorbitals/spaceorbitals/articles/hohmann-transfer-explained/index.html: 770w (threshold 1200w for content_article)
- `spaceorbitals` **thin_with_ads** (critical) — projects/spaceorbitals/spaceorbitals/articles/hohmann-transfer-explained/index.html: page has 3 ad slot(s) but only 770w (AdSense red flag)
- `spaceorbitals` **word_count_low** (high) — projects/spaceorbitals/spaceorbitals/articles/index.html: 20w (threshold 1200w for content_article)
- `spaceorbitals` **word_count_low** (critical) — projects/spaceorbitals/spaceorbitals/articles/leo-economy-2026/index.html: 753w (threshold 1200w for content_article)
- `spaceorbitals` **thin_with_ads** (critical) — projects/spaceorbitals/spaceorbitals/articles/leo-economy-2026/index.html: page has 3 ad slot(s) but only 753w (AdSense red flag)
- `spaceorbitals` **word_count_low** (critical) — projects/spaceorbitals/spaceorbitals/articles/understanding-low-earth-orbit/index.html: 887w (threshold 1200w for content_article)
- `spaceorbitals` **thin_with_ads** (critical) — projects/spaceorbitals/spaceorbitals/articles/understanding-low-earth-orbit/index.html: page has 3 ad slot(s) but only 887w (AdSense red flag)
- `spaceorbitals` **word_count_low** (high) — projects/spaceorbitals/spaceorbitals/authors/index.html: 719w (threshold 800w for legal_umbrella)
- `spaceorbitals` **missing_eeat_sections** (high) — projects/spaceorbitals/spaceorbitals/authors/index.html: /legal/-class page missing E-E-A-T sections: launch_date, editorial_process
- `spaceorbitals` **word_count_low** (high) — projects/spaceorbitals/spaceorbitals/contact/index.html: 42w (threshold 800w for legal_umbrella)
- `spaceorbitals` **word_count_low** (critical) — projects/spaceorbitals/spaceorbitals/newsletters/four-planetary-science-hits/index.html: 1098w (threshold 1200w for content_article)
- `spaceorbitals` **thin_with_ads** (critical) — projects/spaceorbitals/spaceorbitals/newsletters/four-planetary-science-hits/index.html: page has 3 ad slot(s) but only 1098w (AdSense red flag)
- `spaceorbitals` **word_count_low** (critical) — projects/spaceorbitals/spaceorbitals/newsletters/orbital-daily-tracker-perseids-peak-planets-aligned-august-13/index.html: 1198w (threshold 1200w for content_article)
- `spaceorbitals` **thin_with_ads** (critical) — projects/spaceorbitals/spaceorbitals/newsletters/orbital-daily-tracker-perseids-peak-planets-aligned-august-13/index.html: page has 3 ad slot(s) but only 1198w (AdSense red flag)
- `spaceorbitals` **word_count_low** (critical) — projects/spaceorbitals/spaceorbitals/newsletters/weekly-read-reusability-china-era/index.html: 1079w (threshold 1200w for content_article)
- `spaceorbitals` **thin_with_ads** (critical) — projects/spaceorbitals/spaceorbitals/newsletters/weekly-read-reusability-china-era/index.html: page has 3 ad slot(s) but only 1079w (AdSense red flag)
- `spaceorbitals` **word_count_low** (high) — projects/spaceorbitals/spaceorbitals/privacy/index.html: 91w (threshold 800w for legal_umbrella)
- `spaceorbitals` **word_count_low** (critical) — projects/spaceorbitals/spaceorbitals/reviews/celestron-nexstar-8se-review/index.html: 782w (threshold 1200w for content_article)
- `spaceorbitals` **thin_with_ads** (critical) — projects/spaceorbitals/spaceorbitals/reviews/celestron-nexstar-8se-review/index.html: page has 2 ad slot(s) but only 782w (AdSense red flag)
- `spaceorbitals` **word_count_low** (high) — projects/spaceorbitals/spaceorbitals/reviews/index.html: 16w (threshold 1200w for content_article)
- `succession` **missing_eeat_sections** (high) — entities/succession/website/about/index.html: /legal/-class page missing E-E-A-T sections: launch_date
- `succession` **word_count_low** (critical) — entities/succession/website/articles/2026-05-04-first-investment-property/index.html: 836w (threshold 1200w for content_article)
- `succession` **thin_with_ads** (critical) — entities/succession/website/articles/2026-05-04-first-investment-property/index.html: page has 2 ad slot(s) but only 836w (AdSense red flag)
- `succession` **word_count_low** (critical) — entities/succession/website/articles/index.html: 1020w (threshold 1200w for content_article)
- `succession` **thin_with_ads** (critical) — entities/succession/website/articles/index.html: page has 2 ad slot(s) but only 1020w (AdSense red flag)
- `succession` **missing_eeat_sections** (high) — entities/succession/website/contact/index.html: /legal/-class page missing E-E-A-T sections: launch_date, editorial_process
- `succession` **missing_eeat_sections** (high) — entities/succession/website/disclaimer/index.html: /legal/-class page missing E-E-A-T sections: launch_date, editorial_process, corrections_policy, disclosure
- `succession` **word_count_low** (critical) — entities/succession/website/privacy/index.html: 785w (threshold 800w for legal_umbrella)
- `succession` **thin_with_ads** (critical) — entities/succession/website/privacy/index.html: page has 2 ad slot(s) but only 785w (AdSense red flag)
- `succession` **missing_eeat_sections** (high) — entities/succession/website/privacy/index.html: /legal/-class page missing E-E-A-T sections: launch_date, editorial_process, corrections_policy, disclosure
- `succession` **missing_eeat_sections** (high) — entities/succession/website/terms/index.html: /legal/-class page missing E-E-A-T sections: launch_date, editorial_process
- `tredey` **missing_eeat_sections** (high) — projects/tredey/website/about/index.html: /legal/-class page missing E-E-A-T sections: launch_date
- `tredey` **missing_eeat_sections** (high) — projects/tredey/website/contact/index.html: /legal/-class page missing E-E-A-T sections: launch_date, editorial_process, disclosure
- `tredey` **missing_eeat_sections** (high) — projects/tredey/website/disclaimer/index.html: /legal/-class page missing E-E-A-T sections: launch_date, editorial_process, corrections_policy
- `tredey` **word_count_low** (critical) — projects/tredey/website/forecasts/2026-07-31-framework-skip/index.html: 1083w (threshold 1200w for content_article)
- `tredey` **thin_with_ads** (critical) — projects/tredey/website/forecasts/2026-07-31-framework-skip/index.html: page has 3 ad slot(s) but only 1083w (AdSense red flag)
- `tredey` **word_count_low** (critical) — projects/tredey/website/forecasts/vol-expansion-strangle-spx-fomc/index.html: 1052w (threshold 1200w for content_article)
- `tredey` **thin_with_ads** (critical) — projects/tredey/website/forecasts/vol-expansion-strangle-spx-fomc/index.html: page has 3 ad slot(s) but only 1052w (AdSense red flag)
- `tredey` **missing_eeat_sections** (high) — projects/tredey/website/privacy/index.html: /legal/-class page missing E-E-A-T sections: launch_date, editorial_process, disclosure
- `tredey` **missing_eeat_sections** (high) — projects/tredey/website/terms/index.html: /legal/-class page missing E-E-A-T sections: credentials, launch_date, editorial_process
- `triadive` **missing_eeat_sections** (high) — projects/triadive/website/about/index.html: /legal/-class page missing E-E-A-T sections: credentials, launch_date, disclosure
- `triadive` **word_count_low** (critical) — projects/triadive/website/articles/concepts/agent-loop/index.html: 883w (threshold 1200w for content_article)
- `triadive` **thin_with_ads** (critical) — projects/triadive/website/articles/concepts/agent-loop/index.html: page has 1 ad slot(s) but only 883w (AdSense red flag)
- `triadive` **word_count_low** (critical) — projects/triadive/website/articles/concepts/best-ways-to-ask-an-agent/index.html: 1139w (threshold 1200w for content_article)
- `triadive` **thin_with_ads** (critical) — projects/triadive/website/articles/concepts/best-ways-to-ask-an-agent/index.html: page has 1 ad slot(s) but only 1139w (AdSense red flag)
- `triadive` **word_count_low** (critical) — projects/triadive/website/articles/concepts/loops-vs-graphs/index.html: 1042w (threshold 1200w for content_article)
- `triadive` **thin_with_ads** (critical) — projects/triadive/website/articles/concepts/loops-vs-graphs/index.html: page has 1 ad slot(s) but only 1042w (AdSense red flag)
- `triadive` **word_count_low** (critical) — projects/triadive/website/articles/concepts/sessions-sub-agents/index.html: 1143w (threshold 1200w for content_article)
- `triadive` **thin_with_ads** (critical) — projects/triadive/website/articles/concepts/sessions-sub-agents/index.html: page has 1 ad slot(s) but only 1143w (AdSense red flag)
- `triadive` **word_count_low** (critical) — projects/triadive/website/articles/concepts/what-is-a-graph/index.html: 1037w (threshold 1200w for content_article)
- `triadive` **thin_with_ads** (critical) — projects/triadive/website/articles/concepts/what-is-a-graph/index.html: page has 1 ad slot(s) but only 1037w (AdSense red flag)
- `triadive` **word_count_low** (critical) — projects/triadive/website/articles/concepts/what-is-a-loop/index.html: 966w (threshold 1200w for content_article)
- `triadive` **thin_with_ads** (critical) — projects/triadive/website/articles/concepts/what-is-a-loop/index.html: page has 1 ad slot(s) but only 966w (AdSense red flag)
- `triadive` **word_count_low** (critical) — projects/triadive/website/articles/concepts/what-is-an-ai-agent/index.html: 1024w (threshold 1200w for content_article)
- `triadive` **thin_with_ads** (critical) — projects/triadive/website/articles/concepts/what-is-an-ai-agent/index.html: page has 1 ad slot(s) but only 1024w (AdSense red flag)
- `triadive` **word_count_low** (critical) — projects/triadive/website/articles/concepts/what-is-memory-short-long-semantic/index.html: 948w (threshold 1200w for content_article)
- `triadive` **thin_with_ads** (critical) — projects/triadive/website/articles/concepts/what-is-memory-short-long-semantic/index.html: page has 1 ad slot(s) but only 948w (AdSense red flag)
- `triadive` **word_count_low** (critical) — projects/triadive/website/articles/concepts/why-memory-is-the-hardest-part/index.html: 1171w (threshold 1200w for content_article)
- `triadive` **thin_with_ads** (critical) — projects/triadive/website/articles/concepts/why-memory-is-the-hardest-part/index.html: page has 1 ad slot(s) but only 1171w (AdSense red flag)
- `triadive` **word_count_low** (high) — projects/triadive/website/articles/field-notes/index.html: 394w (threshold 1200w for content_article)
- `triadive` **word_count_low** (critical) — projects/triadive/website/articles/field-notes/the-three-amigos-of-the-agent-stack/index.html: 950w (threshold 1200w for content_article)
- `triadive` **thin_with_ads** (critical) — projects/triadive/website/articles/field-notes/the-three-amigos-of-the-agent-stack/index.html: page has 1 ad slot(s) but only 950w (AdSense red flag)
- `triadive` **word_count_low** (critical) — projects/triadive/website/articles/field-notes/triads-not-tools/index.html: 841w (threshold 1200w for content_article)
- `triadive` **thin_with_ads** (critical) — projects/triadive/website/articles/field-notes/triads-not-tools/index.html: page has 1 ad slot(s) but only 841w (AdSense red flag)
- `triadive` **word_count_low** (high) — projects/triadive/website/articles/lessons/index.html: 283w (threshold 1200w for content_article)
- `triadive` **word_count_low** (critical) — projects/triadive/website/articles/workflows/daily-check-in-loop/index.html: 701w (threshold 1200w for content_article)
- `triadive` **thin_with_ads** (critical) — projects/triadive/website/articles/workflows/daily-check-in-loop/index.html: page has 1 ad slot(s) but only 701w (AdSense red flag)
- `triadive` **word_count_low** (critical) — projects/triadive/website/articles/workflows/daily-triage-routine/index.html: 931w (threshold 1200w for content_article)
- `triadive` **thin_with_ads** (critical) — projects/triadive/website/articles/workflows/daily-triage-routine/index.html: page has 1 ad slot(s) but only 931w (AdSense red flag)
- `triadive` **word_count_low** (high) — projects/triadive/website/articles/workflows/index.html: 683w (threshold 1200w for content_article)
- `triadive` **word_count_low** (critical) — projects/triadive/website/articles/workflows/three-rules-for-first-plugin/index.html: 844w (threshold 1200w for content_article)
- `triadive` **thin_with_ads** (critical) — projects/triadive/website/articles/workflows/three-rules-for-first-plugin/index.html: page has 1 ad slot(s) but only 844w (AdSense red flag)
- `triadive` **word_count_low** (high) — projects/triadive/website/contact/index.html: 621w (threshold 800w for legal_umbrella)
- `triadive` **missing_eeat_sections** (high) — projects/triadive/website/contact/index.html: /legal/-class page missing E-E-A-T sections: credentials, launch_date, editorial_process
- `triadive` **word_count_low** (high) — projects/triadive/website/privacy/index.html: 733w (threshold 800w for legal_umbrella)
- `triadive` **missing_eeat_sections** (high) — projects/triadive/website/privacy/index.html: /legal/-class page missing E-E-A-T sections: credentials, launch_date, editorial_process, corrections_policy, disclosure
- `triadive` **word_count_low** (high) — projects/triadive/website/terms/index.html: 751w (threshold 800w for legal_umbrella)
- `triadive` **missing_eeat_sections** (high) — projects/triadive/website/terms/index.html: /legal/-class page missing E-E-A-T sections: credentials, launch_date, editorial_process

## 📋 Other findings

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

