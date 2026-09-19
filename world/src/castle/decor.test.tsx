import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  BANNER_HEX,
  DECOR_SLOTS,
  decorFilter,
  decorImgFilter,
  decorShadow,
  defaultSlotFor,
  slotsForAnchor,
} from "./decor";
import { Emblem } from "./emblems";

describe("decor slots", () => {
  it("десять слотов: четыре у ворот и по одному на остальные якоря", () => {
    expect(Object.keys(DECOR_SLOTS).sort()).toEqual(
      [
        "bridge",
        "courtyard",
        "gate-far-left",
        "gate-far-right",
        "gate-left",
        "gate-right",
        "meadow",
        "roofs",
        "stream",
        "walls",
      ].sort(),
    );
    for (const slot of Object.values(DECOR_SLOTS)) {
      expect(slot.x).toBeGreaterThan(0);
      expect(slot.x).toBeLessThan(1);
      expect(slot.y).toBeGreaterThan(0);
      expect(slot.y).toBeLessThan(1);
    }
  });

  it("слоты у ворот повторяют прежние точки со смещениями — предметы не переехали", () => {
    expect(DECOR_SLOTS["gate-left"]).toMatchObject({ x: 0.412, y: 0.635 });
    expect(DECOR_SLOTS["gate-right"]).toMatchObject({ x: 0.502, y: 0.635 });
    expect(DECOR_SLOTS["gate-far-left"]).toMatchObject({ x: 0.397, y: 0.65 });
    expect(DECOR_SLOTS["gate-far-right"]).toMatchObject({ x: 0.512, y: 0.655 });
  });

  it("slotsForAnchor: у ворот четыре слота, у остальных якорей один одноимённый", () => {
    expect(slotsForAnchor("gate").sort()).toEqual(
      ["gate-left", "gate-right", "gate-far-left", "gate-far-right"].sort(),
    );
    expect(slotsForAnchor("bridge")).toEqual(["bridge"]);
    expect(slotsForAnchor("meadow")).toEqual(["meadow"]);
    expect(slotsForAnchor("unknown")).toEqual([]);
  });

  it("defaultSlotFor: калибровка у ворот, иначе одноимённый якорю слот", () => {
    expect(defaultSlotFor("decor-gate-lantern", "gate")).toBe("gate-left");
    expect(defaultSlotFor("decor-gate-fox-statue", "gate")).toBe("gate-right");
    expect(defaultSlotFor("decor-gate-pots", "gate")).toBe("gate-far-left");
    expect(defaultSlotFor("decor-gate-pumpkins", "gate")).toBe("gate-far-right");
    expect(defaultSlotFor("decor-bridge-garland", "bridge")).toBe("bridge");
    expect(defaultSlotFor("decor-wall-bell", "walls")).toBe("walls");
    expect(defaultSlotFor("decor-unknown", "nowhere")).toBeNull();
  });

  it("окклюзия задана только существующими зданиями", () => {
    const known = new Set(["school", "shop", "glory", "lexicon", "stickers", "nest", "quests", "yard",
      "tower-sp1", "tower-sp2", "tower-sp3", "tower-sp4"]);
    for (const slot of Object.values(DECOR_SLOTS)) {
      for (const id of slot.occludedBy ?? []) expect(known.has(id)).toBe(true);
    }
  });
});

describe("decor look", () => {
  it("подкраска зависит от времени суток, день — без фильтра", () => {
    expect(decorFilter("day")).toBe("none");
    expect(decorFilter("night")).toContain("brightness");
    expect(decorFilter("dawn")).not.toBe(decorFilter("dusk"));
    expect(decorFilter("unknown")).toBe("none");
  });

  it("тень живая: днём короткая, на рассвете и закате направленная в разные стороны", () => {
    expect(decorShadow("day")).toContain("drop-shadow(0 ");
    expect(decorShadow("dawn")).toContain("drop-shadow(-");
    expect(decorShadow("dusk")).not.toBe(decorShadow("dawn"));
    expect(decorShadow("night")).toContain("drop-shadow");
  });

  it("итоговый фильтр собирает подкраску, сезонный тон и тень", () => {
    expect(decorImgFilter("day", "summer")).toBe("saturate(1.06) drop-shadow(0 3px 3px rgb(20 10 30 / 0.35))");
    expect(decorImgFilter("night", "winter")).toContain("brightness(0.62)");
    expect(decorImgFilter("night", "winter")).toContain("brightness(1.04)");
    expect(decorImgFilter("day", "unknown")).toBe(decorShadow("day"));
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
