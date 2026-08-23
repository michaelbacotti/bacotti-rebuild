"""
Site registry — single source of truth for which sites we audit and where they live.

Update this file when a new site is added or moved.
"""
from pathlib import Path

WORKSPACE = Path("/Users/mike/.openclaw/workspace-bacottibot")


def _workspace_path(*parts):
    return WORKSPACE.joinpath(*parts)


# Each site: {name, domain, source_dir, repo_remote}
# If source_dir is None, the site lives in workspace root or external.
SITES = [
    {
        "name": "bacotti",
        "domain": "https://bacotti.com",
        "source_dir": _workspace_path("entities/bacotti-inc/website"),
        "exclude_paths": ["shop"],  # Wildwood Press Shop is a different brand
        "favicon_paths": [
            "favicon.ico",
            "favicon-16x16.png",
            "favicon-32x32.png",
            "favicon-48x48.png",
            "favicon-180x180.png",
            "favicon-192x192.png",
            "favicon-512x512.png",
            "apple-touch-icon.png",
        ],
        "ga4_property": "G-865LW2JQVJ",
    },
    {
        "name": "wildwood-press",
        "domain": "https://shop.bacotti.com",
        "source_dir": _workspace_path("entities/bacotti-inc/website/shop"),
        "favicon_paths": [],  # No favicon assets exist; do not inject bacotti's
    },
    {
        "name": "bithues",
        "domain": "https://bithues.com",
        "source_dir": _workspace_path("_archive/2026-08-22/bithues-crypto-snapshot"),
        # NB: bithues-crypto lives in archive after the 2026-08-22 cleanup.
        # If it's restored to live work, update this path.
        "favicon_paths": [
            "favicon.ico",
            "favicon-16x16.png",
            "favicon-32x32.png",
            "favicon-48x48.png",
            "favicon-180x180.png",
            "favicon-192x192.png",
            "favicon-512x512.png",
            "apple-touch-icon.png",
        ],
    },
    {
        "name": "bithues-crypto",
        "domain": "https://bithues-crypto.com",
        "source_dir": _workspace_path("_archive/2026-08-22/bithues-crypto-snapshot"),
        "favicon_paths": [],
    },
    {
        "name": "dependability",
        "domain": "https://dependability.us",
        "source_dir": _workspace_path("entities/dependability/website"),
        "favicon_paths": [],
    },
    {
        "name": "spaceorbitals",
        "domain": "https://spaceorbitals.com",
        "source_dir": _workspace_path("projects/spaceorbitals/spaceorbitals"),
        "favicon_paths": [],
    },
    {
        "name": "succession",
        "domain": "https://successionholdingllc.com",
        "source_dir": _workspace_path("entities/succession/website"),
        "favicon_paths": [],
    },
    {
        "name": "tredey",
        "domain": "https://tredey.com",
        "source_dir": _workspace_path("projects/tredey/website"),
        "favicon_paths": [],
    },
    {
        "name": "triadive",
        "domain": "https://triadive.com",
        "source_dir": _workspace_path("projects/triadive/website"),
        "favicon_paths": [],
    },
]


def get_site(name):
    for s in SITES:
        if s["name"] == name:
            return s
    return None


def all_html_files(site):
    """Return all .html files in the site's source_dir (recursive)."""
    if not site.get("source_dir") or not site["source_dir"].exists():
        return []
    files = sorted(site["source_dir"].rglob("*.html"))
    # Filter out excluded paths (relative to source_dir)
    excludes = list(site.get("exclude_paths", [])) + [
        "node_modules",   # JS deps — never website content
        "_archive",       # Archived snapshots — not live
        ".venv",
        ".wrangler",
        "test-results",
        "qa-reports",
        ".md-backups",
    ]
    files = [
        f for f in files
        if not any(ex in f.relative_to(site["source_dir"]).parts for ex in excludes)
    ]
    return files


def is_in_archive(path: Path) -> bool:
    """Return True if path is inside any _archive/, archive/, or .trash/ directory."""
    parts = path.parts
    for marker in ("_archive", "archive", "_trash", ".trash", "_removal"):
        if marker in parts:
            return True
    return False
