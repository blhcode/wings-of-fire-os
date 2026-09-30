#!/usr/bin/env python3
"""Trace Pantala from the coloured book plate into the same map format the
Pyrrhia export uses (pantala.json + relief.png + height.png).

    trace-pantala.py PLATE.png OUTDIR [--debug DIR]

PLATE is the coloured Pantala map (3625x2831, "PantalaColored"). Everything
positional below is measured in that plate's pixels. Normalised output
coordinates follow the Pyrrhia map: 0..1 inside the map frame, origin at the
south-west corner, +y north.

Needs numpy, scipy, scikit-image and Pillow.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from skimage import graph, measure, morphology

# Inner edge of the plate's red frame.
FRAME = (95, 92, 3533, 2738)
FRAME_W = FRAME[2] - FRAME[0]
FRAME_H = FRAME[3] - FRAME[1]
# Output raster width (matches the Pyrrhia relief).
OUT_W = 2192

MILES_TO_M = 1609.344
# Same flight model as the Pyrrhia map: ~240 miles a day. The Lost Continent
# puts Cicada Hive -> Wasp Hive at two to three days.
CICADA_TO_WASP_MILES = 2.5 * 240

# Plate areas that are drawn in land colours but are sea: the two compass
# roses and the "PANTALA" cartouche.
SEA_OVERRIDES = [
    ("rect", (95, 1520, 760, 2738)),
    ("circle", (290, 1930, 430)),
    ("rect", (330, 2330, 1110, 2630)),
    ("circle", (3150, 1165, 150)),
    ("rect", (2580, 1330, 3010, 1520)),
    ("circle", (3330, 2420, 130)),
]

HIVES = {
    "tsetse": (1490, 740),
    "yellowjacket": (1900, 740),
    "wasp": (2015, 1000),
    "vinegaroon": (1140, 1275),
    "jewel": (2090, 1425),
    "hornet": (1290, 1625),
    "bloodworm": (1990, 1800),
    "cicada": (1310, 2000),
    "mantis": (1625, 2275),
}

# Silk bridges between Hives, as drawn on the plate.
BRIDGES = [
    ("tsetse", "yellowjacket"), ("yellowjacket", "wasp"), ("wasp", "jewel"),
    ("jewel", "bloodworm"), ("bloodworm", "mantis"), ("mantis", "cicada"),
    ("cicada", "hornet"), ("hornet", "vinegaroon"), ("vinegaroon", "tsetse"),
]

# The same Hives on the Guide to the Dragon World map (819 px wide copy),
# used to carry over places that only the Guide labels.
GUIDE_HIVES = {
    "tsetse": (338, 128), "yellowjacket": (490, 125), "wasp": (508, 172),
    "vinegaroon": (268, 213), "jewel": (522, 238), "hornet": (297, 262),
    "bloodworm": (502, 295), "cicada": (298, 338), "mantis": (440, 375),
}
GUIDE_PLACES = {
    "sinkhole": (360, 203),
}

# Rivers: a few waypoints each (plate pixels); the traced course follows the plate's ink between them.
RIVERS = [
    ("savanna-river", "", [
        [(1761, 1422), (1816, 1485), (1784, 1720), (1698, 1846), (1620, 1987), (1585, 2003)],
        [(1761, 1422), (1682, 1375), (1620, 1407)],
    ]),
    ("northern-river", "", [
        [(1484, 371), (1376, 383), (1303, 359), (1231, 383), (1207, 443), (1122, 419), (1050, 455), (990, 419)],
    ]),
    ("bloodworm-river", "", [
        [(1890, 2170), (2100, 2160), (2340, 2130)],
    ]),
    ("gullet-river", "Gullet River", [
        [(2524, 440), (2608, 512)],
    ]),
    ("snarling-river", "Snarling River", [
        [(2400, 183), (2446, 267), (2471, 342), (2525, 350), (2546, 400), (2492, 425), (2525, 500),
         (2567, 583), (2633, 633)],
    ]),
]

REGIONS = [
    {
        "id": "savanna",
        "name": "The Savanna",
        "tribe": "HiveWings & SilkWings \u00b7 Queen Wasp",
        "label": "#f2c94c",
        "polygon": [(95, 92), (2500, 92), (2500, 1000), (3150, 1000), (3050, 1600),
                    (2900, 2150), (2100, 2200), (2100, 2738), (95, 2738)],
    },
    {
        "id": "poison-jungle",
        "name": "Poison Jungle",
        "tribe": "LeafWings \u00b7 PoisonWings & SapWings",
        "label": "#7fd06a",
        "polygon": [(2500, 92), (3533, 92), (3533, 1000), (2500, 1000)],
    },
    {
        "id": "dragontail",
        "name": "Dragontail Peninsula",
        "tribe": "Wild lands \u00b7 Lake Scorpion",
        "label": "#e6a8d8",
        "polygon": [(2100, 2738), (2100, 2200), (2900, 2150), (3050, 1600),
                    (3150, 1000), (3533, 1000), (3533, 2738)],
    },
]

GROUPS = [
    {"id": "hive", "label": "Hives", "color": "#f0b43c"},
    {"id": "settlement", "label": "LeafWing villages", "color": "#63d0a0"},
    {"id": "water", "label": "Lakes, rivers & landforms", "color": "#5ab6e8"},
    {"id": "ruin", "label": "Hidden places", "color": "#b184e0"},
]

HIVE_BLURBS = {
    "wasp": "The largest and oldest Hive, seat of Queen Wasp.",
    "cicada": "Blue\u2019s home Hive, in the south-west of the ring.",
    "jewel": "Once Lady Jewel\u2019s Hive; its SilkWings planned to flee to Lake Scorpion.",
    "bloodworm": "Once ruled by Lady Bloodworm, one of Queen Wasp\u2019s sisters.",
}
DEFAULT_HIVE_BLURB = "One of the nine treestuff Hives, linked to its neighbours by silk bridges."

EXTRA_LANDMARKS = [
    # id, name, group, rank, blurb, where
    ("beetle-lake", "Beetle Lake", "water", 1,
     "A large lake on the western \u201cwing\u201d of Pantala.", ("lake", "beetle-lake")),
    ("lake-scorpion", "Lake Scorpion", "water", 1,
     "The scorpion-shaped lake of the Dragontail Peninsula.", ("lake", "lake-scorpion")),
    ("dragonfly-bay", "Dragonfly Bay", "water", 1,
     "East-coast bay where a kraken lived for one rainy season.", ("plate", (2780, 1450))),
    ("abyss", "The Abyss", "ruin", 3,
     "A pit beneath Lake Scorpion that once held the othermind.", ("lake", "lake-scorpion", (30, -18))),
    ("sinkhole", "The Sinkhole", "ruin", 2,
     "A pit in the savanna between the Hives where Blue, Cricket and Swordtail hid.", ("guide", "sinkhole")),
    ("eye-of-the-jungle", "Eye of the Jungle", "water", 3,
     "A pool on the northern edge of the Poison Jungle.", ("plate", (2560, 250))),
    ("den-of-vipers", "Den of Vipers", "water", 3,
     "A dangerous hollow deep in the Poison Jungle.", ("plate", (2600, 330))),
    ("sapwing-village", "SapWing Village", "settlement", 2,
     "Home of the SapWing LeafWings, hidden in the jungle canopy.", ("plate", (2800, 420))),
    ("poisonwing-village", "PoisonWing Village", "settlement", 2,
     "Home of the PoisonWing LeafWings.", ("plate", (2600, 520))),
]


def fit_affine(src: dict, dst: dict) -> np.ndarray:
    keys = sorted(src)
    a = np.array([[src[k][0], src[k][1], 1.0] for k in keys])
    b = np.array([dst[k] for k in keys], float)
    m, *_ = np.linalg.lstsq(a, b, rcond=None)
    return m


class Frame:
    """Plate pixels <-> work raster <-> normalised map coordinates."""

    def __init__(self, work_w: int, work_h: int):
        self.w, self.h = work_w, work_h
        self.sx = work_w / FRAME_W
        self.sy = work_h / FRAME_H

    def plate_to_work(self, x: float, y: float) -> tuple[float, float]:
        return (x - FRAME[0]) * self.sx, (y - FRAME[1]) * self.sy

    def work_to_norm(self, x: float, y: float) -> tuple[float, float]:
        return x / self.w, 1.0 - y / self.h

    def plate_to_norm(self, x: float, y: float) -> tuple[float, float]:
        return self.work_to_norm(*self.plate_to_work(x, y))


def rnd(p) -> list[float]:
    return [round(float(p[0]), 5), round(float(p[1]), 5)]


def classify(plate: Image.Image, frame: Frame) -> np.ndarray:
    """Land mask on the work raster."""
    img = plate.crop(FRAME).resize((frame.w, frame.h), Image.LANCZOS)
    hsv = np.asarray(img.convert("HSV")).astype(int)
    hue, sat = hsv[..., 0] * 360 // 255, hsv[..., 1]
    sea = (hue > 160) & (hue < 230) & (sat > 60)
    land = (hue > 35) & (hue < 140) & (sat > 60)

    override = Image.new("L", (frame.w, frame.h), 0)
    d = ImageDraw.Draw(override)
    for kind, v in SEA_OVERRIDES:
        if kind == "rect":
            x0, y0 = frame.plate_to_work(v[0], v[1])
            x1, y1 = frame.plate_to_work(v[2], v[3])
            d.rectangle([x0, y0, x1, y1], fill=255)
        else:
            cx, cy = frame.plate_to_work(v[0], v[1])
            r = v[2] * frame.sx
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    forced = np.asarray(override) > 0
    sea |= forced
    land &= ~forced

    # Ink, lettering and hatching take the class of the nearest coloured pixel.
    known = sea | land
    iy, ix = ndi.distance_transform_edt(~known, return_distances=False, return_indices=True)
    filled = land[iy, ix]
    return ndi.gaussian_filter(filled.astype(float), 1.5) > 0.5


def split_water(land: np.ndarray, min_lake: int = 3000):
    """Returns (land, ocean, lake labels) with thin channels and specks removed."""
    water = ~land
    opened = morphology.opening(water, morphology.disk(4))
    lab, n = ndi.label(opened)
    edge = set(np.unique(np.r_[lab[0], lab[-1], lab[:, 0], lab[:, -1]])) - {0}
    ocean = np.isin(lab, list(edge))
    sizes = ndi.sum(np.ones_like(lab), lab, range(1, n + 1))
    lakes = np.zeros_like(lab)
    near_ocean = ndi.binary_dilation(ocean, iterations=8)
    lake_id = 0
    for i, size in enumerate(sizes, 1):
        if i in edge:
            continue
        comp = lab == i
        if size >= min_lake:
            lake_id += 1
            lakes[comp] = lake_id
        elif (comp & near_ocean).any():
            ocean |= comp
    solid = ~ocean
    lab_l, nl = ndi.label(solid)
    sizes_l = ndi.sum(np.ones_like(lab_l), lab_l, range(1, nl + 1))
    for i, size in enumerate(sizes_l, 1):
        if size < 150:
            solid[lab_l == i] = False
    return solid, ~solid, lakes


def contour_polys(mask: np.ndarray, tol: float, min_pts: int = 4) -> list[np.ndarray]:
    padded = np.pad(mask.astype(float), 1)
    out = []
    for c in measure.find_contours(padded, 0.5):
        c = c - 1
        s = measure.approximate_polygon(c, tolerance=tol)
        if len(s) >= min_pts:
            out.append(s[:, ::-1])  # (row, col) -> (x, y)
    return out


def ink_cost(plate: Image.Image) -> np.ndarray:
    """Cost of travelling each plate pixel: cheap along dark ink, dear elsewhere."""
    val = np.asarray(plate.crop(FRAME).convert("L")).astype(float)
    val = ndi.gaussian_filter(val, 1.2)
    dark = np.clip((200 - val) / 120, 0, 1)
    return 0.05 + (1 - dark) ** 2


def follow(cost: np.ndarray, waypoints: list[tuple[int, int]], pad: int = 120) -> np.ndarray:
    """Least-cost course through the waypoints, as (x, y) plate pixels inside the frame."""
    h, w = cost.shape
    course = []
    for (x0, y0), (x1, y1) in zip(waypoints, waypoints[1:]):
        a = (y0 - FRAME[1], x0 - FRAME[0])
        b = (y1 - FRAME[1], x1 - FRAME[0])
        r0, r1 = max(0, min(a[0], b[0]) - pad), min(h, max(a[0], b[0]) + pad)
        c0, c1 = max(0, min(a[1], b[1]) - pad), min(w, max(a[1], b[1]) + pad)
        path, _ = graph.route_through_array(cost[r0:r1, c0:c1], (a[0] - r0, a[1] - c0),
                                            (b[0] - r0, b[1] - c0), fully_connected=True, geometric=True)
        pts = [(c + c0, r + r0) for r, c in path]
        course.extend(pts if not course else pts[1:])
    line = np.array(course, float)
    line = ndi.uniform_filter1d(line, size=9, axis=0, mode="nearest")
    return measure.approximate_polygon(line, tolerance=2.5)


def trace_rivers(plate: Image.Image, frame: Frame) -> list[dict]:
    cost = ink_cost(plate)
    rivers = []
    for rid, name, branches in RIVERS:
        traced = []
        for waypoints in branches:
            line = follow(cost, waypoints)
            traced.append([rnd(frame.plate_to_norm(x + FRAME[0], y + FRAME[1])) for x, y in line])
        rivers.append({"id": rid, "name": name, "half_width": 0.0012, "branches": traced})
    return rivers


def fbm(shape, seed: int, octaves: int = 5, base: int = 6) -> np.ndarray:
    rng = np.random.default_rng(seed)
    h, w = shape
    total = np.zeros(shape)
    amp, norm = 1.0, 0.0
    for o in range(octaves):
        cells = base * 2 ** o
        grid = rng.random((cells + 1, int(cells * w / h) + 2))
        up = ndi.zoom(grid, (h / (cells), w / (grid.shape[1] - 1)), order=3)[:h, :w]
        total += amp * up
        norm += amp
        amp *= 0.5
    return total / norm


def build_rasters(plate: Image.Image, frame: Frame, land: np.ndarray, lakes: np.ndarray,
                  rivers: list[dict]):
    h, w = land.shape
    img = plate.crop(FRAME).resize((w, h), Image.LANCZOS)
    hsv = np.asarray(img.convert("HSV")).astype(float)
    hue, sat, val = hsv[..., 0] * 360 / 255, hsv[..., 1], hsv[..., 2]

    ground = land & (lakes == 0)
    coast = ndi.distance_transform_edt(land)
    sea_dist = ndi.distance_transform_edt(~land)

    dark_green = (hue > 70) & (hue < 180) & (val < 150) & (sat > 40)
    forest = ndi.gaussian_filter(dark_green.astype(float), 10)
    forest = np.clip((forest - 0.12) / 0.35, 0, 1) * ground
    green = ndi.gaussian_filter(((hue > 65) & (hue < 150)).astype(float), 8)

    yy, xx = np.mgrid[0:h, 0:w]
    px_, py_ = frame.plate_to_work(850, 480)
    highlands = np.exp(-(((xx - px_) / (560 * frame.sx)) ** 2 + ((yy - py_) / (230 * frame.sy)) ** 2))
    mountains = np.clip(ndi.gaussian_filter(dark_green.astype(float), 18) * 2.2, 0, 1) * highlands
    jx, jy = frame.plate_to_work(2950, 480)
    jungle = np.exp(-(((xx - jx) / (500 * frame.sx)) ** 2 + ((yy - jy) / (260 * frame.sy)) ** 2))

    n1 = fbm((h, w), 1)
    n2 = fbm((h, w), 2, octaves=6, base=12)
    n3 = fbm((h, w), 3, octaves=4, base=48)
    ridged = 1 - np.abs(n2 * 2 - 1)

    elev = 20 + 260 * (1 - np.exp(-coast / 90)) + (n1 - 0.5) * 160 + (n3 - 0.5) * 70
    elev += mountains * (900 + 1400 * ridged ** 2)
    elev += jungle * 260 * n1
    elev = np.where(land, np.maximum(elev, 4), -30 - 770 * (1 - np.exp(-sea_dist / 70)))

    river_mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(river_mask)
    for r in rivers:
        for br in r["branches"]:
            pts = [(x * w, (1 - y) * h) for x, y in br]
            d.line(pts, fill=255, width=3)
    river_px = ndi.gaussian_filter(np.asarray(river_mask) / 255.0, 2)
    elev -= river_px * 25 * land

    for i in range(1, lakes.max() + 1):
        comp = lakes == i
        rim = ndi.binary_dilation(comp, iterations=3) & ~comp & land
        level = float(np.percentile(elev[rim], 20)) if rim.any() else 50.0
        elev[comp] = level - 12

    elev = ndi.gaussian_filter(elev, 1.0)

    savanna = np.array([214, 186, 104], float)
    grass = np.array([140, 168, 78], float)
    wood = np.array([58, 98, 52], float)
    rock = np.array([150, 150, 130], float)
    g = np.clip((green - 0.25) / 0.5, 0, 1)[..., None]
    col = savanna * (1 - g) + grass * g
    col = col * (1 - forest[..., None]) + wood * forest[..., None]
    rocky = np.clip((elev - 900) / 900, 0, 1)[..., None]
    col = col * (1 - rocky) + rock * rocky

    gy, gx = np.gradient(elev)
    scale = 1 / 60.0
    nx, ny, nz = -gx * scale, -gy * scale, np.ones_like(elev)
    norm = np.sqrt(nx ** 2 + ny ** 2 + nz ** 2)
    lx, ly, lz = -0.55, -0.55, 0.63
    shade = np.clip((nx * lx + ny * ly + nz * lz) / norm, 0, 1)
    col *= (0.45 + 0.75 * shade)[..., None]
    col *= (0.9 + 0.1 * n2 + 0.1 * n3)[..., None]
    river_ink = np.clip(river_px * 2.5, 0, 1)[..., None] * land[..., None]
    col = col * (1 - river_ink) + np.array([52, 118, 160], float) * river_ink
    col = np.clip(col, 0, 255)

    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[..., :3] = col.astype(np.uint8)
    rgba[..., 3] = np.where(land, 255, 0)
    rgba[lakes > 0] = (38, 104, 140, 255)
    relief = Image.fromarray(rgba, "RGBA")

    hv = np.clip(np.round(elev + 1000), 0, 65535).astype(np.uint32)
    hrgb = np.zeros((h, w, 3), np.uint8)
    hrgb[..., 0] = (hv >> 8).astype(np.uint8)
    hrgb[..., 1] = (hv & 255).astype(np.uint8)
    height = Image.fromarray(hrgb, "RGB")
    return relief, height, elev


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("plate")
    ap.add_argument("outdir")
    ap.add_argument("--debug")
    args = ap.parse_args()

    plate = Image.open(args.plate).convert("RGB")
    if plate.size != (3625, 2831):
        raise SystemExit(f"expected the 3625x2831 coloured plate, got {plate.size}")
    work_h = round(FRAME_H * OUT_W / FRAME_W)
    frame = Frame(OUT_W, work_h)

    land0 = classify(plate, frame)
    land, ocean, lakes = split_water(land0)

    tol = 1.1
    land_polys = []
    lab, n = ndi.label(land)
    for i in range(1, n + 1):
        comp = ndi.binary_fill_holes(lab == i)
        for poly in contour_polys(comp, tol):
            land_polys.append(poly)
    land_polys.sort(key=lambda p: -len(p))

    lake_meta = []
    lake_names = {"beetle-lake": ("Beetle Lake", (1069, 931)),
                  "lake-scorpion": ("Lake Scorpion", (2456, 2311))}
    centroids = {}
    for i in range(1, lakes.max() + 1):
        ys, xs = np.nonzero(lakes == i)
        centroids[i] = (xs.mean(), ys.mean())
    named = {}
    for lid, (_, (x, y)) in lake_names.items():
        wx, wy = frame.plate_to_work(x, y)
        best = min(centroids, key=lambda i: (centroids[i][0] - wx) ** 2 + (centroids[i][1] - wy) ** 2)
        named[best] = lid
    for i in range(1, lakes.max() + 1):
        polys = contour_polys(lakes == i, 1.0)
        if not polys:
            continue
        lid = named.get(i, f"lake-{i}")
        lake_meta.append({
            "id": lid,
            "name": lake_names[lid][0] if lid in lake_names else "",
            "polygon": [rnd(frame.work_to_norm(x, y)) for x, y in max(polys, key=len)],
            "_centroid": frame.work_to_norm(*centroids[i]),
        })

    rivers = trace_rivers(plate, frame)

    wasp = np.array(HIVES["wasp"], float)
    cicada = np.array(HIVES["cicada"], float)
    miles_per_px = CICADA_TO_WASP_MILES / float(np.hypot(*(wasp - cicada)))
    xs = np.concatenate([p[:, 0] for p in land_polys])
    continent_px = (xs.max() - xs.min()) / frame.sx
    world = {
        "width_m": FRAME_W * miles_per_px * MILES_TO_M,
        "height_m": FRAME_H * miles_per_px * MILES_TO_M,
        "continent_ew_miles": round(continent_px * miles_per_px),
        "miles_per_map_px": miles_per_px,
        "map_px": [FRAME_W, FRAME_H],
    }

    guide = fit_affine(GUIDE_HIVES, HIVES)
    lakes_by_id = {l["id"]: l for l in lake_meta}

    landmarks = []
    for hid, (x, y) in HIVES.items():
        landmarks.append({
            "id": f"{hid}-hive",
            "name": f"{hid.capitalize()} Hive",
            "blurb": HIVE_BLURBS.get(hid, DEFAULT_HIVE_BLURB),
            "pos": rnd(frame.plate_to_norm(x, y)),
            "group": "hive",
            "rank": 1,
            "altitude": 1500,
        })
    for lid, name, group, rank, blurb, where in EXTRA_LANDMARKS:
        if where[0] == "plate":
            pos = frame.plate_to_norm(*where[1])
        elif where[0] == "guide":
            gx, gy = where[1] if isinstance(where[1], tuple) else GUIDE_PLACES[where[1]]
            px, py = np.array([gx, gy, 1.0]) @ guide
            pos = frame.plate_to_norm(px, py)
        else:
            cx, cy = lakes_by_id[where[1]]["_centroid"]
            if len(where) > 2:
                dx, dy = where[2]
                cx, cy = cx + dx / FRAME_W, cy - dy / FRAME_H
            pos = (cx, cy)
        landmarks.append({"id": lid, "name": name, "blurb": blurb, "pos": rnd(pos),
                          "group": group, "rank": rank, "altitude": 1200})
    for l in lake_meta:
        l.pop("_centroid")

    bridges = [[rnd(frame.plate_to_norm(*HIVES[a])), rnd(frame.plate_to_norm(*HIVES[b]))]
               for a, b in BRIDGES]

    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    relief, height, _ = build_rasters(plate, frame, land, lakes, rivers)
    relief.save(out / "relief.png", optimize=True)
    height.save(out / "height.png", optimize=True)

    data = {
        "name": "Pantala",
        "source": "Traced from the coloured Pantala plate (The Lost Continent); "
                  "Poison Jungle places placed after A Guide to the Dragon World.",
        "world": world,
        "land": [[rnd(frame.work_to_norm(x, y)) for x, y in p] for p in land_polys],
        "regions": [{**r, "polygon": [rnd(frame.plate_to_norm(x, y)) for x, y in r["polygon"]]}
                    for r in REGIONS],
        "rivers": rivers,
        "lakes": lake_meta,
        "routes": [{"id": "silk-bridges", "name": "Silk bridges", "segments": bridges}],
        "groups": GROUPS,
        "landmarks": landmarks,
    }
    (out / "pantala.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    pts = sum(len(p) for p in data["land"])
    print(f"land polygons {len(land_polys)} ({pts} points), lakes {len(lake_meta)}, "
          f"rivers {len(rivers)}, {miles_per_px:.3f} mi/px, "
          f"continent {world['continent_ew_miles']} mi east-west")

    if args.debug:
        dbg = Path(args.debug)
        dbg.mkdir(parents=True, exist_ok=True)
        base = plate.crop(FRAME).resize((frame.w, frame.h)).convert("RGB")
        base = Image.blend(base, Image.new("RGB", base.size, (255, 255, 255)), 0.45)
        d = ImageDraw.Draw(base)
        def xy(p):
            return (p[0] * frame.w, (1 - p[1]) * frame.h)
        for p in data["land"]:
            d.line([xy(q) for q in p] + [xy(p[0])], fill=(200, 0, 0), width=2)
        for l in data["lakes"]:
            d.line([xy(q) for q in l["polygon"]] + [xy(l["polygon"][0])], fill=(0, 60, 220), width=2)
        for r in data["rivers"]:
            for br in r["branches"]:
                d.line([xy(q) for q in br], fill=(0, 140, 255), width=3)
        for r in data["regions"]:
            d.line([xy(q) for q in r["polygon"]] + [xy(r["polygon"][0])], fill=(160, 0, 160), width=1)
        for s in bridges:
            d.line([xy(s[0]), xy(s[1])], fill=(120, 80, 0), width=1)
        for m in landmarks:
            x, y = xy(m["pos"])
            d.ellipse([x - 6, y - 6, x + 6, y + 6], outline=(0, 0, 0), fill=(255, 220, 0))
            d.text((x + 8, y - 6), m["name"], fill=(0, 0, 0))
        base.save(dbg / "overlay.png")


if __name__ == "__main__":
    main()
