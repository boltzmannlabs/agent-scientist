import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useLocation } from 'react-router';
import { BrandEntranceContext } from './brand-entrance-context';
import { drawLogoParticles, logoParticles } from './boltzmann-particles';
import './brand-entrance.css';

interface BrandEntranceProps { children: ReactNode }
const smooth = (n: number) => { const t = Math.max(0, Math.min(1, n)); return t * t * (3 - 2 * t); };

export function BrandEntrance({ children }: BrandEntranceProps) {
  const location = useLocation();
  // Explicit session/admin links retain their destination and skip the welcome.
  const [visible, setVisible] = useState(() =>
    ['/', '/chat'].includes(location.pathname) && !new URLSearchParams(location.search).has('resume'));
  const [revealing, setRevealing] = useState(false);
  const canvas = useRef<HTMLCanvasElement>(null);
  const app = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!visible) return;
    const surface = canvas.current;
    const ctx = surface?.getContext('2d');
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (!surface || !ctx || reduced.matches) { setVisible(false); return; }
    let frame = 0, previous = 0, elapsed = 0, revealed = false;
    let width = 0, height = 0, ratio = 0;
    const motions = logoParticles.map(() => ({ x: 0, y: 0, vx: 0, vy: 0 }));
    const finish = () => setVisible(false);
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') finish(); };
    const onMotion = () => { if (reduced.matches) finish(); };
    function paint(now: number) {
      if (!ctx || !surface) return;
      if (!document.hidden) elapsed += previous ? Math.min(now - previous, 100) : 0;
      previous = now;
      const t = elapsed / 1000;
      const w = window.innerWidth, h = window.innerHeight, dpr = Math.min(window.devicePixelRatio || 1, 2);
      if (w !== width || h !== height || ratio !== dpr) {
        width = w; height = h; ratio = dpr;
        surface.width = Math.round(w * dpr); surface.height = Math.round(h * dpr);
      }
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      ctx.clearRect(0, 0, width, height);
      const target = app.current?.querySelector('.chat-welcome .boltzmann-particle-logo')?.getBoundingClientRect();
      const dock = target ? smooth((t - 6.2) / 1.3) : 0;
      const openingSize = Math.min(width * 0.72, height * 0.8, 700);
      const size = openingSize + ((target?.width || openingSize) - openingSize) * dock;
      const x = width / 2 + ((target ? target.left + target.width / 2 : width / 2) - width / 2) * dock;
      const y = height / 2 + ((target ? target.top + target.height / 2 : height / 2) - height / 2) * dock;
      ctx.save();
      ctx.translate(x - size / 2, y - size / 2.4);
      drawLogoParticles(ctx, size, 3, motions, null, 1 / 60, smooth((t - 2.2) / 3.6));
      ctx.restore();
      surface.style.opacity = String(smooth((t - 0.5) / 2.2) * (1 - smooth((t - 7.5) / 0.8)));
      if (t >= 7.5 && !revealed) { revealed = true; setRevealing(true); }
      if (t >= 8.3) { finish(); return; }
      frame = requestAnimationFrame(paint);
    }
    window.addEventListener('keydown', onKey);
    reduced.addEventListener('change', onMotion);
    frame = requestAnimationFrame(paint);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('keydown', onKey);
      reduced.removeEventListener('change', onMotion);
    };
  }, [visible]);

  return <BrandEntranceContext.Provider value={visible && !revealing}>
    <div ref={app} className={`brand-app ${visible && !revealing ? 'brand-app--entering' : ''}`}
      inert={visible} aria-hidden={visible || undefined}>{children}</div>
    {visible && <div className={`brand-entrance ${revealing ? 'brand-entrance--revealing' : ''}`}
      role="region" aria-label="Stars forming the Boltzmann logo">
      <canvas ref={canvas} className="brand-entrance__stars" aria-hidden="true" />
      <button className="brand-entrance__skip" onClick={() => setVisible(false)}>Skip intro <span aria-hidden="true">→</span></button>
    </div>}
  </BrandEntranceContext.Provider>;
}
