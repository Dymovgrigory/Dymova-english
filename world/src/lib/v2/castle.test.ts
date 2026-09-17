import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { castleApi } from "./castle";

const view = {
  appearance: { season: null, time_of_day: null, weather: null, banner_color: "plum", banner_emblem: "fox" },
  catalog: [],
  owned: [],
  titles: [],
  coins: 0,
};

describe("castleApi", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(view), { status: 200 })));
  });
  afterEach(() => vi.unstubAllGlobals());

  it("запрашивает состояние замка", async () => {
    await castleApi.get();
    const [url] = (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(String(url)).toContain("/api/v2/castle");
  });

  it("покупает вещь по id", async () => {
    await castleApi.buy("time-night");
    const [url, init] = (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(String(url)).toContain("/api/v2/castle/buy");
    expect(JSON.parse(String((init as RequestInit).body))).toEqual({ item_id: "time-night" });
  });

  it("применяет только переданные поля", async () => {
    await castleApi.apply({ time_of_day: "night" });
    const [, init] = (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(JSON.parse(String((init as RequestInit).body))).toEqual({ time_of_day: "night" });
  });
});
