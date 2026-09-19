import { afterEach, describe, expect, it, vi } from "vitest";

import { detectMessenger, messengerLogin } from "./messenger";

declare const globalThis: Record<string, unknown>;

afterEach(() => {
  delete globalThis.window;
  vi.unstubAllGlobals();
});

describe("detectMessenger", () => {
  it("нет window — null (SSR)", () => {
    expect(detectMessenger()).toBeNull();
  });

  it("Telegram WebApp с непустой initData", () => {
    globalThis.window = { Telegram: { WebApp: { initData: "tg-data" } } };
    expect(detectMessenger()).toEqual({ provider: "telegram", initData: "tg-data" });
  });

  it("пустая initData Telegram — не мессенджер", () => {
    globalThis.window = { Telegram: { WebApp: { initData: "" } } };
    expect(detectMessenger()).toBeNull();
  });

  it("MAX WebApp с initData", () => {
    globalThis.window = { WebApp: { initData: "max-data", platform: "web" } };
    expect(detectMessenger()).toEqual({ provider: "max", initData: "max-data" });
  });

  it("Telegram приоритетнее MAX", () => {
    globalThis.window = {
      Telegram: { WebApp: { initData: "tg-data" } },
      WebApp: { initData: "max-data" },
    };
    expect(detectMessenger()?.provider).toBe("telegram");
  });

  it("обычный браузер — null", () => {
    globalThis.window = {};
    expect(detectMessenger()).toBeNull();
  });
});

describe("messengerLogin", () => {
  it("шлёт init_data на /api/world/auth/telegram и возвращает токен", async () => {
    const calls: { url: string; body?: unknown }[] = [];
    vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ url: String(input), body: init?.body ? JSON.parse(String(init.body)) : undefined });
      return { ok: true, json: async () => ({ token: "wses.x.y", external_key: "telegram:1", display_name: "Маша", id: 1, is_registered: false }) };
    });
    const res = await messengerLogin("telegram", "tg-data");
    expect(calls[0].url).toContain("/api/world/auth/telegram");
    expect(calls[0].body).toEqual({ init_data: "tg-data" });
    expect(res.token).toBe("wses.x.y");
    expect(res.is_registered).toBe(false);
  });

  it("503 provider_not_configured — ApiError с кодом", async () => {
    vi.stubGlobal("fetch", async () => ({
      ok: false,
      status: 503,
      json: async () => ({ detail: { code: "provider_not_configured", provider: "max" } }),
    }));
    await expect(messengerLogin("max", "x")).rejects.toMatchObject({
      status: 503,
      message: "provider_not_configured",
    });
  });
});
