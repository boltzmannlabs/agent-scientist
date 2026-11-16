import { logoParticles } from './boltzmann-particles';

/** The same dotted silhouette as the chat logo, sized for navigation. */
export function BoltzmannMark({ className }: { className?: string }) {
  return <svg viewBox="0 0 100 100" className={className} fill="currentColor" aria-hidden="true">
    {logoParticles.filter((_, i) => i % 3 === 0).map((p, i) =>
      <circle key={i} cx={50 + p.x * 85} cy={50 + p.y * 85} r="0.85" />)}
  </svg>;
}
