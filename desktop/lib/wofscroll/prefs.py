"""Scroll editor preferences, stored in ~/.config/wingsoffire/scroll.json."""
import json
from dataclasses import asdict, dataclass, fields

from pyrrhia import paths


@dataclass
class Prefs:
    font: str = "EB Garamond 14"
    wrap: bool = True
    line_numbers: bool = False
    highlight_line: bool = False
    animations: bool = True
    seal: bool = True
    zoom: int = 100
    width: int = 860
    height: int = 920


def _file():
    return paths.config_dir() / "scroll.json"


def load():
    try:
        data = json.loads(_file().read_text())
    except (OSError, ValueError):
        data = {}
    names = {f.name for f in fields(Prefs)}
    return Prefs(**{k: v for k, v in data.items() if k in names})


def save(prefs):
    path = _file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(prefs), indent=2) + "\n")
    tmp.replace(path)
