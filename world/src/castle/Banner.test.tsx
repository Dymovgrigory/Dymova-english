import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BANNER_HEX } from "./Banner";
import { Emblem } from "./emblems";

describe("Banner", () => {
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
