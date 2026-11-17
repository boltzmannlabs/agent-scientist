// Browser side of the Octet backend: a resolved figure, laid out with Octet Draw's own glyph geometry.
//
// Everything drawn comes from an unmodified checkout of Octet Draw, imported through the build alias "octet-src"
// (build.mjs): the structure renderer, arrow shapes, caption placement, the .oct writer and reader and the SVG export.
// This file decides only what needs Octet's real glyph geometry, in this order:
//   1. all bonds keep their resolved standard length, including bonds between labels;
//   2. each circled single charge gets a free side of its own atom (Octet's default circle size is kept); a box grows
//      to hold the letters and marks of the atoms inside it;
//   3. each curved arrow's start, end and bend are searched on a distance field of the drawn ink and text, with a gap
//      at both ends (Octet has no "larger gap" setting: the end points are placed off the label or bond); the ends
//      are chosen first and must read as the atom or bond asked, then the bend that keeps off the numbers' places;
//   4. each atom number goes beside its own atom, after the curved arrows (never on an H drawn as a letter);
//   5. panel titles without a position go under their panel, level along a row.
// The document is then saved with writeOct, read back with readOct, drawn as Octet's editor draws it, exported with
// standaloneSvg (plus a 6 pt margin) and measured.
//
// Page API (results are JSON-able):
//   window.drawFigure(job) -> result (the job is made by octet_draw.py; see build_job there)
//   window.reexport(octText, names) -> {svg, lost, foreign}: the SVG of a saved .oct read in a fresh page
import {parse} from 'octet-src/file.ts';
import {writeOct, readOct} from 'octet-src/oct.ts';
import {toCdxml} from 'octet-src/cdxml.ts';
import {render as nativeRender, arrowShapes, arrowPath, placeCaptions, labelTurn, hydrogens, orderOf, fitArrows, shapeInk} from 'octet-src/render.ts';
import {lines as richLines} from 'octet-src/richtext.ts';
import {frameStyle, DEFAULT_STYLE, fontStack} from 'octet-src/docstyle.ts';
import {standaloneSvg, glyphInk, inkOfText, withMargin} from 'octet-src/export.ts';
import {measurer} from 'octet-src/chem.ts';
import {formulaCaption, formulaRuns, ELEMENTS} from 'octet-src/labels.ts';
import {widthOf} from 'octet-src/arial.ts';

type Pt = [number, number];
type Box = [number, number, number, number];
type End = {kind: 'atom' | 'bond' | 'gap'; atoms: number[]};
type CurvedReq = {id: string; src: End; snk: End; electrons?: number; bend?: number};
type NumberReq = {atom: number; caption: number};
type TitleReq = {caption: number; atoms: number[]; autoX: boolean; autoY: boolean; generated?: boolean};

const L = 58;                    // px per bond length in Octet's drawing frame
const PAIR_GAP = 0.13 * L;       // tail just outside the two dots, with the usual ink clearance
const HBOND = 10;
const NS = 'http://www.w3.org/2000/svg';
const GAP_PT = 15;               // ACS: a title's baseline 15 pt below its structure's ink (render.ts GAP_PT)
const now = () => performance.now();
const node = (name: string, attrs: any, parent: Element, text?: string) => {
  const e = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) if (v !== undefined) e.setAttribute(k, String(v));
  if (text !== undefined) e.textContent = text;
  parent.appendChild(e);
  return e;
};
// The editor's polygon-to-path serialization.
const toPath = (polys: number[][][]) => polys.map((poly) => 'M' + poly.map(([x, y]) => `${x.toFixed(2)} ${y.toFixed(2)}`).join('L') + 'Z').join('');
const dist = (a: Pt, b: Pt) => Math.hypot(a[0] - b[0], a[1] - b[1]);
const boxDist = (p: Pt, b: Box) => Math.hypot(Math.max(b[0] - p[0], 0, p[0] - b[2]), Math.max(b[1] - p[1], 0, p[1] - b[3]));
const boxGap = (a: Box, b: Box) => Math.hypot(Math.max(b[0] - a[2], a[0] - b[2], 0), Math.max(b[1] - a[3], a[1] - b[3], 0));
const union = (bs: Box[]): Box | null => (bs.length ? [Math.min(...bs.map((b) => b[0])), Math.min(...bs.map((b) => b[1])), Math.max(...bs.map((b) => b[2])), Math.max(...bs.map((b) => b[3]))] : null);
const pad = (b: Box, m: number): Box => [b[0] - m, b[1] - m, b[2] + m, b[3] + m];
const segDist = (p: Pt, a: Pt, b: Pt) => {
  const dx = b[0] - a[0], dy = b[1] - a[1], l2 = dx * dx + dy * dy;
  const t = l2 === 0 ? 0 : Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2));
  return Math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy));
};
// distance along the ray p + s*u (s >= 0) to where it enters box b, or to segment a-b; null when it misses (check_rules.py _ray_box, _ray_seg)
const rayBox = (p: Pt, u: Pt, b: Box): number | null => {
  let lo = 0, hi = Infinity;
  for (const k of [0, 1]) {
    if (Math.abs(u[k]) < 1e-12) { if (p[k] < b[k] || p[k] > b[k + 2]) return null; continue; }
    const t1 = (b[k] - p[k]) / u[k], t2 = (b[k + 2] - p[k]) / u[k];
    lo = Math.max(lo, Math.min(t1, t2)); hi = Math.min(hi, Math.max(t1, t2));
  }
  return lo <= hi ? lo : null;
};
const raySeg = (p: Pt, u: Pt, a: Pt, b: Pt): number | null => {
  const ex = b[0] - a[0], ey = b[1] - a[1], den = u[0] * ey - u[1] * ex;
  if (Math.abs(den) < 1e-12) return null;
  const s = ((a[0] - p[0]) * ey - (a[1] - p[1]) * ex) / den, w = ((a[0] - p[0]) * u[1] - (a[1] - p[1]) * u[0]) / den;
  return s >= 0 && w >= 0 && w <= 1 ? s : null;
};
const pageDeg = (from: Pt, to: Pt) => (((Math.atan2(-(to[1] - from[1]), to[0] - from[0]) * 180) / Math.PI) + 360) % 360;   // counterclockwise on the page
const angDiff = (a: number, b: number) => Math.abs(((a - b + 540) % 360) - 180);
const r2 = (v: number, k = 100) => Math.round(v * k) / k;
const isChargeText = (t: string) => /^\d*[+–−-]$/.test(t);

// Octet has dotted hydrogen bonds but no dotted covalent display. Preserve its bond graph,
// clipping, line spacing and colors, replacing only partial-line dash ink by round dots.
function renderDotted(mol: any, f: any, measure: any, scale: number) {
  const d = nativeRender(mol, f, measure, scale), remove = new Set<number>();
  if ((mol.annotations ?? []).some((a: any) => a.keyword === 'figure-drawing' && JSON.parse(a.content).partial_bonds === 'dashed')) return d;
  const dots: {poly: Pt[]; color: string | undefined; alpha: number}[] = [];
  mol.bonds.forEach((b: any, bi: number) => {
    if (b.display !== 'dashed' || ![1, 2].includes(b.type)) return;
    const p: Pt = [mol.atoms[b.atoms[0]].location[0] * scale, -mol.atoms[b.atoms[0]].location[1] * scale];
    const q: Pt = [mol.atoms[b.atoms[1]].location[0] * scale, -mol.atoms[b.atoms[1]].location[1] * scale];
    const length = dist(p, q), ux = (q[0] - p[0]) / length, uy = (q[1] - p[1]) / length;
    const offset = b.type === 2 ? (d.sides[bi] || 1) * f.spacing : 0;
    const rows: {k: number; lo: number; hi: number; off: number}[] = [];
    d.polygons.forEach((poly: number[][], k: number) => {
      if (poly.length !== 4) return;
      const along = poly.map(([x, y]) => (x - p[0]) * ux + (y - p[1]) * uy);
      const across = poly.map(([x, y]) => -(x - p[0]) * uy + (y - p[1]) * ux);
      const lo = Math.min(...along), hi = Math.max(...along), off = across.reduce((a, v) => a + v, 0) / 4;
      if (lo < -0.1 || hi > length + 0.1 || hi - lo > f.hash * 0.65 || hi - lo < f.line * 1.1
          || Math.abs(Math.max(...across) - Math.min(...across) - f.line) > 0.1 || Math.abs(off - offset) > 0.1) return;
      rows.push({k, lo, hi, off});
    });
    if (!rows.length) return;
    const lo = Math.min(...rows.map((r) => r.lo)) + f.line / 2, hi = Math.max(...rows.map((r) => r.hi)) - f.line / 2;
    if (hi < lo) return;
    rows.forEach((r) => remove.add(r.k));
    const count = Math.max(3, Math.round((hi - lo) / (f.hash / 2)) + 1);
    for (let k = 0; k < count; k++) {
      const a = lo + (hi - lo) * k / (count - 1), c: Pt = [p[0] + a * ux - offset * uy, p[1] + a * uy + offset * ux];
      const poly: Pt[] = Array.from({length: 20}, (_, j) => [c[0] + f.line / 2 * Math.cos(-2 * Math.PI * j / 20), c[1] + f.line / 2 * Math.sin(-2 * Math.PI * j / 20)] as Pt);
      dots.push({poly, color: d.colours[rows[0].k], alpha: d.alphas[rows[0].k]});
    }
  });
  return {...d, polygons: [...d.polygons.filter((_, k) => !remove.has(k)), ...dots.map((x) => x.poly)],
    colours: [...d.colours.filter((_, k) => !remove.has(k)), ...dots.map((x) => x.color)],
    alphas: [...d.alphas.filter((_, k) => !remove.has(k)), ...dots.map((x) => x.alpha)]};
}

// ---------------------------------------------------------------- distance field over drawn ink ---------
// exact Euclidean distance transform of a pixel mask (Felzenszwalb and Huttenlocher, 2012)
function dt1d(f: Float64Array, n: number, d: Float64Array, v: Int32Array, z: Float64Array) {
  const INF = 1e12;
  let k = 0; v[0] = 0; z[0] = -INF; z[1] = INF;
  for (let q = 1; q < n; q++) {
    let s = ((f[q] + q * q) - (f[v[k]] + v[k] * v[k])) / (2 * q - 2 * v[k]);
    while (s <= z[k]) { k--; s = ((f[q] + q * q) - (f[v[k]] + v[k] * v[k])) / (2 * q - 2 * v[k]); }
    k++; v[k] = q; z[k] = s; z[k + 1] = INF;
  }
  k = 0;
  for (let q = 0; q < n; q++) { while (z[k + 1] < q) k++; d[q] = (q - v[k]) * (q - v[k]) + f[v[k]]; }
}
function edt(mask: Uint8Array, w: number, h: number): Float32Array {
  const INF = 1e12, n = Math.max(w, h), f = new Float64Array(n), d = new Float64Array(n), v = new Int32Array(n), z = new Float64Array(n + 1);
  const g = new Float64Array(w * h);
  for (let i = 0; i < w * h; i++) g[i] = mask[i] ? 0 : INF;
  for (let x = 0; x < w; x++) { for (let y = 0; y < h; y++) f[y] = g[y * w + x]; dt1d(f, h, d, v, z); for (let y = 0; y < h; y++) g[y * w + x] = d[y]; }
  for (let y = 0; y < h; y++) { for (let x = 0; x < w; x++) f[x] = g[y * w + x]; dt1d(f, w, d, v, z); for (let x = 0; x < w; x++) g[y * w + x] = d[x]; }
  const out = new Float32Array(w * h);
  for (let i = 0; i < w * h; i++) out[i] = Math.sqrt(g[i]);
  return out;
}
// Distance (px) from any point to the nearest drawn polygon or box.
class Field {
  x0: number; y0: number; w: number; h: number; dt: Float32Array;
  constructor(box: Box, ink: {polys?: number[][][]; boxes?: Box[]}) {
    this.x0 = Math.floor(box[0]) - 20; this.y0 = Math.floor(box[1]) - 20;
    this.w = Math.ceil(box[2] - box[0]) + 40; this.h = Math.ceil(box[3] - box[1]) + 40;
    const cv = document.createElement('canvas'); cv.width = this.w; cv.height = this.h;
    const c = cv.getContext('2d', {willReadFrequently: true})!;
    c.fillStyle = '#000'; c.fillRect(0, 0, this.w, this.h);
    c.fillStyle = '#fff'; c.strokeStyle = '#fff'; c.lineWidth = 1;
    for (const poly of ink.polys ?? []) { c.beginPath(); poly.forEach(([x, y], i) => (i ? c.lineTo(x - this.x0, y - this.y0) : c.moveTo(x - this.x0, y - this.y0))); c.closePath(); c.fill(); c.stroke(); }
    for (const b of ink.boxes ?? []) c.fillRect(b[0] - this.x0, b[1] - this.y0, b[2] - b[0], b[3] - b[1]);
    const img = c.getImageData(0, 0, this.w, this.h).data, mask = new Uint8Array(this.w * this.h);
    for (let i = 0; i < mask.length; i++) mask[i] = img[i * 4] > 127 ? 1 : 0;
    this.dt = edt(mask, this.w, this.h);
  }
  at(p: Pt): number {
    // the pixel that holds the point (pixel k covers k..k+1 of the canvas)
    const x = Math.floor(p[0] - this.x0), y = Math.floor(p[1] - this.y0);
    if (x < 0 || y < 0 || x >= this.w || y >= this.h) return 1e3;
    return this.dt[y * this.w + x];
  }
  // the smallest distance over a box (sampled every `step` px, edges and corners included)
  overBox(b: Box, step = 3): number {
    let m = 1e9;
    for (let x = b[0]; x <= b[2] + 0.01; x += step) for (let y = b[1]; y <= b[3] + 0.01; y += step) m = Math.min(m, this.at([x, y]));
    for (const p of [[b[0], b[1]], [b[2], b[1]], [b[0], b[3]], [b[2], b[3]], [(b[0] + b[2]) / 2, b[1]], [(b[0] + b[2]) / 2, b[3]], [b[0], (b[1] + b[3]) / 2], [b[2], (b[1] + b[3]) / 2]] as Pt[]) m = Math.min(m, this.at(p));
    return m;
  }
}

// ---------------------------------------------------------------- shared context ---------
function makeCtx(mol: any) {
  const style = mol.style, f = frameStyle(style, L), family = fontStack(style.labelFont), pt = (4 / 3) * f.k;
  const measure = (t: string, face?: any) => measurer(face?.font ? fontStack(face.font) : family, f.size, !!face?.bold, !!face?.italic)(t);
  const cctx = document.createElement('canvas').getContext('2d')!;
  const runWidth = (t: string, size: number, bold: boolean | undefined, italic: boolean | undefined, fam: string) => { cctx.font = `${italic ? 'italic ' : ''}${bold ? 'bold ' : ''}${size}px ${fam}`; return cctx.measureText(t).width; };
  // a caption line's width, as the editor measures it: rich text by its runs, conditions on an arrow as a formula
  const capWidth = (t: string, c: any, line = 0) => {
    const px = (c.size ?? style.captionSize) * pt, fam = fontStack(c.font ?? style.captionFont);
    if (c.runs) return (richLines(c.runs)[line] ?? []).reduce((w: number, r: any) => w + runWidth(r.text, (r.size ? r.size * pt : px) * (r.script ? 0.75 : 1), r.bold ?? c.bold, r.italic ?? c.italic, fontStack(r.font ?? c.font ?? style.captionFont)), 0);
    if (formulaCaption(c)) return formulaRuns(t).reduce((w: number, r: any) => w + runWidth(r.text, r.sub ? 0.75 * px : px, c.bold, c.italic, fam), 0);
    return runWidth(t, px, c.bold, c.italic, fam);
  };
  const ratio = (a: any) => (a.size && f.labelPt ? a.size / f.labelPt : 1) * (a.scale ?? 1);
  return {style, f, family, pt, measure, capWidth, ratio};
}
type Ctx = ReturnType<typeof makeCtx>;
// The font the browser draws the labels with, against Arial's own advance widths (Octet's arial.ts): a line of letters
// and digits measured on a canvas.  Without Arial or a font with its widths (Liberation Sans, Arimo) the browser falls
// back to another font, and every label box, gap and visible line is measured in it (the SVG still names Arial).
const FONT_TEST = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
const FONT_WIDTH_TOL = 0.01;
function fontCheck(ctx: Ctx) {
  const font = ctx.style.labelFont as string, c = document.createElement('canvas').getContext('2d')!;
  c.font = `100px ${ctx.family}`;
  const measured = c.measureText(FONT_TEST).width, arial = widthOf(FONT_TEST, 100);
  return {font, family: ctx.family, checked: font === 'Arial' || font === 'Helvetica', measured_px: r2(measured, 1000), arial_px: r2(arial, 1000), ratio: r2(measured / arial, 10000)};
}
(window as any).checkEnvironment = () => {
  const font = fontCheck(makeCtx({style: {...DEFAULT_STYLE, labelFont: 'Arial'}}));
  return {...font, ok: font.checked && Math.abs(font.ratio - 1) <= FONT_WIDTH_TOL};
};
const atomPxOf = (mol: any): Pt[] => mol.atoms.map((a: any) => [a.location[0] * L, -a.location[1] * L] as Pt);
const fittedArrows = (mol: any, ctx: Ctx) => fitArrows(mol, L, (c: any) => Math.max(...c.text.split('\n').map((t: string, j: number) => ctx.capWidth(t, c, j))), ctx.pt);
const placed = (mol: any, d: any, ctx: Ctx, arrows: any[]) => placeCaptions(mol, d, ctx.capWidth, arrows, ctx.pt, ctx.style.captionSize);
// Captions that are obstacles while things are placed: not the atom numbers (placed last) and not the titles that are
// still waiting for their place (they sit at the origin until then).
const obstacleCaps = (mol: any, caps: any[], job: any) => {
  const skip = new Set<number>([...(job.numbers ?? []).map((n: NumberReq) => mol.captions[n.caption]?.id),
    ...(job.titles ?? []).filter((t: TitleReq) => (t.autoX || t.autoY) && !job.titlesPlaced).map((t: TitleReq) => mol.captions[t.caption]?.id)]);
  return caps.filter((c: any) => !skip.has(c.id));
};

// What each polygon of a drawing is: 'mark' (a circled charge's ring and sign, lone pairs, radical dots: polygons wholly
// inside the mark's reach around its center in `electrons`), 'hbond' (the dots of a hydrogen bond) or 'bond'.
function classify(mol: any, d: any, ctx: Ctx): string[] {
  const {f, ratio} = ctx, hw = f.line / 2, cls: string[] = d.polygons.map(() => 'bond'), px = atomPxOf(mol);
  mol.bonds.forEach((b: any) => {
    if (b.type !== HBOND) return;
    const p = px[b.atoms[0]], q = px[b.atoms[1]];
    d.polygons.forEach((poly: number[][], k: number) => { if (cls[k] === 'bond' && poly.every(([x, y]) => segDist([x, y], p, q) <= hw + 0.5)) cls[k] = 'hbond'; });
  });
  for (const e of d.electrons) {
    if (!e.key) continue;
    const z = f.size * ratio(mol.atoms[e.atom]);
    const r = e.key === 'charge' ? (mol.atoms[e.atom].circled ? 0.34 * z + hw + 0.6 : 0) : e.key.startsWith('pair') ? 0.28 * z + hw + 0.6 : e.key.startsWith('radical') ? 0.1 * z + 0.6 : 0;
    if (!r) continue;
    d.polygons.forEach((poly: number[][], k: number) => { if (cls[k] === 'bond' && poly.every(([x, y]) => Math.hypot(x - e.at[0], y - e.at[1]) <= r)) cls[k] = 'mark'; });
  }
  return cls;
}

// The drawn (visible) part of each bond, measured along its axis on its own polygons (px): a bond that stops at a letter
// is shorter than its atom-to-atom length, and this is what the eye reads as its length. s0 and s1 run from atoms[0].
const ownersMemo = new WeakMap<any, number[]>();
// The bond each 'bond' polygon belongs to: the one whose axis is nearest to the polygon's center (-1: none).
function polygonOwners(mol: any, d: any, cls: string[]): number[] {
  const hit = ownersMemo.get(d);
  if (hit) return hit;
  const px = (i: number): Pt => [mol.atoms[i].location[0] * L, -mol.atoms[i].location[1] * L];
  const owners = d.polygons.map((poly: number[][], k: number) => {
    if (cls[k] !== 'bond') return -1;
    const center: Pt = [poly.reduce((s, p) => s + p[0], 0) / poly.length, poly.reduce((s, p) => s + p[1], 0) / poly.length];
    let owner = -1, nearest = Infinity;
    mol.bonds.forEach((other: any, oi: number) => {
      if (other.type === HBOND || other.atoms.some((i: number) => mol.atoms[i].hidden)) return;
      const gap = segDist(center, px(other.atoms[0]), px(other.atoms[1]));
      if (gap < nearest) { nearest = gap; owner = oi; }
    });
    return owner;
  });
  ownersMemo.set(d, owners);
  return owners;
}
function bondVisible(mol: any, d: any, ctx: Ctx, cls: string[], bi: number): {len: number; s0: number; s1: number; visible: number} | null {
  const {f} = ctx, b = mol.bonds[bi];
  if (b.type === HBOND) return null;
  const px = (i: number): Pt => [mol.atoms[i].location[0] * L, -mol.atoms[i].location[1] * L];
  const p = px(b.atoms[0]), q = px(b.atoms[1]), len = dist(p, q);
  if (len < 1e-6) return null;
  const u: Pt = [(q[0] - p[0]) / len, (q[1] - p[1]) / len];
  const off = b.type === 1 && !b.stereo && b.display !== 'bold' ? 0 : b.type === 14 ? 1.5 * f.spacing : f.spacing;
  const half = b.stereo || b.display ? 0.75 * f.bold + f.line / 2 : f.line / 2;
  const tol = off + half + 1.0;
  let s0 = Infinity, s1 = -Infinity;
  const owners = polygonOwners(mol, d, cls);
  d.polygons.forEach((poly: number[][], k: number) => {
    if (owners[k] !== bi) return;
    let amin = Infinity, amax = -Infinity, pe = 0;
    for (const [x, y] of poly) { const a = (x - p[0]) * u[0] + (y - p[1]) * u[1]; amin = Math.min(amin, a); amax = Math.max(amax, a); pe = Math.max(pe, Math.abs((x - p[0]) * u[1] - (y - p[1]) * u[0])); }
    if (pe > tol || amax < 0 || amin > len) return;
    s0 = Math.min(s0, amin); s1 = Math.max(s1, amax);
  });
  if (!Number.isFinite(s0)) return null;
  s0 = Math.max(0, s0); s1 = Math.min(len, s1);
  return {len, s0, s1, visible: s1 - s0};
}

// Each atom's label pieces (px boxes from Octet's glyph metrics) and whether a piece is a charge sign.
function piecesOf(mol: any, d: any, ctx: Ctx) {
  const {f, measure} = ctx, px = atomPxOf(mol), key = (p: Pt) => `${Math.round(p[0] * 2)} ${Math.round(p[1] * 2)}`;
  const at = new Map<string, number>();
  px.forEach((p, i) => at.set(key(p), i));
  // box: the advance from the cap ascent to the lowest ink; ink: the glyphs' own ink (what a reader sees and what
  // check_rules.py measures numbers against)
  const out: {text: string; box: Box; ink: Box; sign: boolean; k: number}[][] = mol.atoms.map(() => []);
  d.labels.forEach((l: any, k: number) => {
    const a = d.labelAt[k] ? at.get(key(d.labelAt[k])) : undefined;
    if (a === undefined) return;
    const m = measure(l.text, l.font || l.bold || l.italic ? {font: l.font, bold: l.bold, italic: l.italic} : undefined), s = l.size / f.size;
    let desc = 0;                    // ink below the baseline (the g of Mg)
    let il = Infinity, it = Infinity, ir = -Infinity, ib = -Infinity;
    for (const q of m.outline) { if (q[1] > desc) desc = q[1]; il = Math.min(il, q[0]); ir = Math.max(ir, q[0]); it = Math.min(it, q[1]); ib = Math.max(ib, q[1]); }
    const box: Box = [l.x, l.y - m.ascent * s, l.x + m.width * s, l.y + desc * s];
    out[a].push({text: l.text, box, ink: Number.isFinite(il) ? [l.x + il * s, l.y + it * s, l.x + ir * s, l.y + ib * s] : box, sign: isChargeText(l.text), k});
  });
  return out;
}

// The box of an atom's own symbol (the O of OH, the N of NH3, the C of CH3) without the hydrogens written beside it;
// the whole label when it holds no such piece (abbreviations); null for a bare vertex.
function ownSymbol(mol: any, pcs: {text: string; box: Box; sign: boolean}[][], px: Pt[], i: number): Box | null {
  const own = pcs[i].filter((p) => !p.sign && p.text === mol.atoms[i].label);
  return own.length ? own.reduce((a, b) => (boxDist(px[i], a.box) <= boxDist(px[i], b.box) ? a : b)).box : union(pcs[i].filter((p) => !p.sign).map((p) => p.box));
}

// What an arrow end reads as: the nearest atom (the box of its symbol letters, or the point of a bare vertex), unless a
// bond's axis is nearer and the end sits beside the middle part of that bond (20-80 % along it): then that bond.
// `center` is the atom whose center is nearest.  The router keeps every end reading as what was asked; the report
// gives this reading for each end.
function readEnd(mol: any, px: Pt[], symbolBox: (j: number) => Box | null, p: Pt) {
  let atom = -1, dA = 1e9, center = -1, dC = 1e9, bond = -1, dB = 1e9, along = 0;
  px.forEach((q, j) => {
    if (mol.atoms[j].hidden) return;
    const b = symbolBox(j), v = b ? boxDist(p, b) : dist(p, q), c = dist(p, q);
    if (v < dA) { dA = v; atom = j; }
    if (c < dC) { dC = c; center = j; }
  });
  mol.bonds.forEach((b: any, bi: number) => { if (b.type === HBOND || b.atoms.some((i: number) => mol.atoms[i].hidden)) return; const v = segDist(p, px[b.atoms[0]], px[b.atoms[1]]); if (v < dB) { dB = v; bond = bi; } });
  if (bond >= 0) {
    const a = px[mol.bonds[bond].atoms[0]], c = px[mol.bonds[bond].atoms[1]], l2 = (c[0] - a[0]) ** 2 + (c[1] - a[1]) ** 2;
    along = l2 ? ((p[0] - a[0]) * (c[0] - a[0]) + (p[1] - a[1]) * (c[1] - a[1])) / l2 : 0;
  }
  const middle = bond >= 0 && along > 0.2 && along < 0.8;
  return {kind: (middle && dB < dA ? 'bond' : 'atom') as 'atom' | 'bond', atom, bond, center, dA, dB, middle};
}

// ---------------------------------------------------------------- 1. label-label bonds ---------
// A bond between two labels keeps the standard length.  Only when its line would read as a dot (under LINE_DOT), a
// curved arrow starts from or ends at it, or a circled charge sits squeezed between the two labels (`extra`), the
// smaller side moves out along the bond until LINE_SHOW of line shows.
const LINE_SHOW = 0.6 * L, LINE_DOT = 0.25 * L;
function lengthenLabelBonds(mol: any, ctx: Ctx, job: any, extra: Set<number> = new Set()) {
  const t0 = now(), rows: any[] = [], skipped: any[] = [], moveEnds = job.moveEnds ?? [];
  const bondOf = (e: End) => mol.bonds.findIndex((b: any) => b.type !== HBOND && b.atoms.includes(e.atoms[0]) && b.atoms.includes(e.atoms[1]));
  const withArrow = new Set<number>(((job.curved ?? []) as CurvedReq[]).flatMap((r) => [r.src, r.snk]).filter((e) => e.kind === 'bond').map(bondOf));
  const side = (start: number, across: number, cut: number): number[] | null => {   // the atoms on start's side of bond `cut`; null in a ring
    const seen = new Set<number>([start]), todo = [start];
    while (todo.length) {
      const i = todo.pop()!;
      mol.bonds.forEach((b: any, k: number) => {
        if (k === cut || b.type === HBOND || !b.atoms.includes(i)) return;
        const j = b.atoms[0] === i ? b.atoms[1] : b.atoms[0];
        if (!seen.has(j)) { seen.add(j); todo.push(j); }
      });
    }
    return seen.has(across) ? null : [...seen];
  };
  mol.bonds.forEach((b: any, bi: number) => {
    if (b.type === HBOND || b.atoms.some((i: number) => mol.atoms[i].hidden) || (extra.size && !extra.has(bi))) return;
    const {d, cls} = drawn(mol, ctx);
    if (!b.atoms.every((i: number) => d.label[i])) return;
    const v = bondVisible(mol, d, ctx, cls, bi), visible = v?.visible ?? 0;
    if (visible >= LINE_SHOW || (visible >= LINE_DOT && !withArrow.has(bi) && !extra.has(bi))) return;
    const asked = moveEnds.find((r: any) => r.bond === bi)?.atom;
    const ends = b.atoms.map((i: number) => ({i, atoms: side(i, b.atoms[0] === i ? b.atoms[1] : b.atoms[0], bi)})).filter((c: any) => c.atoms)
      .sort((p: any, q: any) => Number(q.i === asked) - Number(p.i === asked) || p.atoms.length - q.atoms.length);
    if (!ends.length) { skipped.push({bond: bi, reason: 'ring bond'}); return; }
    const {i: moving, atoms} = ends[0], anchor = b.atoms[0] === moving ? b.atoms[1] : b.atoms[0];
    const from = mol.atoms[anchor].location, to = mol.atoms[moving].location, length = Math.hypot(to[0] - from[0], to[1] - from[1]);
    const grow = (LINE_SHOW - visible) / L, ux = (to[0] - from[0]) / length, uy = (to[1] - from[1]) / length;   // the visible line grows as the bond does
    for (const j of atoms) { const q = mol.atoms[j].location; mol.atoms[j].location = [q[0] + ux * grow, q[1] + uy * grow, ...q.slice(2)]; }
    rows.push({bond: bi, moving, named: moving === asked, branch: atoms, moved_px: grow * L, length_before_px: length * L, length_px: (length + grow) * L,
      visible_before_px: visible, visible_px: LINE_SHOW, target_px: LINE_SHOW});
  });
  return {target_px: LINE_SHOW, rows, skipped, ms: now() - t0};
}

// ---------------------------------------------------------------- 2. circled charges ---------
// Octet puts a circled charge up and to the right of its atom when that is clear of the atom's own bonds, else in the
// widest gap; it does not look at other atoms, arrows or text. Here every circled single charge without a set angle
// takes the first open seat of eight (upper right, upper left, lower right, lower left, right, left, above, below),
// clear of other ink and of where its curved arrows go; when none is open, the one of 24 directions with the most
// room.  The same atom in several panels takes one seat where that fits in every panel.
function placeCharges(mol: any, ctx: Ctx, job: any) {
  const {f, measure, ratio} = ctx, t0 = now(), fixed = new Set<number>(job.fixedChargeAngles ?? []);
  const todo: number[] = mol.atoms.map((_: any, i: number) => i).filter((i: number) => mol.atoms[i].circled && Math.abs(mol.atoms[i].charge ?? 0) === 1 && !fixed.has(i));
  if (!todo.length) return {rows: [], ms: now() - t0};
  const base = render(mol, f, measure, L), cls = classify(mol, base, ctx), px = atomPxOf(mol), hw = f.line / 2;
  const arrows = fittedArrows(mol, ctx), caps = placed(mol, base, ctx, arrows);
  const capBoxes: Box[] = obstacleCaps(mol, caps, job).map((c: any) => c.box);
  const polys = [...base.polygons.filter((_: any, k: number) => cls[k] !== 'mark'), ...arrows.flatMap((a: any) => arrowShapes(a, f, L)), ...(mol.shapes ?? []).flatMap((s: any) => shapeInk(s, f, L))];
  const pcs = piecesOf(mol, base, ctx);
  const all: Box[] = [...pcs.flat().map((p) => p.box), ...capBoxes];
  const bb = union([...px.map((p) => [p[0], p[1], p[0], p[1]] as Box), ...all]) ?? [0, 0, 1, 1];
  const field = new Field(pad(bb, 2 * L), {polys});
  const angles = Array.from({length: 24}, (_, k) => k * 15);
  if (job.options?.repairCharges) for (let a = 1.25; a < 360; a += 1.25) if (a % 15) angles.push(a);
  const centers = new Map<number, (Pt | null)[]>(todo.map((i) => [i, angles.map(() => null)]));
  const saved = new Map<number, any>(todo.map((i) => [i, mol.atoms[i].angles]));
  angles.forEach((deg, k) => {
    for (const i of todo) mol.atoms[i].angles = {...(saved.get(i) ?? {}), charge: deg};
    const dk = render(mol, f, measure, L);
    for (const e of dk.electrons) if (e.key === 'charge' && centers.has(e.atom)) centers.get(e.atom)![k] = e.at;
  });
  for (const i of todo) { if (saved.get(i)) mol.atoms[i].angles = saved.get(i); else delete mol.atoms[i].angles; }
  // where the curved arrows at each atom go: from an atom end toward the other end; around the middle of a bond end;
  // along the line between the two ends
  const endPoint = (e: End): Pt => (e.kind === 'atom' ? px[e.atoms[0]] : [(px[e.atoms[0]][0] + px[e.atoms[1]][0]) / 2, (px[e.atoms[0]][1] + px[e.atoms[1]][1]) / 2]);
  const corridors = new Map<number, number[]>(), bondMids = new Map<number, Pt[]>(), chords = new Map<number, [Pt, Pt][]>();
  const add = <T,>(m: Map<number, T[]>, i: number, v: T) => { if (!m.has(i)) m.set(i, []); m.get(i)!.push(v); };
  for (const r of (job.curved ?? []) as CurvedReq[]) {
    for (const [me, them] of [[r.src, r.snk], [r.snk, r.src]] as [End, End][]) {
      if (me.kind === 'atom') add(corridors, me.atoms[0], pageDeg(px[me.atoms[0]], endPoint(them)));
      else for (const i of me.atoms) add(bondMids, i, endPoint(me));
    }
    for (const i of new Set([...r.src.atoms, ...r.snk.atoms])) add(chords, i, [endPoint(r.src), endPoint(r.snk)] as [Pt, Pt]);
  }
  const nbrDirs = (i: number) => mol.bonds.filter((b: any) => b.atoms.includes(i) && !b.atoms.some((j: number) => mol.atoms[j].hidden)).map((b: any) => pageDeg(px[i], px[b.atoms[0] === i ? b.atoms[1] : b.atoms[0]]));
  const chosen = new Map<number, Pt>();
  const reacting = new Set<number>((job.curved ?? []).filter((r: CurvedReq) => r.electrons !== 1 && r.src.kind === 'atom').map((r: CurvedReq) => r.src.atoms[0]));
  const cost = (i: number, k: number) => {
    const c = centers.get(i)![k];
    if (!c) return {total: 1e9, clear: -1e3, ownership: 1e6};
    const z = f.size * ratio(mol.atoms[i]), Rout = 0.34 * z + hw;
    let clear = field.at(c) - Rout;
    // Octet already seats the ring just clear of its own label's outline; measure the room to everything else
    pcs.forEach((list, j) => { if (j !== i) for (const p of list) clear = Math.min(clear, boxDist(c, p.box) - Rout); });
    for (const b of capBoxes) clear = Math.min(clear, boxDist(c, b) - Rout);
    for (const e of base.electrons) if (e.key?.startsWith('pair')) clear = Math.min(clear, dist(c, e.at) - Rout - 0.28 * f.size * ratio(mol.atoms[e.atom]));
    for (const [j, q] of chosen) if (j !== i) clear = Math.min(clear, dist(c, q) - 2 * Rout);
    const th = pageDeg(px[i], c), dirs = nbrDirs(i);
    const sep = dirs.length ? Math.min(...dirs.map((b: number) => angDiff(th, b))) : 180;
    const corr = (corridors.get(i) ?? []).reduce((s, a) => s + Math.max(0, 75 - angDiff(th, a)) * 3, 0)
      + (bondMids.get(i) ?? []).reduce((s, m) => s + Math.max(0, 0.75 * L - dist(c, m)) * (60 / L), 0)
      + (chords.get(i) ?? []).reduce((s, [p, q]) => s + Math.max(0, 0.35 * L - segDist(c, p, q)) * (80 / L), 0);
    const near = (dist(c, px[i]) / z) * 30;
    let ownership = 0;
    {
      const pg = (b: Box) => {
        const dx = Math.max(b[0] - c[0], 0, c[0] - b[2]), dy = Math.max(b[1] - c[1], 0, c[1] - b[3]);
        return dx || dy ? Math.hypot(dx, dy) : -Math.min(c[0] - b[0], b[2] - c[0], c[1] - b[1], b[3] - c[1]);
      };
      const gap = (j: number) => pcs[j].length ? Math.min(...pcs[j].map((p) => pg(p.ink))) - Rout : dist(c, px[j]) - Rout;
      const own = gap(i), other = Math.min(...px.map((_, j) => j === i ? Infinity : gap(j)));
      const symbols = pcs[i].filter((p) => !p.sign && p.text === mol.atoms[i].label);
      const symbol = symbols.length ? symbols.reduce((a, b) => boxDist(px[i], a.ink) < boxDist(px[i], b.ink) ? a : b).ink : null;
      // Match the saved-drawing check's whole hydrogen tail, not just its separate glyphs.
      const box: Box | null = base.label[i], tail: Box | null = !box || !symbol ? null
        : box[2] - symbol[2] > 2 * ctx.pt ? [symbol[2], box[1], box[2], box[3]]
        : symbol[0] - box[0] > 2 * ctx.pt ? [box[0], box[1], symbol[0], box[3]] : null;
      // hydrogens stacked above or below the symbol (H2 over N): a sign nearer to them than to the symbol reads as theirs
      const stacked = !symbol ? [] : pcs[i].filter((p) => !p.sign && p.ink !== symbol && p.ink[0] < symbol[2] && p.ink[2] > symbol[0] && (p.ink[3] <= symbol[1] + 1 || p.ink[1] >= symbol[3] - 1));
      if (other < own + 0.05 * ctx.pt || (symbol && (pg(symbol) - Rout > 2.95 * ctx.pt
          || (tail && pg(tail) < pg(symbol) + 0.05 * ctx.pt) || stacked.some((p) => pg(p.ink) < pg(symbol) + 0.05 * ctx.pt)))) ownership = 1e6;
      // the ring may reach into the empty corner of its own label box only as far as check_rules.py allows (0.5 pt)
      if (pcs[i].some((p) => !p.sign && pg(p.box) - Rout < -0.45 * ctx.pt)) ownership = 1e6;
    }
    const total = ownership + (sep < 26 ? 1e6 : 0) + (clear < 2 ? 1000 + (2 - clear) * 200 : 0) + (clear < 10 ? (10 - clear) ** 2 * 0.8 : 0) + Math.max(0, 50 - sep) * 2 + corr + near + 0.03 * angDiff(th, 45);
    return {total, clear, th, ownership, sep, corr};
  };
  // the same atom in several panels (job.sameAtom) is placed together
  const groups: number[][] = [];
  const inGroup = new Set<number>();
  for (const g of (job.sameAtom ?? []) as number[][]) { const m = g.filter((i) => centers.has(i)); if (m.length > 1) { groups.push(m); m.forEach((i) => inGroup.add(i)); } }
  for (const i of todo) if (!inGroup.has(i)) groups.push([i]);
  const rows: any[] = [];
  const minClear = job.options?.repairCharges ? 4 : 2;
  for (const g of groups) {
    let bestK = -1, best = Infinity;
    angles.forEach((_, k) => { const cs = g.map((i) => cost(i, k)); if (cs.some((c) => c.clear < minClear || c.ownership || (c.sep ?? 0) < 26)) return; const s = cs.reduce((t, c) => t + c.total, 0); if (s < best) { best = s; bestK = k; } });
    // the first open seat, diagonals first: upper right, upper left, lower right, lower left, then right, left, above,
    // below; other directions only when none is open
    const diagonals = [45, 135, 315, 225, 0, 180, 90, 270].map((a) => angles.indexOf(a));
    const open = (i: number, k: number) => { const c = cost(i, k); return c.clear >= minClear && !c.ownership && (c.sep ?? 0) >= 35 && !c.corr; };
    const shared = diagonals.find((k) => g.every((i) => open(i, k)));
    const cheapest = (i: number) => { let kk = 0, bv = Infinity; angles.forEach((_, k) => { const c = cost(i, k).total; if (c < bv) { bv = c; kk = k; } }); return kk; };
    for (const i of g) {
      const k = shared ?? diagonals.find((d) => open(i, d)) ?? (bestK >= 0 ? bestK : cheapest(i)), c = cost(i, k);
      mol.atoms[i].angles = {...(mol.atoms[i].angles ?? {}), charge: angles[k]};
      chosen.set(i, centers.get(i)![k]!);
      const squeezed = squeezedBy(mol, ctx, pcs, i, centers.get(i)![k]!);
      rows.push({atom: i, angle_deg: angles[k], together: g.length > 1 && bestK >= 0, clearance_px: r2(c.clear), cost: r2(c.total), squeezed});
    }
  }
  return {rows, ms: now() - t0};
}

// bonded labels whose letters come within 2.95 pt of the ring's distance to its own letters: the ring at `at` reads as
// squeezed between the two (the O- of Zn-OH beside the Zn)
function squeezedBy(mol: any, ctx: Ctx, pcs: any[][], i: number, at: Pt): number[] {
  const Rout = 0.34 * ctx.f.size * ctx.ratio(mol.atoms[i]) + ctx.f.line / 2;
  const glyph = (j: number) => Math.min(Infinity, ...pcs[j].filter((p: any) => !p.sign).map((p: any) => boxDist(at, p.ink))) - Rout;
  return mol.bonds.filter((b: any) => b.type !== HBOND && b.atoms.includes(i)).map((b: any) => b.atoms[0] === i ? b.atoms[1] : b.atoms[0])
    .filter((j: number) => pcs[j].length && glyph(j) - glyph(i) < 2.95 * ctx.pt);
}

// the same test for rings whose angle is fixed (kept by a retry), which placeCharges leaves where they are
function squeezedFixed(mol: any, ctx: Ctx, job: any) {
  const fixed = new Set<number>(job.fixedChargeAngles ?? []);
  if (!mol.atoms.some((a: any, i: number) => fixed.has(i) && a.circled && Math.abs(a.charge ?? 0) === 1)) return [];
  const d = render(mol, ctx.f, ctx.measure, L), pcs = piecesOf(mol, d, ctx);
  return d.electrons.filter((e: any) => e.key === 'charge' && fixed.has(e.atom) && mol.atoms[e.atom].circled && Math.abs(mol.atoms[e.atom].charge ?? 0) === 1)
    .map((e: any) => ({atom: e.atom, squeezed: squeezedBy(mol, ctx, pcs, e.atom, e.at)}));
}

// The reacting pair faces the arrow target where the atom's bonds and label leave room.
// Octet's per-mark angles keep this position in both native and CDXML saves.
function placeLonePairs(mol: any, ctx: Ctx, job: any) {
  const px = atomPxOf(mol), {f, measure} = ctx;
  const sources = new Map<number, End>();
  for (const r of (job.curved ?? []) as CurvedReq[]) if (r.electrons !== 1 && r.src.kind === 'atom' && mol.atoms[r.src.atoms[0]].pairs)
    sources.set(r.src.atoms[0], r.snk);
  for (let i = 0; i < mol.atoms.length; i++) {
    const count = Math.min(4, mol.atoms[i].pairs ?? 0);
    if (!count) continue;
    const saved = {...(mol.atoms[i].angles ?? {})}, used: number[] = [];
    const end = sources.get(i), target: Pt | null = !end ? null : end.kind === 'atom' ? px[end.atoms[0]]
      : [(px[end.atoms[0]][0] + px[end.atoms[1]][0]) / 2, (px[end.atoms[0]][1] + px[end.atoms[1]][1]) / 2];
    const want = target ? pageDeg(px[i], target) : 90;
    for (let pairIndex = 0; pairIndex < count; pairIndex++) {
      const key = `pair${pairIndex}`;
      mol.atoms[i].pairs = pairIndex + 1;  // later pairs must not occupy unassigned seats
      let best = Infinity, angle = 90, axialClear = false;
      for (const deg of [90, 270, 0, 180, 45, 135, 225, 315].filter((a) => !used.includes(a))) {
        if (deg % 90 && axialClear) continue;
        mol.atoms[i].angles = {...saved, ...Object.fromEntries(used.map((a, k) => [`pair${k}`, a])), [key]: deg};
        const d = render(mol, f, measure, L), pair = d.electrons.find((e: any) => e.atom === i && e.key === key);
        if (!pair) continue;
        const z = f.size * ctx.ratio(mol.atoms[i]), dotRadius = .09 * z;
        const radians = deg * Math.PI / 180, normal: Pt = [Math.sin(radians), Math.cos(radians)];
        const dots: Pt[] = [-1, 1].map((sign) => [pair.at[0] + sign * .19 * z * normal[0], pair.at[1] + sign * .19 * z * normal[1]] as Pt);
        const own = (poly: number[][]) => dots.some((dot) => poly.every(([x, y]) => dist([x, y], dot) <= dotRadius + .1));
        const movableCharges = d.electrons.filter((e: any) => e.key === 'charge' && mol.atoms[e.atom].circled && !(job.fixedChargeAngles ?? []).includes(e.atom));
        const ink = d.polygons.filter((poly: number[][]) => !own(poly) && !movableCharges.some((e: any) =>
          poly.every(([x, y]) => dist([x, y], e.at) <= .34 * f.size * ctx.ratio(mol.atoms[e.atom]) + f.line / 2 + .6)));
        const field = new Field(pad(union(dots.map((p) => [p[0], p[1], p[0], p[1]] as Box))!, 12), {polys: ink});
        let clear = Math.min(...dots.map((dot) => field.at(dot) - dotRadius));
        const pcs = piecesOf(mol, d, ctx);
        pcs.forEach((list, j) => { if (j !== i) for (const p of list) for (const dot of dots) clear = Math.min(clear, boxDist(dot, p.box) - dotRadius); });
        // A seat past the H of the atom's own label (left of H2N) reads as the H's pair: blocked.
        const symbol = ownSymbol(mol, pcs, px, i);
        if (symbol && Math.min(...dots.map((dot) => boxDist(dot, symbol))) > .5 * z) clear = Math.min(clear, 0);
        const bondDirs = mol.bonds.filter((b: any) => b.type !== HBOND && b.atoms.includes(i)).map((b: any) => pageDeg(px[i], px[b.atoms[0] === i ? b.atoms[1] : b.atoms[0]]));
        const sep = Math.min(180, ...bondDirs.map((b: number) => angDiff(deg, b)));
        // a reacting pair takes no seat facing away (more than 90 degrees) from what it attacks
        // ... nor a seat with one of the atom's own bonds between it and what it attacks (the arrow would have to cross
        // or go round that bond)
        const across = bondDirs.some((b: number) => angDiff(deg, b) + angDiff(b, want) <= angDiff(deg, want) + .5 && angDiff(deg, b) > .5 && angDiff(b, want) > .5);
        const away = pairIndex === 0 && target && (angDiff(deg, want) > 90 || across);
        if (!(deg % 90) && clear >= 1 && sep >= 35 && !away) axialClear = true;
        // Prefer axial seats; diagonal seats are allowed only when every axial seat is blocked.
        // The explicit pair identifies its atom; a nearby bare vertex is not an electron source.
        const score = Math.max(0, 1 - clear) * 1000 + Math.max(0, 35 - sep) * 30 + (deg % 90 ? 180 : 0) + (away ? 1000 : 0)
          + (pairIndex === 0 && target ? angDiff(deg, want) : -sep * 0.2);
        if (score < best) { best = score; angle = deg; }
      }
      used.push(angle);
    }
    mol.atoms[i].pairs = count;
    mol.atoms[i].angles = {...saved, ...Object.fromEntries(used.map((a, k) => [`pair${k}`, a]))};
  }
}

// ---------------------------------------------------------------- 3. curved arrows ---------
// IUPAC chemical features use Octet's native marks, hidden H, multicenter atoms and captions.
function chemicalAnnotations(mol: any): Record<string, any> {
  return Object.assign({}, ...(mol.annotations ?? []).filter((a: any) => a.keyword === 'figure-chemistry').map((a: any) => JSON.parse(a.content)));
}
function radicalIonDisplay(mol: any) {
  if (!mol.atoms.some((a: any) => a.radical === 1 || a.radical === 2)) return mol;
  const chemistry = chemicalAnnotations(mol);
  return {...mol, atoms: mol.atoms.map((a: any, i: number) => {
    if (a.radical !== 1 && a.radical !== 2) return a;
    const used = mol.bonds.filter((b: any) => b.atoms.includes(i)).reduce((v: number, b: any) => v + orderOf(b.type), 0);
    const hiddenH = mol.bonds.filter((b: any) => b.atoms.includes(i) && b.atoms.some((j: number) => j !== i && mol.atoms[j].hidden && mol.atoms[j].label === 'H')).length;
    const h = (chemistry[a.hiddenNumber]?.h ?? hydrogens(a.label, a.charge, used, a.radical)) + hiddenH;
    // Keep a native element/H label and native movable electron dots.
    return {...a, implicitHCount: h, shown: true};
  })};
}
function render(mol: any, style: any, measure: any, scale: number): any {
  let display = radicalIonDisplay(mol);
  if (mol.atoms.some((a: any) => a.hidden)) display = {...display, atoms: display.atoms.map((a: any, i: number) => {
    if (a.implicitHCount === undefined || a.text || a.radical) return a;
    const h = mol.bonds.filter((b: any) => b.atoms.includes(i) && b.atoms.some((j: number) => j !== i && mol.atoms[j].hidden && mol.atoms[j].label === 'H')).length;
    return h ? {...a, implicitHCount: a.implicitHCount + h} : a;
  })};
  return renderDotted(display, style, measure, scale);
}
function logicalStraight(mol: any, rows: any[]) {
  const groups: any[] = (mol.annotations ?? []).filter((a: any) => a.keyword === 'figure-arrow-groups').flatMap((a: any) => JSON.parse(a.content));
  const skipped = new Set(groups.flatMap((g: any) => g.indices.slice(1)));
  return rows.flatMap((row, i) => {
    if (skipped.has(i)) return [];
    const group = groups.find((g: any) => g.indices[0] === i);
    if (group?.kind === 'delocalization') return [];
    return [{...row, kind: group?.kind ?? row.kind, segments: group ? group.indices.map((j: number) => rows[j]).filter(Boolean) : [row]}];
  });
}
// The drawing of the document with its polygon classes and label pieces, kept until an atom, a bond or the style changes:
// the label passes ask for it once per atom and per alignment tried.
const drawnMemo = new WeakMap<any, {key: string; d: any; cls: string[]; pcs: ReturnType<typeof piecesOf>}>();
function drawn(mol: any, ctx: Ctx) {
  const key = JSON.stringify([mol.atoms, mol.bonds, ctx.f]), hit = drawnMemo.get(mol);
  if (hit?.key === key) return hit;
  const d = render(mol, ctx.f, ctx.measure, L), made = {key, d, cls: classify(mol, d, ctx), pcs: piecesOf(mol, d, ctx)};
  drawnMemo.set(mol, made);
  return made;
}
// How badly atom i's label sits: its bonds without a visible line, and its letters on other letters or on bond ink.
function labelClash(mol: any, ctx: Ctx, i: number): number {
  const {d, cls, pcs} = drawn(mol, ctx);
  let value = 0;
  mol.bonds.forEach((b: any, k: number) => {
    if (!b.atoms.includes(i) || b.type === HBOND || b.atoms.some((j: number) => mol.atoms[j].hidden)) return;
    const v = bondVisible(mol, d, ctx, cls, k);
    value += !v ? 1e6 : Math.max(0, L / 3 - v.visible - 0.1) * 1000;   // under 0.1 px short is rounding
  });
  for (const part of pcs[i]) for (let j = 0; j < pcs.length; j++) if (j !== i)
    for (const other of pcs[j]) value += Math.max(0, 2 - boxGap(part.box, other.box)) * 100000;
  if (d.label[i] && pcs[i].length) {
    // in a label that writes H, the atom's own bonds meet its symbol by design (their visible length is counted
    // above) and are left out for the symbol, or they would push the H onto the bond side; its written H and every
    // other piece stay off all bonds
    const owners = polygonOwners(mol, d, cls), bonds = d.polygons.filter((_: any, k: number) => cls[k] === 'bond');
    const others = d.polygons.filter((_: any, k: number) => cls[k] === 'bond' && !(owners[k] >= 0 && mol.bonds[owners[k]].atoms.includes(i)));
    const all = new Field(pad(d.label[i], 8), {polys: bonds}), foreign = new Field(pad(d.label[i], 8), {polys: others});
    const writesH = pcs[i].some((p) => !p.sign && p.text !== mol.atoms[i].label);
    for (const part of pcs[i]) {
      const ink = writesH && !part.sign && part.text === mol.atoms[i].label ? foreign : all;
      value += Math.max(0, 2 - ink.overBox(part.box, 1)) * 100000;
    }
  }
  return value;
}
// A folded H may fill the short gap between two standard-length labeled atoms.
// Search Octet's native label alignments without moving any atom or changing H counts.
// A label stacks on several lines (H above or below its symbol) only on an atom with at least two bonds (IUPAC GR-2).
function stackable(mol: any, i: number): boolean {
  return mol.bonds.filter((b: any) => b.atoms.includes(i) && b.type !== HBOND && !b.atoms.some((j: number) => mol.atoms[j].hidden)).length >= 2;
}
const SIDE_DEG: Record<string, number> = {right: 0, above: 90, left: 180, below: 270};
// The side of the symbol where atom i's label writes its H, or null.
function hydrogenSide(mol: any, ctx: Ctx, i: number): string | null {
  const pcs = drawn(mol, ctx).pcs[i], own = pcs.find((p) => !p.sign && p.text === mol.atoms[i].label), mate = pcs.find((p) => !p.sign && p !== own);
  if (!own || !mate) return null;
  const dx = mate.box[0] + mate.box[2] - own.box[0] - own.box[2], dy = mate.box[1] + mate.box[3] - own.box[1] - own.box[3];
  return Math.abs(dx) >= Math.abs(dy) ? (dx > 0 ? 'right' : 'left') : (dy > 0 ? 'below' : 'above');
}
// The axial seat atom i's reacting lone pair takes in placeLonePairs (35 degrees or more from each bond, within 90
// degrees of what it attacks, nearest that), or null: the written H keep off it.
function pairSeat(mol: any, job: any, i: number): number | null {
  if (!mol.atoms[i].pairs) return null;
  let end: End | null = null;
  for (const r of (job.curved ?? []) as CurvedReq[]) if (r.electrons !== 1 && r.src.kind === 'atom' && r.src.atoms[0] === i) end = r.snk;
  if (!end) return null;
  const px = atomPxOf(mol), target: Pt = end.kind === 'atom' ? px[end.atoms[0]]
    : [(px[end.atoms[0]][0] + px[end.atoms[1]][0]) / 2, (px[end.atoms[0]][1] + px[end.atoms[1]][1]) / 2];
  const want = pageDeg(px[i], target);
  const bondDirs = mol.bonds.filter((b: any) => b.type !== HBOND && b.atoms.includes(i)).map((b: any) => pageDeg(px[i], px[b.atoms[0] === i ? b.atoms[1] : b.atoms[0]]));
  const free = [0, 90, 180, 270].filter((deg) => angDiff(deg, want) <= 90 && bondDirs.every((b: number) => angDiff(deg, b) >= 35));
  return free.length ? free.reduce((a, b) => (angDiff(b, want) < angDiff(a, want) ? b : a)) : null;
}
function placeFoldedHydrogens(mol: any, ctx: Ctx, job: any) {
  for (let i = 0; i < mol.atoms.length; i++) {
    if (mol.atoms[i].hidden || (job.fixedLabelAligns ?? []).includes(i) || !mol.bonds.some((b: any) => b.atoms.includes(i))) continue;
    const stacked = ['above', 'below'].includes(mol.atoms[i].align) && !stackable(mol, i);
    // written H on the reacting pair's seat count as H on bond ink
    const seat = pairSeat(mol, job, i);
    const cost = () => labelClash(mol, ctx, i) + (seat !== null && SIDE_DEG[hydrogenSide(mol, ctx, i) ?? ''] === seat ? 200000 : 0);
    let best = stacked ? Infinity : cost(), chosen = mol.atoms[i].align;
    if (best < 1) continue;
    for (const align of stackable(mol, i) ? ['left', 'right', 'above', 'below', 'centre'] : ['left', 'right', 'centre']) {
      mol.atoms[i].align = align;
      const value = cost();
      if (value < best) { best = value; chosen = align; }
    }
    mol.atoms[i].align = chosen;
  }
}
// The same atom keeps the side of its folded hydrogens from panel to panel (water drawn H-OH leaves OH, not HO).
function keepHydrogenSides(mol: any, ctx: Ctx, job: any) {
  const sideOf = (i: number) => hydrogenSide(mol, ctx, i);
  // the atom maps an atom is bonded to; a group that moved to another atom (a transferred methyl) follows its new bond
  const partners = (i: number): string[] => mol.bonds.filter((b: any) => b.atoms.includes(i) && b.type !== HBOND)
    .map((b: any) => String(job.refs[b.atoms[0] === i ? b.atoms[1] : b.atoms[0]]).split(':').pop() as string);
  for (const group of (job.sameAtom ?? []) as number[][]) {
    let want: string | null = null, first = -1;
    for (const i of group) {
      if (mol.atoms[i].hidden || (job.fixedLabelAligns ?? []).includes(i)) continue;
      const side = sideOf(i);
      if (!side || side === want) continue;
      if (!want) { want = side; first = i; continue; }
      const was = partners(first), now = partners(i);
      if (was.length && now.length && !now.some((m) => was.includes(m))) continue;
      // only onto a side at least 60 degrees from each of its drawn bonds (the written H stand away from them)
      // and never onto the seat of its reacting lone pair
      const px = atomPxOf(mol), toward = SIDE_DEG[want] ?? 0;
      if (mol.bonds.some((b: any) => b.atoms.includes(i) && b.type !== HBOND && !b.atoms.some((j: number) => mol.atoms[j].hidden)
        && angDiff(pageDeg(px[i], px[b.atoms[0] === i ? b.atoms[1] : b.atoms[0]]), toward) < 60) || pairSeat(mol, job, i) === toward) continue;
      const saved = mol.atoms[i].align;
      const fit = (stackable(mol, i) ? ['left', 'right', 'above', 'below'] : ['left', 'right']).find((align) => { mol.atoms[i].align = align; return sideOf(i) === want && labelClash(mol, ctx, i) < 1; });
      mol.atoms[i].align = fit ?? saved;
    }
  }
}
function placeRadicals(mol: any, ctx: Ctx, job: any) {
  const px = atomPxOf(mol);
  mol.atoms.forEach((a: any, i: number) => {
    if (!a.radical || a.radical === 3) return;
    const reqs = ((job.curved ?? []) as CurvedReq[]).filter((r) => r.electrons === 1 && r.src.kind === 'atom' && r.src.atoms[0] === i);
    const angles = reqs.map((r) => {
      const target: Pt = r.snk.kind === 'atom' ? px[r.snk.atoms[0]] : [(px[r.snk.atoms[0]][0] + px[r.snk.atoms[1]][0]) / 2, (px[r.snk.atoms[0]][1] + px[r.snk.atoms[1]][1]) / 2];
      return pageDeg(px[i], target);
    });
    const fixed = job.radicalAngles?.[i];
    if (fixed === undefined && !angles.length) {
      // a dot no arrow starts from takes the widest opening between the atom's bonds and its written H
      const pcs = drawn(mol, ctx).pcs[i], own = pcs.find((p) => !p.sign && p.text === a.label);
      const center = (b: Box): Pt => [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2];
      const taken = [...mol.bonds.filter((b: any) => b.atoms.includes(i) && !b.atoms.some((j: number) => mol.atoms[j].hidden))
        .map((b: any) => pageDeg(px[i], px[b.atoms[0] === i ? b.atoms[1] : b.atoms[0]])),
        ...(own ? pcs.filter((p) => !p.sign && p !== own && !p.text.includes('•')).map((p) => pageDeg(center(own.box), center(p.box))) : [])].sort((x, y) => x - y);
      if (taken.length) {
        let open = 0, wide = -1;
        taken.forEach((t, k) => { const g = ((k + 1 < taken.length ? taken[k + 1] : taken[0] + 360) - t); if (g > wide + 1e-6) { wide = g; open = (t + g / 2) % 360; } });
        angles.push(open, (open + 120) % 360);
      }
    }
    a.angles = {...(a.angles ?? {}), radical0: fixed ?? angles[0] ?? 30,
      ...(a.radical === 2 ? {radical1: angles[1] ?? ((fixed ?? angles[0] ?? 30) + 120) % 360} : {})};
    if (a.charge) a.circled = false;
  });
}
function fitShortHashes(mol: any, ctx: Ctx) {
  // At the default pitch, a short labeled bond can collapse to one transverse mark.
  // Use one finer figure-wide pitch; explicit non-default hash spacing is preserved.
  if (Math.abs((mol.style.hash ?? 2.5) - 2.5) > .01) return;
  const d = render(mol, ctx.f, ctx.measure, L), cls = classify(mol, d, ctx);
  if (!mol.bonds.some((b: any, i: number) => b.stereo === 6 && (bondVisible(mol, d, ctx, cls, i)?.visible ?? Infinity) <= 1.05 * ctx.f.line)) return;
  mol.style.hash = .8;
  ctx.f.hash = .8 * ctx.pt;
}
function placeOxidation(mol: any, ctx: Ctx, job: any) {
  const d = render(mol, ctx.f, ctx.measure, L);
  for (const row of job.attached ?? []) {
    if (job.captionRoles?.[row.caption] !== 'oxidation') continue;
    const box = d.label[row.atom];
    if (!box) continue;
    const c = mol.captions[row.caption];
    c.x = (box[2] + .07 * L) / L;
    c.y = -(box[1] + .18 * ctx.f.size) / L;
  }
}
// seats: where the atom numbers would go without arrows; a route through a seat costs more, so an arrow leaves the
// number its place when it has another good route (the arrow still wins when it has none: numbers are placed after).
function routeArrows(mol: any, ctx: Ctx, job: any, seats: Box[] = []) {
  const {f, measure} = ctx, t0 = now(), opts = job.options ?? {};
  const d0 = render(mol, f, measure, L), cls = classify(mol, d0, ctx), px = atomPxOf(mol);
  const straight = fittedArrows(mol, ctx), caps0 = placed(mol, d0, ctx, straight);
  const pcs = piecesOf(mol, d0, ctx);
  const ratioZ = (i: number) => f.size * ctx.ratio(mol.atoms[i]);
  const ringBox = (e: any): Box => { const R = 0.34 * ratioZ(e.atom) + f.line / 2; return [e.at[0] - R, e.at[1] - R, e.at[0] + R, e.at[1] + R]; };
  const rings = d0.electrons.filter((e: any) => e.key === 'charge' && mol.atoms[e.atom].circled);
  // obstacles: every polygon, the reaction arrows and boxes; letters, rings and captions other than the atom numbers
  const textBoxes: Box[] = [...pcs.flat().map((p) => p.box), ...rings.map(ringBox), ...obstacleCaps(mol, caps0, job).map((c: any) => c.box)];
  const basePolys = [...d0.polygons, ...straight.flatMap((a: any) => arrowShapes(a, f, L)), ...(mol.shapes ?? []).flatMap((s: any) => shapeInk(s, f, L))];
  const bb = union([...px.map((p) => [p[0], p[1], p[0], p[1]] as Box), ...textBoxes]) ?? [0, 0, 1, 1], bounds = pad(bb, 2 * L);
  const atomBox = (i: number): Box | null => ownSymbol(mol, pcs, px, i);
  const besideMates = (i: number, p: Pt): number => {
    const own = atomBox(i);
    if (!own) return 0;
    const mates = pcs[i].filter((q) => !q.sign && q.box !== own);
    return mates.some((q) => boxDist(p, q.box) < boxDist(p, own) + 0.1 * L) ? 400 : 0;
  };
  // the point outside an atom's letters (or just outside a bare vertex) in direction ang, plus a gap
  const boundary = (i: number, ang: number, gap: number): Pt => {
    const p = px[i], b = atomBox(i), u: Pt = [Math.cos(ang), Math.sin(ang)];
    let r = 0.08 * L;
    if (b) for (const t of [(b[0] - p[0]) / u[0], (b[2] - p[0]) / u[0], (b[1] - p[1]) / u[1], (b[3] - p[1]) / u[1]]) if (t > 0 && Number.isFinite(t)) { const q: Pt = [p[0] + t * u[0], p[1] + t * u[1]]; if (q[0] >= b[0] - 0.01 && q[0] <= b[2] + 0.01 && q[1] >= b[1] - 0.01 && q[1] <= b[3] + 0.01) r = Math.max(r, t); }
    return [p[0] + (r + gap) * u[0], p[1] + (r + gap) * u[1]];
  };
  // an arrow must point at (or start from) the atom's symbol, not its charge
  const chargeOf = (i: number): Box[] => [...pcs[i].filter((p) => p.sign).map((p) => p.box), ...rings.filter((e: any) => e.atom === i).map(ringBox)];
  const symbolOf = (i: number): Box[] => pcs[i].filter((p) => !p.sign).map((p) => p.box);
  const chargeAmbiguity = (p: Pt, atom: number): number => {
    const cs = chargeOf(atom), ss = symbolOf(atom);
    if (!cs.length) return 0;
    const dC = Math.min(...cs.map((c) => boxDist(p, c))), dS = ss.length ? Math.min(...ss.map((c) => boxDist(p, c))) : dist(p, px[atom]);
    return (dC < 20 ? (20 - dC) * 25 : 0) + (dC < dS + 6 ? 500 : 0);
  };
  const bondIndex = (i: number, j: number) => mol.bonds.findIndex((b: any) => b.type !== HBOND && b.atoms.includes(i) && b.atoms.includes(j));
  const bondEnd = (bi: number, t: number, side: number, extra: number): Pt => {
    // t runs from the bond's stored first atom; the side of a double bond's second line (d0.sides) is relative to that order
    const b = mol.bonds[bi], p = px[b.atoms[0]], q = px[b.atoms[1]], dx = q[0] - p[0], dy = q[1] - p[1], len = Math.hypot(dx, dy);
    const n: Pt = [-dy / len, dx / len], s = d0.sides?.[bi] ?? 0;
    const lines = b.type === 2 ? (s ? [0, s * f.spacing] : [-f.spacing / 2, f.spacing / 2]) : b.type === 3 ? [0, -f.spacing, f.spacing] : [0];
    const off = (side > 0 ? Math.max(...lines) : Math.min(...lines)) + side * (f.line / 2 + extra);
    return [p[0] + dx * t + n[0] * off, p[1] + dy * t + n[1] * off];
  };
  // an end nearer to some other atom or bond than to its own target is misleading
  const site = (j: number, p: Pt) => { const b = atomBox(j); return b ? boxDist(p, b) : dist(p, px[j]); };
  const aimMargin = (p: Pt, end: End) => {
    const members = new Set(end.atoms);
    const mine = end.kind === 'atom' ? site(end.atoms[0], p) : segDist(p, px[end.atoms[0]], px[end.atoms[1]]);
    let others = 1e9;
    px.forEach((_, j) => { if (!members.has(j)) others = Math.min(others, site(j, p)); });
    mol.bonds.forEach((b: any) => { if (b.type === HBOND || b.atoms.some((x: number) => members.has(x))) return; others = Math.min(others, segDist(p, px[b.atoms[0]], px[b.atoms[1]])); });
    return {mine, others};
  };
  const aim = (p: Pt, end: End) => { const m = aimMargin(p, end); return m.others < m.mine + 6 ? 600 + (m.mine + 6 - m.others) * 30 : 0; };
  // the end must read as what was asked (readEnd, the reading the report gives), an atom end with some room to spare
  // from reading as a bond beside it (the atom's own bonds included)
  const sideHasPair = (p: Pt, end: End) => end.kind === 'atom' && d0.electrons.some((e: any) =>
    e.atom === end.atoms[0] && (e.key?.startsWith('pair') || e.key?.startsWith('radical')) && dist(p, e.at) <= PAIR_GAP + .1);
  const misread = (p: Pt, end: End) => {
    if (end.kind === 'gap' || sideHasPair(p, end)) return 0;
    const r = readEnd(mol, px, atomBox, p);
    if (end.kind === 'atom') {
      const j = end.atoms[0];
      return (r.kind !== 'atom' || r.atom !== j ? 600 : 0) + (r.center !== j ? 600 : 0) + (r.middle && r.dB < r.dA + 4 ? (r.dA + 4 - r.dB) * 30 : 0);
    }
    return r.kind !== 'bond' || r.bond !== bondIndex(end.atoms[0], end.atoms[1]) ? 600 : 0;
  };
  const native = (p: Pt): [number, number] => [p[0] / L, -p[1] / L];
  const radial = (n: number) => Array.from({length: n}, (_, k) => (2 * Math.PI * k) / n);
  const sub2 = (a: Pt, b: Pt): Pt => [a[0] - b[0], a[1] - b[1]];
  const norm = (v: Pt): Pt => { const l = Math.hypot(v[0], v[1]) || 1; return [v[0] / l, v[1] / l]; };
  const angleBetween = (a: Pt, b: Pt) => (Math.acos(Math.max(-1, Math.min(1, a[0] * b[0] + a[1] * b[1]))) * 180) / Math.PI;
  // the point an end aims at: the atom itself, or the nearest point of the bond's axis
  const targetPoint = (end: End, p: Pt): Pt => {
    if (end.kind === 'atom') return px[end.atoms[0]];
    const a = px[end.atoms[0]], b = px[end.atoms[1]], dx = b[0] - a[0], dy = b[1] - a[1], l2 = dx * dx + dy * dy;
    const t = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (l2 || 1)));
    return [a[0] + t * dx, a[1] + t * dy];
  };
  const BARE_HEAD_GAP = 0.07;                  // bond lengths beyond the 0.08 L around a bare vertex (head 0.15 L from it)
  const BENDS = [0.18, -0.18, 0.3, -0.3, 0.45, -0.45, 0.65, -0.65, 0.9, -0.9, 1.2, -1.2, 1.6, -1.6];
  const ARC_MAX = 1.9;                         // longest route / distance between the ends
  const done: {req: CurvedReq; arrow: any; polys: number[][][]; info: any}[] = [];
  const problems: string[] = [];
  const seatField = seats.length ? new Field(bounds, {boxes: seats.map((b) => pad(b, 2))}) : null;
  const requests: CurvedReq[] = [...(job.curved ?? [])];
  if (opts.reverseCurved) requests.reverse();
  for (const req of requests) {
    const retained = opts.fixedCurved?.[req.id];
    if (retained) {
      const arrow: any = {id: 900 + done.length, kind: req.electrons === 1 ? 'fishhook' : 'curved',
        from: retained.from, to: retained.to, bend: retained.bend, colour: '#000000', start: retained.start ?? 'none', end: retained.end ?? (req.electrons === 1 ? 'left' : 'full')};
      const path = arrowPath(arrow, L) as Pt[];
      const length = path.slice(1).reduce((sum, p, k) => sum + dist(p, path[k]), 0);
      done.push({req, arrow, polys: arrowShapes(arrow, f, L) as number[][][],
        info: {start: 'retained', end: 'retained', bend: arrow.bend, length_bonds: length / L, chord_bonds: dist(path[0], path[path.length - 1]) / L}});
      continue;
    }
    const repair = opts.repairArrows && (!opts.repairArrowIds || opts.repairArrowIds.includes(req.id));
    const bends = typeof req.bend === 'number' ? [req.bend] : repair ? [...BENDS, 0.1, -0.1, 0.24, -0.24, 0.38, -0.38, 0.52, -0.52,
      ...(req.src.kind === 'atom' ? [.12, .14, .16, .2, .22, .26, .28, .32, .34, .36, .4, .42, .46, .5, .55, .6, .7, .8, .95, 1].flatMap((b) => [b, -b]) : [])] : BENDS;
    const field = new Field(bounds, {polys: [...basePolys, ...done.flatMap((p) => p.polys)], boxes: textBoxes.map((b) => pad(b, 2))});
    type Cand = {p: Pt; tag: string; t: number; tm: number; ex: number; atom?: number; pen: number};
    const ends = (side: End, gapAtom: number, extras: number[]): Cand[] => {
      const out: Cand[] = [];
      if (side.kind === 'atom') {
        const pairs = side === req.src ? d0.electrons.filter((e: any) => e.atom === side.atoms[0] && e.key?.startsWith(req.electrons === 1 ? 'radical' : 'pair') &&
          done.filter((p) => p.req.src.kind === 'atom' && p.req.src.atoms[0] === e.atom && p.req.electrons === req.electrons && p.info.start.split(':')[0] === e.key).length < (e.multiplier ?? 1)) : [];
        if (pairs.length) {
          const target = targetPoint(req.snk, px[side.atoms[0]]);
          for (const pair of pairs) {
            const outward = norm(sub2(pair.at, px[side.atoms[0]]));
            const directions: Pt[] = req.electrons === 1 ? [outward, ...radial(12).map((a): Pt => [Math.cos(a), Math.sin(a)])] : [outward];
            directions.forEach((u, k) => {
              const p: Pt = [pair.at[0] + PAIR_GAP * u[0], pair.at[1] + PAIR_GAP * u[1]];
              out.push({p, tag: pair.key + (req.electrons === 1 ? ':' + k : ''), t: 0.5, tm: 0.5, ex: 0, atom: side.atoms[0], pen: aim(p, side) + misread(p, side) + angDiff(pageDeg(px[side.atoms[0]], pair.at), pageDeg(px[side.atoms[0]], target))});
            });
          }
          return out;
        }
        // a head that points at a bare vertex ends close to it: there is no letter to point at
        const bareHead = side === req.snk && !atomBox(side.atoms[0]);
        for (const gap of (bareHead ? (repair ? [BARE_HEAD_GAP * L, 0.1 * L] : [BARE_HEAD_GAP * L]) : repair ? [gapAtom, 0.1 * L, 0.25 * L] : [gapAtom])) for (const ang of radial(repair ? 48 : 24)) { const p = boundary(side.atoms[0], ang, gap); out.push({p, tag: `a${Math.round((ang * 180) / Math.PI)}${repair ? ':' + gap : ''}`, t: 0.5, tm: 0.5, ex: 0, atom: side.atoms[0], pen: aim(p, side) + misread(p, side) + besideMates(side.atoms[0], p)}); }
        return out;
      }
      if (side.kind === 'gap') {
        const a = px[side.atoms[0]], b = px[side.atoms[1]], dx = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(dx, dy) || 1;
        // an electron pair that makes a new bond: the head reaches the atom that receives it
        const receivers = side.atoms.filter((i) => !req.src.atoms.includes(i));
        if (req.electrons !== 1 && receivers.length === 1) {
          const asAtom: End = {kind: 'atom', atoms: receivers};
          const gapR = atomBox(receivers[0]) ? gapAtom : BARE_HEAD_GAP * L;
          for (const ang of radial(repair ? 48 : 24)) { const p = boundary(receivers[0], ang, gapR); out.push({p, tag: `to-atom a${Math.round((ang * 180) / Math.PI)}`, t: .5, tm: .5, ex: 0, atom: receivers[0], pen: aim(p, asAtom) + misread(p, asAtom) + besideMates(receivers[0], p)}); }
          return out;
        }
        const fractions = req.electrons === 1 ? [.5, .45, .55, .3, .7] : [.5, .4, .6, .3, .7, ...(repair ? [.26, .35, .65, .74] : [])];
        const offsets = req.electrons === 1 ? [0, .08 * L, -.08 * L] : [0, .08 * L, -.08 * L, .18 * L, -.18 * L, ...(repair ? [.195 * L, -.195 * L, .199 * L, -.199 * L] : [])];
        for (const t of fractions) for (const off of offsets) {
          const p: Pt = [a[0] + dx * t - dy / len * off, a[1] + dy * t + dx / len * off];
          out.push({p, tag: `gap:${t}:${off}`, t, tm: .5, ex: 0, pen: Math.abs(t - .5) * 60});
        }
        return out;
      }
      const bi = bondIndex(side.atoms[0], side.atoms[1]);
      if (bi < 0) { problems.push(`arrow ${req.id}: no bond between the atoms of its ${side === req.src ? 'start' : 'end'}`); return out; }
      // the middle of the visible line (a bond that stops at a letter), else the atom-to-atom middle
      const v = bondVisible(mol, d0, ctx, cls, bi), tm = v ? (v.s0 + v.s1) / 2 / v.len : 0.5;
      // A standard-length bond between two labels has a short visible middle.
      // Keep a positive ink gap while allowing its arrow to read as that bond.
      if (atomBox(side.atoms[0]) && atomBox(side.atoms[1])) extras = [...extras, 0.02 * L, 0.04 * L];
      for (const dt of (repair ? [0, -0.04, 0.04, -0.08, 0.08, -0.12, 0.12, -0.16, 0.16, -0.24, 0.24] : [0, -0.08, 0.08, -0.16, 0.16, 0.24])) for (const sd of [1, -1]) for (const ex of (repair ? [...extras, 0.08 * L, 0.1 * L] : extras)) {
        const t = +(tm + dt).toFixed(3), p = bondEnd(bi, t, sd, ex);
        out.push({p, tag: `b t=${t} side=${sd > 0 ? '+' : '-'} off=${(ex / L).toFixed(2)}L`, t, tm, ex, pen: aim(p, side) + misread(p, side)});
      }
      return out;
    };
    const matches = (p: Pt, end: End) => { if (end.kind === 'gap' || sideHasPair(p, end)) return true; const r = readEnd(mol, px, atomBox, p); return end.kind === 'atom' ? r.kind === 'atom' && r.atom === end.atoms[0] && r.center === end.atoms[0] : r.kind === 'bond' && r.bond === bondIndex(end.atoms[0], end.atoms[1]); };
    const srcPts = ends(req.src, 0.17 * L, [0.14 * L, 0.2 * L, 0.28 * L]).filter((s) => !repair || matches(s.p, req.src));
    // a head does not end beside a drawn pair (or unpaired electron) of the atom it points at: the dots belong to another arrow
    const headAtPair = (i: number, p: Pt): number => d0.electrons.some((e: any) => e.atom === i && (e.key?.startsWith('pair') || e.key?.startsWith('radical')) &&
      angDiff(pageDeg(px[i], p), pageDeg(px[i], e.at)) < 50) ? 500 : 0;
    const snkPts = ends(req.snk, 0.19 * L, [0.16 * L, 0.22 * L, 0.3 * L]).filter((s) => !repair || matches(s.p, req.snk))
      .map((s) => s.atom === undefined ? s : {...s, pen: s.pen + headAtPair(s.atom, s.p)});
    const compactHook = req.electrons === 1 && req.src.kind === 'atom' && req.snk.kind === 'gap';
    const minLen = (compactHook ? 0.3 : 0.62) * L, kind = req.electrons === 1 ? 'fishhook' : 'curved';
    // a bond's electrons moving to a neighboring bond of the same atom: a short arrow in the angle between them is natural
    const tight = req.src.kind === 'bond' && req.snk.kind === 'bond' && req.src.atoms.some((x) => req.snk.atoms.includes(x));
    const wishLen = (tight ? 0.6 : 0.85) * L, wishChord = (tight ? 0.5 : 0.8) * L;
    // The ends come from the cost without the numbers' seats (an arrow end never moves for a number); among the routes
    // with those two ends, the bend that keeps off the seats is taken.
    let bestFree: any = null;
    const withEnds = new Map<string, any>();
    for (const s of srcPts) for (const e of snkPts) {
      const chord = dist(s.p, e.p);
      if (chord < (compactHook ? 0.12 : 0.28) * L || chord > (repair ? 4.5 : 3.2) * L) continue;
      for (const bend of bends) {
        const a: any = {id: 900 + done.length, kind, from: native(s.p), to: native(e.p), bend, colour: '#000000'};
        if (kind === 'curved') { a.start = 'none'; a.end = 'full'; }
        const path = arrowPath(a, L) as Pt[];
        let len = 0; for (let k = 1; k < path.length; k++) len += dist(path[k - 1], path[k]);
        if (len < minLen) continue;
        if ((repair || req.snk.kind === 'gap') && len > 2 * chord) continue;
        const polys = arrowShapes(a, f, L) as number[][][];
        let worst = 1e9, soft = 0;
        // the deliberate gaps at both ends (within 0.17 bond length of the end points) are not penalized again
        const exempt = (p: Pt) => dist(p, s.p) < 0.17 * L || dist(p, e.p) < 0.17 * L;
        for (const poly of polys) for (let j = 0; j < poly.length; j++) {
          const p = poly[j] as Pt, q = poly[(j + 1) % poly.length] as Pt;
          const count = repair ? Math.max(1, Math.ceil(dist(p, q) / 2)) : 1;
          for (let k = 0; k < count; k++) {
            const sample: Pt = [p[0] + (q[0] - p[0]) * k / count, p[1] + (q[1] - p[1]) * k / count];
            const dd = field.at(sample); if (dd < worst) worst = dd; if (dd < 8 && !exempt(sample)) soft += (8 - dd) / count;
          }
        }
        for (const p of path) { const dd = field.at(p); if (dd < worst) worst = dd; if (dd < 8 && !exempt(p)) soft += (8 - dd) * 0.5; }
        // the end points must keep a visible gap (>= 5 px) to the nearest ink, and so must the rest
        const hard = worst < 5.5 ? (5.5 - worst) * 1e4 : 0;
        const amb = (s.atom !== undefined ? chargeAmbiguity(s.p, s.atom) : 0) + (e.atom !== undefined ? chargeAmbiguity(e.p, e.atom) : 0);
        // a number's seat costs only where the arrow's body crosses it, not near its ends (an arrow end never moves for a number)
        let seat = 0;
        if (seatField) { let m = 1e9; for (const poly of polys) for (const p of poly) if (dist(p as Pt, s.p) > 0.45 * L && dist(p as Pt, e.p) > 0.45 * L) m = Math.min(m, seatField.at(p as Pt)); if (m < 4) seat = 60 + (4 - m) * 10; }
        // the head points at its target (an atom's center, or the nearest point of a bond's axis) and the tail leaves its source
        const n = path.length, tEnd = norm([path[n - 1][0] - path[Math.max(0, n - 3)][0], path[n - 1][1] - path[Math.max(0, n - 3)][1]]), tStart = norm([path[Math.min(n - 1, 2)][0] - path[0][0], path[Math.min(n - 1, 2)][1] - path[0][1]]);
        const headDev = angleBetween(tEnd, norm(sub2(targetPoint(req.snk, e.p), e.p))), tailDev = angleBetween(tStart, norm(sub2(s.p, targetPoint(req.src, s.p))));
        const aimDir = (headDev > 25 ? (headDev - 25) * 6 : 0) + (tailDev > 75 ? (tailDev - 75) * 2 : 0);
        // a head beside a symbol whose line, carried on, misses the symbol and meets one of that atom's bonds within a bond
        // length reads as pointing at the bond (check_rules.py arrows_ends; harness_rsi D538, D539)
        let atBond = 0;
        const own = e.atom !== undefined ? pcs[e.atom].filter((q) => !q.sign && q.text === mol.atoms[e.atom].label) : [];
        const box = own.length ? own.reduce((a, b) => (boxDist(px[e.atom], a.ink) <= boxDist(px[e.atom], b.ink) ? a : b)).ink : e.atom !== undefined ? atomBox(e.atom) : null;   // the glyph ink, as check_rules.py measures it
        // the head's direction as drawn: from the middle of the head polygon's other corners to its tip (check_rules.py _head_dir)
        const head = polys.find((q) => q.length >= 3 && q.some((v) => dist(v as Pt, e.p) < 0.1));
        const rest = head ? head.filter((v) => dist(v as Pt, e.p) >= 0.1) : [];
        const uHead = rest.length ? norm([e.p[0] - rest.reduce((t, v) => t + v[0], 0) / rest.length, e.p[1] - rest.reduce((t, v) => t + v[1], 0) / rest.length]) : tEnd;
        if (box && rayBox(e.p, uHead, box) === null)
          for (const b of mol.bonds) {
            if (b.type === HBOND || !b.atoms.includes(e.atom) || b.atoms.some((x: number) => mol.atoms[x].hidden)) continue;
            const sl = raySeg(e.p, uHead, px[b.atoms[0]], px[b.atoms[1]]);
            if (sl !== null && sl <= L) { atBond = 700; break; }
          }
        // an arc, not a loop: a route much longer than the distance between its ends reads as a loop (check_rules.py
        // arrows_shape allows 2.0 times); it is taken only when nothing else is left
        const loop = len > ARC_MAX * chord ? 300 + (len / chord - ARC_MAX) * 200 : 0;
        const pivot = tight ? px[req.src.atoms.find((x) => req.snk.atoms.includes(x))!] : null, mid = path[Math.floor(n / 2)], half: Pt = [(s.p[0] + e.p[0]) / 2, (s.p[1] + e.p[1]) / 2];
        const inward = pivot && (mid[0] - half[0]) * (pivot[0] - half[0]) + (mid[1] - half[1]) * (pivot[1] - half[1]) > 0 ? 600 : 0;
        const cost = inward + hard + amb + aimDir + atBond + loop + s.pen + e.pen + soft * 20 + len * 0.04 + Math.max(0, wishLen - len) * 1.5 + Math.max(0, wishChord - chord) * 2.5 + Math.abs(bend) * 18 + (s.ex + e.ex) * 1.2 + (Math.abs(s.t - s.tm) + Math.abs(e.t - e.tm)) * 45;
        const key = s.tag + '|' + e.tag, cand = {a, polys, cost, seat, worst, len, chord, s: s.tag, e: e.tag, hard, key};
        if (!bestFree || cost < bestFree.cost) bestFree = cand;
        const prev = withEnds.get(key);
        if (!prev || cost + seat < prev.cost + prev.seat) withEnds.set(key, cand);
      }
    }
    const best = bestFree ? withEnds.get(bestFree.key) : null;
    if (!best) { problems.push(`arrow ${req.id}: no route found`); continue; }
    if (best.hard > 0) problems.push(`arrow ${req.id}: best route comes within ${r2(best.worst)} px of other ink`);
    done.push({req, arrow: best.a, polys: best.polys, info: {start: best.s, end: best.e, bend: best.a.bend, length_bonds: r2(best.len / L, 1000), chord_bonds: r2(best.chord / L, 1000), min_gap_px: r2(best.worst), cost: r2(best.cost, 10), seat_cost: r2(best.seat, 10), bend_without_seats: bestFree.a.bend}});
  }
  return {done, problems, ms: now() - t0};
}

// ---------------------------------------------------------------- boxes ---------
// TS hydrogen counts are explicit: the displayed dashed doubles do not have
// ordinary valence. Keep them in the native annotation and standard CDXML nodes.
function tsHydrogens(mol: any): Record<string, number> {
  return Object.assign({}, ...(mol.annotations ?? []).filter((a: any) => a.keyword === 'figure-ts-h')
    .map((a: any) => JSON.parse(a.content)));
}
function restoreTsHydrogens(mol: any, cdxml?: string) {
  const hs = tsHydrogens(mol), nodes = cdxml ? new DOMParser().parseFromString(cdxml, 'text/xml') : null;
  // CDXML's Dot with a covalent Order is a dotted covalent bond. Octet reads
  // every single Dot as HBOND; keep its actual order when adapting that reader.
  if (nodes) {
    const refs = new Map([...nodes.querySelectorAll('n')].map((n) => [n.getAttribute('id'), n.getAttribute('AtomNumber')]));
    for (const raw of nodes.querySelectorAll('b')) if (raw.getAttribute('Display') === 'Dot' && (raw.getAttribute('Order') ?? '1') === '1') {
      const ends = [raw.getAttribute('B'), raw.getAttribute('E')].map((id) => mol.atoms.findIndex((a: any) => a.hiddenNumber === refs.get(id)));
      const b = mol.bonds.find((b: any) => ends.every((i) => i >= 0 && b.atoms.includes(i)));
      if (b) { b.type = 1; b.display = 'dashed'; }
    }
  }
  for (const a of mol.atoms) if (Object.hasOwn(hs, a.hiddenNumber)) {
    const node = nodes ? [...nodes.querySelectorAll('n')].find((n) => n.getAttribute('AtomNumber') === a.hiddenNumber) : null;
    // A missing standard H count must stay missing and fail the H checker.
    a.implicitHCount = nodes ? (node?.hasAttribute('NumHydrogens') ? +node.getAttribute('NumHydrogens')! : -1) : hs[a.hiddenNumber];
  }
  if (nodes) for (const a of mol.atoms) {
    const n = [...nodes.querySelectorAll('n')].find((node) => node.getAttribute('AtomNumber') === a.hiddenNumber);
    if (!n) continue;
    // Octet's label parser can reinterpret a superscript 2H as a generic carbon
    // label. The standard CDXML Element/Isotope attributes are authoritative.
    if (n.hasAttribute('Isotope') && n.getAttribute('NodeType') !== 'Unspecified') {
      if (n.getAttribute('Element') === '1') { a.label = 'H'; delete a.text; delete a.runs; }
      a.isotope = +n.getAttribute('Isotope')!;
    }
    if (n.hasAttribute('Radical') && ['Triplet', 'Doublet'].includes(n.getAttribute('Radical')!)) {
      delete a.text; delete a.runs;
      if (n.hasAttribute('Element')) a.label = Array.from(ELEMENTS)[+n.getAttribute('Element')! - 1];
      if (n.hasAttribute('NumHydrogens')) a.implicitHCount = +n.getAttribute('NumHydrogens')!;
    }
  }
}
function tsCdxml(mol: any): string | undefined {
  const hs = tsHydrogens(mol);
  const dotted = new Set(mol.bonds.filter((b: any) => b.display === 'dashed' && [1, 2].includes(b.type) && !(mol.annotations ?? []).some((a: any) => a.keyword === 'figure-drawing' && JSON.parse(a.content).partial_bonds === 'dashed'))
    .map((b: any) => b.atoms.map((i: number) => mol.atoms[i].hiddenNumber).sort().join('|')));
  const display = radicalIonDisplay(mol);
  if (!Object.keys(hs).length && !dotted.size && display === mol) return undefined;
  const xml = toCdxml(display, mol.style), nodes = new DOMParser().parseFromString(xml, 'text/xml');
  const refs = new Map([...nodes.querySelectorAll('n')].map((n) => [n.getAttribute('id'), n.getAttribute('AtomNumber')]));
  return xml.replace(/<b\b[^>]*>/g, (tag: string) => {
    const ends = ['B', 'E'].map((key) => refs.get(new RegExp(`\\b${key}="([^"]+)"`).exec(tag)?.[1] ?? null));
    return dotted.has(ends.sort().join('|')) ? tag.replace(/\bDisplay(2)?="Dash"/g, 'Display$1="Dot"') : tag;
  }).replace(/<n\b[^>]*>/g, (tag: string) => {
    const key = /\bAtomNumber="([^"]+)"/.exec(tag)?.[1];
    const atom = mol.atoms.find((a: any) => a.hiddenNumber === key);
    if (atom && (atom.radical === 1 || atom.radical === 2)) {
      const symbols = Array.from(ELEMENTS);
      const element = symbols.indexOf(atom.label) + 1;
      const h = chemicalAnnotations(mol)[key!]?.h ?? 0;
      tag = tag.replace(/\s(Charge|Radical|NodeType|Element|NumHydrogens|Isotope)="[^"]*"/g, '').replace(/(\/?>)$/, ` Element="${element || 6}" NumHydrogens="${h}"${atom.isotope ? ` Isotope="${atom.isotope}"` : ''}${atom.charge ? ` Charge="${atom.charge}"` : ''} Radical="${atom.radical === 1 ? 'Doublet' : 'Triplet'}"$1`);
    }
    if (key === undefined || !Object.hasOwn(hs, key)) return tag;
    return tag.replace(/\sNumHydrogens="[^"]*"/, '')
      .replace(/(\/?>)$/, ` NumHydrogens="${hs[key]}"$1`);
  });
}

function placeTsMarks(mol: any, ctx: Ctx, frames: any[]) {
  for (const rq of frames ?? []) {
    const sh = mol.shapes[rq.shape], cap = mol.captions[rq.caption];
    const right = Math.max(sh.from[0], sh.to[0]), top = Math.min(-sh.from[1], -sh.to[1]);
    cap.x = +(right + .25).toFixed(4);
    cap.y = +(-(top - .2 + .716 * (cap.size ?? mol.style.captionSize) * ctx.pt / L / 2)).toFixed(4);
  }
}

// A box keeps the letters, charges and marks of the atoms inside it (measured on Octet's glyphs) 2 pt inside its
// edges: it only grows.  The resolved figure cannot know a label's width.
function fitBoxes(mol: any, ctx: Ctx, tsFrames: any[] = []) {
  const {f, measure, pt, ratio} = ctx, t0 = now(), rows: any[] = [];
  const kinds = new Set(['box', 'rounded', 'oval', 'brackets']);
  if (!(mol.shapes ?? []).some((s: any) => kinds.has(s.kind))) return {rows, ms: 0};
  const d = render(mol, f, measure, L), px = atomPxOf(mol), pcs = piecesOf(mol, d, ctx), m = 2 * pt;
  // (a charge written as text is a label piece; only a circled one is a mark)
  const marks = d.electrons.filter((e: any) => e.key && (e.key !== 'charge' || mol.atoms[e.atom].circled)).map((e: any) => {
    const z = f.size * ratio(mol.atoms[e.atom]), r = e.key === 'charge' ? 0.34 * z + f.line / 2 : e.key.startsWith('pair') ? 0.28 * z + f.line / 2 : 0.1 * z;
    return {atom: e.atom as number, box: [e.at[0] - r, e.at[1] - r, e.at[0] + r, e.at[1] + r] as Box};
  });
  mol.shapes.forEach((s: any, k: number) => {
    if (!kinds.has(s.kind)) return;
    const b: Box = [Math.min(s.from[0], s.to[0]) * L, Math.min(-s.from[1], -s.to[1]) * L, Math.max(s.from[0], s.to[0]) * L, Math.max(-s.from[1], -s.to[1]) * L];
    const ts = tsFrames.find((rq) => rq.shape === k);
    const inside = ts ? ts.atoms : px.map((_, i) => i).filter((i) => px[i][0] > b[0] && px[i][0] < b[2] && px[i][1] > b[1] && px[i][1] < b[3]);
    const ink = union([...inside.flatMap((i: number) => pcs[i].map((p) => p.box)), ...marks.filter((q: any) => inside.includes(q.atom)).map((q: any) => q.box),
      ...(ts ? inside.map((i: number) => [px[i][0], px[i][1], px[i][0], px[i][1]] as Box) : [])]);
    if (!ink) return;
    const margin = ts ? Math.max(m, .4 * L) : m;
    const nb: Box = [Math.min(b[0], ink[0] - margin), Math.min(b[1], ink[1] - margin), Math.max(b[2], ink[2] + margin), Math.max(b[3], ink[3] + margin)];
    const grown = [b[0] - nb[0], b[1] - nb[1], nb[2] - b[2], nb[3] - b[3]];
    if (grown.every((g) => g < 0.01)) return;
    s.from = [+(nb[0] / L).toFixed(4), +(-nb[1] / L).toFixed(4)]; s.to = [+(nb[2] / L).toFixed(4), +(-nb[3] / L).toFixed(4)];
    rows.push({shape: k, atoms_inside: inside.length, grown_pt: grown.map((g) => r2(g / pt, 1000))});
  });
  return {rows, ms: now() - t0};
}

// ---------------------------------------------------------------- 4. atom numbers ---------
// Each number goes to the free spot nearest its atom: candidates on a ring of directions and distances around the atom,
// scored by room (bonds, rings, letters, arrows, captions, numbers placed before), by the free sectors around the atom
// (between its bonds, label and marks), and by the rules: on the side of the atom's own symbol (for CH3 next to the C,
// never after the H3), clearly nearer its own atom than anything else, never between two labels.
// dry: only find the places (the seats the curved arrows are asked to leave free), do not move the captions.
function placeNumbers(mol: any, ctx: Ctx, job: any, curvedPolys: number[][][], dry = false) {
  const {f, measure, pt, style, capWidth} = ctx, t0 = now(), opts = job.options ?? {};
  const reqs: NumberReq[] = job.numbers ?? [];
  if (!reqs.length) return {rows: [], problems: [], seats: [] as Box[], ms: 0};
  const d0 = render(mol, f, measure, L), px = atomPxOf(mol), pcs = piecesOf(mol, d0, ctx);
  const straight = fittedArrows(mol, ctx), caps0 = placed(mol, d0, ctx, straight);
  const otherCaps = obstacleCaps(mol, caps0, job);
  const rings = d0.electrons.filter((e: any) => e.key === 'charge' && mol.atoms[e.atom].circled).map((e: any) => ({atom: e.atom as number, c: e.at as Pt, R: 0.34 * f.size * ctx.ratio(mol.atoms[e.atom]) + f.line / 2}));
  const marks = d0.electrons.filter((e: any) => e.key && e.key !== 'charge').map((e: any) => ({atom: e.atom as number, c: e.at as Pt}));
  const polys = [...d0.polygons, ...straight.flatMap((a: any) => arrowShapes(a, f, L)), ...curvedPolys, ...(mol.shapes ?? []).flatMap((s: any) => shapeInk(s, f, L))];
  const bb = union([...px.map((p) => [p[0], p[1], p[0], p[1]] as Box), ...pcs.flat().map((p) => p.box), ...otherCaps.map((c: any) => c.box)]) ?? [0, 0, 1, 1];
  const field = new Field(pad(bb, 2 * L), {polys});
  // an SVG text's line box reaches 0.189 em above a capital's top and 0.212 em below the baseline
  const lineBoxes: Box[] = [...d0.labels.map((l: any) => { const m = measure(l.text), s = l.size / f.size; return [l.x, l.y - m.ascent * s - 0.189 * l.size, l.x + m.width * s, l.y + 0.212 * l.size] as Box; }), ...otherCaps.map((c: any) => c.box)];
  // px (4.03 px = 1 pt), between the number's glyph ink and the rest: own gap at least 6 and about 8; the nearest other
  // atom, number or circle at least 6.5 (1.6 pt) farther than the own atom; other atoms' letters at least 12.5 (3.1 pt)
  // away, 27 wished
  const OWN_MIN = 6, OWN_WISH = 8, OWN_MARGIN = opts.ownMarginPx ?? 6.5, LETTER_MIN = 12.5, LETTER_CLEAR = 27;
  const rows: any[] = [], problems: string[] = [];
  const symOf = (i: number) => {
    const ps = pcs[i].filter((p) => !p.sign).sort((x, y) => boxDist(px[i], x.box) - boxDist(px[i], y.box));
    if (!ps.length) return null;
    const sym = ps[0].box, symInk = ps[0].ink, tails = ps.slice(1).map((p) => p.box);
    const dir = tails.length ? Math.sign(tails.reduce((s, t) => s + (t[0] + t[2]) / 2, 0) / tails.length - (sym[0] + sym[2]) / 2) : 0;
    return {sym, symInk, tails, dir};
  };
  // what each number needs: its atom, size, the free sectors around its atom (between its bonds, the rest of its label, its marks)
  const preps: any[] = [];
  for (const rq of reqs) {
    const i = rq.atom, cap = mol.captions[rq.caption], a = mol.atoms[i];
    if (!cap) continue;
    if (a.label === 'H' && !a.text && pcs[i].length) { problems.push(`number ${cap.text} on an H drawn as a letter: not placed (numbers never go on an H)`); rows.push({caption: rq.caption, atom: i, text: cap.text, refused: 'H'}); continue; }
    const sizePx = (cap.size ?? style.captionSize) * pt, w = capWidth(cap.text, cap), asc = 0.716 * sizePx, si = symOf(i);
    // the glyphs' ink from the caption's anchor (the middle of its advance, on the baseline), from Octet's measurer
    const mm = measure(cap.text, cap.font ? {font: cap.font} : undefined), sc = sizePx / f.size;
    let il = Infinity, it = Infinity, ir = -Infinity, ib = -Infinity;
    for (const q of mm.outline) { il = Math.min(il, q[0]); ir = Math.max(ir, q[0]); it = Math.min(it, q[1]); ib = Math.max(ib, q[1]); }
    const ink: Box = Number.isFinite(il) ? [il * sc - (mm.width * sc) / 2, it * sc, ir * sc - (mm.width * sc) / 2, ib * sc] : [-w / 2, -asc, w / 2, 0];
    const taken: number[] = mol.bonds.filter((b: any) => b.atoms.includes(i)).map((b: any) => pageDeg(px[i], px[b.atoms[0] === i ? b.atoms[1] : b.atoms[0]]));
    if (si) for (const t of si.tails) taken.push(pageDeg(px[i], [(t[0] + t[2]) / 2, (t[1] + t[3]) / 2]));
    for (const r of rings) if (r.atom === i) taken.push(pageDeg(px[i], r.c));
    for (const m of marks) if (m.atom === i) taken.push(pageDeg(px[i], m.c));
    const sorted = [...taken].sort((x, y) => x - y), gaps: {mid: number; size: number}[] = [];
    sorted.forEach((t, k) => { const next = k + 1 < sorted.length ? sorted[k + 1] : sorted[0] + 360, size = next - t || 360; gaps.push({mid: (t + size / 2) % 360, size}); });
    preps.push({rq, i, cap, sizePx, w, asc, ink, si, gaps, maxGap: Math.max(0, ...gaps.map((g) => g.size)), r0: si ? 0.62 : 0.6, ownSet: new Set(pcs[i].map((p) => p.k))});
  }
  // the best place for one number, the other numbers' boxes given
  const search = (P: any, others: Box[]) => {
    const {i, w, asc, ink, si, gaps, maxGap, r0, ownSet, sizePx} = P;
    const put = others.map((b) => pad(b, 0.5)), lbs = [...lineBoxes, ...others.map((b) => [b[0], b[1] - 0.189 * sizePx, b[2], b[3] + 0.212 * sizePx] as Box)];
    let best: any = null;
    const fixed = opts.fixedNumbers?.[job.refs?.[i]];
    if (fixed) {
      const cx = fixed.x * L, base = fixed.y * L, cy = base - asc / 2;
      const box: Box = [cx + ink[0], base + ink[1], cx + ink[2], base + ink[3]];
      return {cost: 0, deg: pageDeg(px[i], [cx, cy]), r: dist(px[i], [cx, cy]) / L, cx, cy, box, clear: 100, own: 0, nearestOther: 100, nearestLetter: 100, terms: {fixed: true}};
    }
    for (let deg = 0; deg < 360; deg += opts.repairNumbers ? 2.5 : 5) for (let r = r0 - (opts.repairNumbers ? 0.4 : 0.25); r <= r0 + (opts.repairNumbers ? 0.9 : 0.6) + 1e-9; r += opts.repairNumbers ? 0.0125 : 0.025) {
      const th = (deg * Math.PI) / 180, cx = px[i][0] + r * L * Math.cos(th), cy = px[i][1] - r * L * Math.sin(th), base = cy + asc / 2;
      const adv: Box = [cx - w / 2, cy - asc / 2, cx + w / 2, base], box: Box = [cx + ink[0], base + ink[1], cx + ink[2], base + ink[3]];
      let clear = field.overBox(box);
      pcs.forEach((list) => { for (const p of list) if (!ownSet.has(p.k)) clear = Math.min(clear, boxGap(box, pad(p.box, 0.5))); });
      for (const c of otherCaps) clear = Math.min(clear, boxGap(box, pad(c.box, 0.5)));
      for (const b of put) clear = Math.min(clear, boxGap(box, b));
      const ang = gaps.length ? Math.min(...gaps.map((g: any) => (angDiff(deg, g.mid) / 30) ** 2 + 3 * (1 - g.size / maxGap))) : 0;
      const rad = ((r - r0) / 0.15) ** 2 * 0.5;
      // room around the glyphs' ink: 12 px (3 pt) wished, 6.5 px (1.6 pt) at least
      const clr = (clear >= 12 ? 0 : ((12 - clear) / 4) ** 2) + (clear < 6.5 ? 100 + (6.5 - clear) * 50 : 0);
      const lb: Box = [adv[0], adv[1] - 0.189 * sizePx, adv[2], adv[3] + 0.212 * sizePx];
      const gapB = (b: Box) => boxGap(box, b);
      // gaps to letters are taken between glyph inks (the number's and the letter's), as a reader sees them
      const gapTo = (j: number) => (pcs[j].length ? Math.min(...pcs[j].map((p) => gapB(p.ink))) : boxDist(px[j], box));
      // the number must read as its own atom's: the gap to its symbol (or the point of a bare carbon) clearly the smallest
      const own = si ? gapB(si.symInk) : boxDist(px[i], box);
      let nearestOther = 1e9, nearestLetter = 1e9;
      for (let j = 0; j < px.length; j++) if (j !== i) { nearestOther = Math.min(nearestOther, gapTo(j)); for (const p of pcs[j]) nearestLetter = Math.min(nearestLetter, gapB(p.ink)); }
      for (const b of put) nearestOther = Math.min(nearestOther, gapB(b));
      for (const q of rings) if (q.atom !== i) nearestOther = Math.min(nearestOther, Math.max(0, boxDist(q.c, box) - q.R));
      const assoc = own + OWN_MARGIN > nearestOther ? 150 + (own + OWN_MARGIN - nearestOther) * 5 : 0;
      // never between two labels: the letters of every other atom stay LETTER_MIN away (a rule), LETTER_CLEAR if there is room
      const between = (nearestLetter < LETTER_MIN ? 150 + (LETTER_MIN - nearestLetter) * 5 : 0) + (nearestLetter < LETTER_CLEAR ? ((LETTER_CLEAR - nearestLetter) / 4) ** 2 * 0.6 : 0);
      // on the side of the symbol: not past it toward the rest of the label (after the H3 of CH3)
      const side = si && si.tails.length && ((si.dir > 0 && cx > si.sym[2]) || (si.dir < 0 && cx < si.sym[0])) ? 300 : 0;
      const lineHit = lbs.some((o) => lb[0] < o[2] + 0.5 && lb[2] > o[0] - 0.5 && lb[1] < o[3] + 0.5 && lb[3] > o[1] - 0.5) ? 200 : 0;
      const ownTerm = si ? (own < OWN_MIN ? 100 + (OWN_MIN - own) * 50 : ((own - OWN_WISH) / 4) ** 2 * 0.6) : 0;
      const cost = ang + rad + clr + lineHit + assoc + between + side + ownTerm;
      const terms = {angle: r2(ang), radius: r2(rad), clearance: r2(clr), line_box: lineHit, ownership: r2(assoc), between_labels: r2(between), symbol_side: side, own_gap: r2(ownTerm)};
      if (!best || cost < best.cost) best = {cost, deg, r, cx, cy, box, clear, own, nearestOther, nearestLetter, terms};
    }
    return best;
  };
  // first in order, each with the numbers placed before it; then again, each with all the others, until nothing moves
  const state: any[] = [];
  preps.forEach((P, k) => { state[k] = search(P, state.slice(0, k).map((s) => s.box)); });
  let passes = 1;
  for (; passes < 4; passes++) {
    let moved = false;
    preps.forEach((P, k) => {
      const s = search(P, state.filter((_, j) => j !== k).map((x) => x.box));
      if (s.deg !== state[k].deg || Math.abs(s.r - state[k].r) > 1e-6) moved = true;
      state[k] = s;
    });
    if (!moved) break;
  }
  // a number that breaks a rule because of another number nearby: place the two the other way round, keep the better
  for (let k = 0; k < preps.length; k++) {
    if (state[k].cost < 100) continue;
    let j = -1, dj = 1e9;
    state.forEach((s, m) => { if (m !== k) { const g = boxGap(s.box, state[k].box); if (g < dj) { dj = g; j = m; } } });
    if (j < 0 || dj > 1.2 * L) continue;
    const rest = state.filter((_, m) => m !== k && m !== j).map((x) => x.box);
    const sk = search(preps[k], rest), sj = search(preps[j], [...rest, sk.box]), sk2 = search(preps[k], [...rest, sj.box]);
    if (sk2.cost + sj.cost < state[k].cost + state[j].cost - 1) { state[k] = sk2; state[j] = sj; }
  }
  // seats for the arrow router: only places that keep every rule (a number without one must not bend arrows into loops)
  if (dry) return {rows: [], problems: [], seats: state.filter((s) => s.cost < 100).map((s) => s.box as Box), ms: now() - t0};
  preps.forEach((P, k) => {
    const best = state[k], cap = P.cap;
    cap.x = +(best.cx / L).toFixed(4); cap.y = +(-(best.cy + P.asc / 2) / L).toFixed(4); cap.align = 'centre';
    if (best.cost >= 100) problems.push(`number ${cap.text}: the best place breaks a rule (cost ${r2(best.cost)})`);
    rows.push({caption: P.rq.caption, atom: P.i, text: cap.text, deg: best.deg, r_bonds: r2(best.r, 1000), clearance_px: r2(best.clear), own_gap_px: r2(best.own), nearest_other_gap_px: r2(best.nearestOther), nearest_other_letter_px: r2(best.nearestLetter), cost: r2(best.cost), terms: best.terms});
  });
  return {rows, problems, passes, seats: state.map((s) => s.box as Box), ms: now() - t0};
}

// ---------------------------------------------------------------- 5. titles ---------
function placeTitles(mol: any, ctx: Ctx, job: any, curvedPolys: number[][][]) {
  const reqs: TitleReq[] = (job.titles ?? []).filter((t: TitleReq) => t.autoX || t.autoY || t.generated);
  if (!reqs.length) return [];
  const {f, measure, pt} = ctx, d = render(mol, f, measure, L), arrows = fittedArrows(mol, ctx), caps = placed(mol, d, ctx, arrows);
  const titleIds = new Set(reqs.map((t) => mol.captions[t.caption]?.id));
  const byId = new Map(caps.map((c: any) => [c.id, c]));
  const curvedBoxes = curvedPolys.map((poly) => union(poly.map(([x, y]) => [x, y, x, y] as Box))!);
  const rows = reqs.map((t) => {
    const ink = union(t.atoms.flatMap((i) => [d.ink[i], d.label[i]].filter(Boolean) as Box[])) ?? [0, 0, 0, 0];
    // captions and curved arrows that sit within the panel's columns count too (numbers, residue labels, conditions)
    const extra = [...caps.filter((c: any) => !titleIds.has(c.id) && c.box[2] > ink[0] && c.box[0] < ink[2] && c.box[1] < ink[3] + 2 * L && c.box[3] > ink[1]).map((c: any) => c.box as Box),
      ...curvedBoxes.filter((b) => b[2] > ink[0] && b[0] < ink[2] && b[3] > ink[1] && b[1] < ink[3] + L)];
    const all = union([ink, ...extra])!;
    return {t, ink, bottom: all[3], top: ink[1], cx: (ink[0] + ink[2]) / 2};
  });
  // a row: panels whose atoms overlap vertically; their titles share one baseline
  for (const r of rows) {
    const row = rows.filter((o) => o.ink[1] < r.ink[3] && o.ink[3] > r.ink[1]);
    const base = Math.max(...row.map((o) => o.bottom)) + GAP_PT * pt;
    const cap = mol.captions[r.t.caption];
    if (!cap) continue;
    const capBox = byId.get(cap.id)?.box;
    const blockedGenerated = r.t.generated && capBox && r.t.atoms.some((i) => d.label[i] && boxGap(capBox, d.label[i]) < ctx.pt);
    if (r.t.autoY || blockedGenerated) cap.y = +(-base / L).toFixed(4);
    if (r.t.autoX) cap.x = +(r.cx / L).toFixed(4);
    cap.align = 'centre';
    delete cap.under;
  }
  return rows.map((r) => ({caption: r.t.caption, x: mol.captions[r.t.caption]?.x, y: mol.captions[r.t.caption]?.y}));
}

// ---------------------------------------------------------------- drawing and export ---------
// Draw a document on the page's <svg> the way Octet's editor does: boxes, the structure's ink (one path per kind and
// color: bonds, hydrogen bonds, marks), atom label pieces, arrows (fitted to their conditions, as the editor shows
// them) and captions placed by Octet's placeCaptions. Roles are written as element ids (standaloneSvg removes data-*
// attributes) and turned into data-role afterwards.
function paint(mol: any, ctx: Ctx) {
  const {style, f, pt, measure, capWidth} = ctx;
  const d = render(mol, f, measure, L), cls = classify(mol, d, ctx), arrows = fittedArrows(mol, ctx);
  const canvas = document.querySelector('svg')! as SVGSVGElement;
  canvas.replaceChildren();
  for (const a of ['width', 'height', 'viewBox']) canvas.removeAttribute(a);
  const g = node('g', {}, canvas);
  const ids = new Map<string, number>(), id = (role: string) => { const k = ids.get(role) ?? 0; ids.set(role, k + 1); return `role-${role}-${k}`; };
  (mol.shapes ?? []).forEach((s: any) => node('path', {d: toPath(shapeInk(s, f, L)), fill: s.colour ?? '#000000', id: id('box')}, g));
  const groups = new Map<string, number[][][]>();
  d.polygons.forEach((poly: number[][], i: number) => {
    const key = `${cls[i]}|${(d.colours[i] ?? '#000000').toLowerCase()}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(poly);
  });
  if (![...groups.keys()].some((k) => k.startsWith('bond|'))) groups.set('bond|#000000', []);
  for (const [key, polys] of groups) { const [role, color] = key.split('|'); node('path', {d: toPath(polys), fill: color, id: id(role)}, g); }
  d.labels.forEach((l: any) => node('text', {x: l.x, y: l.y, transform: labelTurn(l), 'font-family': fontStack(l.font ?? style.labelFont), 'font-size': l.size, 'font-weight': l.bold ? 'bold' : undefined, 'font-style': l.italic ? 'italic' : undefined, fill: l.colour ?? '#000000'}, g, l.text));
  const delocalized = new Set((mol.annotations ?? []).filter((a: any) => a.keyword === 'figure-arrow-groups').flatMap((a: any) => JSON.parse(a.content)).filter((a: any) => a.kind === 'delocalization').flatMap((a: any) => a.indices));
  arrows.forEach((a: any, i: number) => node('path', {d: toPath(arrowShapes(a, f, L)), fill: a.colour ?? '#000000', id: delocalized.has(i) ? id('bond') : `role-arrow-${i}`}, g));
  const caps = placed(mol, d, ctx, arrows);
  const capOf = new Map((mol.captions ?? []).map((c: any) => [c.id, c]));
  for (const c of caps) {
    const src: any = capOf.get(c.id) ?? {};
    const t = node('text', {'text-anchor': c.anchor, 'font-family': fontStack(c.font ?? style.captionFont), 'font-size': c.size, 'font-weight': c.bold ? 'bold' : undefined, 'font-style': c.italic ? 'italic' : undefined, fill: c.colour ?? '#000000', id: `role-caption-${c.id}`}, g) as SVGTextElement;
    for (const l of c.lines) {
      const ts = node('tspan', {x: l.x, y: l.y}, t);
      // conditions on an arrow without runs of their own are drawn as a formula (their counts as subscripts), as the editor does
      const runs = l.runs ?? (formulaCaption(src) && formulaRuns(l.text).some((r: any) => r.sub) ? formulaRuns(l.text).map((r: any) => (r.sub ? {text: r.text, script: 'sub'} : {text: r.text})) : undefined);
      if (runs) { let shift = 0; for (const r of runs) { const to = r.script === 'sub' ? 0.212 * c.size : r.script === 'super' ? -0.33 * c.size : 0, dy = to - shift; shift = to; const sz = r.size ? r.size * pt : c.size; node('tspan', {dy: dy || undefined, 'font-size': r.script ? sz * 0.75 : sz}, ts, r.text); } }
      else ts.textContent = l.text;
    }
  }
  const bb = g.getBBox(), bounds: Box = [bb.x - 14, bb.y - 14, bb.x + bb.width + 14, bb.y + bb.height + 14];
  // attribute order width, height, viewBox: export.ts's withMargin matches the standalone SVG header in that order
  canvas.setAttribute('width', String(bounds[2] - bounds[0])); canvas.setAttribute('height', String(bounds[3] - bounds[1]));
  canvas.setAttribute('viewBox', `${bounds[0]} ${bounds[1]} ${bounds[2] - bounds[0]} ${bounds[3] - bounds[1]}`);
  return {d, cls, canvas, g, bounds, arrows, caps};
}

// Octet's standalone SVG with a 6 pt margin; paths and texts get data-role (bond, mark, arrow, caption) for the checks.
function exportSvg(canvas: SVGSVGElement, bounds: Box, pt: number, names: string[]) {
  const svg0 = standaloneSvg(canvas, bounds, 1 / pt), svg = withMargin(svg0, 6);
  if (svg === svg0) throw new Error('withMargin did not apply (SVG header order differs from export.ts expectation)');
  const clean = (s: string) => s.replace(/[^\w.:-]/g, '_');
  return svg.replace(/ id="role-(\w+)-(\d+)"/g, (_m: string, role: string, k: string) => {
    if (role === 'arrow') return ` data-role="arrow" data-id="${clean(names[+k] ?? `arrow${k}`)}"`;
    if (role === 'caption') return ' data-role="caption"';
    if (role === 'hbond') return ' data-role="bond" data-kind="hbond"';
    if (role === 'box') return ' data-role="bond" data-kind="box"';
    return ` data-role="${role}"`;
  });
}

// What a saved drawing holds, read back: atoms (with the ref each one had, from hiddenNumber), bonds, hydrogen bonds,
// arrows, captions, boxes and numbers, in the resolved frame (bond lengths, y down).
function viewOf(m: any, refs: string[], numberReqs: NumberReq[], placedIds: string[], captionRoles: string[] = []) {
  const numberCaps = new Set(numberReqs.map((n) => n.caption)), roleOf = (k: number) => captionRoles[k] ?? 'text';
  const mp = atomPxOf(m), used = (i: number) => m.bonds.filter((b: any) => b.atoms.includes(i)).reduce((n: number, b: any) => n + orderOf(b.type), 0);
  const ref = (i: number) => refs[+(m.atoms[i].hiddenNumber ?? -1)] ?? `#${i}`;
  const chemistry = chemicalAnnotations(m);
  return {
    atoms: m.atoms.map((a: any, i: number) => ({ref: ref(i), hidden: a.hiddenNumber ?? null, el: a.label, text: a.text ?? null, shown: !!a.shown, chemical: a.chemical !== false, charge: a.charge ?? 0, circled: !!a.circled,
      h: a.implicitHCount ?? (a.text ? null : hydrogens(a.label, a.charge || 0, used(i), a.radical || 0)), pairs: a.pairs ?? 0, color: a.colour ? a.colour.toLowerCase() : null, align: a.align ?? null,
      isotope: a.isotope ?? 0, radical: a.radical ?? 0, hidden_h: !!a.hidden, center: a.centre?.atoms.map(ref) ?? null, oxidation: chemistry[a.hiddenNumber]?.oxidation ?? null,
      charge_angle: a.angles?.charge ?? null, x: r2(a.location[0], 1e4), y: r2(-a.location[1], 1e4)})),
    bonds: m.bonds.filter((b: any) => b.type !== HBOND).map((b: any) => ({a: ref(b.atoms[0]), b: ref(b.atoms[1]), order: b.type === 4 ? 1.5 : b.type, style: b.stereo === 1 ? 'wedge' : b.stereo === 6 ? 'hash' : b.display === 'bold' ? 'bold' : b.display ?? 'plain', color: b.colour ? b.colour.toLowerCase() : null})),
    hbonds: m.bonds.filter((b: any) => b.type === HBOND).map((b: any) => [ref(b.atoms[0]), ref(b.atoms[1])]),
    curved: (m.arrows ?? []).filter((a: any) => a.kind === 'curved' || a.kind === 'fishhook').map((a: any, k: number) => ({id: placedIds[k] ?? null, kind: a.kind, from: [r2(a.from[0], 1e4), r2(-a.from[1], 1e4)], to: [r2(a.to[0], 1e4), r2(-a.to[1], 1e4)], bend: a.bend ?? 0, color: (a.colour ?? '#000000').toLowerCase(), start: a.start ?? null, end: a.end ?? null})),
    straight: logicalStraight(m, (m.arrows ?? []).filter((a: any) => !(a.kind === 'curved' || a.kind === 'fishhook')).map((a: any) => ({kind: a.kind, x1: r2(a.from[0], 1e4), y1: r2(-a.from[1], 1e4), x2: r2(a.to[0], 1e4), y2: r2(-a.to[1], 1e4), color: (a.colour ?? '#000000').toLowerCase(), head: a.end ?? (['cut', 'line', 'curve'].includes(a.kind) ? 'none' : 'full'), tail: a.start ?? (a.kind === 'resonance' ? 'full' : 'none')}))),      captions: (m.captions ?? []).map((c: any, k: number) => ({text: c.text, role: numberCaps.has(k) ? 'number' : roleOf(k), x: r2(c.x, 1e4), y: r2(-c.y, 1e4), size: c.size ?? null, align: c.align ?? null, color: c.colour ? c.colour.toLowerCase() : null, on: c.on ? {arrow: (m.arrows ?? []).findIndex((a: any) => a.id === c.on.arrow), side: c.on.side} : null})),
    boxes: (m.shapes ?? []).map((s: any) => ({kind: s.kind, x1: r2(s.from[0], 1e4), y1: r2(-s.from[1], 1e4), x2: r2(s.to[0], 1e4), y2: r2(-s.to[1], 1e4)})),
    numbers: numberReqs.map((n: NumberReq) => { const c = m.captions?.[n.caption]; return {ref: refs[n.atom] ?? null, text: c?.text ?? null, x: c ? r2(c.x, 1e4) : null, y: c ? r2(-c.y, 1e4) : null, size: c?.size ?? null}; }),
    annotations: m.annotations ?? [],
    delocalized: (m.annotations ?? []).filter((a: any) => a.keyword === 'figure-arrow-groups').flatMap((a: any) => JSON.parse(a.content)).filter((g: any) => g.kind === 'delocalization').map((g: any) => {
      const a = m.arrows?.[g.indices[0]]; return {center: g.center, kind: a?.kind, points: a?.curve?.points.length ?? 0, head: a?.end ?? 'none', tail: a?.start ?? 'none'};
    }),
    style: m.style ? {preset: m.style.preset, bond: m.style.bond, line: m.style.line, labelFont: m.style.labelFont, labelSize: m.style.labelSize, captionFont: m.style.captionFont, captionSize: m.style.captionSize} : null,
  };
}

// A fresh page: a .cdxml file (CDXML alone, no Octet JSON) read with Octet's own CDXML reader, as ChemDraw users get it.
(window as any).readCdxml = async (text: string, refs: string[] = [], numberReqs: NumberReq[] = [], ids: string[] = [], roles: string[] = []) => {
  const r = readOct(text);
  restoreTsHydrogens(r.mol, text);
  return {...viewOf(r.mol, refs, numberReqs, ids, roles), lost: r.lost, foreign: !!r.foreign};
};

// ---------------------------------------------------------------- main ---------
(window as any).drawFigure = async (job: any) => {
  const T: Record<string, number> = {}, tAll = now();
  const mol = parse(job.doc);
  restoreTsHydrogens(mol);
  mol.style = {...DEFAULT_STYLE, ...(job.style ?? {})};
  mol.arrows ??= [];
  mol.captions ??= [];
  const ctx = makeCtx(mol), {f, pt, measure} = ctx;
  const refs: string[] = job.refs ?? [];
  const before = atomPxOf(mol);

  // 1. label-label bonds (after the folded hydrogens have their side: it decides how much line shows)
  let t = now();
  placeFoldedHydrogens(mol, ctx, job);
  keepHydrogenSides(mol, ctx, job);
  T.labels = now() - t;
  const lengthen = lengthenLabelBonds(mol, ctx, job);
  T.lengthen = lengthen.ms;
  // captions tied to an atom (residue labels) move with it
  const followCaptions = (was: Pt[]) => {
    const after = atomPxOf(mol);
    for (const t of (job.attached ?? []) as {caption: number; atom: number}[]) {
      const c = mol.captions[t.caption];
      if (!c) continue;
      c.x = +(c.x + (after[t.atom][0] - was[t.atom][0]) / L).toFixed(4); c.y = +(c.y - (after[t.atom][1] - was[t.atom][1]) / L).toFixed(4);
    }
  };
  followCaptions(before);
  t = now();
  fitShortHashes(mol, ctx);
  placeLonePairs(mol, ctx, job);
  // placeLonePairs handles atom, bond and forming-bond targets together.
  placeRadicals(mol, ctx, job);
  placeOxidation(mol, ctx, job);
  T.pairs = now() - t;
  // 2. circled charges
  const charges = placeCharges(mol, ctx, job);
  // a ring squeezed against a bonded label: show LINE_SHOW of the line between them; the ring keeps its seat at its
  // own atom and moves away with it
  const squeezed = new Set<number>([...charges.rows, ...squeezedFixed(mol, ctx, job)].flatMap((r: any) => (r.squeezed ?? []).map((j: number) =>
    mol.bonds.findIndex((b: any) => b.type !== HBOND && b.atoms.includes(r.atom) && b.atoms.includes(j)))).filter((bi: number) => bi >= 0));
  if (squeezed.size) {
    const was = atomPxOf(mol), more = lengthenLabelBonds(mol, ctx, job, squeezed);
    followCaptions(was);
    lengthen.rows.push(...more.rows);
  }
  T.charges = charges.ms;
  // boxes around their atoms' letters and marks
  const boxed = fitBoxes(mol, ctx, job.tsFrames);
  placeTsMarks(mol, ctx, job.tsFrames);
  T.boxes = boxed.ms;
  // 3. curved arrows (first, leaving the numbers' seats free where they can), 4. numbers (after the arrows), 5. titles
  const seats = placeNumbers(mol, ctx, job, [], true).seats;
  const routed = routeArrows(mol, ctx, job, seats);
  T.arrows = routed.ms;
  const curvedPolys = routed.done.flatMap((p) => p.polys);
  const numbers = placeNumbers(mol, ctx, job, curvedPolys);
  T.numbers = numbers.ms;
  for (const p of routed.done) mol.arrows!.push(p.arrow);
  t = now();
  const titles = placeTitles(mol, ctx, job, curvedPolys);
  T.titles = now() - t;
  const names: string[] = [...(job.straightNames ?? []).slice(0, mol.arrows!.length - routed.done.length), ...routed.done.map((p) => p.req.id)];
  while (names.length < mol.arrows!.length) names.push(`arrow${names.length}`);

  // save with writeOct, read back with readOct: everything below draws, measures and exports the reloaded document
  t = now();
  const oct = writeOct(mol, mol.style, {}, tsCdxml(mol));
  const re = readOct(oct), M = re.mol;
  restoreTsHydrogens(M);
  const cdxmlText = oct.slice(0, oct.lastIndexOf('<!--Octet 1 '));     // Octet's toCdxml output: what a .cdxml holds
  T.save_reload = now() - t;
  t = now();
  const {d, cls, canvas, g, bounds} = paint(M, ctx);
  const svg = exportSvg(canvas, bounds, pt, names);
  T.draw_export = now() - t;

  // ---- measurements on the live canvas (the browser's own font metrics) ----
  t = now();
  const P = (v: number) => r2(v / pt, 1000), PB = (b: Box | null | undefined) => (b ? [P(b[0]), P(b[1]), P(b[2]), P(b[3])] : null), PP = (p: Pt) => [P(p[0]), P(p[1])];
  const px = atomPxOf(M);
  const refOf = (i: number) => refs[+(M.atoms[i].hiddenNumber ?? -1)] ?? `#${i}`;
  const texts = [...g.querySelectorAll('text')].map((el: any) => {
    const b = el.getBBox(), k = inkOfText(el, glyphInk), id = el.getAttribute('id') ?? '';
    return {el, caption: id.startsWith('role-caption-') ? +id.slice(13) : null, text: el.textContent as string, ink: (k ? [k[0], k[1], k[2], k[3]] : [b.x, b.y, b.x + b.width, b.y + b.height]) as Box, line: [b.x, b.y, b.x + b.width, b.y + b.height] as Box};
  });
  const labelTexts = texts.filter((x) => x.caption === null);          // the label pieces, in d.labels order
  const pcs = piecesOf(M, d, ctx), pieceAtom = new Map<number, number>();
  pcs.forEach((list, i) => list.forEach((p) => pieceAtom.set(p.k, i)));
  const curvedM: any[] = (M.arrows ?? []).filter((a: any) => a.kind === 'curved' || a.kind === 'fishhook');     // (a file without arrows reads back with none)
  const straightM: any[] = (M.arrows ?? []).filter((a: any) => !(a.kind === 'curved' || a.kind === 'fishhook'));
  const rq: CurvedReq[] = job.curved ?? [];
  const placedIds = routed.done.map((p) => p.req.id);
  const numberCaps = new Set((job.numbers ?? []).map((n: NumberReq) => n.caption));
  const capIndex = new Map<number, number>((M.captions ?? []).map((c: any, k: number) => [c.id, k]));
  const roleOf = (k: number) => job.captionRoles?.[k] ?? 'text';

  // atoms
  const atomsOut: Record<string, any> = {};
  M.atoms.forEach((a: any, i: number) => { atomsOut[refOf(i)] = {x_pt: P(px[i][0]), y_pt: P(px[i][1]), label_box_pt: PB(d.label[i] as Box), moved_pt: [P(px[i][0] - before[i][0]), P(px[i][1] - before[i][1])]}; });
  const pairsOut = d.electrons.filter((e: any) => e.key?.startsWith('pair')).map((e: any) => {
    const dx = e.at[0] - px[e.atom][0], dy = e.at[1] - px[e.atom][1], len = Math.hypot(dx, dy) || 1;
    const z = f.size * ctx.ratio(M.atoms[e.atom]), n: Pt = [-dy / len, dx / len];
    return {ref: refOf(e.atom), key: e.key, center_pt: PP(e.at), radius_pt: P(0.09 * z),
      dots_pt: [PP([e.at[0] + n[0] * 0.19 * z, e.at[1] + n[1] * 0.19 * z]), PP([e.at[0] - n[0] * 0.19 * z, e.at[1] - n[1] * 0.19 * z])]};
  });
  const radicalsOut = d.electrons.filter((e: any) => e.key?.startsWith('radical')).map((e: any) => ({ref: refOf(e.atom), key: e.key, center_pt: PP(e.at), multiplier: e.multiplier ?? 1, radius_pt: P(.1 * f.size * ctx.ratio(M.atoms[e.atom]))}));
  // bonds: atom-to-atom length, visible line, labels at the ends, lengthened or not
  const lengthened = new Map<number, any>(lengthen.rows.map((r: any) => [r.bond, r]));
  const bondsOut = M.bonds.map((b: any, bi: number) => {
    const v = bondVisible(M, d, ctx, cls, bi), labels = (d.label[b.atoms[0]] ? 1 : 0) + (d.label[b.atoms[1]] ? 1 : 0), lr = lengthened.get(bi);
    return {a: refOf(b.atoms[0]), b: refOf(b.atoms[1]), order: b.type === HBOND ? 0 : b.type, hbond: b.type === HBOND || undefined, length_pt: P(dist(px[b.atoms[0]], px[b.atoms[1]])), visible_line_pt: v ? P(v.visible) : null,
      labels, hidden_h: b.atoms.some((i: number) => M.atoms[i].hidden), lengthened: !!lr && lr.moved_px > 0.05, ...(lr ? {length_before_pt: P(lr.length_before_px), target_pt: lr.target_px === null ? null : P(lr.target_px)} : {})};
  });
  // curved arrows: ends, and what each end reads as (readEnd: an atom's symbol letters or bare vertex, or a bond's axis)
  const symbolBox = (j: number): Box | null => ownSymbol(M, pcs, px, j);
  const nearestTarget = (p: Pt, pairRef?: string) => {
    if (pairRef) {
      const pair = d.electrons.find((e: any) => e.key?.startsWith('pair') && refOf(e.atom) === pairRef && dist(p, e.at) <= PAIR_GAP + .2);
      if (pair) return {kind: 'atom', refs: [pairRef], distance_pt: P(dist(p, pair.at))};
    }
    const r = readEnd(M, px, symbolBox, p);
    if (r.kind === 'bond') { const b = M.bonds[r.bond]; return {kind: 'bond', refs: [refOf(b.atoms[0]), refOf(b.atoms[1])], distance_pt: P(r.dB)}; }
    return {kind: 'atom', refs: [refOf(r.atom)], distance_pt: P(r.dA)};
  };
  const curvedOut = curvedM.map((a: any, k: number) => {
    const request = routed.done[k]?.req;
    const sourcePairRef = request?.src.kind === 'atom' && request.electrons !== 1 ? refs[request.src.atoms[0]] : undefined;
    const s: Pt = [a.from[0] * L, -a.from[1] * L], e: Pt = [a.to[0] * L, -a.to[1] * L];
    const path = arrowPath(a, L) as Pt[];
    let len = 0; for (let q = 1; q < path.length; q++) len += dist(path[q - 1], path[q]);
    const id = placedIds[k] ?? `curved${k}`, req = rq.find((r) => r.id === id);
    return {id, kind: a.kind, electrons: a.kind === 'fishhook' ? 1 : 2, color: (a.colour ?? '#000000').toLowerCase(), start_head: a.start ?? 'none', end_head: a.end ?? (a.kind === 'fishhook' ? 'half' : 'full'),
      start_pt: PP(s), end_pt: PP(e), start_ref: req?.src.kind === 'atom' && d.electrons.some((m: any) => m.atom === req.src.atoms[0] && m.key?.startsWith(req.electrons === 1 ? 'radical' : 'pair') && dist(m.at, s) / pt <= 2)
        ? {kind: 'atom', refs: [refOf(req.src.atoms[0])]} : nearestTarget(s, sourcePairRef), end_ref: nearestTarget(e), bend: a.bend ?? 0, length_pt: P(len),
      requested: req ? {from: req.src, to: req.snk} : null};
  });
  // numbers: the glyph ink of each number and its room
  const numbersOut = (job.numbers ?? []).map((n: NumberReq) => {
    const c = M.captions?.[n.caption], tx = c ? texts.find((x) => x.caption === c.id) : undefined, row = numbers.rows.find((r: any) => r.caption === n.caption);
    if (!c || !tx) return {ref: refOf(n.atom), text: c?.text ?? null, box_pt: null, size_pt: c?.size ?? null, placed: false, refused: row?.refused ?? null};
    return {ref: refOf(n.atom), text: c.text, box_pt: PB(tx.ink), size_pt: c.size ?? M.style!.captionSize, placed: !row?.refused,
      own_gap_pt: row?.own_gap_px !== undefined ? P(row.own_gap_px) : null, nearest_other_gap_pt: row?.nearest_other_gap_px !== undefined ? P(row.nearest_other_gap_px) : null, direction_deg: row?.deg ?? null};
  });
  // charges: circles (center and outer diameter from the ring's polygons) and charges written as text
  const chargesOut: any[] = [];
  M.atoms.forEach((a: any, i: number) => {
    if (!a.charge) return;
    const ring = d.electrons.find((e: any) => e.atom === i && e.key === 'charge' && a.circled);
    if (ring) {
      const c = ring.at as Pt, z = f.size * ctx.ratio(a), R = 0.34 * z + f.line / 2;
      const own = d.polygons.filter((poly: number[][], k: number) => cls[k] === 'mark' && poly.every(([x, y]) => Math.hypot(x - c[0], y - c[1]) <= R + 0.6));
      const outer = Math.max(0, ...own.flat().map(([x, y]: number[]) => Math.hypot(x - c[0], y - c[1])));
      const bars = own.length - 40;
      chargesOut.push({ref: refOf(i), charge: a.charge, kind: 'circle', center_pt: PP(c), outer_d_pt: P(2 * outer), default_outer_d_pt: P(2 * R), sign_bars: bars,
        center_to_atom_bonds: r2(dist(c, px[i]) / L, 1000), angle_deg: a.angles?.charge ?? null});
    } else {
      const signs = pcs[i].filter((p) => p.sign), sb = union(signs.map((p) => p.box));
      chargesOut.push({ref: refOf(i), charge: a.charge, kind: 'text', text: signs.map((p) => p.text).join('') || null, center_pt: sb ? PP([(sb[0] + sb[2]) / 2, (sb[1] + sb[3]) / 2]) : null, outer_d_pt: null, box_pt: PB(sb),
        size_pt: signs.length ? r2(d.labels[signs[0].k].size / pt, 100) : null});
    }
  });
  // captions: titles, texts, residue labels, conditions, numbers (glyph ink boxes)
  // (the numbers are listed under "numbers" only)
  const textsOut = texts.filter((x) => x.caption !== null && !numberCaps.has(capIndex.get(x.caption!) ?? -1)).map((x) => { const k = capIndex.get(x.caption!) ?? -1; return {text: x.text, role: roleOf(k), caption: k, box_pt: PB(x.ink), size_pt: r2((M.captions![k]?.size ?? M.style!.captionSize), 100)}; });
  const piecesOut = labelTexts.map((x, k) => ({ref: pieceAtom.has(k) ? refOf(pieceAtom.get(k)!) : null, text: x.text, box_pt: PB(x.ink), size_pt: r2(d.labels[k]?.size / pt, 100)}));
  const font = fontCheck(ctx), fontProblems: string[] = [];
  if (font.checked && Math.abs(font.ratio - 1) > FONT_WIDTH_TOL)
    fontProblems.push(`font: the browser has no ${font.font} or a font with its widths (Liberation Sans, Arimo): text is ${r2(Math.abs(font.ratio - 1) * 100, 10)} % ${font.ratio > 1 ? 'wider' : 'narrower'} than ${font.font}, so labels, gaps and visible lines are measured, and the PNG drawn, in another font (install Arial or Liberation Sans, for example the package fonts-liberation)`);
  T.measure = now() - t;

  // ---- what the saved file holds, read back (the reloaded drawing and its CDXML part alone) ----
  const view = (m: any) => viewOf(m, refs, job.numbers ?? [], placedIds, job.captionRoles ?? []);
  const reload = {...view(M), lost: re.lost, foreign: !!re.foreign};
  T.total_page = now() - tAll;
  return {
    oct, cdxml: cdxmlText, svg, names, reload, meta: {refs, numbers: job.numbers ?? [], curvedIds: placedIds, captionRoles: job.captionRoles ?? []},
    report: {
      units: 'pt, the SVG frame (x right, y down)', px_per_pt: pt, svg_bounds_pt: PB(bounds),
      atoms: atomsOut, bonds: bondsOut, curved: curvedOut, numbers: numbersOut, charges: chargesOut, lone_pairs: pairsOut, radicals: radicalsOut, texts: textsOut, label_pieces: piecesOut,
      straight_arrows: straightM.map((a: any) => ({kind: a.kind, from_pt: PP([a.from[0] * L, -a.from[1] * L]), to_pt: PP([a.to[0] * L, -a.to[1] * L]), color: (a.colour ?? '#000000').toLowerCase()})),
      lengthening: {target_visible_line_pt: lengthen.target_px === null ? null : P(lengthen.target_px), target_estimated: lengthen.target_estimated, reference_bonds: lengthen.reference_bonds, skipped: lengthen.skipped.map((s: any) => ({...s, a: refOf(M.bonds[s.bond].atoms[0]), b: refOf(M.bonds[s.bond].atoms[1])})),
        bonds: lengthen.rows.map((r: any) => ({a: refOf(M.bonds[r.bond].atoms[0]), b: refOf(M.bonds[r.bond].atoms[1]), moved: refOf(r.moving), moved_end_named: r.named, branch_atoms: r.branch.length, moved_pt: P(r.moved_px), length_before_pt: P(r.length_before_px), length_pt: P(r.length_px),
          length_bonds: r2(r.length_px / L, 1000), visible_before_pt: r.visible_before_px === null ? null : P(r.visible_before_px), visible_pt: r.visible_px === null ? null : P(r.visible_px), target_pt: r.target_px === null ? null : P(r.target_px)}))},
      charge_placement: charges.rows.map((r: any) => ({...r, ref: refOf(r.atom)})),
      boxes_grown: boxed.rows,
      routes: routed.done.map((p) => ({id: p.req.id, ...p.info})),
      number_placement: numbers.rows.map((r: any) => ({...r, ref: refOf(r.atom)})),
      titles,
      font_check: font,
      problems: [...routed.problems, ...numbers.problems, ...fontProblems],
      // a bond between two labels in a ring keeps its length (a ring cannot be lengthened on one side)
      notes: lengthen.skipped.map((s: any) => `bond ${refOf(M.bonds[s.bond].atoms[0])}-${refOf(M.bonds[s.bond].atoms[1])} between two labels is a ring bond: not lengthened (a ring cannot be lengthened on one side); visible line ${bondsOut[s.bond]?.visible_line_pt ?? '?'} pt`),
      reload: {lost: re.lost, foreign: !!re.foreign},
      timings_ms: T,
    },
  };
};
