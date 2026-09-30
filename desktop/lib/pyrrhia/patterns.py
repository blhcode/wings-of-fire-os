"""Seamless SVG tiles, one per tribe pattern (stars for NightWings, waves for SeaWings, ...).

Used for Firefox's toolbar, the terminal background, wallpapers and the settings app.
"""
import math
import random
from urllib.parse import quote


def _svg(width, height, body, background=None):
    bg = f'<rect width="{width}" height="{height}" fill="{background}"/>' if background else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">{bg}{body}</svg>')


def _stars(fg, rng):
    body = []
    for _ in range(26):
        x, y, r = rng.uniform(6, 194), rng.uniform(6, 194), rng.choice((0.6, 0.8, 1.1, 1.5))
        body.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fg}" opacity="{rng.uniform(0.35, 1):.2f}"/>')
    for _ in range(3):
        x, y, s = rng.uniform(15, 185), rng.uniform(15, 185), rng.uniform(3, 5)
        body.append(f'<path d="M{x:.1f} {y - s:.1f}L{x + s / 4:.1f} {y:.1f}L{x:.1f} {y + s:.1f}'
                    f'L{x - s / 4:.1f} {y:.1f}ZM{x - s:.1f} {y:.1f}L{x:.1f} {y - s / 4:.1f}'
                    f'L{x + s:.1f} {y:.1f}L{x:.1f} {y + s / 4:.1f}Z" fill="{fg}"/>')
    return 200, 200, "".join(body)


def _waves(fg, rng):
    body = "".join(
        f'<path d="M0 {y} Q15 {y - 9} 30 {y} T60 {y} T90 {y} T120 {y}" fill="none" stroke="{fg}" '
        f'stroke-width="2" opacity="{o}"/>' for y, o in ((12, 0.9), (32, 0.5)))
    return 120, 40, body


def _embers(fg, rng):
    body = "".join(
        f'<circle cx="{rng.uniform(4, 156):.1f}" cy="{rng.uniform(4, 156):.1f}" r="{rng.uniform(0.8, 2.4):.1f}" '
        f'fill="{fg}" opacity="{rng.uniform(0.3, 0.9):.2f}"/>' for _ in range(18))
    return 160, 160, body


def _frost(fg, rng):
    parts = []
    for cx, cy, s in ((30, 30, 16), (90, 85, 11)):
        for k in range(6):
            a = math.radians(k * 60)
            ex, ey = cx + s * math.cos(a), cy + s * math.sin(a)
            parts.append(f"M{cx} {cy}L{ex:.1f} {ey:.1f}")
            for side in (-1, 1):
                b = a + side * math.radians(35)
                mx, my = cx + s * 0.6 * math.cos(a), cy + s * 0.6 * math.sin(a)
                parts.append(f"M{mx:.1f} {my:.1f}L{mx + s * 0.35 * math.cos(b):.1f} {my + s * 0.35 * math.sin(b):.1f}")
    return 120, 120, f'<path d="{"".join(parts)}" stroke="{fg}" stroke-width="1.6" stroke-linecap="round" fill="none"/>'


def _dunes(fg, rng):
    body = "".join(
        f'<path d="M0 {y} C30 {y - 10} 60 {y + 10} 90 {y} S150 {y - 10} 180 {y}" fill="none" '
        f'stroke="{fg}" stroke-width="{w}" opacity="{o}"/>' for y, w, o in ((14, 2, 0.8), (34, 1.4, 0.5), (50, 1, 0.35)))
    return 180, 60, body


def _leaves(fg, rng):
    leaf = "M0 -14 C9 -8 9 8 0 14 C-9 8 -9 -8 0 -14Z M0 -12 L0 12"
    body = "".join(
        f'<path d="{leaf}" transform="translate({x} {y}) rotate({a})" fill="{fg}" fill-opacity="0.55" '
        f'stroke="{fg}" stroke-width="1"/>' for x, y, a in ((25, 25, 30), (75, 60, -40), (35, 90, 70)))
    return 100, 110, body


def _hex(fg, rng):
    d = "M28 66L0 50L0 16L28 0L56 16L56 50L28 66L28 100"
    return 56, 100, f'<path d="{d}" fill="none" stroke="{fg}" stroke-width="1.6"/>'


def _silk(fg, rng):
    body = "".join(
        f'<path d="M{x} 0 L{x + 80} 80" stroke="{fg}" stroke-width="{w}" opacity="{o}"/>'
        f'<path d="M{x + 80} 0 L{x} 80" stroke="{fg}" stroke-width="{w}" opacity="{o * 0.5}"/>'
        for x, w, o in ((-40, 1, 0.7), (0, 0.6, 0.5), (40, 1, 0.7)))
    return 80, 80, body


def _mud(fg, rng):
    body = "".join(
        f'<ellipse cx="{rng.uniform(10, 110):.1f}" cy="{rng.uniform(10, 110):.1f}" rx="{rng.uniform(4, 10):.1f}" '
        f'ry="{rng.uniform(2, 5):.1f}" fill="{fg}" opacity="{rng.uniform(0.25, 0.6):.2f}"/>' for _ in range(9))
    return 120, 120, body


def _rain(fg, rng):
    body = []
    for _ in range(16):
        x, y, length = rng.uniform(5, 115), rng.uniform(5, 105), rng.uniform(6, 14)
        body.append(f'<path d="M{x:.1f} {y:.1f}l-2 {length:.1f}" stroke="{fg}" stroke-width="1.3" '
                    f'stroke-linecap="round" opacity="{rng.uniform(0.4, 0.9):.2f}"/>')
    return 120, 120, "".join(body)


_GENERATORS = {
    "stars": _stars, "waves": _waves, "embers": _embers, "frost": _frost, "dunes": _dunes,
    "leaves": _leaves, "hex": _hex, "silk": _silk, "mud": _mud, "rain": _rain,
}


def tile(pattern, colour, background=None, opacity=1.0, scale=1.0):
    """(width, height, svg) of one tile of the pattern drawn in `colour`."""
    width, height, body = _GENERATORS[pattern](colour, random.Random(pattern))
    width, height = width * scale, height * scale
    body = f'<g opacity="{opacity}" transform="scale({scale})">{body}</g>'
    return width, height, _svg(f"{width:g}", f"{height:g}", body, background)


def svg(pattern, colour, background=None, opacity=1.0, scale=1.0):
    return tile(pattern, colour, background, opacity, scale)[2]


def data_uri(svg_text):
    return "data:image/svg+xml," + quote(svg_text)
