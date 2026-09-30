"""Pyrrhia Settings: choose your tribe, its wallpaper, and which parts of the desktop follow it.
Every choice applies straight away: clicking a tribe changes everything that follows it."""
import shutil
import sys
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

from . import colors, components, firefox, paths, state as state_mod, theme, thumbnails, tribes  # noqa: E402

APP_ID = "org.wingsoffire.PyrrhiaSettings"
CARD_W, CARD_H = 168, 95
WALL_W, WALL_H = 160, 90
HERO_W, HERO_H = 288, 162
WELCOME = ("Welcome to Wings of Fire OS! Pick your tribe below: your wallpaper, colours, icons, terminal, "
           "Firefox, sounds and login screen all change at once. Come back any time from the Pyrrhia "
           "Settings button in the dock.")

APP_CSS = """
.wof-wordmark { font-family: "Wings of Fire Title", serif; font-size: 20px; }
.wof-hero-name { font-family: "EB Garamond", serif; font-size: 34px; font-weight: bold; }
.wof-section { font-family: "EB Garamond", serif; font-size: 19px; font-weight: bold; margin-top: 8px; }
.wof-realm { font-size: 11px; letter-spacing: 2px; opacity: 0.75; }
.wof-hero-image { border-radius: 10px; }
flowboxchild.wof-card { padding: 0; border-radius: 12px; }
.wof-card-box { border-radius: 12px; padding: 8px; border: 2px solid transparent; }
flowboxchild.wof-card:selected { background-color: transparent; }
.wof-note { font-style: italic; opacity: 0.8; }
.wof-status { opacity: 0.85; }
.wof-walls flowboxchild { padding: 4px; border-radius: 8px; }
"""


def article(name):
    return "an" if name[:1].upper() in "AEIOU" else "a"


def _css_provider(text):
    provider = Gtk.CssProvider()
    provider.load_from_data(text.encode())
    return provider


class Swatches(Gtk.DrawingArea):
    def __init__(self, tribe, height=14):
        super().__init__()
        self.tribe = tribe
        self.set_size_request(-1, height)
        self.connect("draw", self._draw)

    def _draw(self, _widget, cr):
        keys = ("accent", "accent_alt", "background", "surface", "text")
        height = self.get_allocated_height()
        size = height
        for i, key in enumerate(keys):
            cr.set_source_rgb(*colors.parse(self.tribe.colors[key]))
            cr.arc(size / 2 + i * (size + 6), height / 2, size / 2, 0, 6.2832)
            cr.fill_preserve()
            cr.set_source_rgba(0, 0, 0, 0.35)
            cr.set_line_width(1)
            cr.stroke()


class TribeCard(Gtk.FlowBoxChild):
    def __init__(self, tribe):
        super().__init__()
        self.tribe = tribe
        self.get_style_context().add_class("wof-card")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.get_style_context().add_class("wof-card-box")
        self.image = Gtk.Image()
        self.image.set_size_request(CARD_W, CARD_H)
        box.pack_start(self.image, False, False, 0)
        name = Gtk.Label(xalign=0)
        name.set_markup(f"<b>{GLib.markup_escape_text(tribe.name)}</b>")
        realm = Gtk.Label(label=tribe.realm.upper(), xalign=0)
        realm.get_style_context().add_class("wof-realm")
        row = Gtk.Box(spacing=8)
        row.pack_start(name, False, False, 0)
        row.pack_end(realm, False, False, 0)
        box.pack_start(row, False, False, 0)
        box.pack_start(Swatches(tribe), False, False, 0)
        self.add(box)
        c = tribe.colors
        self.box_style = box.get_style_context()
        self.box_style.add_provider(_css_provider(
            f".wof-card-box {{ background-color: {c['surface']}; color: {c['text']}; }}"
            f"flowboxchild:selected .wof-card-box, .wof-card-box.current {{ border-color: {c['accent']}; }}"
            f"flowboxchild:hover .wof-card-box {{ border-color: {colors.rgba(c['accent'], 0.6)}; }}"),
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
        wall = tribe.wallpaper()
        if wall:
            thumbnails.load_async(wall, CARD_W, CARD_H, self.image.set_from_pixbuf)
        self.set_tooltip_text(tribe.description)


class WallpaperTile(Gtk.FlowBoxChild):
    def __init__(self, path):
        super().__init__()
        self.path = path
        image = Gtk.Image()
        image.set_size_request(WALL_W, WALL_H)
        self.add(image)
        self.set_tooltip_text(path.name + (" (placeholder)" if tribes.is_placeholder(path) else ""))
        thumbnails.load_async(path, WALL_W, WALL_H, image.set_from_pixbuf)


class SettingsWindow(Gtk.ApplicationWindow):
    def __init__(self, app, welcome=False):
        super().__init__(application=app, title="Pyrrhia Settings")
        self.set_default_size(*self._fitted_size(1040, 820))
        self.set_icon_name("pyrrhia-settings")
        self.state = state_mod.load()
        self.all = tribes.all_tribes()
        if self.state.tribe not in self.all:
            self.state.tribe = next(iter(self.all))
        self.busy = False
        self.pending = None

        header = Gtk.HeaderBar(show_close_button=True)
        title = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        mark = Gtk.Label(label="Wings of Fire OS")
        mark.get_style_context().add_class("wof-wordmark")
        title.pack_start(mark, False, False, 0)
        sub = Gtk.Label(label="Pyrrhia Settings")
        sub.get_style_context().add_class("dim-label")
        title.pack_start(sub, False, False, 0)
        header.set_custom_title(title)
        self.set_titlebar(header)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(outer)
        self.infobar = Gtk.InfoBar(revealed=False, show_close_button=True)
        self.infobar.connect("response", lambda bar, _r: bar.set_revealed(False))
        self.info_label = Gtk.Label(xalign=0, wrap=True)
        self.infobar.get_content_area().add(self.info_label)
        outer.pack_start(self.infobar, False, False, 0)

        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        outer.pack_start(scroller, True, True, 0)
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=20)
        scroller.add(page)

        page.pack_start(self._section("Current Tribe"), False, False, 0)
        page.pack_start(self._hero(), False, False, 0)

        page.pack_start(self._section("Change Tribe"), False, False, 0)
        page.pack_start(self._note("Click a tribe and everything ticked below changes to it at once."),
                        False, False, 0)
        self.cards = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.SINGLE, homogeneous=True,
                                 column_spacing=12, row_spacing=12, max_children_per_line=5)
        self.card_by_id = {}
        for tribe in self.all.values():
            card = TribeCard(tribe)
            self.card_by_id[tribe.id] = card
            self.cards.add(card)
        self.cards.connect("child-activated", self._on_card)
        page.pack_start(self.cards, False, False, 0)

        self.wall_title = self._section("Wallpaper")
        page.pack_start(self.wall_title, False, False, 0)
        self.wall_note = self._note("")
        page.pack_start(self.wall_note, False, False, 0)
        self.walls = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.SINGLE, column_spacing=10, row_spacing=10,
                                 max_children_per_line=8)
        self.walls.set_halign(Gtk.Align.START)
        self.walls.get_style_context().add_class("wof-walls")
        self.walls.connect("child-activated", self._on_wallpaper)
        page.pack_start(self.walls, False, False, 0)
        buttons = Gtk.Box(spacing=8)
        add = Gtk.Button(label="Add wallpapers…")
        add.connect("clicked", self._add_wallpapers)
        folder = Gtk.Button(label="Open wallpaper folder")
        folder.connect("clicked", self._open_folder)
        buttons.pack_start(add, False, False, 0)
        buttons.pack_start(folder, False, False, 0)
        page.pack_start(buttons, False, False, 0)

        page.pack_start(self._section("What follows your tribe"), False, False, 0)
        grid = Gtk.Grid(column_spacing=24, row_spacing=6)
        self.checks = {}
        for i, comp in enumerate(components.COMPONENTS):
            check = Gtk.CheckButton()
            label = Gtk.Label(xalign=0)
            label.set_markup(f"<b>{GLib.markup_escape_text(comp.label)}</b>\n"
                             f"<small>{GLib.markup_escape_text(comp.description)}</small>")
            check.add(label)
            check.set_active(self.state.enabled(comp.id))
            check.connect("toggled", self._on_toggle, comp.id)
            self.checks[comp.id] = check
            grid.attach(check, i % 2, i // 2, 1, 1)
        page.pack_start(grid, False, False, 0)

        bar = Gtk.ActionBar()
        self.spinner = Gtk.Spinner()
        self.status = Gtk.Label(xalign=0)
        self.status.get_style_context().add_class("wof-status")
        bar.pack_start(self.spinner)
        bar.pack_start(self.status)
        self.apply_button = Gtk.Button(label="Apply again")
        self.apply_button.set_tooltip_text("Re-apply your tribe to everything ticked above")
        self.apply_button.connect("clicked", lambda _b: self._run(self.state.tribe, None, None))
        bar.pack_end(self.apply_button)
        outer.pack_end(bar, False, False, 0)

        self._refresh()
        self._watch_user_folder()
        if welcome:
            self.info_label.set_text(WELCOME)
            self.infobar.set_message_type(Gtk.MessageType.INFO)
            self.infobar.set_revealed(True)

    # --- building blocks -------------------------------------------------------------------------

    @staticmethod
    def _fitted_size(width, height):
        display = Gdk.Display.get_default()
        monitor = display and (display.get_primary_monitor() or display.get_monitor(0))
        if not monitor:
            return width, height
        area = monitor.get_workarea()
        return min(width, area.width - 40), min(height, area.height - 60)

    def _section(self, text):
        label = Gtk.Label(label=text, xalign=0)
        label.get_style_context().add_class("wof-section")
        return label

    def _note(self, text):
        label = Gtk.Label(label=text, xalign=0, wrap=True)
        label.get_style_context().add_class("wof-note")
        return label

    def _hero(self):
        box = Gtk.Box(spacing=20)
        self.hero_image = Gtk.Image()
        self.hero_image.set_size_request(HERO_W, HERO_H)
        self.hero_image.get_style_context().add_class("wof-hero-image")
        box.pack_start(self.hero_image, False, False, 0)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, valign=Gtk.Align.CENTER)
        self.hero_realm = Gtk.Label(xalign=0)
        self.hero_realm.get_style_context().add_class("wof-realm")
        self.hero_name = Gtk.Label(xalign=0)
        self.hero_name.get_style_context().add_class("wof-hero-name")
        self.hero_desc = Gtk.Label(xalign=0, wrap=True, max_width_chars=48)
        self.hero_swatches = Gtk.Box()
        text.pack_start(self.hero_realm, False, False, 0)
        text.pack_start(self.hero_name, False, False, 0)
        text.pack_start(self.hero_desc, False, False, 0)
        text.pack_start(self.hero_swatches, False, False, 4)
        box.pack_start(text, True, True, 0)
        return box

    # --- state -----------------------------------------------------------------------------------

    @property
    def selected(self):
        return self.all[self.state.tribe]

    def _refresh(self):
        tribe = self.selected
        for tid, card in self.card_by_id.items():
            ctx = card.get_children()[0].get_style_context()
            (ctx.add_class if tid == tribe.id else ctx.remove_class)("current")
        self.cards.select_child(self.card_by_id[tribe.id])
        self.hero_realm.set_text(f"KINGDOMS OF {tribe.realm.upper()}")
        self.hero_name.set_text(tribe.name)
        self.hero_desc.set_text(tribe.description)
        for child in self.hero_swatches.get_children():
            self.hero_swatches.remove(child)
        sw = Swatches(tribe, 20)
        sw.set_size_request(5 * 26, 20)
        self.hero_swatches.pack_start(sw, False, False, 0)
        self.hero_swatches.show_all()
        wall = tribe.wallpaper(self.state.wallpaper or None)
        if wall:
            thumbnails.load_async(wall, HERO_W, HERO_H, self.hero_image.set_from_pixbuf)
        else:
            self.hero_image.clear()
        self._fill_wallpapers(wall)

    def _fill_wallpapers(self, current):
        for child in self.walls.get_children():
            self.walls.remove(child)
        tribe = self.selected
        options = tribe.wallpapers()
        for path in options:
            tile = WallpaperTile(path)
            self.walls.add(tile)
            if current and path == current:
                self.walls.select_child(tile)
        # The box is start-aligned (so tiles don't stretch), which leaves it only one tile wide unless told.
        self.walls.set_min_children_per_line(max(1, min(len(options), 5)))
        self.walls.show_all()
        self.wall_title.set_text(f"{tribe.name} Wallpapers")
        folder = paths.user_tribes() / tribe.id / "wallpapers"
        if tribe.has_own_wallpaper():
            self.wall_note.set_text(f"Click one to use it. Your own {tribe.name} wallpapers go in {folder}")
        else:
            self.wall_note.set_text(f"The {tribe.name}s don't have their own wallpaper yet, so they get a "
                                    f"patterned placeholder. Add your own with the button below.")

    # --- events ----------------------------------------------------------------------------------

    def _on_card(self, _box, card):
        if card.tribe.id != self.state.tribe:
            self._run(card.tribe.id, None, None)

    def _on_wallpaper(self, _box, tile):
        if tile.path != self.selected.wallpaper(self.state.wallpaper or None):
            self._run(self.state.tribe, tile.path.name, ["wallpaper", "login"])

    def _on_toggle(self, check, comp_id):
        on = check.get_active()
        self.state.components[comp_id] = on
        state_mod.save(self.state)
        if on:
            self._run(self.state.tribe, None, [comp_id])
        elif comp_id == "firefox":
            firefox.remove()
            self.status.set_text("Firefox theme removed (restart Firefox to see it).")

    def _user_wall_dir(self):
        folder = paths.user_tribes() / self.selected.id / "wallpapers"
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def _add_wallpapers(self, _button):
        dialog = Gtk.FileChooserNative(title=f"Add {self.selected.name} wallpapers", transient_for=self,
                                       action=Gtk.FileChooserAction.OPEN, select_multiple=True)
        images = Gtk.FileFilter()
        images.set_name("Images")
        for pattern in ("*.png", "*.jpg", "*.jpeg", "*.webp", "*.svg", "*.PNG", "*.JPG", "*.JPEG"):
            images.add_pattern(pattern)
        dialog.add_filter(images)
        if dialog.run() == Gtk.ResponseType.ACCEPT:
            folder = self._user_wall_dir()
            added = []
            for f in dialog.get_filenames():
                src = Path(f)
                if src.suffix.lower() in tribes.WALLPAPER_SUFFIXES:
                    shutil.copy2(src, folder / src.name)
                    added.append(src.name)
            if added:
                self._reload_tribes()
                self._run(self.state.tribe, added[0], ["wallpaper", "login"])
        dialog.destroy()

    def _open_folder(self, _button):
        Gio.AppInfo.launch_default_for_uri(self._user_wall_dir().as_uri(), None)

    def _watch_user_folder(self):
        root = paths.user_tribes()
        root.mkdir(parents=True, exist_ok=True)
        self.monitors = []

        def watch(path):
            mon = Gio.File.new_for_path(str(path)).monitor_directory(Gio.FileMonitorFlags.NONE, None)
            mon.connect("changed", self._on_folder_changed)
            self.monitors.append(mon)

        watch(root)
        for d in root.iterdir():
            if (d / "wallpapers").is_dir():
                watch(d / "wallpapers")
        self._reload_pending = False

    def _on_folder_changed(self, *_args):
        if not self._reload_pending:
            self._reload_pending = True
            GLib.timeout_add(500, self._reload_tribes)

    def _reload_tribes(self):
        self._reload_pending = False
        self.all = tribes.all_tribes()
        for card in self.card_by_id.values():
            card.tribe = self.all.get(card.tribe.id, card.tribe)
        self._refresh()
        return False

    def _run(self, tribe_id, wallpaper, only):
        """Choose and apply in the background. A choice made while one is running replaces any
        waiting one, so clicking through tribes quickly ends on the last one clicked."""
        if self.busy:
            self.pending = (tribe_id, wallpaper, only)
            return
        self.busy = True
        self.spinner.start()
        state = theme.choose(tribe_id, wallpaper)
        self.state = state
        self._refresh()

        def progress(comp):
            GLib.idle_add(self.status.set_text, f"Theming {comp.label.lower()}…")

        def work():
            tribe, results = theme.apply(state, only=only, progress=progress)
            GLib.idle_add(self._applied, tribe, results)

        threading.Thread(target=work, daemon=True).start()

    def _applied(self, tribe, results):
        self.busy = False
        self.spinner.stop()
        failures = [(comp, msg) for comp, ok, msg in results if not ok]
        notes = [f"{comp.label}: {msg}" for comp, ok, msg in results if ok and "restart" in msg]
        if failures:
            self.info_label.set_text("Some parts couldn't change:\n" +
                                     "\n".join(f"• {comp.label}: {msg}" for comp, msg in failures))
            self.infobar.set_message_type(Gtk.MessageType.WARNING)
            self.infobar.set_revealed(True)
        elif notes:
            self.info_label.set_text("\n".join(notes))
            self.infobar.set_message_type(Gtk.MessageType.INFO)
            self.infobar.set_revealed(True)
        else:
            self.infobar.set_revealed(False)
        self.status.set_text(f"You are {article(tribe.name)} {tribe.name}.")
        if self.pending:
            job, self.pending = self.pending, None
            self._run(*job)
        return False


class SettingsApp(Gtk.Application):
    def __init__(self, welcome=False):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.welcome = welcome

    def do_startup(self):
        Gtk.Application.do_startup(self)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), _css_provider(APP_CSS),
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 2)

    def do_activate(self):
        window = self.props.active_window or SettingsWindow(self, welcome=self.welcome)
        window.show_all()
        window.present()


def welcome_marker():
    return paths.config_dir() / "welcomed"


def main():
    """`pyrrhia-settings --welcome` (run at login) opens the window only the first time for each user."""
    argv = list(sys.argv)
    welcome = "--welcome" in argv
    if welcome:
        argv.remove("--welcome")
        marker = welcome_marker()
        if marker.exists():
            return 0
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()
    return SettingsApp(welcome).run(argv)


if __name__ == "__main__":
    sys.exit(main())
