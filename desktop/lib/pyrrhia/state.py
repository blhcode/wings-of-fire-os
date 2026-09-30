"""The user's tribe choices, stored in ~/.config/wingsoffire/state.json."""
import json
from dataclasses import asdict, dataclass, field

from . import paths, tribes


@dataclass
class State:
    tribe: str = ""
    wallpaper: str = ""
    components: dict = field(default_factory=dict)

    def enabled(self, component_id, default=True):
        return self.components.get(component_id, default)


def state_file():
    return paths.config_dir() / "state.json"


def exists():
    return state_file().is_file()


def load():
    try:
        data = json.loads(state_file().read_text())
    except (OSError, ValueError):
        data = {}
    state = State(**{k: v for k, v in data.items() if k in State.__dataclass_fields__})
    if not state.tribe:
        state.tribe = tribes.default_id()
    return state


def save(state):
    path = state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(state), indent=2) + "\n")
    tmp.replace(path)
