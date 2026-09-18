"use client";

import { DECOR_POINTS, decorFilter, type DecorAnchor } from "./decor";
import type { DecorItem } from "@/lib/v2/castle";

/**
 * Слой украшений поверх диорамы: купленные и поставленные предметы на авторских точках.
 * Контактная тень — эллипс под предметом, подкраска — по времени суток, z — по вертикали
 * (ниже на картинке = ближе к зрителю = выше слой).
 */
export function Decor({ items, time }: { items: DecorItem[]; time: string }) {
  const placed = items.filter((item) => item.active && item.anchor in DECOR_POINTS);
  if (placed.length === 0) return null;
  return (
    <>
      {placed.map((item) => {
        const point = DECOR_POINTS[item.anchor as DecorAnchor];
        const zIndex = Math.round(point.y * 100);
        return (
          <div
            key={item.item_id}
            aria-hidden
            data-decor={item.item_id}
            className="pointer-events-none absolute"
            style={{
              left: `${(point.x - point.width / 2) * 100}%`,
              top: `${point.y * 100}%`,
              width: `${point.width * 100}%`,
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
              style={{ filter: decorFilter(time) }}
            />
            <div
              className="mx-auto"
              style={{
                width: "70%",
                height: 8,
                marginTop: -4,
                borderRadius: "50%",
                background: "radial-gradient(closest-side, rgb(20 10 30 / 0.4), transparent)",
              }}
            />
          </div>
        );
      })}
    </>
  );
}
