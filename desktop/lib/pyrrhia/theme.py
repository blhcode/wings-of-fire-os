"""Switching tribes: save the choice, then apply every enabled component."""
from . import components, paths, state as state_mod, system, tribes


def choose(tribe_id, wallpaper=None, component_choices=None):
    """Record a tribe choice. Returns the new state (not yet applied)."""
    tribe = tribes.get(tribe_id)
    state = state_mod.load()
    if tribe_id != state.tribe and wallpaper is None:
        state.wallpaper = ""
    state.tribe = tribe.id
    if wallpaper is not None:
        state.wallpaper = wallpaper
    if component_choices:
        state.components.update(component_choices)
    state_mod.save(state)
    return state


def apply(state=None, only=None, progress=None, chime=True):
    state = state or state_mod.load()
    tribe = tribes.get(state.tribe)
    wall = tribe.wallpaper(state.wallpaper or None)
    results = components.apply(tribe, wall, state.enabled, only=only, progress=progress)
    if chime and state.enabled("sounds") and (only is None or "sounds" in only):
        sound = tribe_sound(tribe, "complete")
        if sound:
            system.play_sound(sound)
    return tribe, results


def tribe_sound(tribe, event):
    for root in (paths.DATA_DIR.parent / "sounds", paths.data_home() / "sounds"):
        path = root / tribe.sound_theme / "stereo" / f"{event}.wav"
        if path.exists():
            return path
    return None


def session_start():
    """Run at login. First login: apply the default tribe. Later: theme what's new since last time
    (monitors, workspaces, Firefox profiles) without undoing changes made in XFCE's own settings."""
    first = not state_mod.exists()
    state = state_mod.load()
    if first:
        state_mod.save(state)
        return apply(state, only=[c.id for c in components.COMPONENTS if c.session], chime=False)
    tribe, results = apply(state, only=["firefox"], chime=False)
    if state.enabled("wallpaper"):
        comp = components.BY_ID["wallpaper"]
        try:
            results.insert(0, (comp, True, components.wallpaper_new_screens(
                tribe, tribe.wallpaper(state.wallpaper or None))))
        except (system.CommandError, OSError) as err:
            results.insert(0, (comp, False, str(err)))
    return tribe, results
