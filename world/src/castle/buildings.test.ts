import { describe, expect, it } from "vitest";
import { BUILDINGS, CASTLE_MAP, CASTLE_MAP_DUSK, MAP_VIEWBOX, castleMapSrc, isCastleDusk } from "./buildings";

describe("castle dusk", () => {
  it("keeps the clickable day map so building hitboxes stay true", () => {
    expect(castleMapSrc()).toBe(CASTLE_MAP);
    expect(CASTLE_MAP_DUSK).toContain("map-dusk");
  });

  it("marks evening hours as dusk", () => {
    expect(isCastleDusk(14)).toBe(false);
    expect(isCastleDusk(20)).toBe(true);
    expect(isCastleDusk(5)).toBe(true);
  });

  it("defines polygon hotspots inside the map viewBox", () => {
    for (const b of BUILDINGS) {
      expect(b.polygon.split(/\s+/).length).toBeGreaterThanOrEqual(3);
      for (const pair of b.polygon.split(/\s+/)) {
        const [x, y] = pair.split(",").map(Number);
        expect(x).toBeGreaterThanOrEqual(0);
        expect(y).toBeGreaterThanOrEqual(0);
        expect(x).toBeLessThanOrEqual(MAP_VIEWBOX.width);
        expect(y).toBeLessThanOrEqual(MAP_VIEWBOX.height);
      }
      expect(b.label.x).toBeLessThanOrEqual(MAP_VIEWBOX.width);
      expect(b.label.y).toBeLessThanOrEqual(MAP_VIEWBOX.height);
    }
  });
});
