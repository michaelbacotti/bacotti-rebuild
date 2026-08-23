"""
fix.py — Layer 4: apply safe auto-fixes.

For each finding with auto_fixable=True and a fix_class, attempt the fix.
All fixes are idempotent and reversible via git. If a fix can't be applied
cleanly, it gets downgraded to "would_have_fixed" and surfaced in the report.
"""
import re
import subprocess
from pathlib import Path

WORKSPACE = Path("/Users/mike/.openclaw/workspace-bacottibot")


def _run(cmd, cwd=WORKSPACE, timeout=60):
    """Run a shell command, return (returncode, stdout)."""
    try:
        out = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=isinstance(cmd, str),
        )
        return out.returncode, (out.stdout + out.stderr).strip()
    except Exception as e:
        return -1, str(e)


def fix_ga4_typo(finding) -> dict | None:
    """Replace G-G-XXXXXX with G-XXXXXX in the offending file."""
    file_path = WORKSPACE / finding["file"]
    if not file_path.exists():
        return None
    text = file_path.read_text(encoding="utf-8")
    fixed_text = GA4_TYPO_RE.sub(GA4_CORRECT_REPLACE, text)
    if fixed_text == text:
        return None
    file_path.write_text(fixed_text, encoding="utf-8")
    return {
        "fix_class": "ga4_typo",
        "file": finding["file"],
        "before": finding.get("typo_value", ""),
        "after": finding.get("typo_value", "").replace("G-G-", "G-") if finding.get("typo_value") else "(typo stripped)",
    }


GA4_TYPO_RE = re.compile(r'\bG-G-[A-Z0-9]+\b')


def GA4_CORRECT_REPLACE(m):
    """Replace G-G-XXXXXX with G-XXXXXX in a re.sub callback."""
    return m.group(0).replace("G-G-", "G-", 1)


# AdSense ins-tag pattern. Captures the whole <ins ... class="adsbygoogle" ...></ins> block.
AD_INSLOT_RE = re.compile(
    r'<ins\s+[^>]*class="adsbygoogle"[^>]*>\s*</ins>',
    re.IGNORECASE | re.DOTALL,
)


def fix_dedup_ad_slots(finding) -> dict | None:
    """Remove duplicate AdSense <ins> blocks on the same page.

    Strategy:
    1. Find every <ins class="adsbygoogle" ...></ins> block on the page.
    2. For each data-ad-slot value, keep the FIRST occurrence, drop the rest.
    3. Leave pages with no duplicates unchanged.
    """
    file_path = WORKSPACE / finding["file"]
    if not file_path.exists():
        return None
    try:
        text = file_path.read_text(encoding="utf-8")
    except Exception:
        return None

    # Walk every ins block, track which data-ad-slots we've seen, drop later dups
    seen_slots = set()
    removed_count = 0
    kept = []

    last_end = 0
    for m in AD_INSLOT_RE.finditer(text):
        # Determine this ins block's data-ad-slot
        ins_block = m.group(0)
        slot_m = re.search(r'data-ad-slot="(\d+)"', ins_block)
        slot = slot_m.group(1) if slot_m else None
        if slot is None:
            # No slot — keep it (untouched)
            kept.append((m.start(), m.end(), text[m.start():m.end()]))
            continue
        if slot in seen_slots:
            # Duplicate — drop this block
            removed_count += 1
            continue
        # First occurrence — keep
        seen_slots.add(slot)
        kept.append((m.start(), m.end(), ins_block))

    if removed_count == 0:
        return None

    # Rebuild by walking through text and skipping the dropped ins blocks.
    # Determine which (start, end) ranges to drop = all ins blocks NOT in `kept`.
    kept_set = {(s, e) for s, e, _ in kept}
    ranges_to_drop = []
    for m in AD_INSLOT_RE.finditer(text):
        if (m.start(), m.end()) not in kept_set:
            ranges_to_drop.append((m.start(), m.end()))

    new_text = []
    cursor = 0
    for start, end in ranges_to_drop:
        new_text.append(text[cursor:start])
        cursor = end
    new_text.append(text[cursor:])
    final = "".join(new_text)

    if final == text:
        return None

    file_path.write_text(final, encoding="utf-8")
    return {
        "fix_class": "dedup_ad_slots",
        "file": finding["file"],
        "removed_count": removed_count,
        "kept_slots": sorted(seen_slots),
    }


def fix_inject_favicon(finding) -> dict | None:
    """Run the existing inject_favicon.py against the site."""
    site_name = finding["site"]
    inject_script = WORKSPACE / "entities/bacotti-inc/website/_build/inject_favicon.py"
    if not inject_script.exists():
        return None
    rc, out = _run(["python3", str(inject_script)], cwd=inject_script.parent.parent)
    if rc != 0:
        return None
    return {
        "fix_class": "inject_favicon",
        "file": finding["file"],
        "tool": "_build/inject_favicon.py",
        "output": out[:300],
    }


FIXERS = {
    "ga4_typo": fix_ga4_typo,
    "inject_favicon": fix_inject_favicon,
    "dedup_ad_slots": fix_dedup_ad_slots,
}


def apply_fixes(findings: list, dry_run: bool = False) -> list:
    """Iterate over auto-fixable findings, apply, return list of applied fixes."""
    fixed = []
    # Dedupe: if the same fix_class hits the same file N times, only fix once.
    seen = set()
    for f in findings:
        if not f.get("auto_fixable"):
            continue
        fix_class = f.get("fix_class", f.get("class"))
        dedup_key = (fix_class, f.get("file"))
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        fixer = FIXERS.get(fix_class)
        if not fixer:
            continue
        if dry_run:
            fixed.append({"dry_run": True, "would_fix": fix_class, "file": f.get("file")})
            continue
        try:
            result = fixer(f)
            if result:
                fixed.append(result)
        except Exception as e:
            fixed.append({"fix_class": fix_class, "file": f.get("file"), "error": str(e)})

    # After all fixes, commit any modified files (one commit per site to keep history clean)
    if fixed and not dry_run:
        _commit_fixes(fixed)
    return fixed


def _commit_fixes(fixed: list) -> None:
    """Stage changed files and commit with a descriptive message."""
    # Collect unique (cwd, files) tuples by site
    by_cwd = {}
    for f in fixed:
        if not f.get("file") or f.get("dry_run") or f.get("error"):
            continue
        file_path = WORKSPACE / f["file"]
        # Find the nearest git repo
        cwd = file_path.parent if file_path.is_file() else WORKSPACE
        # Walk up to find .git
        for parent in [cwd] + list(cwd.parents):
            if (parent / ".git").exists():
                cwd = parent
                break
        by_cwd.setdefault(str(cwd), []).append(f["file"])

    for cwd, files in by_cwd.items():
        if not Path(cwd + "/.git").exists():
            continue
        # Add relative paths
        rel_files = []
        for f in files:
            try:
                rel_files.append(str((Path(cwd) / f).relative_to(cwd)))
            except ValueError:
                rel_files.append(f)
        _run(["git", "-C", cwd, "add", "--"] + rel_files, timeout=60)
        msg = f"site-code-audit: auto-fix {len(rel_files)} file(s)\n\n"
        msg += "\n".join(f"- {f.get('fix_class')}: {f.get('file')}" for f in fixed if f.get('file') in files)
        _run(["git", "-C", cwd, "commit", "-m", msg], timeout=60)
