import { useEffect, useRef } from 'react';
import { drawLogoParticles, logoParticles } from './boltzmann-particles';
import type { LogoPointer } from './boltzmann-particle-motion';
import './boltzmann-particle-logo.css';

interface BoltzmannParticleLogoProps { active?: boolean }

export function BoltzmannParticleLogo({ active = true }: BoltzmannParticleLogoProps) {
  const host = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const element = host.current, surface = canvas.current;
    if (!element || !surface || !active) return;
    const ctx = surface.getContext('2d');
    if (!ctx) return;
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
    let frame = 0, visible = true, elapsed = 0, last = 0, painted = -Infinity;
    let size = 0, ratio = 0;
    const motions = logoParticles.map(() => ({ x: 0, y: 0, vx: 0, vy: 0 }));
    let pointer: LogoPointer | null = null;
    function followPointer(event: PointerEvent) {
      const rect = surface!.getBoundingClientRect();
      if (!rect.width || !rect.height || reduced.matches) return;
      pointer = {
        x: ((event.clientX - rect.left) / rect.width - 0.5) / 0.78,
        y: ((event.clientY - rect.top) / rect.height - 0.5) / (1.2 * 0.78),
      };
    }
    function releasePointer() { pointer = null; }
    function paint(now: number) {
      frame = 0;
      if (!ctx || !element || !surface) return;
      if (last) elapsed += Math.min(now - last, 100);
      last = now;
      if (now - painted >= 1000 / 30) {
        const nextSize = element.clientWidth || 360;
        const nextRatio = Math.min(window.devicePixelRatio || 1, 2);
        if (size !== nextSize || ratio !== nextRatio) {
          size = nextSize; ratio = nextRatio;
          surface.width = Math.round(size * ratio);
          surface.height = Math.round(size / 1.2 * ratio);
          ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
        }
        drawLogoParticles(ctx, size, elapsed / 1000, motions, pointer,
          Number.isFinite(painted) ? Math.min((now - painted) / 1000, 0.1) : 1 / 30);
        element.dataset.animated = 'true';
        painted = now;
      }
      frame = requestAnimationFrame(paint);
    }
    function sync() {
      cancelAnimationFrame(frame);
      frame = 0; last = 0;
      painted = -Infinity;
      releasePointer();
      if (!visible || document.hidden || reduced.matches) {
        if (reduced.matches) delete element!.dataset.animated;
        return;
      }
      frame = requestAnimationFrame(paint);
    }
    const observer = new IntersectionObserver(entries => {
      visible = entries.some(entry => entry.isIntersecting);
      sync();
    });
    observer.observe(element);
    element.addEventListener('pointermove', followPointer);
    element.addEventListener('pointerdown', followPointer);
    element.addEventListener('pointerleave', releasePointer);
    element.addEventListener('pointercancel', releasePointer);
    element.addEventListener('pointerup', releasePointer);
    window.addEventListener('blur', releasePointer);
    document.addEventListener('visibilitychange', sync);
    reduced.addEventListener('change', sync);
    sync();
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      element.removeEventListener('pointermove', followPointer);
      element.removeEventListener('pointerdown', followPointer);
      element.removeEventListener('pointerleave', releasePointer);
      element.removeEventListener('pointercancel', releasePointer);
      element.removeEventListener('pointerup', releasePointer);
      window.removeEventListener('blur', releasePointer);
      document.removeEventListener('visibilitychange', sync);
      reduced.removeEventListener('change', sync);
      delete element.dataset.animated;
    };
  }, [active]);

  return <div className="boltzmann-particle-logo" ref={host} role="img" aria-label="Boltzmann Labs dotted b logo">
    <svg className="boltzmann-particle-logo__still" viewBox="-0.64 -0.54 1.28 1.08" aria-hidden="true">
      {logoParticles.map((p, i) => <circle key={i} cx={p.x} cy={p.y} r={0.0028} fill={i % 5 ? '#ff9fc4' : '#b6dfff'} />)}
    </svg>
    <canvas ref={canvas} aria-hidden="true" />
  </div>;
}
