"use client";

import { useEffect, useRef } from "react";

/** Погода над замком: частицы на canvas. Ограничены по числу и выключаются при «уменьшить движение». */
const COUNTS: Record<string, number> = { snow: 90, rain: 120, fireflies: 45, petals: 60, fog: 0, aurora: 0 };

export function Weather({ kind }: { kind: string | null }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas || !kind) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const context = canvas.getContext("2d");
    const count = COUNTS[kind] ?? 0;
    if (!context || count === 0) return;

    let frame = 0;
    const resize = () => {
      canvas.width = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    };
    resize();
    window.addEventListener("resize", resize);

    const drops = Array.from({ length: count }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      speed: 0.3 + Math.random() * (kind === "rain" ? 4 : 1.2),
      drift: (Math.random() - 0.5) * 0.6,
      size: kind === "rain" ? 1 : 1 + Math.random() * 2.5,
    }));

    const colors: Record<string, string> = {
      snow: "rgba(255,255,255,0.9)",
      rain: "rgba(180,210,255,0.6)",
      fireflies: "rgba(255,214,120,0.9)",
      petals: "rgba(255,190,214,0.85)",
    };

    const tick = () => {
      context.clearRect(0, 0, canvas.width, canvas.height);
      context.fillStyle = colors[kind] ?? colors.snow;
      for (const drop of drops) {
        drop.y += drop.speed;
        drop.x += drop.drift;
        if (drop.y > canvas.height) {
          drop.y = -4;
          drop.x = Math.random() * canvas.width;
        }
        context.beginPath();
        context.arc(drop.x, drop.y, drop.size, 0, Math.PI * 2);
        context.fill();
      }
      frame = window.requestAnimationFrame(tick);
    };
    tick();

    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("resize", resize);
    };
  }, [kind]);

  if (!kind) return null;
  return <canvas ref={ref} aria-hidden className="pointer-events-none absolute inset-0 h-full w-full" />;
}
