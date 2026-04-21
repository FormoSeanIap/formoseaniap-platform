"""Filesystem-safe path and string utilities for the article build.

These helpers are shared across frontmatter parsing, asset copying, and
payload building. They have no project-specific dependencies beyond the
``INVALID_ARTIFACT_PATH_CHARS`` constant defined here, so they're safe
to import from any part of the pipeline without pulling the whole
build module into scope.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote


INVALID_ARTIFACT_PATH_CHARS: frozenset[str] = frozenset({'"', ":", "<", ">", "|", "*", "?"})


def humanize_token(value: str) -> str:
    """Return a human-readable version of ``value``.

    Underscores and hyphens are replaced with spaces and surrounding
    whitespace is collapsed. When ``value`` already contains any
    upper-case letter we assume it is already camel-/PascalCased and
    leave the word casing alone; otherwise we Title-Case it.
    """
    normalized = re.sub(r"\s+", " ", value.replace("_", " ").replace("-", " ")).strip() or value
    if re.search(r"[A-Z]", normalized):
        return normalized
    return normalized.title()


def validate_filesystem_safe_rel_path(rel_path: Path) -> None:
    """Raise ``ValueError`` when ``rel_path`` contains filesystem-invalid characters.

    The build pipeline ends up writing every article asset to disk, and
    filenames with characters like ``"``, ``:``, ``<``, ``>``, ``|``,
    ``*`` or ``?`` either break Windows checkouts or create undebuggable
    S3 sync failures later. This check surfaces the problem at the
    content layer, before any output is produced.
    """
    invalid_chars = sorted({char for part in rel_path.parts for char in part if char in INVALID_ARTIFACT_PATH_CHARS})
    if not invalid_chars:
        return

    invalid_display = " ".join(invalid_chars)
    raise ValueError(
        "Article asset paths must not contain filesystem-invalid characters "
        f"({invalid_display}): {rel_path.as_posix()}"
    )


def slugify(value: str) -> str:
    """Return a URL-safe lowercase slug derived from ``value``."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower())
    return slug.strip("-")


def humanize_slug(value: str) -> str:
    """Return a Title-Cased human-readable label for ``value``."""
    clean = value.replace("_", " ").replace("-", " ").strip()
    return re.sub(r"\s+", " ", clean).title() if clean else value


def quote_path(rel_path: Path) -> str:
    """Return ``rel_path`` with every segment percent-encoded for URLs."""
    return "/".join(quote(part) for part in rel_path.parts)
