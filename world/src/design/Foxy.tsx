"use client";

/**
 * Foxy — маскот Фоксинбурга. Базовые позы (cheer/wave/think/oops) — /content/foxy,
 * новые позы и наряды для разных мест (2026-11-05, Meshy: «Новые Фокси (Meshy).command») —
 * /content/foxi. Пока новой картинки нет, показываем ближайшую базовую позу.
 */
import { useState } from "react";

export type FoxyBasePose = "cheer" | "wave" | "think" | "oops";
export type FoxyPose =
  | FoxyBasePose
  | "school" | "lexicon" | "yard" | "nest" | "glory" | "quests" | "stickers" | "shop" | "tower"
  | "listen" | "speak" | "read" | "winter" | "summer" | "point";

const BASE: Record<FoxyPose, FoxyBasePose> = {
  cheer: "cheer", wave: "wave", think: "think", oops: "oops",
  school: "wave", lexicon: "think", yard: "cheer", nest: "cheer", glory: "cheer", quests: "think",
  stickers: "cheer", shop: "wave", tower: "wave", listen: "think", speak: "cheer", read: "think",
  winter: "wave", summer: "cheer", point: "wave",
};

/** Новые позы есть и для базовых имён (cheer/think/oops) — свежая отрисовка в одном стиле. */
const NEW_ART: ReadonlySet<FoxyPose> = new Set<FoxyPose>([
  "cheer", "think", "oops", "school", "lexicon", "yard", "nest", "glory", "quests", "stickers", "shop", "tower",
  "listen", "speak", "read", "winter", "summer", "point",
]);

export function Foxy({ pose, size = 160, className = "" }: { pose: FoxyPose; size?: number; className?: string }) {
  const [fallback, setFallback] = useState(false);
  const src = NEW_ART.has(pose) && !fallback ? `/content/foxi/${pose}.webp` : `/content/foxy/${BASE[pose]}.webp`;
  return (
    // eslint-disable-next-line @next/next/no-img-element -- прозрачный WebP маскота фиксированного размера
    <img
      src={src}
      alt="Foxy"
      width={size}
      height={size}
      onError={() => setFallback(true)}
      className={`select-none object-contain ${className}`}
      draggable={false}
    />
  );
}
