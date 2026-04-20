#!/usr/bin/env python3
"""
Build article JSON and RSS outputs for the static site.

Supports two content styles:
1) Frontmatter-driven files (new schema)
2) Legacy nested files without frontmatter (metadata inferred from path + content)

Outputs (main site — all articles):
- site/data/articles.index.json
- site/data/articles.search.json
- site/data/articles/<lang>/<id>.json
- site/rss.xml
- site/zh/rss.xml
- copied article assets under site/assets/articles/

Outputs (engineering site — technical articles only):
- site-eng/data/articles.index.json
- site-eng/data/articles.search.json
- site-eng/data/articles/<lang>/<id>.json
- site-eng/rss.xml
- copied technical article assets under site-eng/assets/articles/
"""

from __future__ import annotations

import json
import re
import shutil
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timezone
from html import escape, unescape
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlencode, urlparse


ROOT = Path(__file__).resolve().parents[1]
CONTENT_DIR = ROOT / "content" / "articles"
TAGS_PATH = ROOT / "content" / "tags.json"
SITE_CONFIG_PATH = ROOT / "content" / "site.json"

SITE_DIR = ROOT / "site"
DATA_DIR = SITE_DIR / "data"
ARTICLES_DATA_DIR = DATA_DIR / "articles"
ASSETS_ARTICLES_DIR = SITE_DIR / "assets" / "articles"
INDEX_PATH = DATA_DIR / "articles.index.json"
SEARCH_INDEX_PATH = DATA_DIR / "articles.search.json"
RSS_EN_PATH = SITE_DIR / "rss.xml"
RSS_ZH_PATH = SITE_DIR / "zh" / "rss.xml"

# Engineering site output paths (technical articles only)
ENG_SITE_DIR = ROOT / "site-eng"
ENG_DATA_DIR = ENG_SITE_DIR / "data"
ENG_ARTICLES_DATA_DIR = ENG_DATA_DIR / "articles"
ENG_ASSETS_ARTICLES_DIR = ENG_SITE_DIR / "assets" / "articles"
ENG_INDEX_PATH = ENG_DATA_DIR / "articles.index.json"
ENG_SEARCH_INDEX_PATH = ENG_DATA_DIR / "articles.search.json"
ENG_RSS_PATH = ENG_SITE_DIR / "rss.xml"

SUPPORTED_LANGS = {"en", "zh"}
SUPPORTED_CATEGORIES = {"technical", "review", "other"}
LANG_DIR_MAP = {
    "english": "en",
    "mandarin": "zh",
    "chinese": "zh",
    "zh": "zh",
    "en": "en",
}
GENERIC_SERIES_NAMES = {
    "reviews",
    "review",
    "technical",
    "english",
    "mandarin",
    "part1",
    "part2",
    "part3",
    "part4",
    "part5",
}
INVALID_ARTIFACT_PATH_CHARS = {'"', ":", "<", ">", "|", "*", "?"}


def humanize_token(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value.replace("_", " ").replace("-", " ")).strip() or value
    if re.search(r"[A-Z]", normalized):
        return normalized
    return normalized.title()


def validate_filesystem_safe_rel_path(rel_path: Path) -> None:
    invalid_chars = sorted({char for part in rel_path.parts for char in part if char in INVALID_ARTIFACT_PATH_CHARS})
    if not invalid_chars:
        return

    invalid_display = " ".join(invalid_chars)
    raise ValueError(
        "Article asset paths must not contain filesystem-invalid characters "
        f"({invalid_display}): {rel_path.as_posix()}"
    )


def derive_subcategory_metadata(parts: list[str]) -> tuple[str, str]:
    if not parts:
        return ("others", "Others")

    root = parts[0].lower()
    raw = "others"
    if root == "reviews" and len(parts) > 1:
        raw = parts[1]
    elif root == "technical" and len(parts) > 1:
        raw = parts[1]
    elif root == "others":
        raw = "others"

    return (raw, humanize_token(raw))


@dataclass
class ArticleRecord:
    meta: dict[str, Any]
    body_markdown: str
    body_html: str
    source_rel: Path

    @property
    def source_path(self) -> str:
        return f"content/articles/{self.source_rel.as_posix()}"

    @property
    def id(self) -> str:
        return str(self.meta["id"])

    @property
    def lang(self) -> str:
        return str(self.meta["lang"])

    @property
    def published_at(self) -> str:
        return str(self.meta["published_at"])


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower())
    return slug.strip("-")


def humanize_slug(value: str) -> str:
    clean = value.replace("_", " ").replace("-", " ").strip()
    return re.sub(r"\s+", " ", clean).title() if clean else value


def quote_path(rel_path: Path) -> str:
    return "/".join(quote(part) for part in rel_path.parts)


def parse_frontmatter_value(raw: str) -> Any:
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
    if not text.startswith("---\n"):
        raise ValueError(f"{path}: missing frontmatter opening marker '---'")
    marker = "\n---\n"
    idx = text.find(marker, 4)
    if idx == -1:
        raise ValueError(f"{path}: missing frontmatter closing marker '---'")
    header = text[4:idx].splitlines()
    body = text[idx + len(marker) :].lstrip("\n")
    return header, body


def parse_frontmatter(lines: list[str], path: Path) -> dict[str, Any]:
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


def extract_first_heading(markdown: str) -> str | None:
    for line in markdown.splitlines():
        if line.startswith("# "):
            heading = line[2:].strip()
            heading = re.sub(r"[*_`]+", "", heading).strip()
            return heading
    return None


def extract_medium_link(markdown: str) -> str | None:
    match = re.search(r"\(\[Medium Article\]\((https?://[^)]+)\)\)", markdown)
    if match:
        return match.group(1).strip()
    return None


def strip_markdown_for_excerpt(line: str) -> str:
    text = line.strip()
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[`*_>#]", "", text)
    return text.strip()


def extract_excerpt(markdown: str, limit: int = 180) -> str:
    for raw in markdown.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        if line.startswith("!"):
            continue
        if line in {"\\", "---"}:
            continue
        cleaned = strip_markdown_for_excerpt(line)
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered.startswith("source:"):
            continue
        if lowered.startswith("(medium article)"):
            continue
        if lowered.startswith("home"):
            continue
        if lowered.startswith("previous"):
            continue
        if lowered.startswith("next"):
            continue
        if cleaned.startswith("主頁") or cleaned.startswith("上一章"):
            continue
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[: limit - 1].rstrip() + "…"
    return ""


def estimate_read_time(markdown: str) -> int:
    plain = re.sub(r"\s+", " ", strip_markdown_for_excerpt(markdown))
    words = len(re.findall(r"[A-Za-z0-9_]+", plain))
    cjk_chars = len(re.findall(r"[\u4e00-\u9fff]", plain))
    if cjk_chars > words:
        minutes = round(cjk_chars / 280)
    else:
        minutes = round(words / 220)
    return max(1, minutes)


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def to_rfc822(value: str) -> str:
    dt = datetime.combine(parse_date(value), datetime.min.time(), tzinfo=timezone.utc)
    return dt.strftime("%a, %d %b %Y %H:%M:%S GMT")


def article_page_url(article_id: str, lang: str) -> str:
    return f"article.html?id={article_id}&lang={lang}"


def language_sort_rank(lang: str) -> int:
    if lang == "en":
        return 0
    if lang == "zh":
        return 1
    return 9


def normalize_search_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = normalized.lower()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def markdown_to_plain_text(markdown: str) -> str:
    text = markdown
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`[^`]*`", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^\s*\\\s*$", " ", text, flags=re.MULTILINE)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s{0,3}>\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*_>#~-]", " ", text)
    return normalize_search_text(text)


def resolve_frontmatter_asset_ref(source_rel: Path, ref_url: str | None, field_name: str) -> str | None:
    if ref_url is None:
        return None

    value = str(ref_url).strip()
    if not value:
        return None

    if value.startswith(("http://", "https://", "data:", "/")):
        return value

    source_abs = CONTENT_DIR / source_rel
    target_abs = (source_abs.parent / value).resolve()
    try:
        target_rel = target_abs.relative_to(CONTENT_DIR)
    except ValueError as exc:
        raise ValueError(f"{source_rel}: {field_name} must stay within content/articles: {value}") from exc

    if target_abs.suffix.lower() == ".md":
        raise ValueError(f"{source_rel}: {field_name} must reference an asset, not markdown: {value}")
    if not target_abs.exists():
        raise ValueError(f"{source_rel}: {field_name} asset not found: {value}")

    return f"assets/articles/{quote_path(target_rel)}"


def infer_path_metadata(path: Path, body_md: str) -> dict[str, Any]:
    rel = path.relative_to(CONTENT_DIR)
    parts = list(rel.parts)
    stem = path.stem
    stem_slug = slugify(stem.replace("_", "-"))

    lang = "en"
    lang_idx: int | None = None
    for idx, part in enumerate(parts):
        mapped = LANG_DIR_MAP.get(part.lower())
        if mapped:
            lang = mapped
            lang_idx = idx
            break

    part_number: int | None = None
    part_idx: int | None = None
    for idx, part in enumerate(parts):
        match = re.fullmatch(r"part\s*([0-9]+)", part, flags=re.IGNORECASE)
        if match:
            part_number = int(match.group(1))
            part_idx = idx
            break
        match = re.fullmatch(r"part([0-9]+)", part, flags=re.IGNORECASE)
        if match:
            part_number = int(match.group(1))
            part_idx = idx
            break

    title = extract_first_heading(body_md) or humanize_slug(stem)
    if part_number is None:
        match = re.search(r"\(part\s*([0-9]+)\)", title, flags=re.IGNORECASE)
        if match:
            part_number = int(match.group(1))

    category_raw = parts[0].lower() if parts else "other"
    if category_raw == "technical":
        category = "technical"
    elif category_raw in {"reviews", "review"}:
        category = "review"
    else:
        category = "other"
    subcategory_id, subcategory_label = derive_subcategory_metadata(parts)

    folder_parts = parts[:-1]
    series_parts: list[str] = []
    for idx, part in enumerate(folder_parts):
        if idx == lang_idx or idx == part_idx:
            continue
        series_parts.append(part)

    series_id = slugify("/".join(series_parts)) if series_parts else stem_slug
    series_title = None
    for candidate in reversed(series_parts):
        token = slugify(candidate)
        if token and token not in GENERIC_SERIES_NAMES:
            series_title = candidate.replace("_", " ").strip()
            break
    if not series_title:
        series_title = humanize_slug(series_parts[-1]) if series_parts else humanize_slug(stem)

    medium_link = extract_medium_link(body_md)
    excerpt = extract_excerpt(body_md)
    published_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).date().isoformat()

    tags = [category]
    if category == "review":
        tags.append("review")
    lower_parts = [p.lower() for p in parts]
    if any("anime" in p for p in lower_parts):
        tags.append("anime")
    if any("manga" in p for p in lower_parts):
        tags.append("manga")
    if any("movie" in p for p in lower_parts):
        tags.append("movie")
    if any("drama" in p for p in lower_parts):
        tags.append("tv-drama")
    tags = list(dict.fromkeys(tags))

    base_id_parts = [series_id, stem_slug]
    if part_number is not None:
        base_id_parts.insert(1, f"part-{part_number}")
    article_id = slugify("-".join(part for part in base_id_parts if part))

    return {
        "id": article_id,
        "lang": lang,
        "title": title,
        "slug": stem_slug,
        "excerpt": excerpt,
        "category": category,
        "subcategory_id": subcategory_id,
        "subcategory_label": subcategory_label,
        "tags": tags,
        "published_at": published_at,
        "updated_at": None,
        "read_time": estimate_read_time(body_md),
        "external_url": medium_link,
        "cover_image": None,
        "series_cover_image": None,
        "draft": False,
        "series_id": series_id,
        "series_title": series_title,
        "part_number": part_number,
    }


def merge_metadata(inferred: dict[str, Any], parsed: dict[str, Any]) -> dict[str, Any]:
    merged = dict(inferred)
    for key, value in parsed.items():
        if key == "tags" and isinstance(value, list) and value:
            merged[key] = value
            continue
        if key in {"external_url", "cover_image", "series_cover_image", "updated_at"} and (
            value is None or value == "" or value == []
        ):
            merged[key] = None
            continue
        if value is not None and value != "":
            merged[key] = value
    return merged


def sanitize_meta(meta: dict[str, Any], source_rel: Path) -> dict[str, Any]:
    clean = dict(meta)
    inferred_subcategory_id, inferred_subcategory_label = derive_subcategory_metadata(list(source_rel.parts))
    clean["id"] = slugify(str(clean.get("id") or source_rel.stem))
    clean["lang"] = str(clean.get("lang") or "en").lower()
    if clean["lang"] not in SUPPORTED_LANGS:
        raise ValueError(f"{source_rel}: unsupported lang '{clean['lang']}'")

    clean["title"] = str(clean.get("title") or humanize_slug(source_rel.stem))
    clean["slug"] = slugify(str(clean.get("slug") or source_rel.stem))
    clean["excerpt"] = str(clean.get("excerpt") or "")
    category = str(clean.get("category") or "other").lower()
    if category == "others":
        category = "other"
    if category not in SUPPORTED_CATEGORIES:
        category = "other"
    clean["category"] = category
    subcategory_id = clean.get("subcategory_id")
    clean["subcategory_id"] = (
        str(subcategory_id).strip()
        if subcategory_id is not None and str(subcategory_id).strip()
        else inferred_subcategory_id
    )
    subcategory_label = clean.get("subcategory_label")
    clean["subcategory_label"] = (
        str(subcategory_label).strip()
        if subcategory_label is not None and str(subcategory_label).strip()
        else inferred_subcategory_label
    )

    tags = clean.get("tags") or []
    if not isinstance(tags, list):
        tags = [str(tags)]
    clean["tags"] = [slugify(str(tag)) for tag in tags if str(tag).strip()]
    clean["tags"] = [tag for tag in clean["tags"] if tag]
    clean["tags"] = list(dict.fromkeys(clean["tags"]))
    if not clean["tags"]:
        clean["tags"] = [category]

    published = clean.get("published_at")
    if not published:
        published = datetime.now(timezone.utc).date().isoformat()
    clean["published_at"] = str(published)
    parse_date(clean["published_at"])

    updated = clean.get("updated_at")
    if updated:
        parse_date(str(updated))
        clean["updated_at"] = str(updated)
    else:
        clean["updated_at"] = None

    read_time = clean.get("read_time")
    try:
        clean["read_time"] = max(1, int(read_time))
    except (TypeError, ValueError):
        clean["read_time"] = 1

    clean["external_url"] = str(clean["external_url"]).strip() if clean.get("external_url") else None
    clean["cover_image"] = resolve_frontmatter_asset_ref(source_rel, clean.get("cover_image"), "cover_image")
    clean["series_cover_image"] = resolve_frontmatter_asset_ref(
        source_rel,
        clean.get("series_cover_image"),
        "series_cover_image",
    )
    clean["draft"] = bool(clean.get("draft", False))

    series_id = clean.get("series_id")
    clean["series_id"] = slugify(str(series_id)) if series_id else None
    series_title = clean.get("series_title")
    clean["series_title"] = str(series_title).strip() if series_title else None

    part_number = clean.get("part_number")
    try:
        clean["part_number"] = int(part_number) if part_number is not None else None
    except (TypeError, ValueError):
        clean["part_number"] = None

    series_order = clean.get("series_order")
    try:
        clean["series_order"] = int(series_order) if series_order is not None else None
    except (TypeError, ValueError):
        clean["series_order"] = None

    return clean


def propagate_series_cover_images(records: list[ArticleRecord]) -> None:
    grouped: dict[str, list[ArticleRecord]] = {}
    for record in records:
        series_id = str(record.meta.get("series_id") or record.id)
        grouped.setdefault(series_id, []).append(record)

    for series_id, items in grouped.items():
        cover_values = {
            str(record.meta["series_cover_image"])
            for record in items
            if record.meta.get("series_cover_image")
        }
        if len(cover_values) > 1:
            raise ValueError(
                f"Conflicting series_cover_image values for series '{series_id}': {sorted(cover_values)}"
            )
        resolved = next(iter(cover_values), None)
        for record in items:
            record.meta["series_cover_image"] = resolved


def apply_emphasis_markup(text: str) -> str:
    # Bold first so paired markers are consumed before italic.
    text = re.sub(r"(?<!\\)\*\*([^\n*]+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\\)__([^\n_]+?)__", r"<strong>\1</strong>", text)
    # Keep italic conservative to avoid converting snake_case identifiers.
    text = re.sub(r"(?<!\\)(?<!\w)\*([^\n*]+?)\*(?!\w)", r"<em>\1</em>", text)
    text = re.sub(r"(?<!\\)(?<!\w)_([^\n_]+?)_(?!\w)", r"<em>\1</em>", text)
    return text


IMAGE_INLINE_RE = re.compile(
    r'!\[(?P<alt>[^\]]*)\]\((?P<src>[^)\s]+?)(?:\s+"(?P<title>(?:[^"\\]|\\.)*)")?\)'
)
IMAGE_ONLY_LINE_RE = re.compile(
    r'^\s*!\[(?P<alt>[^\]]*)\]\((?P<src>[^)\s]+?)(?:\s+"(?P<title>(?:[^"\\]|\\.)*)")?\)\s*$'
)
EMBED_LINK_ONLY_RE = re.compile(
    r'^\s*\[(?P<label>[^\]]+)\]\((?P<href>[^)]+)\)\s*$'
)


def unescape_image_title(value: str | None) -> str | None:
    if value is None:
        return None
    return re.sub(r'\\(["\\])', r"\1", value)


def is_embedded_media_label(label: str) -> bool:
    return label.strip().lower() == "embedded media"


def normalize_video_embed_url(raw_href: str) -> str | None:
    parsed = urlparse(raw_href.strip())
    host = parsed.netloc.lower()
    path = parsed.path.strip("/")
    query = parse_qs(parsed.query)

    def build_youtube_url(video_id: str | None) -> str | None:
        if not video_id:
            return None
        params: dict[str, str] = {}
        for key in ("start", "end", "list"):
            values = query.get(key)
            if values and values[-1]:
                params[key] = values[-1]
        if "start" not in params:
            values = query.get("t")
            if values and values[-1]:
                params["start"] = values[-1].rstrip("s")
        qs = f"?{urlencode(params)}" if params else ""
        return f"https://www.youtube.com/embed/{quote(video_id, safe='')}{qs}"

    if host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        if path.startswith("embed/"):
            return build_youtube_url(path.split("/", 1)[1].split("/", 1)[0])
        if path == "watch":
            values = query.get("v")
            return build_youtube_url(values[-1] if values else None)
        if path.startswith("shorts/"):
            return build_youtube_url(path.split("/", 1)[1].split("/", 1)[0])

    if host == "youtu.be":
        return build_youtube_url(path.split("/", 1)[0] if path else None)

    def build_vimeo_url(video_id: str | None) -> str | None:
        if not video_id or not re.fullmatch(r"\d+", video_id):
            return None
        return f"https://player.vimeo.com/video/{video_id}"

    if host in {"vimeo.com", "www.vimeo.com"}:
        return build_vimeo_url(path.split("/", 1)[0] if path else None)

    if host == "player.vimeo.com" and path.startswith("video/"):
        return build_vimeo_url(path.split("/", 1)[1].split("/", 1)[0])

    return None


def build_embedded_media_html(raw_href: str, label: str) -> str | None:
    embed_url = normalize_video_embed_url(raw_href)
    if embed_url is None:
        return None

    title = label.strip() if label.strip() and not is_embedded_media_label(label) else "Embedded video"
    return (
        '<div class="embedded-media">'
        f'<iframe src="{escape(embed_url, quote=True)}" title="{escape(title, quote=True)}" '
        'loading="lazy" referrerpolicy="strict-origin-when-cross-origin" '
        'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" '
        "allowfullscreen></iframe>"
        "</div>"
    )


def render_inline(text: str) -> str:
    tokens: dict[str, str] = {}
    token_idx = 0

    def stash(html: str) -> str:
        nonlocal token_idx
        key = f"@@INLINE{token_idx}@@"
        token_idx += 1
        tokens[key] = html
        return key

    def code_repl(match: re.Match[str]) -> str:
        return stash(f"<code>{escape(match.group(1))}</code>")

    def image_repl(match: re.Match[str]) -> str:
        alt = escape(match.group("alt"))
        src = escape(match.group("src"), quote=True)
        title = unescape_image_title(match.group("title"))
        title_attr = f' title="{escape(title, quote=True)}"' if title else ""
        return stash(f'<img src="{src}" alt="{alt}" loading="lazy"{title_attr} />')

    def link_repl(match: re.Match[str]) -> str:
        label_html = render_inline(match.group(1))
        raw_href = match.group(2).strip()
        href = escape(raw_href, quote=True)
        if raw_href.startswith(("http://", "https://")):
            html = f'<a href="{href}" target="_blank" rel="noopener noreferrer">{label_html}</a>'
        else:
            html = f'<a href="{href}">{label_html}</a>'
        return stash(html)

    text = re.sub(r"`([^`]+)`", code_repl, text)
    text = IMAGE_INLINE_RE.sub(image_repl, text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link_repl, text)

    escaped = escape(text)
    escaped = apply_emphasis_markup(escaped)

    for token, html in tokens.items():
        escaped = escaped.replace(token, html)
    return escaped


def is_thematic_break(line: str) -> bool:
    stripped = line.strip()
    return bool(
        re.fullmatch(r"(?:(?:-\s*){3,}|(?:\*\s*){3,}|(?:_\s*){3,})", stripped)
    )


def markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    out: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    ordered_items: list[str] = []
    quote_lines: list[str] = []
    pending_blank_lines = 0
    in_code = False
    code_lang = ""
    code_lines: list[str] = []

    def append_block(html: str) -> None:
        out.append(html)

    def flush_pending_blank_lines() -> None:
        nonlocal pending_blank_lines
        if pending_blank_lines >= 2 and out:
            append_block('<div class="article-break article-break--large" aria-hidden="true"></div>')
        pending_blank_lines = 0

    def append_small_break() -> None:
        append_block('<div class="article-break article-break--small" aria-hidden="true"></div>')

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            joined = " ".join(part.strip() for part in paragraph if part.strip())
            rendered = render_inline(joined)
            append_block(f"<p>{rendered}</p>")
            paragraph = []

    def flush_list() -> None:
        nonlocal list_items
        if list_items:
            items = "".join(f"<li>{render_inline(item)}</li>" for item in list_items)
            append_block(f"<ul>{items}</ul>")
            list_items = []

    def flush_ordered_list() -> None:
        nonlocal ordered_items
        if ordered_items:
            items = "".join(f"<li>{render_inline(item)}</li>" for item in ordered_items)
            append_block(f"<ol>{items}</ol>")
            ordered_items = []

    def flush_quote() -> None:
        nonlocal quote_lines
        if quote_lines:
            quote_body = " ".join(part.strip() for part in quote_lines if part.strip())
            append_block(f"<blockquote><p>{render_inline(quote_body)}</p></blockquote>")
            quote_lines = []

    for raw in lines:
        line = raw.rstrip("\n")

        if in_code:
            if line.startswith("```"):
                class_attr = f' class="language-{escape(code_lang)}"' if code_lang else ""
                code_text = escape("\n".join(code_lines))
                append_block(f"<pre><code{class_attr}>{code_text}</code></pre>")
                in_code = False
                code_lang = ""
                code_lines = []
            else:
                code_lines.append(line)
            continue

        if line.startswith("```"):
            flush_pending_blank_lines()
            flush_paragraph()
            flush_list()
            flush_ordered_list()
            flush_quote()
            in_code = True
            code_lang = line[3:].strip()
            code_lines = []
            continue

        if not line.strip():
            flush_paragraph()
            flush_list()
            flush_ordered_list()
            flush_quote()
            pending_blank_lines += 1
            continue

        if line.strip() == "\\":
            flush_paragraph()
            flush_list()
            flush_ordered_list()
            flush_quote()
            pending_blank_lines = 0
            if out:
                append_small_break()
            continue

        if is_thematic_break(line):
            flush_pending_blank_lines()
            flush_paragraph()
            flush_list()
            flush_ordered_list()
            flush_quote()
            if out:
                append_block("<hr />")
            continue

        if line.startswith("#"):
            flush_pending_blank_lines()
            flush_paragraph()
            flush_list()
            flush_ordered_list()
            flush_quote()
            level = len(line) - len(line.lstrip("#"))
            level = max(1, min(level, 6))
            title = line[level:].strip()
            append_block(f"<h{level}>{render_inline(title)}</h{level}>")
            continue

        ul_match = re.match(r"^\s*[-*]\s+(.+)$", line)
        if ul_match:
            flush_pending_blank_lines()
            flush_paragraph()
            flush_ordered_list()
            flush_quote()
            list_items.append(ul_match.group(1))
            continue

        ol_match = re.match(r"^\s*\d+\.\s+(.+)$", line)
        if ol_match:
            flush_pending_blank_lines()
            flush_paragraph()
            flush_list()
            flush_quote()
            ordered_items.append(ol_match.group(1))
            continue

        quote_match = re.match(r"^\s*>\s?(.+)$", line)
        if quote_match:
            flush_pending_blank_lines()
            flush_paragraph()
            flush_list()
            flush_ordered_list()
            quote_lines.append(quote_match.group(1))
            continue

        image_only_match = IMAGE_ONLY_LINE_RE.match(line)
        if image_only_match:
            flush_pending_blank_lines()
            flush_paragraph()
            flush_list()
            flush_ordered_list()
            flush_quote()
            append_block(f'<p class="image-block">{render_inline(line.strip())}</p>')
            title = unescape_image_title(image_only_match.group("title"))
            if title:
                append_block(f'<p class="image-caption">{render_inline(title)}</p>')
            continue

        embed_only_match = EMBED_LINK_ONLY_RE.match(line)
        if embed_only_match and is_embedded_media_label(embed_only_match.group("label")):
            embedded_html = build_embedded_media_html(
                embed_only_match.group("href"),
                embed_only_match.group("label"),
            )
            if embedded_html:
                flush_pending_blank_lines()
                flush_paragraph()
                flush_list()
                flush_ordered_list()
                flush_quote()
                append_block(embedded_html)
                continue

        flush_pending_blank_lines()
        paragraph.append(line)

    flush_paragraph()
    flush_list()
    flush_ordered_list()
    flush_quote()

    if in_code:
        code_text = escape("\n".join(code_lines))
        class_attr = f' class="language-{escape(code_lang)}"' if code_lang else ""
        out.append(f"<pre><code{class_attr}>{code_text}</code></pre>")

    return "\n".join(out)


def copy_assets() -> None:
    if ASSETS_ARTICLES_DIR.exists():
        shutil.rmtree(ASSETS_ARTICLES_DIR)
    ASSETS_ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    for path in CONTENT_DIR.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() == ".md":
            continue
        rel = path.relative_to(CONTENT_DIR)
        dst = ASSETS_ARTICLES_DIR / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dst)


def copy_engineering_assets(records: list[ArticleRecord]) -> None:
    """Copy assets only for technical articles to the engineering site."""
    if ENG_ASSETS_ARTICLES_DIR.exists():
        shutil.rmtree(ENG_ASSETS_ARTICLES_DIR)
    ENG_ASSETS_ARTICLES_DIR.mkdir(parents=True, exist_ok=True)

    technical_dirs: set[Path] = set()
    for record in records:
        if record.meta.get("category") != "technical":
            continue
        source_abs = CONTENT_DIR / record.source_rel
        technical_dirs.add(source_abs.parent)

    for path in CONTENT_DIR.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() == ".md":
            continue
        if not any(path.parent == d or d in path.parents for d in technical_dirs):
            continue
        rel = path.relative_to(CONTENT_DIR)
        dst = ENG_ASSETS_ARTICLES_DIR / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dst)


def ensure_engineering_output_dirs() -> None:
    """Create engineering site output directories."""
    ENG_DATA_DIR.mkdir(parents=True, exist_ok=True)
    if ENG_ARTICLES_DATA_DIR.exists():
        shutil.rmtree(ENG_ARTICLES_DATA_DIR)
    ENG_ARTICLES_DATA_DIR.mkdir(parents=True, exist_ok=True)


def validate_content_asset_paths() -> None:
    for path in CONTENT_DIR.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() == ".md":
            continue
        validate_filesystem_safe_rel_path(path.relative_to(CONTENT_DIR))


def resolve_local_ref(source_rel: Path, ref_url: str, source_to_page: dict[str, str]) -> str:
    if not ref_url:
        return ref_url
    if ref_url.startswith(("http://", "https://", "mailto:", "data:", "#")):
        return ref_url
    if ref_url.startswith("/"):
        return ref_url

    if "#" in ref_url:
        base, fragment = ref_url.split("#", 1)
        frag = f"#{fragment}"
    else:
        base, frag = ref_url, ""

    if not base:
        return ref_url

    if base.lower().endswith("readme.md"):
        return f"articles.html{frag}"

    source_abs = CONTENT_DIR / source_rel
    target_abs = (source_abs.parent / base).resolve()
    try:
        target_rel = target_abs.relative_to(CONTENT_DIR)
    except ValueError:
        return ref_url

    target_rel_posix = target_rel.as_posix()
    if target_abs.suffix.lower() == ".md":
        mapped = source_to_page.get(target_rel_posix)
        return (mapped + frag) if mapped else ref_url

    if target_abs.exists():
        return f"assets/articles/{quote_path(target_rel)}{frag}"

    return ref_url


def rewrite_html_links(html_text: str, source_rel: Path, source_to_page: dict[str, str]) -> str:
    pattern = re.compile(r'(href|src)="([^"]+)"')

    def replacer(match: re.Match[str]) -> str:
        attr = match.group(1)
        original = unescape(match.group(2))
        rewritten = resolve_local_ref(source_rel, original, source_to_page)
        return f'{attr}="{escape(rewritten, quote=True)}"'

    return pattern.sub(replacer, html_text)


def extract_first_local_image_src(html_text: str) -> str | None:
    for match in re.finditer(r'<img[^>]+src="([^"]+)"', html_text):
        src = unescape(match.group(1))
        if src.startswith("assets/articles/"):
            return src
    return None


def ensure_output_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if ARTICLES_DATA_DIR.exists():
        shutil.rmtree(ARTICLES_DATA_DIR)
    ARTICLES_DATA_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "zh").mkdir(parents=True, exist_ok=True)


def load_site_config() -> dict[str, str]:
    default = {
        "site_name": "Seng-Gan Iap Portfolio",
        "site_url": "https://example.com",
        "author": "Seng-Gan Iap",
    }
    if not SITE_CONFIG_PATH.exists():
        return default
    user = load_json(SITE_CONFIG_PATH)
    if not isinstance(user, dict):
        return default
    return {
        "site_name": str(user.get("site_name", default["site_name"])),
        "site_url": str(user.get("site_url", default["site_url"])).rstrip("/"),
        "author": str(user.get("author", default["author"])),
    }


def load_articles() -> list[ArticleRecord]:
    records: list[ArticleRecord] = []
    seen_ids: set[tuple[str, str]] = set()

    for path in sorted(CONTENT_DIR.rglob("*.md")):
        if path.name.lower() == "readme.md":
            continue

        text = path.read_text(encoding="utf-8")
        inferred = infer_path_metadata(path, text)

        if text.startswith("---\n"):
            header_lines, body_md = split_frontmatter(text, path)
            parsed = parse_frontmatter(header_lines, path)
            merged_meta = merge_metadata(inferred, parsed)
        else:
            body_md = text
            merged_meta = inferred

        meta = sanitize_meta(merged_meta, path.relative_to(CONTENT_DIR))
        if meta.get("draft"):
            continue

        key = (meta["id"], meta["lang"])
        if key in seen_ids:
            raise ValueError(f"Duplicate article id/lang detected: {key} at {path}")
        seen_ids.add(key)

        records.append(
            ArticleRecord(
                meta=meta,
                body_markdown=body_md,
                body_html=markdown_to_html(body_md),
                source_rel=path.relative_to(CONTENT_DIR),
            )
        )
    propagate_series_cover_images(records)
    return records


def series_sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
    series_order = item.get("series_order")
    part_number = item.get("part_number")
    return (
        series_order is None,
        series_order if series_order is not None else 99999,
        part_number is None,
        part_number if part_number is not None else 99999,
        item["published_at"],
        item["title"].lower(),
    )


def collection_preview_sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
    return (*series_sort_key(item), language_sort_rank(str(item.get("lang") or "")))


def build_series_links(index_items: list[dict[str, Any]]) -> None:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in index_items:
        series_id = item.get("series_id")
        if not series_id:
            continue
        groups.setdefault((str(series_id), str(item["lang"])), []).append(item)

    for group_items in groups.values():
        group_items.sort(key=series_sort_key)
        total = len(group_items)
        for idx, item in enumerate(group_items):
            item["part_total"] = total
            prev_item = group_items[idx - 1] if idx > 0 else None
            next_item = group_items[idx + 1] if idx < total - 1 else None
            item["series_previous"] = (
                {
                    "id": prev_item["id"],
                    "title": prev_item["title"],
                    "part_number": prev_item.get("part_number"),
                    "page_url": prev_item["page_url"],
                }
                if prev_item
                else None
            )
            item["series_next"] = (
                {
                    "id": next_item["id"],
                    "title": next_item["title"],
                    "part_number": next_item.get("part_number"),
                    "page_url": next_item["page_url"],
                }
                if next_item
                else None
            )


def build_series_preview_images(index_items: list[dict[str, Any]]) -> None:
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in index_items:
        key = str(item.get("series_id") or item["id"])
        groups.setdefault(key, []).append(item)

    for group_items in groups.values():
        group_items.sort(key=collection_preview_sort_key)
        explicit = next((item.get("series_cover_image") for item in group_items if item.get("series_cover_image")), None)
        inferred = next((item.get("preview_image") for item in group_items if item.get("preview_image")), None)
        resolved = explicit or inferred
        for item in group_items:
            item["series_preview_image"] = resolved


def merge_tag_labels(base_labels: dict[str, Any], articles: list[dict[str, Any]]) -> dict[str, Any]:
    labels = dict(base_labels)
    missing: list[str] = []
    for article in articles:
        for tag in article.get("tags") or []:
            if tag not in labels:
                missing.append(tag)
    for tag in sorted(set(missing)):
        pretty = humanize_slug(tag)
        labels[tag] = {"en": pretty, "zh": pretty}
    if missing:
        print(f"Warning: auto-generated labels for missing tags: {sorted(set(missing))}")
    return labels


def build_payloads(records: list[ArticleRecord], tag_labels: dict[str, Any]) -> dict[str, Any]:
    by_id: dict[str, dict[str, ArticleRecord]] = {}
    source_to_page: dict[str, str] = {}
    generated_at = datetime.now(timezone.utc).isoformat()
    index_lookup: dict[tuple[str, str], dict[str, Any]] = {}
    rewritten_html_by_key: dict[tuple[str, str], str] = {}

    index_items: list[dict[str, Any]] = []
    for record in records:
        by_id.setdefault(record.id, {})[record.lang] = record

    for record in records:
        translations = {
            lang: article_page_url(record.id, lang)
            for lang in sorted(by_id.get(record.id, {}).keys())
            if lang != record.lang
        }
        item = {
            **record.meta,
            "source_path": record.source_path,
            "article_path": f"data/articles/{record.lang}/{record.id}.json",
            "page_url": article_page_url(record.id, record.lang),
            "translations": translations,
            "series_order": record.meta.get("series_order"),
            "preview_image": None,
            "series_preview_image": None,
            "part_total": None,
            "series_previous": None,
            "series_next": None,
        }
        index_items.append(item)
        index_lookup[(record.lang, record.id)] = item
        source_to_page[record.source_rel.as_posix()] = item["page_url"]

    index_items.sort(
        key=lambda item: (
            parse_date(str(item["published_at"])),
            item["part_number"] if item["part_number"] is not None else -1,
            str(item["title"]).lower(),
        ),
        reverse=True,
    )

    build_series_links(index_items)
    merged_tags = merge_tag_labels(tag_labels, index_items)

    for record in records:
        key = (record.lang, record.id)
        index_item = index_lookup[key]
        rewritten_html = rewrite_html_links(record.body_html, record.source_rel, source_to_page)
        rewritten_html_by_key[key] = rewritten_html
        index_item["preview_image"] = index_item.get("cover_image") or extract_first_local_image_src(rewritten_html)

    build_series_preview_images(index_items)

    details: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        key = (record.lang, record.id)
        detail_payload = dict(index_lookup[key])
        detail_payload.update(
            {
                "body_markdown": record.body_markdown,
                "body_html": rewritten_html_by_key[key],
            }
        )
        details[key] = detail_payload

    return {
        "index": {
            "generated_at": generated_at,
            "tags": merged_tags,
            "articles": index_items,
        },
        "search": {
            "generated_at": generated_at,
            "articles": {
                lang: {
                    record.id: {
                        "title": normalize_search_text(str(record.meta.get("title") or "")),
                        "series": normalize_search_text(
                            str(record.meta.get("series_title") or record.meta.get("title") or "")
                        ),
                        "content": markdown_to_plain_text(record.body_markdown),
                    }
                    for record in records
                    if record.lang == lang
                }
                for lang in sorted(SUPPORTED_LANGS)
            },
        },
        "details": details,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_rss_xml(site_config: dict[str, str], articles: list[dict[str, Any]], lang: str) -> str:
    if lang == "zh":
        feed_title = f"{site_config['site_name']} - Articles (Chinese)"
        feed_link = f"{site_config['site_url']}/articles.html?lang=zh"
        feed_desc = "Chinese articles feed"
        feed_self = f"{site_config['site_url']}/zh/rss.xml"
        feed_lang = "zh-tw"
    else:
        feed_title = f"{site_config['site_name']} - Articles"
        feed_link = f"{site_config['site_url']}/articles.html?lang=en"
        feed_desc = "Technical and personal articles."
        feed_self = f"{site_config['site_url']}/rss.xml"
        feed_lang = "en-us"

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        "  <channel>",
        f"    <title>{escape(feed_title)}</title>",
        f"    <link>{escape(feed_link)}</link>",
        f"    <description>{escape(feed_desc)}</description>",
        f"    <language>{feed_lang}</language>",
        f'    <atom:link href="{escape(feed_self)}" rel="self" type="application/rss+xml" />',
    ]

    for article in articles:
        link = article["external_url"] or f"{site_config['site_url']}/{article['page_url']}"
        lines.extend(
            [
                "    <item>",
                f"      <title>{escape(str(article['title']))}</title>",
                f"      <link>{escape(str(link))}</link>",
                f"      <guid>{escape(str(link))}</guid>",
                f"      <pubDate>{to_rfc822(str(article['published_at']))}</pubDate>",
                f"      <description>{escape(str(article.get('excerpt') or ''))}</description>",
                "    </item>",
            ]
        )

    lines.extend(["  </channel>", "</rss>"])
    return "\n".join(lines) + "\n"


def write_rss(index_payload: dict[str, Any], site_config: dict[str, str]) -> None:
    articles = index_payload["articles"]
    en_articles = [item for item in articles if item["lang"] == "en"]
    zh_articles = [item for item in articles if item["lang"] == "zh"]

    RSS_EN_PATH.write_text(build_rss_xml(site_config, en_articles, "en"), encoding="utf-8")
    RSS_ZH_PATH.write_text(build_rss_xml(site_config, zh_articles, "zh"), encoding="utf-8")


def write_outputs(payloads: dict[str, Any], site_config: dict[str, str]) -> None:
    write_json(INDEX_PATH, payloads["index"])
    write_json(SEARCH_INDEX_PATH, payloads["search"])
    for (lang, article_id), detail in payloads["details"].items():
        out_path = ARTICLES_DATA_DIR / lang / f"{article_id}.json"
        write_json(out_path, detail)
    write_rss(payloads["index"], site_config)


def build_engineering_rss_xml(
    site_config: dict[str, str], articles: list[dict[str, Any]], lang: str
) -> str:
    """Build RSS XML for the engineering section (technical articles only)."""
    base_url = site_config["site_url"].rstrip("/")
    eng_url = f"{base_url}/engineer"

    if lang == "zh":
        feed_title = f"{site_config['site_name']} - Engineering Articles (Chinese)"
        feed_link = f"{eng_url}/articles.html?lang=zh"
        feed_desc = "Chinese technical articles feed"
        feed_self = f"{eng_url}/rss.xml"
        feed_lang = "zh-tw"
    else:
        feed_title = f"{site_config['site_name']} - Engineering Articles"
        feed_link = f"{eng_url}/articles.html?lang=en"
        feed_desc = "Technical engineering articles."
        feed_self = f"{eng_url}/rss.xml"
        feed_lang = "en-us"

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        "  <channel>",
        f"    <title>{escape(feed_title)}</title>",
        f"    <link>{escape(feed_link)}</link>",
        f"    <description>{escape(feed_desc)}</description>",
        f"    <language>{feed_lang}</language>",
        f'    <atom:link href="{escape(feed_self)}" rel="self" type="application/rss+xml" />',
    ]

    for article in articles:
        link = article["external_url"] or f"{eng_url}/{article['page_url']}"
        lines.extend(
            [
                "    <item>",
                f"      <title>{escape(str(article['title']))}</title>",
                f"      <link>{escape(str(link))}</link>",
                f"      <guid>{escape(str(link))}</guid>",
                f"      <pubDate>{to_rfc822(str(article['published_at']))}</pubDate>",
                f"      <description>{escape(str(article.get('excerpt') or ''))}</description>",
                "    </item>",
            ]
        )

    lines.extend(["  </channel>", "</rss>"])
    return "\n".join(lines) + "\n"


def write_engineering_rss(index_payload: dict[str, Any], site_config: dict[str, str]) -> None:
    """Write a single combined RSS feed for the engineering section."""
    articles = index_payload["articles"]
    # Combine all languages into one engineering RSS feed
    ENG_RSS_PATH.write_text(
        build_engineering_rss_xml(site_config, articles, "en"), encoding="utf-8"
    )


def write_engineering_outputs(payloads: dict[str, Any], site_config: dict[str, str]) -> None:
    """Write engineering site output files (technical articles only)."""
    write_json(ENG_INDEX_PATH, payloads["index"])
    write_json(ENG_SEARCH_INDEX_PATH, payloads["search"])
    for (lang, article_id), detail in payloads["details"].items():
        out_path = ENG_ARTICLES_DATA_DIR / lang / f"{article_id}.json"
        write_json(out_path, detail)
    write_engineering_rss(payloads["index"], site_config)


def main() -> None:
    if not CONTENT_DIR.exists():
        raise FileNotFoundError(f"Missing content directory: {CONTENT_DIR}")
    if not TAGS_PATH.exists():
        raise FileNotFoundError(f"Missing tags file: {TAGS_PATH}")

    site_config = load_site_config()
    base_tags = load_json(TAGS_PATH)
    if not isinstance(base_tags, dict):
        raise ValueError("content/tags.json must be an object")

    validate_content_asset_paths()
    ensure_output_dirs()
    copy_assets()
    records = load_articles()

    # Main site output: all articles
    payloads = build_payloads(records, base_tags)
    write_outputs(payloads, site_config)

    print(f"Built {len(payloads['index']['articles'])} article entries")
    print(f"Wrote index: {INDEX_PATH.relative_to(ROOT)}")
    print(f"Wrote search index: {SEARCH_INDEX_PATH.relative_to(ROOT)}")
    print(f"Wrote details dir: {ARTICLES_DATA_DIR.relative_to(ROOT)}")
    print(f"Copied assets: {ASSETS_ARTICLES_DIR.relative_to(ROOT)}")
    print(f"Wrote RSS: {RSS_EN_PATH.relative_to(ROOT)} and {RSS_ZH_PATH.relative_to(ROOT)}")

    # Engineering site output: technical articles only
    technical_records = [r for r in records if r.meta.get("category") == "technical"]
    ensure_engineering_output_dirs()
    copy_engineering_assets(records)

    if technical_records:
        eng_payloads = build_payloads(technical_records, base_tags)
        write_engineering_outputs(eng_payloads, site_config)
        eng_count = len(eng_payloads["index"]["articles"])
    else:
        # Write empty outputs when no technical articles exist
        empty_payloads: dict[str, Any] = {
            "index": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "tags": base_tags,
                "articles": [],
            },
            "search": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "articles": {lang: {} for lang in sorted(SUPPORTED_LANGS)},
            },
            "details": {},
        }
        write_engineering_outputs(empty_payloads, site_config)
        eng_count = 0

    print(f"\nEngineering site: {eng_count} technical article entries")
    print(f"Wrote eng index: {ENG_INDEX_PATH.relative_to(ROOT)}")
    print(f"Wrote eng search index: {ENG_SEARCH_INDEX_PATH.relative_to(ROOT)}")
    print(f"Wrote eng details dir: {ENG_ARTICLES_DATA_DIR.relative_to(ROOT)}")
    print(f"Copied eng assets: {ENG_ASSETS_ARTICLES_DIR.relative_to(ROOT)}")
    print(f"Wrote eng RSS: {ENG_RSS_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
