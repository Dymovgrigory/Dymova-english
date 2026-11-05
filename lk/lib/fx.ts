"use client";

// Конфетти и маленькие праздники (canvas-confetti).
import confetti from "canvas-confetti";

export function celebrate(big = false): void {
  if (typeof window === "undefined") return;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const colors = ["#FFC929", "#3CC35E", "#2EA8F5", "#FF5A5F", "#9C5BE0", "#FF8A1F"];
  if (!big) {
    void confetti({ particleCount: 40, spread: 60, startVelocity: 32, origin: { y: 0.85 }, colors, scalar: 0.8 });
    return;
  }
  const end = Date.now() + 1200;
  const frame = () => {
    void confetti({ particleCount: 6, angle: 60, spread: 70, origin: { x: 0, y: 0.7 }, colors });
    void confetti({ particleCount: 6, angle: 120, spread: 70, origin: { x: 1, y: 0.7 }, colors });
    if (Date.now() < end) requestAnimationFrame(frame);
  };
  frame();
}
