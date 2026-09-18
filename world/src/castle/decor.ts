/**
 * Украшения на сцене замка: предмет стоит на авторской точке с контактной тенью.
 * Координаты — доли картинки (0..1), точка привязки — низ по центру предмета,
 * чтобы «ноги» стояли на земле, а не висели. Откалибровано по диораме 1536×864.
 */

export type DecorAnchor = "gate" | "bridge" | "courtyard" | "roofs" | "stream" | "meadow" | "walls";

export type DecorPoint = {
  /** Низ-центр предмета, доли сцены. */
  x: number;
  y: number;
  /** Ширина предмета, доля ширины сцены. */
  width: number;
};

export const DECOR_POINTS: Record<DecorAnchor, DecorPoint> = {
  gate: { x: 0.452, y: 0.635, width: 0.045 },      // у створок ворот; предметы разводит DECOR_OFFSETS
  bridge: { x: 0.503, y: 0.755, width: 0.105 },    // гирлянда над мостом, столбы по краям
  courtyard: { x: 0.585, y: 0.5, width: 0.05 },    // правая часть двора у Лавки
  roofs: { x: 0.362, y: 0.46, width: 0.035 },      // конёк крыши Школы
  stream: { x: 0.625, y: 0.8, width: 0.05 },       // вода ручья справа от моста
  meadow: { x: 0.18, y: 0.76, width: 0.06 },       // луг перед замком слева
  walls: { x: 0.4, y: 0.6, width: 0.04 },          // парапет передней стены левее ворот
};

/**
 * Личные смещения предметов от точки привязки (доли сцены). Нужны там, где одну
 * точку делят несколько предметов (ворота), чтобы они не вставали друг в друга.
 */
export const DECOR_OFFSETS: Record<string, { dx?: number; dy?: number }> = {
  "decor-gate-lantern": { dx: -0.04 },
  "decor-gate-fox-statue": { dx: 0.05 },
  "decor-gate-pots": { dx: -0.055, dy: 0.015 },
  "decor-gate-pumpkins": { dx: 0.06, dy: 0.02 },
};

/** Подкраска предмета под время суток — та же логика, что у светового слоя сцены. */
export function decorFilter(time: string): string {
  const filters: Record<string, string> = {
    dawn: "brightness(0.94) sepia(0.22) hue-rotate(-12deg)",
    day: "none",
    dusk: "brightness(0.88) sepia(0.28) hue-rotate(-18deg)",
    night: "brightness(0.62) saturate(0.75) hue-rotate(12deg)",
  };
  return filters[time] ?? "none";
}

/** Цвета знамени — пары к каталогу бэкенда (BANNER_COLORS). */
export const BANNER_HEX: Record<string, string> = {
  plum: "#7c4d8f",
  emerald: "#2e8b6e",
  gold: "#c9962e",
  azure: "#3b7dd8",
  rose: "#d35f7f",
};
