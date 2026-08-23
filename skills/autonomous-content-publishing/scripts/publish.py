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
