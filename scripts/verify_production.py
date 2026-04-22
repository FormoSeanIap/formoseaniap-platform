#!/usr/bin/env python3
"""Reusable production verification for the Formoseaniap platform.

Bypasses Cloudflare by connecting directly to CloudFront via IP + SNI.
Covers every deployed contract from Lanes A-E, Task 3, and Phases 1-3.

Usage::

    python3 scripts/verify_production.py

Exit code 0 = all checks pass, 1 = at least one failure.

Design notes
------------
- Standard-library only (http.client, ssl, socket, json, re).
- Each check is a small function that calls ``check()`` to record pass/fail.
- The ``fetch()`` helper opens a fresh TLS connection per request to avoid
  connection-reuse issues with CloudFront edge nodes.
- MIME-type assertions on every fingerprinted asset catch the class of bug
  where ``aws s3 cp --metadata-directive REPLACE`` drops Content-Type.
"""

from __future__ import annotations

import http.client
import json
import re
import socket
import ssl
import sys
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CLOUDFRONT_HOST = "d2esa661qwpx1f.cloudfront.net"
SITE_HOST = "www.formoseaniap.com"
TIMEOUT = 20

# Expected MIME types for fingerprinted assets.
EXPECTED_MIME: dict[str, str] = {
    ".css": "text/css",
    ".js": "application/javascript",
}

# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

_cf_ip: Optional[str] = None


def _resolve_cf_ip() -> str:
    global _cf_ip
    if _cf_ip is None:
        _cf_ip = socket.gethostbyname(CLOUDFRONT_HOST)
    return _cf_ip


def fetch(
    path: str,
    method: str = "GET",
    data: Optional[bytes] = None,
    headers: Optional[dict] = None,
) -> tuple[int, dict[str, str], bytes]:
    """Fetch a path via CloudFront direct (bypass Cloudflare)."""
    ip = _resolve_cf_ip()
    ctx = ssl.create_default_context()
    ctx.check_hostname = True
    raw = socket.create_connection((ip, 443), timeout=TIMEOUT)
    tls = ctx.wrap_socket(raw, server_hostname=SITE_HOST)
    conn = http.client.HTTPSConnection(SITE_HOST, 443, timeout=TIMEOUT, context=ctx)
    conn.sock = tls
    merged = {"Host": SITE_HOST, "User-Agent": "verify-production/1.0", "Accept": "*/*"}
    if headers:
        merged.update(headers)
    conn.request(method, path, body=data, headers=merged)
    resp = conn.getresponse()
    body = resp.read()
    hdrs = {k.lower(): v for k, v in resp.getheaders()}
    conn.close()
    return resp.status, hdrs, body


# ---------------------------------------------------------------------------
# Check infrastructure
# ---------------------------------------------------------------------------

_results: list[tuple[str, str, str]] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    _results.append(("PASS" if ok else "FAIL", label, detail))


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

# Pages to scan (both trees, excluding engineering about which doesn't exist).
MAIN_PAGES = [
    "/", "/articles.html", "/artworks.html", "/podcasts.html",
    "/projects.html", "/about.html", "/article.html",
    "/admin/analytics.html",
]
ENG_PAGES = [
    "/engineer/", "/engineer/articles.html", "/engineer/projects.html",
    "/engineer/article.html", "/engineer/admin/analytics.html",
]
ALL_PAGES = MAIN_PAGES + ENG_PAGES

# Cache fetched HTML for reuse across checks.
_page_cache: dict[str, tuple[int, dict[str, str], str]] = {}


def _get_page(path: str) -> tuple[int, dict[str, str], str]:
    if path not in _page_cache:
        status, hdrs, body = fetch(path)
        _page_cache[path] = (status, hdrs, body.decode("utf-8", errors="replace"))
    return _page_cache[path]


def check_favicons() -> None:
    """Favicon assets serve 200 with correct content-type."""
    for path, expected_ct in [
        ("/favicon.ico", "image/"),
        ("/favicon.svg", "image/svg"),
        ("/favicon-dark.svg", "image/svg"),
        ("/apple-touch-icon.png", "image/png"),
    ]:
        status, hdrs, body = fetch(path)
        ct = hdrs.get("content-type", "")
        check(f"favicon {path}", status == 200 and expected_ct in ct and len(body) > 0,
              f"HTTP {status}, CT={ct}, {len(body)}B")


def check_icon_links() -> None:
    """Every page carries favicon link tags."""
    markers = ['rel="icon"', 'rel="apple-touch-icon"', 'href="/favicon.svg"', 'href="/favicon.ico"']
    for path in ALL_PAGES:
        status, _, html = _get_page(path)
        missing = [m for m in markers if m not in html]
        check(f"icon links {path}", status == 200 and not missing,
              f"HTTP {status}" + (f", missing={missing}" if missing else ""))


def check_custom_404() -> None:
    """Bogus URLs return styled 404 page, not S3 XML."""
    for path in ("/definitely-not-real.html", "/engineer/bogus.html"):
        status, hdrs, body = fetch(path)
        html = body.decode("utf-8", errors="replace")
        styled = "Page not found" in html and "<Error>" not in html
        check(f"404 {path}", status == 404 and styled, f"HTTP {status}, styled={styled}")


def check_paired_urls() -> None:
    """Main and engineering paired URLs serve distinct content."""
    for left, right in [("/", "/engineer/"), ("/projects.html", "/engineer/projects.html"),
                         ("/articles.html", "/engineer/articles.html")]:
        _, hl, bl = fetch(left)
        _, hr, br = fetch(right)
        el = hl.get("etag", "")
        er = hr.get("etag", "")
        check(f"paired {left} vs {right}", bl != br and el != er,
              f"body-distinct={bl != br}, etag-distinct={el != er}")


def check_shared_assets() -> None:
    """Shared CSS byte-identical across trees; analytics.js deliberately different."""
    for path in ("/assets/css/base.css", "/assets/css/components.css"):
        _, _, bm = fetch(path)
        _, _, be = fetch(f"/engineer{path}")
        check(f"shared {path}", bm == be and len(bm) > 0, f"main={len(bm)}, eng={len(be)}")

    _, _, am = fetch("/assets/js/analytics.js")
    _, _, ae = fetch("/engineer/assets/js/analytics.js")
    check("analytics.js different", am != ae and b"main" in am and b"engineering" in ae)


def check_security_headers() -> None:
    """Security response headers present."""
    _, hdrs, _ = fetch("/")
    for h in ["strict-transport-security", "x-content-type-options", "referrer-policy", "x-frame-options"]:
        check(f"header {h}", bool(hdrs.get(h, "")))


def check_seo() -> None:
    """Canonical, robots, sitemap, OG tags."""
    _, _, html = _get_page("/")
    check("canonical /", 'rel="canonical"' in html and 'href="https://www.formoseaniap.com/"' in html)

    status, _, body = fetch("/robots.txt")
    check("robots.txt", status == 200 and b"Sitemap:" in body)

    status, _, body = fetch("/sitemap.xml")
    sitemap = body.decode("utf-8", errors="replace")
    article_count = len(re.findall(r"article\.html\?id=", sitemap))
    check("sitemap articles", status == 200 and article_count > 50, f"{article_count} article URLs")

    status, _, body = fetch("/engineer/sitemap.xml")
    eng_sitemap = body.decode("utf-8", errors="replace")
    eng_count = len(re.findall(r"article\.html\?id=", eng_sitemap))
    check("eng sitemap articles", status == 200 and eng_count > 10, f"{eng_count} article URLs")


def check_og_image() -> None:
    """OG image tags present and image serves correctly."""
    _, _, html = _get_page("/")
    check("og:image on /", 'property="og:image"' in html and "/assets/og/default.png" in html)
    check("twitter:image on /", 'name="twitter:image"' in html and "/assets/og/default.png" in html)
    check("summary_large_image", 'content="summary_large_image"' in html)

    status, hdrs, body = fetch("/assets/og/default.png")
    ct = hdrs.get("content-type", "")
    check("OG image serves", status == 200 and "image/png" in ct and len(body) > 10000,
          f"HTTP {status}, CT={ct}, {len(body)}B")


def check_a11y_basics() -> None:
    """Skip link and admin noindex."""
    _, _, html = _get_page("/about.html")
    check("skip link", "skip-link" in html or "Skip to main content" in html)

    for path in ("/admin/analytics.html", "/engineer/admin/analytics.html"):
        _, _, html = _get_page(path)
        check(f"noindex {path}", 'name="robots"' in html and "noindex" in html)


def check_analytics() -> None:
    """Analytics collector round-trip and OPTIONS preflight."""
    payload = json.dumps({
        "scope": "page", "page_key": "home",
        "visitor_id": "verify-prod-xxxxxxxxxxxxxxxx", "domain": "main",
    }).encode()
    status, _, body = fetch("/analytics-api/collect", method="POST", data=payload,
                            headers={"Content-Type": "application/json"})
    check("analytics 202", status == 202, f"HTTP {status}")

    # OPTIONS preflight — should return 204 with CORS headers from the
    # CloudFront Function, not a 404 from the API Gateway origin.
    status, hdrs, _ = fetch(
        "/analytics-api/collect",
        method="OPTIONS",
        headers={
            "Origin": f"https://{SITE_HOST}",
            "Access-Control-Request-Method": "POST",
        },
    )
    acao = hdrs.get("access-control-allow-origin", "")
    acam = hdrs.get("access-control-allow-methods", "")
    check("OPTIONS preflight 204",
          status == 204 and SITE_HOST in acao and "POST" in acam,
          f"HTTP {status}, ACAO={acao}, ACAM={acam}")


def check_fingerprinted_assets() -> None:
    """Fingerprinted CSS/JS in HTML, correct MIME types, immutable cache."""
    fp_re = re.compile(r'(?:href|src)="([^"]*assets/(?:css|js)/[a-z-]+\.[0-9a-f]{10}\.(css|js))"')

    _, _, html = _get_page("/")
    matches = fp_re.findall(html)
    check("fingerprinted refs /", len(matches) >= 4, f"{len(matches)} refs")

    for ref, ext in matches:
        # Resolve relative URL
        asset_path = "/" + ref if not ref.startswith("/") else ref
        status, hdrs, body = fetch(asset_path)
        ct = hdrs.get("content-type", "")
        cc = hdrs.get("cache-control", "")
        expected = EXPECTED_MIME.get(f".{ext}", "")

        check(f"MIME {asset_path}",
              status == 200 and expected in ct,
              f"HTTP {status}, CT={ct}, expected={expected}")
        check(f"immutable {asset_path}",
              "immutable" in cc,
              f"CC={cc}")

    # Also check engineering tree
    _, _, eng_html = _get_page("/engineer/")
    eng_matches = fp_re.findall(eng_html)
    check("fingerprinted refs /engineer/", len(eng_matches) >= 4, f"{len(eng_matches)} refs")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ip = _resolve_cf_ip()
    print(f"CloudFront IP: {ip} (host: {SITE_HOST})\n")

    check_favicons()
    check_icon_links()
    check_custom_404()
    check_paired_urls()
    check_shared_assets()
    check_security_headers()
    check_seo()
    check_og_image()
    check_a11y_basics()
    check_analytics()
    check_fingerprinted_assets()

    passes = sum(1 for s, *_ in _results if s == "PASS")
    fails = sum(1 for s, *_ in _results if s == "FAIL")
    print(f"\n=== Production verification — {passes} PASS / {fails} FAIL ===\n")
    for status, label, detail in _results:
        marker = "✓" if status == "PASS" else "✗"
        print(f"  {marker} {status}  {label}")
        if detail and status == "FAIL":
            print(f"           {detail}")

    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
