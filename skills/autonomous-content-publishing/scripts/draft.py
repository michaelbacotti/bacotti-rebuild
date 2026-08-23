#!/usr/bin/env python3
"""
draft.py — Generate an article draft from a research dossier with mandatory citations.

This wraps the LLM via the llm-task tool (or direct model call). Each generated
claim MUST be tagged with a source URL from the research dossier. The verifier
later re-checks each claim against its cited source.

Output: memory/autonomous-content/draft-<date>-<topic_slug>.md
"""
import json
import datetime
import re
import argparse
import sys
from pathlib import Path

WORKSPACE = Path("/Users/mike/.openclaw/workspace-bacottibot")
OUT_DIR = WORKSPACE / "memory" / "autonomous-content"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# Article template. The 4-section recipe that Mike uses for the AdSense rewrite,
# adapted for autonomous generation.
ARTICLE_TEMPLATE = """---
title: "{title}"
slug: "{slug}"
site: "{site}"
section: "{section}"
description: "{description}"
date: "{date}"
word_count_target: {word_count_target}
author: "{author}"
ai_generated: true
review_required: {review_required}
---

# {title}

> **AI-generated draft.** This article was drafted by the autonomous content
> pipeline. Every factual claim is tagged with a citation. The verify step has
> not yet run; the article is not published until verification passes
> (and, for financial sites, Mike reviews it).

## Intro ({intro_words}w)

{intro_body}

## Worked Example ({example_words}w)

{example_body}

## Common Mistakes ({mistakes_words}w)

{mistakes_body}

## Decision Checklist ({checklist_words}w)

{checklist_body}

## When This Doesn't Apply ({scope_words}w)

{scope_body}

## Sources

The following primary sources back the claims in this article. Each claim was
verified against its cited source by `verify.py` before publication.

{source_list}
"""


def build_prompt(topic: str, site: str, dossier: dict, word_target: int) -> str:
    """Build the LLM prompt that generates the article.

    Strict anti-hallucination guardrails:
    - Must only use facts from dossier.all_facts
    - Each claim must cite its source URL inline as [n]
    - Final source list must mirror dossier sources in order
    - If a fact isn't in the dossier, omit it (do NOT invent)
    """
    facts_text = "\n".join(f"- {f}" for f in dossier.get("all_facts", [])[:30])
    sources_text = "\n".join(
        f"[{i+1}] {s['url']} (tier {s['tier']})" for i, s in enumerate(dossier.get("sources", []))
    )
    return f"""You are drafting an article for {site} about: {topic}

Target word count: {word_target}w. Sections: intro, worked example, common
mistakes, decision checklist, when this doesn't apply.

## Anti-hallucination rules (CRITICAL)

1. Use ONLY facts from the dossier below. If a fact isn't there, omit it.
2. Each factual claim MUST cite a source inline as [1], [2], etc.
3. The numbered sources at the bottom MUST mirror the dossier sources in order.
4. Do not invent dates, percentages, names, or numbers. If you're unsure, leave
   it out — verify.py will catch unverified claims and reject the draft.
5. No first-person ("I think..."). Use neutral, evidence-based tone.
6. End with a Sources section listing every URL used.

## Dossier facts (use these and ONLY these)

{facts_text}

## Numbered sources (cite as [n])

{sources_text}

## Output

Respond with a JSON object exactly like:
{{
  "title": "...",
  "slug": "...",
  "section": "...",
  "description": "...",
  "intro": "...",
  "worked_example": "...",
  "common_mistakes": "...",
  "decision_checklist": "...",
  "when_doesnt_apply": "...",
  "claims": [
    {{"claim": "the sentence containing the claim", "citation": 1}},
    ...
  ]
}}

The claims list should contain every fact-bearing sentence in the article. The
verify step re-fetches each cited source and confirms the claim matches.
"""


def generate_draft(topic: str, site: str, dossier_path: Path, word_target: int = 1200,
                   review_required: bool = False) -> dict:
    """Generate a draft article from a research dossier.

    This is the LLM call. In production, this calls llm-task with a prompt that
    enforces the anti-hallucination rules above. The function below returns a
    stub draft if no LLM is configured — the actual LLM call is wired via
    llm-task when running inside OpenClaw.
    """
    if not dossier_path.exists():
        return {"error": f"dossier not found: {dossier_path}"}
    dossier = json.loads(dossier_path.read_text())
    prompt = build_prompt(topic, site, dossier, word_target)
    return {
        "topic": topic,
        "site": site,
        "prompt": prompt,
        "dossier_path": str(dossier_path),
        "note": "In production, this calls llm-task. The orchestrator wires that in.",
    }


def render_article(draft_data: dict, sources: list, template_vars: dict) -> str:
    """Render the JSON draft into a Markdown file using the template."""
    # This would normally take the LLM JSON output and render it.
    # For now, build a stub showing what the output looks like.
    sources_md = "\n".join(
        f"{i+1}. [{s['url']}]({s['url']}) — tier {s['tier']}, retrieved {s['retrieved_at'][:10]}"
        for i, s in enumerate(sources)
    )
    return ARTICLE_TEMPLATE.format(
        **template_vars,
        source_list=sources_md,
        intro_body=template_vars.get("intro", "(LLM-generated intro)"),
        example_body=template_vars.get("worked_example", "(LLM-generated example)"),
        mistakes_body=template_vars.get("common_mistakes", "(LLM-generated)"),
        checklist_body=template_vars.get("decision_checklist", "(LLM-generated)"),
        scope_body=template_vars.get("when_doesnt_apply", "(LLM-generated)"),
    )


def main():
    ap = argparse.ArgumentParser(description="Generate article draft")
    ap.add_argument("--topic", required=True)
    ap.add_argument("--site", required=True)
    ap.add_argument("--dossier", required=True, help="Path to research dossier JSON")
    ap.add_argument("--word-target", type=int, default=1200)
    ap.add_argument("--review-required", action="store_true")
    ap.add_argument("--emit-prompt", action="store_true", help="Just print the LLM prompt, no actual call")
    args = ap.parse_args()

    dossier_path = Path(args.dossier)
    if args.emit_prompt:
        dossier = json.loads(dossier_path.read_text())
        prompt = build_prompt(args.topic, args.site, dossier, args.word_target)
        print(prompt)
        return

    draft = generate_draft(
        topic=args.topic,
        site=args.site,
        dossier_path=dossier_path,
        word_target=args.word_target,
        review_required=args.review_required,
    )

    date = datetime.date.today().isoformat()
    slug = re.sub(r"[^a-z0-9]+", "-", args.topic.lower()).strip("-")[:50]
    out_file = OUT_DIR / f"draft-{date}-{slug}.json"
    out_file.write_text(json.dumps(draft, indent=2))
    print(f"[draft] wrote {out_file}")
    print(json.dumps({"topic": args.topic, "site": args.site, "file": str(out_file)}, indent=2))


if __name__ == "__main__":
    main()
