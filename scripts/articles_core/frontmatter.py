"""YAML-subset frontmatter parser used by the article build pipeline.

The parser is intentionally tiny: it handles scalar keys, simple list
entries (one ``  - item`` per line), and the small set of scalar types
the platform actually uses (strings, booleans, integers, null). That
keeps the build with zero third-party dependencies while still giving
authors enough structure to describe an article.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def parse_frontmatter_value(raw: str) -> Any:
    """Coerce a frontmatter scalar ``raw`` string into its Python value.

    Supports the scalar forms the platform actually uses: strings (plain
    or quoted), integers, booleans, and ``null``/``~``. Unquoted strings
    are preserved verbatim, including content after internal spaces.
    """
    value = raw.strip()
    if value in {"", "null", "~"}:
        return None
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if re.fullmatch(r"-?\d+", value):
        try:
            return int(value)
        except ValueError:
            return value
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value


def split_frontmatter(text: str, path: Path) -> tuple[list[str], str]:
    """Return ``(header_lines, body)`` split from an article's ``text``.

    Raises ``ValueError`` when the opening or closing ``---`` marker is
    missing so authors get an actionable error keyed to the file path
    rather than a cryptic parse failure later.
    """
    if not text.startswith("---\n"):
        raise ValueError(f"{path}: missing frontmatter opening marker '---'")
    marker = "\n---\n"
    idx = text.find(marker, 4)
    if idx == -1:
        raise ValueError(f"{path}: missing frontmatter closing marker '---'")
    header = text[4:idx].splitlines()
    body = text[idx + len(marker):].lstrip("\n")
    return header, body


def parse_frontmatter(lines: list[str], path: Path) -> dict[str, Any]:
    """Return the parsed metadata dict for the frontmatter header ``lines``.

    Keys map to scalars parsed by :func:`parse_frontmatter_value`; when a
    key is followed by ``  - item`` lines the value becomes a list of
    those parsed items. A key with no value and no list items resolves
    to ``None`` -- useful for intentionally empty fields.
    """
    meta: dict[str, Any] = {}
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            i += 1
            continue
        if line.startswith("  - "):
            raise ValueError(f"{path}: list item without key on line {i + 1}")
        if ":" not in line:
            raise ValueError(f"{path}: invalid frontmatter line {i + 1}: {line}")
        key, raw_val = line.split(":", 1)
        key = key.strip()
        raw_val = raw_val.strip()

        if raw_val != "":
            meta[key] = parse_frontmatter_value(raw_val)
            i += 1
            continue

        j = i + 1
        items: list[Any] = []
        while j < len(lines):
            nxt = lines[j].rstrip()
            if not nxt.strip():
                j += 1
                continue
            if nxt.startswith("  - "):
                items.append(parse_frontmatter_value(nxt[4:]))
                j += 1
                continue
            break
        if items:
            meta[key] = items
            i = j
        else:
            meta[key] = None
            i += 1
    return meta
