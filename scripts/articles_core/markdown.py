"""Minimal Markdown-to-HTML renderer used by the article build pipeline.

This is deliberately a small, opinionated subset. The site ships everything
as static HTML so authors can rely on whatever Markdown features are here
and nothing else. What the renderer supports:

* Paragraphs, blank-line paragraph breaks, and a custom ``\\`` line that
  produces a small in-paragraph break.
* ATX headings (``#`` through ``######``).
* Fenced code blocks with optional language tag.
* Unordered and ordered lists (single-level).
* Blockquotes.
* Inline emphasis via ``**bold**``, ``__bold__``, ``*italic*``, and
  ``_italic_`` with a conservative italic rule so ``snake_case`` survives.
* Inline code, links, and images (including an "image only on its own
  line" mode that pulls the title out as a caption).
* A small "embedded media" hook: a standalone ``[Embedded Media](url)``
  line becomes an iframe when the URL is a recognised YouTube or Vimeo
  video.

The renderer does its own escaping, so callers pass raw Markdown and
receive HTML safe to drop into an article template.
"""

from __future__ import annotations

import re
from html import escape
from urllib.parse import parse_qs, quote, urlencode, urlparse


IMAGE_INLINE_RE = re.compile(
    r'!\[(?P<alt>[^\]]*)\]\((?P<src>[^)\s]+?)(?:\s+"(?P<title>(?:[^"\\]|\\.)*)")?\)'
)
IMAGE_ONLY_LINE_RE = re.compile(
    r'^\s*!\[(?P<alt>[^\]]*)\]\((?P<src>[^)\s]+?)(?:\s+"(?P<title>(?:[^"\\]|\\.)*)")?\)\s*$'
)
EMBED_LINK_ONLY_RE = re.compile(
    r'^\s*\[(?P<label>[^\]]+)\]\((?P<href>[^)]+)\)\s*$'
)


def apply_emphasis_markup(text: str) -> str:
    """Return ``text`` with Markdown emphasis markers replaced by HTML.

    Bold is applied first so paired ``**`` or ``__`` are consumed before
    the italic pass looks at them. Italic markers use a conservative
    word-boundary rule so identifiers like ``snake_case`` keep their
    underscores instead of sprouting ``<em>`` tags.
    """
    # Bold first so paired markers are consumed before italic.
    text = re.sub(r"(?<!\\)\*\*([^\n*]+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\\)__([^\n_]+?)__", r"<strong>\1</strong>", text)
    # Keep italic conservative to avoid converting snake_case identifiers.
    text = re.sub(r"(?<!\\)(?<!\w)\*([^\n*]+?)\*(?!\w)", r"<em>\1</em>", text)
    text = re.sub(r"(?<!\\)(?<!\w)_([^\n_]+?)_(?!\w)", r"<em>\1</em>", text)
    return text


def unescape_image_title(value: str | None) -> str | None:
    """Unescape ``\\"`` and ``\\\\`` inside an image ``title`` attribute.

    Markdown image titles allow a backslash-escaped double-quote so the
    title itself can contain a literal quote. This normalises the
    captured group back to its human-visible form.
    """
    if value is None:
        return None
    return re.sub(r'\\(["\\])', r"\1", value)


def is_embedded_media_label(label: str) -> bool:
    """Return ``True`` when ``label`` is the sentinel embedded-media label."""
    return label.strip().lower() == "embedded media"


def normalize_video_embed_url(raw_href: str) -> str | None:
    """Return an embeddable iframe URL for recognised YouTube/Vimeo links.

    Supports the common YouTube URL shapes (``watch?v=``, ``youtu.be``,
    ``shorts/``, ``/embed/``), preserves ``start``/``end``/``list``
    query params, and coerces the ``t=`` shortcut into the iframe's
    ``start`` param. Supports Vimeo ``vimeo.com/<id>`` and
    ``player.vimeo.com/video/<id>`` shapes.

    Returns ``None`` when the URL is not a recognised embeddable video,
    which lets the caller fall back to an ordinary link.
    """
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
    """Return an ``<iframe>`` block for ``raw_href`` or ``None`` when not embeddable."""
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
    """Render a single line of Markdown inline markup to HTML.

    Inline code, images, and links are tokenised first so their contents
    are not mangled by the emphasis pass. The surrounding text is then
    HTML-escaped, emphasis markers are applied, and the tokens are
    substituted back in place of their placeholders.
    """
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
    """Return ``True`` when ``line`` is a Markdown thematic break (``---``, ``***``, ``___``)."""
    stripped = line.strip()
    return bool(
        re.fullmatch(r"(?:(?:-\s*){3,}|(?:\*\s*){3,}|(?:_\s*){3,})", stripped)
    )


def markdown_to_html(markdown: str) -> str:
    """Return the HTML rendering of a Markdown document.

    Implements the block-level grammar described in this module's
    docstring. The renderer walks lines once, buffering open paragraphs,
    lists, and blockquotes until a boundary flushes them, and emits one
    HTML block per logical Markdown block.
    """
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
