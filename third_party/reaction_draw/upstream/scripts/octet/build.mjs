// SPDX-License-Identifier: Apache-2.0
// Build step (maintainers only): bundle adapter.ts and the Octet Draw source files it imports into ONE self-contained
// HTML page.
//
//   node build.mjs --octet <Octet Draw checkout> --out dist/octet-adapter.html [--record dist/octet-adapter.json]
//                  [--node-modules <dir with esbuild>]
//
// The drawing scripts use the prebuilt page shipped in dist/ (made by this script from Octet Draw at commit PINNED), so
// a user needs neither Node.js nor an Octet Draw checkout.  Run this script after changing adapter.ts, or to build the
// page from another checkout: octet_draw.py --octet <checkout> runs it and keeps the page in its cache.
//
// The alias "octet-src" points at <checkout>/src; Octet's files are used unchanged.  Two third-party imports that only
// the desktop app needs are replaced by tiny in-memory stand-ins, so no npm package ends up in the page: the chemistry
// engine "indigo-ketcher" that src/chem.ts loads, and "@tauri-apps/api/core" that src/export.ts imports.  The only npm
// package needed to run this script is esbuild.
//
// The page contains code of Octet Draw (Apache-2.0): see ../../third_party/octet-draw/NOTICE.  --record writes what
// was built (the commit, the esbuild version, the SHA-256 of adapter.ts and of the page, and the bytes each source
// file adds to the page); octet_draw.py reads it to warn when adapter.ts has changed since the page was built.
import {createRequire} from 'node:module';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const PINNED = '934719abf213e0a8c9725256338bcbc0f305cab6';
const UPSTREAM = 'https://github.com/SamChemMan/Octet-Draw';
const here = path.dirname(fileURLToPath(import.meta.url));
const usage = 'usage: node build.mjs --octet <Octet Draw checkout> --out <page.html> [--record <page.json>] [--node-modules <dir>]';

function fail(message) {
  console.error('build.mjs: ' + message);
  process.exit(2);
}

const args = new Map();
for (let i = 2; i < process.argv.length; i += 2) {
  const key = process.argv[i];
  if (!key.startsWith('--') || i + 1 >= process.argv.length) fail(usage);
  args.set(key.slice(2), process.argv[i + 1]);
}
if (!args.has('octet') || !args.has('out')) fail(usage);
const octet = path.resolve(args.get('octet'));
const out = path.resolve(args.get('out'));

let esbuild;
try {
  // from --node-modules, else from this directory (npm install in scripts/octet) or NODE_PATH
  esbuild = createRequire(import.meta.url)(args.has('node-modules') ? path.join(path.resolve(args.get('node-modules')), 'esbuild') : 'esbuild');
} catch {
  fail('the npm package "esbuild" was not found.  Run "npm install" in ' + here + ' (or pass --node-modules, or point NODE_PATH at a node_modules that has it).');
}

const src = path.join(octet, 'src');
for (const need of ['render.ts', 'file.ts', 'oct.ts', 'export.ts', 'docstyle.ts', 'richtext.ts', 'chem.ts']) {
  if (!fs.existsSync(path.join(src, need))) fail(`${path.join(src, need)} does not exist: "${octet}" is not an Octet Draw checkout.`);
}
let commit = null;
if (fs.existsSync(path.join(octet, '.git'))) {
  try {
    commit = execFileSync('git', ['-C', octet, 'rev-parse', 'HEAD'], {encoding: 'utf8'}).trim();
    if (commit !== PINNED) console.warn(`build.mjs: warning: the checkout is at ${commit}, this adapter was written against ${PINNED}.  Check the result carefully.`);
  } catch {
    console.warn('build.mjs: warning: could not read the checkout\'s commit (git not available?).');
  }
} else {
  console.warn(`build.mjs: warning: ${octet} has no .git directory; cannot confirm that it is at ${PINNED}.`);
}
let octetVersion = null;
try { octetVersion = JSON.parse(fs.readFileSync(path.join(octet, 'package.json'), 'utf8')).version ?? null; } catch { /* no package.json */ }

// In-memory stand-ins.  Octet's chem.ts starts the Indigo WebAssembly engine at import time; the adapter only needs
// chem.ts's glyph measurer, which does not use it.  export.ts imports the desktop bridge for clipboard and file
// functions that standaloneSvg does not call.
const stubs = {
  name: 'octet-stubs',
  setup(build) {
    build.onResolve({filter: /^indigo-ketcher(\/.*)?$/}, (a) => ({path: a.path, namespace: 'octet-stub'}));
    build.onResolve({filter: /^@tauri-apps\/api(\/.*)?$/}, (a) => ({path: a.path, namespace: 'octet-stub'}));
    build.onLoad({filter: /.*/, namespace: 'octet-stub'}, (a) => ({
      contents: a.path.startsWith('indigo-ketcher')
        ? 'export default function Indigo() { return Promise.resolve({}); }'
        : 'export const invoke = async () => { throw new Error("desktop-only function"); };\nexport const convertFileSrc = (p) => p;\nexport default {};',
      loader: 'js',
    }));
  },
};

const banner = `// reaction-draw Octet adapter page.  Contains code compiled from Octet Draw (${UPSTREAM}), ` +
  `commit ${commit ?? 'unknown'}, licensed under the Apache License, Version 2.0; see third_party/octet-draw/NOTICE.`;
let result;
try {
  result = await esbuild.build({
    entryPoints: [path.join(here, 'adapter.ts')], bundle: true, format: 'esm', platform: 'browser', target: 'chrome130', write: false,
    alias: {'octet-src': src}, plugins: [stubs], logLevel: 'error', metafile: true, loader: {'.json': 'json'}, banner: {js: banner},
  });
} catch (e) {
  fail('esbuild failed (see the messages above).  The checkout may be at a different commit than ' + PINNED + '.');
}
const inputs = Object.keys(result.metafile.inputs);
const outside = inputs.filter((k) => k.includes('node_modules'));
if (outside.length) console.warn('build.mjs: warning: unexpected npm inputs in the bundle: ' + outside.join(', '));

// esbuild writes a "// <path of the source file>" comment above each module; drop them so the page does not carry local paths.
const comments = new Set(inputs.flatMap((k) => ['// ' + k, '// ' + path.relative(process.cwd(), path.resolve(k))]));
const text = result.outputFiles[0].text.split('\n').filter((line) => !comments.has(line) && !/^\/\/ octet-stub:/.test(line)).join('\n');
const script = text.replace(/<\/script/gi, '<\\/script');
const page = '<!doctype html><meta charset="utf-8"><body style="margin:0;background:#fff"><svg xmlns="http://www.w3.org/2000/svg"></svg><script type="module">' + script + '</script>';
fs.mkdirSync(path.dirname(out), {recursive: true});
fs.writeFileSync(out, page);
console.log(`wrote ${out} (${fs.statSync(out).size} bytes, ${inputs.length} source files)`);

if (args.has('record')) {
  const sha = (b) => crypto.createHash('sha256').update(b).digest('hex');
  const name = (k) => {
    const abs = path.resolve(k);
    if (abs.startsWith(octet + path.sep)) return 'Octet-Draw/' + path.relative(octet, abs).split(path.sep).join('/');
    if (abs.startsWith(here + path.sep)) return path.relative(here, abs).split(path.sep).join('/');
    return k.startsWith('octet-stub:') ? k : path.basename(k);
  };
  const outInputs = Object.values(result.metafile.outputs)[0]?.inputs ?? {};
  const record = {
    page: path.basename(out), page_bytes: Buffer.byteLength(page), page_sha256: sha(page),
    octet_draw: {repository: UPSTREAM, commit, version: octetVersion, pinned: PINNED},
    esbuild: esbuild.version, adapter_sha256: sha(fs.readFileSync(path.join(here, 'adapter.ts'))),
    stand_ins: ['indigo-ketcher', '@tauri-apps/api/core'],
    inputs: Object.entries(outInputs).map(([k, v]) => ({file: name(k), bytes_in_page: v.bytesInOutput})).sort((a, b) => a.file.localeCompare(b.file)),
  };
  const rec = path.resolve(args.get('record'));
  fs.writeFileSync(rec, JSON.stringify(record, null, 1) + '\n');
  console.log(`wrote ${rec}`);
}
