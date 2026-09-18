import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BANNER_HEX, DECOR_POINTS, decorFilter } from "./decor";
import { Emblem } from "./emblems";

describe("decor", () => {
  it("все семь точек заданы в пределах сцены", () => {
    expect(Object.keys(DECOR_POINTS).sort()).toEqual(
      ["bridge", "courtyard", "gate", "meadow", "roofs", "stream", "walls"].sort(),
    );
    for (const point of Object.values(DECOR_POINTS)) {
      expect(point.x).toBeGreaterThan(0);
      expect(point.x).toBeLessThan(1);
      expect(point.y).toBeGreaterThan(0);
      expect(point.y).toBeLessThan(1);
    }
  });

  it("подкраска зависит от времени суток, день — без фильтра", () => {
    expect(decorFilter("day")).toBe("none");
    expect(decorFilter("night")).toContain("brightness");
    expect(decorFilter("dawn")).not.toBe(decorFilter("dusk"));
    expect(decorFilter("unknown")).toBe("none");
  });

  it("у всех цветов знамени из каталога есть hex", () => {
    for (const color of ["plum", "emerald", "gold", "azure", "rose"]) {
      expect(BANNER_HEX[color]).toMatch(/^#[0-9a-f]{6}$/);
    }
  });
});

describe("Emblem", () => {
  it("у каждой ветки своя эмблема, неизвестная — лиса", () => {
    const tracks = ["lexicon", "yard", "nest", "glory", "stickers"];
    const svgs = new Map(
      tracks.map((track) => [track, render(<Emblem id={track} />).container.innerHTML]),
    );
    expect(new Set(svgs.values()).size).toBe(tracks.length);
    expect(render(<Emblem id="fox" />).container.innerHTML).toContain("<svg");
    expect(render(<Emblem id="unknown" />).container.innerHTML).toBe(render(<Emblem id="fox" />).container.innerHTML);
  });
});
