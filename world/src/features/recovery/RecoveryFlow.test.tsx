import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RecoveryFlow } from "./RecoveryFlow";

type FetchReply = { ok: boolean; json: () => Promise<unknown> };

const replies: FetchReply[] = [];
const calls: { url: string; body?: Record<string, unknown> }[] = [];
const store = new Map<string, string>();

const localStorageStub = {
  getItem: (k: string) => store.get(k) ?? null,
  setItem: (k: string, v: string) => void store.set(k, v),
  removeItem: (k: string) => void store.delete(k),
  clear: () => store.clear(),
};

function jsonResponse(status: number, body: unknown): FetchReply {
  return { ok: status >= 200 && status < 300, json: async () => body };
}

beforeEach(() => {
  replies.length = 0;
  calls.length = 0;
  store.clear();
  vi.stubGlobal("localStorage", localStorageStub);
  vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    calls.push({ url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    return replies.shift() ?? jsonResponse(500, { detail: "no_reply_queued" });
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("RecoveryFlow", () => {
  it("happy path: email → код → новый пароль → токен", async () => {
    replies.push(jsonResponse(200, { status: "code_sent", email_masked: "m***a@example.ru" }));
    replies.push(jsonResponse(200, { status: "code_ok", reset_token: "tok-abc", email_masked: "m***a@example.ru" }));
    replies.push(jsonResponse(200, {
      status: "verified", token: "wses.abc.def", external_key: "kid-1", display_name: "Ева",
    }));
    const onDone = vi.fn();
    render(<RecoveryFlow onDone={onDone} />);

    fireEvent.change(screen.getByLabelText(/Email из анкеты/), { target: { value: "mama@example.ru" } });
    fireEvent.click(screen.getByRole("button", { name: "Получить код" }));

    await waitFor(() => expect(screen.getByLabelText("Код из письма")).toBeInTheDocument());
    expect(calls.find((c) => c.url.includes("/recovery/start"))?.body).toEqual({ email: "mama@example.ru" });

    fireEvent.change(screen.getByLabelText("Код из письма"), { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: "Дальше" }));

    await waitFor(() => expect(screen.getByLabelText(/Новый пароль/)).toBeInTheDocument());
    expect(calls.find((c) => c.url.includes("/recovery/verify"))?.body).toEqual({
      email: "mama@example.ru", code: "123456",
    });

    fireEvent.change(screen.getByLabelText(/Новый пароль/), { target: { value: "newpass99" } });
    fireEvent.change(screen.getByLabelText(/Повторите пароль/), { target: { value: "newpass99" } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить и войти" }));

    await waitFor(() => expect(screen.getByText(/Пароль обновлён/)).toBeInTheDocument());
    expect(calls.find((c) => c.url.includes("/recovery/password"))?.body).toEqual({
      reset_token: "tok-abc", password: "newpass99",
    });
    expect(localStorageStub.getItem("world.playerToken")).toBe("wses.abc.def");
    expect(localStorageStub.getItem("world.playerKey")).toBe("kid-1");

    fireEvent.click(screen.getByRole("button", { name: "Продолжить" }));
    expect(onDone).toHaveBeenCalled();
  });

  it("неверный код: показывает ошибку, токен не сохраняется", async () => {
    replies.push(jsonResponse(200, { status: "code_sent", email_masked: "m***a@example.ru" }));
    replies.push(jsonResponse(409, { detail: "code_invalid", attempts_left: 3 }));
    render(<RecoveryFlow onDone={() => {}} />);

    fireEvent.change(screen.getByLabelText(/Email из анкеты/), { target: { value: "mama@example.ru" } });
    fireEvent.click(screen.getByRole("button", { name: "Получить код" }));
    await waitFor(() => expect(screen.getByLabelText("Код из письма")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Код из письма"), { target: { value: "000000" } });
    fireEvent.click(screen.getByRole("button", { name: "Дальше" }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Неверный код"));
    expect(localStorageStub.getItem("world.playerToken")).toBeNull();
  });

  it("тестовый режим: dev_code показан подсказкой", async () => {
    replies.push(jsonResponse(200, { status: "code_sent", email_masked: "m***a@example.ru", dev_code: "777777" }));
    render(<RecoveryFlow onDone={() => {}} />);

    fireEvent.change(screen.getByLabelText(/Email из анкеты/), { target: { value: "mama@example.ru" } });
    fireEvent.click(screen.getByRole("button", { name: "Получить код" }));

    await waitFor(() => expect(screen.getByRole("note")).toHaveTextContent("777777"));
  });

  it("по телефону: start шлёт phone, затем пароль", async () => {
    replies.push(jsonResponse(200, {
      status: "code_sent", email_masked: "m***a@example.ru", phone_masked: "+7 916 ***-**-67",
    }));
    replies.push(jsonResponse(200, { status: "code_ok", reset_token: "tok-ph", email_masked: "m***a@example.ru" }));
    replies.push(jsonResponse(200, {
      status: "verified", token: "wses.phone.1", external_key: "kid-phone", display_name: "Ева",
    }));
    render(<RecoveryFlow onDone={() => {}} />);

    fireEvent.click(screen.getByRole("button", { name: "Телефон" }));
    fireEvent.change(screen.getByPlaceholderText("+7 916 123-45-67"), { target: { value: "8 916 123-45-67" } });
    fireEvent.click(screen.getByRole("button", { name: "Получить код" }));
    await waitFor(() => expect(screen.getByLabelText("Код из письма")).toBeInTheDocument());
    expect(calls.find((c) => c.url.includes("/recovery/start"))?.body).toEqual({ phone: "+79161234567" });

    fireEvent.change(screen.getByLabelText("Код из письма"), { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: "Дальше" }));
    await waitFor(() => expect(screen.getByLabelText(/Новый пароль/)).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText(/Новый пароль/), { target: { value: "phonepass1" } });
    fireEvent.change(screen.getByLabelText(/Повторите пароль/), { target: { value: "phonepass1" } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить и войти" }));
    await waitFor(() => expect(localStorageStub.getItem("world.playerToken")).toBe("wses.phone.1"));
  });
});
