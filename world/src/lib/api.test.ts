import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, humanizeError, worldApi } from "./api";

/** Ответы API с машинными кодами превращаются в понятные фразы, без сырого JSON. */
describe("humanizeError", () => {
  it("мапит известные коды магазина на русские фразы", () => {
    expect(humanizeError(new ApiError(409, "not enough coins"), "Ошибка")).toBe("Не хватает монет");
    expect(humanizeError(new ApiError(404, "item not found"), "Ошибка")).toBe("Товар не найден");
    expect(humanizeError(new ApiError(409, "item_not_for_sale"), "Ошибка")).toBe("Это не продаётся");
    expect(humanizeError(new ApiError(409, "title_required"), "Ошибка")).toBe("Сначала нужно звание");
    expect(humanizeError(new ApiError(409, "item_not_owned"), "Ошибка")).toBe("Сначала нужно купить");
    expect(humanizeError(new ApiError(409, "quest not complete"), "Ошибка")).toBe("Задание ещё не выполнено");
    expect(humanizeError(new ApiError(409, "nothing_to_practice"), "Ошибка")).toBe(
      "Пока нечего тренировать — сначала пройди урок",
    );
  });

  it("неизвестный код и не-ApiError отдают fallback, без сырого тела ответа", () => {
    expect(humanizeError(new ApiError(500, "weird code"), "Что-то пошло не так")).toBe("Что-то пошло не так");
    expect(humanizeError(new Error("network down"), "Что-то пошло не так")).toBe("network down");
    expect(humanizeError("строка", "Что-то пошло не так")).toBe("Что-то пошло не так");
  });
});

describe("worldApi error detail", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("покупка в лавке при 409 отдаёт detail, а не сырое тело с путём", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ detail: "not enough coins" }), { status: 409 })),
    );
    const err = await worldApi.buyShop("hearts_refill").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(409);
    expect((err as ApiError).message).toBe("not enough coins");
    expect(humanizeError(err, "Не хватило монет")).toBe("Не хватает монет");
  });

  it("не-JSON тело ошибки не роняет разбор — статус как detail", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("boom", { status: 500 })));
    const err = await worldApi.buyShop("hearts_refill").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).message).toBe("500");
  });
});
