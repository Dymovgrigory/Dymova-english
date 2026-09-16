import { describe, expect, it } from "vitest";

import { NODE_LABELS, nodeOffset } from "./pathLayout";

describe("nodeOffset", () => {
  it("starts in the centre and snakes within the amplitude", () => {
    expect(nodeOffset(0, 70)).toBe(0);
    const offsets = Array.from({ length: 24 }, (_, i) => nodeOffset(i, 70));
    expect(Math.max(...offsets)).toBe(70);
    expect(Math.min(...offsets)).toBe(-70);
    expect(offsets.every((x) => Math.abs(x) <= 70)).toBe(true);
  });

  it("changes gradually between neighbours", () => {
    for (let i = 1; i < 16; i += 1) {
      expect(Math.abs(nodeOffset(i, 70) - nodeOffset(i - 1, 70))).toBeLessThanOrEqual(50);
    }
  });
});

describe("NODE_LABELS", () => {
  it("names every node kind in Russian", () => {
    expect(NODE_LABELS.words).toBe("Слова");
    expect(NODE_LABELS.module_test).toBe("Контрольная");
    expect(Object.keys(NODE_LABELS)).toHaveLength(6);
  });
});
