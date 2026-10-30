"""Generate the VoiceBridge Studio icon artwork.

Writes the 1024px desktop icon source and the in-app logo. Regenerate every
platform icon from the source with:

    python scripts/make_app_icon.py
    cd tauri && bunx tauri icon app-icon.png
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT_ICON_SOURCE = ROOT / "tauri" / "app-icon.png"
OUT_APP_LOGO = ROOT / "app" / "src" / "assets" / "app-logo.png"

BG_TOP = (30, 41, 59)      # slate-800
BG_BOTTOM = (15, 23, 42)   # slate-900
BAR_COLOR = (56, 189, 248)  # sky-400
BAR_COLOR_DIM = (14, 116, 144)  # cyan-800


def render(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Rounded-square background with a vertical gradient.
    for y in range(size):
        t = y / max(size - 1, 1)
        color = tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3))
        draw.line([(0, y), (size, y)], fill=color + (255,))

    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    radius = int(size * 0.22)
    mask_draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    rounded = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    rounded.paste(img, (0, 0), mask)
    img = rounded
    draw = ImageDraw.Draw(img)

    # Waveform / audio-bridge glyph: symmetric bars of varying height.
    bar_count = 7
    margin = size * 0.22
    usable_w = size - 2 * margin
    gap = usable_w * 0.18 / bar_count
    bar_w = (usable_w - gap * (bar_count - 1)) / bar_count
    heights = [0.35, 0.55, 0.85, 1.0, 0.85, 0.55, 0.35]
    center_y = size / 2

    for i, h in enumerate(heights):
        x0 = margin + i * (bar_w + gap)
        x1 = x0 + bar_w
        bar_h = h * size * 0.6
        y0 = center_y - bar_h / 2
        y1 = center_y + bar_h / 2
        color = BAR_COLOR if i in (2, 3, 4) else BAR_COLOR_DIM
        r = bar_w / 2
        draw.rounded_rectangle([x0, y0, x1, y1], radius=r, fill=color + (255,))

    return img


def main() -> None:
    render(1024).save(OUT_ICON_SOURCE)
    print(f"Wrote {OUT_ICON_SOURCE}")
    render(256).save(OUT_APP_LOGO)
    print(f"Wrote {OUT_APP_LOGO}")


if __name__ == "__main__":
    main()
