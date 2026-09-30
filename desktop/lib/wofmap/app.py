"""Map of the Dragon World: Pyrrhia, Pantala and any continent added later, flat or in 3D."""
import argparse
import json
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

from pyrrhia import colors, paths, state as state_mod, tribes  # noqa: E402

from . import atlas, view2d, view3d  # noqa: E402

APP_ID = "org.wingsoffire.Map"

APP_CSS = """
.wof-wordmark { font-family: "Wings of Fire Title", serif; font-size: 18px; }
.wof-info { padding: 16px 18px; border-radius: 12px; margin: 12px; min-width: 300px;
            background-color: alpha(@theme_bg_color, 0.96); border: 1px solid alpha(@theme_fg_color, 0.15);
            box-shadow: 0 4px 18px alpha(black, 0.35); }
.wof-info-title { font-family: "EB Garamond", serif; font-size: 26px; font-weight: bold; }
.wof-info-kind { font-size: 11px; letter-spacing: 2px; opacity: 0.8; }
.wof-info-blurb { font-family: "EB Garamond", serif; font-size: 16px; }
.wof-info-meta { opacity: 0.85; }
.wof-status { padding: 4px 12px; border-radius: 12px; margin: 10px; color: #fdf6e3;
              background-color: rgba(20, 16, 10, 0.72); font-family: "EB Garamond", serif; font-size: 14px; }
.wof-zoom { margin: 12px; }
.wof-3d-note { font-family: "EB Garamond", serif; font-size: 16px; padding: 18px 24px; border-radius: 12px;
               color: #fdf6e3; background-color: rgba(20, 16, 10, 0.75); }
.wof-hint { padding: 3px 10px; border-radius: 10px; color: #fdf6e3; background-color: rgba(20, 16, 10, 0.5);
            font-style: italic; font-size: 12px; }
"""


def prefs_file():
    return paths.config_dir() / "map.json"


def load_prefs():
    try:
        return json.loads(prefs_file().read_text())
    except (OSError, ValueError):
        return {}


def save_prefs(prefs):
    path = prefs_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(prefs, indent=2) + "\n")
    except OSError:
        pass


def current_tribe():
    try:
        return tribes.get(state_mod.load().tribe)
    except Exception:  # a broken tribe must not stop the map opening
        return None


class InfoPanel(Gtk.Revealer):
    def __init__(self, on_close, on_3d, on_zoom):
        super().__init__()
        self.set_transition_type(Gtk.RevealerTransitionType.SLIDE_LEFT)
        self.set_halign(Gtk.Align.END)
        self.set_valign(Gtk.Align.START)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.get_style_context().add_class("wof-info")
        box.set_size_request(320, -1)

        top = Gtk.Box(spacing=6)
        self.kind = Gtk.Label(xalign=0)
        self.kind.get_style_context().add_class("wof-info-kind")
        close = Gtk.Button.new_from_icon_name("window-close-symbolic", Gtk.IconSize.MENU)
        close.set_relief(Gtk.ReliefStyle.NONE)
        close.set_tooltip_text("Close")
        close.connect("clicked", lambda *_: on_close())
        top.pack_start(self.kind, True, True, 0)
        top.pack_end(close, False, False, 0)
        box.pack_start(top, False, False, 0)

        self.title = Gtk.Label(xalign=0)
        self.title.set_line_wrap(True)
        self.title.get_style_context().add_class("wof-info-title")
        box.pack_start(self.title, False, False, 0)
        self.region = Gtk.Label(xalign=0)
        self.region.set_line_wrap(True)
        self.region.get_style_context().add_class("wof-info-meta")
        box.pack_start(self.region, False, False, 0)
        self.blurb = Gtk.Label(xalign=0)
        self.blurb.set_line_wrap(True)
        self.blurb.set_max_width_chars(38)
        self.blurb.get_style_context().add_class("wof-info-blurb")
        box.pack_start(self.blurb, False, False, 0)
        self.meta = Gtk.Label(xalign=0)
        self.meta.set_line_wrap(True)
        self.meta.get_style_context().add_class("wof-info-meta")
        box.pack_start(self.meta, False, False, 0)

        buttons = Gtk.Box(spacing=8)
        self.btn_3d = Gtk.Button(label="Show in 3D")
        self.btn_3d.get_style_context().add_class("suggested-action")
        self.btn_3d.connect("clicked", lambda *_: on_3d())
        zoom = Gtk.Button(label="Zoom to")
        zoom.connect("clicked", lambda *_: on_zoom())
        buttons.pack_start(self.btn_3d, False, False, 0)
        buttons.pack_start(zoom, False, False, 0)
        box.pack_start(buttons, False, False, 4)
        self.add(box)

    def show_landmark(self, continent, landmark, assets, can_3d):
        group = continent.group(landmark.group) or {"label": "", "color": "#ffffff"}
        dot = GLib.markup_escape_text("\u25cf")
        self.kind.set_markup(f'<span foreground="{group["color"]}">{dot}</span>  '
                             f'{GLib.markup_escape_text(group["label"].upper())}')
        self.title.set_text(landmark.name)
        region = continent.region_at(*landmark.pos) if continent.regions else None
        if region:
            text = f"<b>{GLib.markup_escape_text(region.name)}</b>"
            if region.tribe:
                text += f"\n{GLib.markup_escape_text(region.tribe)}"
            self.region.set_markup(text)
            self.region.show()
        else:
            self.region.hide()
        self.blurb.set_text(landmark.blurb)
        self.blurb.set_visible(bool(landmark.blurb))
        meta = [continent.name]
        if assets and assets.heights:
            metres = assets.heights.metres(*landmark.pos)
            if metres > 0:
                meta.append(f"Ground at {atlas.format_height(metres)}")
        self.meta.set_text("  \u00b7  ".join(meta))
        self.btn_3d.set_sensitive(can_3d)
        self.btn_3d.set_tooltip_text(None if can_3d else "3D maps need WebKitGTK (gir1.2-webkit2-4.1)")
        self.set_reveal_child(True)


class MapWindow(Gtk.ApplicationWindow):
    def __init__(self, app, options):
        super().__init__(application=app, title="Map")
        self.set_default_size(1280, 820)
        self.set_icon_name("wof-map")
        self.prefs = load_prefs()
        self.continents = atlas.all_continents()
        self.assets = {}
        self.continent = None
        self.selected = None
        self.tribe = current_tribe()

        provider = Gtk.CssProvider()
        provider.load_from_data(APP_CSS.encode())
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        header = Gtk.HeaderBar(show_close_button=True)
        self.set_titlebar(header)

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        switcher = Gtk.StackSwitcher(stack=self.stack)
        header.set_custom_title(switcher)

        continents_box = Gtk.Box()
        continents_box.get_style_context().add_class("linked")
        self.continent_buttons = {}
        group = None
        for c in self.continents:
            b = Gtk.RadioButton.new_with_label_from_widget(group, c.name)
            b.set_mode(False)
            group = group or b
            b.connect("toggled", self._continent_toggled, c)
            continents_box.pack_start(b, False, False, 0)
            self.continent_buttons[c.id] = b
        header.pack_start(continents_box)

        self.search = Gtk.SearchEntry(placeholder_text="Find a place\u2026")
        self.search.set_width_chars(22)
        self._build_completion()
        self.search.connect("activate", self._search_activate)
        header.pack_end(self._build_layers_button())
        header.pack_end(self.search)

        self.view = view2d.MapView()
        self.view.connect("selected", self._on_selected)
        self.view.connect("hover", self._on_hover)

        overlay = Gtk.Overlay()
        overlay.add(self.view)
        self.info = InfoPanel(self._clear_selection, self._show_selected_in_3d, self._zoom_selected)
        overlay.add_overlay(self.info)
        self.status = Gtk.Label()
        self.status.get_style_context().add_class("wof-status")
        self.status.set_halign(Gtk.Align.CENTER)
        self.status.set_valign(Gtk.Align.END)
        self.status.set_no_show_all(True)
        overlay.add_overlay(self.status)
        overlay.set_overlay_pass_through(self.status, True)
        overlay.add_overlay(self._build_zoom_buttons())
        hint = Gtk.Label(label="Drag to move \u00b7 scroll to zoom \u00b7 right-drag to measure")
        hint.get_style_context().add_class("wof-hint")
        hint.set_halign(Gtk.Align.END)
        hint.set_valign(Gtk.Align.END)
        hint.set_margin_end(70)
        hint.set_margin_bottom(20)
        overlay.add_overlay(hint)
        overlay.set_overlay_pass_through(hint, True)

        self.map3d = view3d.Map3D(atlas.maps_dir())
        self.stack.add_titled(overlay, "2d", "Map")
        self.stack.add_titled(self.map3d, "3d", "3D")
        self.stack.connect("notify::visible-child-name", self._view_changed)

        if not self.continents:
            empty = Gtk.Label()
            empty.set_markup(f"<big>No maps installed</big>\nExpected them in {atlas.maps_dir()}")
            self.add(empty)
            return
        self.add(self.stack)

        self._apply_palette()
        self._watch_tribe()
        self.connect("key-press-event", self._on_key)

        start = options.continent or self.prefs.get("continent")
        first = next((c for c in self.continents if c.id == start), self.continents[0])
        self.continent_buttons[first.id].set_active(True)
        self._set_continent(first)
        if options.landmark:
            m = first.landmark(options.landmark)
            if m:
                GLib.idle_add(lambda: self.view.select(m) and False)
        if options.three_d:
            GLib.idle_add(lambda: self.stack.set_visible_child_name("3d") and False)

    # --- building blocks ------------------------------------------------------------------

    def _build_zoom_buttons(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.get_style_context().add_class("linked")
        box.get_style_context().add_class("wof-zoom")
        box.set_halign(Gtk.Align.END)
        box.set_valign(Gtk.Align.END)
        for icon, tip, action in (("zoom-in-symbolic", "Zoom in (+)", lambda: self.view.zoom_by(1.5)),
                                  ("zoom-out-symbolic", "Zoom out (\u2212)", lambda: self.view.zoom_by(1 / 1.5)),
                                  ("zoom-fit-best-symbolic", "Whole continent (0)", lambda: self.view.fit())):
            b = Gtk.Button.new_from_icon_name(icon, Gtk.IconSize.BUTTON)
            b.set_tooltip_text(tip)
            b.connect("clicked", lambda _b, a=action: a())
            box.pack_start(b, False, False, 0)
        return box

    def _build_layers_button(self):
        button = Gtk.MenuButton()
        button.set_image(Gtk.Image.new_from_icon_name("view-list-symbolic", Gtk.IconSize.BUTTON))
        button.set_tooltip_text("Layers and style")
        self.layers_popover = Gtk.Popover()
        button.set_popover(self.layers_popover)
        return button

    def _fill_layers(self):
        old = self.layers_popover.get_child()
        if old:
            self.layers_popover.remove(old)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_border_width(12)

        def heading(text):
            label = Gtk.Label(xalign=0)
            label.set_markup(f"<b>{GLib.markup_escape_text(text)}</b>")
            box.pack_start(label, False, False, 4)

        heading("Style")
        tribe_name = self.tribe.name if self.tribe else "Tribe"
        style = self.prefs.get("style", "tribe")
        r1 = Gtk.RadioButton.new_with_label(None, f"{tribe_name} colours")
        r2 = Gtk.RadioButton.new_with_label_from_widget(r1, "Old parchment")
        (r2 if style == "parchment" else r1).set_active(True)
        r1.connect("toggled", lambda b: b.get_active() and self._set_style("tribe"))
        r2.connect("toggled", lambda b: b.get_active() and self._set_style("parchment"))
        box.pack_start(r1, False, False, 0)
        box.pack_start(r2, False, False, 0)

        heading("Show")
        c = self.continent
        for key, label, present in (("regions", "Kingdoms and regions", bool(c.regions)),
                                    ("rivers", "Rivers", bool(c.rivers)),
                                    ("routes", "Silk bridges" if c.routes else "Routes", bool(c.routes)),
                                    ("labels", "Names", True)):
            if not present:
                continue
            check = Gtk.CheckButton(label=label)
            check.set_active(self.view.layers[key])
            check.connect("toggled", lambda b, k=key: self.view.set_layer(k, b.get_active()))
            box.pack_start(check, False, False, 0)

        heading("Places")
        for g in c.groups:
            row = Gtk.Box(spacing=6)
            check = Gtk.CheckButton()
            check.set_active(g["id"] not in self.view.hidden_groups)
            check.connect("toggled", lambda b, gid=g["id"]: self.view.set_group_visible(gid, b.get_active()))
            label = Gtk.Label(xalign=0)
            label.set_markup(f'<span foreground="{g["color"]}">\u25cf</span> {GLib.markup_escape_text(g["label"])}')
            check.add(label)
            row.pack_start(check, False, False, 0)
            box.pack_start(row, False, False, 0)
        box.show_all()
        self.layers_popover.add(box)

    def _build_completion(self):
        self.places = Gtk.ListStore(str, str, str, str)
        for c in self.continents:
            for m in c.landmarks:
                self.places.append([m.name, c.name, "landmark", f"{c.id}/{m.id}"])
            for r in c.regions:
                self.places.append([r.name, c.name, "region", f"{c.id}/{r.id}"])
            for lake in c.lakes:
                if lake.get("name") and not c.landmark(lake["name"]):
                    self.places.append([lake["name"], c.name, "lake", f"{c.id}/{lake['id']}"])
            for river in c.rivers:
                if river.get("name"):
                    self.places.append([river["name"], c.name, "river", f"{c.id}/{river['id']}"])
        completion = Gtk.EntryCompletion(model=self.places)
        completion.set_minimum_key_length(1)
        completion.set_popup_set_width(False)
        completion.set_match_func(self._match, None)
        name_cell = Gtk.CellRendererText()
        completion.pack_start(name_cell, True)
        completion.add_attribute(name_cell, "text", 0)
        where = Gtk.CellRendererText(foreground="#888888", xalign=1)
        completion.pack_start(where, False)
        completion.add_attribute(where, "text", 1)
        completion.connect("match-selected", self._match_selected)
        self.search.set_completion(completion)

    @staticmethod
    def _match(_completion, key, it, _data):
        model = _completion.get_model()
        name = model[it][0].lower()
        key = key.lower().strip()
        return bool(key) and (name.startswith(key) or f" {key}" in name)

    # --- behaviour ------------------------------------------------------------------------

    def _assets_for(self, continent):
        if continent.id not in self.assets:
            a = view2d.Assets(continent)
            atlas.region_anchors(continent, a.is_land)
            self.assets[continent.id] = a
        return self.assets[continent.id]

    def _continent_toggled(self, button, continent):
        if button.get_active() and continent is not self.continent:
            self._set_continent(continent)

    def _set_continent(self, continent):
        self.continent = continent
        self.selected = None
        self.info.set_reveal_child(False)
        self.view.set_continent(continent, self._assets_for(continent))
        self.set_title(f"Map \u2014 {continent.name}")
        self._fill_layers()
        self.prefs["continent"] = continent.id
        save_prefs(self.prefs)
        if self.stack.get_visible_child_name() == "3d":
            self.map3d.show_continent(continent)

    def _view_changed(self, *_):
        if self.stack.get_visible_child_name() == "3d" and self.continent:
            self.map3d.show_continent(self.continent)

    def _set_style(self, style):
        self.prefs["style"] = style
        save_prefs(self.prefs)
        self._apply_palette()

    def _apply_palette(self):
        style = self.prefs.get("style", "tribe")
        if self.tribe:
            palette = view2d.Palette(style, self.tribe.colors, self.tribe.dark)
        else:
            palette = view2d.Palette(style)
        self.view.set_palette(palette)

    def _watch_tribe(self):
        f = Gio.File.new_for_path(str(state_mod.state_file()))
        self._state_monitor = f.monitor_file(Gio.FileMonitorFlags.NONE, None)
        self._state_monitor.connect("changed", self._tribe_changed)

    def _tribe_changed(self, _m, _f, _o, event):
        if event in (Gio.FileMonitorEvent.CHANGES_DONE_HINT, Gio.FileMonitorEvent.CREATED,
                     Gio.FileMonitorEvent.RENAMED, Gio.FileMonitorEvent.MOVED_IN):
            self.tribe = current_tribe()
            self._apply_palette()
            if self.continent:
                self._fill_layers()

    def _on_selected(self, _view, landmark):
        self.selected = landmark
        if landmark is None:
            self.info.set_reveal_child(False)
            return
        self.info.show_landmark(self.continent, landmark, self.assets.get(self.continent.id), view3d.available())

    def _on_hover(self, _view, text):
        if text:
            self.status.set_text(text)
            self.status.show()
        else:
            self.status.hide()

    def _clear_selection(self):
        self.view.select(None, zoom=False)

    def _zoom_selected(self):
        if self.selected:
            self.view.select(self.selected)

    def _show_selected_in_3d(self):
        if not self.selected:
            return
        self.stack.set_visible_child_name("3d")
        self.map3d.focus(self.continent, self.selected)

    def _match_selected(self, _completion, model, it):
        self._go_to(model[it][3], model[it][2])
        self.search.set_text("")
        return True

    def _search_activate(self, entry):
        key = entry.get_text().strip().lower()
        if not key:
            return
        for row in self.places:
            if row[0].lower().startswith(key) or f" {key}" in row[0].lower():
                self._go_to(row[3], row[2])
                entry.set_text("")
                return

    def _go_to(self, ref, kind):
        cid, item = ref.split("/", 1)
        continent = next(c for c in self.continents if c.id == cid)
        if continent is not self.continent:
            self.continent_buttons[cid].set_active(True)
        self.stack.set_visible_child_name("2d")
        if kind == "landmark":
            self.view.select(continent.landmark(item))
        elif kind == "region":
            region = next(r for r in continent.regions if r.id == item)
            if region.anchor:
                self.view.show_point(*region.anchor, zoom=1.8)
        elif kind == "lake":
            lake = next(l for l in continent.lakes if l["id"] == item)
            xs, ys = zip(*lake["polygon"])
            self.view.show_point(sum(xs) / len(xs), sum(ys) / len(ys), zoom=3)
        elif kind == "river":
            river = next(r for r in continent.rivers if r["id"] == item)
            branch = max(river["branches"], key=len)
            x, y = branch[len(branch) // 2]
            self.view.show_point(x, y, zoom=2.5)

    def _on_key(self, _w, event):
        ctrl = event.state & Gdk.ModifierType.CONTROL_MASK
        key = Gdk.keyval_name(event.keyval) or ""
        if ctrl and key.lower() == "f":
            self.search.grab_focus()
            return True
        if self.search.has_focus() or self.stack.get_visible_child_name() != "2d":
            return False
        step = 80
        actions = {
            "plus": lambda: self.view.zoom_by(1.5), "equal": lambda: self.view.zoom_by(1.5),
            "KP_Add": lambda: self.view.zoom_by(1.5), "minus": lambda: self.view.zoom_by(1 / 1.5),
            "KP_Subtract": lambda: self.view.zoom_by(1 / 1.5), "0": lambda: self.view.fit(),
            "Left": lambda: self.view.pan_by(step, 0), "Right": lambda: self.view.pan_by(-step, 0),
            "Up": lambda: self.view.pan_by(0, step), "Down": lambda: self.view.pan_by(0, -step),
            "Escape": self._clear_selection,
        }
        action = actions.get(key)
        if action:
            action()
            return True
        return False


class MapApp(Gtk.Application):
    def __init__(self, options):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.options = options

    def do_activate(self):
        win = MapWindow(self, self.options)
        win.show_all()
        win.info.set_reveal_child(False)
        win.status.hide()
        self.add_action(self._action("quit", lambda *_: self.quit()))
        self.set_accels_for_action("app.quit", ["<Control>q"])

    @staticmethod
    def _action(name, callback):
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        return action


def parse_args(argv):
    ap = argparse.ArgumentParser(prog="wof-map", description="Maps of the Dragon World")
    ap.add_argument("--continent", help="continent to open, e.g. pyrrhia or pantala")
    ap.add_argument("--place", dest="landmark", help="place to select, e.g. \"Jade Mountain\"")
    ap.add_argument("--3d", dest="three_d", action="store_true", help="open the 3D view")
    return ap.parse_args(argv)


def main(argv=None):
    options = parse_args(sys.argv[1:] if argv is None else argv)
    return MapApp(options).run([sys.argv[0]])


if __name__ == "__main__":
    sys.exit(main())
