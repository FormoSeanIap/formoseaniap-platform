#!/usr/bin/env python3
"""
Localize Medium-hosted markdown images into local sibling files.

Usage:
  python3 scripts/localize_medium_images.py <path>
  python3 scripts/localize_medium_images.py <path> --write
"""

from __future__ import annotations

import argparse
import hashlib
import mimetypes
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlparse, urlunparse
from urllib.request import Request, urlopen


IMAGE_RE = re.compile(
    r"!\[(?P<alt>[^\]]*)\]"
    r"\("
    r"(?P<leading>\s*)"
    r"(?P<url>https?://[^\s)]+)"
    r"(?P<trailing>(?:\s+(?:\"(?:\\.|[^\"])*\"|'(?:\\.|[^'])*'|\((?:\\.|[^)])*\)))?\s*)"
    r"\)"
)
MEDIUM_IMAGE_HOST_RE = re.compile(r"^(?:cdn-images-\d+\.medium\.com|miro\.medium\.com)$")
ASCII_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
CHAPTER_RE = re.compile(r"\b(chapter|ch)\.?\s*(\d+(?:\.\d+)?)\b", re.IGNORECASE)
EPISODE_RE = re.compile(r"\b(episode|ep)\.?\s*(\d+(?:\.\d+)?)\b", re.IGNORECASE)
SEASON_RE = re.compile(r"\bseason\s*(\d+)\b", re.IGNORECASE)
CJK_ANIME_EPISODE_RE = re.compile(r"(?:動畫|动画)\s*第\s*(\d+(?:\.\d+)?)\s*集")
CJK_CHAPTER_RE = re.compile(r"第\s*(\d+(?:\.\d+)?)\s*話")
CJK_EPISODE_RE = re.compile(r"第\s*(\d+(?:\.\d+)?)\s*集")
CJK_SEASON_RE = re.compile(r"第\s*(\d+)\s*季")
MIME_EXTENSION_OVERRIDES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
    "image/avif": ".avif",
    "image/bmp": ".bmp",
}
RETRYABLE_HTTP_STATUS = {429, 500, 502, 503, 504}
MAX_DOWNLOAD_ATTEMPTS = 6
REQUEST_PAUSE_SECONDS = 1.0
CACHE_DIR = Path("/tmp/localize_medium_images_cache")
MEDIUM_PROXY_BASE = "https://wsrv.nl/?url="
DUCK_PROXY_BASE = "https://proxy.duckduckgo.com/iu/?u="
MEDIUM_MAX_PATH_RE = re.compile(r"^/max/(\d+)/(.*)$")


@dataclass(frozen=True)
class PendingOccurrence:
    path: Path
    start: int
    end: int
    url: str
    alt: str
    trailing: str


@dataclass(frozen=True)
class DownloadedImage:
    content: bytes
    extension: str


@dataclass(frozen=True)
class PlannedOccurrence:
    path: Path
    start: int
    end: int
    url: str
    local_name: str

    @property
    def local_ref(self) -> str:
        return f"./{self.local_name}"


@dataclass(frozen=True)
class FilePlan:
    path: Path
    occurrences: list[PlannedOccurrence]
    rewritten_text: str


class DirectoryPlanner:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.used_names = {
            child.name
            for child in directory.iterdir()
            if child.is_file() and child.suffix.lower() != ".md"
        }
        self.url_to_name: dict[str, str] = {}
        self.fallback_index = 1

    def assign(self, url: str, label: str, extension: str) -> str:
        if url in self.url_to_name:
            return self.url_to_name[url]

        base = slugify_label(label)
        if base:
            candidate = f"{base}{extension}"
            name = unique_name(candidate, self.used_names)
        else:
            while True:
                candidate = f"image-{self.fallback_index:02d}{extension}"
                self.fallback_index += 1
                if candidate not in self.used_names:
                    name = candidate
                    break

        self.used_names.add(name)
        self.url_to_name[url] = name
        return name


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download Medium CDN images referenced by markdown and rewrite them to local sibling paths."
    )
    parser.add_argument("target", help="Markdown file or directory tree to scan.")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Download images, write local files, and rewrite markdown in place.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    target = Path(args.target).resolve()

    try:
        markdown_files = collect_markdown_files(target)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not markdown_files:
        print("No markdown files found.")
        return 0

    pending = scan_files(markdown_files)
    if not pending:
        print("No Medium-hosted markdown images found.")
        return 0

    if args.write:
        try:
            downloads = download_all({occ.url for occ in pending})
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        file_plans = plan_files(pending, downloads)
        write_outputs(file_plans, downloads)
        print_summary(markdown_files, file_plans, downloads, mode="apply")
        return 0

    file_plans = plan_files(pending, None)
    print_summary(markdown_files, file_plans, None, mode="dry-run")
    return 0


def collect_markdown_files(target: Path) -> list[Path]:
    if not target.exists():
        raise ValueError(f"target does not exist: {target}")
    if target.is_file():
        if target.suffix.lower() != ".md":
            raise ValueError(f"target is not a markdown file: {target}")
        return [target]
    if target.is_dir():
        return sorted(path for path in target.rglob("*.md") if path.is_file())
    raise ValueError(f"unsupported target: {target}")


def scan_files(paths: list[Path]) -> list[PendingOccurrence]:
    pending: list[PendingOccurrence] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for match in IMAGE_RE.finditer(text):
            url = match.group("url")
            if not is_medium_image_url(url):
                continue
            pending.append(
                PendingOccurrence(
                    path=path,
                    start=match.start("url"),
                    end=match.end("url"),
                    url=url,
                    alt=match.group("alt"),
                    trailing=match.group("trailing") or "",
                )
            )
    return pending


def is_medium_image_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    return bool(MEDIUM_IMAGE_HOST_RE.fullmatch(parsed.netloc.lower()))


def plan_files(
    pending: list[PendingOccurrence], downloads: dict[str, DownloadedImage] | None
) -> list[FilePlan]:
    by_path: dict[Path, list[PendingOccurrence]] = {}
    for occ in pending:
        by_path.setdefault(occ.path, []).append(occ)

    planners: dict[Path, DirectoryPlanner] = {}
    file_plans: list[FilePlan] = []

    for path in sorted(by_path):
        directory = path.parent
        planner = planners.setdefault(directory, DirectoryPlanner(directory))
        replacements: list[PlannedOccurrence] = []
        for occ in by_path[path]:
            extension = resolve_extension(occ.url, downloads)
            label = extract_label(occ.alt, occ.trailing)
            local_name = planner.assign(occ.url, label, extension)
            replacements.append(
                PlannedOccurrence(
                    path=path,
                    start=occ.start,
                    end=occ.end,
                    url=occ.url,
                    local_name=local_name,
                )
            )

        text = path.read_text(encoding="utf-8")
        rewritten = apply_replacements(text, replacements)
        file_plans.append(FilePlan(path=path, occurrences=replacements, rewritten_text=rewritten))

    return file_plans


def resolve_extension(url: str, downloads: dict[str, DownloadedImage] | None) -> str:
    suffix = url_path_extension(url)
    if suffix:
        return suffix
    if downloads and url in downloads:
        return downloads[url].extension
    return ".img"


def url_path_extension(url: str) -> str:
    path = Path(unquote(urlparse(url).path))
    suffix = path.suffix.lower()
    if not suffix:
        return ""
    if re.fullmatch(r"\.[A-Za-z0-9]{1,6}", suffix):
        return suffix
    return ""


def extract_label(alt: str, trailing: str) -> str:
    title = decode_optional_title(trailing)
    if title:
        return title
    return alt.strip()


def decode_optional_title(trailing: str) -> str:
    text = trailing.strip()
    if not text:
        return ""
    if text[0] == text[-1] and text[0] in {'"', "'"}:
        return decode_markdown_escapes(text[1:-1]).strip()
    if text[0] == "(" and text[-1] == ")":
        return decode_markdown_escapes(text[1:-1]).strip()
    return decode_markdown_escapes(text).strip()


def decode_markdown_escapes(text: str) -> str:
    return (
        text.replace(r"\\", "\\")
        .replace(r"\"", '"')
        .replace(r"\'", "'")
        .replace(r"\)", ")")
        .replace(r"\(", "(")
    )


def slugify_label(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""
    cleaned = re.sub(r"[*_`~]", "", cleaned)
    cleaned = cleaned.replace("&", " and ")
    cleaned = cleaned.replace("×", "x")
    cleaned = CJK_ANIME_EPISODE_RE.sub(
        lambda m: f" anime Ep{format_number_token(m.group(1))} ", cleaned
    )
    cleaned = CJK_CHAPTER_RE.sub(lambda m: f" Ch{format_number_token(m.group(1))} ", cleaned)
    cleaned = CJK_EPISODE_RE.sub(lambda m: f" Ep{format_number_token(m.group(1))} ", cleaned)
    cleaned = CJK_SEASON_RE.sub(lambda m: f" S{m.group(1)} ", cleaned)
    cleaned = CHAPTER_RE.sub(lambda m: f" Ch{format_number_token(m.group(2))} ", cleaned)
    cleaned = EPISODE_RE.sub(lambda m: f" Ep{format_number_token(m.group(2))} ", cleaned)
    cleaned = SEASON_RE.sub(lambda m: f" S{m.group(1)} ", cleaned)
    cleaned = re.sub(r"[“”\"'()\[\]{}:,;!?/\\|]+", " ", cleaned)
    tokens = ASCII_TOKEN_RE.findall(cleaned)
    if not tokens:
        return ""

    parts: list[str] = []
    for token in tokens:
        if re.fullmatch(r"(?:Ch|Ep|S)\d+(?:_\d+)?", token):
            parts.append(token)
            continue
        parts.append(token.lower())

    slug = "_".join(parts)
    slug = re.sub(r"_+", "_", slug).strip("_")
    if len(slug) > 80:
        slug = slug[:80].rstrip("_")
    return slug


def format_number_token(value: str) -> str:
    if value.isdigit():
        number = int(value)
        if number < 100:
            return f"{number:02d}"
        return str(number)
    return value.replace(".", "_")


def unique_name(candidate: str, used_names: set[str]) -> str:
    if candidate not in used_names:
        return candidate

    stem = Path(candidate).stem
    suffix = Path(candidate).suffix
    index = 2
    while True:
        name = f"{stem}-{index}{suffix}"
        if name not in used_names:
            return name
        index += 1


def apply_replacements(text: str, replacements: list[PlannedOccurrence]) -> str:
    if not replacements:
        return text
    out: list[str] = []
    last = 0
    for replacement in replacements:
        out.append(text[last : replacement.start])
        out.append(replacement.local_ref)
        last = replacement.end
    out.append(text[last:])
    return "".join(out)


def download_all(urls: set[str]) -> dict[str, DownloadedImage]:
    downloads: dict[str, DownloadedImage] = {}
    for index, url in enumerate(sorted(urls), start=1):
        cached = read_cached_download(url)
        if cached is not None:
            downloads[url] = cached
            continue
        downloads[url] = download_image(url)
        write_cached_download(url, downloads[url])
        if index < len(urls):
            time.sleep(REQUEST_PAUSE_SECONDS)
    return downloads


def download_image(url: str) -> DownloadedImage:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; localize-medium-images/1.0)",
            "Accept": "image/*,*/*;q=0.8",
        },
    )
    for attempt in range(1, MAX_DOWNLOAD_ATTEMPTS + 1):
        try:
            with urlopen(request, timeout=30) as response:
                content_type = (response.headers.get_content_type() or "").lower()
                content = response.read()
            if not content:
                raise RuntimeError(f"download returned empty body for {url}")
            if content_type and not content_type.startswith("image/"):
                raise RuntimeError(f"download did not return an image for {url}: {content_type}")

            extension = url_path_extension(url) or extension_from_content_type(content_type)
            return DownloadedImage(content=content, extension=extension)
        except HTTPError as exc:
            if exc.code == 429 and is_medium_image_url(url):
                try:
                    return download_image_via_proxy(url)
                except RuntimeError:
                    pass
            if attempt < MAX_DOWNLOAD_ATTEMPTS and exc.code in RETRYABLE_HTTP_STATUS:
                time.sleep(retry_delay_seconds(attempt, exc.headers.get("Retry-After")))
                continue
            raise RuntimeError(f"download failed for {url}: HTTP {exc.code}") from exc
        except URLError as exc:
            if attempt < MAX_DOWNLOAD_ATTEMPTS:
                time.sleep(retry_delay_seconds(attempt, None))
                continue
            raise RuntimeError(f"download failed for {url}: {exc.reason}") from exc

    raise RuntimeError(f"download failed for {url}: exhausted retries")


def retry_delay_seconds(attempt: int, retry_after: str | None) -> float:
    if retry_after:
        try:
            return max(1.0, min(float(retry_after), 30.0))
        except ValueError:
            pass
    return min(5.0 * (2 ** (attempt - 1)), 60.0)


def download_image_via_proxy(source_url: str) -> DownloadedImage:
    errors: list[str] = []
    for candidate, proxy_url in proxy_request_candidates(source_url):
        request = Request(
            proxy_url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; localize-medium-images/1.0)",
                "Accept": "image/*,*/*;q=0.8",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                content_type = (response.headers.get_content_type() or "").lower()
                content = response.read()
        except HTTPError as exc:
            errors.append(f"{candidate}: HTTP {exc.code}")
            continue
        except URLError as exc:
            errors.append(f"{candidate}: {exc.reason}")
            continue

        if not content:
            errors.append(f"{candidate}: empty body")
            continue
        if content_type and not content_type.startswith("image/"):
            errors.append(f"{candidate}: non-image {content_type}")
            continue

        extension = (
            url_path_extension(source_url)
            or url_path_extension(candidate)
            or extension_from_content_type(content_type)
        )
        return DownloadedImage(content=content, extension=extension)

    detail = "; ".join(errors) if errors else "no proxy candidates succeeded"
    raise RuntimeError(f"proxy download failed for {source_url}: {detail}")


def read_cached_download(url: str) -> DownloadedImage | None:
    data_path, meta_path = cache_paths(url)
    if not data_path.exists() or not meta_path.exists():
        return None
    extension = meta_path.read_text(encoding="utf-8").strip() or ".img"
    content = data_path.read_bytes()
    if not content:
        return None
    return DownloadedImage(content=content, extension=extension)


def write_cached_download(url: str, image: DownloadedImage) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    data_path, meta_path = cache_paths(url)
    data_path.write_bytes(image.content)
    meta_path.write_text(image.extension, encoding="utf-8")


def cache_paths(url: str) -> tuple[Path, Path]:
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{key}.bin", CACHE_DIR / f"{key}.ext"


def proxy_source_candidates(source_url: str) -> list[str]:
    candidates: list[str] = []
    canonical = canonical_medium_image_url(source_url)
    if canonical:
        candidates.append(canonical)
    if source_url not in candidates:
        candidates.append(source_url)
    return candidates


def proxy_request_candidates(source_url: str) -> list[tuple[str, str]]:
    requests: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for candidate in proxy_source_candidates(source_url):
        proxy_urls = [
            f"{MEDIUM_PROXY_BASE}{quote(candidate, safe='')}",
            f"{DUCK_PROXY_BASE}{quote(candidate, safe='')}&f=1",
        ]
        for proxy_url in proxy_urls:
            key = (candidate, proxy_url)
            if key in seen:
                continue
            seen.add(key)
            requests.append(key)
    return requests


def canonical_medium_image_url(url: str) -> str:
    if not is_medium_image_url(url):
        return url
    parsed = urlparse(url)
    match = MEDIUM_MAX_PATH_RE.match(parsed.path)
    if not match:
        return url
    width, rest = match.groups()
    canonical_path = f"/v2/resize:fit:{width}/{rest}"
    return urlunparse(parsed._replace(path=canonical_path, params="", query="", fragment=""))


def extension_from_content_type(content_type: str) -> str:
    if not content_type:
        return ".img"
    if content_type in MIME_EXTENSION_OVERRIDES:
        return MIME_EXTENSION_OVERRIDES[content_type]
    guessed = mimetypes.guess_extension(content_type, strict=False)
    return guessed or ".img"


def write_outputs(file_plans: list[FilePlan], downloads: dict[str, DownloadedImage]) -> None:
    asset_targets: dict[Path, bytes] = {}
    for file_plan in file_plans:
        for occ in file_plan.occurrences:
            output_path = file_plan.path.parent / occ.local_name
            asset_targets[output_path] = downloads[occ.url].content

    for output_path, content in sorted(asset_targets.items()):
        output_path.write_bytes(content)
    for file_plan in file_plans:
        file_plan.path.write_text(file_plan.rewritten_text, encoding="utf-8")


def print_summary(
    markdown_files: list[Path],
    file_plans: list[FilePlan],
    downloads: dict[str, DownloadedImage] | None,
    *,
    mode: str,
) -> None:
    refs = sum(len(plan.occurrences) for plan in file_plans)
    unique_urls = {
        occ.url
        for plan in file_plans
        for occ in plan.occurrences
    }
    asset_paths = {
        plan.path.parent / occ.local_name
        for plan in file_plans
        for occ in plan.occurrences
    }

    print(f"Mode: {mode}")
    print(f"Markdown files scanned: {len(markdown_files)}")
    print(f"Markdown files with Medium-hosted images: {len(file_plans)}")
    print(f"Medium image references: {refs}")
    print(f"Unique Medium image URLs: {len(unique_urls)}")
    print(f"Local files {'written' if mode == 'apply' else 'planned'}: {len(asset_paths)}")
    if downloads is None:
        unresolved = sum(1 for url in unique_urls if not url_path_extension(url))
        if unresolved:
            print(f"Note: {unresolved} URL(s) have no file extension; dry-run uses .img placeholders.")
    else:
        print(f"Images downloaded: {len(downloads)}")

    for plan in file_plans:
        print(f"- {plan.path}: {len(plan.occurrences)} reference(s)")
        seen_names: set[str] = set()
        for occ in plan.occurrences:
            if occ.local_name in seen_names:
                continue
            print(f"  {occ.local_ref} <- {occ.url}")
            seen_names.add(occ.local_name)


if __name__ == "__main__":
    raise SystemExit(main())
