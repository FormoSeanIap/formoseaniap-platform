"""One-off generator for favicon.ico and apple-touch-icon.png.

Reads ``site/favicon.svg``, renders raster variants at the resolutions
browsers actually request, and writes them next to the SVG under
``site/``.

This script is a developer aid, **not** part of the build pipeline or
CI. It runs manually whenever the favicon design changes. Because the
raster encoders are not standard library, this is the one script in
``scripts/`` that depends on pip packages (``Pillow`` and
``cairosvg``). To keep the main build dependency-free, install those
packages into a throwaway venv rather than adding them to any project
lock file.

Usage::

    python3 -m venv /tmp/favicon-venv
    /tmp/favicon-venv/bin/pip install Pillow cairosvg
    /tmp/favicon-venv/bin/python scripts/generate_favicons.py

After running, commit the regenerated ``site/favicon.ico`` and
``site/apple-touch-icon.png`` alongside any SVG change.
"""

from __future__ import annotations

import io
from pathlib import Path

import cairosvg
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SVG_PATH = ROOT / "site" / "favicon.svg"
ICO_PATH = ROOT / "site" / "favicon.ico"
APPLE_TOUCH_PATH = ROOT / "site" / "apple-touch-icon.png"

# Rendering backgrounds for the apple-touch icon. iOS renders the icon
# inside its own rounded mask with no browser-tab chrome, so the icon
# needs to ship its own background. The cream colour matches
# ``--bg`` on the light theme in site/assets/css/variables.css.
APPLE_BG = "#f4efe7"


def _render_png(svg_path: Path, size: int) -> Image.Image:
    """Render ``svg_path`` to a ``size``x``size`` RGBA PNG in memory."""
    png_bytes = cairosvg.svg2png(
        bytestring=svg_path.read_bytes(),
        output_width=size,
        output_height=size,
    )
    return Image.open(io.BytesIO(png_bytes)).convert("RGBA")


def build_ico() -> None:
    """Generate a multi-resolution favicon.ico from the light-ink SVG.

    Browsers that fall back to ICO (typically older browsers on light
    chrome) get the light-ink glyph. Dark-chrome modern browsers
    consume the SVG variants directly via their ``media``-scoped
    ``<link rel="icon">`` declarations.
    """
    sizes = [16, 32, 48]
    # Render the source at the largest target size so Pillow can
    # downsample to each frame without upscaling. The ``sizes=`` kwarg
    # on the ICO encoder then writes a 3-frame container.
    source = _render_png(SVG_PATH, max(sizes))
    source.save(
        ICO_PATH,
        format="ICO",
        sizes=[(s, s) for s in sizes],
    )
    print(f"wrote {ICO_PATH.relative_to(ROOT)} ({ICO_PATH.stat().st_size} bytes, sizes={sizes})")


def build_apple_touch() -> None:
    """Generate a 180x180 apple-touch-icon.png with a padded mark on cream.

    iOS masks the icon into a rounded square; padding the mark inside
    the frame (at 66% of the total size, centred) keeps the glyph
    clear of the mask edge.
    """
    size = 180
    background = Image.new("RGBA", (size, size), APPLE_BG)
    mark_size = int(size * 0.66)
    mark = _render_png(SVG_PATH, mark_size)
    offset = ((size - mark_size) // 2, (size - mark_size) // 2)
    background.paste(mark, offset, mark)
    background = background.convert("RGB")
    background.save(APPLE_TOUCH_PATH, format="PNG", optimize=True)
    print(
        f"wrote {APPLE_TOUCH_PATH.relative_to(ROOT)} "
        f"({APPLE_TOUCH_PATH.stat().st_size} bytes, {size}x{size})"
    )


def main() -> None:
    build_ico()
    build_apple_touch()


if __name__ == "__main__":
    main()
