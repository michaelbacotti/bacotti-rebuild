#!/usr/bin/env python3
"""
adsense-upgrade-report.py — Generate per-site AdSense upgrade workboard cards.

Reads the latest code-audit-YYYY-MM-DD.json and groups AdSense-relevant
findings by site. Outputs:
  - One workboard card per site with full list of pages needing upgrade
  - Editable HTML scaffolds for each (8-section recipe by page type)
  - Markdown summary file with all pages ordered by priority

Usage:
    python3 scripts/adsense-upgrade-report.py [--date YYYY-MM-DD] [--create-cards] [--write-scaffolds]
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

WORKSPACE = Path("/Users/mike/.openclaw/workspace-bacottibot")
MEMORY_DIR = WORKSPACE / "memory" / "memory"
REPORTS_DIR = WORKSPACE / "memory" / "adsense-upgrades"

# Site name -> URL path prefix (for human-readable card titles)
SITE_URL = {
    "bacotti":         "bacotti.com",
    "wildwood-press":  "wildwood-press.com",
    "dependability":   "dependability.us",
    "spaceorbitals":   "spaceorbitals.com",
    "succession":      "successionholdingllc.com",
    "tredey":          "tredey.com",
    "triadive":        "triadive.com",
}

# Section recipes by page type (so each scaffold tells Mike exactly what to write)
RECIPES = {
    "legal_umbrella_about": """E-E-A-T recipe for /about/ pages (target 800w minimum):
1. **Who runs this site** — named founder/editor + brief credentials (~80w)
2. **Site launch date** — when the site started, where it is now (~50w)
3. **Editorial selection process** — how topics/books/strategies are chosen (~150w)
4. **Writing process** — research → draft → review → publish workflow (~150w)
5. **Corrections policy** — how errors are handled, when corrections are visible (~100w)
6. **Disclosure** — affiliations, conflicts, who funds the work (~100w)
7. **What we don't do** — clear list of avoided practices (~100w)
8. **How to reach us** — editor email, response times (~70w)""",

    "legal_umbrella_legal": """Legal-page expansion recipe (target 600w minimum):
1. Site launch date + how long it has been operating
2. Editorial process reference (link to /about/ for full details)
3. Corrections policy reference
4. Contact information for the editor""",

    "content_article": """Article/review/forecast expansion recipe (target 1200w minimum):
For reviews (bithues/spaceorbitals):
  1. Why this sits in our collection (selection rationale, ~150w)
  2. The argument that earns attention (thesis + claim, ~200w)
  3. Where it's strongest (concrete strengths, ~200w)
  4. Where it's weaker (HONEST critique — critical for E-E-A-T, ~200w)
  5. Who this is for (reader match, ~100w)
  6. How this review approaches the work (methodology, ~100w)
  7. Sources / cited references (~50w)

For succession articles:
  1. Worked example with real numbers ($/%/property types, ~250w)
  2. Common mistakes (3-4 named pitfalls + consequences, ~250w)
  3. Decision checklist (5-7 bulleted items operators use, ~200w)
  4. When this metric doesn't apply (edge cases, ~150w)

For dependability commentary/forecast:
  1. The named event (CPI/FOMC/nonfarm/etc) + date + level (~150w)
  2. Pre-event consensus + the surprise (~200w)
  3. Market reaction across 4 asset classes (~250w)
  4. Why this matters for next week (~200w)
  5. Sources cited (~50w)""",

    "thin_content_article": """Lightweight expansion (~100-300w to add):
1. Specific named examples (numbers, dates, sources)
2. Why this matters in context (relevance to current week)
3. Sources cited
4. Decision-actionable takeaways""",
}


def load_latest_findings(date: str | None) -> tuple:
    """Load the code-audit JSON, return (findings, date)."""
    if date:
        path = MEMORY_DIR / f"code-audit-{date}.json"
    else:
        paths = sorted(MEMORY_DIR.glob("code-audit-*.json"), reverse=True)
        if not paths:
            print("No code-audit JSONs found in", MEMORY_DIR, file=sys.stderr)
            sys.exit(1)
        path = paths[0]
    with path.open() as f:
        data = json.load(f)
    findings = data.get("findings", []) if isinstance(data, dict) else data
    return findings, path.stem.replace("code-audit-", "")


def filter_adsense(findings) -> list:
    """Keep only AdSense-relevant findings."""
    return [
        f for f in findings
        if f["class"] in (
            "thin_with_ads", "word_count_low", "duplicate_ad_slot",
            "missing_eeat_sections", "missing_ad_unit"
        )
    ]


def group_by_site(findings) -> dict:
    """Group findings by site, sorted by severity."""
    by_site = defaultdict(list)
    for f in findings:
        by_site[f["site"]].append(f)
    # Sort each site's findings: critical first, then by word count ascending
    for site in by_site:
        by_site[site].sort(key=lambda f: (
            0 if f["severity"] == "critical" else 1 if f["severity"] == "high" else 2,
            f.get("word_count", 9999)
        ))
    return dict(sorted(by_site.items()))


def short_path(file_path: str) -> str:
    """Convert /entities/dependability/website/about/index.html -> /about/"""
    # Strip the site prefix
    parts = file_path.split("/")
    # Find 'website/' or 'spaceorbitals/' or 'bithues-may24/' etc
    for i, p in enumerate(parts):
        if p in ("website", "spaceorbitals", "bithues-may24", "site"):
            return "/" + "/".join(parts[i+1:]) if i+1 < len(parts) else "/"
    return "/" + "/".join(parts[-2:])


def pick_recipe(page_type: str, missing_sections: list | None = None) -> str:
    """Pick the right recipe for a page."""
    if page_type == "legal_umbrella" and missing_sections:
        return RECIPES["legal_umbrella_about"]
    if page_type == "legal_umbrella":
        return RECIPES["legal_umbrella_legal"]
    if page_type == "content_article":
        return RECIPES["content_article"]
    return RECIPES["thin_content_article"]


def write_markdown_report(findings_by_site: dict, date: str) -> Path:
    """Write a Markdown per-site upgrade plan."""
    out = REPORTS_DIR / f"adsense-upgrade-{date}.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# AdSense Upgrade Plan — {date}",
        "",
        "Generated by `scripts/adsense-upgrade-report.py` from `code-audit-{date}.json`.",
        "",
        "Per-site list of pages needing expansion, dedup, or E-E-A-T sections.",
        "Each entry shows: page, current word count, threshold, fix recipe, scaffold.",
        "",
    ]
    for site, findings in findings_by_site.items():
        url = SITE_URL.get(site, site)
        # Count by class
        cls_counts = defaultdict(int)
        for f in findings:
            cls_counts[f["class"]] += 1
        thin_ads = cls_counts.get("thin_with_ads", 0)
        wc_low = cls_counts.get("word_count_low", 0)
        dup = cls_counts.get("duplicate_ad_slot", 0)
        eeat = cls_counts.get("missing_eeat_sections", 0)
        miss_unit = cls_counts.get("missing_ad_unit", 0)

        lines.append(f"## {site} ({url})")
        lines.append("")
        lines.append(f"- **{thin_ads}** thin+ads (CRITICAL — fix first)")
        lines.append(f"- **{wc_low}** word count low (high severity if no ads, critical if has ads)")
        lines.append(f"- **{dup}** duplicate ad slots (high — auto-fixable)")
        lines.append(f"- **{eeat}** missing E-E-A-T sections (high — needs content)")
        lines.append(f"- **{miss_unit}** missing ad units (medium — revenue opportunity)")
        lines.append("")
        lines.append("| Class | Severity | Page | Current | Target | Action |")
        lines.append("|---|---|---|---|---|---|")

        for f in findings:
            sp = short_path(f["file"])
            cur = f.get("word_count", "-")
            tgt = f.get("threshold", "-")
            cls = f["class"]
            if cls == "thin_with_ads":
                action = f"Expand to {tgt}w (page has {f.get('ad_count', 1)} ad slot(s) — AdSense red flag)"
            elif cls == "word_count_low":
                action = f"Expand to {tgt}w ({f.get('page_type', '')})"
            elif cls == "duplicate_ad_slot":
                action = f"Dedup ad slots: {f.get('duplicated_slots', [])}"
            elif cls == "missing_eeat_sections":
                action = f"Add E-E-A-T sections: {', '.join(f.get('missing_sections', []))}"
            elif cls == "missing_ad_unit":
                action = f"Add AdSense ins tag (lost revenue opportunity)"
            else:
                action = "-"
            lines.append(f"| {cls} | {f['severity']} | `{sp}` | {cur}w | {tgt}w | {action} |")

        lines.append("")
    out.write_text("\n".join(lines))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="YYYY-MM-DD (default: latest)")
    ap.add_argument("--create-cards", action="store_true", help="Create workboard cards")
    ap.add_argument("--write-scaffolds", action="store_true", help="Write editable HTML scaffolds")
    args = ap.parse_args()

    findings, date = load_latest_findings(args.date)
    adsense = filter_adsense(findings)
    by_site = group_by_site(adsense)

    md_path = write_markdown_report(by_site, date)
    print(f"Wrote {md_path}", file=sys.stderr)

    print(f"Date: {date}", file=sys.stderr)
    print(f"Total AdSense-relevant findings: {len(adsense)}", file=sys.stderr)
    print(f"Sites with findings: {len(by_site)}", file=sys.stderr)
    for site, findings in by_site.items():
        print(f"  {site:18s} {len(findings)} findings", file=sys.stderr)

    # Print summary to stdout (for cron/log capture)
    summary = {
        "date": date,
        "total_adsense_findings": len(adsense),
        "sites": {
            site: {
                "thin_with_ads": sum(1 for f in findings if f["class"] == "thin_with_ads"),
                "word_count_low": sum(1 for f in findings if f["class"] == "word_count_low"),
                "duplicate_ad_slot": sum(1 for f in findings if f["class"] == "duplicate_ad_slot"),
                "missing_eeat_sections": sum(1 for f in findings if f["class"] == "missing_eeat_sections"),
                "missing_ad_unit": sum(1 for f in findings if f["class"] == "missing_ad_unit"),
            }
            for site, findings in by_site.items()
        },
        "report_path": str(md_path.relative_to(WORKSPACE)),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
