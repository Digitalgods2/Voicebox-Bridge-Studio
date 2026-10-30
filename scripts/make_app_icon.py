"""Generate every VoiceBridge Studio logo and icon from branding/logo-source.png.

The source artwork sits on a plain white background. Only the white that is
connected to the image border is removed, so enclosed whites (the filmstrip's
sprocket holes, highlights) stay opaque. The result is cropped to the artwork
and centered on a transparent square.

    python scripts/make_app_icon.py
    cd tauri && bunx tauri icon app-icon.png

Requires Pillow and NumPy (both are in backend/venv).
"""

from __future__ import annotations

from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "branding" / "logo-source.png"
OUT_ICON_SOURCE = ROOT / "tauri" / "app-icon.png"
OUT_APP_LOGO = ROOT / "app" / "src" / "assets" / "app-logo.png"
OUT_FAVICONS = (ROOT / "web" / "public" / "favicon.png", ROOT / "app" / "public" / "favicon.png")

# A pixel is background when every channel is at least this bright and it is
# reachable from the border through other background pixels.
BACKGROUND_MIN = 232
PADDING = 0.03


# Drop shadows on the white background are near-neutral (channel spread up to
# about 30 where they darken into a brown tint); the gold artwork spreads 50+.
SHADOW_MAX_SPREAD = 30
SHADOW_MIN = 120
# Background visible through closed loops in the artwork (the filmstrip's
# upper-left loop) is not connected to the border, so it is seeded explicitly.
# Source-image (x, y) coordinates; update these if the artwork changes.
ENCLOSED_BACKGROUND_SEEDS = ((205, 455),)
# Width in source pixels of the anti-aliased edge cleaned around the background.
EDGE_BAND = 3


def flood(allowed: np.ndarray, seeds: np.ndarray) -> np.ndarray:
    """Pixels in ``allowed`` reachable from ``seeds`` through 4-connected neighbors."""
    height, width = allowed.shape
    reached = np.zeros_like(allowed)
    queue = deque(zip(*np.nonzero(seeds & allowed), strict=True))
    while queue:
        y, x = queue.popleft()
        if reached[y, x]:
            continue
        reached[y, x] = True
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < height and 0 <= nx < width and allowed[ny, nx] and not reached[ny, nx]:
                queue.append((ny, nx))
    return reached


def cut_out(source: Image.Image) -> Image.Image:
    rgb = np.asarray(source.convert("RGB")).astype(np.int16)
    border = np.zeros(rgb.shape[:2], dtype=bool)
    border[[0, -1], :] = border[:, [0, -1]] = True
    for x, y in ENCLOSED_BACKGROUND_SEEDS:
        border[y, x] = True
    background = flood(rgb.min(axis=2) >= BACKGROUND_MIN, border)
    # Shadows cast on the background: neutral light grays connected to it.
    neutral = (rgb.max(axis=2) - rgb.min(axis=2) <= SHADOW_MAX_SPREAD) & (rgb.min(axis=2) >= SHADOW_MIN)
    shadow = flood(neutral | background, background) & ~background

    # Shadows become translucent black so they read on light and dark surfaces.
    alpha = np.full(rgb.shape[:2], 255.0)
    pixels = rgb.astype(np.float64)
    alpha[shadow] = 255 - rgb[shadow].mean(axis=1)
    pixels[shadow] = 0
    alpha[background] = 0

    # Edge pixels are artwork blended with the white background. "Color to
    # alpha" against white recovers the artwork color and its coverage, so no
    # pale fringe shows on dark surfaces.
    cleared = Image.fromarray(np.where(background | shadow, 255, 0).astype(np.uint8))
    band = np.asarray(cleared.filter(ImageFilter.MaxFilter(2 * EDGE_BAND + 1))) > 0
    band &= ~(background | shadow)
    edge = rgb[band].astype(np.float64)
    coverage = np.clip((255 - edge).max(axis=1) / 255, 1 / 255, 1)
    pixels[band] = 255 - (255 - edge) / coverage[:, None]
    alpha[band] = coverage * 255
    rgba = np.dstack([np.clip(pixels, 0, 255), alpha]).round().astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def square(image: Image.Image) -> Image.Image:
    box = image.getchannel("A").point(lambda value: 255 if value > 8 else 0).getbbox()
    art = image.crop(box)
    side = round(max(art.size) * (1 + 2 * PADDING))
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(art, ((side - art.width) // 2, (side - art.height) // 2), art)
    return canvas


def main() -> None:
    logo = square(cut_out(Image.open(SOURCE)))
    outputs = [(OUT_ICON_SOURCE, 1024), (OUT_APP_LOGO, 256)] + [(path, 64) for path in OUT_FAVICONS]
    for path, size in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        logo.resize((size, size), Image.Resampling.LANCZOS).save(path, optimize=True)
        print(f"Wrote {path.relative_to(ROOT)} ({size}px)")


if __name__ == "__main__":
    main()
