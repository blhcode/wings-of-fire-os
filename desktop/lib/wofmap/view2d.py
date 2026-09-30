"""The flat map: a pannable, zoomable cairo drawing of one continent."""
import math

import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gdk, GdkPixbuf, GLib, GObject, Gtk, Pango, PangoCairo  # noqa: E402

from pyrrhia import colors  # noqa: E402

from . import atlas  # noqa: E402

LAKE_RGB = (38, 104, 140)
MAX_ZOOM = 10.0
RANK_ZOOM = {1: 0.0, 2: 1.7, 3: 3.2}
ANIM_MS = 380


class Palette:
    def __init__(self, style, tribe_colours=None, dark=True):
        t = tribe_colours or {"accent": "#e8541e", "accent_alt": "#f7b733", "background": "#1d1a17",
                              "surface": "#2a2521", "text": "#f3e6c4"}
        self.style = style
        if style == "parchment":
            self.ocean = colors.parse("#eadbb4")
            self.shallow = colors.parse("#e2cc9a")
            self.waves = colors.parse("#b89a5e")
            self.coast = colors.parse("#3b2a1a")
            self.label = colors.parse("#3b2a1a")
            self.halo = colors.parse("#f3e6c4")
            self.river = colors.parse("#4a6b8a")
            self.lake = colors.parse("#c3cdb9")
            self.sepia = colors.parse("#dcc28c")
            self.select = colors.parse("#b3261e")
            self.route = colors.parse("#7a5a2a")
        else:
            base_sea = "#1f4f6e" if dark else "#8fbdd6"
            self.ocean = colors.parse(colors.mix(base_sea, t["background"], 0.3))
            self.shallow = colors.parse(colors.lighten(colors.to_hex(self.ocean), 0.16))
            self.waves = None
            self.coast = colors.parse("#1b140c")
            self.label = colors.parse("#fdf6e3")
            self.halo = colors.parse("#1b140c")
            self.river = colors.parse("#3d8fc4")
            self.lake = None
            self.sepia = None
            self.select = colors.parse(t["accent_alt"] if dark else t["accent"])
            self.route = colors.parse("#fff3d6")


def _surface_from_pixbuf(pixbuf):
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, pixbuf.get_width(), pixbuf.get_height())
    cr = cairo.Context(surface)
    Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)
    cr.paint()
    return surface


class Assets:
    """Rasters for one continent, decoded once."""

    def __init__(self, continent):
        relief = GdkPixbuf.Pixbuf.new_from_file(str(continent.relief_path))
        if not relief.get_has_alpha():
            relief = relief.add_alpha(False, 0, 0, 0)
        self.width, self.height = relief.get_width(), relief.get_height()
        self.relief = _surface_from_pixbuf(relief)
        grey = relief.copy()
        relief.saturate_and_pixelate(grey, 0.0, False)
        self.relief_grey = _surface_from_pixbuf(grey)
        self._px = relief.get_pixels()
        self._stride = relief.get_rowstride()
        self._channels = relief.get_n_channels()
        try:
            hp = GdkPixbuf.Pixbuf.new_from_file(str(continent.height_path))
            self.heights = atlas.HeightField(hp.get_pixels(), hp.get_width(), hp.get_height(),
                                             hp.get_rowstride(), hp.get_n_channels())
        except GLib.Error:
            self.heights = None

    def is_land(self, nx, ny):
        x = int(nx * (self.width - 1) + 0.5)
        y = int((1 - ny) * (self.height - 1) + 0.5)
        if not (0 <= x < self.width and 0 <= y < self.height):
            return False
        i = y * self._stride + x * self._channels
        if self._px[i + 3] < 128:
            return False
        return tuple(self._px[i:i + 3]) != LAKE_RGB


class MapView(Gtk.DrawingArea):
    __gsignals__ = {
        "selected": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        "hover": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self):
        super().__init__()
        self.set_can_focus(True)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK
                        | Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.SCROLL_MASK
                        | Gdk.EventMask.SMOOTH_SCROLL_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.continent = None
        self.assets = None
        self.palette = Palette("tribe")
        self.layers = {"regions": True, "rivers": True, "routes": True, "labels": True}
        self.hidden_groups = set()
        self.selected = None
        self.scale = 1.0
        self.cx = self.cy = 0.0
        self._fitted = False
        self._press = None
        self._dragging = False
        self._measure = None
        self._anim = None
        self._wave_pattern = None

        self.connect("draw", self._draw)
        self.connect("size-allocate", self._on_size)
        self.connect("button-press-event", self._on_press)
        self.connect("button-release-event", self._on_release)
        self.connect("motion-notify-event", self._on_motion)
        self.connect("scroll-event", self._on_scroll)
        self.connect("leave-notify-event", lambda *_: self.emit("hover", ""))

        self._zoom_gesture = Gtk.GestureZoom.new(self)
        self._zoom_gesture.connect("begin", self._pinch_begin)
        self._zoom_gesture.connect("scale-changed", self._pinch_scale)

    # --- public API -----------------------------------------------------------------------

    def set_continent(self, continent, assets):
        self.continent, self.assets = continent, assets
        self.selected = None
        self._measure = None
        self._fitted = False
        if self.get_allocated_width() > 1:
            self.fit(animate=False)
        self.queue_draw()

    def set_palette(self, palette):
        self.palette = palette
        self._wave_pattern = None
        self.queue_draw()

    def set_layer(self, name, on):
        self.layers[name] = on
        self.queue_draw()

    def set_group_visible(self, group_id, on):
        (self.hidden_groups.discard if on else self.hidden_groups.add)(group_id)
        self.queue_draw()

    def select(self, landmark, zoom=True):
        self.selected = landmark
        if landmark is not None and zoom:
            mx, my = self._norm_to_map(*landmark.pos)
            target = max(self.scale, self.fit_scale() * max(2.2, RANK_ZOOM[landmark.rank] + 0.4))
            self.animate_to(mx, my, target)
        self.queue_draw()
        self.emit("selected", landmark)

    def show_point(self, nx, ny, zoom=2.0):
        mx, my = self._norm_to_map(nx, ny)
        self.animate_to(mx, my, max(self.scale, self.fit_scale() * zoom))

    def fit_scale(self):
        if not self.assets:
            return 1.0
        w, h = self.get_allocated_width(), self.get_allocated_height()
        return min(w / self.assets.width, h / self.assets.height) * 0.96

    def fit(self, animate=True):
        if not self.assets:
            return
        target = (self.assets.width / 2, self.assets.height / 2, self.fit_scale())
        if animate:
            self.animate_to(*target)
        else:
            self.cx, self.cy, self.scale = target
            self.queue_draw()
        self._fitted = True

    def zoom_by(self, factor, sx=None, sy=None):
        if not self.assets:
            return
        w, h = self.get_allocated_width(), self.get_allocated_height()
        sx = w / 2 if sx is None else sx
        sy = h / 2 if sy is None else sy
        mx, my = self._screen_to_map(sx, sy)
        new = self._clamp_scale(self.scale * factor)
        self.scale = new
        self.cx = mx - (sx - w / 2) / new
        self.cy = my - (sy - h / 2) / new
        self._clamp_centre()
        self.queue_draw()

    def pan_by(self, dx, dy):
        self.cx -= dx / self.scale
        self.cy -= dy / self.scale
        self._clamp_centre()
        self.queue_draw()

    def animate_to(self, cx, cy, scale):
        scale = self._clamp_scale(scale)
        self._anim = {"from": (self.cx, self.cy, self.scale), "to": (cx, cy, scale),
                      "start": None}
        self.add_tick_callback(self._tick)

    def zoom_level(self):
        return self.scale / self.fit_scale()

    # --- coordinates ----------------------------------------------------------------------

    def _norm_to_map(self, nx, ny):
        return nx * self.assets.width, (1 - ny) * self.assets.height

    def _map_to_norm(self, mx, my):
        return mx / self.assets.width, 1 - my / self.assets.height

    def _map_to_screen(self, mx, my):
        w, h = self.get_allocated_width(), self.get_allocated_height()
        return (mx - self.cx) * self.scale + w / 2, (my - self.cy) * self.scale + h / 2

    def _screen_to_map(self, sx, sy):
        w, h = self.get_allocated_width(), self.get_allocated_height()
        return (sx - w / 2) / self.scale + self.cx, (sy - h / 2) / self.scale + self.cy

    def _norm_to_screen(self, nx, ny):
        return self._map_to_screen(*self._norm_to_map(nx, ny))

    def _clamp_scale(self, s):
        fit = self.fit_scale()
        return min(max(s, fit * 0.8), fit * MAX_ZOOM)

    def _clamp_centre(self):
        if not self.assets:
            return
        self.cx = min(max(self.cx, 0), self.assets.width)
        self.cy = min(max(self.cy, 0), self.assets.height)

    def miles_per_px(self):
        c = self.continent
        return c.world_w_m / atlas.MILES_TO_M / (self.assets.width * self.scale)

    # --- events ---------------------------------------------------------------------------

    def _on_size(self, *_):
        if self.assets and not self._fitted:
            self.fit(animate=False)

    def _tick(self, _widget, clock):
        a = self._anim
        if a is None:
            return GLib.SOURCE_REMOVE
        now = clock.get_frame_time() / 1000
        if a["start"] is None:
            a["start"] = now
        t = min(1.0, (now - a["start"]) / ANIM_MS)
        e = 1 - (1 - t) ** 3
        (x0, y0, s0), (x1, y1, s1) = a["from"], a["to"]
        # Zoom in log space so big scale changes feel even.
        self.scale = math.exp(math.log(s0) + (math.log(s1) - math.log(s0)) * e)
        self.cx = x0 + (x1 - x0) * e
        self.cy = y0 + (y1 - y0) * e
        self.queue_draw()
        if t >= 1:
            self._anim = None
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def _on_press(self, _w, event):
        self.grab_focus()
        if not self.assets:
            return False
        if event.type == Gdk.EventType._2BUTTON_PRESS and event.button == 1:
            self._anim = None
            self.animate_to(*self._screen_to_map(event.x, event.y), self.scale * 2)
            return True
        if event.button == 1:
            self._anim = None
            self._press = (event.x, event.y, self.cx, self.cy)
            self._dragging = False
        elif event.button == 3:
            start = self._screen_to_map(event.x, event.y)
            self._measure = [start, start]
            self.queue_draw()
        return True

    def _on_release(self, _w, event):
        if event.button == 1 and self._press:
            if not self._dragging:
                self._click(event.x, event.y)
            self._press = None
            self._dragging = False
            win = self.get_window()
            if win:
                win.set_cursor(None)
        return True

    def _on_motion(self, _w, event):
        if not self.assets:
            return False
        if self._press and event.state & Gdk.ModifierType.BUTTON1_MASK:
            x0, y0, cx0, cy0 = self._press
            if not self._dragging and math.hypot(event.x - x0, event.y - y0) > 4:
                self._dragging = True
                win = self.get_window()
                if win:
                    win.set_cursor(Gdk.Cursor.new_from_name(self.get_display(), "grabbing"))
            if self._dragging:
                self.cx = cx0 - (event.x - x0) / self.scale
                self.cy = cy0 - (event.y - y0) / self.scale
                self._clamp_centre()
                self.queue_draw()
        if self._measure is not None and event.state & Gdk.ModifierType.BUTTON3_MASK:
            self._measure[1] = self._screen_to_map(event.x, event.y)
            self.queue_draw()
        self.emit("hover", self._describe_point(*self._map_to_norm(*self._screen_to_map(event.x, event.y))))
        return False

    def _on_scroll(self, _w, event):
        if not self.assets:
            return False
        self._anim = None
        if event.direction == Gdk.ScrollDirection.SMOOTH:
            _ok, _dx, dy = event.get_scroll_deltas()
        else:
            dy = {Gdk.ScrollDirection.UP: -1, Gdk.ScrollDirection.DOWN: 1}.get(event.direction, 0)
        if dy:
            self.zoom_by(1.2 ** (-dy), event.x, event.y)
        return True

    def _pinch_begin(self, *_):
        self._pinch_start = self.scale

    def _pinch_scale(self, _g, scale):
        ok, x, y = self._zoom_gesture.get_bounding_box_center()
        target = self._clamp_scale(self._pinch_start * scale)
        self.zoom_by(target / self.scale, x if ok else None, y if ok else None)

    def _click(self, sx, sy):
        best, best_d = None, 16.0
        for m in self._visible_landmarks():
            px, py = self._norm_to_screen(*m.pos)
            d = math.hypot(px - sx, py - sy)
            if d < best_d:
                best, best_d = m, d
        if self._measure is not None:
            self._measure = None
        self.selected = best
        self.queue_draw()
        self.emit("selected", best)

    def _describe_point(self, nx, ny):
        if not (0 <= nx <= 1 and 0 <= ny <= 1):
            return ""
        c = self.continent
        if not self.assets.is_land(nx, ny):
            lake = next((l for l in c.lakes if atlas.point_in_polygon(nx, ny, l["polygon"])), None)
            if lake:
                return lake.get("name") or "Lake"
            return "Open sea"
        parts = []
        region = next((r for r in c.regions
                       if len(r.polygon) >= 3 and atlas.point_in_polygon(nx, ny, r.polygon)), None)
        if region:
            parts.append(region.name)
        if self.assets.heights:
            parts.append(atlas.format_height(self.assets.heights.metres(nx, ny)))
        return "  \u00b7  ".join(parts)

    # --- drawing --------------------------------------------------------------------------

    def _visible_landmarks(self):
        if not self.continent:
            return []
        z = self.zoom_level()
        out = []
        for m in self.continent.landmarks:
            if m.group in self.hidden_groups and m is not self.selected:
                continue
            if z >= RANK_ZOOM.get(m.rank, 3.2) or m is self.selected:
                out.append(m)
        return out

    def _land_path(self, cr):
        cr.new_path()
        for poly in self.continent.land:
            x, y = self._norm_to_map(*poly[0])
            cr.move_to(x, y)
            for p in poly[1:]:
                cr.line_to(*self._norm_to_map(*p))
            cr.close_path()

    def _poly_path(self, cr, poly, close=True):
        x, y = self._norm_to_map(*poly[0])
        cr.move_to(x, y)
        for p in poly[1:]:
            cr.line_to(*self._norm_to_map(*p))
        if close:
            cr.close_path()

    def _waves(self):
        if self._wave_pattern is None:
            tile = cairo.ImageSurface(cairo.FORMAT_ARGB32, 64, 28)
            t = cairo.Context(tile)
            t.set_source_rgba(*self.palette.waves, 0.45)
            t.set_line_width(1)
            for ox, oy in ((6, 8), (38, 22)):
                t.move_to(ox, oy)
                t.curve_to(ox + 4, oy - 4, ox + 8, oy - 4, ox + 12, oy)
                t.curve_to(ox + 16, oy - 4, ox + 20, oy - 4, ox + 24, oy)
            t.stroke()
            self._wave_pattern = cairo.SurfacePattern(tile)
            self._wave_pattern.set_extend(cairo.EXTEND_REPEAT)
        return self._wave_pattern

    def _draw(self, _w, cr):
        pal = self.palette
        w, h = self.get_allocated_width(), self.get_allocated_height()
        cr.set_source_rgb(*pal.ocean)
        cr.paint()
        if not self.assets:
            return
        if pal.waves:
            cr.set_source(self._waves())
            cr.paint()

        s = self.scale
        cr.save()
        cr.translate(w / 2, h / 2)
        cr.scale(s, s)
        cr.translate(-self.cx, -self.cy)

        self._land_path(cr)
        cr.set_source_rgba(*pal.shallow, 0.9)
        cr.set_line_width(14 / s)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.stroke()

        moving = self._dragging or self._anim is not None
        if pal.style == "parchment":
            cr.set_source_surface(self.assets.relief_grey, 0, 0)
            cr.get_source().set_filter(cairo.FILTER_FAST if moving else cairo.FILTER_GOOD)
            cr.paint()
            cr.set_operator(cairo.OPERATOR_MULTIPLY)
            cr.set_source_rgb(*pal.sepia)
            cr.mask_surface(self.assets.relief, 0, 0)
            cr.set_operator(cairo.OPERATOR_OVER)
        else:
            cr.set_source_surface(self.assets.relief, 0, 0)
            cr.get_source().set_filter(cairo.FILTER_FAST if moving else cairo.FILTER_GOOD)
            cr.paint()

        c = self.continent
        if self.layers["regions"] and c.regions:
            cr.save()
            self._land_path(cr)
            cr.clip()
            for r in c.regions:
                if len(r.polygon) < 3:
                    continue
                cr.new_path()
                self._poly_path(cr, r.polygon)
                cr.set_source_rgba(*colors.parse(r.colour), 0.16 if pal.style != "parchment" else 0.22)
                cr.fill_preserve()
                cr.set_source_rgba(*colors.parse(r.colour), 0.55)
                cr.set_line_width(1.4 / s)
                cr.set_dash([6 / s, 4 / s])
                cr.stroke()
            cr.set_dash([])
            cr.restore()

        for lake in c.lakes:
            cr.new_path()
            self._poly_path(cr, lake["polygon"])
            if pal.lake:
                cr.set_source_rgb(*pal.lake)
                cr.fill_preserve()
            cr.set_source_rgba(*pal.coast, 0.7)
            cr.set_line_width(1.0 / s)
            cr.stroke()

        self._land_path(cr)
        cr.set_source_rgba(*pal.coast, 0.85)
        cr.set_line_width(1.2 / s)
        cr.stroke()

        if self.layers["rivers"]:
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            cr.set_line_join(cairo.LINE_JOIN_ROUND)
            for river in c.rivers:
                width = max(1.1, river.get("half_width", 0.0015) * 2 * self.assets.width * s)
                cr.set_source_rgb(*pal.river)
                cr.set_line_width(min(width, 5) / s)
                for branch in river["branches"]:
                    if len(branch) > 1:
                        cr.new_path()
                        self._poly_path(cr, branch, close=False)
                        cr.stroke()

        if self.layers["routes"]:
            for route in c.routes:
                for a, b in route["segments"]:
                    cr.new_path()
                    self._poly_path(cr, [a, b], close=False)
                    cr.set_source_rgba(*pal.coast, 0.6)
                    cr.set_line_width(3.2 / s)
                    cr.stroke_preserve()
                    cr.set_source_rgb(*pal.route)
                    cr.set_line_width(1.6 / s)
                    cr.set_dash([5 / s, 3 / s])
                    cr.stroke()
                    cr.set_dash([])
        cr.restore()

        self._draw_markers(cr)
        if self.layers["labels"]:
            self._draw_labels(cr, w, h)
        self._draw_measure(cr)
        self._draw_scale(cr, w, h)
        self._draw_compass(cr, w)

    def _draw_markers(self, cr):
        pal = self.palette
        groups = {g["id"]: g["color"] for g in self.continent.groups}
        for m in self._visible_landmarks():
            x, y = self._norm_to_screen(*m.pos)
            r = 6 if m.rank == 1 else 4.5
            if m is self.selected:
                cr.arc(x, y, r + 6, 0, 2 * math.pi)
                cr.set_source_rgba(*pal.select, 0.35)
                cr.fill()
            cr.arc(x, y, r, 0, 2 * math.pi)
            cr.set_source_rgb(*colors.parse(groups.get(m.group, "#ffffff")))
            cr.fill_preserve()
            cr.set_source_rgb(*(pal.select if m is self.selected else pal.coast))
            cr.set_line_width(2 if m is self.selected else 1.4)
            cr.stroke()

    def _layout(self, cr, text, size, weight="normal", italic=False, spacing=0, caps=False):
        layout = PangoCairo.create_layout(cr)
        style = "italic" if italic else "normal"
        esc = GLib.markup_escape_text(text.upper() if caps else text)
        layout.set_markup(f'<span font_family="EB Garamond" size="{int(size * Pango.SCALE)}" '
                          f'weight="{weight}" style="{style}" letter_spacing="{int(spacing * 1024)}">'
                          f'{esc}</span>', -1)
        return layout

    def _text(self, cr, layout, x, y, fg, halo, angle=0.0):
        cr.save()
        cr.translate(x, y)
        if angle:
            cr.rotate(angle)
        PangoCairo.layout_path(cr, layout)
        cr.set_source_rgba(*halo, 0.85)
        cr.set_line_width(3.2)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.stroke_preserve()
        cr.set_source_rgb(*fg)
        cr.fill()
        cr.restore()

    def _draw_labels(self, cr, w, h):
        pal = self.palette
        placed = []

        def free(rect):
            x0, y0, x1, y1 = rect
            if x1 < 0 or y1 < 0 or x0 > w or y0 > h:
                return False
            return all(x1 < a or x0 > c or y1 < b or y0 > d for a, b, c, d in placed)

        z = self.zoom_level()
        c = self.continent

        ordered = sorted(self._visible_landmarks(),
                         key=lambda m: (m is not self.selected, m.rank, m.name))
        # Selected label first, then regions, so kingdoms keep their names at low zoom.
        queue = ordered[:1] if ordered and ordered[0] is self.selected else []
        rest = ordered[len(queue):]

        def place_landmark(m):
            x, y = self._norm_to_screen(*m.pos)
            size = 13.5 if m.rank == 1 else 12 if m.rank == 2 else 11
            layout = self._layout(cr, m.name, size, weight="bold" if m.rank == 1 else "600")
            lw, lh = [v / Pango.SCALE for v in layout.get_size()]
            for ox, oy in ((9, -lh / 2), (-9 - lw, -lh / 2), (-lw / 2, -lh - 8), (-lw / 2, 8)):
                rect = (x + ox - 2, y + oy, x + ox + lw + 2, y + oy + lh)
                if free(rect) or m is self.selected:
                    placed.append(rect)
                    fg = pal.select if m is self.selected else pal.label
                    self._text(cr, layout, x + ox, y + oy, fg, pal.halo)
                    return

        for m in queue:
            place_landmark(m)

        if self.layers["regions"] and z < 4.5:
            alpha = 1.0 if z < 3 else max(0.0, (4.5 - z) / 1.5)
            size = min(26, 13 + 5 * z)
            for r in c.regions:
                if not r.anchor:
                    continue
                x, y = self._norm_to_screen(*r.anchor)
                layout = self._layout(cr, r.name, size, weight="bold", spacing=size * 0.18, caps=True)
                lw, lh = [v / Pango.SCALE for v in layout.get_size()]
                rect = (x - lw / 2, y - lh / 2, x + lw / 2, y + lh / 2)
                if not free(rect):
                    continue
                placed.append(rect)
                region_col = colors.parse(r.colour)
                if pal.style == "parchment":
                    fg = colors.parse(colors.darken(r.colour, 0.55))
                else:
                    fg = colors.parse(colors.lighten(r.colour, 0.25))
                fg = tuple(a * alpha + b * (1 - alpha) for a, b in zip(fg, region_col))
                cr.push_group()
                self._text(cr, layout, x - lw / 2, y - lh / 2, fg, pal.halo)
                cr.pop_group_to_source()
                cr.paint_with_alpha(alpha * 0.92)

        for m in rest:
            place_landmark(m)

        if self.layers["rivers"] and z >= 1.4:
            for river in c.rivers:
                name = river.get("name")
                if not name or not river["branches"]:
                    continue
                branch = max(river["branches"], key=len)
                pts = [self._norm_to_screen(*p) for p in branch]
                if len(pts) < 2:
                    continue
                lengths = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]
                total, acc = sum(lengths), 0.0
                for i, seg in enumerate(lengths):
                    if acc + seg >= total / 2:
                        break
                    acc += seg
                (ax, ay), (bx, by) = pts[i], pts[i + 1]
                angle = math.atan2(by - ay, bx - ax)
                if angle > math.pi / 2:
                    angle -= math.pi
                elif angle < -math.pi / 2:
                    angle += math.pi
                layout = self._layout(cr, name, 11.5, italic=True, spacing=0.5)
                lw, lh = [v / Pango.SCALE for v in layout.get_size()]
                mx, my = (ax + bx) / 2, (ay + by) / 2
                rect = (mx - lw / 2, my - lh / 2, mx + lw / 2, my + lh / 2)
                if not free(rect):
                    continue
                placed.append(rect)
                cr.save()
                cr.translate(mx, my)
                cr.rotate(angle)
                self._text(cr, layout, -lw / 2, -lh - 2, pal.river if pal.style == "parchment" else pal.label,
                           pal.halo)
                cr.restore()

    def _draw_measure(self, cr):
        if not self._measure:
            return
        (ax, ay), (bx, by) = self._measure
        if math.hypot(bx - ax, by - ay) * self.scale < 4:
            return
        pal = self.palette
        sa, sb = self._map_to_screen(ax, ay), self._map_to_screen(bx, by)
        cr.move_to(*sa)
        cr.line_to(*sb)
        cr.set_source_rgba(*pal.halo, 0.8)
        cr.set_line_width(4)
        cr.stroke_preserve()
        cr.set_source_rgb(*pal.select)
        cr.set_line_width(2)
        cr.set_dash([7, 4])
        cr.stroke()
        cr.set_dash([])
        for p in (sa, sb):
            cr.arc(*p, 4, 0, 2 * math.pi)
            cr.fill()
        miles = self.continent.distance_miles(self._map_to_norm(ax, ay), self._map_to_norm(bx, by))
        text = f"{atlas.format_miles(miles)}  \u00b7  {atlas.flight_time(miles)}"
        layout = self._layout(cr, text, 13, weight="bold")
        self._text(cr, layout, sb[0] + 10, sb[1] + 6, pal.label, pal.halo)

    def _draw_scale(self, cr, w, h):
        pal = self.palette
        miles, length = atlas.nice_scale(self.miles_per_px())
        x, y = 18, h - 26
        cr.rectangle(x - 1, y - 1, length + 2, 8)
        cr.set_source_rgba(*pal.halo, 0.7)
        cr.fill()
        for i in range(4):
            cr.rectangle(x + i * length / 4, y, length / 4, 6)
            cr.set_source_rgb(*(pal.label if i % 2 == 0 else pal.halo))
            cr.fill()
        label = f"{miles:,g} miles"
        layout = self._layout(cr, label, 11, weight="bold")
        self._text(cr, layout, x, y - 20, pal.label, pal.halo)

    def _draw_compass(self, cr, w):
        pal = self.palette
        x, y, r = w - 34, 38, 16
        cr.move_to(x, y - r)
        cr.line_to(x + r * 0.38, y)
        cr.line_to(x, y + r * 0.35)
        cr.line_to(x - r * 0.38, y)
        cr.close_path()
        cr.set_source_rgba(*pal.halo, 0.8)
        cr.set_line_width(3)
        cr.stroke_preserve()
        cr.set_source_rgb(*pal.select)
        cr.fill()
        layout = self._layout(cr, "N", 12, weight="bold")
        lw = layout.get_size()[0] / Pango.SCALE
        self._text(cr, layout, x - lw / 2, y + r * 0.45, pal.label, pal.halo)
