"""Guard against PAGE_KEYS drift between the frontend trackers and backend.

The public page-tracking allow-list lives in three places today:

* ``analytics_backend.config.ALLOWED_PAGE_KEYS`` -- the collector validates
  every incoming event against this set.
* ``site/assets/js/analytics.js`` -- main-site tracker subset.
* ``site-eng/assets/js/analytics.js`` -- engineering-section tracker subset.

Each frontend file intentionally only contains the keys that its own
section can emit, which keeps a main-site page from accidentally tagging
itself as engineering and vice versa. That per-domain filter is a safety
feature, so this test does not try to unify the three sources into one
file. Instead, it fails fast if the **union** of the two frontend lists
ever drifts from the backend allow-list -- that is the silent footgun
that would make a new page's analytics disappear until someone noticed.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from analytics_backend.config import ALLOWED_PAGE_KEYS


ROOT_DIR = Path(__file__).resolve().parent.parent
MAIN_ANALYTICS_JS = ROOT_DIR / "site" / "assets" / "js" / "analytics.js"
ENG_ANALYTICS_JS = ROOT_DIR / "site-eng" / "assets" / "js" / "analytics.js"

# Matches: const PAGE_KEYS = new Set(["a", "b", "c"]);
# Tolerant to whitespace and single or double quotes inside the Set literal.
PAGE_KEYS_RE = re.compile(
    r"const\s+PAGE_KEYS\s*=\s*new\s+Set\(\s*\[([^\]]*)\]\s*\)\s*;",
    re.MULTILINE,
)
QUOTED_KEY_RE = re.compile(r"""(?:"([^"]+)"|'([^']+)')""")


def parse_frontend_page_keys(source: str) -> set[str]:
    match = PAGE_KEYS_RE.search(source)
    if not match:
        raise AssertionError(
            "Could not locate `const PAGE_KEYS = new Set([...])` in the analytics tracker."
        )
    keys: set[str] = set()
    for double, single in QUOTED_KEY_RE.findall(match.group(1)):
        keys.add(double or single)
    if not keys:
        raise AssertionError("PAGE_KEYS set literal appears to be empty.")
    return keys


class PageKeysDriftTests(unittest.TestCase):
    def test_frontend_files_declare_disjoint_key_sets(self) -> None:
        main_keys = parse_frontend_page_keys(MAIN_ANALYTICS_JS.read_text(encoding="utf-8"))
        eng_keys = parse_frontend_page_keys(ENG_ANALYTICS_JS.read_text(encoding="utf-8"))
        overlap = main_keys & eng_keys
        self.assertFalse(
            overlap,
            f"Main-site and engineering PAGE_KEYS must not overlap; found {sorted(overlap)}",
        )

    def test_backend_allowed_page_keys_matches_union_of_frontends(self) -> None:
        main_keys = parse_frontend_page_keys(MAIN_ANALYTICS_JS.read_text(encoding="utf-8"))
        eng_keys = parse_frontend_page_keys(ENG_ANALYTICS_JS.read_text(encoding="utf-8"))
        frontend_union = main_keys | eng_keys
        self.assertEqual(
            frozenset(frontend_union),
            ALLOWED_PAGE_KEYS,
            "analytics_backend.config.ALLOWED_PAGE_KEYS must equal the union of "
            "the main-site and engineering-site PAGE_KEYS sets. "
            "Update all three together when adding or removing a page.",
        )


if __name__ == "__main__":
    unittest.main()
