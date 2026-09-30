// Overview 3D viewer for a continent exported as map.json + relief.png + height.png.
// Opened as viewer/index.html?map=<continent>; the continent folder sits next to viewer/.
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { CSS2DObject, CSS2DRenderer } from 'three/examples/jsm/renderers/CSS2DRenderer.js';

type P = [number, number];
interface Landmark { id: string; name: string; blurb: string; pos: P; group: string; rank: number }
interface MapData {
  name: string;
  world: { width_m: number; height_m: number };
  rivers: { id: string; name: string; branches: P[][] }[];
  routes?: { id: string; name: string; segments: P[][] }[];
  groups: { id: string; label: string; color: string }[];
  landmarks: Landmark[];
}

const KM = 1000;
const EXAGGERATION = 18;
const SEGMENTS = 480;

const params = new URLSearchParams(location.search);
const mapId = (params.get('map') ?? 'pantala').replace(/[^a-z0-9-]/g, '');
const base = `../${mapId}/`;

const status = document.getElementById('status')!;
const info = document.getElementById('info')!;

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`could not load ${url}`));
    img.src = url;
  });
}

function pixels(img: HTMLImageElement): ImageData {
  const c = document.createElement('canvas');
  c.width = img.width;
  c.height = img.height;
  const ctx = c.getContext('2d', { willReadFrequently: true })!;
  ctx.drawImage(img, 0, 0);
  return ctx.getImageData(0, 0, img.width, img.height);
}

async function main(): Promise<void> {
  const [data, heightImg, reliefImg] = await Promise.all([
    fetch(`${base}map.json`).then((r) => {
      if (!r.ok) throw new Error(`no map called ${mapId}`);
      return r.json() as Promise<MapData>;
    }),
    loadImage(`${base}height.png`),
    loadImage(`${base}relief.png`),
  ]);
  document.title = `${data.name} in 3D`;
  status.textContent = `Raising ${data.name}…`;

  const hp = pixels(heightImg);
  const W = data.world.width_m / KM;
  const H = data.world.height_m / KM;

  const elevation = (nx: number, ny: number): number => {
    const x = Math.min(hp.width - 1, Math.max(0, nx * (hp.width - 1)));
    const y = Math.min(hp.height - 1, Math.max(0, (1 - ny) * (hp.height - 1)));
    const x0 = Math.floor(x), y0 = Math.floor(y);
    const x1 = Math.min(hp.width - 1, x0 + 1), y1 = Math.min(hp.height - 1, y0 + 1);
    const at = (px: number, py: number) => {
      const i = (py * hp.width + px) * 4;
      return hp.data[i] * 256 + hp.data[i + 1] - 1000;
    };
    const fx = x - x0, fy = y - y0;
    const top = at(x0, y0) * (1 - fx) + at(x1, y0) * fx;
    const bottom = at(x0, y1) * (1 - fx) + at(x1, y1) * fx;
    return top * (1 - fy) + bottom * fy;
  };
  const toScene = (nx: number, ny: number, lift = 0): THREE.Vector3 =>
    new THREE.Vector3((nx - 0.5) * W, (Math.max(0, elevation(nx, ny)) * EXAGGERATION) / KM + lift, (0.5 - ny) * H);

  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(innerWidth, innerHeight);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  document.body.appendChild(renderer.domElement);

  const labels = new CSS2DRenderer();
  labels.setSize(innerWidth, innerHeight);
  labels.domElement.className = 'labels';
  document.body.appendChild(labels.domElement);

  const scene = new THREE.Scene();
  const sky = new THREE.Color('#9fc7e0');
  scene.background = sky;
  scene.fog = new THREE.Fog(sky, W * 0.9, W * 2.6);

  const camera = new THREE.PerspectiveCamera(45, innerWidth / innerHeight, 1, W * 6);
  camera.position.set(0, W * 0.62, H * 0.78);

  scene.add(new THREE.HemisphereLight('#dfefff', '#5a4a30', 1.1));
  const sun = new THREE.DirectionalLight('#fff4dc', 2.2);
  sun.position.set(-W, W * 0.9, -H * 0.6);
  scene.add(sun);

  const cols = SEGMENTS;
  const rows = Math.round((SEGMENTS * H) / W);
  const geo = new THREE.PlaneGeometry(W, H, cols, rows);
  geo.rotateX(-Math.PI / 2);
  const pos = geo.attributes.position as THREE.BufferAttribute;
  for (let i = 0; i < pos.count; i++) {
    const nx = pos.getX(i) / W + 0.5;
    const ny = 0.5 - pos.getZ(i) / H;
    pos.setY(i, (elevation(nx, ny) * EXAGGERATION) / KM);
  }
  geo.computeVertexNormals();

  const relief = new THREE.Texture(reliefImg);
  relief.colorSpace = THREE.SRGBColorSpace;
  relief.anisotropy = renderer.capabilities.getMaxAnisotropy();
  relief.needsUpdate = true;
  const land = new THREE.Mesh(
    geo,
    new THREE.MeshStandardMaterial({ map: relief, alphaTest: 0.5, roughness: 0.95, metalness: 0 }),
  );
  scene.add(land);

  const sea = new THREE.Mesh(
    new THREE.PlaneGeometry(W * 5, H * 5),
    new THREE.MeshStandardMaterial({ color: '#2f6f96', roughness: 0.55, metalness: 0.05 }),
  );
  sea.rotateX(-Math.PI / 2);
  sea.position.y = -0.4;
  scene.add(sea);

  const riverMat = new THREE.LineBasicMaterial({ color: '#3d8fc4' });
  for (const river of data.rivers) {
    for (const branch of river.branches) {
      const pts: THREE.Vector3[] = [];
      for (let i = 0; i < branch.length - 1; i++) {
        const [ax, ay] = branch[i];
        const [bx, by] = branch[i + 1];
        const steps = Math.max(1, Math.ceil(Math.hypot(bx - ax, by - ay) * 400));
        for (let s = 0; s < steps; s++) {
          const t = s / steps;
          pts.push(toScene(ax + (bx - ax) * t, ay + (by - ay) * t, 1.2));
        }
      }
      const [lx, ly] = branch[branch.length - 1];
      pts.push(toScene(lx, ly, 1.2));
      scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), riverMat));
    }
  }

  const hives = data.landmarks.filter((l) => l.group === 'hive');
  const towerTop = new Map<string, THREE.Vector3>();
  const treestuff = new THREE.MeshStandardMaterial({ color: '#b98a52', roughness: 0.8 });
  const band = new THREE.MeshStandardMaterial({ color: '#7a4a26', roughness: 0.8 });
  for (const hive of hives) {
    const g = new THREE.Group();
    const scale = hive.rank === 1 ? 1.35 : 1;
    const levels = [
      [4.2, 3.4, 6], [3.4, 3.8, 5], [3.8, 2.6, 5], [2.6, 1.6, 4],
    ];
    let y = 0;
    levels.forEach(([r0, r1, h], i) => {
      const m = new THREE.Mesh(new THREE.CylinderGeometry(r1, r0, h, 10), i % 2 ? band : treestuff);
      m.position.y = y + h / 2;
      g.add(m);
      y += h;
    });
    const spire = new THREE.Mesh(new THREE.ConeGeometry(1.6, 6, 10), treestuff);
    spire.position.y = y + 3;
    g.add(spire);
    g.scale.setScalar(scale);
    const at = toScene(hive.pos[0], hive.pos[1]);
    g.position.copy(at);
    scene.add(g);
    towerTop.set(hive.id, at.clone().add(new THREE.Vector3(0, 16 * scale, 0)));
  }

  const silk = new THREE.LineBasicMaterial({ color: '#fff6e0', transparent: true, opacity: 0.85 });
  for (const route of data.routes ?? []) {
    for (const [a, b] of route.segments) {
      const pa = toScene(a[0], a[1], 16);
      const pb = toScene(b[0], b[1], 16);
      const mid = pa.clone().lerp(pb, 0.5);
      mid.y -= pa.distanceTo(pb) * 0.04;
      const curve = new THREE.QuadraticBezierCurve3(pa, mid, pb);
      scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(curve.getPoints(32)), silk));
    }
  }

  const groupColour = new Map(data.groups.map((g) => [g.id, g.color]));
  const markers: { lm: Landmark; obj: CSS2DObject; at: THREE.Vector3 }[] = [];
  for (const lm of data.landmarks) {
    const el = document.createElement('button');
    el.className = `marker rank-${lm.rank}`;
    el.style.setProperty('--chip', groupColour.get(lm.group) ?? '#fff');
    el.innerHTML = `<i></i><span>${lm.name}</span>`;
    el.addEventListener('click', () => focus(lm.id));
    const at = towerTop.get(lm.id) ?? toScene(lm.pos[0], lm.pos[1], 2);
    const obj = new CSS2DObject(el);
    obj.position.copy(at);
    scene.add(obj);
    markers.push({ lm, obj, at });
  }

  const controls = new OrbitControls(camera, labels.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.maxPolarAngle = Math.PI * 0.46;
  controls.minDistance = 25;
  controls.maxDistance = W * 1.6;
  controls.screenSpacePanning = false;

  let flight: { from: THREE.Vector3; to: THREE.Vector3; camFrom: THREE.Vector3; camTo: THREE.Vector3; t: number } | null = null;

  function focus(id: string): boolean {
    const m = markers.find((k) => k.lm.id === id || k.lm.name.toLowerCase() === id.toLowerCase());
    if (!m) return false;
    const offset = camera.position.clone().sub(controls.target).setLength(Math.max(120, W * 0.09));
    offset.y = Math.max(offset.y, W * 0.05);
    flight = {
      from: controls.target.clone(),
      to: m.at.clone(),
      camFrom: camera.position.clone(),
      camTo: m.at.clone().add(offset),
      t: 0,
    };
    info.innerHTML = `<strong>${m.lm.name}</strong><span>${m.lm.blurb}</span>`;
    info.hidden = false;
    for (const k of markers) k.obj.element.classList.toggle('selected', k === m);
    return true;
  }
  (window as unknown as { wofFocus: (id: string) => boolean }).wofFocus = focus;
  (window as unknown as { wofReady: boolean }).wofReady = true;

  addEventListener('resize', () => {
    camera.aspect = innerWidth / innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(innerWidth, innerHeight);
    labels.setSize(innerWidth, innerHeight);
  });

  const initial = params.get('focus');
  if (initial) focus(initial);

  const clock = new THREE.Clock();
  renderer.setAnimationLoop(() => {
    const dt = clock.getDelta();
    if (flight) {
      flight.t = Math.min(1, flight.t + dt / 1.4);
      const e = flight.t < 0.5 ? 4 * flight.t ** 3 : 1 - (-2 * flight.t + 2) ** 3 / 2;
      controls.target.lerpVectors(flight.from, flight.to, e);
      camera.position.lerpVectors(flight.camFrom, flight.camTo, e);
      if (flight.t >= 1) flight = null;
    }
    controls.update();
    const dist = camera.position.distanceTo(controls.target);
    for (const k of markers) {
      const show = k.lm.rank === 1 || (k.lm.rank === 2 && dist < W * 0.75) || dist < W * 0.3;
      k.obj.visible = show || k.obj.element.classList.contains('selected');
    }
    renderer.render(scene, camera);
    labels.render(scene, camera);
  });

  status.remove();
}

main().catch((e: Error) => {
  status.textContent = e.message;
  status.classList.add('error');
});
