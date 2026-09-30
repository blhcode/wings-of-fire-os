"""Build-time generators for everything a tribe themes: GTK/notification theme, icon theme,
terminal colour scheme, text editor styles, sound theme and placeholder wallpapers.

`build_all(root)` writes them under `root` (a directory laid out like /usr/share)."""
from pathlib import Path

from .. import tribes as tribes_mod
from . import gtk, icons, sounds, sourceview, terminal, wallpaper


def build_tribe(tribe, root):
    root = Path(root)
    gtk.write(tribe, root / "themes" / tribe.theme_name)
    icons.write(tribe, root / "icons" / tribe.icon_theme)
    terminal.write(tribe, root / "xfce4/terminal/colorschemes" / f"wof-{tribe.id}.theme")
    sourceview.write(tribe, root / "gtksourceview-4/styles")
    sounds.write(tribe, root / "sounds" / tribe.sound_theme)


def build_all(root, tribe_list=None, tribes_dir=None):
    """Generate every tribe's assets. `tribes_dir` gets placeholder wallpapers for tribes that ship none."""
    tribe_list = tribe_list or list(tribes_mod.all_tribes().values())
    for tribe in tribe_list:
        build_tribe(tribe, root)
        if tribes_dir and not tribe.wallpapers():
            wallpaper.write_placeholder(tribe, Path(tribes_dir) / tribe.id / "wallpapers")
    icons.write_app_icons(Path(root) / "icons/hicolor")
    return tribe_list
