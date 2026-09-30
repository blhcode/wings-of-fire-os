"""Thin wrappers around the desktop's settings tools (xfconf-query, gsettings, pw-play)."""
import shutil
import subprocess


class CommandError(RuntimeError):
    pass


def run(*args, check=True):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as err:
        raise CommandError(f"{args[0]}: {err}") from err
    if check and result.returncode != 0:
        raise CommandError(f"{' '.join(args)}: {result.stderr.strip() or f'exit {result.returncode}'}")
    return result.stdout


def have(program):
    return shutil.which(program) is not None


def _xfconf_type(value):
    if isinstance(value, bool):
        return "bool", "true" if value else "false"
    if isinstance(value, int):
        return "int", str(value)
    return "string", str(value)


def _need_xfconf():
    if not have("xfconf-query"):
        raise CommandError("xfconf-query not found (this needs the Wings of Fire OS XFCE desktop)")


def xfconf_set(channel, prop, value):
    _need_xfconf()
    kind, text = _xfconf_type(value)
    run("xfconf-query", "-c", channel, "-p", prop, "-n", "-t", kind, "-s", text)


def xfconf_get(channel, prop, default=None):
    _need_xfconf()
    result = subprocess.run(["xfconf-query", "-c", channel, "-p", prop], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else default


def xfconf_list(channel):
    _need_xfconf()
    result = subprocess.run(["xfconf-query", "-c", channel, "-l"], capture_output=True, text=True)
    return result.stdout.split() if result.returncode == 0 else []


def gsettings_set(schema, key, value):
    if not have("gsettings"):
        return False
    schemas = run("gsettings", "list-schemas", check=False).split()
    if schema not in schemas:
        return False
    run("gsettings", "set", schema, key, value)
    return True


def play_sound(path):
    for player in ("pw-play", "paplay", "aplay"):
        if have(player):
            subprocess.Popen([player, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
    return False


def monitor_names():
    """Connector names (e.g. "Virtual-1", "HDMI-A-1") as xfdesktop uses them."""
    if not have("xrandr"):
        return []
    names = []
    for line in run("xrandr", "--listmonitors", check=False).splitlines()[1:]:
        parts = line.split()
        if parts:
            names.append(parts[-1])
    return names
