import { describe, expect, it } from "vitest";
import { effectiveAppearance, lightLayer, seasonByDate, timeByClock } from "./appearance";

describe("облик замка", () => {
  it("сезон по календарю, если ничего не куплено", () => {
    expect(seasonByDate(new Date("2026-01-15T12:00:00"))).toBe("winter");
    expect(seasonByDate(new Date("2026-07-15T12:00:00"))).toBe("summer");
  });

  it("время суток по часам ребёнка", () => {
    expect(timeByClock(new Date("2026-09-17T06:30:00"))).toBe("dawn");
    expect(timeByClock(new Date("2026-09-17T13:00:00"))).toBe("day");
    expect(timeByClock(new Date("2026-09-17T19:30:00"))).toBe("dusk");
    expect(timeByClock(new Date("2026-09-17T23:30:00"))).toBe("night");
  });

  it("выбранное побеждает автоматическое", () => {
    const result = effectiveAppearance(
      { season: "winter", time_of_day: "night", weather: "snow", banner_color: "gold", banner_emblem: "fox" },
      new Date("2026-07-15T13:00:00"),
    );
    expect(result).toEqual({ season: "winter", time: "night", weather: "snow" });
  });

  it("пустой выбор подставляет календарь и часы", () => {
    const result = effectiveAppearance(
      { season: null, time_of_day: null, weather: null, banner_color: "plum", banner_emblem: "fox" },
      new Date("2026-07-15T13:00:00"),
    );
    expect(result).toEqual({ season: "summer", time: "day", weather: null });
  });

  it("день не затемняет сцену, ночь затемняет", () => {
    expect(lightLayer("day").background).toContain("transparent");
    expect(lightLayer("night").background).not.toContain("transparent");
  });
});
