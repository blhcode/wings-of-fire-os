"""Scroll: the Wings of Fire OS text editor. A real plain-text/code editor drawn as a parchment scroll
that unrolls when it opens and rolls back up when it closes."""
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GtkSource", "4")
from gi.repository import Gdk, Gio, GLib, GObject, Gtk, GtkSource, Pango  # noqa: E402

from pyrrhia import colors, state as state_mod, tribes  # noqa: E402
from . import drawing, prefs as prefs_mod  # noqa: E402

APP_ID = "org.wingsoffire.Scroll"
INK = "#3b2a1a"
EDGES = {
    "n": Gdk.WindowEdge.NORTH, "s": Gdk.WindowEdge.SOUTH, "e": Gdk.WindowEdge.EAST, "w": Gdk.WindowEdge.WEST,
    "ne": Gdk.WindowEdge.NORTH_EAST, "nw": Gdk.WindowEdge.NORTH_WEST,
    "se": Gdk.WindowEdge.SOUTH_EAST, "sw": Gdk.WindowEdge.SOUTH_WEST,
}
CURSORS = {"n": "n-resize", "s": "s-resize", "e": "e-resize", "w": "w-resize", "ne": "ne-resize",
           "nw": "nw-resize", "se": "se-resize", "sw": "sw-resize"}

CSS = f"""
.wof-scroll-window, .wof-scroll-window > overlay {{ background-color: transparent; }}
.wof-scroll-content, .wof-scroll-content label {{ color: {INK}; }}
.wof-scroll-content textview, .wof-scroll-content textview text,
.wof-scroll-content scrolledwindow, .wof-scroll-content viewport {{ background-color: transparent; }}
.wof-scroll-content textview border {{ background-color: transparent; }}
.wof-scroll-content scrolledwindow undershoot, .wof-scroll-content scrolledwindow overshoot {{ background: none; }}
.wof-scroll-content scrollbar {{ background-color: transparent; border: none; }}
.wof-scroll-content scrollbar slider {{ background-color: {colors.rgba(INK, 0.35)}; min-width: 6px; }}
.wof-scroll-toolbar {{ border-bottom: 1px solid {colors.rgba(INK, 0.25)}; padding-bottom: 4px; }}
.wof-scroll-content button {{
    background-image: none; background-color: transparent; border: 1px solid transparent; box-shadow: none;
    color: {INK}; -gtk-icon-shadow: none; text-shadow: none; min-height: 26px; min-width: 26px; padding: 3px;
}}
.wof-scroll-content button:hover {{ background-color: {colors.rgba(INK, 0.1)}; border-color: {colors.rgba(INK, 0.2)}; }}
.wof-scroll-content button:active, .wof-scroll-content button:checked {{ background-color: {colors.rgba(INK, 0.18)}; }}
.wof-scroll-content button:disabled {{ color: {colors.rgba(INK, 0.35)}; }}
.wof-scroll-title {{ font-family: "EB Garamond", serif; font-size: 17px; font-weight: bold; }}
.wof-scroll-status {{ font-size: 11px; color: {colors.rgba(INK, 0.7)}; border-top: 1px solid {colors.rgba(INK, 0.2)}; padding-top: 3px; }}
.wof-scroll-content entry {{
    background-image: none; background-color: {colors.rgba("#ffffff", 0.45)}; color: {INK};
    border: 1px solid {colors.rgba(INK, 0.3)}; box-shadow: none; caret-color: {INK};
}}
.wof-scroll-content entry.error {{ border-color: #b83227; }}
.wof-scroll-content checkbutton check {{ background-image: none; background-color: {colors.rgba("#ffffff", 0.5)};
    border-color: {colors.rgba(INK, 0.4)}; color: {INK}; }}
.wof-scroll-search {{ padding: 4px 0; border-bottom: 1px solid {colors.rgba(INK, 0.2)}; }}
"""


def _css(text, widget=None, priority=Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 20):
    provider = Gtk.CssProvider()
    provider.load_from_data(text.encode())
    if widget is None:
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, priority)
    else:
        widget.get_style_context().add_provider(provider, priority)
    return provider


def tribe_look():
    """The current tribe's colours for the rollers and seal, plus its parchment style scheme id."""
    try:
        tribe = tribes.get(state_mod.load().tribe)
    except tribes.TribeError:
        return drawing.Look(), "classic", None
    accent = tribe.colors["accent"]
    look = drawing.Look(
        knob=colors.parse(accent),
        seal=colors.parse(tribe.editor["seal"]),
        wood=colors.parse(colors.mix("#5a3417", accent, 0.12)),
    )
    return look, f"wof-parchment-{tribe.id}", tribe


class Animation:
    """Runs frame(ms) on every frame for `duration` ms, then done()."""

    def __init__(self, widget, duration, frame, done=None):
        self.widget, self.duration, self.frame, self.done = widget, duration, frame, done
        self.start = None
        self.id = widget.add_tick_callback(self._tick)

    def _tick(self, _widget, clock):
        now = clock.get_frame_time() / 1000
        if self.start is None:
            self.start = now
        ms = now - self.start
        self.frame(min(ms, self.duration))
        if ms >= self.duration:
            if self.done:
                self.done()
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def cancel(self):
        self.widget.remove_tick_callback(self.id)


class SealIndicator(Gtk.DrawingArea):
    """A small wax seal in the toolbar: whole when the file is saved, cracked when it has changes."""

    def __init__(self):
        super().__init__()
        self.set_size_request(30, 30)
        self.colour = drawing.Look().seal
        self.broken = False
        self.scale = 1.0
        self.connect("draw", self._draw)

    def _draw(self, _w, cr):
        w, h = self.get_allocated_width(), self.get_allocated_height()
        drawing.draw_seal(cr, w / 2, h / 2, 11 * self.scale, self.colour, broken=self.broken)

    def set_state(self, broken):
        self.broken = broken
        self.set_tooltip_text("Unsaved changes" if broken else "Sealed (saved)")
        self.queue_draw()

    def stamp(self, animate=True):
        self.set_state(False)
        if not animate:
            return

        def frame(ms):
            t = ms / 260
            self.scale = 1 + 0.5 * (1 - drawing.ease_out_cubic(t))
            self.queue_draw()
        Animation(self, 260, frame)


class ScrollWindow(Gtk.ApplicationWindow):
    def __init__(self, app, path=None):
        super().__init__(application=app, title="Scroll")
        self.app = app
        self.prefs = app.prefs
        self.set_icon_name("wof-scroll")
        self.set_decorated(False)
        self.set_app_paintable(True)
        self.get_style_context().add_class("wof-scroll-window")
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        self.composited = bool(visual) and screen.is_composited()
        if self.composited:
            self.set_visual(visual)
        self.set_default_size(self.prefs.width, self.prefs.height)
        self.look, self.scheme_id, self.tribe = tribe_look()
        if not self.composited:
            self.look.opaque_surround = self._surround_colour()

        self.progress = 0.0 if app.animate else 1.0
        self.seal_pop = 0.0 if app.animate else 1.0
        self.closing = False
        self.close_ok = False
        self.animation = None

        overlay = Gtk.Overlay()
        self.add(overlay)
        self.paper = Gtk.DrawingArea()
        self.paper.add_events(Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.BUTTON_PRESS_MASK)
        self.paper.connect("draw", self._draw_paper)
        self.paper.connect("motion-notify-event", self._paper_motion)
        self.paper.connect("button-press-event", self._paper_press)
        overlay.add(self.paper)

        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.content.get_style_context().add_class("wof-scroll-content")
        left, top, right, bottom = drawing.content_margins(0, 0)
        self.content.set_margin_start(left)
        self.content.set_margin_end(right)
        self.content.set_margin_top(top)
        self.content.set_margin_bottom(bottom)
        overlay.add_overlay(self.content)

        self._build_toolbar()
        self._build_search()
        self._build_editor()
        self._build_status()
        self._build_actions()
        self.content.set_opacity(1.0 if not app.animate else 0.0)

        self.file = GtkSource.File()
        self.connect("delete-event", self._on_delete)
        self.connect("map-event", self._on_map)
        self.connect("configure-event", self._on_configure)
        self._apply_prefs()
        self._update_title()
        if path:
            self.load(Gio.File.new_for_path(str(path)))

    # --- construction ----------------------------------------------------------------------------

    def _button(self, icon, tooltip, action=None, callback=None):
        button = Gtk.Button.new_from_icon_name(icon, Gtk.IconSize.SMALL_TOOLBAR)
        button.set_tooltip_text(tooltip)
        button.set_relief(Gtk.ReliefStyle.NONE)
        button.set_can_focus(False)
        if action:
            button.set_action_name(action)
        if callback:
            button.connect("clicked", callback)
        return button

    def _build_toolbar(self):
        bar = Gtk.Box(spacing=2)
        bar.get_style_context().add_class("wof-scroll-toolbar")
        events = Gtk.EventBox()
        events.add(bar)
        events.connect("button-press-event", self._toolbar_press)
        self.content.pack_start(events, False, False, 0)

        bar.pack_start(self._button("document-new-symbolic", "New scroll (Ctrl+N)", "win.new"), False, False, 0)
        bar.pack_start(self._button("document-open-symbolic", "Open (Ctrl+O)", "win.open"), False, False, 0)
        recent = Gtk.MenuButton()
        recent.set_tooltip_text("Recent scrolls")
        recent.set_relief(Gtk.ReliefStyle.NONE)
        recent.set_can_focus(False)
        recent.add(Gtk.Image.new_from_icon_name("pan-down-symbolic", Gtk.IconSize.MENU))
        menu = Gtk.RecentChooserMenu(show_not_found=False, limit=12, sort_type=Gtk.RecentSortType.MRU)
        text_filter = Gtk.RecentFilter()
        text_filter.add_mime_type("text/*")
        text_filter.add_mime_type("application/json")
        text_filter.add_mime_type("application/x-shellscript")
        menu.add_filter(text_filter)
        menu.connect("item-activated", lambda m: self.app.open_uri(m.get_current_uri(), self))
        recent.set_popup(menu)
        bar.pack_start(recent, False, False, 0)
        bar.pack_start(self._button("document-save-symbolic", "Save (Ctrl+S)", "win.save"), False, False, 0)
        bar.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL, margin=4), False, False, 0)
        bar.pack_start(self._button("edit-undo-symbolic", "Undo (Ctrl+Z)", "win.undo"), False, False, 0)
        bar.pack_start(self._button("edit-redo-symbolic", "Redo (Ctrl+Shift+Z)", "win.redo"), False, False, 0)
        bar.pack_start(self._button("edit-find-symbolic", "Search (Ctrl+F)", "win.find"), False, False, 0)

        self.title_label = Gtk.Label(ellipsize=Pango.EllipsizeMode.MIDDLE)
        self.title_label.get_style_context().add_class("wof-scroll-title")
        bar.set_center_widget(self.title_label)

        bar.pack_end(self._button("window-close-symbolic", "Close (Ctrl+W)", "win.close"), False, False, 0)
        bar.pack_end(self._button("window-maximize-symbolic", "Maximise", callback=self._toggle_max), False, False, 0)
        bar.pack_end(self._button("window-minimize-symbolic", "Minimise", callback=lambda _b: self.iconify()),
                     False, False, 0)
        settings = Gtk.MenuButton()
        settings.set_tooltip_text("Settings")
        settings.set_relief(Gtk.ReliefStyle.NONE)
        settings.set_can_focus(False)
        settings.add(Gtk.Image.new_from_icon_name("emblem-system-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
        settings.set_popover(self._settings_popover(settings))
        bar.pack_end(settings, False, False, 0)
        self.seal = SealIndicator()
        bar.pack_end(self.seal, False, False, 4)

    def _settings_popover(self, relative):
        pop = Gtk.Popover(relative_to=relative)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin=12)
        pop.add(box)
        font_row = Gtk.Box(spacing=8)
        font_row.pack_start(Gtk.Label(label="Font"), False, False, 0)
        self.font_button = Gtk.FontButton(font=self.prefs.font, use_font=True)
        self.font_button.connect("font-set", lambda b: self._set_pref("font", b.get_font()))
        font_row.pack_end(self.font_button, False, False, 0)
        box.pack_start(font_row, False, False, 0)
        self.pref_checks = {}
        for key, label in (("wrap", "Wrap long lines"), ("line_numbers", "Line numbers"),
                           ("highlight_line", "Highlight current line"),
                           ("animations", "Unroll and roll-up animations"), ("seal", "Wax seal")):
            check = Gtk.CheckButton(label=label, active=getattr(self.prefs, key))
            check.connect("toggled", lambda c, k=key: self._set_pref(k, c.get_active()))
            self.pref_checks[key] = check
            box.pack_start(check, False, False, 0)
        zoom = Gtk.Box(spacing=4)
        zoom.pack_start(Gtk.Label(label="Zoom"), False, False, 0)
        self.zoom_label = Gtk.Label()
        for icon, action in (("zoom-in-symbolic", "win.zoom-in"), ("zoom-original-symbolic", "win.zoom-reset"),
                             ("zoom-out-symbolic", "win.zoom-out")):
            zoom.pack_end(Gtk.Button.new_from_icon_name(icon, Gtk.IconSize.MENU), False, False, 0)
            zoom.get_children()[-1].set_action_name(action)
        zoom.pack_end(self.zoom_label, False, False, 6)
        box.pack_start(zoom, False, False, 0)
        box.show_all()
        return pop

    def _build_search(self):
        self.search_settings = GtkSource.SearchSettings(wrap_around=True)
        self.search_revealer = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN)
        grid = Gtk.Grid(column_spacing=4, row_spacing=4)
        grid.get_style_context().add_class("wof-scroll-search")
        self.search_entry = Gtk.SearchEntry(placeholder_text="Search the scroll…", hexpand=True)
        self.search_entry.connect("search-changed", self._search_changed)
        self.search_entry.connect("activate", lambda _e: self.find(forward=True))
        self.search_entry.connect("key-press-event", self._search_key)
        self.search_count = Gtk.Label(width_chars=10)
        grid.attach(self.search_entry, 0, 0, 1, 1)
        grid.attach(self.search_count, 1, 0, 1, 1)
        grid.attach(self._button("go-up-symbolic", "Previous (Ctrl+Shift+G)", "win.find-prev"), 2, 0, 1, 1)
        grid.attach(self._button("go-down-symbolic", "Next (Ctrl+G)", "win.find-next"), 3, 0, 1, 1)
        case = Gtk.CheckButton(label="Match case")
        case.connect("toggled", lambda c: self.search_settings.set_case_sensitive(c.get_active()))
        grid.attach(case, 4, 0, 1, 1)
        grid.attach(self._button("window-close-symbolic", "Close search (Esc)", callback=lambda _b: self.hide_search()),
                    5, 0, 1, 1)
        self.replace_entry = Gtk.Entry(placeholder_text="Replace with…", hexpand=True)
        self.replace_entry.connect("activate", lambda _e: self.replace_one())
        self.replace_entry.connect("key-press-event", self._search_key)
        self.replace_row = [self.replace_entry]
        grid.attach(self.replace_entry, 0, 1, 1, 1)
        replace = Gtk.Button(label="Replace")
        replace.connect("clicked", lambda _b: self.replace_one())
        replace_all = Gtk.Button(label="Replace all")
        replace_all.connect("clicked", lambda _b: self.replace_all())
        grid.attach(replace, 1, 1, 1, 1)
        grid.attach(replace_all, 2, 1, 3, 1)
        self.replace_row += [replace, replace_all]
        self.search_revealer.add(grid)
        self.content.pack_start(self.search_revealer, False, False, 0)

    def _build_editor(self):
        self.buffer = GtkSource.Buffer()
        self.buffer.connect("modified-changed", lambda _b: self._update_title())
        self.buffer.connect("notify::cursor-position", lambda *_a: self._update_status())
        self.view = GtkSource.View(buffer=self.buffer, auto_indent=True, tab_width=4,
                                   smart_home_end=GtkSource.SmartHomeEndType.BEFORE,
                                   left_margin=6, right_margin=6, top_margin=6, bottom_margin=40,
                                   pixels_below_lines=2)
        self.view.set_background_pattern(GtkSource.BackgroundPatternType.NONE)
        self.search = GtkSource.SearchContext(buffer=self.buffer, settings=self.search_settings)
        self.search.connect("notify::occurrences-count", lambda *_a: self._update_search_count())
        scroller = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.add(self.view)
        self.content.pack_start(scroller, True, True, 0)
        self.font_provider = Gtk.CssProvider()
        self.view.get_style_context().add_provider(self.font_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 30)
        self._apply_scheme()

    def _build_status(self):
        bar = Gtk.Box(spacing=12)
        bar.get_style_context().add_class("wof-scroll-status")
        self.status_msg = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END)
        self.status_pos = Gtk.Label()
        self.status_lang = Gtk.Label()
        bar.pack_start(self.status_msg, True, True, 0)
        bar.pack_end(self.status_pos, False, False, 0)
        bar.pack_end(self.status_lang, False, False, 0)
        self.content.pack_end(bar, False, False, 0)

    def _build_actions(self):
        simple = {
            "new": lambda: self.app.new_window(self), "open": self.open_dialog, "save": self.save,
            "save-as": self.save_as, "close": self.close_scroll, "undo": self.undo, "redo": self.redo,
            "find": lambda: self.show_search(False), "replace": lambda: self.show_search(True),
            "find-next": lambda: self.find(True), "find-prev": lambda: self.find(False),
            "zoom-in": lambda: self.zoom(10), "zoom-out": lambda: self.zoom(-10), "zoom-reset": lambda: self.zoom(0),
            "fullscreen": self._toggle_fullscreen,
        }
        self.actions = {}
        for name, callback in simple.items():
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda _a, _p, cb=callback: cb())
            self.add_action(action)
            self.actions[name] = action
        self.buffer.bind_property("can-undo", self.actions["undo"], "enabled", GObject.BindingFlags.SYNC_CREATE)
        self.buffer.bind_property("can-redo", self.actions["redo"], "enabled", GObject.BindingFlags.SYNC_CREATE)

    # --- look ------------------------------------------------------------------------------------

    def _surround_colour(self):
        if self.tribe:
            return colors.parse(self.tribe.colors["background"])
        return (0.1, 0.07, 0.05)

    def _apply_scheme(self):
        manager = GtkSource.StyleSchemeManager.get_default()
        scheme = manager.get_scheme(self.scheme_id) or manager.get_scheme("classic")
        self.buffer.set_style_scheme(scheme)

    def reload_tribe(self):
        self.look, self.scheme_id, self.tribe = tribe_look()
        if not self.composited:
            self.look.opaque_surround = self._surround_colour()
        self.seal.colour = self.look.seal
        self._apply_scheme()
        self.paper.queue_draw()
        self.seal.queue_draw()

    def _apply_prefs(self):
        p = self.prefs
        self.view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR if p.wrap else Gtk.WrapMode.NONE)
        self.view.set_show_line_numbers(p.line_numbers)
        self.view.set_highlight_current_line(p.highlight_line)
        self.buffer.set_highlight_matching_brackets(True)
        desc = Pango.FontDescription.from_string(p.font)
        size = (desc.get_size() / Pango.SCALE or 14) * p.zoom / 100
        family = desc.get_family() or "EB Garamond"
        weight = int(desc.get_weight())
        style = "italic" if desc.get_style() == Pango.Style.ITALIC else "normal"
        self.font_provider.load_from_data(
            f'textview {{ font-family: "{family}"; font-size: {size:.1f}pt; font-weight: {weight}; '
            f'font-style: {style}; }}'.encode())
        self.seal.set_visible(p.seal)
        self.seal.colour = self.look.seal
        self.zoom_label.set_text(f"{p.zoom}%")

    def _set_pref(self, key, value):
        setattr(self.prefs, key, value)
        prefs_mod.save(self.prefs)
        for window in self.app.get_windows():
            if isinstance(window, ScrollWindow):
                window._apply_prefs()

    # --- drawing and animation -------------------------------------------------------------------

    def _draw_paper(self, widget, cr):
        drawing.draw_scroll(cr, widget.get_allocated_width(), widget.get_allocated_height(),
                            self.progress, self.seal_pop, self.look, show_seal=self.prefs.seal)
        return False

    def set_frame(self, progress, seal_pop, content_alpha):
        self.progress, self.seal_pop = progress, seal_pop
        self.content.set_opacity(content_alpha)
        self.content.set_visible(content_alpha > 0.001)
        self.paper.queue_draw()

    def set_progress(self, fraction):
        """Freeze the opening animation at `fraction` (0..1) - used for previews."""
        self.set_frame(*drawing.open_frame(fraction * drawing.OPEN_MS))

    def _animations_on(self):
        return self.app.animate and self.prefs.animations and self.composited

    def _on_map(self, *_args):
        if self._animations_on() and self.progress < 1:
            self.set_frame(*drawing.open_frame(0))
            self.animation = Animation(self, drawing.OPEN_MS, lambda ms: self.set_frame(*drawing.open_frame(ms)),
                                       self._opened)
        else:
            self.set_frame(1.0, 1.0, 1.0)
            self._opened()
        return False

    def _opened(self):
        self.animation = None
        self.view.grab_focus()

    def _roll_up_and_close(self):
        self.closing = True
        self._save_size()
        if self.animation:
            self.animation.cancel()
        if not self._animations_on():
            self._finish_close()
            return
        self.animation = Animation(self, drawing.CLOSE_MS, lambda ms: self.set_frame(*drawing.close_frame(ms)),
                                   self._finish_close)

    def _finish_close(self):
        self.close_ok = True
        self.destroy()

    # --- window moving and resizing --------------------------------------------------------------

    def _toolbar_press(self, _widget, event):
        if event.button != 1:
            return False
        if event.type == Gdk.EventType._2BUTTON_PRESS:
            self._toggle_max()
        else:
            self.begin_move_drag(event.button, int(event.x_root), int(event.y_root), event.time)
        return True

    def _paper_motion(self, widget, event):
        edge = drawing.hit_edge(widget.get_allocated_width(), widget.get_allocated_height(), event.x, event.y)
        window = widget.get_window()
        cursor = Gdk.Cursor.new_from_name(widget.get_display(), CURSORS[edge]) if edge else None
        window.set_cursor(cursor)
        return False

    def _paper_press(self, widget, event):
        edge = drawing.hit_edge(widget.get_allocated_width(), widget.get_allocated_height(), event.x, event.y)
        if event.button == 1 and edge and not self.is_maximized():
            self.begin_resize_drag(EDGES[edge], event.button, int(event.x_root), int(event.y_root), event.time)
            return True
        if event.button == 1:
            self.begin_move_drag(event.button, int(event.x_root), int(event.y_root), event.time)
            return True
        return False

    def _toggle_max(self, *_args):
        self.unmaximize() if self.is_maximized() else self.maximize()

    def _toggle_fullscreen(self):
        state = self.get_window().get_state() if self.get_window() else 0
        self.unfullscreen() if state & Gdk.WindowState.FULLSCREEN else self.fullscreen()

    def _on_configure(self, *_args):
        return False

    def _save_size(self):
        if not self.is_maximized():
            width, height = self.get_size()
            self.prefs.width, self.prefs.height = width, height
            prefs_mod.save(self.prefs)

    # --- files -----------------------------------------------------------------------------------

    def display_name(self):
        location = self.file.get_location()
        return location.get_basename() if location else "Untitled scroll"

    def is_blank(self):
        return self.file.get_location() is None and not self.buffer.get_modified() and self.buffer.get_char_count() == 0

    def _update_title(self):
        modified = self.buffer.get_modified()
        name = self.display_name()
        self.title_label.set_text(("• " if modified else "") + name)
        self.set_title(f"{'*' if modified else ''}{name} - Scroll")
        self.seal.set_state(modified)
        self._update_status()

    def _update_status(self, message=None):
        if message is not None:
            self.status_msg.set_text(message)
        it = self.buffer.get_iter_at_mark(self.buffer.get_insert())
        self.status_pos.set_text(f"Line {it.get_line() + 1}, column {it.get_line_offset() + 1}")
        lang = self.buffer.get_language()
        self.status_lang.set_text(lang.get_name() if lang else "Plain text")

    def _guess_language(self, gfile):
        content_type = None
        try:
            info = gfile.query_info("standard::content-type", Gio.FileQueryInfoFlags.NONE, None)
            content_type = info.get_content_type()
        except GLib.Error:
            pass
        lang = GtkSource.LanguageManager.get_default().guess_language(gfile.get_basename(), content_type)
        self.buffer.set_language(lang)

    def load(self, gfile):
        self.file.set_location(gfile)
        loader = GtkSource.FileLoader.new(self.buffer, self.file)
        self._update_status("Unrolling…")
        loader.load_async(GLib.PRIORITY_DEFAULT, None, None, None, self._loaded, gfile)

    def _loaded(self, loader, result, gfile):
        try:
            loader.load_finish(result)
        except GLib.Error as err:
            self.file.set_location(None)
            self._error(f"Couldn't open {gfile.get_basename()}", err.message)
            self._update_title()
            return
        self._guess_language(gfile)
        self.buffer.place_cursor(self.buffer.get_start_iter())
        self.buffer.set_modified(False)
        Gtk.RecentManager.get_default().add_item(gfile.get_uri())
        self._update_title()
        self._update_status("")

    def open_dialog(self):
        dialog = Gtk.FileChooserNative(title="Open a scroll", transient_for=self, action=Gtk.FileChooserAction.OPEN,
                                       select_multiple=True)
        location = self.file.get_location()
        if location and location.get_parent():
            dialog.set_current_folder_file(location.get_parent())
        if dialog.run() == Gtk.ResponseType.ACCEPT:
            for gfile in dialog.get_files():
                self.app.open_file(gfile, self)
        dialog.destroy()

    def save(self, then=None):
        if self.file.get_location() is None:
            self.save_as(then)
            return
        saver = GtkSource.FileSaver.new(self.buffer, self.file)
        self._update_status("Sealing…")
        saver.save_async(GLib.PRIORITY_DEFAULT, None, None, None, self._saved, then)

    def _saved(self, saver, result, then):
        try:
            saver.save_finish(result)
        except GLib.Error as err:
            self._error(f"Couldn't save {self.display_name()}", err.message)
            return
        self.buffer.set_modified(False)
        self._guess_language(self.file.get_location())
        Gtk.RecentManager.get_default().add_item(self.file.get_location().get_uri())
        self.seal.stamp(self.prefs.animations)
        self._update_title()
        self._update_status("Sealed.")
        if then:
            then()

    def save_as(self, then=None):
        dialog = Gtk.FileChooserNative(title="Save scroll as", transient_for=self, action=Gtk.FileChooserAction.SAVE)
        dialog.set_do_overwrite_confirmation(True)
        location = self.file.get_location()
        if location:
            dialog.set_file(location)
        else:
            dialog.set_current_name("Untitled scroll.txt")
            docs = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOCUMENTS)
            if docs:
                dialog.set_current_folder(docs)
        if dialog.run() == Gtk.ResponseType.ACCEPT:
            self.file.set_location(dialog.get_file())
            self.save(then)
        dialog.destroy()

    def _error(self, title, detail):
        dialog = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.ERROR,
                                   buttons=Gtk.ButtonsType.CLOSE, text=title, secondary_text=detail)
        dialog.run()
        dialog.destroy()
        self._update_status("")

    # --- closing ---------------------------------------------------------------------------------

    def close_scroll(self):
        if self.closing:
            return
        if not self.buffer.get_modified():
            self._roll_up_and_close()
            return
        dialog = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION,
                                   text=f"Seal your changes to “{self.display_name()}” before rolling it up?",
                                   secondary_text="If you don't, your changes will be lost.")
        dialog.add_buttons("Don't save", Gtk.ResponseType.REJECT, "Cancel", Gtk.ResponseType.CANCEL,
                           "Save", Gtk.ResponseType.ACCEPT)
        dialog.set_default_response(Gtk.ResponseType.ACCEPT)
        response = dialog.run()
        dialog.destroy()
        if response == Gtk.ResponseType.ACCEPT:
            self.save(then=self._roll_up_and_close)
        elif response == Gtk.ResponseType.REJECT:
            self._roll_up_and_close()

    def _on_delete(self, *_args):
        if self.close_ok:
            return False
        self.close_scroll()
        return True

    # --- editing ---------------------------------------------------------------------------------

    def undo(self):
        if self.buffer.can_undo():
            self.buffer.undo()

    def redo(self):
        if self.buffer.can_redo():
            self.buffer.redo()

    def zoom(self, step):
        self._set_pref("zoom", 100 if step == 0 else max(50, min(300, self.prefs.zoom + step)))

    # --- search ----------------------------------------------------------------------------------

    def show_search(self, replace):
        for widget in self.replace_row:
            widget.set_visible(replace)
        self.search_revealer.set_reveal_child(True)
        bounds = self.buffer.get_selection_bounds()
        if bounds and bounds[0].get_line() == bounds[1].get_line():
            self.search_entry.set_text(self.buffer.get_text(bounds[0], bounds[1], False))
        self.search_entry.grab_focus()
        self.search.set_highlight(True)

    def hide_search(self):
        self.search_revealer.set_reveal_child(False)
        self.search.set_highlight(False)
        self.view.grab_focus()

    def _search_key(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.hide_search()
            return True
        if event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and event.state & Gdk.ModifierType.SHIFT_MASK:
            self.find(False)
            return True
        return False

    def _search_changed(self, entry):
        self.search_settings.set_search_text(entry.get_text() or None)
        self.find(True, from_selection_start=True)

    def _update_search_count(self):
        count = self.search.get_occurrences_count()
        text = self.search_settings.get_search_text()
        ctx = self.search_entry.get_style_context()
        if not text:
            self.search_count.set_text("")
            ctx.remove_class("error")
        elif count == 0:
            self.search_count.set_text("not found")
            ctx.add_class("error")
        else:
            self.search_count.set_text(f"{count} found" if count > 0 else "")
            ctx.remove_class("error")

    def find(self, forward=True, from_selection_start=False):
        if not self.search_settings.get_search_text():
            if not self.search_revealer.get_reveal_child():
                self.show_search(False)
            return
        bounds = self.buffer.get_selection_bounds()
        insert = self.buffer.get_iter_at_mark(self.buffer.get_insert())
        if bounds:
            start = bounds[0] if (from_selection_start or not forward) else bounds[1]
        else:
            start = insert
        found, match_start, match_end, _wrapped = (self.search.forward(start) if forward
                                                   else self.search.backward(start))
        if found:
            self.buffer.select_range(match_start, match_end)
            self.view.scroll_to_iter(match_start, 0.2, False, 0, 0)

    def replace_one(self):
        bounds = self.buffer.get_selection_bounds()
        replacement = self.replace_entry.get_text()
        if bounds:
            try:
                self.search.replace(bounds[0], bounds[1], replacement, -1)
            except GLib.Error:
                pass
        self.find(True)

    def replace_all(self):
        try:
            count = self.search.replace_all(self.replace_entry.get_text(), -1)
        except GLib.Error as err:
            self._update_status(err.message)
            return
        self._update_status(f"Replaced {count}.")


class ScrollApp(Gtk.Application):
    def __init__(self, animate=True):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)
        self.animate = animate
        self.prefs = prefs_mod.load()
        self.state_monitor = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        _css(CSS)
        accels = {
            "win.new": ["<Ctrl>n"], "win.open": ["<Ctrl>o"], "win.save": ["<Ctrl>s"],
            "win.save-as": ["<Ctrl><Shift>s"], "win.close": ["<Ctrl>w"], "app.quit": ["<Ctrl>q"],
            "win.undo": ["<Ctrl>z"], "win.redo": ["<Ctrl><Shift>z", "<Ctrl>y"],
            "win.find": ["<Ctrl>f"], "win.replace": ["<Ctrl>h"],
            "win.find-next": ["<Ctrl>g", "F3"], "win.find-prev": ["<Ctrl><Shift>g", "<Shift>F3"],
            "win.zoom-in": ["<Ctrl>plus", "<Ctrl>equal", "<Ctrl>KP_Add"],
            "win.zoom-out": ["<Ctrl>minus", "<Ctrl>KP_Subtract"], "win.zoom-reset": ["<Ctrl>0"],
            "win.fullscreen": ["F11"],
        }
        for action, keys in accels.items():
            self.set_accels_for_action(action, keys)
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_a: self.quit_all())
        self.add_action(quit_action)
        state_file = Gio.File.new_for_path(str(state_mod.state_file()))
        self.state_monitor = state_file.monitor_file(Gio.FileMonitorFlags.NONE, None)
        self.state_monitor.connect("changed", self._tribe_changed)

    def _tribe_changed(self, _mon, _file, _other, event):
        if event in (Gio.FileMonitorEvent.CHANGES_DONE_HINT, Gio.FileMonitorEvent.CREATED,
                     Gio.FileMonitorEvent.RENAMED, Gio.FileMonitorEvent.MOVED_IN):
            for window in self.get_windows():
                if isinstance(window, ScrollWindow):
                    window.reload_tribe()

    def do_activate(self):
        self.new_window()

    def do_open(self, files, _n, _hint):
        for gfile in files:
            self.open_file(gfile)

    def new_window(self, near=None, path=None):
        window = ScrollWindow(self, path)
        window.show_all()
        window.search_revealer.set_reveal_child(False)
        window._apply_prefs()
        window.present()
        return window

    def open_file(self, gfile, current=None):
        for window in self.get_windows():
            if isinstance(window, ScrollWindow):
                location = window.file.get_location()
                if location and location.equal(gfile):
                    window.present()
                    return window
        if current is not None and current.is_blank():
            current.load(gfile)
            return current
        window = self.new_window()
        window.load(gfile)
        return window

    def open_uri(self, uri, current=None):
        if uri:
            self.open_file(Gio.File.new_for_uri(uri), current)

    def quit_all(self):
        for window in list(self.get_windows()):
            if isinstance(window, ScrollWindow):
                window.close_scroll()


def main():
    return ScrollApp().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
