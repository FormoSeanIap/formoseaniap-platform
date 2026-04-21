"""Unit tests for ``scripts/sync_shared_assets.py``.

These tests exercise the sync logic in isolation from the real ``site/``
and ``site-eng/`` trees by pointing the module-level ``SOURCE_ASSETS_DIR``
and ``TARGET_ASSETS_DIR`` at temporary directories. That keeps the test
suite fast and prevents flakes from the real working tree changing state
mid-run.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock


SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import sync_shared_assets  # noqa: E402


class SyncSharedAssetsTests(unittest.TestCase):
    def _seed_source(self, source_root: Path) -> None:
        for name in sync_shared_assets.SHARED_CSS_FILES:
            path = source_root / "css" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"/* source {name} */\n", encoding="utf-8")
        for name in sync_shared_assets.SHARED_JS_FILES:
            path = source_root / "js" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"// source {name}\n", encoding="utf-8")

    def _patch_paths(self, source_root: Path, target_root: Path) -> mock._patch:
        return mock.patch.multiple(
            sync_shared_assets,
            SOURCE_ASSETS_DIR=source_root,
            TARGET_ASSETS_DIR=target_root,
        )

    def test_sync_copies_every_shared_file(self) -> None:
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "site" / "assets"
            target = Path(tmp) / "site-eng" / "assets"
            self._seed_source(source)
            with self._patch_paths(source, target):
                exit_code = sync_shared_assets.sync(check_only=False)
            self.assertEqual(exit_code, 0)
            for name in sync_shared_assets.SHARED_CSS_FILES:
                self.assertEqual(
                    (source / "css" / name).read_text(encoding="utf-8"),
                    (target / "css" / name).read_text(encoding="utf-8"),
                )
            for name in sync_shared_assets.SHARED_JS_FILES:
                self.assertEqual(
                    (source / "js" / name).read_text(encoding="utf-8"),
                    (target / "js" / name).read_text(encoding="utf-8"),
                )

    def test_sync_is_idempotent_when_targets_already_match(self) -> None:
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "site" / "assets"
            target = Path(tmp) / "site-eng" / "assets"
            self._seed_source(source)
            with self._patch_paths(source, target):
                self.assertEqual(sync_shared_assets.sync(check_only=False), 0)
                # Second run should not raise and should stay green.
                self.assertEqual(sync_shared_assets.sync(check_only=False), 0)

    def test_check_only_returns_zero_when_target_matches_source(self) -> None:
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "site" / "assets"
            target = Path(tmp) / "site-eng" / "assets"
            self._seed_source(source)
            with self._patch_paths(source, target):
                sync_shared_assets.sync(check_only=False)
                self.assertEqual(sync_shared_assets.sync(check_only=True), 0)

    def test_check_only_returns_one_when_target_drifts(self) -> None:
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "site" / "assets"
            target = Path(tmp) / "site-eng" / "assets"
            self._seed_source(source)
            with self._patch_paths(source, target):
                sync_shared_assets.sync(check_only=False)
                drifted = target / "css" / "base.css"
                drifted.write_text("/* drifted */\n", encoding="utf-8")
                self.assertEqual(sync_shared_assets.sync(check_only=True), 1)

    def test_check_only_returns_one_when_target_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "site" / "assets"
            target = Path(tmp) / "site-eng" / "assets"
            self._seed_source(source)
            with self._patch_paths(source, target):
                self.assertEqual(sync_shared_assets.sync(check_only=True), 1)

    def test_sync_returns_two_when_source_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "site" / "assets"
            target = Path(tmp) / "site-eng" / "assets"
            # Intentionally do not seed source.
            with self._patch_paths(source, target):
                self.assertEqual(sync_shared_assets.sync(check_only=False), 2)
                self.assertEqual(sync_shared_assets.sync(check_only=True), 2)


if __name__ == "__main__":
    unittest.main()
