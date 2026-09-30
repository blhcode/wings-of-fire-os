#!/usr/bin/env python3
"""Draws the Wings of Fire OS artwork that isn't a shipped wallpaper.

Usage: make-artwork.py OUT_DIR [WALLPAPER]
Writes into OUT_DIR:
  grub.png           1024x768   boot menu background: the emblem and wordmark, like the boot splash
  logo.png           256x256    the emblem from artwork/bootlogo.png, cropped to its circle (the OS logo)
  welcome.png        457x300    installer welcome banner
  slide.png          800x480    installer slideshow
  wordmark.png       stacked "Wings / of / Fire / OS" in the book-cover lettering style
  wordmark-wide.png  the same on one line (boot splash)
  spinner.png        loading ring that fits around artwork/bootlogo.png (boot splash)
The installer images are cropped from WALLPAPER when given, otherwise drawn.
"""
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageFont

ARTWORK = Path(__file__).resolve().parent.parent / "artwork"
WORDMARK_FONT = ARTWORK / "fonts/WingsOfFireTitle.otf"

# Top-to-bottom colour of the Wings of Fire title: dark red, through orange, to gold and back.
FIRE = [(0.0, (130, 14, 18)), (0.28, (212, 40, 28)), (0.45, (242, 112, 30)),
        (0.55, (255, 190, 64)), (0.68, (242, 112, 30)), (0.85, (212, 40, 28)), (1.0, (150, 18, 20))]

# WingsOfFireTitle.otf (traced from the book logo by scripts/trace-font.py) only has the glyphs
# W I N G S O F R E, space, and "o" "f" for the small raised "OF". Its spacing is the logo's own,
# so "WINGSofFIRE" without spaces reproduces the logo exactly.
STACKED = ["WINGS", "of", "FIRE OS"]
WIDE = ["WINGSofFIRE OS"]

# Circle of artwork/bootlogo.png (500x500): centre and radius in pixels.
EMBLEM_CENTRE = (251, 242.5)
EMBLEM_RADIUS = 217
SPINNER_SIZE = 540


def lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def gradient_colour(stops, t):
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t <= t1:
            return lerp(c0, c1, (t - t0) / (t1 - t0))
    return stops[-1][1]


def wordmark(lines, height):
    """Renders lines of text in fire-gradient lettering, trimmed and scaled to `height`."""
    base = 400
    font = ImageFont.truetype(str(WORDMARK_FONT), base)

    layout = []
    for text in lines:
        left, top, right, bottom = font.getbbox(text, anchor="ls")
        layout.append((text, left, right, top, bottom))

    width = max(r - l for _, l, r, _, _ in layout)
    gap = -base * 0.07
    pad = base * 0.3
    canvas_h = sum(b - t for *_, t, b in layout) + gap * (len(layout) - 1) + 2 * pad
    mask = Image.new("L", (round(width + 2 * pad), round(canvas_h)), 0)
    draw = ImageDraw.Draw(mask)
    y = pad
    for text, left, right, top, bottom in layout:
        x = pad + (width - (right - left)) / 2 - left
        draw.text((x, y - top), text, font=font, fill=255, anchor="ls")
        y += bottom - top + gap

    left, top, right, bottom = mask.getbbox()
    fill = Image.new("RGB", mask.size)
    fd = ImageDraw.Draw(fill)
    for row in range(mask.height):
        t = min(max((row - top) / (bottom - top), 0), 1)
        fd.line([(0, row), (mask.width, row)], fill=gradient_colour(FIRE, t))

    edge = mask.filter(ImageFilter.MaxFilter(9))
    glow = edge.filter(ImageFilter.GaussianBlur(base * 0.06)).point(lambda v: v * 0.55)
    out = Image.new("RGBA", mask.size, (0, 0, 0, 0))
    out = Image.alpha_composite(out, solid((255, 120, 30), glow))
    out = Image.alpha_composite(out, solid((70, 8, 10), edge))
    out.paste(fill, (0, 0), mask)

    out = out.crop(out.getbbox())
    return out.resize((round(out.width * height / out.height), height), Image.LANCZOS)


def solid(colour, alpha):
    layer = Image.new("RGBA", alpha.size, colour + (0,))
    layer.putalpha(alpha)
    return layer


def spinner():
    """Faint full ring plus a bright arc with a fading tail, centred for rotation.

    Drawn at the bootlogo's scale: the ring hugs the emblem's circle when both are scaled equally.
    """
    scale = 4
    size = SPINNER_SIZE * scale
    c = size / 2
    radius = (EMBLEM_RADIUS + 18) * scale
    thickness = 13 * scale
    ring = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(ring)
    box = [c - radius, c - radius, c + radius, c + radius]
    draw.ellipse(box, outline=(90, 200, 255, 45), width=thickness)
    steps = 240
    sweep = 280
    for i in range(steps):
        t = i / steps
        start = -90 + t * sweep
        colour = lerp((40, 170, 255), (215, 250, 255), t)
        draw.arc(box, start, start + sweep / steps + 0.6, fill=colour + (round(255 * t ** 0.9),),
                 width=thickness)
    head = math.radians(-90 + sweep)
    hx, hy = c + radius * math.cos(head), c + radius * math.sin(head)
    dot = thickness * 0.9
    draw.ellipse([hx - dot, hy - dot, hx + dot, hy + dot], fill=(235, 252, 255, 255))
    ring = ring.resize((SPINNER_SIZE, SPINNER_SIZE), Image.LANCZOS)
    glow = ring.filter(ImageFilter.GaussianBlur(6))
    return Image.alpha_composite(glow, ring)


def scene(width, height):
    """The boot splash as a still: emblem and wordmark on black, between GRUB's menu entries (top
    quarter) and the bottom of its menu box (70% down at 640x480)."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    size, cy = round(height * 0.30), height * 0.43
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([width / 2 - size * 0.6, cy - size * 0.6,
                                  width / 2 + size * 0.6, cy + size * 0.6], fill=(40, 170, 255, 70))
    img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(size * 0.15)))
    img.alpha_composite(logo(size), (round((width - size) / 2), round(cy - size / 2)))
    mark = wordmark(WIDE, round(height * 0.055))
    img.alpha_composite(mark, (round((width - mark.width) / 2), round(cy + size / 2 + height * 0.025)))
    return img.convert("RGB")


def logo(size):
    """The boot splash emblem, cropped to its circle."""
    emblem = Image.open(ARTWORK / "bootlogo.png").convert("RGBA")
    (cx, cy), r = EMBLEM_CENTRE, EMBLEM_RADIUS + 6
    box = (round(cx - r), round(cy - r), round(cx + r), round(cy + r))
    return emblem.crop(box).resize((size, size), Image.LANCZOS)


def main():
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    photo = Image.open(sys.argv[2]).convert("RGB") if len(sys.argv) == 3 else None

    def banner(width, height):
        if photo is None:
            return scene(width, height)
        return ImageOps.fit(photo, (width, height), Image.LANCZOS)

    scene(1024, 768).save(out / "grub.png", optimize=True)
    banner(457, 300).save(out / "welcome.png", optimize=True)
    banner(800, 480).save(out / "slide.png", optimize=True)
    logo(256).save(out / "logo.png", optimize=True)
    wordmark(STACKED, 480).save(out / "wordmark.png", optimize=True)
    wordmark(WIDE, 160).save(out / "wordmark-wide.png", optimize=True)
    spinner().save(out / "spinner.png", optimize=True)


if __name__ == "__main__":
    main()
