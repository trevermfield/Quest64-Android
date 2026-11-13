"""Generate the Android launcher icon set from the engine's icons/512.png (the four Elements gems).
Usage: python3 -I make-icons.py <path to icons/512.png> <output dir>
Writes the same res/ layout the Android project uses, ready for adapt-overlay-polish.py to copy in.
Needs Pillow (a one-time local step; the PNGs are committed, CI does not run this).
"""
import pathlib
import sys

from PIL import Image, ImageDraw

src = Image.open(sys.argv[1]).convert("RGBA")
out = pathlib.Path(sys.argv[2])
BACKGROUND = (34, 25, 24, 255)  # matches ic_launcher_background.xml (#221918)


def resized(size):
    return src.resize((size, size), Image.LANCZOS)


# Adaptive icon foreground: 108dp canvas at xxxhdpi = 432px. Android crops to a circle/squircle, keeping the central
# 66dp (about 61%) safe, so the artwork is scaled to roughly that.
(out / "drawable").mkdir(parents=True, exist_ok=True)
foreground = Image.new("RGBA", (432, 432), (0, 0, 0, 0))
art = resized(288)
foreground.alpha_composite(art, ((432 - 288) // 2, (432 - 288) // 2))
foreground.save(out / "drawable" / "ic_launcher_foreground.png", optimize=True)

# Legacy launcher icons (only used below Android 8): gems on a rounded dark square.
for density, px in (("mdpi", 48), ("hdpi", 72), ("xhdpi", 96), ("xxhdpi", 144), ("xxxhdpi", 192)):
    folder = out / f"mipmap-{density}"
    folder.mkdir(parents=True, exist_ok=True)
    tile = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    mask = Image.new("L", (px, px), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, px - 1, px - 1), radius=px // 5, fill=255)
    tile.paste(Image.new("RGBA", (px, px), BACKGROUND), (0, 0), mask)
    inner = int(px * 0.78)
    tile.alpha_composite(resized(inner), ((px - inner) // 2, (px - inner) // 2))
    tile.save(folder / "ic_launcher.png", optimize=True)

print("icons written to", out)
