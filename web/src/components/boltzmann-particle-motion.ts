export interface LogoPointer { x: number; y: number }
export interface ParticleMotion { x: number; y: number; vx: number; vy: number }

// Coordinates are relative to the logo scale, keeping the interaction identical
// across desktop/mobile sizes and device pixel ratios.
export function moveParticle(motion: ParticleMotion, home: LogoPointer, pointer: LogoPointer | null, seconds: number, seed: number) {
  const steps = Math.max(1, Math.ceil(Math.min(seconds, 0.1) * 120));
  const dt = Math.min(seconds, 0.1) / steps;
  for (let i = 0; i < steps; i++) {
    let ax = -50 * motion.x - 12 * motion.vx;
    let ay = -50 * motion.y - 12 * motion.vy;
    if (pointer) {
      const dx = home.x + motion.x - pointer.x;
      const dy = home.y + motion.y - pointer.y;
      const distance = Math.hypot(dx, dy);
      const force = 24 * Math.pow(Math.max(0, 1 - distance / 0.24), 2);
      // A dot directly under the pointer still needs a direction to escape.
      ax += force * (distance > 0.0001 ? dx / distance : Math.cos(seed * Math.PI * 2));
      ay += force * (distance > 0.0001 ? dy / distance : Math.sin(seed * Math.PI * 2));
    }
    motion.vx += ax * dt; motion.vy += ay * dt;
    motion.x += motion.vx * dt; motion.y += motion.vy * dt;
  }
}
