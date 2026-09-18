import { describe, expect, it } from "vitest";

import { formatWeekRange, medalForRank } from "./weeks";

describe("formatWeekRange", () => {
  it("форматирует неделю внутри одного месяца", () => {
    expect(formatWeekRange("2026-09-07")).toBe("7–13 сен");
  });

  it("показывает оба месяца на стыке", () => {
    expect(formatWeekRange("2026-09-28")).toBe("28 сен – 4 окт");
  });

  it("невалидная дата возвращается как есть", () => {
    expect(formatWeekRange("непонятно")).toBe("непонятно");
  });
});

describe("medalForRank", () => {
  it("даёт медали за 1–3 место", () => {
    expect(medalForRank(1)).toBe("🥇");
    expect(medalForRank(2)).toBe("🥈");
    expect(medalForRank(3)).toBe("🥉");
  });

  it("ниже третьего места медали нет", () => {
    expect(medalForRank(4)).toBeNull();
    expect(medalForRank(10)).toBeNull();
  });
});
