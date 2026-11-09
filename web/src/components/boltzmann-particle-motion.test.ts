import { expect, it } from 'vitest';
import { moveParticle } from './boltzmann-particle-motion';

it('repels nearby particles, leaves distant dots alone, and reforms after release across frame rates', () => {
  for (const fps of [20, 30, 60, 120]) {
    const near = { x: 0, y: 0, vx: 0, vy: 0 };
    const far = { ...near };
    const home = { x: 0, y: 0 };
    for (let i = 0; i < fps; i++) {
      moveParticle(near, home, home, 1 / fps, 0.3);
      moveParticle(far, { x: 1, y: 1 }, home, 1 / fps, 0.3);
    }
    expect(Math.hypot(near.x, near.y)).toBeGreaterThan(0.08);
    expect(far).toEqual({ x: 0, y: 0, vx: 0, vy: 0 });
    for (let i = 0; i < fps * 3; i++) moveParticle(near, home, null, 1 / fps, 0.3);
    expect(Math.hypot(near.x, near.y, near.vx, near.vy)).toBeLessThan(0.0001);
  }
});
