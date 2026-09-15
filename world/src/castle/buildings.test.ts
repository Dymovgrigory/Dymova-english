import { describe, expect, it } from "vitest";
import { CASTLE_MAP, CASTLE_MAP_DUSK, castleMapSrc, isCastleDusk } from "./buildings";

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
});
