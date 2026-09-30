"""Loading tribe definitions.

A tribe is a directory containing ``tribe.toml`` and a ``wallpapers/`` folder. System tribes live
in /usr/share/wingsoffire/tribes; a user can add tribes, or extra wallpapers for existing tribes,
under ~/.local/share/wingsoffire/tribes/<id>/.
"""
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import colors, paths

REQUIRED_COLOURS = ("accent", "accent_alt", "background", "surface", "text")
PATTERNS = ("stars", "waves", "embers", "frost", "dunes", "leaves", "hex", "silk", "mud", "rain")
WALLPAPER_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".svg"}


class TribeError(ValueError):
    pass


@dataclass(frozen=True)
class Tribe:
    id: str
    name: str
    realm: str
    description: str
    dark: bool
    pattern: str
    colors: dict
    editor: dict
    sounds: dict
    terminal: dict
    default_wallpaper: str
    directory: Path
    extra_dirs: tuple = field(default=())

    @property
    def theme_name(self):
        return f"WoF-{self.name}"

    @property
    def icon_theme(self):
        return f"WoF-{self.name}"

    @property
    def sound_theme(self):
        return f"wof-{self.id}"

    def wallpapers(self):
        """All wallpapers, the tribe's own first, then the user's additions."""
        found = []
        for directory in (self.directory, *self.extra_dirs):
            folder = directory / "wallpapers"
            if folder.is_dir():
                found += sorted(p for p in folder.iterdir() if p.suffix.lower() in WALLPAPER_SUFFIXES)
        return sorted(found, key=is_placeholder)

    def has_own_wallpaper(self):
        return any(not is_placeholder(p) for p in self.wallpapers())

    def wallpaper(self, name=None):
        options = self.wallpapers()
        for wanted in (name, self.default_wallpaper):
            for path in options:
                if wanted and path.name == wanted:
                    return path
        return options[0] if options else None


def is_placeholder(path):
    return Path(path).stem.startswith("placeholder")


def load(directory, extra_dirs=()):
    directory = Path(directory)
    try:
        data = tomllib.loads((directory / "tribe.toml").read_text())
    except (OSError, tomllib.TOMLDecodeError) as err:
        raise TribeError(f"{directory}: {err}") from err

    def need(table, key):
        if key not in table:
            raise TribeError(f"{directory}/tribe.toml: missing '{key}'")
        return table[key]

    colours = dict(need(data, "colors"))
    for key in list(REQUIRED_COLOURS) + [k for k in colours if k not in REQUIRED_COLOURS]:
        try:
            colors.parse(need(colours, key))
        except (ValueError, AttributeError) as err:
            raise TribeError(f"{directory}/tribe.toml: colour '{key}': {err}") from err
    if "seal" in data.get("editor", {}):
        try:
            colors.parse(data["editor"]["seal"])
        except (ValueError, AttributeError) as err:
            raise TribeError(f"{directory}/tribe.toml: editor seal colour: {err}") from err
    pattern = data.get("pattern", "stars")
    if pattern not in PATTERNS:
        raise TribeError(f"{directory}/tribe.toml: unknown pattern '{pattern}' (one of {', '.join(PATTERNS)})")
    editor = dict(data.get("editor", {}))
    editor.setdefault("seal", colors.darken(colours["accent"], 0.25))
    return Tribe(
        id=directory.name,
        name=need(data, "name"),
        realm=data.get("realm", "Pyrrhia"),
        description=data.get("description", ""),
        dark=bool(data.get("dark", True)),
        pattern=pattern,
        colors=colours,
        editor=editor,
        sounds=dict(data.get("sounds", {})),
        terminal=dict(data.get("terminal", {})),
        default_wallpaper=data.get("default_wallpaper", ""),
        directory=directory,
        extra_dirs=tuple(Path(d) for d in extra_dirs),
    )


def all_tribes():
    """Tribes by id, sorted by name. A user tribe with the same id as a system one replaces it."""
    roots = [paths.SYSTEM_TRIBES, paths.user_tribes()]
    directories = {}
    for root in roots:
        if root.is_dir():
            for d in root.iterdir():
                if d.is_dir():
                    directories.setdefault(d.name, []).append(d)
    tribes = {}
    for tribe_id, dirs in directories.items():
        with_toml = [d for d in dirs if (d / "tribe.toml").is_file()]
        if not with_toml:
            continue
        main = with_toml[-1]
        try:
            tribes[tribe_id] = load(main, [d for d in dirs if d != main])
        except TribeError as err:
            print(f"wingsoffire: skipping tribe: {err}", file=sys.stderr)
    return dict(sorted(tribes.items(), key=lambda item: item[1].name))


def get(tribe_id):
    tribes = all_tribes()
    if tribe_id not in tribes:
        raise TribeError(f"unknown tribe '{tribe_id}' (available: {', '.join(tribes)})")
    return tribes[tribe_id]


def default_id():
    try:
        return paths.DEFAULT_TRIBE_FILE.read_text().strip()
    except OSError:
        return "seawing"
