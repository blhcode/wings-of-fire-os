"""3D maps in a WebKit view.

The maps are served from disk through a private ``wofmap://maps/`` scheme rather than file://,
because the 3D builds load ES modules, which WebKit refuses to run from file URLs.
"""
import json
import mimetypes
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

WebKit2 = None
for _version in ("4.1", "4.0"):
    try:
        gi.require_version("WebKit2", _version)
        from gi.repository import WebKit2  # noqa: E402,F811
        break
    except (ValueError, ImportError):
        WebKit2 = None

SCHEME = "wofmap"
MIME = {".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".html": "text/html",
        ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg", ".svg": "image/svg+xml",
        ".wasm": "application/wasm", ".glb": "model/gltf-binary", ".woff2": "font/woff2"}

# Pyrrhia's own 3D map has no API; its landmark list does exactly what we want when clicked.
FOCUS_OWN_3D = """
(function (name) {
  function find() {
    return Array.from(document.querySelectorAll('.lm-btn')).find(function (b) {
      var s = b.querySelector('strong');
      return s && s.textContent === name;
    });
  }
  function go() {
    var loading = document.getElementById('loading');
    if (loading && !loading.classList.contains('is-done')) return setTimeout(go, 300);
    var search = document.getElementById('landmark-search');
    var button = find();
    if (!button && search) {
      search.value = name;
      search.dispatchEvent(new Event('input'));
      button = find();
    }
    if (button) button.click();
    if (search && search.value) {
      search.value = '';
      search.dispatchEvent(new Event('input'));
    }
  }
  go();
})(%s);
"""
FOCUS_VIEWER = """
(function (id) {
  function go() {
    if (!window.wofReady) return setTimeout(go, 300);
    window.wofFocus(id);
  }
  go();
})(%s);
"""


def available():
    return WebKit2 is not None


def resolve(root, uri_path):
    """File under ``root`` for a request path, or None if it escapes the maps folder."""
    root = Path(root).resolve()
    try:
        target = (root / uri_path.lstrip("/")).resolve()
    except (OSError, RuntimeError):
        return None
    if target != root and root not in target.parents:
        return None
    return target if target.is_file() else None


def url_for(continent):
    if continent.own_3d:
        return f"{SCHEME}://maps/{continent.id}/3d/index.html"
    return f"{SCHEME}://maps/viewer/index.html?map={continent.id}"


def focus_script(continent, landmark):
    if continent.own_3d:
        return FOCUS_OWN_3D % json.dumps(landmark.name)
    return FOCUS_VIEWER % json.dumps(landmark.id)


_registered = set()


def _register(context, root):
    if id(context) in _registered:
        return
    _registered.add(id(context))

    def handle(request):
        path = resolve(root, request.get_path() or "/")
        if path is None:
            request.finish_error(GLib.Error.new_literal(Gio.io_error_quark(), "Not found",
                                                        int(Gio.IOErrorEnum.NOT_FOUND)))
            return
        mime = MIME.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        stream = Gio.File.new_for_path(str(path)).read(None)
        size = path.stat().st_size
        if hasattr(WebKit2, "URISchemeResponse"):
            response = WebKit2.URISchemeResponse.new(stream, size)
            response.set_content_type(mime)
            request.finish_with_response(response)
        else:
            request.finish(stream, size, mime)

    context.register_uri_scheme(SCHEME, handle)
    security = context.get_security_manager()
    security.register_uri_scheme_as_secure(SCHEME)
    security.register_uri_scheme_as_cors_enabled(SCHEME)


class Map3D(Gtk.Overlay):
    """Holds the web view (created on first use) and a note while a map loads."""

    def __init__(self, root):
        super().__init__()
        self.root = root
        self.view = None
        self.current_url = None
        self._pending = None
        self.note = Gtk.Label()
        self.note.get_style_context().add_class("wof-3d-note")
        self.note.set_line_wrap(True)
        self.note.set_justify(Gtk.Justification.CENTER)
        self.add_overlay(self.note)
        if not available():
            self.note.set_markup("<big><b>3D maps need WebKitGTK</b></big>\n"
                                 "Install the <tt>gir1.2-webkit2-4.1</tt> package to fly over the maps.")
            self.add(Gtk.Box())

    def _ensure_view(self):
        if self.view or not available():
            return self.view is not None
        context = WebKit2.WebContext.get_default()
        _register(context, self.root)
        self.view = WebKit2.WebView.new_with_context(context)
        settings = self.view.get_settings()
        settings.set_enable_webgl(True)
        settings.set_enable_developer_extras(False)
        if hasattr(settings, "set_hardware_acceleration_policy"):
            settings.set_hardware_acceleration_policy(WebKit2.HardwareAccelerationPolicy.ALWAYS
                                                      if hasattr(WebKit2.HardwareAccelerationPolicy, "ALWAYS")
                                                      else WebKit2.HardwareAccelerationPolicy.ON_DEMAND)
        self.view.connect("load-changed", self._load_changed)
        self.view.connect("load-failed", self._load_failed)
        self.view.connect("context-menu", lambda *_: True)
        self.add(self.view)
        self.view.show()
        return True

    def show_continent(self, continent):
        if not self._ensure_view():
            return
        url = url_for(continent)
        if url != self.current_url:
            self.current_url = url
            self.note.set_markup(f"<big>Unrolling {GLib.markup_escape_text(continent.name)}\u2026</big>")
            self.note.show()
            self.view.load_uri(url)

    def focus(self, continent, landmark):
        """Fly to a landmark once the continent's 3D map is ready."""
        if not self._ensure_view():
            return
        script = focus_script(continent, landmark)
        url = url_for(continent)
        if url != self.current_url or self.view.is_loading():
            self._pending = script
            self.show_continent(continent)
        else:
            self._run(script)

    def _run(self, script):
        if hasattr(self.view, "evaluate_javascript"):
            self.view.evaluate_javascript(script, -1, None, None, None, None, None)
        else:
            self.view.run_javascript(script, None, None, None)

    def _load_changed(self, _view, event):
        if event == WebKit2.LoadEvent.FINISHED:
            self.note.hide()
            if self._pending:
                script, self._pending = self._pending, None
                self._run(script)

    def _load_failed(self, _view, _event, uri, error):
        self.note.set_markup(f"<b>Couldn\u2019t open the 3D map</b>\n{GLib.markup_escape_text(error.message)}")
        self.note.show()
        return True
