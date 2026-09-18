/**
 * Сезонные облики замка: у каждого сезона своя диорама, своя карта зон и свои маски
 * (здания на перерисованной картинке могут сместиться на пару пикселей — см. season-masks).
 * Неизвестный сезон откатывается на базовую сцену, чтобы интерфейс не ломался.
 */
import hotspotsSpring from "./castle-hotspots-spring.json";
import hotspotsSummer from "./castle-hotspots-summer.json";
import hotspotsAutumn from "./castle-hotspots-autumn.json";
import hotspotsWinter from "./castle-hotspots-winter.json";
import { buildSpots, SPOTS, type Spot } from "./buildings";

export type SeasonId = "spring" | "summer" | "autumn" | "winter";

export const SEASON_IDS: SeasonId[] = ["spring", "summer", "autumn", "winter"];

const SEASON_SPOTS: Record<SeasonId, Spot[]> = {
  spring: buildSpots(hotspotsSpring, "masks/spring"),
  summer: buildSpots(hotspotsSummer, "masks/summer"),
  autumn: buildSpots(hotspotsAutumn, "masks/autumn"),
  winter: buildSpots(hotspotsWinter, "masks/winter"),
};

export function isSeason(value: string): value is SeasonId {
  return (SEASON_IDS as string[]).includes(value);
}

/** Здания и маски сезона; базовая раскладка — если сезон неизвестен. */
export function spotsForSeason(season: string): Spot[] {
  return isSeason(season) ? SEASON_SPOTS[season] : SPOTS;
}

/** Картинка сцены сезона; базовая диорама — если сезон неизвестен. */
export function sceneForSeason(season: string): string {
  return isSeason(season) ? `/content/castle/seasons/${season}.webp` : "/content/castle/castle-diorama.webp";
}

/** Карта зон кликов сезона; базовая — если сезон неизвестен. */
export function hotspotsForSeason(season: string): string {
  return isSeason(season) ? `/content/castle/castle-hotspots-${season}.png` : "/content/castle/castle-hotspots.png";
}
