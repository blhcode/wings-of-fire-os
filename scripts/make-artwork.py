#!/usr/bin/env python3
"""Draws all Wings of Fire OS artwork.

Usage: make-artwork.py OUT_DIR "OS Name"
Writes into OUT_DIR:
  wallpaper.png  1920x1080  desktop background
  grub.png       1024x768   boot menu background
  logo.png       256x256    transparent logo (installer, launcher icon)
  welcome.png    457x300    installer welcome banner
  slide.png      800x480    installer slideshow
"""
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

SKY = [(0.0, (10, 3, 8)), (0.55, (70, 8, 12)), (1.0, (215, 80, 18))]
FEATHERS = [(255, 220, 90), (255, 170, 40), (245, 110, 25), (215, 55, 20), (160, 25, 20)]


def lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def sky_colour(t):
    for (t0, c0), (t1, c1) in zip(SKY, SKY[1:]):
        if t <= t1:
            return lerp(c0, c1, (t - t0) / (t1 - t0))
    return SKY[-1][1]


def draw_wing(draw, cx, cy, size, side):
    """Fan of feathers sweeping up and outward from (cx, cy); side is 1 (right) or -1 (left)."""
    count = 9
    for i in range(count):
        angle = math.radians(12 + i * 8)
        length = size * (1.0 - i * 0.07)
        tip = (cx + side * length * math.cos(angle), cy - length * math.sin(angle))
        spread = size * 0.07
        base_a = (cx + side * spread * math.sin(angle), cy + spread * math.cos(angle))
        base_b = (cx - side * spread * math.sin(angle), cy - spread * math.cos(angle))
        mid = (cx + side * length * 0.55 * math.cos(angle - 0.08),
               cy - length * 0.55 * math.sin(angle - 0.08) + size * 0.06)
        colour = FEATHERS[min(i * len(FEATHERS) // count, len(FEATHERS) - 1)]
        draw.polygon([base_a, mid, tip, base_b], fill=colour + (235,))


def wings_layer(width, height, cx, cy, size):
    """Transparent layer with both wings, the body and a soft glow behind them."""
    wings = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    wd = ImageDraw.Draw(wings)
    for side in (1, -1):
        draw_wing(wd, cx + side * size * 0.04, cy, size, side)
    wd.ellipse([cx - size * 0.05, cy - size * 0.12, cx + size * 0.05, cy + size * 0.1],
               fill=(255, 235, 150, 255))
    glow = wings.filter(ImageFilter.GaussianBlur(size * 0.08))
    return Image.alpha_composite(glow, wings)


def glowing_text(img, text, top):
    width, height = img.size
    try:
        font = ImageFont.truetype(FONT, round(height * 0.07))
    except OSError:
        font = ImageFont.load_default()
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    td = ImageDraw.Draw(layer)
    box = td.textbbox((0, 0), text, font=font)
    pos = ((width - (box[2] - box[0])) / 2, top)
    td.text(pos, text, font=font, fill=(255, 150, 40, 255))
    layer = layer.filter(ImageFilter.GaussianBlur(height * 0.012))
    ImageDraw.Draw(layer).text(pos, text, font=font, fill=(255, 240, 210, 255))
    return Image.alpha_composite(img, layer)


def scene(width, height, name):
    img = Image.new("RGBA", (width, height))
    sky = ImageDraw.Draw(img)
    for y in range(height):
        sky.line([(0, y), (width, y)], fill=sky_colour(y / (height - 1)))
    img = Image.alpha_composite(
        img, wings_layer(width, height, width / 2, height * 0.52, min(width, height) * 0.42))
    return glowing_text(img, name, height * 0.74).convert("RGB")


def logo(size):
    return wings_layer(size, size, size / 2, size * 0.6, size * 0.42)


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    name = sys.argv[2]
    scene(1920, 1080, name).save(out / "wallpaper.png", optimize=True)
    scene(1024, 768, name).save(out / "grub.png", optimize=True)
    scene(457, 300, name).save(out / "welcome.png", optimize=True)
    scene(800, 480, name).save(out / "slide.png", optimize=True)
    logo(256).save(out / "logo.png", optimize=True)


if __name__ == "__main__":
    main()
