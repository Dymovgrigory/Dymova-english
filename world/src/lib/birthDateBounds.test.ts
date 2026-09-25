import { describe, expect, it } from "vitest";

import { birthDateBounds } from "./birthDateBounds";

describe("birthDateBounds", () => {
  it("возраст 3–17 на фиксированную дату", () => {
    const bounds = birthDateBounds(new Date(2026, 8, 25)); // 25.09.2026
    expect(bounds.min).toBe("2009-09-25");
    expect(bounds.max).toBe("2023-09-25");
  });
});
