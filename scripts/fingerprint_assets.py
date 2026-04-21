#!/usr/bin/env python3
"""Fingerprint shared CSS/JS assets and rewrite HTML references.

Why
---
CloudFront currently serves `/assets/css/*.css` and `/assets/js/*.js` with a
short default TTL, which means every reader re-downloads unchanged files on
that cadence. Fingerprinting the filename (`components.<hash>.css`) unlocks a
year-long `Cache-Control: public, max-age=31536000, immutable` header because
the filename changes on every content change. HTML keeps its short TTL, so
new filenames propagate within the existing deploy invalidation window.

What this script does
---------------------
1. Hashes every file under `site/assets/css/` and `site/assets/js/` (content-
   based SHA-256, truncated to 10 chars for URL-friendliness).
2. Copies each file to a fingerprinted companion, e.g.
   `site/assets/css/components.a3f5d8b901.css`. The original is left in place
   so that anything that still references the non-fingerprinted URL keeps
   working. The production S3 sync step uploads both; only the fingerprinted
   variant receives the immutable cache-control header.
3. Rewrites every `<link rel="stylesheet" href="assets/css/<name>">` and
   `<script src="assets/js/<name>">` reference in every HTML page under
   `site/` and `site-eng/` to point at the fingerprinted filename. Works for
   both root-relative (`assets/css/base.css`) and parent-relative
   (`../assets/css/base.css`) references so admin pages are covered.
4. Writes `site/assets/asset-manifest.json` and
   `site-eng/assets/asset-manifest.json` (identical content) so the deploy
   step can enumerate fingerprinted filenames for cache-header targeting.
5. Mirrors the fingerprinted copies + manifest into `site-eng/assets/*` to
   match the existing `scripts/sync_shared_assets.py` topology.

Idempotence
-----------
The script is safe to re-run on a clean checkout because fingerprinted
filenames are derived purely from file contents. Running the script twice
produces the same output.

Running it on a tree that already has fingerprinted copies from a previous
run cleans them up first so stale hashes don't accumulate.

Design notes
------------
- Deliberately standard-library-only (hashlib, shutil, re, json, pathlib),
  same convention as the other build scripts.
- Leaves `site/assets/articles/**` untouched — those images are content,
  not shared assets, and fingerprinting them would add noise without clear
  benefit.
- Does not fingerprint inline `<style>` or `<script>` blocks.
- Does not touch `site/data/*.json` (content payload) or Google Fonts links.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
SITE_DIR = ROOT / "site"
ENG_SITE_DIR = ROOT / "site-eng"

# Relative paths (inside site/) of the assets eligible for fingerprinting.
ASSET_DIRS = ("assets/css", "assets/js")

# File extensions we fingerprint and rewrite references for.
ASSET_EXTS = (".css", ".js")

# Length of the hash slice used in filenames. 10 chars of SHA-256 hex gives a
# ~1 in 10^12 collision probability across a small number of files, which is
# plenty for a personal portfolio. Short enough to keep URLs readable.
HASH_LENGTH = 10

# Fingerprinted filename pattern: <basename>.<10-hex-char-hash>.<ext>.
FINGERPRINTED_RE = re.compile(r"^(?P<base>.+)\.[0-9a-f]{%d}\.(?P<ext>css|js)$" % HASH_LENGTH)

# Relative path of the asset manifest emitted at build time.
MANIFEST_REL = "assets/asset-manifest.json"


def file_hash(path: Path) -> str:
    """Return the first HASH_LENGTH hex chars of the file's SHA-256 digest."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()[:HASH_LENGTH]


def fingerprinted_name(original: Path, digest: str) -> str:
    """Return `<basename>.<digest>.<ext>` for a source file."""
    return f"{original.stem}.{digest}{original.suffix}"


def remove_existing_fingerprinted_copies(asset_dir: Path) -> None:
    """Delete any `<base>.<hash>.<ext>` files left from a previous run."""
    if not asset_dir.exists():
        return
    for child in asset_dir.iterdir():
        if not child.is_file():
            continue
        if FINGERPRINTED_RE.match(child.name):
            child.unlink()


def fingerprint_tree(site_root: Path) -> dict[str, str]:
    """Fingerprint assets under a site tree. Returns `{original_rel: fingerprinted_rel}`.

    Keys and values are POSIX-style relative paths under ``site_root``
    (e.g. ``"assets/css/base.css"``).
    """
    manifest: dict[str, str] = {}

    for asset_dir_rel in ASSET_DIRS:
        asset_dir = site_root / asset_dir_rel
        if not asset_dir.is_dir():
            continue

        remove_existing_fingerprinted_copies(asset_dir)

        for original in sorted(asset_dir.iterdir()):
            if not original.is_file() or original.suffix not in ASSET_EXTS:
                continue
            digest = file_hash(original)
            fp_name = fingerprinted_name(original, digest)
            fp_path = asset_dir / fp_name
            # Copy rather than rename so the non-fingerprinted original stays
            # in place as a safety net if HTML ever ends up referencing it.
            shutil.copyfile(original, fp_path)

            original_rel = f"{asset_dir_rel}/{original.name}"
            fingerprinted_rel = f"{asset_dir_rel}/{fp_name}"
            manifest[original_rel] = fingerprinted_rel

    return manifest


def rewrite_html_file(path: Path, manifest: dict[str, str]) -> bool:
    """Rewrite CSS/JS references in the given HTML file using the manifest.

    Idempotent: if the file already contains fingerprinted references from a
    previous run (e.g. the HTML source was committed after a local build),
    they are first reverted to their un-fingerprinted originals and then
    rewritten to the current hashes. That keeps the rewrite correct whether
    the input is a clean source file or already-fingerprinted artifact.

    Returns True if the file was changed.
    """
    original = path.read_text(encoding="utf-8")
    updated = original

    # Step 1: normalize. Any `<base>.<10hex>.<ext>` inside an
    # `assets/{css,js}/` reference is stripped back to `<base>.<ext>` so step
    # 2 can apply the current hashes cleanly. Covers root-absolute
    # (`/assets/...`), root-relative (`assets/...`), and parent-relative
    # (`../assets/...`) forms.
    normalize_pattern = re.compile(
        r'(?P<prefix>href="|src=")(?P<relative>/?(?:\.\./)*assets/(?:css|js)/)'
        r'(?P<base>[A-Za-z0-9_-]+)\.[0-9a-f]{%d}\.(?P<ext>css|js)"' % HASH_LENGTH
    )
    updated = normalize_pattern.sub(
        lambda m: f'{m.group("prefix")}{m.group("relative")}{m.group("base")}.{m.group("ext")}"',
        updated,
    )

    # Step 2: apply current fingerprints from the manifest.
    for original_rel, fp_rel in manifest.items():
        pattern = re.compile(
            r'(?P<prefix>href="|src=")(?P<relative>/?(?:\.\./)*)'
            + re.escape(original_rel)
            + r'"'
        )
        updated = pattern.sub(
            lambda m: f'{m.group("prefix")}{m.group("relative")}{fp_rel}"',
            updated,
        )

    if updated != original:
        path.write_text(updated, encoding="utf-8")
        return True
    return False


def iter_html_files(site_root: Path) -> Iterable[Path]:
    if not site_root.is_dir():
        return
    yield from sorted(site_root.rglob("*.html"))


def write_manifest(site_root: Path, manifest: dict[str, str]) -> Path:
    out_path = site_root / MANIFEST_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return out_path


def mirror_to_engineering_tree(manifest: dict[str, str]) -> None:
    """Copy fingerprinted files from site/ to site-eng/ for parity.

    The engineering tree already mirrors the non-fingerprinted sources via
    `scripts/sync_shared_assets.py`. After fingerprinting we need to mirror
    the new hashed copies too so `/engineer/assets/css/components.<hash>.css`
    serves the same bytes as `/assets/css/components.<hash>.css`.
    """
    for _, fp_rel in manifest.items():
        source = SITE_DIR / fp_rel
        target = ENG_SITE_DIR / fp_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def _rel_to_root(path: Path) -> str:
    """Format a path relative to ROOT if possible, otherwise as-is."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def main() -> int:
    if not SITE_DIR.is_dir():
        raise FileNotFoundError(f"Missing site directory: {SITE_DIR}")

    manifest = fingerprint_tree(SITE_DIR)
    if not manifest:
        print("No shared assets to fingerprint under site/assets/css or site/assets/js.")
        return 0

    # Mirror the fingerprinted copies into the engineering tree and also clear
    # stale fingerprinted copies that may still live there from an older run.
    for asset_dir_rel in ASSET_DIRS:
        remove_existing_fingerprinted_copies(ENG_SITE_DIR / asset_dir_rel)
    mirror_to_engineering_tree(manifest)

    # Write the asset manifest into both trees so the deploy step can see it.
    manifest_main = write_manifest(SITE_DIR, manifest)
    manifest_eng = write_manifest(ENG_SITE_DIR, manifest)

    # Rewrite HTML references across both trees.
    changed = 0
    for html_path in iter_html_files(SITE_DIR):
        if rewrite_html_file(html_path, manifest):
            changed += 1
    for html_path in iter_html_files(ENG_SITE_DIR):
        if rewrite_html_file(html_path, manifest):
            changed += 1

    print(f"Fingerprinted {len(manifest)} asset(s) across site/ and site-eng/.")
    print(f"Rewrote references in {changed} HTML file(s).")
    print(f"Wrote manifest: {_rel_to_root(manifest_main)}")
    print(f"Wrote manifest: {_rel_to_root(manifest_eng)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
