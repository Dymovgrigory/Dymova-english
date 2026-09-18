"use client";

import { BANNER_HEX } from "./decor";
import { Emblem } from "./emblems";

/**
 * Знамя на остроконечной башенке правее главных ворот: цвет выбранный в Мастерской,
 * эмблема носимого звания. Вектор: меняется мгновенно и бесплатно. Полотнище чуть
 * колышется на ветру; при «уменьшить движение» анимация выключена.
 */
export function Banner({ color, emblem }: { color: string; emblem: string }) {
  const hex = BANNER_HEX[color] ?? BANNER_HEX.plum;
  return (
    <div
      aria-hidden
      data-banner={color}
      data-emblem={emblem}
      className="pointer-events-none absolute"
      style={{ left: "56.3%", top: "42.5%", width: "4.6%", zIndex: 58 }}
    >
      <svg viewBox="0 0 64 96" className="block h-auto w-full drop-shadow-[0_4px_6px_rgb(20_10_30/0.45)]">
        {/* древко с наконечником */}
        <rect x="4" y="4" width="3.4" height="92" rx="1.7" fill="#5d4632" />
        <circle cx="5.7" cy="4.4" r="3.2" fill="#c9962e" />
        {/* полотнище с глубоким симметричным фестоном */}
        <path
          d="M9 10h44v26l-22 14-22-14V10z"
          fill={hex}
          className="motion-safe:animate-[castle-banner_2.6s_ease-in-out_infinite_alternate]"
          style={{ transformOrigin: "9px 10px" }}
        />
        <path d="M9 10h44v7H9z" fill="rgb(255 255 255 / 0.18)" />
        <g transform="translate(19 15) scale(0.95)">
          <Emblem id={emblem} className="text-white" />
        </g>
      </svg>
    </div>
  );
}
