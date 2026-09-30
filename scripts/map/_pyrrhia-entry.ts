// Bundled into a headless page by export-pyrrhia.mjs, from inside a checkout of
// github.com/blhcode/pyrrhia-3d-map. Dumps the map's geography as JSON and the generated terrain
// as a hillshaded relief image, for the Wings of Fire OS 2D map.
import { ALL_LAND } from '../src/data/coastline';
import { KINGDOMS, SEA_KINGDOM_META } from '../src/data/kingdoms';
import { LANDMARK_GROUPS, LANDMARKS, labelRank } from '../src/data/landmarks';
import { LAKES, RIVERS } from '../src/data/rivers';
import { CONTINENT_EW_MILES, MILES_PER_MAP_PX, WORLD_HEIGHT_M, WORLD_WIDTH_M } from '../src/data/scale';
import { MAP_IN_H, MAP_IN_W } from '../src/data/mapref';
import { generateTerrain } from '../src/terrain/generate';

declare global {
  interface Window {
    exportMap: (size: number, width: number, height: number) => Promise<{ json: string; relief: string; height: string }>;
  }
}

const round = (v: number) => Math.round(v * 100000) / 100000;
const pts = (poly: ReadonlyArray<readonly [number, number]>) => poly.map(([x, y]) => [round(x), round(y)]);

function geography() {
  return {
    name: 'Pyrrhia',
    source: 'https://github.com/blhcode/pyrrhia-3d-map',
    world: {
      width_m: WORLD_WIDTH_M,
      height_m: WORLD_HEIGHT_M,
      continent_ew_miles: CONTINENT_EW_MILES,
      miles_per_map_px: MILES_PER_MAP_PX,
      map_px: [MAP_IN_W, MAP_IN_H],
    },
    land: ALL_LAND.map(pts),
    regions: [
      ...KINGDOMS.map((k) => ({ id: k.id, name: k.name, tribe: k.tribe, label: k.label, polygon: pts(k.polygon) })),
      { id: SEA_KINGDOM_META.id, name: SEA_KINGDOM_META.name, tribe: SEA_KINGDOM_META.tribe,
        label: SEA_KINGDOM_META.label, polygon: [],
        // Mostly open ocean: label only, out at sea east of the Mud Kingdom.
        anchor: [0.87, 0.47] },
    ],
    rivers: RIVERS.map((r) => ({ id: r.id, name: r.name, half_width: r.halfWidth, branches: r.branches.map(pts) })),
    lakes: LAKES.map((l) => ({ id: l.id, name: l.name, polygon: pts(l.polygon) })),
    groups: LANDMARK_GROUPS.map((g) => ({ id: g.id, label: g.label, color: g.color })),
    landmarks: LANDMARKS.map((l) => ({
      id: l.id, name: l.name, blurb: l.blurb, pos: [round(l.pos[0]), round(l.pos[1])], group: l.group,
      rank: labelRank(l.id), altitude: l.altitude,
    })),
  };
}

window.exportMap = async (size, width, height) => {
  const t = await generateTerrain(size);
  const vert = 15;
  const spacing = WORLD_WIDTH_M / size;
  const sun = { x: -0.55, y: 0.62, z: -0.56 };
  const sample = (arr: ArrayLike<number>, stride: number, off: number, x: number, y: number) => {
    const cx = Math.max(0, Math.min(size - 1, x));
    const cy = Math.max(0, Math.min(size - 1, y));
    return arr[(cy * size + cx) * stride + off];
  };

  // The terrain grid is square over the (wider than tall) world box; resample to the map's aspect.
  const relief = document.createElement('canvas');
  relief.width = width;
  relief.height = height;
  const rctx = relief.getContext('2d')!;
  const rimg = rctx.createImageData(width, height);
  const heights = document.createElement('canvas');
  heights.width = width;
  heights.height = height;
  const hctx = heights.getContext('2d')!;
  const himg = hctx.createImageData(width, height);

  for (let py = 0; py < height; py++) {
    for (let px = 0; px < width; px++) {
      const x = Math.round((px / (width - 1)) * (size - 1));
      const y = Math.round((py / (height - 1)) * (size - 1));
      const h = (dx: number, dy: number) => sample(t.data, 4, 0, x + dx, y + dy) * vert;
      let nx = (h(-1, 0) - h(1, 0)) / (2 * spacing);
      let nz = (h(0, -1) - h(0, 1)) / (2 * spacing);
      const len = Math.hypot(nx, 1, nz);
      nx /= len;
      nz /= len;
      const lambert = Math.max(0, nx * sun.x + (1 / len) * sun.y + nz * sun.z);
      const shade = 0.4 + 0.7 * lambert;
      const i = y * size + x;
      const o = (py * width + px) * 4;
      const isLand = t.data[i * 4 + 3] > 0.5;
      const base = t.data[i * 4];
      if (!isLand) {
        rimg.data[o + 3] = 0;
      } else if (base < 0) {
        rimg.data[o] = 38; rimg.data[o + 1] = 104; rimg.data[o + 2] = 140; rimg.data[o + 3] = 255;
      } else {
        const canopy = t.forest[i] / 255;
        const r = (t.albedo[i * 4] / 255) * (1 - canopy * 0.55) + 0.12 * canopy;
        const g = (t.albedo[i * 4 + 1] / 255) * (1 - canopy * 0.55) + 0.42 * canopy;
        const b = (t.albedo[i * 4 + 2] / 255) * (1 - canopy * 0.55) + 0.14 * canopy;
        rimg.data[o] = Math.min(255, r * shade * 255);
        rimg.data[o + 1] = Math.min(255, g * shade * 255);
        rimg.data[o + 2] = Math.min(255, b * shade * 255);
        rimg.data[o + 3] = 255;
      }
      // Elevation in metres + 1000, as 16 bits split across red (high) and green (low).
      const e = Math.max(0, Math.min(65535, Math.round(base + 1000)));
      himg.data[o] = e >> 8;
      himg.data[o + 1] = e & 255;
      himg.data[o + 2] = 0;
      himg.data[o + 3] = 255;
    }
  }
  rctx.putImageData(rimg, 0, 0);
  hctx.putImageData(himg, 0, 0);
  return { json: JSON.stringify(geography()), relief: relief.toDataURL('image/png'), height: heights.toDataURL('image/png') };
};
