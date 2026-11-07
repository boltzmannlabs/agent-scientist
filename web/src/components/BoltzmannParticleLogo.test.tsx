// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { expect, it, vi } from 'vitest';
import { BoltzmannParticleLogo } from './BoltzmannParticleLogo';
import { logoParticles } from './boltzmann-particles';

it('pauses off-screen, hidden, inactive and reduced-motion, then releases animation resources', async () => {
  const frames = new Map<number, FrameRequestCallback>();
  let id = 0;
  const media = new EventTarget() as MediaQueryList;
  Object.defineProperty(media, 'matches', { value: false, configurable: true });
  vi.stubGlobal('matchMedia', () => media);
  vi.stubGlobal('requestAnimationFrame', (fn: FrameRequestCallback) => { frames.set(++id, fn); return id; });
  vi.stubGlobal('cancelAnimationFrame', (key: number) => frames.delete(key));
  let intersection: IntersectionObserverCallback;
  const disconnect = vi.fn();
  vi.stubGlobal('IntersectionObserver', class {
    constructor(callback: IntersectionObserverCallback) { intersection = callback; }
    observe() {} disconnect = disconnect;
  });
  const context = {
    setTransform: vi.fn(), clearRect: vi.fn(), fillRect: vi.fn(), beginPath: vi.fn(), arc: vi.fn(), fill: vi.fn(),
    createRadialGradient: () => ({ addColorStop: vi.fn() }),
  };
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(context as unknown as CanvasRenderingContext2D);
  vi.spyOn(document, 'hidden', 'get').mockReturnValue(false);
  const container = document.createElement('div');
  const root = createRoot(container);
  const step = (time: number) => {
    const entry = frames.entries().next().value!;
    frames.delete(entry[0]); entry[1](time);
  };
  try {
    await act(async () => root.render(<BoltzmannParticleLogo />));
    step(100); step(200);
    expect(context.arc.mock.calls.length).toBeGreaterThan(logoParticles.length);
    expect(container.querySelector('[data-animated]')).not.toBeNull();
    intersection!([{ isIntersecting: false } as IntersectionObserverEntry], {} as IntersectionObserver);
    expect(frames.size).toBe(0);
    intersection!([{ isIntersecting: true } as IntersectionObserverEntry], {} as IntersectionObserver);
    expect(frames.size).toBe(1);
    vi.spyOn(document, 'hidden', 'get').mockReturnValue(true);
    document.dispatchEvent(new Event('visibilitychange'));
    expect(frames.size).toBe(0);
    vi.spyOn(document, 'hidden', 'get').mockReturnValue(false);
    document.dispatchEvent(new Event('visibilitychange'));
    Object.defineProperty(media, 'matches', { value: true });
    media.dispatchEvent(new Event('change'));
    expect(frames.size).toBe(0);
    expect(container.querySelector('[data-animated]')).toBeNull();
    expect(container.querySelectorAll('svg circle')).toHaveLength(logoParticles.length);
    await act(async () => root.render(<BoltzmannParticleLogo active={false} />));
    expect(disconnect).toHaveBeenCalled();
    expect(frames.size).toBe(0);
  } finally {
    await act(async () => root.unmount());
    expect(frames.size).toBe(0);
    vi.restoreAllMocks(); vi.unstubAllGlobals();
  }
});

it('keeps an accessible dotted logo when canvas is unavailable', async () => {
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null);
  const container = document.createElement('div');
  const root = createRoot(container);
  try {
    await act(async () => root.render(<BoltzmannParticleLogo />));
    expect(container.querySelector('[role=img]')?.getAttribute('aria-label')).toContain('Boltzmann');
    expect(container.querySelectorAll('svg circle')).toHaveLength(logoParticles.length);
    expect(container.querySelector('[data-animated]')).toBeNull();
  } finally {
    await act(async () => root.unmount()); vi.restoreAllMocks();
  }
});
