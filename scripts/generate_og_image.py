"""One-off generator for the site's default Open Graph share image.

Reads no source files — the output is driven by the constants at the top
of this script. Writes a 1200x630 PNG to ``site/assets/og/default.png``
suitable for LinkedIn, Slack, Discord, Twitter (via
``summary_large_image``), and Facebook share cards.

This is a developer aid, **not** part of the build pipeline or CI. It
runs manually whenever the OG design changes. Like
``scripts/generate_favicons.py``, it depends on Pillow — a pip package
that intentionally does not live in any project lock file so the main
build stays dependency-free. Install into a throwaway venv::

    python3 -m venv /tmp/og-venv
    /tmp/og-venv/bin/pip install Pillow
    /tmp/og-venv/bin/python scripts/generate_og_image.py

After running, commit the regenerated ``site/assets/og/default.png``.
A copy is also written to ``site-eng/assets/og/default.png`` so the
engineering tree serves the same card without an extra runtime fetch.

Design notes
------------
- 1200x630 is the canonical OG image size. Most consumers re-crop to
  1.91:1 aspect, so the safe area is the full frame but text should
  stay well within the centre.
- Dark background matches the site's dark-theme palette so the card
  reads identically whether the viewer is on dark or light mode.
- Serif headline font mirrors the Noto Serif JP used across the site
  for display type. DejaVu Serif is the free-font stand-in available
  on the generator machine; the actual shipped PNG is a raster so the
  viewer never needs the font installed.
- Accent stripe on the left is the same warm ochre used for links
  across the site (``--accent`` in ``site/assets/css/variables.css``).
"""

from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH_MAIN = ROOT / "site" / "assets" / "og" / "default.png"
OUTPUT_PATH_ENG = ROOT / "site-eng" / "assets" / "og" / "default.png"

WIDTH = 1200
HEIGHT = 630

# Palette — taken from site/assets/css/variables.css dark-theme values.
BG = "#17120d"
TEXT_PRIMARY = "#f7f7f2"
TEXT_MUTED = "#bfb8ad"
ACCENT = "#c78c3c"

# Layout
SAFE_PADDING = 72
ACCENT_STRIPE_WIDTH = 10

# Typography
TITLE = "Sêng-Gān Ia̍p"
SUBTITLE = "Platform Engineer / Writer / Creator"
URL_LINE = "www.formoseaniap.com"

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"


def _load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _draw_card(output: Path) -> None:
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    # Accent stripe on the left edge.
    draw.rectangle(
        [(0, 0), (ACCENT_STRIPE_WIDTH, HEIGHT)],
        fill=ACCENT,
    )

    # Kicker line — small all-caps label above the title.
    kicker_font = _load_font(FONT_REGULAR, 32)
    draw.text(
        (SAFE_PADDING, SAFE_PADDING),
        "PORTFOLIO",
        font=kicker_font,
        fill=ACCENT,
    )

    # Title — bold serif, large. Sits roughly 20% down the frame.
    title_font = _load_font(FONT_BOLD, 108)
    draw.text(
        (SAFE_PADDING, SAFE_PADDING + 60),
        TITLE,
        font=title_font,
        fill=TEXT_PRIMARY,
    )

    # Subtitle — the site tagline. Kept medium-weight and muted so it
    # doesn't compete with the title.
    subtitle_font = _load_font(FONT_REGULAR, 44)
    draw.text(
        (SAFE_PADDING, SAFE_PADDING + 60 + 140),
        SUBTITLE,
        font=subtitle_font,
        fill=TEXT_MUTED,
    )

    # URL line — small, bottom-left. Gives the viewer the domain at a
    # glance without having to expand the card.
    url_font = _load_font(FONT_REGULAR, 32)
    draw.text(
        (SAFE_PADDING, HEIGHT - SAFE_PADDING - 32),
        URL_LINE,
        font=url_font,
        fill=TEXT_MUTED,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    img.save(output, format="PNG", optimize=True)


def main() -> None:
    _draw_card(OUTPUT_PATH_MAIN)
    print(f"Wrote {OUTPUT_PATH_MAIN.relative_to(ROOT)} ({OUTPUT_PATH_MAIN.stat().st_size} bytes)")

    # Mirror to the engineering tree so /engineer/assets/og/default.png
    # serves the same image byte-identical.
    OUTPUT_PATH_ENG.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(OUTPUT_PATH_MAIN, OUTPUT_PATH_ENG)
    print(f"Mirrored to {OUTPUT_PATH_ENG.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
