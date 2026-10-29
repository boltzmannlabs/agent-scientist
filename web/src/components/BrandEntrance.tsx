import { useEffect, useState, type ReactNode } from "react";
import introVideo from "@/assets/agent-scientist-intro.mp4";
import "./brand-entrance.css";

interface BrandEntranceProps {
  children: ReactNode;
}

export function BrandEntrance({ children }: BrandEntranceProps) {
  const [visible, setVisible] = useState(
    () => !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );

  useEffect(() => {
    if (!visible) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setVisible(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [visible]);

  return (
    <>
      <div className="brand-app" inert={visible} aria-hidden={visible || undefined}>{children}</div>
      {visible && (
        <div className="brand-entrance" role="region" aria-label="Welcome to Agent Scientist">
          <video
            className="brand-entrance__video"
            src={introVideo}
            autoPlay
            muted
            playsInline
            preload="auto"
            aria-label="Agent Scientist title intro"
            onEnded={() => setVisible(false)}
            onError={() => setVisible(false)}
          />
          <button className="brand-entrance__skip" onClick={() => setVisible(false)}>Skip intro <span aria-hidden="true">→</span></button>
        </div>
      )}
    </>
  );
}
