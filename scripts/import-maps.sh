#!/bin/sh
# Regenerate desktop/maps/ from its sources:
#   Pyrrhia  - geography, relief and heightmap exported from the 3D map at
#              github.com/blhcode/pyrrhia-3d-map, plus that map's 3D build.
#   Pantala  - traced from the coloured Lost Continent plate (scripts/map/trace-pantala.py).
#   viewer   - the overview 3D viewer used for continents without their own 3D map.
# Needs git, node/npm and a Python with numpy, scipy, scikit-image and Pillow (build/venv
# is created with them if missing). The results are committed, so the OS build never runs this.
set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
EXT="$ROOT/build/ext"
MAPS="$ROOT/desktop/maps"
REPO=https://github.com/blhcode/pyrrhia-3d-map
COMMIT=a62068bcd3ec90cd78d87bb8b20183e33128d637
PLATE_URL="https://static.wikia.nocookie.net/wingsoffire/images/2/23/PantalaColored.jpg/revision/latest?cb=20190120231512"

say() { printf '\033[1;33m==> %s\033[0m\n' "$*"; }

mkdir -p "$EXT"
SRC="$EXT/pyrrhia-3d-map"
if [ ! -d "$SRC/.git" ]; then
    say "Cloning $REPO"
    git clone --quiet "$REPO" "$SRC"
fi
git -C "$SRC" fetch --quiet origin
git -C "$SRC" checkout --quiet "$COMMIT"
if [ ! -d "$SRC/node_modules" ]; then
    say "Installing the 3D map's npm packages"
    (cd "$SRC" && npm ci --no-audit --no-fund)
fi

say "Exporting Pyrrhia"
cp "$ROOT/scripts/map/_pyrrhia-entry.ts" "$ROOT/scripts/map/export-pyrrhia.mjs" "$SRC/scripts/"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
(cd "$SRC" && node scripts/export-pyrrhia.mjs "$TMP/pyrrhia")
rm -rf "$MAPS/pyrrhia"
mkdir -p "$MAPS/pyrrhia"
mv "$TMP/pyrrhia/pyrrhia.json" "$MAPS/pyrrhia/map.json"
mv "$TMP/pyrrhia/relief.png" "$TMP/pyrrhia/height.png" "$MAPS/pyrrhia/"

say "Building the Pyrrhia 3D map"
(cd "$SRC" && npx tsc && npx vite build --logLevel warn --base ./ --outDir "$MAPS/pyrrhia/3d" --emptyOutDir)

say "Building the overview 3D viewer"
rm -rf "$MAPS/viewer"
mkdir -p "$MAPS/viewer"
cp "$ROOT/scripts/map/viewer/index.html" "$MAPS/viewer/"
cp "$ROOT/scripts/map/viewer/viewer.ts" "$SRC/scripts/_wof-viewer.ts"
(cd "$SRC" && npx esbuild scripts/_wof-viewer.ts --bundle --minify --format=iife \
    --target=es2020 --log-level=warning --outfile="$MAPS/viewer/viewer.js")
rm -f "$SRC/scripts/_wof-viewer.ts" "$SRC/scripts/_pyrrhia-entry.ts" "$SRC/scripts/export-pyrrhia.mjs"

PY="$ROOT/build/venv/bin/python"
if ! "$PY" -c 'import numpy, scipy, skimage, PIL' 2>/dev/null; then
    say "Creating build/venv for the Pantala tracer"
    python3 -m venv "$ROOT/build/venv"
    "$PY" -m pip install --quiet numpy scipy scikit-image pillow
fi
PLATE="$EXT/PantalaColored.jpg"
if [ ! -s "$PLATE" ]; then
    say "Downloading the Pantala plate"
    curl -fsSL -o "$PLATE" "$PLATE_URL" \
        -A "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36" \
        -H "Referer: https://wingsoffire.fandom.com/" -H "Accept: image/webp,image/*,*/*"
fi
say "Tracing Pantala"
rm -rf "$MAPS/pantala"
"$PY" "$ROOT/scripts/map/trace-pantala.py" "$PLATE" "$TMP/pantala"
mkdir -p "$MAPS/pantala"
mv "$TMP/pantala/pantala.json" "$MAPS/pantala/map.json"
mv "$TMP/pantala/relief.png" "$TMP/pantala/height.png" "$MAPS/pantala/"

du -sh "$MAPS"/*
say "Maps updated in desktop/maps"
