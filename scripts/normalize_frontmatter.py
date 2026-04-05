#!/usr/bin/env python3
"""
One-time normalization tool:
- Adds frontmatter to legacy markdown files under content/articles/** that do not have it.
- Keeps files that already contain frontmatter unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path

from build_articles import CONTENT_DIR, infer_path_metadata, sanitize_meta


def format_scalar(value: object, *, quoted: bool = False) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    text = str(value)
    return json.dumps(text, ensure_ascii=False) if quoted else text


def build_frontmatter(meta: dict[str, object]) -> str:
    lines: list[str] = ["---"]

    lines.append(f"id: {format_scalar(meta['id'])}")
    lines.append(f"lang: {format_scalar(meta['lang'])}")
    lines.append(f"title: {format_scalar(meta['title'], quoted=True)}")
    lines.append(f"slug: {format_scalar(meta['slug'])}")
    lines.append(f"excerpt: {format_scalar(meta['excerpt'], quoted=True)}")
    lines.append(f"category: {format_scalar(meta['category'])}")

    lines.append("tags:")
    tags = meta.get("tags") or []
    for tag in tags:
        lines.append(f"  - {format_scalar(tag)}")

    lines.append(f"published_at: {format_scalar(meta['published_at'])}")
    lines.append(f"updated_at: {format_scalar(meta.get('updated_at'))}")
    lines.append(f"read_time: {format_scalar(meta['read_time'])}")
    lines.append(f"external_url: {format_scalar(meta.get('external_url'))}")
    lines.append(f"cover_image: {format_scalar(meta.get('cover_image'))}")
    lines.append(f"series_cover_image: {format_scalar(meta.get('series_cover_image'))}")
    lines.append(f"draft: {format_scalar(meta.get('draft', False))}")

    if meta.get("series_id"):
        lines.append(f"series_id: {format_scalar(meta['series_id'])}")
    if meta.get("series_title"):
        lines.append(f"series_title: {format_scalar(meta['series_title'], quoted=True)}")
    if meta.get("series_order") is not None:
        lines.append(f"series_order: {format_scalar(meta['series_order'])}")
    if meta.get("part_number") is not None:
        lines.append(f"part_number: {format_scalar(meta['part_number'])}")

    lines.append("---")
    return "\n".join(lines) + "\n\n"


def normalize() -> tuple[int, int]:
    scanned = 0
    changed = 0

    for path in sorted(CONTENT_DIR.rglob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        scanned += 1
        text = path.read_text(encoding="utf-8")
        if text.startswith("---\n"):
            continue

        inferred = infer_path_metadata(path, text)
        meta = sanitize_meta(inferred, path.relative_to(CONTENT_DIR))
        frontmatter = build_frontmatter(meta)
        new_text = frontmatter + text.lstrip("\n")
        path.write_text(new_text, encoding="utf-8")
        changed += 1

    return scanned, changed


def main() -> None:
    scanned, changed = normalize()
    print(f"Scanned {scanned} markdown files")
    print(f"Added frontmatter to {changed} files")


if __name__ == "__main__":
    main()
