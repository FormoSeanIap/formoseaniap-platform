"""Synchronize shared static assets from ``site/`` to ``site-eng/``.

The main site under ``site/assets/`` is the canonical source of truth for
CSS and JavaScript that the engineering section under ``site-eng/`` also
uses. A small set of files are intentionally not shared:

* ``site/assets/css/podcasts.css`` and ``site/assets/js/podcasts.js`` --
  only the main site has a podcasts page.
* ``site/assets/js/analytics.js`` vs ``site-eng/assets/js/analytics.js`` --
  both trees deliberately differ by two lines (per-domain ``PAGE_KEYS``
  allow-list and the ``domain`` tag attached to every collect event).
  Each file stays tracked independently so the filter cannot drift.

Run this script as part of local preview startup and CI so both trees
ship the same shared CSS/JS without keeping byte-identical duplicates in
version control.

Usage::

    python3 scripts/sync_shared_assets.py          # copy source -> dest
    python3 scripts/sync_shared_assets.py --check  # fail if dest drifts
"""

from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
SOURCE_ASSETS_DIR = ROOT_DIR / "site" / "assets"
TARGET_ASSETS_DIR = ROOT_DIR / "site-eng" / "assets"

SHARED_CSS_FILES = (
    "admin.css",
    "base.css",
    "components.css",
    "layout.css",
    "variables.css",
)
SHARED_JS_FILES = (
    "admin-analytics.js",
    "articles.js",
    "main.js",
    "progressive-list.js",
    "projects.js",
)


def shared_file_pairs() -> list[tuple[Path, Path]]:
    """Return (source, target) pairs for every shared asset file."""
    pairs: list[tuple[Path, Path]] = []
    for name in SHARED_CSS_FILES:
        pairs.append((SOURCE_ASSETS_DIR / "css" / name, TARGET_ASSETS_DIR / "css" / name))
    for name in SHARED_JS_FILES:
        pairs.append((SOURCE_ASSETS_DIR / "js" / name, TARGET_ASSETS_DIR / "js" / name))
    return pairs


def _display_path(path: Path) -> str:
    """Render ``path`` relative to the repo root when possible, else absolute."""
    try:
        return str(path.relative_to(ROOT_DIR))
    except ValueError:
        return str(path)


def sync(*, check_only: bool) -> int:
    """Copy (or verify) every shared asset from ``site/`` to ``site-eng/``.

    Returns a process exit code: ``0`` when the target matches the source
    (either after copying, or already in sync in ``--check`` mode), ``1``
    when ``--check`` mode detects drift, and ``2`` when a source file is
    missing on disk.
    """
    drift: list[Path] = []
    missing_sources: list[Path] = []

    for source, target in shared_file_pairs():
        if not source.is_file():
            missing_sources.append(source)
            continue

        if check_only:
            if not target.is_file() or not filecmp.cmp(source, target, shallow=False):
                drift.append(target)
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file() and filecmp.cmp(source, target, shallow=False):
            continue
        shutil.copyfile(source, target)

    if missing_sources:
        print(
            "Missing shared asset source file(s); cannot sync site-eng/:",
            file=sys.stderr,
        )
        for path in missing_sources:
            print(f"  - {_display_path(path)}", file=sys.stderr)
        return 2

    if check_only and drift:
        print(
            "Shared asset drift detected; run `python3 scripts/sync_shared_assets.py`:",
            file=sys.stderr,
        )
        for path in drift:
            print(f"  - {_display_path(path)}", file=sys.stderr)
        return 1

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when site-eng/assets/ differs from site/assets/ instead of copying.",
    )
    args = parser.parse_args()
    return sync(check_only=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
