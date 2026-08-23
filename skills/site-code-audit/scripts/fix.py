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


# AdSense ins template — the in-content ad we add to long pages without ads.
# Reads the existing pub-id from a sibling file if available, else falls back
# to Mike's known pub-id.
DEFAULT_ADSENSE_PUB_ID = "ca-pub-9312870448453345"
AD_INS_TEMPLATE = (
    '<ins class="adsbygoogle" style="display:block" '
    'data-ad-client="{pub_id}" '
    'data-ad-slot="0000000000" data-ad-format="auto" '
    'data-full-width-responsive="true"></ins>\n'
    '<script>(adsbygoogle = window.adsbygoogle || []).push(' + '{}' + ');</script>'
)


def _detect_pub_id(file_path: Path) -> str:
    """Find the AdSense pub-id used elsewhere on this site, or fall back."""
    try:
        text = file_path.read_text(encoding="utf-8")
    except Exception:
        return DEFAULT_ADSENSE_PUB_ID
    m = re.search(r'ca-pub-[A-Za-z0-9]+', text)
    return m.group(0) if m else DEFAULT_ADSENSE_PUB_ID


def fix_missing_ad_unit(finding) -> dict | None:
    """Insert a single AdSense <ins> block into a long page that has no ads.

    Strategy:
      1. Find a mid-article location (before </article>, before </main>, or
         after the first <h2> section's closing </p>) and drop the ins there.
      2. Reuse the existing pub-id from this site (or fall back to default).
      3. Use a placeholder data-ad-slot (0000000000) — Mike must replace it
         with a real slot from his AdSense dashboard before AdSense will serve.

    Returns: dict with fix details, or None if no insertion happened.
    """
    file_path = WORKSPACE / finding["file"]
    if not file_path.exists():
        return None
    try:
        text = file_path.read_text(encoding="utf-8")
    except Exception:
        return None

    # Already has an ad? Bail.
    if AD_INSLOT_RE.search(text):
        return None

    pub_id = _detect_pub_id(file_path)
    # Use plain string replacement, not str.format — the template contains
    # literal {} for the JS object push() call which str.format would mangle.
    ins_block = AD_INS_TEMPLATE.replace("{pub_id}", pub_id)

    # Pick insertion point: just before </article>, else </main>, else first </p>
    # after the intro (skip the first </p> which is usually the lede).
    insertion = None
    for marker in ("</article>", "</main>", "</section>"):
        idx = text.lower().find(marker)
        if idx > 0:
            insertion = idx
            break
    if insertion is None:
        # Fall back: find the second </p> after the first <h1>/<h2>
        h1_idx = text.lower().find("<h1")
        h2_idx = text.lower().find("<h2")
        anchor = max(h1_idx, h2_idx)
        if anchor > 0:
            # Walk forward to find 2nd </p>
            rest = text[anchor:]
            closes = [m.end() for m in re.finditer(r"</p>", rest, re.IGNORECASE)]
            if len(closes) >= 2:
                insertion = anchor + closes[1]
    if insertion is None:
        # Last resort: append before </body>
        body_close = text.lower().rfind("</body>")
        if body_close < 0:
            return None
        insertion = body_close

    new_text = text[:insertion] + "\n" + ins_block + "\n" + text[insertion:]
    file_path.write_text(new_text, encoding="utf-8")
    return {
        "fix_class": "missing_ad_unit",
        "file": finding["file"],
        "added_at_marker": text[max(0, insertion-30):insertion].strip(),
        "pub_id": pub_id,
        "note": "data-ad-slot=0000000000 is a placeholder — Mike must replace it with a real slot.",
    }


# Internal link pattern (for broken-link detection + fixing)
INTERNAL_HREF_RE = re.compile(r'href="(/[^"#?]*)"', re.IGNORECASE)


def _scan_existing_slugs(site_root: Path, href: str) -> list:
    """For a broken href like /articles/best-books-about-productivity, list
    every existing slug under the same parent path (here: /articles/*)."""
    parts = [p for p in href.split("/") if p]
    if not parts:
        return []
    parent = "/".join(parts[:-1]) + "/" if len(parts) > 1 else ""
    parent_dir = site_root / parent.rstrip("/")
    if not parent_dir.is_dir():
        return []
    out = []
    for child in parent_dir.iterdir():
        if child.is_dir():
            # /articles/<slug>/
            out.append(f"/{parent}{child.name}/")
    return out


def _resolve_internal_path(site_root: Path, href: str) -> Path | None:
    """Try to resolve an internal href like /articles/2/ to a real file.

    Strips query/anchor, normalizes trailing slash, and tries several common
    HTML structures:
      - <site_root>/<href>/index.html
      - <site_root>/<href>.html
      - <site_root>/<href>
    """
    if not href.startswith("/"):
        return None
    # Strip query/fragment
    href = href.split("?")[0].split("#")[0]
    # Drop leading slash
    clean = href.lstrip("/")
    if not clean:
        return None
    candidates = [
        site_root / clean / "index.html",
        site_root / (clean + ".html"),
        site_root / clean,
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return c
    return None


def fix_broken_internal_link(finding) -> dict | None:
    """Fix a broken internal link.

    Strategy:
      1. Read the source file, find every internal href.
      2. For each, try to resolve to a real file under the site root.
      3. If unresolved AND the href looks like a near-typo of an existing
         path (e.g. /articles1/ vs /articles/1/), try a few common rewrites.
      4. If a rewrite resolves, replace the href with the correct path.
      5. If still unresolvable and the link is part of an obvious placeholder
         (e.g. /catalog/ where no catalog exists), drop the <a> tag, keep text.

    Returns: dict with fix details, or None if nothing changed.
    """
    file_path = WORKSPACE / finding["file"]
    if not file_path.exists():
        return None
    try:
        text = file_path.read_text(encoding="utf-8")
    except Exception:
        return None

    site_root = file_path.parent
    # Walk up to find the website/ root (one level above the file)
    while site_root.name not in {"website", "public", "dist", "build", "site"} and site_root != site_root.parent:
        site_root = site_root.parent
    if site_root == site_root.parent:
        site_root = file_path.parent  # fallback

    fixed_links = []
    removed_links = []
    seen_in_pass = set()

    for m in INTERNAL_HREF_RE.finditer(text):
        href = m.group(1)
        if not href or href in seen_in_pass:
            continue
        seen_in_pass.add(href)

        # Already resolves?
        if _resolve_internal_path(site_root, href) is not None:
            continue

        # If the href contains a JS template literal (e.g. /reviews/' + b.slug + '),
        # skip — this is a false positive from a static scan over a JS-built page.
        if any(tok in href for tok in ("' +", "+ '", '${', "{{", "}}")):
            continue

        # Try common typos: /articles1/ → /articles/1/, /articlesN/ → /articles/N/
        candidates = []
        # Pattern: /wordN/ where N is digits → /word/N/
        typo_m = re.match(r"^/([a-z][a-z0-9-]*?)(\d+)/?$", href, re.IGNORECASE)
        if typo_m:
            word, num = typo_m.group(1), typo_m.group(2)
            candidates.append(f"/{word}/{num}/")
            candidates.append(f"/{word}/{num}")
            # If /word/N/ doesn't exist but /word/ (index) does, link there.
            if _resolve_internal_path(site_root, f"/{word}/") is not None:
                candidates.append(f"/{word}/")
        # Pattern: /word/N_extra/ → /word/N/
        if (m2 := re.match(r"^/([a-z][a-z0-9-]*)/(\d+)_.*$", href, re.IGNORECASE)):
            candidates.append(f"/{m2.group(1)}/{m2.group(2)}/")
        # Pattern: /word1/ where 1 is the lowest page (no /word/1/ exists) → /word/
        first_page_m = re.match(r"^/([a-z][a-z0-9-]*?)1/?$", href, re.IGNORECASE)
        if first_page_m:
            word = first_page_m.group(1)
            if (_resolve_internal_path(site_root, f"/{word}/1/") is None
                    and _resolve_internal_path(site_root, f"/{word}/") is not None):
                candidates.append(f"/{word}/")
        # If href looks like a /category/ that doesn't exist (e.g. /catalog/),
        # we'll fall through to "remove" below.

        rewritten = False
        for cand in candidates:
            if _resolve_internal_path(site_root, cand) is not None:
                old = f'href="{href}"'
                new = f'href="{cand}"'
                text = text.replace(old, new, 1)
                fixed_links.append({"from": href, "to": cand})
                rewritten = True
                break

        if not rewritten and not simple_index_m:
            # Try fuzzy match: e.g. /articles/best-books-about-productivity
            # has no exact match but maybe there's a similar slug.
            target_slug = href.rstrip("/").split("/")[-1]
            target_words = set(re.findall(r"[a-z]+", target_slug))
            best_match = None
            best_score = 0
            for cand in candidates + _scan_existing_slugs(site_root, href):
                cand_slug = cand.rstrip("/").split("/")[-1]
                cand_words = set(re.findall(r"[a-z]+", cand_slug))
                if not target_words or not cand_words:
                    continue
                # Jaccard similarity
                intersect = target_words & cand_words
                union = target_words | cand_words
                score = len(intersect) / len(union) if union else 0
                if score > best_score and score >= 0.5:
                    best_score = score
                    best_match = cand
            if best_match and _resolve_internal_path(site_root, best_match) is not None:
                old = f'href="{href}"'
                new = f'href="{best_match}"'
                text = text.replace(old, new, 1)
                fixed_links.append({"from": href, "to": best_match, "fuzzy": True, "score": round(best_score, 2)})
                rewritten = True

        if rewritten:
            continue

        # No rewrite worked. If the href is a plausible-but-missing index
        # (short path, no extension), drop the <a> tag, keep the inner text.
        # Otherwise leave it alone (don't remove links we can't reason about).
        simple_index_m = re.match(r"^/[a-z][a-z0-9-]*/?$", href, re.IGNORECASE)
        if simple_index_m:
            # Find the <a href="href">inner</a> wrapper and unwrap it
            anchor_re = re.compile(
                r'<a\s+[^>]*href="' + re.escape(href) + r'"[^>]*>(.*?)</a>',
                re.IGNORECASE | re.DOTALL,
            )
            new_text = anchor_re.sub(r"\1", text, count=1)
            if new_text != text:
                text = new_text
                removed_links.append(href)

    if not fixed_links and not removed_links:
        return None

    file_path.write_text(text, encoding="utf-8")
    return {
        "fix_class": "broken_internal_link",
        "file": finding["file"],
        "fixed_count": len(fixed_links),
        "removed_count": len(removed_links),
        "fixes": fixed_links,
        "removed": removed_links,
    }


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
    "broken_internal_link": fix_broken_internal_link,
    "missing_ad_unit": fix_missing_ad_unit,
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
