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
  /** Tooltip anchor in the same coordinate space. */
  label: { x: number; y: number };
};

/** map.png is 1376×768 — polygons share this space with the SVG <image>. */
export const MAP_VIEWBOX = { width: 1376, height: 768 } as const;

export const CASTLE_MAP = "/world/castle/map.png";
export const CASTLE_MAP_DUSK = "/world/castle/map-dusk.png";

export function isCastleDusk(hour = new Date().getHours()): boolean {
  return hour >= 18 || hour < 6;
}

/** Кликабельная карта всегда дневная: хитбоксы привязаны к map.png. Вечер — фильтр. */
export function castleMapSrc(): string {
  return CASTLE_MAP;
}

/**
 * Только открытые здания. Остальная застройка на карте — декор без клика.
 * Полигоны плотно обводят силуэт (калибровка по сетке 10px на map v3).
 */
export const BUILDINGS: Building[] = [
  {
    id: "school",
    title: "Школа Foxy",
    hint: "Уроки 1 класса",
    art: "/world/castle/school.png",
    polygon:
      "480,48 535,105 525,115 525,195 555,220 575,255 570,305 530,340 430,340 340,335 325,300 325,260 375,225 435,195 435,115 425,105",
    label: { x: 480, y: 80 },
  },
  {
    id: "shop",
    title: "Лавка Фокси",
    hint: "Монетки на сердца и стикеры",
    art: "/world/castle/shop.png",
    // pink shop + striped awning (sign ~615,108; awning median ~630,200)
    polygon:
      "575,122 608,98 642,105 675,140 688,185 680,235 650,265 605,275 575,255 568,210 570,155",
    label: { x: 620, y: 120 },
  },
  {
    id: "glory",
    title: "Башня Славы",
    hint: "Лига и рейтинг недели",
    art: "/world/castle/glory.png",
    polygon:
      "720,28 745,32 770,55 790,95 815,145 808,190 785,220 760,235 700,235 670,220 648,190 642,145 665,95 690,55 705,35",
    label: { x: 725, y: 55 },
  },
  {
    id: "lexicon",
    title: "Сокровищница слов",
    hint: "Всё, что уже звучало на уроке",
    art: "/world/castle/lexicon.png",
    polygon:
      "835,118 880,102 930,112 962,150 972,205 952,268 905,295 855,285 822,245 815,185 820,145",
    label: { x: 895, y: 145 },
  },
  {
    id: "stickers",
    title: "Башня стикеров",
    hint: "Альбом наклеек",
    art: "/world/castle/stickers.png",
    // narrow cylinder ~1010–1075, wider battlements at top
    polygon:
      "1005,55 1035,42 1065,48 1090,70 1095,100 1088,155 1080,210 1068,255 1045,280 1020,288 1000,275 990,240 988,180 992,120 998,80",
    label: { x: 1035, y: 90 },
  },
  {
    id: "yard",
    title: "Двор тренировки",
    hint: "Повторить слова без нового урока",
    art: "/world/castle/yard.png",
    // wooden fence paddock — tight to fence posts
    polygon:
      "1095,290 1145,305 1185,340 1205,385 1185,430 1145,455 1100,460 1060,435 1040,395 1050,345 1075,305",
    label: { x: 1120, y: 360 },
  },
  {
    id: "quests",
    title: "Беседка поручений",
    hint: "Задания на сегодня",
    art: "/world/castle/quests.png",
    polygon:
      "580,545 615,565 645,595 640,660 635,715 580,730 525,715 520,660 515,595 545,565",
    label: { x: 580, y: 560 },
  },
  {
    id: "nest",
    title: "Гнездо Foxy",
    hint: "Твой уровень, сердца, серия",
    art: "/world/castle/nest.png",
    // glass dome + entrance steps — crystal ~185–300, frame to ~355
    polygon:
      "210,375 270,385 325,425 350,480 348,545 310,590 255,605 200,575 170,515 172,450 190,400",
    label: { x: 255, y: 430 },
  },
];

export const TIER_RU: Record<string, string> = {
  gold: "Золотая лига",
  silver: "Серебряная лига",
  bronze: "Бронзовая лига",
};
