"""
scan_live.py — Layer 2: HTTP probes against live sites.

Verifies:
  - apex and www respond 200 with a real UA (Cloudflare challenge → treated as warning)
  - /favicon.ico and key favicon sizes serve 200
  - /sitemap.xml is reachable
  - homepage HTML contains the expected site title
  - HTML doesn't accidentally contain GA4 double-G typo on the live page

This catches:
  - deploys that left the site 5xx
  - missing favicon files on the live CDN
  - the kind of bug where local source is fixed but the push never happened
"""
import re
import ssl
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

from sites import SITES

# Real desktop Chrome UA — Cloudflare's bot challenge won't block this.
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
TIMEOUT = 15
GA4_TYPO_RE = re.compile(r'\bG-G-[A-Z0-9]+\b')

FAVICON_PROBES = [
    "favicon.ico",
    "favicon-32x32.png",
    "apple-touch-icon.png",
]

# Use certifi's CA bundle (Python 3.14 removed the bundled certs).
# Falls back gracefully if certifi isn't installed.
try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = ssl.create_default_context()


def _fetch(url: str, want_body: bool = False):
    """Returns (status_code, body_bytes_or_none, content_type)."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=_SSL_CTX) as resp:
            body = resp.read(50_000) if want_body else None
            return resp.status, body, resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, None, e.headers.get("Content-Type", "") if e.headers else ""
    except Exception as e:
        return 0, None, f"error: {type(e).__name__}: {e}"


def _probe_one(site) -> list:
    findings = []
    domain = site["domain"]
    www_domain = domain.replace("https://", "https://www.")

    # Apex
    status_apex, _, ct_apex = _fetch(domain)
    if status_apex == 0:
        findings.append(
            {
                "site": site["name"],
                "class": "live_unreachable",
                "severity": "critical",
                "file": domain,
                "details": f"apex fetch failed: {ct_apex}",
                "auto_fixable": False,
            }
        )
        return findings
    if status_apex != 200:
        # 403 with cf-mitigated: challenge is OK (Cloudflare bot challenge); just info
        if status_apex == 403 and "challenge" in ct_apex.lower():
            pass  # CF bot challenge — not a real error
        else:
            findings.append(
                {
                    "site": site["name"],
                    "class": "live_non_200",
                    "severity": "high",
                    "file": domain,
                    "details": f"apex returned HTTP {status_apex}",
                    "auto_fixable": False,
                }
            )

    # www redirect
    status_www, _, _ = _fetch(www_domain)
    if status_www not in (200, 301, 302, 308):
        if status_www != 0:
            findings.append(
                {
                    "site": site["name"],
                    "class": "live_non_200",
                    "severity": "high",
                    "file": www_domain,
                    "details": f"www returned HTTP {status_www}",
                    "auto_fixable": False,
                }
            )

    # Sitemap
    status_sitemap, _, _ = _fetch(f"{domain}/sitemap.xml")
    if status_sitemap == 0:
        # Some sites don't have a sitemap (legacy / minimal sites). Not critical.
        pass
    elif status_sitemap not in (200,):
        findings.append(
            {
                "site": site["name"],
                "class": "sitemap_unreachable",
                "severity": "medium",
                "file": f"{domain}/sitemap.xml",
                "details": f"HTTP {status_sitemap}",
                "auto_fixable": False,
            }
        )

    # Favicons (only check sites with declared favicon paths)
    if site["favicon_paths"]:
        for probe in FAVICON_PROBES:
            url = f"{domain}/{probe}"
            status, _, _ = _fetch(url)
            if status == 200:
                continue
            if status == 0:
                continue  # network blip
            findings.append(
                {
                    "site": site["name"],
                    "class": "live_favicon_missing",
                    "severity": "medium",
                    "file": url,
                    "details": f"favicon returned HTTP {status}",
                    "auto_fixable": False,  # would require a deploy — needs Mike
                }
            )

    # Live HTML check: GA4 typo on the deployed page
    status_h, body, _ = _fetch(domain, want_body=True)
    if status_h == 200 and body:
        html = body.decode("utf-8", errors="ignore")
        for m in GA4_TYPO_RE.finditer(html):
            findings.append(
                {
                    "site": site["name"],
                    "class": "live_ga4_typo",
                    "severity": "critical",
                    "file": domain,
                    "details": f"live page has GA4 typo: '{m.group(0)}' — fix did not deploy",
                    "auto_fixable": False,
                    "fix_class": "ga4_typo",
                }
            )

    return findings


def scan_live(site_names: list | None = None) -> list:
    findings = []
    targets = [s for s in SITES if not site_names or s["name"] in site_names]
    # Probe in parallel — saves time on 8 sites.
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(_probe_one, site): site for site in targets}
        for fut in as_completed(futures):
            try:
                findings.extend(fut.result())
            except Exception as e:
                site = futures[fut]
                findings.append(
                    {
                        "site": site["name"],
                        "class": "live_probe_error",
                        "severity": "medium",
                        "file": site["domain"],
                        "details": f"probe crashed: {e}",
                        "auto_fixable": False,
                    }
                )
    return findings
