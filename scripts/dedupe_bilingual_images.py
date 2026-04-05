#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
CONTENT_DIR = ROOT_DIR / "content" / "articles"
LANG_DIRS = ("English", "Mandarin")
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
MARKDOWN_IMAGE_RE = re.compile(
    r"(?P<prefix>!\[[^\]]*\]\()(?P<src>[^)\s]+)(?P<suffix>(?:\s+\"(?:[^\"\\]|\\.)*\")?\))"
)
HTML_IMG_RE = re.compile(r'(?P<prefix><img\b[^>]*\bsrc=")(?P<src>[^"]+)(?P<suffix>")')


@dataclass(frozen=True)
class SharedAssetPlan:
    target_rel: Path
    source_path: Path
    duplicate_paths: tuple[Path, ...]
    removable_bytes: int


@dataclass(frozen=True)
class WorkPlan:
    work_dir: Path
    shared_assets: tuple[SharedAssetPlan, ...]

    @property
    def removable_bytes(self) -> int:
        return sum(asset.removable_bytes for asset in self.shared_assets)

    @property
    def duplicate_count(self) -> int:
        return sum(len(asset.duplicate_paths) - 1 for asset in self.shared_assets)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_local_ref(ref: str) -> bool:
    return not ref.startswith(("http://", "https://", "mailto:", "data:", "#", "/"))


def quote_path(path: Path) -> str:
    return path.as_posix()


def find_work_dirs(roots: list[Path]) -> list[Path]:
    work_dirs: set[Path] = set()
    for root in roots:
        search_root = root if root.is_dir() else root.parent
        if (search_root / LANG_DIRS[0]).is_dir() and (search_root / LANG_DIRS[1]).is_dir():
            work_dirs.add(search_root.resolve())
        for path in search_root.rglob("*"):
            if not path.is_dir():
                continue
            if all((path / lang).is_dir() for lang in LANG_DIRS):
                work_dirs.add(path.resolve())
    return sorted(work_dirs)


def collect_image_files(lang_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in lang_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTS
    )


def relative_after_lang(path: Path, work_dir: Path) -> Path:
    rel = path.relative_to(work_dir)
    return Path(*rel.parts[1:])


def choose_shared_targets(work_dir: Path) -> WorkPlan | None:
    images_by_lang = {
        lang: collect_image_files(work_dir / lang)
        for lang in LANG_DIRS
        if (work_dir / lang).is_dir()
    }
    if not images_by_lang.get("English") or not images_by_lang.get("Mandarin"):
        return None

    by_hash: dict[str, dict[str, list[Path]]] = defaultdict(lambda: defaultdict(list))
    for lang, paths in images_by_lang.items():
        for path in paths:
            by_hash[sha256(path)][lang].append(path)

    shared_hashes = sorted(
        file_hash
        for file_hash, per_lang in by_hash.items()
        if per_lang.get("English") and per_lang.get("Mandarin")
    )
    if not shared_hashes:
        return None

    used_target_rels: set[Path] = set()
    shared_assets: list[SharedAssetPlan] = []
    shared_dir = work_dir / "Shared"

    for file_hash in shared_hashes:
        per_lang = by_hash[file_hash]
        english_paths = sorted(
            per_lang["English"],
            key=lambda path: (
                len(path.name),
                path.name,
                quote_path(relative_after_lang(path, work_dir)),
            ),
        )
        source_path = english_paths[0]
        candidate_rel = Path(source_path.name)
        if candidate_rel in used_target_rels:
            candidate_rel = relative_after_lang(source_path, work_dir)
        used_target_rels.add(candidate_rel)

        all_paths = sorted(per_lang["English"] + per_lang["Mandarin"])
        removable_bytes = all_paths[0].stat().st_size * (len(all_paths) - 1)
        shared_assets.append(
            SharedAssetPlan(
                target_rel=Path("Shared") / candidate_rel,
                source_path=source_path,
                duplicate_paths=tuple(all_paths),
                removable_bytes=removable_bytes,
            )
        )

    return WorkPlan(work_dir=work_dir, shared_assets=tuple(shared_assets))


def rewrite_text_refs(text: str, source_path: Path, old_to_new: dict[Path, Path]) -> tuple[str, bool]:
    changed = False

    def rewrite_ref(raw_ref: str) -> str | None:
        if not is_local_ref(raw_ref):
            return None
        resolved = (source_path.parent / raw_ref).resolve()
        new_target = old_to_new.get(resolved)
        if new_target is None:
            return None
        rel = os.path.relpath(new_target, source_path.parent)
        return rel.replace(os.sep, "/")

    def markdown_replacer(match: re.Match[str]) -> str:
        nonlocal changed
        new_ref = rewrite_ref(match.group("src"))
        if new_ref is None:
            return match.group(0)
        changed = True
        return f"{match.group('prefix')}{new_ref}{match.group('suffix')}"

    def html_replacer(match: re.Match[str]) -> str:
        nonlocal changed
        new_ref = rewrite_ref(match.group("src"))
        if new_ref is None:
            return match.group(0)
        changed = True
        return f"{match.group('prefix')}{new_ref}{match.group('suffix')}"

    text = MARKDOWN_IMAGE_RE.sub(markdown_replacer, text)
    text = HTML_IMG_RE.sub(html_replacer, text)
    return text, changed


def iter_markdown_files(work_dirs: list[Path]) -> list[Path]:
    files: list[Path] = []
    for work_dir in work_dirs:
        files.extend(sorted(work_dir.rglob("*.md")))
    return files


def apply_plan(plans: list[WorkPlan]) -> tuple[int, int]:
    old_to_new: dict[Path, Path] = {}
    shared_targets: dict[Path, Path] = {}
    for plan in plans:
        for asset in plan.shared_assets:
            target_path = plan.work_dir / asset.target_rel
            shared_targets[target_path] = asset.source_path
            for old_path in asset.duplicate_paths:
                old_to_new[old_path.resolve()] = target_path.resolve()

    rewritten_files = 0
    for md_path in iter_markdown_files([plan.work_dir for plan in plans]):
        original = md_path.read_text(encoding="utf-8")
        rewritten, changed = rewrite_text_refs(original, md_path, old_to_new)
        if changed:
            md_path.write_text(rewritten, encoding="utf-8")
            rewritten_files += 1

    for target_path, source_path in shared_targets.items():
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)

    removed_files = 0
    for old_path, new_path in old_to_new.items():
        old = Path(old_path)
        if old.resolve() == new_path.resolve():
            continue
        if old.exists():
            old.unlink()
            removed_files += 1

    return rewritten_files, removed_files


def verify_local_image_refs(roots: list[Path]) -> list[str]:
    missing: list[str] = []
    for root in roots:
        search_root = root if root.is_dir() else root.parent
        for md_path in sorted(search_root.rglob("*.md")):
            if md_path.name.lower() == "readme.md":
                continue
            text = md_path.read_text(encoding="utf-8")
            for pattern in (MARKDOWN_IMAGE_RE, HTML_IMG_RE):
                for match in pattern.finditer(text):
                    raw_ref = match.group("src")
                    if not is_local_ref(raw_ref):
                        continue
                    target = (md_path.parent / raw_ref).resolve()
                    if not target.exists():
                        missing.append(f"{md_path}: {raw_ref}")
    return missing


def format_size(size: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Deduplicate identical bilingual article images into Shared/ folders."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=[str(CONTENT_DIR)],
        help="Path(s) to scan. Defaults to content/articles.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Apply the deduplication instead of performing a dry run.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify that local markdown image refs resolve after the scan or write.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    roots = [Path(path).resolve() for path in args.paths]
    work_dirs = find_work_dirs(roots)
    plans = [plan for work_dir in work_dirs if (plan := choose_shared_targets(work_dir))]

    total_assets = sum(len(plan.shared_assets) for plan in plans)
    total_removed = sum(plan.duplicate_count for plan in plans)
    total_saved = sum(plan.removable_bytes for plan in plans)

    mode = "WRITE" if args.write else "DRY RUN"
    print(f"{mode}: {len(plans)} work group(s), {total_assets} shared asset(s)")
    print(f"Duplicate files removable: {total_removed}")
    print(f"Estimated space savings: {format_size(total_saved)}")

    for plan in plans:
        work_rel = plan.work_dir.relative_to(ROOT_DIR)
        print(f"\n[{work_rel}]")
        print(
            f"  shared assets: {len(plan.shared_assets)} | "
            f"duplicate files: {plan.duplicate_count} | "
            f"savings: {format_size(plan.removable_bytes)}"
        )
        for asset in plan.shared_assets:
            target_rel = (plan.work_dir / asset.target_rel).relative_to(ROOT_DIR)
            sources = ", ".join(
                quote_path(path.relative_to(plan.work_dir)) for path in asset.duplicate_paths
            )
            print(f"  - {target_rel}")
            print(f"    from: {sources}")

    if args.write and plans:
        rewritten_files, removed_files = apply_plan(plans)
        print(
            f"\nApplied changes: rewritten markdown files={rewritten_files}, "
            f"removed original image files={removed_files}"
        )

    if args.verify:
        missing = verify_local_image_refs(roots)
        if missing:
            print("\nMissing local image refs:")
            for item in missing:
                print(f"  - {item}")
            return 1
        print("\nVerification passed: all local markdown image refs resolve.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
