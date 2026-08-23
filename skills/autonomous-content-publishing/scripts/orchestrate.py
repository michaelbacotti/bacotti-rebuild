#!/usr/bin/env python3
"""
orchestrate.py — Top-level runner for the autonomous content publishing pipeline.

Modes:
  --all                Run for all sites (1 topic per site)
  --site <name>        Run for one site
  --topic "..."        Specific topic (skips trend discovery)
  --dry-run            Skip publish + commit
  --skip-verify        Skip the verification step (NOT recommended)

Flow:
  1. trends.py  — discover trending topics
  2. research.py — deep-research top topic
  3. draft.py   — generate article draft (via llm-task)
  4. verify.py  — cross-check claims against sources
  5. review_gate.py — create workboard card or skip if autonomous OK
  6. publish.py — if approved (or autonomous OK), commit + build + verify

When run inside OpenClaw, llm-task is wired to the orchestrator's model. When
run standalone (cron, manual), the orchestrator emits prompts and pauses for
the LLM to be invoked separately.
"""
import json
import datetime
import argparse
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path("/Users/mike/.openclaw/workspace-bacottibot")
SCRIPTS_DIR = WORKSPACE / "skills" / "autonomous-content-publishing" / "scripts"


def run_script(name: str, *args) -> dict:
    """Run a script in the same dir, return parsed JSON or raw text."""
    script = SCRIPTS_DIR / name
    cmd = ["python3", str(script)] + list(args)
    result = subprocess.run(cmd, cwd=WORKSPACE, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        return {"error": result.stderr, "stdout": result.stdout, "returncode": result.returncode}
    # Try to parse last line as JSON; otherwise return raw
    try:
        lines = [l for l in result.stdout.splitlines() if l.strip()]
        # Last JSON-looking line
        for line in reversed(lines):
            if line.startswith("{"):
                return json.loads(line)
        return {"stdout": result.stdout, "returncode": result.returncode}
    except Exception:
        return {"stdout": result.stdout, "returncode": result.returncode}


def orchestrate_one(site: str, topic: str | None, dry_run: bool = True,
                    word_target: int = 1200, max_sources: int = 5,
                    seed_urls: list | None = None) -> dict:
    """Run the full pipeline for one (site, topic) pair."""
    log = {"site": site, "topic": topic, "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "steps": []}

    # Step 1: discover trends (if no specific topic)
    if not topic:
        trends_result = run_script("trends.py", "--site", site)
        log["steps"].append({"step": "trends", "result": trends_result})
        if not trends_result.get("topics"):
            log["error"] = "no trending topics found"
            return log
        topic = trends_result["topics"][0]["topic"]
        # Use the first result URL as a seed for research
        first = trends_result["topics"][0].get("first_result")
        if first and not seed_urls:
            seed_urls = [first["url"]]
        log["topic"] = topic

    # Step 2: research
    args = ["--topic", topic, "--max-sources", str(max_sources)]
    if seed_urls:
        for url in seed_urls:
            args.extend(["--seed-url", url])
    research_result = run_script("research.py", *args)
    log["steps"].append({"step": "research", "result": research_result})
    if "error" in research_result:
        log["error"] = f"research failed: {research_result['error']}"
        return log

    # Find the dossier file we just wrote
    import re
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:50]
    date = datetime.date.today().isoformat()
    dossier_path = WORKSPACE / "memory" / "autonomous-content" / f"research-{date}-{slug}.json"

    # Step 3: draft (emit prompt only — actual LLM call is separate)
    draft_result = run_script("draft.py", "--topic", topic, "--site", site,
                              "--dossier", str(dossier_path), "--word-target", str(word_target),
                              "--emit-prompt")
    log["steps"].append({"step": "draft", "result_summary": {"topic": topic, "site": site}})

    log["ended_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    log["status"] = "drafted" if not dry_run else "stub (dry-run)"
    log["next_step"] = "Run llm-task on the prompt from draft.py --emit-prompt, save to draft JSON, then run verify.py"
    log["dossier_path"] = str(dossier_path)
    return log


def main():
    ap = argparse.ArgumentParser(description="Run the autonomous content publishing pipeline")
    ap.add_argument("--all", action="store_true", help="Run for all sites")
    ap.add_argument("--site", help="Single site to run for")
    ap.add_argument("--topic", help="Specific topic (skips trend discovery)")
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--no-dry-run", dest="dry_run", action="store_false")
    ap.add_argument("--word-target", type=int, default=1200)
    ap.add_argument("--max-sources", type=int, default=5)
    args = ap.parse_args()

    sites = ["bithues", "dependability", "spaceorbitals", "tredey", "succession", "triadive"]
    if args.site:
        sites = [args.site]

    results = []
    for site in sites:
        print(f"\n=== {site} ===", file=sys.stderr)
        result = orchestrate_one(
            site=site,
            topic=args.topic,
            dry_run=args.dry_run,
            word_target=args.word_target,
            max_sources=args.max_sources,
        )
        results.append(result)
        print(json.dumps(result, indent=2))

    summary = {"ran_for": sites, "results_count": len(results), "results": results}
    out_file = WORKSPACE / "memory" / "autonomous-content" / f"orchestrate-{datetime.date.today().isoformat()}.json"
    out_file.write_text(json.dumps(summary, indent=2))
    print(f"\n[orchestrate] wrote {out_file}", file=sys.stderr)


if __name__ == "__main__":
    main()
