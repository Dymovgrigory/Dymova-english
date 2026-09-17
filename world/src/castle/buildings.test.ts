import { describe, expect, it } from "vitest";
import { CASTLE_SCENE, SPOTS, spotAt, type HotspotMap } from "./buildings";

function mapWith(width: number, height: number, fill: (x: number, y: number) => number): HotspotMap {
  const labels = new Uint8Array(width * height);
  for (let y = 0; y < height; y += 1) for (let x = 0; x < width; x += 1) labels[y * width + x] = fill(x, y);
  return { width, height, labels };
}

describe("castle diorama", () => {
  it("renders one fused diorama instead of stacked sprites", () => {
    expect(CASTLE_SCENE).toContain("castle-diorama");
  });

  it("has twelve spots with unique map indexes and areas inside the scene", () => {
    expect(SPOTS).toHaveLength(12);
    expect(SPOTS.filter((s) => s.kind === "tower")).toHaveLength(4);
    expect(new Set(SPOTS.map((s) => s.index)).size).toBe(12);
    for (const s of SPOTS) {
      expect(s.area.left).toBeGreaterThanOrEqual(0);
      expect(s.area.top).toBeGreaterThanOrEqual(0);
      expect(s.area.left + s.area.width).toBeLessThanOrEqual(100.01);
      expect(s.area.top + s.area.height).toBeLessThanOrEqual(100.01);
    }
  });

  it("finds the building under a point by its silhouette, not its box", () => {
    const school = SPOTS.find((s) => s.id === "school")!;
    const map = mapWith(8, 4, (x, y) => (x >= 4 && y >= 2 ? school.index : 0));
    expect(spotAt(map, 0.7, 0.8)).toBe("school");
    expect(spotAt(map, 0.2, 0.2)).toBeNull();
  });

  it("clamps points on the scene edge and ignores unknown indexes", () => {
    const map = mapWith(4, 4, () => 250);
    expect(spotAt(map, 1, 1)).toBeNull();
    const nest = SPOTS.find((s) => s.id === "nest")!;
    expect(spotAt(mapWith(4, 4, () => nest.index), 1, 1)).toBe("nest");
    expect(spotAt(mapWith(4, 4, () => nest.index), -0.1, 0)).toBeNull();
  });
});
