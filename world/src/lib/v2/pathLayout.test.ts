import { describe, expect, it } from "vitest";

import { NODE_LABELS } from "./pathLayout";

describe("NODE_LABELS", () => {
  it("names every node kind in Russian", () => {
    expect(NODE_LABELS.words).toBe("Слова");
    expect(NODE_LABELS.module_test).toBe("Контрольная");
    expect(Object.keys(NODE_LABELS)).toHaveLength(6);
  });
});
