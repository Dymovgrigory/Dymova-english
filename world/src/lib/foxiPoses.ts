export const FOXI_POSES = [
  "wave",
  "sit",
  "sun",
  "rain",
  "cat",
  "hat",
  "cap",
  "pan",
  "map",
  "nap",
  "dog",
  "duck",
  "bed",
  "fan",
  "ship",
  "night",
  "moon",
  "bee",
  "car",
  "book",
  "cheer",
] as const;

export type FoxiPose = (typeof FOXI_POSES)[number];

export function foxiSrc(pose?: string) {
  const id = FOXI_POSES.includes(pose as FoxiPose) ? pose : "wave";
  return `/world/foxi/${id}.png`;
}
