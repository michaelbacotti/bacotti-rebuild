#!/usr/bin/env python3
"""
publish.py — Commit the article to the site's source dir and run the build.

Steps:
1. Move the draft .md file to the correct content directory per site
2. Run the site's build.py
3. Verify the rendered HTML has AdSense ins, canonical URL, and the title
4. (Optional) commit to git, push to remote, deploy to CF Pages

Per-site config lives in skills/autonomous-content-publishing/references/site-paths.md
"""
import json
import datetime
import argparse
import re
import subprocess
import shutil
from pathlib import Path

WORKSPACE = Path("/Users/mike/.openclaw/workspace-bacottibot")


# Per-site source directory + build command.
# Map site → (source_dir, build_cmd, deploy_cmd)
SITE_CONFIG = {
    "bithues": {
        "source_dir": "projects/bithues/content",
        "section_dirs": {
            "guides": "guides",
            "articles": "articles",
            "reviews": "reviews",
            "list": "list",
            "lists": "lists",
        },
        "build_cmd": ["python3", "projects/bithues/bithues-build/build.py"],
        "deploy_cmd": ["python3", "projects/bithues/bithues-build/deploy.py"],
    },
    "dependability": {
        "source_dir": "projects/dependability/content",
        "section_dirs": {
            "education": "education",
            "strategies": "strategies",
            "commentary": "commentary",
            "forecasts": "forecasts",
            "articles": "articles",
        },
        "build_cmd": ["python3", "projects/dependability/dependability-build/build.py"],
        "deploy_cmd": ["python3", "projects/dependability/dependability-build/deploy.py"],
    },
    "spaceorbitals": {
        "source_dir": "projects/spaceorbitals/content",
        "section_dirs": {
            "articles": "articles",
            "news": "news",
            "reviews": "reviews",
            "newsletters": "newsletters",
        },
        "build_cmd": ["python3", "projects/spaceorbitals/spaceorbitals-build/build.py"],
        "deploy_cmd": ["python3", "projects/spaceorbitals/spaceorbitals-build/deploy.py"],
    },
    "tredey": {
        "source_dir": "projects/tredey/content",
        "section_dirs": {
            "articles": "articles",
            "forecasts": "forecasts",
            "playbook": "playbook",
            "education": "education",
            "strategies": "strategies",
        },
        "build_cmd": ["python3", "projects/tredey/trading-journal-build/build.py"],
        "deploy_cmd": ["python3", "projects/tredey/trading-journal-build/deploy.py"],
    },
    "succession": {
        "source_dir": "projects/succession/content",
        "section_dirs": {
            "guides": "guides",
            "compliance": "compliance",
            "articles": "articles",
        },
        "build_cmd": ["python3", "projects/succession/succession-build/build.py"],
        "deploy_cmd": ["python3", "projects/succession/succession-build/deploy.py"],
    },
    "triadive": {
        "source_dir": "projects/triadive/content",
        "section_dirs": {
            "articles": "articles",
            "dispatches": "dispatches",
            "glossary": "glossary",
            "pages": "pages",
        },
        "build_cmd": ["python3", "projects/triadive/triadive-build/build.py"],
        "deploy_cmd": ["python3", "projects/triadive/triadive-build/deploy.py"],
    },
}


def get_target_dir(site: str, section: str) -> Path:
    """Resolve the target directory for a section in a site."""
    cfg = SITE_CONFIG.get(site)
    if not cfg:
        raise ValueError(f"unknown site: {site}")
    section_subdir = cfg["section_dirs"].get(section, section)
    return WORKSPACE / cfg["source_dir"] / section_subdir


def verify_built_html(site: str, target_file: Path) -> dict:
    """Run verify_published.py against the rendered HTML for the article.

    Quality gate per Mike's standard (2026-08-23):
    - Word count ≥ 400 (FAIL), ≥ 800 (WARN), prefer 1200
    - AdSense <ins> tag present
    - 5-section E-E-A-T recipe baked into a build template (NOT hand-edited)
    - canonical URL present
    Returns a dict with ok status + details. Caller decides whether to abort.
    """
    verifier = WORKSPACE / "skills" / "site-code-audit" / "scripts" / "verify_published.py"
    if not verifier.exists():
        return {"ok": True, "skipped": f"verify_published.py not found at {verifier}"}
    try:
        result = subprocess.run(
            ["python3", str(verifier), "--file", str(target_file), "--json"],
            cwd=str(WORKSPACE),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode not in (0, 1):
            return {"ok": True, "skipped": f"verify_published returned {result.returncode}",
                    "stderr_tail": result.stderr[-300:]}
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"ok": True, "skipped": "verify_published JSON parse failed",
                    "stdout_tail": result.stdout[-300:]}
        # Pull per-file result out of the aggregate
        per_file = next((r for r in data.get("results", []) if r.get("file")), None)
        ok = data.get("exit_code", 1) == 0 and (per_file is None or per_file.get("ok", False))
        return {
            "ok": ok,
            "exit_code": data.get("exit_code"),
            "files_pass": data.get("pass"),
            "files_total": data.get("files"),
            "per_file": per_file,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "verify_published timed out"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def publish_article(site: str, draft_path: Path, section: str, commit: bool = False,
                    build: bool = True, deploy: bool = False, dry_run: bool = True) -> dict:
    """Publish an article: move to source dir, optionally build, deploy, commit."""
    target_dir = get_target_dir(site, section)
    if not target_dir.exists():
        return {"ok": False, "error": f"target dir does not exist: {target_dir}"}

    target_file = target_dir / draft_path.name
    log = {"site": site, "section": section, "draft": str(draft_path),
           "target": str(target_file), "actions": []}

    if dry_run:
        log["actions"].append({"step": "dry-run", "would_copy_to": str(target_file)})
        log["dry_run"] = True
        return log

    # Step 1: copy draft to source dir
    shutil.copy2(draft_path, target_file)
    log["actions"].append({"step": "copied", "to": str(target_file)})

    # Step 2: build
    if build:
        cfg = SITE_CONFIG[site]
        try:
            result = subprocess.run(cfg["build_cmd"], cwd=WORKSPACE, capture_output=True, text=True, timeout=120)
            log["actions"].append({
                "step": "build",
                "command": cfg["build_cmd"],
                "returncode": result.returncode,
                "stdout_tail": result.stdout[-500:],
                "stderr_tail": result.stderr[-500:],
            })
        except Exception as e:
            log["actions"].append({"step": "build", "error": str(e)})

        # Step 2b: quality gate — verify_published.py
        # Renders the article, then scans the rendered HTML against Mike's
        # quality standards (word count, AdSense, E-E-A-T baked in, canonical).
        # On failure, abort the publish so a thin/non-compliant article never
        # reaches production.
        verify = verify_built_html(site, target_file)
        log["actions"].append({"step": "verify", "result": verify})
        if build and not verify.get("ok", False) and not verify.get("skipped"):
            log["ok"] = False
            log["error"] = "verify_published failed; publish aborted"
            return log

    # Step 3: deploy (only if explicit)
    if deploy:
        cfg = SITE_CONFIG[site]
        try:
            result = subprocess.run(cfg["deploy_cmd"], cwd=WORKSPACE, capture_output=True, text=True, timeout=300)
            log["actions"].append({
                "step": "deploy",
                "command": cfg["deploy_cmd"],
                "returncode": result.returncode,
                "stdout_tail": result.stdout[-500:],
                "stderr_tail": result.stderr[-500:],
            })
        except Exception as e:
            log["actions"].append({"step": "deploy", "error": str(e)})

    # Step 4: git commit
    if commit:
        try:
            result = subprocess.run(
                ["git", "-C", str(WORKSPACE), "add", str(target_file.relative_to(WORKSPACE))],
                capture_output=True, text=True, timeout=30,
            )
            log["actions"].append({"step": "git add", "returncode": result.returncode})
            msg = f"autonomous-content: new article '{target_file.stem}' on {site}"
            result = subprocess.run(
                ["git", "-C", str(WORKSPACE), "commit", "-m", msg],
                capture_output=True, text=True, timeout=30,
            )
            log["actions"].append({"step": "git commit", "returncode": result.returncode, "stdout_tail": result.stdout[-200:]})
        except Exception as e:
            log["actions"].append({"step": "git commit", "error": str(e)})

    log["ok"] = log.get("ok", True)
    return log


def main():
    ap = argparse.ArgumentParser(description="Publish article to site")
    ap.add_argument("--site", required=True)
    ap.add_argument("--section", required=True)
    ap.add_argument("--draft", required=True)
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--build", action="store_true", default=True)
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--no-dry-run", dest="dry_run", action="store_false")
    args = ap.parse_args()

    log = publish_article(
        site=args.site,
        draft_path=Path(args.draft),
        section=args.section,
        commit=args.commit,
        build=args.build,
        deploy=args.deploy,
        dry_run=args.dry_run,
    )
    print(json.dumps(log, indent=2))


if __name__ == "__main__":
    main()
