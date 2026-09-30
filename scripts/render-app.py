#!/usr/bin/env python3
"""Render a Wings of Fire OS app window to PNG without showing it (for previews and checks).

usage: render-app.py settings|scroll|map OUT.png [--tribe ID] [--delay SECONDS] [--file PATH]
       map options: --continent ID --place NAME --style tribe|parchment --zoom N --measure A B
Run under a throwaway display, e.g. GDK_BACKEND=broadway with broadwayd running.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "desktop/lib"))

import gi  # noqa: E402

gi.require_version("Gtk", "3.0")
import cairo  # noqa: E402
from gi.repository import GLib, Gtk  # noqa: E402


def snapshot(window, out):
    alloc = window.get_allocation()
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, alloc.width, alloc.height)
    cr = cairo.Context(surface)
    window.draw(cr)
    surface.write_to_png(out)
    print(f"wrote {out} ({alloc.width}x{alloc.height})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("app", choices=("settings", "scroll", "map"))
    parser.add_argument("out")
    parser.add_argument("--tribe")
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--file")
    parser.add_argument("--size", help="window size WxH")
    parser.add_argument("--search", help="scroll: open the search bar with this text")
    parser.add_argument("--scroll", type=float, help="settings: scroll to this fraction of the page")
    parser.add_argument("--progress", type=float, help="scroll: freeze the open animation at this point (0..1)")
    parser.add_argument("--continent", help="map: continent to show")
    parser.add_argument("--place", help="map: place to select")
    parser.add_argument("--style", choices=("tribe", "parchment"), help="map: drawing style")
    parser.add_argument("--zoom", type=float, help="map: zoom factor after fitting")
    parser.add_argument("--measure", nargs=2, metavar="PLACE", help="map: measure between two places")
    args = parser.parse_args()

    if args.app == "settings":
        from pyrrhia import settings_app
        app = settings_app.SettingsApp()

        def activate(application):
            window = settings_app.SettingsWindow(application)
            if args.size:
                window.set_default_size(*map(int, args.size.split("x")))
            window.show_all()
            if args.scroll is not None:
                def scroll():
                    adj = window.get_child().get_children()[1].get_vadjustment()
                    adj.set_value(args.scroll * (adj.get_upper() - adj.get_page_size()))
                GLib.timeout_add(int(args.delay * 500), scroll)
            if args.tribe:
                window._on_card(None, window.card_by_id[args.tribe])
            GLib.timeout_add(int(args.delay * 1000), lambda: (snapshot(window, args.out), application.quit()))
        app.connect("activate", activate)
        app.do_activate = lambda: None
    elif args.app == "map":
        from wofmap import app as map_app
        options = map_app.parse_args([a for a in (["--continent", args.continent] if args.continent else [])])
        app = map_app.MapApp(options)

        def activate(application):
            window = map_app.MapWindow(application, options)
            window.set_default_size(*map(int, (args.size or "1280x820").split("x")))
            if args.style:
                window.prefs["style"] = args.style
                window._apply_palette()
            window.show_all()
            window.info.set_reveal_child(False)
            window.status.hide()
            view = window.view
            view._fitted = False

            def pose():
                view.fit(animate=False)
                if args.zoom:
                    view.zoom_by(args.zoom)
                if args.place:
                    m = window.continent.landmark(args.place)
                    view.select(m, zoom=False)
                    mx, my = view._norm_to_map(*m.pos)
                    view.cx, view.cy = mx, my
                if args.measure:
                    a, b = (window.continent.landmark(n) for n in args.measure)
                    view._measure = [view._norm_to_map(*a.pos), view._norm_to_map(*b.pos)]
                view.queue_draw()
            GLib.timeout_add(int(args.delay * 400), pose)
            GLib.timeout_add(int(args.delay * 1000), lambda: (snapshot(window, args.out), application.quit()))
        app.connect("activate", activate)
        app.do_activate = lambda: None
    else:
        from wofscroll import app as scroll_app
        app = scroll_app.ScrollApp(animate=args.progress is None)

        def activate(application):
            window = scroll_app.ScrollWindow(application, Path(args.file) if args.file else None)
            if args.size:
                window.resize(*map(int, args.size.split("x")))
            window.show_all()
            window.search_revealer.set_reveal_child(False)
            if args.search:
                GLib.timeout_add(int(args.delay * 400), lambda: (window.show_search(True),
                                                                 window.search_entry.set_text(args.search)))
            if args.progress is not None:
                GLib.timeout_add(int(args.delay * 500), lambda: window.set_progress(args.progress))
            GLib.timeout_add(int(args.delay * 1000), lambda: (snapshot(window, args.out), application.quit()))
        app.connect("activate", activate)
        app.do_activate = lambda: None
    app.run([sys.argv[0]])


if __name__ == "__main__":
    main()
