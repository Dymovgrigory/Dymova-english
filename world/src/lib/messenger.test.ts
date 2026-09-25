import { afterEach, describe, expect, it, vi } from "vitest";

import {
  buildRegistrationPrefill,
  detectMessenger,
  messengerLogin,
  requestTelegramContact,
} from "./messenger";

declare const globalThis: Record<string, unknown>;

afterEach(() => {
  delete globalThis.window;
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("requestTelegramContact", () => {
  it("без requestContact — false", async () => {
    globalThis.window = { Telegram: { WebApp: { initData: "x" } } };
    await expect(requestTelegramContact()).resolves.toBe(false);
  });

  it("колбэк true — true", async () => {
    const requestContact = vi.fn((cb?: (sent: boolean) => void) => cb?.(true));
    globalThis.window = { Telegram: { WebApp: { initData: "x", requestContact } } };
    await expect(requestTelegramContact()).resolves.toBe(true);
    expect(requestContact).toHaveBeenCalled();
  });

  it("колбэк не приходит — false по таймауту (не зависаем)", async () => {
    vi.useFakeTimers();
    const requestContact = vi.fn(() => {
      /* никогда не зовём callback — баг части клиентов TG */
    });
    globalThis.window = { Telegram: { WebApp: { initData: "x", requestContact } } };
    const pending = requestTelegramContact();
    await vi.advanceTimersByTimeAsync(90_000);
    await expect(pending).resolves.toBe(false);
  });
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

describe("buildRegistrationPrefill", () => {
  it("полный lead из бота: имя/фамилия ребёнка, дата ДД.ММ.ГГГГ → ISO, телефон", () => {
    expect(
      buildRegistrationPrefill("Маша Петрова", {
        fio_parent: "Петрова Анна Сергеевна",
        fio_child: "Миша Петров",
        birthday: "15.03.2016",
        phone: "+79164552233",
      }),
    ).toEqual({
      firstName: "Миша",
      lastName: "Петров",
      birthDate: "2016-03-15",
      phone: "+79164552233",
    });
  });

  it("без лида — имя из профиля мессенджера, остальное пусто", () => {
    expect(buildRegistrationPrefill("Маша Петрова", null)).toEqual({
      firstName: "Маша",
      lastName: undefined,
      birthDate: undefined,
      phone: undefined,
    });
  });

  it("fio_child только имя — lastName не заполняется", () => {
    expect(buildRegistrationPrefill("", { fio_child: "Миша" })).toEqual({
      firstName: "Миша",
      lastName: undefined,
      birthDate: undefined,
      phone: undefined,
    });
  });

  it("дата уже ISO — оставляем; возраст «9 лет» — пропускаем", () => {
    expect(buildRegistrationPrefill("", { birthday: "2016-03-15" }).birthDate).toBe("2016-03-15");
    expect(buildRegistrationPrefill("", { birthday: "9 лет" }).birthDate).toBeUndefined();
  });

  it("пустой телефон → undefined", () => {
    expect(buildRegistrationPrefill("", { phone: "   " }).phone).toBeUndefined();
  });
});
