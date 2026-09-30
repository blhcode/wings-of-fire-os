"""Continent data for the Map app.

Each continent is a folder under /usr/share/wingsoffire/maps holding ``map.json`` (geography in
normalised 0..1 coordinates, origin south-west, +y north), ``relief.png`` (shaded land, transparent
sea) and ``height.png`` (elevation + 1000 m, high byte in red, low byte in green). A continent may
also carry its own 3D map in ``3d/index.html``; the others use the shared overview viewer.
"""
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from pyrrhia import paths

MILES_TO_M = 1609.344
FEET_PER_M = 3.28084
# Mixed-party dragon flight, the same figure the maps are scaled with.
DAILY_FLIGHT_MILES = 240
ORDER = ("pyrrhia", "pantala")


def maps_dir():
    return paths.DATA_DIR / "maps"


@dataclass
class Landmark:
    id: str
    name: str
    blurb: str
    pos: tuple
    group: str
    rank: int
    altitude: float = 0.0


@dataclass
class Region:
    id: str
    name: str
    tribe: str
    colour: str
    polygon: list
    anchor: tuple = None


@dataclass
class Continent:
    id: str
    name: str
    directory: Path
    world_w_m: float
    world_h_m: float
    land: list
    regions: list
    rivers: list
    lakes: list
    routes: list
    groups: list
    landmarks: list
    source: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def relief_path(self):
        return self.directory / "relief.png"

    @property
    def height_path(self):
        return self.directory / "height.png"

    @property
    def own_3d(self):
        return (self.directory / "3d" / "index.html").is_file()

    def group(self, group_id):
        return next((g for g in self.groups if g["id"] == group_id), None)

    def landmark(self, key):
        key = key.lower()
        return next((m for m in self.landmarks if m.id == key or m.name.lower() == key), None)

    def region_at(self, nx, ny):
        """Region containing the point, if it is on land."""
        if not on_land(self, nx, ny):
            return None
        for region in self.regions:
            if len(region.polygon) >= 3 and point_in_polygon(nx, ny, region.polygon):
                return region
        return None

    def distance_miles(self, a, b):
        dx = (a[0] - b[0]) * self.world_w_m
        dy = (a[1] - b[1]) * self.world_h_m
        return math.hypot(dx, dy) / MILES_TO_M

    def nearest_landmark(self, nx, ny, max_norm=None, visible=None):
        best, best_d = None, None
        for m in self.landmarks:
            if visible is not None and not visible(m):
                continue
            d = math.hypot((m.pos[0] - nx) * self.world_w_m, (m.pos[1] - ny) * self.world_h_m) / self.world_w_m
            if best_d is None or d < best_d:
                best, best_d = m, d
        if max_norm is not None and (best_d is None or best_d > max_norm):
            return None
        return best


class MapError(Exception):
    pass


def load(directory):
    directory = Path(directory)
    try:
        data = json.loads((directory / "map.json").read_text())
    except (OSError, ValueError) as e:
        raise MapError(f"{directory.name}: {e}") from e
    try:
        world = data["world"]
        return Continent(
            id=directory.name,
            name=data["name"],
            directory=directory,
            world_w_m=float(world["width_m"]),
            world_h_m=float(world["height_m"]),
            land=[[tuple(p) for p in poly] for poly in data["land"]],
            regions=[Region(r["id"], r["name"], r.get("tribe", ""), r.get("label", "#ffffff"),
                            [tuple(p) for p in r.get("polygon", [])],
                            tuple(r["anchor"]) if r.get("anchor") else None) for r in data.get("regions", [])],
            rivers=data.get("rivers", []),
            lakes=data.get("lakes", []),
            routes=data.get("routes", []),
            groups=data.get("groups", []),
            landmarks=[Landmark(m["id"], m["name"], m.get("blurb", ""), tuple(m["pos"]), m.get("group", ""),
                                int(m.get("rank", 2)), float(m.get("altitude", 0))) for m in data.get("landmarks", [])],
            source=data.get("source", ""),
        )
    except (KeyError, TypeError, ValueError) as e:
        raise MapError(f"{directory.name}: bad map.json ({e})") from e


def all_continents(root=None):
    root = Path(root) if root else maps_dir()
    found = []
    if root.is_dir():
        for d in root.iterdir():
            if (d / "map.json").is_file():
                try:
                    found.append(load(d))
                except MapError as e:
                    print(f"wof-map: skipping {e}", flush=True)
    rank = {cid: i for i, cid in enumerate(ORDER)}
    return sorted(found, key=lambda c: (rank.get(c.id, len(ORDER)), c.name))


def point_in_polygon(x, y, poly):
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def on_land(continent, nx, ny):
    if not any(point_in_polygon(nx, ny, poly) for poly in continent.land):
        return False
    return not any(point_in_polygon(nx, ny, lake["polygon"]) for lake in continent.lakes)


def region_anchors(continent, is_land, steps=96):
    """Place each region's label at the middle of the land it covers.

    ``is_land(nx, ny)`` is a fast land test (the app samples the relief's alpha). The anchor is the
    land point inside the region that is furthest from the region's other edges, found on a grid.
    """
    aspect = continent.world_h_m / continent.world_w_m
    cols, rows = steps, max(8, round(steps * aspect))
    for region in continent.regions:
        if len(region.polygon) < 3:
            continue  # label-only region: keeps the anchor given in map.json
        cells = set()
        for j in range(rows):
            ny = 1 - (j + 0.5) / rows
            for i in range(cols):
                nx = (i + 0.5) / cols
                if is_land(nx, ny) and point_in_polygon(nx, ny, region.polygon):
                    cells.add((i, j))
        if not cells:
            region.anchor = None
            continue
        # Grid distance transform: peel the region's cells layer by layer.
        depth = {}
        frontier = {c for c in cells if any((c[0] + dx, c[1] + dy) not in cells
                                            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))}
        remaining = set(cells)
        level = 0
        while frontier:
            for c in frontier:
                depth[c] = level
            remaining -= frontier
            level += 1
            frontier = {c for c in remaining if any((c[0] + dx, c[1] + dy) not in remaining
                                                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))}
        deepest = max(depth.values())
        core = [c for c, d in depth.items() if d == deepest]
        ci = sum(c[0] for c in core) / len(core)
        cj = sum(c[1] for c in core) / len(core)
        best = min(core, key=lambda c: (c[0] - ci) ** 2 + (c[1] - cj) ** 2)
        region.anchor = ((best[0] + 0.5) / cols, 1 - (best[1] + 0.5) / rows)


class HeightField:
    """Elevation lookup over a height.png decoded into raw bytes."""

    def __init__(self, pixels, width, height, rowstride, channels):
        self.pixels, self.width, self.height = pixels, width, height
        self.rowstride, self.channels = rowstride, channels

    def metres(self, nx, ny):
        x = min(self.width - 1, max(0, int(nx * (self.width - 1) + 0.5)))
        y = min(self.height - 1, max(0, int((1 - ny) * (self.height - 1) + 0.5)))
        i = y * self.rowstride + x * self.channels
        return self.pixels[i] * 256 + self.pixels[i + 1] - 1000


def format_miles(miles):
    if miles < 10:
        return f"{miles:.1f} miles"
    return f"{round(miles):,} miles"


def flight_time(miles):
    days = miles / DAILY_FLIGHT_MILES
    if days < 0.4:
        hours = max(1, round(days * 12))
        return f"about {hours} hour{'s' if hours != 1 else ''} of flying"
    if days < 1.25:
        return "about a day\u2019s flight"
    return f"about {days:.1f} days\u2019 flight".replace(".0 ", " ")


def format_height(metres):
    if metres <= 0:
        return "sea level"
    return f"{round(metres):,} m ({round(metres * FEET_PER_M):,} ft)"


def nice_scale(miles_per_px, target_px=140):
    """A round distance for the scale bar and its length in pixels."""
    raw = miles_per_px * target_px
    magnitude = 10 ** math.floor(math.log10(raw))
    for step in (1, 2, 5, 10):
        if step * magnitude >= raw * 0.6:
            miles = step * magnitude
            break
    return miles, miles / miles_per_px
