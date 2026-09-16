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
  /** Percent of the map image box. */
  box: { left: number; top: number; width: number; height: number };
};

export const CASTLE_MAP = "/world/castle/map.png";
export const CASTLE_MAP_DUSK = "/world/castle/map-dusk.png";

export function isCastleDusk(hour = new Date().getHours()): boolean {
  return hour >= 18 || hour < 6;
}

/** Кликабельная карта всегда дневная: хитбоксы привязаны к map.png. Вечер — фильтр. */
export function castleMapSrc(): string {
  return CASTLE_MAP;
}

/** Хитбоксы под Meshy map v2 (изометрия 16:9, floating island). */
export const BUILDINGS: Building[] = [
  {
    id: "school",
    title: "Школа Foxy",
    hint: "Уроки 1 класса",
    art: "/world/castle/school.png",
    box: { left: 27, top: 14, width: 12, height: 30 },
  },
  {
    id: "shop",
    title: "Лавка Фокси",
    hint: "Монетки на сердца и стикеры",
    art: "/world/castle/shop.png",
    box: { left: 35, top: 32, width: 11, height: 16 },
  },
  {
    id: "glory",
    title: "Башня Славы",
    hint: "Лига и рейтинг недели",
    art: "/world/castle/glory.png",
    box: { left: 44, top: 18, width: 12, height: 22 },
  },
  {
    id: "lexicon",
    title: "Сокровищница слов",
    hint: "Всё, что уже звучало на уроке",
    art: "/world/castle/lexicon.png",
    box: { left: 54, top: 24, width: 13, height: 28 },
  },
  {
    id: "stickers",
    title: "Башня стикеров",
    hint: "Альбом наклеек",
    art: "/world/castle/stickers.png",
    box: { left: 62, top: 36, width: 10, height: 16 },
  },
  {
    id: "yard",
    title: "Двор тренировки",
    hint: "Повторить слова без нового урока",
    art: "/world/castle/yard.png",
    box: { left: 18, top: 60, width: 16, height: 22 },
  },
  {
    id: "nest",
    title: "Гнездо Foxy",
    hint: "Твой уровень, сердца, серия",
    art: "/world/castle/nest.png",
    box: { left: 70, top: 50, width: 16, height: 22 },
  },
  {
    id: "quests",
    title: "Беседка поручений",
    hint: "Задания на сегодня",
    art: "/world/castle/quests.png",
    box: { left: 40, top: 55, width: 12, height: 16 },
  },
];

export const TIER_RU: Record<string, string> = {
  gold: "Золотая лига",
  silver: "Серебряная лига",
  bronze: "Бронзовая лига",
};
