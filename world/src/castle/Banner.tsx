"use client";

import { BANNER_HEX } from "./decor";
import { Emblem } from "./emblems";

/**
 * Знамя над главными воротами: цвет выбранный в Мастерской, эмблема носимого звания.
 * Вектор: меняется мгновенно и бесплатно. Полотнище чуть колышется на ветру;
 * при «уменьшить движение» анимация выключена.
 */
export function Banner({ color, emblem }: { color: string; emblem: string }) {
  const hex = BANNER_HEX[color] ?? BANNER_HEX.plum;
  return (
    <div
      aria-hidden
      data-banner={color}
      data-emblem={emblem}
      className="pointer-events-none absolute"
      style={{ left: "47.6%", top: "52.2%", width: "3.6%", zIndex: 58 }}
    >
      <svg viewBox="0 0 48 72" className="block h-auto w-full drop-shadow-[0_4px_6px_rgb(20_10_30/0.45)]">
        {/* древко */}
        <rect x="3" y="0" width="2.6" height="72" rx="1.3" fill="#5d4632" />
        <circle cx="4.3" cy="1.6" r="2.4" fill="#c9962e" />
        {/* полотнище с фестоном снизу */}
        <path
          d="M6 6h36v34l-12.5 8L18 40l-6 4-6-4V6z"
          fill={hex}
          className="motion-safe:animate-[castle-banner_2.6s_ease-in-out_infinite_alternate]"
          style={{ transformOrigin: "6px 6px" }}
        />
        <path d="M6 6h36v6H6z" fill="rgb(255 255 255 / 0.18)" />
        <g transform="translate(13 12) scale(0.92)">
          <Emblem id={emblem} className="text-white" />
        </g>
      </svg>
    </div>
  );
}
