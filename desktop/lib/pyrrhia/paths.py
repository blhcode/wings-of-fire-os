"""Filesystem locations. WOF_DATA overrides the system data directory (used when running from the
source tree)."""
import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("WOF_DATA", "/usr/share/wingsoffire"))
SYSTEM_TRIBES = DATA_DIR / "tribes"
ARTWORK = DATA_DIR / "artwork"
DEFAULT_TRIBE_FILE = DATA_DIR / "default-tribe"
# Every system tribe's wallpapers linked into one folder (/usr/share/backgrounds/wingsoffire).
BACKGROUNDS = DATA_DIR.parent / "backgrounds" / DATA_DIR.name


def home():
    return Path(os.environ.get("HOME", Path.home()))


def config_home():
    return Path(os.environ.get("XDG_CONFIG_HOME") or home() / ".config")


def data_home():
    return Path(os.environ.get("XDG_DATA_HOME") or home() / ".local/share")


def config_dir():
    return config_home() / "wingsoffire"


def user_tribes():
    return data_home() / "wingsoffire/tribes"
