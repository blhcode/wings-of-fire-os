"""Tribe icon themes: folders, scroll-shaped text files, framed images, config tablets and the
Wings of Fire OS app icons. Everything else is inherited from the base icon theme, so file
associations and behaviour don't change - only the pictures do."""
import base64
import textwrap
from pathlib import Path

from .. import colors as c
from .. import paths, patterns
from . import palette

FIRE = {"accent": "#e8541e", "accent_alt": "#f7b733", "seal": "#b3261e"}

# The emblem replaces Debian's and XFCE's logos: the panel's Applications button, "start here" and
# "distributor logo" (About dialogs, system info tools).
LOGO_NAMES = ("wingsoffire-logo", "distributor-logo", "start-here", "org.xfce.panel.applicationsmenu",
              "xfce4-panel-menu", "debian-logo")
FOLDER_NAMES = ("folder", "inode-directory", "folder-remote", "network-workgroup")
OPEN_FOLDER_NAMES = ("folder-open", "folder-drag-accept")
SPECIAL_FOLDERS = {
    "user-home": "home", "folder-home": "home", "user-desktop": "desktop", "folder-desktop": "desktop",
    "folder-documents": "scroll", "folder-download": "download", "folder-downloads": "download",
    "folder-pictures": "picture", "folder-images": "picture", "folder-music": "music",
    "folder-videos": "video", "folder-templates": "scroll", "folder-publicshare": "share",
    "user-trash": "trash",
}
TEXT_NAMES = ("text-plain", "text-x-generic", "text-x-log", "text-markdown", "text-x-readme",
              "application-rtf", "text-rtf", "x-office-document")
SCRIPT_NAMES = ("text-x-script", "application-x-shellscript", "text-x-python", "text-x-python3",
                "application-x-executable-script", "text-x-csrc", "text-x-chdr", "text-x-c++src",
                "text-html", "text-css", "application-javascript", "text-x-javascript")
IMAGE_NAMES = ("image-x-generic", "image-png", "image-jpeg", "image-gif", "image-bmp", "image-webp",
               "image-svg+xml", "image-tiff", "image-x-icon")
CONFIG_NAMES = ("text-x-ini", "application-x-desktop", "application-json", "application-xml", "text-xml",
                "application-toml", "application-x-yaml", "text-x-yaml", "text-x-makefile",
                "application-x-config", "text-x-install", "preferences-system")


def _svg(body, defs=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">'
            f'<defs>{defs}</defs>{body}</svg>\n')


def _grad(gid, top, bottom, vertical=True):
    x2, y2 = ("0", "1") if vertical else ("1", "0")
    return (f'<linearGradient id="{gid}" x1="0" y1="0" x2="{x2}" y2="{y2}">'
            f'<stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bottom}"/></linearGradient>')


def _pattern_def(pattern, colour):
    w, h, tile = patterns.tile(pattern, colour, opacity=0.5, scale=0.32)
    return (f'<pattern id="motif" patternUnits="userSpaceOnUse" width="{w:g}" height="{h:g}">'
            f'<image width="{w:g}" height="{h:g}" href="{patterns.data_uri(tile)}"/></pattern>')


EMBLEMS = {
    "home": "M32 29 L22 37 V47 H28 V41 H36 V47 H42 V37 Z",
    "desktop": "M21 31 H43 V43 H21 Z M29 43 H35 V47 H29 Z M26 47 H38",
    "scroll": "M23 30 H41 V46 H23 Z M26 34 H38 M26 38 H38 M26 42 H34",
    "download": "M32 29 V42 M26 37 L32 43 L38 37 M24 47 H40",
    "picture": "M22 31 H42 V46 H22 Z M24 44 L30 37 L34 41 L37 38 L40 44 Z",
    "music": "M28 44 A3 3 0 1 1 27.9 44 M31 44 V31 L40 29 V41 M40 41 A3 3 0 1 1 39.9 41",
    "video": "M22 31 H42 V46 H22 Z M29 34 L37 38.5 L29 43 Z",
    "share": "M26 40 A3 3 0 1 1 25.9 40 M39 33 A3 3 0 1 1 38.9 33 M39 46 A3 3 0 1 1 38.9 46 M28 39 L36 34 M28 41 L36 45",
}


def folder(p, pattern, emblem=None, open_=False):
    back, front = c.darken(p["accent"], 0.25), p["accent"]
    defs = _grad("front", c.lighten(front, 0.15), c.darken(front, 0.08)) + _pattern_def(pattern, c.lighten(front, 0.45))
    body = [f'<path d="M6 14 Q6 11 9 11 H24 L29 16 H55 Q58 16 58 19 V50 Q58 53 55 53 H9 Q6 53 6 50 Z" fill="{back}"/>']
    if open_:
        body.append('<path d="M10 20 H54 V46 H10 Z" fill="#fbf3dc"/>')
        body.append(f'<path d="M4 27 Q4 24 7 24 H57 Q60 24 59.5 27 L56 50 Q55.5 53 52.5 53 H11.5 Q8.5 53 8 50 Z" fill="url(#front)"/>')
        body.append('<path d="M4 27 Q4 24 7 24 H57 Q60 24 59.5 27 L56 50 Q55.5 53 52.5 53 H11.5 Q8.5 53 8 50 Z" fill="url(#motif)" opacity="0.6"/>')
    else:
        body.append('<path d="M9 18 H55 V40 H9 Z" fill="#fbf3dc"/>')
        body.append('<path d="M6 24 Q6 21 9 21 H55 Q58 21 58 24 V50 Q58 53 55 53 H9 Q6 53 6 50 Z" fill="url(#front)"/>')
        body.append('<path d="M6 24 Q6 21 9 21 H55 Q58 21 58 24 V50 Q58 53 55 53 H9 Q6 53 6 50 Z" fill="url(#motif)" opacity="0.6"/>')
    body.append(f'<path d="M6 50.5 H58" stroke="{c.darken(front, 0.35)}" stroke-width="1" opacity="0.5"/>')
    if emblem:
        body.append(f'<path d="{EMBLEMS[emblem]}" fill="none" stroke="{c.lighten(front, 0.85)}" stroke-width="2.4" '
                    f'stroke-linecap="round" stroke-linejoin="round"/>')
    return _svg("".join(body), defs)


def trash(p, pattern):
    col = p["accent"]
    defs = _grad("bin", c.lighten(col, 0.1), c.darken(col, 0.2))
    return _svg(
        f'<path d="M16 18 H48 L45 56 Q45 58 43 58 H21 Q19 58 19 56 Z" fill="url(#bin)"/>'
        f'<path d="M12 12 H52 V18 H12 Z" fill="{c.darken(col, 0.3)}"/><path d="M26 8 H38 V12 H26 Z" fill="{c.darken(col, 0.3)}"/>'
        f'<path d="M26 24 V52 M32 24 V52 M38 24 V52" stroke="{c.lighten(col, 0.6)}" stroke-width="2" stroke-linecap="round"/>',
        defs)


def scroll(p, lines="text"):
    """A parchment scroll between two tribe-coloured rollers."""
    roller, dark = p["accent"], c.darken(p["accent"], 0.35)
    defs = (_grad("paper", "#fbf1d6", "#e8d2a0", vertical=False) + _grad("roller", c.lighten(roller, 0.2), dark, vertical=False))
    body = [
        '<path d="M16 9 H48 V55 H16 Z" fill="url(#paper)"/>',
        '<path d="M16 9 H48 V55 H16 Z" fill="none" stroke="#b89a5e" stroke-width="0.8"/>',
        f'<rect x="11" y="4" width="42" height="7" rx="3.5" fill="url(#roller)"/>',
        f'<rect x="11" y="53" width="42" height="7" rx="3.5" fill="url(#roller)"/>',
        f'<circle cx="11" cy="7.5" r="3" fill="{dark}"/><circle cx="53" cy="7.5" r="3" fill="{dark}"/>',
        f'<circle cx="11" cy="56.5" r="3" fill="{dark}"/><circle cx="53" cy="56.5" r="3" fill="{dark}"/>',
    ]
    ink = "#5a4127"
    if lines == "text":
        for y, w in ((18, 26), (23, 22), (28, 25), (33, 18), (38, 24), (43, 14)):
            body.append(f'<path d="M20 {y} H{20 + w}" stroke="{ink}" stroke-width="1.8" stroke-linecap="round" opacity="0.75"/>')
    elif lines == "script":
        body.append(f'<path d="M21 22 L27 27 L21 32" fill="none" stroke="{roller}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>')
        body.append(f'<path d="M30 33 H40" stroke="{ink}" stroke-width="2.6" stroke-linecap="round"/>')
        for y, w in ((40, 22), (45, 16)):
            body.append(f'<path d="M20 {y} H{20 + w}" stroke="{ink}" stroke-width="1.6" stroke-linecap="round" opacity="0.6"/>')
    elif lines == "seal":
        for y, w in ((18, 26), (23, 22), (28, 25), (33, 18)):
            body.append(f'<path d="M20 {y} H{20 + w}" stroke="{ink}" stroke-width="1.8" stroke-linecap="round" opacity="0.75"/>')
        body.append(seal_svg(38, 44, 8, p["seal"]))
    return _svg("".join(body), defs)


def seal_svg(cx, cy, r, colour):
    """A wax seal with a flame stamped into it."""
    import math
    blob = []
    for k in range(16):
        a = math.tau * k / 16
        rr = r * (1.0 if k % 2 == 0 else 0.9)
        blob.append(f"{cx + rr * math.cos(a):.2f} {cy + rr * math.sin(a):.2f}")
    s = r / 8
    flame = (f"M{cx} {cy - 5 * s} C{cx + 4 * s} {cy - 1 * s} {cx + 3.5 * s} {cy + 4 * s} {cx} {cy + 4.5 * s} "
             f"C{cx - 3.5 * s} {cy + 4 * s} {cx - 4 * s} {cy} {cx - 1.2 * s} {cy - 2 * s} "
             f"C{cx - 1 * s} {cy} {cx} {cy + 0.5 * s} {cx} {cy - 5 * s}Z")
    return (f'<path d="M{" L".join(blob)}Z" fill="{colour}"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r * 0.72:.2f}" fill="none" stroke="{c.darken(colour, 0.3)}" stroke-width="{s:.2f}"/>'
            f'<path d="{flame}" fill="{c.darken(colour, 0.35)}"/>')


def image(p):
    frame, sky = c.darken(p["accent"], 0.3), c.mix(p["accent_alt"], "#ffffff", 0.35)
    defs = _grad("sky", sky, c.mix(p["accent"], "#ffffff", 0.55))
    return _svg(
        f'<rect x="6" y="12" width="52" height="40" rx="4" fill="{frame}"/>'
        f'<rect x="10" y="16" width="44" height="32" fill="url(#sky)"/>'
        f'<circle cx="44" cy="24" r="4.5" fill="{p["accent_alt"]}"/>'
        f'<path d="M10 48 L24 30 L33 40 L39 34 L54 48 Z" fill="{c.darken(p["accent"], 0.1)}"/>'
        f'<path d="M20 26 q3 -3 6 0 q3 -3 6 0" fill="none" stroke="{frame}" stroke-width="1.5" stroke-linecap="round"/>',
        defs)


def config(p):
    """A stone tablet with a gear carved into it."""
    import math
    stone = c.mix("#8d8a86", p["accent"], 0.15)
    teeth = []
    for k in range(8):
        a = math.tau * k / 8
        teeth.append(f'<rect x="-2.6" y="-13" width="5.2" height="6" rx="1" transform="translate(32 34) rotate({math.degrees(a):.1f})"/>')
    return _svg(
        f'<path d="M12 10 Q12 6 16 6 H48 Q52 6 52 10 V56 Q52 58 50 58 H14 Q12 58 12 56 Z" fill="{stone}"/>'
        f'<path d="M12 10 Q12 6 16 6 H48 Q52 6 52 10 V14 H12 Z" fill="{c.lighten(stone, 0.2)}"/>'
        f'<g fill="{p["accent"]}">{"".join(teeth)}<circle cx="32" cy="34" r="9"/></g>'
        f'<circle cx="32" cy="34" r="3.5" fill="{stone}"/>'
        f'<path d="M18 50 H46" stroke="{c.darken(stone, 0.3)}" stroke-width="2" stroke-linecap="round"/>')


WING = ("M10 44 C14 30 24 16 40 10 C44 9 50 10 54 13 L50 16 C52 20 52 25 50 30 C46 28 42 28 40 31 "
        "C37 29 33 30 31 34 C28 32 24 33 22 38 C18 37 13 40 10 44 Z")


def settings_icon(p):
    defs = _grad("disc", c.lighten(p["accent"], 0.1), c.darken(p["accent"], 0.3))
    return _svg(
        f'<circle cx="32" cy="32" r="29" fill="url(#disc)"/>'
        f'<circle cx="32" cy="32" r="25" fill="none" stroke="{p["accent_alt"]}" stroke-width="2.5"/>'
        f'<path d="{WING}" transform="translate(4 6) scale(0.87)" fill="{p["accent_alt"]}"/>'
        f'<path d="M14 44 C18 34 26 24 38 18" transform="translate(4 6) scale(0.87)" fill="none" '
        f'stroke="{c.darken(p["accent"], 0.35)}" stroke-width="2" stroke-linecap="round"/>', defs)


def map_icon(p):
    """A folded parchment map with a dragon-shaped continent and a dashed flight path."""
    defs = _grad("sheet", "#fbf1d6", "#e3c98f")
    land = c.mix(p["accent"], "#6f8f3a", 0.35)
    body = (
        '<path d="M6 12 L22 7 L42 12 L58 7 V52 L42 57 L22 52 L6 57 Z" fill="url(#sheet)" '
        'stroke="#a8864c" stroke-width="1.2" stroke-linejoin="round"/>'
        '<path d="M22 7 V52 M42 12 V57" stroke="#b89a5e" stroke-width="1" opacity="0.8"/>'
        '<path d="M22 7 L42 12 V57 L22 52 Z" fill="#000" opacity="0.07"/>'
        f'<path d="M12 22 C16 16 26 15 30 19 C34 14 44 13 50 18 C46 20 42 22 44 26 C50 27 53 33 49 38 '
        f'C45 42 38 40 36 44 C33 49 26 49 22 45 C17 46 12 42 14 37 C10 33 11 27 15 26 C12 25 11 24 12 22 Z" '
        f'fill="{land}" stroke="{c.darken(land, 0.35)}" stroke-width="1"/>'
        '<path d="M18 30 C24 26 30 34 36 29 S46 26 47 33" fill="none" stroke="#2e1f12" '
        'stroke-width="1.8" stroke-dasharray="3 2.4" stroke-linecap="round"/>'
        f'<circle cx="47" cy="33" r="2.8" fill="{p["seal"]}" stroke="#2e1f12" stroke-width="1.2"/>'
        f'<path d="M50 44 L52 48 L50 52 L48 48 Z" fill="{p["accent_alt"]}" stroke="#5a4127" stroke-width="0.6"/>'
    )
    return _svg(body, defs)


def logo_icon():
    """The OS emblem (artwork/logo.png, drawn by scripts/make-artwork.py) as a scalable icon, or None
    if the artwork hasn't been drawn."""
    path = paths.ARTWORK / "logo.png"
    if not path.is_file():
        return None
    data = base64.b64encode(path.read_bytes()).decode()
    return _svg(f'<image width="64" height="64" href="data:image/png;base64,{data}"/>')


def write_icon(theme_dir, context, names, svg_text):
    folder_ = Path(theme_dir) / "scalable" / context
    folder_.mkdir(parents=True, exist_ok=True)
    first, *aliases = names
    (folder_ / f"{first}.svg").write_text(svg_text)
    for name in aliases:
        link = folder_ / f"{name}.svg"
        link.unlink(missing_ok=True)
        link.symlink_to(f"{first}.svg")


def index_theme(name, comment, inherits):
    return textwrap.dedent(f"""\
    [Icon Theme]
    Name={name}
    Comment={comment}
    Inherits={inherits}
    Directories=scalable/places,scalable/mimetypes,scalable/apps

    [scalable/places]
    Context=Places
    Size=64
    MinSize=16
    MaxSize=512
    Type=Scalable

    [scalable/mimetypes]
    Context=MimeTypes
    Size=64
    MinSize=16
    MaxSize=512
    Type=Scalable

    [scalable/apps]
    Context=Applications
    Size=64
    MinSize=16
    MaxSize=512
    Type=Scalable
    """)


def _colours(tribe):
    pal = palette.of(tribe)
    return {"accent": pal.accent, "accent_alt": pal.accent_alt, "seal": pal.seal}


def write(tribe, theme_dir):
    theme_dir = Path(theme_dir)
    p = _colours(tribe)
    base = "elementary-xfce-dark" if tribe.dark else "elementary-xfce"
    theme_dir.mkdir(parents=True, exist_ok=True)
    (theme_dir / "index.theme").write_text(index_theme(
        tribe.icon_theme, f"Wings of Fire OS icons for the {tribe.name}s",
        f"{base},elementary-xfce,Adwaita,hicolor"))
    write_icon(theme_dir, "places", FOLDER_NAMES, folder(p, tribe.pattern))
    write_icon(theme_dir, "places", OPEN_FOLDER_NAMES, folder(p, tribe.pattern, open_=True))
    for name, emblem in SPECIAL_FOLDERS.items():
        svg_text = trash(p, tribe.pattern) if emblem == "trash" else folder(p, tribe.pattern, emblem)
        write_icon(theme_dir, "places", (name,), svg_text)
    write_icon(theme_dir, "mimetypes", TEXT_NAMES, scroll(p))
    write_icon(theme_dir, "mimetypes", SCRIPT_NAMES, scroll(p, "script"))
    write_icon(theme_dir, "mimetypes", IMAGE_NAMES, image(p))
    write_icon(theme_dir, "mimetypes", CONFIG_NAMES, config(p))
    _write_apps(theme_dir, p)


def _write_apps(theme_dir, p):
    write_icon(theme_dir, "apps", ("wof-scroll", "accessories-text-editor", "org.xfce.mousepad"), scroll(p, "seal"))
    write_icon(theme_dir, "apps", ("pyrrhia-settings",), settings_icon(p))
    write_icon(theme_dir, "apps", ("wof-map",), map_icon(p))
    logo = logo_icon()
    if logo:
        write_icon(theme_dir, "apps", LOGO_NAMES, logo)


def write_app_icons(hicolor_dir):
    """Fire-coloured app icons for when no tribe icon theme is active."""
    hicolor_dir = Path(hicolor_dir)
    write_icon(hicolor_dir, "apps", ("wof-scroll",), scroll(FIRE, "seal"))
    write_icon(hicolor_dir, "apps", ("pyrrhia-settings",), settings_icon(FIRE))
    write_icon(hicolor_dir, "apps", ("wof-map",), map_icon(FIRE))
    logo = logo_icon()
    if logo:
        write_icon(hicolor_dir, "apps", ("wingsoffire-logo",), logo)
