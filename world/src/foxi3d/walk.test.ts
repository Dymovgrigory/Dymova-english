import { describe, expect, it } from "vitest";

import { WALK_MAX_MS, WALK_MIN_MS, walkDurationMs, walkFacing, walkStartTransform } from "./walk";

describe("walkDurationMs", () => {
  it("возвращает 0 для нулевого/микроскопического смещения", () => {
    expect(walkDurationMs({ dx: 0, dy: 0 })).toBe(0);
    expect(walkDurationMs({ dx: 0.4, dy: -0.4 })).toBe(0);
  });

  it("не ниже минимума на короткой дистанции", () => {
    expect(walkDurationMs({ dx: 30, dy: 0 })).toBe(WALK_MIN_MS);
  });

  it("растёт пропорционально расстоянию", () => {
    const near = walkDurationMs({ dx: 220, dy: 0 });
    const far = walkDurationMs({ dx: 440, dy: 0 });
    expect(near).toBe(1000);
    expect(far).toBe(2000);
    expect(far).toBeGreaterThan(near);
  });

  it("учитывает диагональ (гипотенуза)", () => {
    expect(walkDurationMs({ dx: 300, dy: 400 })).toBeGreaterThan(walkDurationMs({ dx: 400, dy: 0 }));
  });

  it("не выше максимума на длинной дистанции", () => {
    expect(walkDurationMs({ dx: 5000, dy: 8000 })).toBe(WALK_MAX_MS);
  });

  it("устойчива к NaN/Infinity", () => {
    expect(walkDurationMs({ dx: Number.NaN, dy: 10 })).toBe(0);
    expect(walkDurationMs({ dx: Number.POSITIVE_INFINITY, dy: 0 })).toBe(0);
  });
});

describe("walkFacing", () => {
  it("лис смотрит по направлению движения (к точке 0,0)", () => {
    expect(walkFacing({ dx: 150, dy: 0 })).toBe(-1); // старт справа → идёт влево
    expect(walkFacing({ dx: -150, dy: 0 })).toBe(1); // старт слева → идёт вправо
  });

  it("при вертикальном переходе смотрит вправо", () => {
    expect(walkFacing({ dx: 0, dy: -300 })).toBe(1);
  });
});

describe("walkStartTransform", () => {
  it("округляет и собирает translate", () => {
    expect(walkStartTransform({ dx: 120.6, dy: -40.2 })).toBe("translate(121px, -40px)");
  });
});
