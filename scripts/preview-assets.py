#!/usr/bin/env python3
"""Render a contact sheet of generated tribe assets (icons, wallpapers, terminal palette) to a PNG.

usage: preview-assets.py ASSET_ROOT TRIBES_DIR OUT.png
"""
import sys
from pathlib import Path

import gi

gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Gdk", "3.0")
import cairo
from gi.repository import Gdk, GdkPixbuf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "desktop/lib"))
from pyrrhia import colors, tribes  # noqa: E402
from pyrrhia.assets import terminal  # noqa: E402

ICONS = [("places", "folder"), ("places", "folder-open"), ("places", "user-home"), ("places", "folder-documents"),
         ("places", "folder-pictures"), ("places", "user-trash"), ("mimetypes", "text-plain"),
         ("mimetypes", "text-x-script"), ("mimetypes", "image-png"), ("mimetypes", "application-json"),
         ("apps", "wof-scroll"), ("apps", "pyrrhia-settings")]
ROW_H, ICON, WALL_W = 130, 56, 200


def main(root, tribes_dir, out):
    root = Path(root)
    all_tribes = list(tribes.all_tribes().values())
    width = 150 + WALL_W + 20 + len(ICONS) * (ICON + 8) + 20 + 8 * 18
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, width, ROW_H * len(all_tribes))
    cr = cairo.Context(surface)
    for row, tribe in enumerate(all_tribes):
        y = row * ROW_H
        cr.set_source_rgb(*colors.parse(tribe.colors["surface"]))
        cr.rectangle(0, y, width, ROW_H)
        cr.fill()
        cr.set_source_rgb(*colors.parse(tribe.colors["text"]))
        cr.select_font_face("Serif", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(18)
        cr.move_to(12, y + 40)
        cr.show_text(tribe.name)
        x = 150
        wall = tribe.wallpaper()
        if wall:
            pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(wall), WALL_W, ROW_H - 16, False)
            Gdk.cairo_set_source_pixbuf(cr, pb, x, y + 8)
            cr.paint()
        x += WALL_W + 20
        for context, name in ICONS:
            path = root / "icons" / tribe.icon_theme / "scalable" / context / f"{name}.svg"
            pb = GdkPixbuf.Pixbuf.new_from_file_at_size(str(path), ICON, ICON)
            Gdk.cairo_set_source_pixbuf(cr, pb, x, y + 20)
            cr.paint()
            x += ICON + 8
        x += 12
        palette = terminal.colours(tribe)["color-palette"].split(";")
        cr.set_source_rgb(*colors.parse(terminal.colours(tribe)["color-background"]))
        cr.rectangle(x - 4, y + 16, 8 * 18 + 8, 2 * 18 + 8)
        cr.fill()
        for i, col in enumerate(palette):
            cr.set_source_rgb(*colors.parse(col))
            cr.rectangle(x + (i % 8) * 18, y + 20 + (i // 8) * 18, 16, 16)
            cr.fill()
    surface.write_to_png(out)


if __name__ == "__main__":
    main(*sys.argv[1:4])
