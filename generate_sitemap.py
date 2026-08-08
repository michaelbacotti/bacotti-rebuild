#!/usr/bin/env python3
"""
Sitemap generator for Bacotti Inc. static website.
Scans for all .html files and outputs sitemap.xml with proper directory-style URLs.
"""
import os
from pathlib import Path

WEBSITE_ROOT = Path(__file__).parent
BASE_URL = "https://bacotti.com"

def html_files():
    """Yield all .html files under website root, excluding .git/."""
    for root, dirs, files in os.walk(WEBSITE_ROOT):
        # Skip .git directory
        dirs[:] = [d for d in dirs if d != '.git']
        for fname in files:
            # Skip files starting with underscore (templates, partials)
            if fname.endswith('.html') and not fname.startswith('_'):
                yield Path(root) / fname

def to_sitemap_url(path):
    """Convert an HTML file path to a clean directory-style URL."""
    rel = path.relative_to(WEBSITE_ROOT)

    # index.html at root = homepage
    if rel == Path('index.html'):
        return '/'

    # about/index.html -> /about/
    if rel.name == 'index.html':
        parts = rel.parts[:-1]  # remove 'index.html'
        if not parts:
            return '/'
        return '/' + '/'.join(parts) + '/'

    # articles/slug.html -> /articles/slug/
    # Any other X.html -> /X/
    parts = rel.parts[:-1] + (rel.stem,)
    return '/' + '/'.join(parts) + '/'

def priority_for_url(url):
    """Assign priority based on URL depth and type."""
    if url == '/':
        return 1.0
    if url.count('/') == 2:  # e.g. /about/, /contact/, /services/, etc.
        return 0.8
    # Deeper URLs (e.g. articles)
    return 0.7

def generate_sitemap():
    urls = []
    for f in html_files():
        url = to_sitemap_url(f)
        if url is None:
            continue
        urls.append((url, priority_for_url(url)))

    # Remove duplicates, preserve order
    seen = set()
    unique = []
    for u, p in urls:
        if u not in seen:
            seen.add(u)
            unique.append((u, p))

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    # Per bithues/tredey convention: every <url> needs <lastmod>. Bacotti has
    # no frontmatter date field, so we use filesystem mtime. This is accurate
    # because pages are static and a deploy = mtime update.
    from datetime import date as _date
    today = _date.today().isoformat()

    url_to_lastmod = {}
    for f in html_files():
        url = to_sitemap_url(f)
        if url is None:
            continue
        try:
            import datetime as _dt
            mtime_iso = _dt.date.fromtimestamp(f.stat().st_mtime).isoformat()
        except Exception:
            mtime_iso = today
        url_to_lastmod[url] = mtime_iso

    for url, pri in unique:
        # Homepage gets highest priority
        priority = 1.0 if url == '/' else pri
        loc = f"<loc>{BASE_URL}{url}</loc>"
        pri_tag = f"<priority>{priority}</priority>"
        lm = url_to_lastmod.get(url, today)
        lm_tag = f"<lastmod>{lm}</lastmod>"
        lines.append(f"  <url>")
        lines.append(f"    {loc}")
        lines.append(f"    {lm_tag}")
        lines.append(f"    {pri_tag}")
        lines.append(f"  </url>")
    lines.append('</urlset>')

    sitemap_path = WEBSITE_ROOT / 'sitemap.xml'
    with open(sitemap_path, 'w') as fh:
        fh.write('\n'.join(lines) + '\n')

    print(f"Generated {sitemap_path}")
    print(f"URLs found ({len(unique)}):")
    for url, pri in unique:
        print(f"  {BASE_URL}{url}  [priority={pri}]")

if __name__ == '__main__':
    generate_sitemap()