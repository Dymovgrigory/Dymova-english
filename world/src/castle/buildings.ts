/**
 * Замок Фоксинбург — одна цельная диорама `castle-diorama.webp` (flare сплавил спрайты зданий
 * на площадках плашки, см. `world-pipeline/castle_compose.py`).
 *
 * Здания не клеятся поверх картинки: клик и hover определяются по карте зон `castle-hotspots.png`
 * (каждый пиксель знает своё здание), подсветка — вырез той же картинки по маске `masks/{id}.png`.
 * Области и индексы ниже приходят из `castle-hotspots.json` — после перегенерации ничего не правится руками.
 */
import hotspots from "./castle-hotspots.json";

export type SpotId =
  | "school"
  | "shop"
  | "glory"
  | "lexicon"
  | "stickers"
  | "nest"
  | "quests"
  | "yard"
  | "tower-sp1"
  | "tower-sp2"
  | "tower-sp3"
  | "tower-sp4";

export type SpotKind = "building" | "tower";

/** Прямоугольник вокруг видимого силуэта здания, % от сцены. */
export type SpotArea = { left: number; top: number; width: number; height: number };

export type Spot = {
  id: SpotId;
  kind: SpotKind;
  title: string;
  short: string;
  hint: string;
  /** Иконка здания для ленты локаций. */
  art: string;
  room?: string;
  bookId?: string;
  /** Номер здания в карте зон. */
  index: number;
  area: SpotArea;
  /** Верх плотной части силуэта, % от высоты области — сюда садится подпись. */
  labelTop: number;
  mask: string;
};

export const CASTLE_SCENE = "/content/castle/castle-diorama.webp";
export const CASTLE_HOTSPOTS = "/content/castle/castle-hotspots.png";
export const CASTLE_LABEL_STEP = hotspots.labelStep;

type SpotInfo = Omit<Spot, "index" | "area" | "labelTop" | "mask">;

const INFO: SpotInfo[] = [
  { id: "tower-sp1", kind: "tower", title: "Башня 1 класса", short: "1 кл.", hint: "Spotlight 1 · Башня плюща", art: "/content/castle/tower-sp1.webp", room: "/content/castle/room-tower-sp1.webp", bookId: "sp1" },
  { id: "tower-sp2", kind: "tower", title: "Башня 2 класса", short: "2 кл.", hint: "Spotlight 2 · Башня мастеров", art: "/content/castle/tower-sp2.webp", room: "/content/castle/room-tower-sp2.webp", bookId: "sp2" },
  { id: "tower-sp3", kind: "tower", title: "Башня 3 класса", short: "3 кл.", hint: "Spotlight 3 · Башня звездочётов", art: "/content/castle/tower-sp3.webp", room: "/content/castle/room-tower-sp3.webp", bookId: "sp3" },
  { id: "tower-sp4", kind: "tower", title: "Башня 4 класса", short: "4 кл.", hint: "Spotlight 4 · Башня путешественников", art: "/content/castle/tower-sp4.webp", room: "/content/castle/room-tower-sp4.webp", bookId: "sp4" },
  { id: "school", kind: "building", title: "Школа Foxy", short: "Школа", hint: "К пути обучения", art: "/content/castle/school.webp", room: "/content/castle/room-school.webp" },
  { id: "shop", kind: "building", title: "Лавка Фокси", short: "Лавка", hint: "Монеты за уроки → сердца и стикеры", art: "/content/castle/shop.webp", room: "/content/castle/room-shop.webp" },
  { id: "glory", kind: "building", title: "Башня Славы", short: "Слава", hint: "Лига и рейтинг недели", art: "/content/castle/glory.webp", room: "/content/castle/room-glory.webp" },
  { id: "lexicon", kind: "building", title: "Сокровищница слов", short: "Слова", hint: "Слова из твоих уроков", art: "/content/castle/lexicon.webp", room: "/content/castle/room-lexicon.webp" },
  { id: "stickers", kind: "building", title: "Башня стикеров", short: "Стикеры", hint: "Альбом наклеек", art: "/content/castle/stickers.webp", room: "/content/castle/room-stickers.webp" },
  { id: "nest", kind: "building", title: "Гнездо Foxy", short: "Гнездо", hint: "Уровень, серия, монеты", art: "/content/castle/nest.webp", room: "/content/castle/room-nest.webp" },
  { id: "quests", kind: "building", title: "Беседка поручений", short: "Задания", hint: "Задания на сегодня", art: "/content/castle/quests.webp", room: "/content/castle/room-quests.webp" },
  { id: "yard", kind: "building", title: "Двор тренировки", short: "Двор", hint: "Повторить слова без нового урока", art: "/content/castle/yard.webp", room: "/content/castle/room-yard.webp" },
];

/** Порядок = лента локаций; на сцене здания рисуются сзади вперёд по `index`. */
export const SPOTS: Spot[] = INFO.map((info) => {
  const zone = hotspots.spots.find((s) => s.id === info.id);
  if (!zone) throw new Error(`castle-hotspots.json: нет зоны для ${info.id}`);
  return { ...info, index: zone.index, area: zone.area, labelTop: zone.labelTop, mask: `/content/castle/masks/${info.id}.png` };
});

/** Замок на картинке (доли 0..1): все здания с небольшим запасом — его сцена вписывает в экран целиком. */
export const CASTLE_FOCUS = (() => {
  const left = Math.min(...SPOTS.map((s) => s.area.left)) - 2;
  const top = Math.min(...SPOTS.map((s) => s.area.top)) - 3;
  const right = Math.max(...SPOTS.map((s) => s.area.left + s.area.width)) + 2;
  const bottom = Math.max(...SPOTS.map((s) => s.area.top + s.area.height)) + 4;
  return { left: left / 100, top: top / 100, width: (right - left) / 100, height: (bottom - top) / 100 };
})();

export const CASTLE_SCENE_SIZE = { width: 1536, height: 864 } as const;

export type BuildingId = SpotId;

/** Карта зон: номер здания на каждый пиксель (0 — пусто), строками сверху вниз. */
export type HotspotMap = { width: number; height: number; labels: ArrayLike<number> };

/** Здание под точкой сцены (x, y в долях 0..1) — по силуэту, а не по прямоугольнику. */
export function spotAt(map: HotspotMap, x: number, y: number): SpotId | null {
  if (x < 0 || y < 0 || x > 1 || y > 1) return null;
  const column = Math.min(map.width - 1, Math.floor(x * map.width));
  const row = Math.min(map.height - 1, Math.floor(y * map.height));
  const index = map.labels[row * map.width + column];
  return SPOTS.find((s) => s.index === index)?.id ?? null;
}

export const TIER_RU: Record<string, string> = {
  gold: "Золотая лига",
  silver: "Серебряная лига",
  bronze: "Бронзовая лига",
};
