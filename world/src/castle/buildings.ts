export type BuildingId =
  | "school"
  | "shop"
  | "glory"
  | "lexicon"
  | "stickers"
  | "nest"
  | "quests"
  | "yard";

export type Building = {
  id: BuildingId;
  title: string;
  hint: string;
  art: string;
  /** SVG polygon points in MAP_VIEWBOX pixel space (same as map.png). */
  polygon: string;
  /** Tooltip anchor — name appears here on hover (above the silhouette). */
  label: { x: number; y: number };
};

/** map.png is 1376×768 — polygons share this space with the SVG <image>. */
export const MAP_VIEWBOX = { width: 1376, height: 768 } as const;

export const CASTLE_MAP = "/world/castle/map.png";
export const CASTLE_MAP_DUSK = "/world/castle/map-dusk.png";

export function isCastleDusk(hour = new Date().getHours()): boolean {
  return hour >= 18 || hour < 6;
}

/** Кликабельная карта всегда дневная: хитбоксы привязаны к map.png. */
export function castleMapSrc(): string {
  return CASTLE_MAP;
}

/**
 * Только открытые здания. Остальная застройка — декор без клика.
 * Полигоны: map-v3 (калибровка по сетке, восстановлены после cinematic drift).
 */
export const BUILDINGS: Building[] = [
  {
    id: "school",
    title: "Школа Foxy",
    hint: "Уроки 1 класса",
    art: "/world/castle/school.png",
    polygon:
      "480,48 535,105 525,115 525,195 555,220 575,255 570,305 530,340 430,340 340,335 325,300 325,260 375,225 435,195 435,115 425,105",
    label: { x: 455, y: 40 },
  },
  {
    id: "shop",
    title: "Лавка Фокси",
    hint: "Монетки на сердца и стикеры",
    art: "/world/castle/shop.png",
    polygon:
      "575,122 608,98 642,105 675,140 688,185 680,235 650,265 605,275 575,255 568,210 570,155",
    label: { x: 625, y: 90 },
  },
  {
    id: "glory",
    title: "Башня Славы",
    hint: "Лига и рейтинг недели",
    art: "/world/castle/glory.png",
    polygon:
      "720,28 745,32 770,55 790,95 815,145 808,190 785,220 760,235 700,235 670,220 648,190 642,145 665,95 690,55 705,35",
    label: { x: 730, y: 20 },
  },
  {
    id: "lexicon",
    title: "Сокровищница слов",
    hint: "Всё, что уже звучало на уроке",
    art: "/world/castle/lexicon.png",
    polygon:
      "835,118 880,102 930,112 962,150 972,205 952,268 905,295 855,285 822,245 815,185 820,145",
    label: { x: 895, y: 95 },
  },
  {
    id: "stickers",
    title: "Башня стикеров",
    hint: "Альбом наклеек",
    art: "/world/castle/stickers.png",
    polygon:
      "1005,55 1035,42 1065,48 1090,70 1095,100 1088,155 1080,210 1068,255 1045,280 1020,288 1000,275 990,240 988,180 992,120 998,80",
    label: { x: 1040, y: 35 },
  },
  {
    id: "yard",
    title: "Двор тренировки",
    hint: "Повторить слова без нового урока",
    art: "/world/castle/yard.png",
    // wooden fence paddock — hug inner rails, clear of pines/path (map-v3)
    polygon: "1070,298 1105,278 1148,280 1172,315 1175,355 1150,390 1110,400 1075,385 1060,340",
    label: { x: 1120, y: 268 },
  },
  {
    id: "quests",
    title: "Беседка поручений",
    hint: "Задания на сегодня",
    art: "/world/castle/quests.png",
    polygon:
      "580,545 615,565 645,595 640,660 635,715 580,730 525,715 520,660 515,595 545,565",
    label: { x: 580, y: 530 },
  },
  {
    id: "nest",
    title: "Гнездо Foxy",
    hint: "Твой уровень, сердца, серия",
    art: "/world/castle/nest.png",
    polygon:
      "210,375 270,385 325,425 350,480 348,545 310,590 255,605 200,575 170,515 172,450 190,400",
    label: { x: 255, y: 365 },
  },
];

export const TIER_RU: Record<string, string> = {
  gold: "Золотая лига",
  silver: "Серебряная лига",
  bronze: "Бронзовая лига",
};
