"""Tests for scripts/fingerprint_assets.py.

The fingerprinter is safety-critical: if it rewrites an HTML reference to a
fingerprinted filename that doesn't actually exist in the artifact, readers
see broken styling in production. These tests cover:

- basic rename + manifest emission for a synthetic tree
- idempotence across repeated runs on already-rewritten HTML
- rewrite behaviour for root-relative, parent-relative, and absolute hrefs
- that cleanup removes stale fingerprinted copies from previous runs
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import fingerprint_assets  # noqa: E402


class FingerprintAssetsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.site = self.tmp / "site"
        self.eng = self.tmp / "site-eng"
        (self.site / "assets" / "css").mkdir(parents=True)
        (self.site / "assets" / "js").mkdir(parents=True)
        (self.eng / "assets" / "css").mkdir(parents=True)
        (self.eng / "assets" / "js").mkdir(parents=True)

        # Point the module at our sandbox. The fingerprinter references
        # SITE_DIR and ENG_SITE_DIR as module-level Paths.
        self._orig_site = fingerprint_assets.SITE_DIR
        self._orig_eng = fingerprint_assets.ENG_SITE_DIR
        fingerprint_assets.SITE_DIR = self.site
        fingerprint_assets.ENG_SITE_DIR = self.eng
        self.addCleanup(setattr, fingerprint_assets, "SITE_DIR", self._orig_site)
        self.addCleanup(setattr, fingerprint_assets, "ENG_SITE_DIR", self._orig_eng)

    def _write_css(self, name: str, body: str) -> Path:
        path = self.site / "assets" / "css" / name
        path.write_text(body, encoding="utf-8")
        return path

    def _write_js(self, name: str, body: str) -> Path:
        path = self.site / "assets" / "js" / name
        path.write_text(body, encoding="utf-8")
        return path

    def _write_html(self, relative: str, body: str, eng: bool = False) -> Path:
        root = self.eng if eng else self.site
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return path

    def test_basic_fingerprinting_emits_manifest_and_renames(self) -> None:
        self._write_css("base.css", "body { margin: 0; }")
        self._write_js("main.js", "console.log('hi')")
        index = self._write_html(
            "index.html",
            '<link href="assets/css/base.css"><script src="assets/js/main.js"></script>',
        )

        rc = fingerprint_assets.main()
        self.assertEqual(rc, 0)

        manifest_path = self.site / "assets" / "asset-manifest.json"
        self.assertTrue(manifest_path.exists())

        import json
        manifest = json.loads(manifest_path.read_text())

        self.assertIn("assets/css/base.css", manifest)
        self.assertIn("assets/js/main.js", manifest)
        # Fingerprinted filenames are <base>.<10hex>.<ext>
        self.assertRegex(manifest["assets/css/base.css"], r"^assets/css/base\.[0-9a-f]{10}\.css$")
        self.assertRegex(manifest["assets/js/main.js"], r"^assets/js/main\.[0-9a-f]{10}\.js$")

        # Fingerprinted copies exist on disk
        self.assertTrue((self.site / manifest["assets/css/base.css"]).exists())
        self.assertTrue((self.site / manifest["assets/js/main.js"]).exists())

        # Originals are still in place
        self.assertTrue((self.site / "assets/css/base.css").exists())
        self.assertTrue((self.site / "assets/js/main.js").exists())

        # HTML references were rewritten
        updated = index.read_text()
        self.assertIn(manifest["assets/css/base.css"], updated)
        self.assertIn(manifest["assets/js/main.js"], updated)
        self.assertNotRegex(updated, r'href="assets/css/base\.css"')

    def test_idempotence_across_repeated_runs(self) -> None:
        self._write_css("base.css", "body { margin: 0; }")
        self._write_js("main.js", "console.log('hi')")
        index = self._write_html(
            "index.html",
            '<link href="assets/css/base.css"><script src="assets/js/main.js"></script>',
        )

        fingerprint_assets.main()
        first_html = index.read_text()
        first_fp_files = sorted(str(p.name) for p in (self.site / "assets" / "css").iterdir())

        # Second run on already-rewritten HTML should be a no-op for output.
        fingerprint_assets.main()
        second_html = index.read_text()
        second_fp_files = sorted(str(p.name) for p in (self.site / "assets" / "css").iterdir())

        self.assertEqual(first_html, second_html, "HTML drifted across runs")
        self.assertEqual(first_fp_files, second_fp_files, "fingerprinted files drifted")

    def test_rewrites_root_relative_parent_relative_and_absolute_refs(self) -> None:
        self._write_css("base.css", "body { margin: 0; }")
        self._write_js("main.js", "console.log('hi')")

        # Three different href shapes that all mean the same asset
        self._write_html(
            "index.html",
            '<link href="assets/css/base.css">',
        )
        self._write_html(
            "admin/analytics.html",
            '<link href="../assets/css/base.css">',
        )
        self._write_html(
            "404.html",
            '<link href="/assets/css/base.css"><script src="/assets/js/main.js"></script>',
        )

        fingerprint_assets.main()

        import json
        manifest = json.loads((self.site / "assets" / "asset-manifest.json").read_text())
        fp_css = manifest["assets/css/base.css"]
        fp_js = manifest["assets/js/main.js"]

        self.assertIn(f'href="{fp_css}"', (self.site / "index.html").read_text())
        self.assertIn(f'href="../{fp_css}"', (self.site / "admin" / "analytics.html").read_text())
        self.assertIn(f'href="/{fp_css}"', (self.site / "404.html").read_text())
        self.assertIn(f'src="/{fp_js}"', (self.site / "404.html").read_text())

    def test_cleanup_removes_stale_fingerprinted_copies(self) -> None:
        self._write_css("base.css", "v1")
        self._write_html("index.html", '<link href="assets/css/base.css">')
        fingerprint_assets.main()

        import json
        first_fp = json.loads((self.site / "assets" / "asset-manifest.json").read_text())["assets/css/base.css"]
        self.assertTrue((self.site / first_fp).exists())

        # Change asset content → hash changes on second run
        self._write_css("base.css", "v2")
        fingerprint_assets.main()

        second_fp = json.loads((self.site / "assets" / "asset-manifest.json").read_text())["assets/css/base.css"]
        self.assertNotEqual(first_fp, second_fp, "hash should change when content changes")

        # Stale fingerprinted copy from first run is gone
        self.assertFalse((self.site / first_fp).exists(), "stale fingerprinted copy should be removed")
        self.assertTrue((self.site / second_fp).exists())

        # HTML references the current hash, not the stale one
        html = (self.site / "index.html").read_text()
        self.assertIn(second_fp, html)
        self.assertNotIn(first_fp, html)

    def test_engineering_tree_receives_mirrored_fingerprinted_copies(self) -> None:
        self._write_css("base.css", "body { margin: 0; }")
        self._write_html("index.html", '<link href="assets/css/base.css">')
        self._write_html(
            "index.html",
            '<link href="assets/css/base.css">',
            eng=True,
        )

        fingerprint_assets.main()

        import json
        manifest_main = json.loads((self.site / "assets" / "asset-manifest.json").read_text())
        manifest_eng = json.loads((self.eng / "assets" / "asset-manifest.json").read_text())
        self.assertEqual(manifest_main, manifest_eng)

        fp_rel = manifest_main["assets/css/base.css"]
        self.assertTrue((self.site / fp_rel).exists())
        self.assertTrue((self.eng / fp_rel).exists())
        # Content matches
        self.assertEqual((self.site / fp_rel).read_bytes(), (self.eng / fp_rel).read_bytes())

        # Engineering HTML got rewritten too
        eng_html = (self.eng / "index.html").read_text()
        self.assertIn(fp_rel, eng_html)


if __name__ == "__main__":
    unittest.main()
