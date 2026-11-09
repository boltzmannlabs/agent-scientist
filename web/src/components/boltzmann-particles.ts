import art from '../../../sci_cli/data/science-terminal-art.json';
import { moveParticle, type LogoPointer, type ParticleMotion } from './boltzmann-particle-motion';

interface Particle { x: number; y: number; seed: number }
const dots = [[1, 8], [2, 16], [4, 32], [64, 128]];
const width = art.boltzmann[0].length * 2;
const height = art.boltzmann.length * 4;

// Decode the actual CLI artwork, so the particle silhouette stays the same logo.
export const logoParticles: Particle[] = art.boltzmann.flatMap((line, row) =>
  Array.from(line).flatMap((char, col) => dots.flatMap((masks, dy) =>
    masks.flatMap((mask, dx) => {
      if (!((char.charCodeAt(0) - 0x2800) & mask)) return [];
      const x = col * 2 + dx, y = row * 4 + dy;
      let hash = Math.imul(x + 1, 374761393) + Math.imul(y + 1, 668265263);
      hash = Math.imul(hash ^ (hash >>> 13), 1274126177);
      const seed = ((hash ^ (hash >>> 16)) >>> 0) / 4294967296;
      return [{ x: (x - width / 2) / width, y: (y - height / 2) / height, seed }];
    }),
  )),
);

export function drawLogoParticles(ctx: CanvasRenderingContext2D, size: number, time: number,
  motions: ParticleMotion[], pointer: LogoPointer | null, seconds: number) {
  const height = size / 1.2;
  const cx = size / 2, cy = height / 2;
  const scale = size * 0.78;
  ctx.clearRect(0, 0, size, height);
  const halo = ctx.createRadialGradient(cx, cy, 0, cx, cy, size * 0.45);
  halo.addColorStop(0, '#42213a38');
  halo.addColorStop(0.6, '#132b3b24');
  halo.addColorStop(1, '#00000000');
  ctx.fillStyle = halo;
  ctx.fillRect(0, 0, size, height);
  const arrival = Math.pow(Math.max(0, 1 - time / 2), 3);
  const yaw = Math.sin(time * 0.35) * 0.22;
  const colors = ['#f5d9ed', '#a5d9f5', '#ff8fbb', '#d5ecff'];

  for (const [index, p] of logoParticles.entries()) {
    const phase = p.seed * Math.PI * 2;
    const radius = Math.hypot(p.x, p.y);
    const turn = arrival * (2 + radius * 3);
    const angle = Math.atan2(p.y, p.x) + turn;
    const expansion = 1 + arrival * 0.65;
    const x = Math.cos(angle) * radius * expansion;
    const y = Math.sin(angle) * radius * expansion;
    const drift = Math.sin(time * 0.7 + phase) * 0.004;
    const home = { x: x * Math.cos(yaw) + drift, y: y + Math.cos(time * 0.5 + phase) * 0.003 };
    const motion = motions[index];
    moveParticle(motion, home, pointer, seconds, p.seed);
    const px = cx + (home.x + motion.x) * scale;
    const py = cy + (home.y + motion.y) * scale;
    const glow = 0.5 + 0.5 * Math.sin(time * 1.2 + phase * 9);
    const bright = p.seed < 0.035;
    ctx.globalAlpha = bright ? 0.55 + glow * 0.45 : 0.5 + glow * 0.45;
    ctx.fillStyle = colors[Math.floor(p.seed * colors.length)];
    ctx.beginPath();
    ctx.arc(px, py, (bright ? 1.3 + glow * 0.6 : 0.55 + p.seed * 0.45) * size / 360, 0, Math.PI * 2);
    ctx.fill();
    if (bright) {
      const light = ctx.createRadialGradient(px, py, 0, px, py, size * 0.018);
      light.addColorStop(0, '#fff4fc99');
      light.addColorStop(0.3, '#c9e9ff44');
      light.addColorStop(1, '#b5dfff00');
      ctx.fillStyle = light;
      ctx.fillRect(px - size * 0.018, py - size * 0.018, size * 0.036, size * 0.036);
    }
  }
  // Sparse, slowly orbiting stars give the mark a little depth without obscuring it.
  for (let i = 0; i < 65; i++) {
    const angle = i * 2.39996 + time * (i % 2 ? 0.025 : -0.018);
    const radius = size * (0.29 + (i % 13) * 0.013);
    ctx.globalAlpha = 0.12 + (1 + Math.sin(i + time)) * 0.12;
    ctx.fillStyle = i % 3 ? '#a5d9f5' : '#ffadd0';
    ctx.beginPath();
    ctx.arc(cx + Math.cos(angle) * radius, cy + Math.sin(angle) * radius * 0.8, size / 650, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.globalAlpha = 1;
}
