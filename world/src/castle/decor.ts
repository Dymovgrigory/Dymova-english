/**
 * Украшения на сцене замка: предмет встаёт в слот на авторской точке.
 * Координаты — доли картинки (0..1), точка привязки — низ по центру предмета,
 * чтобы «ноги» стояли на земле, а не висели. Откалибровано по диораме 1536×864.
 * Слоты у ворот повторяют прежние DECOR_POINTS+DECOR_OFFSETS, предметы не переехали.
 */
import type { SpotId } from "./buildings";

export type DecorAnchor = "gate" | "bridge" | "courtyard" | "roofs" | "stream" | "meadow" | "walls";

export type DecorSlot = {
  /** Низ-центр предмета, доли сцены. */
  x: number;
  y: number;
  /** Ширина предмета, доля ширины сцены. */
  width: number;
  anchor: DecorAnchor;
  /** Здания, встающие перед предметом — их силуэт рисуется поверх (окклюзия). */
  occludedBy?: SpotId[];
};

export const DECOR_SLOTS: Record<string, DecorSlot> = {
  "gate-left": { x: 0.412, y: 0.635, width: 0.045, anchor: "gate", occludedBy: ["quests"] },
  "gate-right": { x: 0.502, y: 0.635, width: 0.045, anchor: "gate" },
  "gate-far-left": { x: 0.397, y: 0.65, width: 0.045, anchor: "gate", occludedBy: ["quests"] },
  "gate-far-right": { x: 0.512, y: 0.655, width: 0.045, anchor: "gate" },
  bridge: { x: 0.503, y: 0.755, width: 0.105, anchor: "bridge" },   // гирлянда над мостом, столбы по краям
  courtyard: { x: 0.585, y: 0.5, width: 0.05, anchor: "courtyard" }, // правая часть двора у Лавки
  roofs: { x: 0.362, y: 0.46, width: 0.035, anchor: "roofs" },       // конёк крыши Школы
  stream: { x: 0.625, y: 0.8, width: 0.05, anchor: "stream" },       // вода ручья справа от моста
  meadow: { x: 0.18, y: 0.76, width: 0.06, anchor: "meadow" },       // луг перед замком слева
  walls: { x: 0.4, y: 0.6, width: 0.04, anchor: "walls", occludedBy: ["quests"] }, // парапет передней стены
};

/** Слоты якоря: у ворот четыре точки, у остальных — одноимённый слот. */
export function slotsForAnchor(anchor: string): string[] {
  return Object.entries(DECOR_SLOTS)
    .filter(([, slot]) => slot.anchor === anchor)
    .map(([id]) => id);
}

/** Калиброванные позиции у ворот — чтобы предметы не вставали друг в друга. */
const DEFAULT_SLOTS: Record<string, string> = {
  "decor-gate-lantern": "gate-left",
  "decor-gate-fox-statue": "gate-right",
  "decor-gate-pots": "gate-far-left",
  "decor-gate-pumpkins": "gate-far-right",
};

/** Слот предмета по умолчанию: явная калибровка у ворот, иначе одноимённый якорю. */
export function defaultSlotFor(itemId: string, anchor?: string | null): string | null {
  if (DEFAULT_SLOTS[itemId]) return DEFAULT_SLOTS[itemId];
  if (anchor && anchor in DECOR_SLOTS) return anchor;
  return null;
}

/** Человеческие названия слотов для выбора места. */
export const SLOT_TITLES: Record<string, string> = {
  "gate-left": "Слева у ворот",
  "gate-right": "Справа у ворот",
  "gate-far-left": "У левого края ворот",
  "gate-far-right": "У правого края ворот",
  bridge: "На мосту",
  courtyard: "Во дворе",
  roofs: "На крыше",
  stream: "На ручье",
  meadow: "На лугу",
  walls: "На стене",
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

/** Лёгкий тон предмета под сезон: осень теплит, зима выбеливает. */
export function decorSeasonTint(season: string): string {
  const tints: Record<string, string> = {
    spring: "sepia(0.08) hue-rotate(18deg)",
    summer: "saturate(1.06)",
    autumn: "sepia(0.12) hue-rotate(-10deg) saturate(1.05)",
    winter: "brightness(1.04) saturate(0.88)",
  };
  return tints[season] ?? "none";
}

/**
 * Живая тень предмета: днём — короткая под ногами, на рассвете тянется влево от
 * восточного солнца, на закате — вправо, ночью едва заметна.
 */
export function decorShadow(time: string): string {
  const shadows: Record<string, string> = {
    dawn: "drop-shadow(-5px 3px 4px rgb(30 15 40 / 0.35))",
    day: "drop-shadow(0 3px 3px rgb(20 10 30 / 0.35))",
    dusk: "drop-shadow(5px 3px 5px rgb(25 12 35 / 0.35))",
    night: "drop-shadow(0 2px 3px rgb(0 0 0 / 0.25))",
  };
  return shadows[time] ?? shadows.day;
}

/** Итоговый filter картинки предмета: подкраска + сезонный тон + тень. */
export function decorImgFilter(time: string, season: string): string {
  const parts = [decorFilter(time), decorSeasonTint(season), decorShadow(time)].filter((f) => f !== "none");
  return parts.length ? parts.join(" ") : "none";
}

/** Цвета знамени — пары к каталогу бэкенда (BANNER_COLORS). */
export const BANNER_HEX: Record<string, string> = {
  plum: "#7c4d8f",
  emerald: "#2e8b6e",
  gold: "#c9962e",
  azure: "#3b7dd8",
  rose: "#d35f7f",
};
