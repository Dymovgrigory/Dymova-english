"use client";

import { lightLayer } from "./appearance";
import type { Spot } from "./buildings";
import { DECOR_SLOTS, decorImgFilter, defaultSlotFor, type DecorSlot } from "./decor";
import type { DecorItem } from "@/lib/v2/castle";

/** Окклюзия поверх любого украшения (их z — до y*100 ≈ 80), но ниже подсветок зданий (100+). */
export const DECOR_OCCLUSION_Z = 90;

/**
 * Передние элементы диорамы поверх украшений: вырез той же сцены по маске силуэта
 * (приём SpotHighlight). Пиксели совпадают с базовой картинкой, поэтому вне предметов
 * слой незаметен; световая плёнка времени суток повторяется внутри, чтобы вырез
 * не светился на фоне затемнённой сцены.
 */
function OcclusionLayer({ scene, spots, time }: { scene: string; spots: Spot[]; time: string }) {
  if (spots.length === 0) return null;
  const film = lightLayer(time);
  return (
    <>
      {spots.map((spot) => {
        const { left, top, width, height } = spot.area;
        return (
          <div
            key={spot.id}
            aria-hidden
            className="pointer-events-none absolute"
            style={{
              left: `${left}%`,
              top: `${top}%`,
              width: `${width}%`,
              height: `${height}%`,
              zIndex: DECOR_OCCLUSION_Z,
            }}
          >
            <div
              className="h-full w-full"
              style={{
                backgroundImage: `url(${scene})`,
                backgroundSize: `${10000 / width}% ${10000 / height}%`,
                backgroundPosition: `${(left / (100 - width)) * 100}% ${(top / (100 - height)) * 100}%`,
                WebkitMaskImage: `url(${spot.mask})`,
                maskImage: `url(${spot.mask})`,
                WebkitMaskSize: "100% 100%",
                maskSize: "100% 100%",
              }}
            />
            <div
              className="absolute inset-0"
              style={{ background: film.background, mixBlendMode: film.mixBlendMode as "soft-light" | "multiply" }}
            />
          </div>
        );
      })}
    </>
  );
}

/**
 * Слой украшений поверх диорамы: купленные и поставленные предметы в своих слотах.
 * Тень — направленная по времени суток на самой картинке, подкраска — время + сезон,
 * z — по вертикали (ниже на картинке = ближе к зрителю = выше слой).
 */
export function Decor({
  items,
  time,
  season,
  scene,
  spots,
}: {
  items: DecorItem[];
  time: string;
  season: string;
  scene: string;
  spots: Spot[];
}) {
  const placed = items
    .map((item) => {
      if (!item.active) return null;
      const slotId = item.slot ?? defaultSlotFor(item.item_id, item.anchor);
      const slot = slotId ? DECOR_SLOTS[slotId] : undefined;
      return slot ? { item, slot } : null;
    })
    .filter((entry): entry is { item: DecorItem; slot: DecorSlot } => entry !== null);
  if (placed.length === 0) return null;

  const occluderIds = new Set(placed.flatMap(({ slot }) => slot.occludedBy ?? []));
  const occluders = spots.filter((spot) => occluderIds.has(spot.id));
  const filter = decorImgFilter(time, season);

  return (
    <>
      {placed.map(({ item, slot }) => {
        const zIndex = Math.round(slot.y * 100);
        return (
          <div
            key={item.item_id}
            aria-hidden
            data-decor={item.item_id}
            data-slot={item.slot ?? defaultSlotFor(item.item_id, item.anchor)}
            className="pointer-events-none absolute"
            style={{
              left: `${(slot.x - slot.width / 2) * 100}%`,
              top: `${slot.y * 100}%`,
              width: `${slot.width * 100}%`,
              transform: "translateY(-100%)",
              zIndex,
            }}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={`/content/castle/decor/${item.item_id}.webp`}
              alt=""
              draggable={false}
              className="block h-auto w-full"
              style={{ filter }}
            />
          </div>
        );
      })}
      <OcclusionLayer scene={scene} spots={occluders} time={time} />
    </>
  );
}
