#!/usr/bin/env python3
"""Draws the desktop wallpaper and GRUB background.

Usage: make-wallpaper.py OUT_DIR "OS Name"
Writes OUT_DIR/wallpaper.png (1920x1080) and OUT_DIR/grub.png (1024x768).
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


def render(width, height, name):
    img = Image.new("RGB", (width, height))
    sky = ImageDraw.Draw(img)
    for y in range(height):
        sky.line([(0, y), (width, y)], fill=sky_colour(y / (height - 1)))

    wings = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    wd = ImageDraw.Draw(wings)
    cx, cy, size = width / 2, height * 0.52, min(width, height) * 0.42
    for side in (1, -1):
        draw_wing(wd, cx + side * size * 0.04, cy, size, side)
    wd.ellipse([cx - size * 0.05, cy - size * 0.12, cx + size * 0.05, cy + size * 0.1],
               fill=(255, 235, 150, 255))

    glow = wings.filter(ImageFilter.GaussianBlur(size * 0.08))
    img.paste(glow, (0, 0), glow)
    img.paste(wings, (0, 0), wings)

    text_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    td = ImageDraw.Draw(text_layer)
    try:
        font = ImageFont.truetype(FONT, round(height * 0.07))
    except OSError:
        font = ImageFont.load_default()
    box = td.textbbox((0, 0), name, font=font)
    pos = ((width - (box[2] - box[0])) / 2, height * 0.74)
    td.text(pos, name, font=font, fill=(255, 150, 40, 255))
    text_glow = text_layer.filter(ImageFilter.GaussianBlur(height * 0.012))
    img.paste(text_glow, (0, 0), text_glow)
    td.text(pos, name, font=font, fill=(255, 240, 210, 255))
    img.paste(text_layer, (0, 0), text_layer)
    return img


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    name = sys.argv[2]
    render(1920, 1080, name).save(out / "wallpaper.png", optimize=True)
    render(1024, 768, name).save(out / "grub.png", optimize=True)


if __name__ == "__main__":
    main()
