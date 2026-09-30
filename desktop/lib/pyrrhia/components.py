"""The parts of the desktop a tribe can theme. Each can be switched on or off in Pyrrhia Settings.

To add a component: write a function taking (tribe, wallpaper_path) and register it in COMPONENTS.
"""
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import firefox as firefox_mod
from . import paths, system
from .assets import terminal as terminal_assets

LOGIN_HELPER = "/usr/libexec/wingsoffire/wof-login-theme"


@dataclass(frozen=True)
class Component:
    id: str
    label: str
    description: str
    apply: Callable
    session: bool = True  # re-applied at every login (cheap, keeps new monitors/profiles themed)


def wallpaper(tribe, wall):
    if wall is None:
        return "no wallpaper for this tribe"
    # xfdesktop only reads monitor<connector>/workspace<n>; Debian's defaults also leave old-style
    # monitor0/monitor1 keys, which are set too but aren't enough on their own.
    props = {p for p in system.xfconf_list("xfce4-desktop") if p.endswith("/last-image")}
    try:
        workspaces = int(system.xfconf_get("xfwm4", "/general/workspace_count", "4"))
    except ValueError:
        workspaces = 4
    monitors = system.monitor_names() or ([] if props else ["0"])
    props |= {f"/backdrop/screen0/monitor{m}/workspace{w}/last-image" for m in monitors for w in range(workspaces)}
    for prop in sorted(props):
        system.xfconf_set("xfce4-desktop", prop, str(wall))
        system.xfconf_set("xfce4-desktop", prop.replace("/last-image", "/image-style"), 5)
    return f"{Path(wall).name} on {len(props)} desktop(s)"


def colours(tribe, wall):
    system.xfconf_set("xsettings", "/Net/ThemeName", tribe.theme_name)
    system.xfconf_set("xfce4-notifyd", "/theme", tribe.theme_name)
    return tribe.theme_name


def icons(tribe, wall):
    system.xfconf_set("xsettings", "/Net/IconThemeName", tribe.icon_theme)
    return tribe.icon_theme


def terminal(tribe, wall):
    for prop, value in terminal_assets.colours(tribe).items():
        system.xfconf_set("xfce4-terminal", f"/{prop}", value)
    return f"{tribe.name} colours"


def firefox(tribe, wall):
    touched = firefox_mod.apply(tribe)
    note = " (restart Firefox to see it)" if firefox_mod.running() else ""
    return f"{len(touched)} profile(s){note}"


def editor(tribe, wall):
    # The Scroll editor follows state.json by itself; Mousepad needs telling.
    system.gsettings_set("org.xfce.mousepad.preferences.view", "color-scheme", f"wof-{tribe.id}")
    return f"wof-{tribe.id}"


def sounds(tribe, wall):
    system.xfconf_set("xsettings", "/Net/SoundThemeName", tribe.sound_theme)
    system.xfconf_set("xsettings", "/Net/EnableEventSounds", True)
    return tribe.sound_theme


def login(tribe, wall):
    """The login screen is shared by every user, so this goes through a small root helper that only
    accepts system tribes and their own wallpapers."""
    if not Path(tribe.directory).is_relative_to(paths.SYSTEM_TRIBES):
        return "skipped: custom tribes can't theme the login screen"
    name = Path(wall).name if wall and Path(wall).parent == tribe.directory / "wallpapers" else ""
    result = subprocess.run(["pkexec", LOGIN_HELPER, tribe.id, name], capture_output=True, text=True)
    if result.returncode != 0:
        raise system.CommandError(result.stderr.strip() or "not authorised")
    return "updated"


COMPONENTS = [
    Component("wallpaper", "Wallpaper", "Desktop background", wallpaper),
    Component("colours", "Colours", "Window, panel and notification accent colours", colours),
    Component("icons", "Icons", "Folders, scroll text files and other file icons", icons),
    Component("terminal", "Terminal", "Terminal colours", terminal),
    Component("firefox", "Firefox", "Browser toolbar and new tab page", firefox),
    Component("editor", "Text editor", "Scroll editor wax seal and Mousepad colours", editor),
    Component("sounds", "Sounds", "System sounds", sounds),
    Component("login", "Login screen", "Login background and colours (for everyone on this PC)", login,
              session=False),
]
BY_ID = {c.id: c for c in COMPONENTS}


def apply(tribe, wall, enabled, only=None, progress=None):
    """Apply every enabled component. Returns [(component, ok, message)]."""
    results = []
    for comp in COMPONENTS:
        if only is not None and comp.id not in only:
            continue
        if not enabled(comp.id):
            continue
        if progress:
            progress(comp)
        try:
            results.append((comp, True, comp.apply(tribe, wall) or ""))
        except (system.CommandError, OSError) as err:
            results.append((comp, False, str(err)))
    return results
