import { useEffect, useRef } from 'react';
import { drawLogoParticles, logoParticles } from './boltzmann-particles';
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
        drawLogoParticles(ctx, size, elapsed / 1000);
        element.dataset.animated = 'true';
        painted = now;
      }
      frame = requestAnimationFrame(paint);
    }
    function sync() {
      cancelAnimationFrame(frame);
      frame = 0; last = 0;
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
    document.addEventListener('visibilitychange', sync);
    reduced.addEventListener('change', sync);
    sync();
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
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
