export type QualityProfile = "ultra" | "high" | "medium" | "low";

/** Профиль рендера по возможностям устройства (architecture.md §7). */
export function qualityProfile(): QualityProfile {
  if (typeof window === "undefined") return "medium";
  const memory = (navigator as Navigator & { deviceMemory?: number }).deviceMemory ?? 4;
  const cores = navigator.hardwareConcurrency ?? 4;
  const coarse = window.matchMedia("(pointer: coarse)").matches;
  if (coarse && memory <= 4) return "low";
  if (memory >= 8 && cores >= 8) return "ultra";
  if (memory >= 8) return "high";
  return "medium";
}

export const DPR: Record<QualityProfile, [number, number]> = {
  ultra: [1, 2],
  high: [1, 1.75],
  medium: [1, 1.5],
  low: [0.75, 1],
};

export const SHADOWS: Record<QualityProfile, boolean> = {
  ultra: true, high: true, medium: true, low: false,
};

export const POSTFX: Record<QualityProfile, boolean> = {
  ultra: true, high: true, medium: true, low: false,
};

export const FIREFLIES: Record<QualityProfile, number> = {
  ultra: 160, high: 120, medium: 80, low: 0,
};
