#!/usr/bin/env python3
"""Rebuilds artwork/fonts/WingsOfFireTitle.otf by tracing the letters of the Wings of Fire title logo.

Usage (one-off, needs the dev venv):
  python3 -m venv build/venv && build/venv/bin/pip install fonttools potracer numpy pillow scikit-image
  build/venv/bin/python scripts/trace-font.py LOGO.png

LOGO.png is the transparent 1024x832 "Wings of Fire Horizontal Title Logo" by ScarletOfTheSkyWings
(DeviantArt); its second row has every letter as a separate shape.

Glyphs: W I N G S F R E from the logo, O derived from the logo's small O, "o" and "f" are the logo's
small raised "OF", plus space. Letter advances reproduce the logo's own spacing.
"""
import sys
from pathlib import Path

import numpy as np
import potrace
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.t2CharStringPen import T2CharStringPen
from PIL import Image, ImageFilter
from scipy import ndimage
from skimage import measure, morphology

OUT = Path(__file__).resolve().parent.parent / "artwork/fonts/WingsOfFireTitle.otf"

ROW = (215, 418)
# Letters of the row, left to right, as they are in the logo.
SEQUENCE = ["W", "I", "N", "G", "S", "o", "f", "F", "I2", "R", "E"]
UPSCALE = 4
BASELINE = 390           # logo pixel row the capitals sit on
CAP_TOP = 266            # top of the plain "I"
UPM = 1000
CAP_HEIGHT = 700
GAP = 6                  # logo pixels after letters whose logo neighbour isn't a letter we keep
SPACE = 34
ALPHA_CUT = 200          # the scan's soft edge makes letters too heavy at lower cut-offs
SMOOTHING = 1.0          # blur radius in logo pixels before tracing, evens out scan wobble


def letter_masks(logo_path):
    alpha = np.array(Image.open(logo_path).convert("RGBA"))[ROW[0]:ROW[1], :, 3]
    solid = alpha > ALPHA_CUT
    labels = measure.label(solid, connectivity=2)
    regions = sorted((r for r in measure.regionprops(labels) if r.area > 30), key=lambda r: r.bbox[1])
    if len(regions) != len(SEQUENCE):
        sys.exit(f"expected {len(SEQUENCE)} letters in the logo row, found {len(regions)}")
    letters = {}
    for name, region in zip(SEQUENCE, regions):
        y0, x0, y1, x1 = region.bbox
        mask = labels[y0:y1, x0:x1] == region.label
        letters[name] = {"mask": mask, "x": x0, "y": y0 + ROW[0], "width": x1 - x0}
    return letters


def stroke_width(mask):
    skeleton = morphology.skeletonize(mask)
    return 2 * float(np.median(ndimage.distance_transform_edt(mask)[skeleton]))


def big_o(letters):
    """The logo only has a small O; scale it to the height of its round sibling S and thin the
    strokes to match."""
    small = letters["o"]["mask"]
    s = letters["S"]
    target_stroke = stroke_width(letters["I"]["mask"]) * 0.75
    height = s["mask"].shape[0]
    factor = height / small.shape[0]
    thinning = max(0, round((stroke_width(small) * factor - target_stroke) / 2))
    size = (round(small.shape[1] * factor) + 2 * thinning, height + 2 * thinning)
    img = Image.fromarray(small.astype(np.uint8) * 255).resize(size, Image.LANCZOS)
    mask = np.array(img.filter(ImageFilter.GaussianBlur(3))) > 128
    mask = ndimage.binary_erosion(mask, morphology.disk(thinning))
    ys, xs = np.nonzero(mask)
    mask = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return {"mask": mask, "x": 0, "y": s["y"] + s["mask"].shape[0] - mask.shape[0],
            "width": mask.shape[1]}


def trace(mask):
    """Potrace curves for a letter mask, in logo pixels relative to the mask's top-left corner."""
    h, w = mask.shape
    img = Image.fromarray(np.pad(mask, 2).astype(np.uint8) * 255)
    img = img.resize(((w + 4) * UPSCALE, (h + 4) * UPSCALE), Image.LANCZOS)
    smooth = np.array(img.filter(ImageFilter.GaussianBlur(UPSCALE * SMOOTHING))) > 128
    return potrace.Bitmap(~smooth).trace(turdsize=16, alphamax=1.2, opticurve=True, opttolerance=0.4)


def draw_glyph(letter, left_bearing, glyph_set):
    """Charstring for a letter: logo pixels -> font units, y flipped, baseline at 0."""
    scale = CAP_HEIGHT / (BASELINE - CAP_TOP)

    def point(p):
        x = (p.x / UPSCALE - 2) + left_bearing
        y = (p.y / UPSCALE - 2) + letter["y"]
        return round(x * scale), round((BASELINE - y) * scale)

    advance = round(letter["advance"] * scale)
    pen = T2CharStringPen(advance, glyph_set)
    for curve in trace(letter["mask"]):
        pen.moveTo(point(curve.start_point))
        for seg in curve.segments:
            if seg.is_corner:
                pen.lineTo(point(seg.c))
                pen.lineTo(point(seg.end_point))
            else:
                pen.curveTo(point(seg.c1), point(seg.c2), point(seg.end_point))
        pen.closePath()
    return pen.getCharString(), advance


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    letters = letter_masks(sys.argv[1])

    for name, nxt in zip(SEQUENCE, SEQUENCE[1:]):
        letters[name]["advance"] = letters[nxt]["x"] - letters[name]["x"]
    letters["I"]["advance"] = letters["N"]["x"] - letters["I"]["x"]
    for name in ("S", "f", "E"):
        letters[name]["advance"] = letters[name]["width"] + GAP
    letters["O"] = big_o(letters)
    letters["O"]["advance"] = letters["O"]["width"] + GAP
    del letters["I2"]

    names = [".notdef", "space"] + sorted(letters)
    charstrings, metrics = {}, {}
    pen = T2CharStringPen(500, None)
    charstrings[".notdef"], metrics[".notdef"] = pen.getCharString(), (500, 0)
    scale = CAP_HEIGHT / (BASELINE - CAP_TOP)
    space = round(SPACE * scale)
    charstrings["space"], metrics["space"] = T2CharStringPen(space, None).getCharString(), (space, 0)
    for name in sorted(letters):
        charstrings[name], advance = draw_glyph(letters[name], 0, None)
        metrics[name] = (advance, 0)

    fb = FontBuilder(UPM, isTTF=False)
    fb.setupGlyphOrder(names)
    fb.setupCharacterMap({ord(" "): "space", **{ord(n): n for n in letters}})
    fb.setupCFF("WingsOfFireTitle-Regular", {"FullName": "Wings of Fire Title"}, charstrings, {})
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=1000, descent=-200)
    fb.setupNameTable({"familyName": "Wings of Fire Title", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=1000, sTypoDescender=-200, usWinAscent=1000, usWinDescent=200,
                sCapHeight=CAP_HEIGHT)
    fb.setupPost()
    fb.font.recalcBBoxes = True
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fb.save(str(OUT))
    print(f"wrote {OUT} with glyphs: {' '.join(sorted(letters))}")


if __name__ == "__main__":
    main()
