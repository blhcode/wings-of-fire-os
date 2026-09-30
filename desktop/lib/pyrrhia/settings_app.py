"""Pyrrhia Settings: choose your tribe, its wallpaper, and which parts of the desktop follow it."""
import shutil
import sys
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

from . import colors, components, paths, state as state_mod, theme, thumbnails, tribes  # noqa: E402
from .assets import gtk as gtk_theme  # noqa: E402

APP_ID = "org.wingsoffire.PyrrhiaSettings"
CARD_W, CARD_H = 208, 117
WALL_W, WALL_H = 176, 99
HERO_W, HERO_H = 360, 203

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
    def __init__(self, app):
        super().__init__(application=app, title="Pyrrhia Settings")
        self.set_default_size(1000, 760)
        self.set_icon_name("pyrrhia-settings")
        self.state = state_mod.load()
        self.all = tribes.all_tribes()
        if self.state.tribe not in self.all:
            self.state.tribe = next(iter(self.all))
        self.selected = self.all[self.state.tribe]
        self.selected_wall = self.state.wallpaper
        self.preview_provider = None
        self.busy = False

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
        self.cards = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.SINGLE, homogeneous=True,
                                 column_spacing=12, row_spacing=12, max_children_per_line=6)
        self.card_by_id = {}
        for tribe in self.all.values():
            card = TribeCard(tribe)
            self.card_by_id[tribe.id] = card
            self.cards.add(card)
        self.cards.connect("child-activated", self._on_card)
        page.pack_start(self.cards, False, False, 0)

        page.pack_start(self._section("Wallpaper"), False, False, 0)
        self.wall_note = Gtk.Label(xalign=0, wrap=True)
        self.wall_note.get_style_context().add_class("wof-note")
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
            self.checks[comp.id] = check
            grid.attach(check, i % 2, i // 2, 1, 1)
        page.pack_start(grid, False, False, 0)

        bar = Gtk.ActionBar()
        self.spinner = Gtk.Spinner()
        self.status = Gtk.Label(xalign=0)
        self.status.get_style_context().add_class("wof-status")
        bar.pack_start(self.spinner)
        bar.pack_start(self.status)
        self.apply_button = Gtk.Button()
        self.apply_button.get_style_context().add_class("suggested-action")
        self.apply_button.connect("clicked", self._apply)
        bar.pack_end(self.apply_button)
        outer.pack_end(bar, False, False, 0)

        self.cards.select_child(self.card_by_id[self.selected.id])
        self._refresh()
        self._watch_user_folder()

    # --- building blocks -------------------------------------------------------------------------

    def _section(self, text):
        label = Gtk.Label(label=text, xalign=0)
        label.get_style_context().add_class("wof-section")
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

    def _current_wallpaper(self):
        return self.selected.wallpaper(self.selected_wall or None)

    def _refresh(self):
        tribe = self.selected
        current = self.all.get(self.state.tribe)
        for tid, card in self.card_by_id.items():
            ctx = card.get_children()[0].get_style_context()
            (ctx.add_class if tid == self.state.tribe else ctx.remove_class)("current")
        self.hero_realm.set_text(f"KINGDOMS OF {tribe.realm.upper()}")
        is_current = current and current.id == tribe.id
        self.hero_name.set_text(tribe.name if is_current else f"{tribe.name}  (preview)")
        self.hero_desc.set_text(tribe.description)
        for child in self.hero_swatches.get_children():
            self.hero_swatches.remove(child)
        sw = Swatches(tribe, 20)
        sw.set_size_request(5 * 26, 20)
        self.hero_swatches.pack_start(sw, False, False, 0)
        self.hero_swatches.show_all()
        wall = self._current_wallpaper()
        if wall:
            thumbnails.load_async(wall, HERO_W, HERO_H, self.hero_image.set_from_pixbuf)
        else:
            self.hero_image.clear()
        self._fill_wallpapers()
        self.apply_button.set_label(f"Become {article(tribe.name)} {tribe.name}" if not is_current else "Apply again")
        self._preview_theme(tribe)

    def _fill_wallpapers(self):
        for child in self.walls.get_children():
            self.walls.remove(child)
        tribe = self.selected
        current = self._current_wallpaper()
        for path in tribe.wallpapers():
            tile = WallpaperTile(path)
            self.walls.add(tile)
            if current and path == current:
                self.walls.select_child(tile)
        self.walls.show_all()
        folder = paths.user_tribes() / tribe.id / "wallpapers"
        if tribe.has_own_wallpaper():
            self.wall_note.set_text(f"Your own {tribe.name} wallpapers go in {folder}")
        else:
            self.wall_note.set_text(f"The {tribe.name}s don't have their own wallpaper yet, so they get a "
                                    f"patterned placeholder. Add your own with the button below.")

    def _preview_theme(self, tribe):
        """Show the window in the chosen tribe's colours before applying."""
        screen = Gdk.Screen.get_default()
        if self.preview_provider:
            Gtk.StyleContext.remove_provider_for_screen(screen, self.preview_provider)
        self.preview_provider = _css_provider(gtk_theme.css(tribe))
        Gtk.StyleContext.add_provider_for_screen(screen, self.preview_provider,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    # --- events ----------------------------------------------------------------------------------

    def _on_card(self, _box, card):
        if card.tribe.id != self.selected.id:
            self.selected = card.tribe
            self.selected_wall = self.state.wallpaper if card.tribe.id == self.state.tribe else ""
            self._refresh()

    def _on_wallpaper(self, _box, tile):
        self.selected_wall = tile.path.name
        wall = self._current_wallpaper()
        thumbnails.load_async(wall, HERO_W, HERO_H, self.hero_image.set_from_pixbuf)

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
                self.selected_wall = added[0]
                self._reload_tribes()
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
        self.selected = self.all.get(self.selected.id, self.selected)
        for card in self.card_by_id.values():
            card.tribe = self.all.get(card.tribe.id, card.tribe)
        self._refresh()
        return False

    def _apply(self, _button):
        if self.busy:
            return
        self.busy = True
        self.apply_button.set_sensitive(False)
        self.spinner.start()
        choices = {cid: check.get_active() for cid, check in self.checks.items()}
        firefox_turned_off = self.state.enabled("firefox") and not choices["firefox"]
        state = theme.choose(self.selected.id, self.selected_wall, choices)

        def progress(comp):
            GLib.idle_add(self.status.set_text, f"Theming {comp.label.lower()}…")

        def work():
            if firefox_turned_off:
                from . import firefox
                firefox.remove()
            tribe, results = theme.apply(state, progress=progress)
            GLib.idle_add(self._applied, state, tribe, results)

        threading.Thread(target=work, daemon=True).start()

    def _applied(self, state, tribe, results):
        self.busy = False
        self.spinner.stop()
        self.apply_button.set_sensitive(True)
        self.state = state
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
        self._refresh()
        return False


class SettingsApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)

    def do_startup(self):
        Gtk.Application.do_startup(self)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), _css_provider(APP_CSS),
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 2)

    def do_activate(self):
        window = self.props.active_window or SettingsWindow(self)
        window.show_all()
        window.present()


def main():
    return SettingsApp().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
