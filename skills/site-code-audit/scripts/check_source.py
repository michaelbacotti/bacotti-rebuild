#!/usr/bin/env python3
"""check_source.py — for any HTML file, determine its source of truth.

Returns one of:
  - 'hand_crafted'  — file is the source (no build.py touches it)
  - 'md_source'     — built from <content-dir>/<section>/<slug>.md
  - 'inline_static' — built from a string literal in build.py
  - 'orphan'        — build.py exists but no MD source found (build won't regenerate)
  - 'unsure'        — couldn't classify (CHECK MANUALLY before editing)

Usage:
  python3 check_source.py path/to/index.html
"""
import re
import sys
from pathlib import Path

WORKSPACE = Path.home() / ".openclaw" / "workspace-bacottibot"


def find_build_py(html_path: Path) -> Path | None:
    """Walk up from the file AND check sibling dirs for a build.py.
    
    Many sites have the structure:
      projects/<site>/website/<file>      ← the HTML
      projects/<site>/<site>-build/build.py  ← the builder
      projects/<site>/content/<...>           ← MD source
    """
    # 1. Walk up from the file
    cur = html_path.parent
    for _ in range(6):
        if (cur / "build.py").exists():
            return cur / "build.py"
        # 2. Check sibling dirs
        for sibling in cur.iterdir():
            if sibling.is_dir() and (sibling / "build.py").exists():
                return sibling / "build.py"
        cur = cur.parent
    return None


def get_content_root(build_py: Path) -> Path | None:
    """Find the content/ dir that build.py reads from."""
    text = build_py.read_text()
    m = re.search(r'CONTENT_DIR\s*=\s*([^\n]+)', text)
    if m:
        expr = m.group(1).strip()
        # ROOT.parent / "content" - assume ROOT = build_py.parent
        if 'ROOT.parent' in expr or 'parent' in expr:
            return build_py.parent.parent / "content"
        if 'WEBSITE_DIR' in expr:
            m2 = re.search(r'WEBSITE_DIR\s*=\s*([^\n]+)', text)
            if m2 and 'parent' in m2.group(1):
                return build_py.parent.parent / "content"
    # Fallback: search nearby content/ dirs
    for candidate in [
        build_py.parent / "content",
        build_py.parent.parent / "content",
        build_py.parent.parent / ".." / "content",
    ]:
        if candidate.exists():
            return candidate
    return None


def find_md_source(content_root: Path | None, slug: str) -> Path | None:
    """Search all MD files in content_root for one with this slug."""
    if not content_root or not content_root.exists():
        return None
    for md_file in content_root.rglob("*.md"):
        if any(part.startswith("_") for part in md_file.parts):
            continue
        if md_file.stem == slug:
            return md_file
    return None


def find_inline_static_pages(build_py: Path) -> set[str]:
    """Find pages defined as string literals in build.py."""
    text = build_py.read_text()
    pages = set()
    for match in re.finditer(r'(\w+)_body\s*=\s*["\'\"]', text):
        prefix = match.group(1).lower()
        if prefix in ('privacy', 'contact', 'about', 'terms', 'disclaimer', 'methodology'):
            pages.add(f"/{prefix}/")
    return pages


def is_in_static_pages(build_py: Path, slug: str) -> bool:
    text = build_py.read_text()
    if re.search(rf'\(\s*["\']({slug})["\']\s*,', text):
        return True
    return False


def is_generated_by_author_index(build_py: Path, slug: str) -> bool:
    text = build_py.read_text()
    if 'build_authors_index' not in text:
        return False
    if re.search(rf'authors_section.*index\.html|\(authors.*index\.html', text, re.DOTALL):
        return True
    if 'build_authors_index' in text and 'authors' in slug:
        return True
    return False


def check(html_path: str) -> dict:
    p = Path(html_path).resolve()
    rel = p.relative_to(WORKSPACE) if p.is_relative_to(WORKSPACE) else p
    
    # Determine slug
    slug = p.parent.name if p.parent.name not in ('', 'index', '.') else p.stem
    
    # Section is the dir above slug (e.g., "articles" for /articles/hohmann-...)
    section = p.parent.parent.name if p.parent.parent != p.parent else ''
    
    build_py = find_build_py(p)
    if not build_py:
        return {
            "file": str(rel),
            "slug": slug,
            "section": section,
            "build_py": None,
            "source_type": "hand_crafted",
            "warning": "✓ No build.py found — file is hand-crafted source",
        }
    
    build_py_rel = str(build_py.relative_to(WORKSPACE))
    
    # 1. Inline static page (privacy_body etc)
    if is_in_static_pages(build_py, slug):
        return {
            "file": str(rel),
            "slug": slug,
            "section": section,
            "build_py": build_py_rel,
            "source_type": "inline_static",
            "warning": "⚠ Built from inline string in build.py. EDIT build.py, not the HTML.",
        }
    
    inline_pages = find_inline_static_pages(build_py)
    if f"/{slug}/" in inline_pages:
        return {
            "file": str(rel),
            "slug": slug,
            "section": section,
            "build_py": build_py_rel,
            "source_type": "inline_static",
            "warning": "⚠ Built from inline string in build.py. EDIT build.py, not the HTML.",
        }
    
    # 2. Authors index
    if slug == "authors" and is_generated_by_author_index(build_py, slug):
        return {
            "file": str(rel),
            "slug": slug,
            "section": section,
            "build_py": build_py_rel,
            "source_type": "inline_static",
            "warning": "⚠ Built from build_authors_index() in build.py. EDIT build.py, not the HTML.",
        }
    
    # 3. MD source check
    content_root = get_content_root(build_py)
    md_source = find_md_source(content_root, slug)
    if md_source:
        return {
            "file": str(rel),
            "slug": slug,
            "section": section,
            "build_py": build_py_rel,
            "source_type": "md_source",
            "md_source": str(md_source.relative_to(WORKSPACE)),
            "warning": "⚠ MD source exists. EDIT MD, not HTML.",
        }
    
    return {
        "file": str(rel),
        "slug": slug,
        "section": section,
        "build_py": build_py_rel,
        "source_type": "orphan",
        "warning": "✓ No MD source / inline definition. File is orphaned — safe to edit (build.py leaves it alone).",
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 check_source.py path/to/index.html")
        sys.exit(1)
    result = check(sys.argv[1])
    print(f"File:      {result['file']}")
    print(f"Slug:      {result['slug']}")
    print(f"Section:   {result['section']}")
    print(f"Build.py:  {result.get('build_py') or '(none)'}")
    if result.get('md_source'):
        print(f"MD source: {result['md_source']}")
    print(f"Source:    {result['source_type']}")
    print(f"{result['warning']}")
