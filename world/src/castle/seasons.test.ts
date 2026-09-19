import { describe, expect, it } from "vitest";

import { SPOTS } from "./buildings";
import { hotspotsForSeason, isSeason, sceneForSeason, spotsForSeason } from "./seasons";

describe("seasons", () => {
  it("у каждого сезона свои здания с сезонными масками", () => {
    const winter = spotsForSeason("winter");
    expect(winter.map((s) => s.id)).toEqual(SPOTS.map((s) => s.id));
    expect(winter[0].mask).toContain("/content/castle/masks/winter/");
  });

  it("неизвестный сезон откатывается на базовую сцену", () => {
    expect(spotsForSeason("mars")).toBe(SPOTS);
    expect(sceneForSeason("mars")).toBe("/content/castle/castle-diorama.webp");
    expect(hotspotsForSeason("mars")).toBe("/content/castle/castle-hotspots.png");
  });

  it("сезонные файлы адресуются по имени сезона", () => {
    expect(sceneForSeason("autumn")).toBe("/content/castle/seasons/autumn.webp");
    expect(hotspotsForSeason("autumn")).toBe("/content/castle/castle-hotspots-autumn.png");
    expect(isSeason("spring")).toBe(true);
    expect(isSeason("")).toBe(false);
  });

  it("запечённый набор заменяет сцену независимо от сезона, null — сезонная", () => {
    expect(sceneForSeason("autumn", "garland")).toBe("/content/castle/sets/garland.webp");
    expect(sceneForSeason("mars", "pumpkins")).toBe("/content/castle/sets/pumpkins.webp");
    expect(sceneForSeason("autumn", null)).toBe("/content/castle/seasons/autumn.webp");
    expect(sceneForSeason("autumn", "")).toBe("/content/castle/seasons/autumn.webp");
  });
});
