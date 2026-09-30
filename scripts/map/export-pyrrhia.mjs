// Run from inside a checkout of github.com/blhcode/pyrrhia-3d-map (scripts/import-maps.sh copies
// this file there). Writes pyrrhia.json, relief.png and height.png to the directory given.
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { build } from 'esbuild';
import puppeteer from 'puppeteer';

const out = resolve(process.argv[2] ?? 'map-export');
const SIZE = 2048;
const WIDTH = 2192;   // 548 x 404 map pixels, x4
const HEIGHT = 1616;
mkdirSync(out, { recursive: true });

const bundle = await build({
  entryPoints: ['scripts/_pyrrhia-entry.ts'],
  bundle: true,
  format: 'iife',
  write: false,
  platform: 'browser',
});
const browser = await puppeteer.launch({ headless: 'shell', protocolTimeout: 900_000, args: ['--no-sandbox'] });
const page = await browser.newPage();
page.on('pageerror', (e) => console.log('[pageerror]', e.message));
await page.setContent('<body></body>');
await page.addScriptTag({ content: bundle.outputFiles[0].text });
const started = Date.now();
const result = await page.evaluate((s, w, h) => window.exportMap(s, w, h), SIZE, WIDTH, HEIGHT);
await browser.close();
console.log(`terrain generated in ${((Date.now() - started) / 1000).toFixed(1)} s`);

const png = (url) => Buffer.from(url.split(',')[1], 'base64');
writeFileSync(resolve(out, 'pyrrhia.json'), JSON.stringify(JSON.parse(result.json), null, 1));
writeFileSync(resolve(out, 'relief.png'), png(result.relief));
writeFileSync(resolve(out, 'height.png'), png(result.height));
console.log('wrote', out);
