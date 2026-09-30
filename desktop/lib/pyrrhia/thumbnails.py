"""Wallpaper thumbnails, cached in ~/.cache/wingsoffire/thumbnails and loaded off the UI thread."""
import hashlib
import os
import threading
from pathlib import Path

import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, GLib  # noqa: E402


def cache_dir():
    base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / "wingsoffire/thumbnails"


def _key(path, width, height):
    st = Path(path).stat()
    raw = f"{path}:{st.st_mtime_ns}:{st.st_size}:{width}x{height}"
    return hashlib.sha1(raw.encode()).hexdigest()


def load_sync(path, width, height):
    """A pixbuf cropped to fill width x height."""
    cached = cache_dir() / f"{_key(path, width, height)}.png"
    if cached.exists():
        try:
            return GdkPixbuf.Pixbuf.new_from_file(str(cached))
        except GLib.Error:
            pass
    info = GdkPixbuf.Pixbuf.get_file_info(str(path))
    src_w, src_h = (info[1], info[2]) if info and info[0] else (width, height)
    scale = max(width / max(1, src_w), height / max(1, src_h))
    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path), max(width, round(src_w * scale)),
                                                     max(height, round(src_h * scale)), True)
    x = (pixbuf.get_width() - width) // 2
    y = (pixbuf.get_height() - height) // 2
    pixbuf = pixbuf.new_subpixbuf(max(0, x), max(0, y), min(width, pixbuf.get_width()),
                                  min(height, pixbuf.get_height())).copy()
    try:
        cached.parent.mkdir(parents=True, exist_ok=True)
        pixbuf.savev(str(cached), "png", [], [])
    except (GLib.Error, OSError):
        pass
    return pixbuf


def load_async(path, width, height, callback):
    """Calls callback(pixbuf or None) on the main loop."""
    def work():
        try:
            pixbuf = load_sync(path, width, height)
        except (GLib.Error, OSError):
            pixbuf = None
        GLib.idle_add(callback, pixbuf)
    threading.Thread(target=work, daemon=True).start()
