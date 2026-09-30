"""Drawing the scroll with cairo: parchment between two wooden rollers, plus the wax seal.

Everything here is pure cairo (no GTK) so frames can be rendered offscreen for previews and tests.

progress 0 = rolled up (both rollers together in the middle), 1 = fully open.
"""
import math
import random
from dataclasses import dataclass

import cairo

MARGIN = 10          # transparent space around the scroll (for the shadow)
ROLLER = 30          # roller diameter when open
ROLLER_EXTRA = 22    # extra thickness when rolled up (the paper wound around it)
KNOB = 8            # how far the knobs stick out above and below the parchment
PAPER_INSET_Y = 26   # parchment top/bottom inset from the window edge (room for knobs)
CONTENT_PAD = 22     # gap between a roller and the text


@dataclass
class Look:
    parchment: tuple = (0.953, 0.902, 0.769)
    parchment_edge: tuple = (0.80, 0.68, 0.45)
    ink: tuple = (0.23, 0.165, 0.10)
    wood: tuple = (0.42, 0.25, 0.13)
    knob: tuple = (0.12, 0.43, 0.55)       # tribe accent
    seal: tuple = (0.12, 0.44, 0.55)       # tribe seal colour
    opaque_surround: tuple = None          # fill outside the scroll when there's no compositing


def ease_out_cubic(t):
    return 1 - (1 - t) ** 3


def ease_in_out_cubic(t):
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def clamp01(t):
    return max(0.0, min(1.0, t))


def phase(ms, start, end):
    return clamp01((ms - start) / (end - start))


# --- timelines ---------------------------------------------------------------------------------

OPEN_MS = 700
CLOSE_MS = 560


def open_frame(ms):
    """(progress, seal_pop, content_alpha) at `ms` into the opening animation.
    seal_pop: 0 = seal sitting on the rolled scroll, 1 = popped off and gone."""
    return (ease_out_cubic(phase(ms, 110, 600)),
            ease_out_cubic(phase(ms, 0, 180)),
            phase(ms, 520, OPEN_MS))


def close_frame(ms):
    return (1 - ease_in_out_cubic(phase(ms, 100, 470)),
            1 - ease_out_cubic(phase(ms, 400, CLOSE_MS)),
            1 - phase(ms, 0, 140))


# --- geometry ----------------------------------------------------------------------------------

def roller_width(progress):
    return ROLLER + ROLLER_EXTRA * (1 - progress) ** 1.5


def paper_span(width, progress):
    """x of the left and right edge of the visible parchment."""
    cx = width / 2
    full_half = width / 2 - MARGIN - ROLLER / 2
    half = full_half * progress
    return cx - half, cx + half


def content_margins(width, height):
    """Margins (left, top, right, bottom) of the area the editor widgets sit in when fully open."""
    side = MARGIN + ROLLER + CONTENT_PAD
    return side, PAPER_INSET_Y + 6, side, PAPER_INSET_Y + 6


def hit_edge(width, height, x, y):
    """Which window edge a pointer at (x, y) should resize, or None."""
    left = x < MARGIN + ROLLER + 4
    right = x > width - MARGIN - ROLLER - 4
    top = y < PAPER_INSET_Y
    bottom = y > height - PAPER_INSET_Y
    if not (left or right or top or bottom):
        return None
    return ("n" if top else "s" if bottom else "") + ("w" if left else "e" if right else "")


# --- parchment ---------------------------------------------------------------------------------

_texture_cache = {}


def parchment_texture(width, height, look):
    key = (width, height, look.parchment, look.parchment_edge)
    if key in _texture_cache:
        return _texture_cache[key]
    _texture_cache.clear()
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, max(1, width), max(1, height))
    cr = cairo.Context(surface)
    rng = random.Random(7)
    cr.set_source_rgb(*look.parchment)
    cr.paint()
    # Soft stains.
    for _ in range(max(4, width * height // 60000)):
        x, y = rng.uniform(0, width), rng.uniform(0, height)
        r = rng.uniform(40, 160)
        g = cairo.RadialGradient(x, y, 0, x, y, r)
        g.add_color_stop_rgba(0, *look.parchment_edge, rng.uniform(0.05, 0.12))
        g.add_color_stop_rgba(1, *look.parchment_edge, 0)
        cr.set_source(g)
        cr.arc(x, y, r, 0, math.tau)
        cr.fill()
    # Fibres.
    cr.set_line_width(0.6)
    for _ in range(width * height // 900):
        x, y = rng.uniform(0, width), rng.uniform(0, height)
        a = rng.uniform(-0.4, 0.4)
        length = rng.uniform(4, 14)
        dark = rng.random() < 0.6
        cr.set_source_rgba(*(look.parchment_edge if dark else (1, 1, 1)), rng.uniform(0.08, 0.2))
        cr.move_to(x, y)
        cr.line_to(x + length * math.cos(a), y + length * math.sin(a))
        cr.stroke()
    # Speckles.
    for _ in range(width * height // 1500):
        cr.set_source_rgba(*look.parchment_edge, rng.uniform(0.1, 0.35))
        cr.arc(rng.uniform(0, width), rng.uniform(0, height), rng.uniform(0.3, 0.9), 0, math.tau)
        cr.fill()
    # Aged edges at top and bottom.
    for y0, y1 in ((0, 60), (height, height - 60)):
        g = cairo.LinearGradient(0, y0, 0, y1)
        g.add_color_stop_rgba(0, *look.parchment_edge, 0.45)
        g.add_color_stop_rgba(1, *look.parchment_edge, 0)
        cr.set_source(g)
        cr.rectangle(0, min(y0, y1), width, 60)
        cr.fill()
    _texture_cache[key] = surface
    return surface


def _deckle(width, seed, amplitude=2.2, step=9):
    rng = random.Random(seed)
    return [(x, rng.uniform(-amplitude, amplitude)) for x in range(0, int(width) + step, step)]


def _paper_path(cr, x0, x1, top, bottom, width):
    top_edge = _deckle(width, 1)
    bottom_edge = _deckle(width, 2)
    cr.move_to(x0, top)
    for x, dy in top_edge:
        if x0 < x < x1:
            cr.line_to(x, top + dy)
    cr.line_to(x1, top)
    cr.line_to(x1, bottom)
    for x, dy in reversed(bottom_edge):
        if x0 < x < x1:
            cr.line_to(x, bottom + dy)
    cr.line_to(x0, bottom)
    cr.close_path()


def draw_paper(cr, width, height, x0, x1, look):
    top, bottom = PAPER_INSET_Y, height - PAPER_INSET_Y
    if x1 - x0 < 1:
        return
    # Shadow.
    for i in range(6, 0, -1):
        cr.set_source_rgba(0, 0, 0, 0.035)
        cr.rectangle(x0 + i * 0.5, top + i, x1 - x0, bottom - top)
        cr.fill()
    cr.save()
    _paper_path(cr, x0, x1, top, bottom, width)
    cr.clip_preserve()
    tex = parchment_texture(int(width), int(height), look)
    cr.set_source_surface(tex, 0, 0)
    cr.fill()
    # The paper curls into each roller.
    for edge, direction in ((x0, 1), (x1, -1)):
        g = cairo.LinearGradient(edge, 0, edge + direction * 36, 0)
        g.add_color_stop_rgba(0, 0.25, 0.15, 0.05, 0.35)
        g.add_color_stop_rgba(1, 0.25, 0.15, 0.05, 0)
        cr.set_source(g)
        cr.rectangle(min(edge, edge + direction * 36), top - 4, 36, bottom - top + 8)
        cr.fill()
    cr.restore()


# --- rollers -----------------------------------------------------------------------------------

def _shade(colour, amount):
    if amount >= 0:
        return tuple(c + (1 - c) * amount for c in colour)
    return tuple(c * (1 + amount) for c in colour)


def draw_roller(cr, cx, height, diameter, look, paper_wound):
    top, bottom = PAPER_INSET_Y - 3, height - PAPER_INSET_Y + 3

    def cylinder(colour, x, w, y0, y1, alpha=1.0):
        g = cairo.LinearGradient(x, 0, x + w, 0)
        g.add_color_stop_rgba(0, *_shade(colour, -0.45), alpha)
        g.add_color_stop_rgba(0.35, *_shade(colour, 0.15), alpha)
        g.add_color_stop_rgba(0.55, *_shade(colour, 0.05), alpha)
        g.add_color_stop_rgba(1, *_shade(colour, -0.55), alpha)
        cr.set_source(g)
        cr.rectangle(x, y0, w, y1 - y0)
        cr.fill()

    # The wooden rod, then the parchment wound around it (thick when rolled up, gone when open).
    cylinder(look.wood, cx - ROLLER / 2, ROLLER, top, bottom)
    r = diameter / 2
    wrap_alpha = clamp01(paper_wound * 4)
    if wrap_alpha > 0:
        cylinder(look.parchment, cx - r, diameter, top + 3, bottom - 3, wrap_alpha)
        cr.set_source_rgba(*look.parchment_edge, 0.5 * wrap_alpha)
        cr.set_line_width(0.8)
        for k in range(1, 4):
            x = cx - r + diameter * k / 4
            cr.move_to(x, top + 3)
            cr.line_to(x, bottom - 3)
            cr.stroke()
    # Knobs.
    knob_r = ROLLER / 2 * 0.62
    for y, direction in ((top, -1), (bottom, 1)):
        rod_h = KNOB
        g = cairo.LinearGradient(cx - knob_r, 0, cx + knob_r, 0)
        g.add_color_stop_rgb(0, *_shade(look.wood, -0.5))
        g.add_color_stop_rgb(0.4, *_shade(look.wood, 0.25))
        g.add_color_stop_rgb(1, *_shade(look.wood, -0.6))
        cr.set_source(g)
        y0 = y if direction > 0 else y - rod_h
        cr.rectangle(cx - knob_r * 0.55, y0, knob_r * 1.1, rod_h)
        cr.fill()
        ky = y + direction * (rod_h + 1)
        g = cairo.RadialGradient(cx - knob_r * 0.3, ky - knob_r * 0.3, 1, cx, ky, knob_r)
        g.add_color_stop_rgb(0, *_shade(look.knob, 0.45))
        g.add_color_stop_rgb(0.6, *look.knob)
        g.add_color_stop_rgb(1, *_shade(look.knob, -0.45))
        cr.set_source(g)
        cr.arc(cx, ky, knob_r, 0, math.tau)
        cr.fill()
        # Gold band where knob meets roller.
        cr.set_source_rgb(0.83, 0.66, 0.26)
        cr.rectangle(cx - r - 1, y - (2 if direction < 0 else 0), diameter + 2, 2)
        cr.fill()


# --- wax seal ----------------------------------------------------------------------------------

def seal_path(cr, cx, cy, r):
    points = 18
    for k in range(points + 1):
        a = math.tau * k / points
        rr = r * (1.0 if k % 2 == 0 else 0.92)
        x, y = cx + rr * math.cos(a), cy + rr * math.sin(a)
        (cr.move_to if k == 0 else cr.line_to)(x, y)
    cr.close_path()


def draw_seal(cr, cx, cy, r, colour, alpha=1.0, broken=False):
    """A wax seal with a flame stamped into it. broken=True draws it cracked open (unsaved)."""
    cr.save()
    cr.push_group()
    cr.set_source_rgba(0, 0, 0, 0.3)
    seal_path(cr, cx + 1.5, cy + 2, r)
    cr.fill()
    g = cairo.RadialGradient(cx - r * 0.35, cy - r * 0.35, r * 0.1, cx, cy, r)
    g.add_color_stop_rgb(0, *_shade(colour, 0.35))
    g.add_color_stop_rgb(0.7, *colour)
    g.add_color_stop_rgb(1, *_shade(colour, -0.35))
    cr.set_source(g)
    seal_path(cr, cx, cy, r)
    cr.fill()
    cr.set_line_width(max(1, r * 0.1))
    cr.set_source_rgb(*_shade(colour, -0.3))
    cr.arc(cx, cy, r * 0.7, 0, math.tau)
    cr.stroke()
    s = r / 8
    cr.move_to(cx, cy - 5 * s)
    cr.curve_to(cx + 4 * s, cy - s, cx + 3.5 * s, cy + 4 * s, cx, cy + 4.5 * s)
    cr.curve_to(cx - 3.5 * s, cy + 4 * s, cx - 4 * s, cy, cx - 1.2 * s, cy - 2 * s)
    cr.curve_to(cx - s, cy, cx, cy + 0.5 * s, cx, cy - 5 * s)
    cr.close_path()
    cr.set_source_rgb(*_shade(colour, -0.4))
    cr.fill()
    if broken:
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.set_line_width(max(1.2, r * 0.12))
        cr.move_to(cx - r * 0.2, cy - r * 1.1)
        cr.line_to(cx + r * 0.1, cy - r * 0.3)
        cr.line_to(cx - r * 0.15, cy + r * 0.2)
        cr.line_to(cx + r * 0.2, cy + r * 1.1)
        cr.stroke()
    cr.pop_group_to_source()
    cr.paint_with_alpha(alpha)
    cr.restore()


# --- whole frame -------------------------------------------------------------------------------

def draw_scroll(cr, width, height, progress, seal_pop=1.0, look=None, show_seal=True):
    look = look or Look()
    if look.opaque_surround:
        cr.set_source_rgb(*look.opaque_surround)
    else:
        cr.set_source_rgba(0, 0, 0, 0)
    cr.set_operator(cairo.OPERATOR_SOURCE)
    cr.paint()
    cr.set_operator(cairo.OPERATOR_OVER)
    x0, x1 = paper_span(width, progress)
    draw_paper(cr, width, height, x0, x1, look)
    diameter = roller_width(progress)
    wound = 1 - progress
    offset = diameter / 2 * (1 - progress)
    draw_roller(cr, x0 - offset, height, diameter, look, wound)
    draw_roller(cr, x1 + offset, height, diameter, look, wound)
    if show_seal and seal_pop < 1:
        # The seal sits across the join of the two rollers and pops up and away as it breaks.
        t = seal_pop
        r = 22 * (1 + 0.5 * t)
        cy = height / 2 - 40 * t
        cr.save()
        cr.translate(width / 2, cy)
        cr.rotate(0.5 * t)
        draw_seal(cr, 0, 0, r, look.seal, alpha=1 - t)
        cr.restore()
