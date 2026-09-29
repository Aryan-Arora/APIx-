"use client";

import { useEffect, useRef, useState } from "react";

/** A decorative wordmark reveal, independent of API loading or readiness. */
export default function ParticleIntro({
  children,
}: {
  children: React.ReactNode;
}) {
  const [visible, setVisible] = useState(true);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const skipRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!visible) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    let frame = 0;
    let finished = false;
    const finish = () => {
      if (finished) return;
      finished = true;
      cancelAnimationFrame(frame);
      setVisible(false);
      if (document.activeElement === skipRef.current) {
        requestAnimationFrame(() =>
          document.querySelector<HTMLAnchorElement>(".brand")?.focus(),
        );
      }
    };
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    if (!canvas || !context || reduced.matches) {
      frame = requestAnimationFrame(finish);
      return () => cancelAnimationFrame(frame);
    }

    const width = window.innerWidth;
    const height = window.innerHeight;
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    context.scale(ratio, ratio);

    // Sample a local system-font wordmark: no font download or external asset.
    const stencil = document.createElement("canvas");
    stencil.width = 800;
    stencil.height = 260;
    const ink = stencil.getContext("2d");
    if (!ink) {
      frame = requestAnimationFrame(finish);
      return () => cancelAnimationFrame(frame);
    }
    ink.font =
      '700 210px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
    ink.textBaseline = "middle";
    const total = ink.measureText("APIx").width;
    const left = (800 - total) / 2;
    ink.fillStyle = "#ffffff";
    ink.fillText("API", left, 138);
    ink.fillStyle = "#f4b46c";
    ink.fillText("x", left + ink.measureText("API").width, 138);
    const pixels = ink.getImageData(0, 0, 800, 260).data;
    const scale = Math.min((width - 48) / 800, 0.9);
    const random = (n: number) => {
      const value = Math.sin(n * 127.1 + 311.7) * 43758.5453;
      return value - Math.floor(value);
    };
    const particles: { x: number; y: number; startX: number; startY: number; delay: number; color: string; size: number }[] = [];
    for (let y = 0; y < 260; y += 5) {
      for (let x = 0; x < 800; x += 5) {
        const pixel = (y * 800 + x) * 4;
        if (pixels[pixel + 3] < 150) continue;
        const n = particles.length + 1;
        particles.push({
          x: width / 2 + (x - 400) * scale,
          y: height / 2 - 20 + (y - 130) * scale,
          startX: random(n) * width,
          startY: random(n + 3000) * height,
          delay: random(n + 6000) * 240,
          color: pixels[pixel + 1] < 230 ? "#f4b46c" : "#edf4fb",
          size: Math.max(0.8, 1.65 * scale),
        });
      }
    }
    const started = performance.now();
    const draw = (now: number) => {
      const elapsed = now - started;
      if (elapsed >= 2200) {
        finish();
        return;
      }
      context.clearRect(0, 0, width, height);
      for (const particle of particles) {
        const progress = Math.max(
          0,
          Math.min(1, (elapsed - particle.delay) / 1250),
        );
        const eased = 1 - Math.pow(1 - progress, 3);
        context.globalAlpha =
          Math.min(1, elapsed / 200) * (0.35 + 0.65 * eased);
        context.fillStyle = particle.color;
        context.beginPath();
        context.arc(
          particle.startX + (particle.x - particle.startX) * eased,
          particle.startY + (particle.y - particle.startY) * eased,
          particle.size,
          0,
          Math.PI * 2,
        );
        context.fill();
      }
      frame = requestAnimationFrame(draw);
    };
    frame = requestAnimationFrame(draw);
    // Resize and accessibility changes dismiss rather than restart the sequence.
    const safety = window.setTimeout(finish, 2600);
    window.addEventListener("resize", finish, { once: true });
    reduced.addEventListener("change", finish);
    return () => {
      finished = true;
      cancelAnimationFrame(frame);
      clearTimeout(safety);
      window.removeEventListener("resize", finish);
      reduced.removeEventListener("change", finish);
    };
  }, [visible]);

  return (
    <>
      <div inert={visible}>{children}</div>
      {visible && (
        <div className="particle-intro" aria-label="APIx introduction">
          <canvas ref={canvasRef} aria-hidden="true" />
          <div className="intro-caption" aria-hidden="true">
            INDIA AIRFARE OBSERVATORY
          </div>
          <button
            ref={skipRef}
            className="intro-skip"
            onClick={() => {
              setVisible(false);
              requestAnimationFrame(() =>
                document.querySelector<HTMLAnchorElement>(".brand")?.focus(),
              );
            }}
          >
            Skip intro <span aria-hidden="true">↗</span>
          </button>
          <span className="sr-only">APIx. India Airfare Observatory.</span>
        </div>
      )}
    </>
  );
}
