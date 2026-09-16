/** Word-lesson props (legacy Meshy set under /world/foxi/). */
const LESSON_POSES = [
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

/** Emotion / guide poses from Meshy batch (under /world/foxi/poses/). */
const GUIDE_POSES = ["point", "think", "celebrate", "sad", "surprised"] as const;

export const FOXI_POSES = [...LESSON_POSES, ...GUIDE_POSES] as const;

export type FoxiPose = (typeof FOXI_POSES)[number];

/** Files that live under /world/foxi/poses/ (wave also copied to /foxi/wave.png). */
const POSES_DIR = new Set<string>(["wave", ...GUIDE_POSES]);

/** cheer finish art → celebrate pose file. */
const POSE_ALIASES: Record<string, string> = {
  cheer: "celebrate",
};

export function foxiSrc(pose?: string) {
  const raw = pose || "wave";
  const aliased = POSE_ALIASES[raw] ?? raw;
  const id = FOXI_POSES.includes(aliased as FoxiPose)
    ? aliased
    : FOXI_POSES.includes(raw as FoxiPose)
      ? raw
      : "wave";
  if (POSES_DIR.has(id)) return `/world/foxi/poses/${id}.png`;
  return `/world/foxi/${id}.png`;
}
