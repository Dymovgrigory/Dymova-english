import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RegistrationFlow } from "./RegistrationFlow";
import { subscriberDigits, toE164 } from "./phone";

type FetchReply = { ok: boolean; json: () => Promise<unknown> };

const replies: FetchReply[] = [];
const calls: { url: string; body?: Record<string, unknown> }[] = [];

function jsonResponse(status: number, body: unknown): FetchReply {
  return { ok: status >= 200 && status < 300, json: async () => body };
}

function queueStart(result: unknown = { status: "code_sent", channel: "sms", phone_masked: "+7 (916) ***-**-33", cooldown_sec: 60 }) {
  replies.push(jsonResponse(200, result));
}

beforeEach(() => {
  replies.length = 0;
  calls.length = 0;
  // по умолчанию: status() → анкеты нет
  vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    calls.push({ url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    // status() всегда отвечает «анкеты нет», очередь replies — только для start/verify
    if (url.includes("/registration/status")) return jsonResponse(200, { identity: null, consents: [] });
    return replies.shift() ?? jsonResponse(200, { identity: null, consents: [] });
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

/** Проходит анкету → контакты → согласия и нажимает «Получить код». */
async function reachConsents(phone: string, onDone: () => void = () => {}) {
  render(<RegistrationFlow mode="onboarding" onDone={onDone} />);
  await waitFor(() => expect(screen.getByPlaceholderText("Аня")).toBeInTheDocument());

  fireEvent.change(screen.getByPlaceholderText("Аня"), { target: { value: "Аня" } });
  fireEvent.change(screen.getByPlaceholderText("Иванова"), { target: { value: "Иванова" } });
  fireEvent.change(screen.getByLabelText(/Дата рождения/), { target: { value: "2015-05-12" } });
  fireEvent.change(screen.getByPlaceholderText("12"), { target: { value: "12" } });
  fireEvent.click(screen.getByRole("button", { name: "3" }));
  fireEvent.click(screen.getByRole("button", { name: "Дальше" }));

  fireEvent.change(screen.getByPlaceholderText("+7 (___) ___-__-__"), { target: { value: phone } });
  fireEvent.change(screen.getByPlaceholderText("parent@example.ru"), { target: { value: "mama@example.ru" } });
  fireEvent.click(screen.getByRole("button", { name: "Дальше" }));
}

describe("RegistrationFlow", () => {
  it("happy path: анкета → контакты → согласия → код → успех", async () => {
    queueStart();
    replies.push(jsonResponse(200, { status: "verified" }));
    const onDone = vi.fn();
    await reachConsents("+7 (916) 455-22-33", onDone);

    // без обязательных согласий кнопка недоступна
    const send = screen.getByRole("button", { name: "Получить код" });
    expect(send).toBeDisabled();

    fireEvent.click(screen.getByRole("checkbox", { name: /законным представителем/ }));
    fireEvent.click(screen.getByRole("checkbox", { name: /политику конфиденциальности/ }));
    expect(send).toBeEnabled();
    fireEvent.click(send);

    await waitFor(() => expect(screen.getByLabelText("Код подтверждения")).toBeInTheDocument());
    const start = calls.find((c) => c.url.includes("/registration/start"));
    expect(start?.body).toMatchObject({
      parent_phone: "+79164552233",
      channel: "sms",
      class_grade: 3,
    });
    expect(start?.body?.consents).toEqual(
      expect.arrayContaining([
        { type: "pd_child", version: expect.any(String) },
        { type: "privacy", version: expect.any(String) },
      ]),
    );

    fireEvent.change(screen.getByLabelText("Код подтверждения"), { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: "Подтвердить" }));

    await waitFor(() => expect(screen.getByText(/Телефон подтверждён/)).toBeInTheDocument());
    const verify = calls.find((c) => c.url.includes("/registration/verify"));
    expect(verify?.body).toEqual({ code: "123456" });

    fireEvent.click(screen.getByRole("button", { name: "Продолжить" }));
    expect(onDone).toHaveBeenCalled();
  });

  it("неверный код: показывает «Неверный код» и остаток попыток", async () => {
    queueStart();
    replies.push(jsonResponse(409, { detail: "code_invalid", attempts_left: 2 }));
    await reachConsents("9164552233");

    fireEvent.click(screen.getByRole("checkbox", { name: /законным представителем/ }));
    fireEvent.click(screen.getByRole("checkbox", { name: /политику конфиденциальности/ }));
    fireEvent.click(screen.getByRole("button", { name: "Получить код" }));
    await waitFor(() => expect(screen.getByLabelText("Код подтверждения")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Код подтверждения"), { target: { value: "000000" } });
    fireEvent.click(screen.getByRole("button", { name: "Подтвердить" }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Неверный код. Осталось попыток: 2"));
  });

  it("phone_recently_sent: просит подождать минуту", async () => {
    replies.push(jsonResponse(409, { detail: "phone_recently_sent" }));
    await reachConsents("9164552233");

    fireEvent.click(screen.getByRole("checkbox", { name: /законным представителем/ }));
    fireEvent.click(screen.getByRole("checkbox", { name: /политику конфиденциальности/ }));
    fireEvent.click(screen.getByRole("button", { name: "Получить код" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Код уже отправлен, подождите минуту"),
    );
    expect(screen.queryByLabelText("Код подтверждения")).not.toBeInTheDocument();
  });

  it("нормализация: 8916… → +7916…", async () => {
    queueStart();
    await reachConsents("8 (916) 455-22-33");

    fireEvent.click(screen.getByRole("checkbox", { name: /законным представителем/ }));
    fireEvent.click(screen.getByRole("checkbox", { name: /политику конфиденциальности/ }));
    fireEvent.click(screen.getByRole("button", { name: "Получить код" }));

    await waitFor(() => {
      const start = calls.find((c) => c.url.includes("/registration/start"));
      expect(start?.body?.parent_phone).toBe("+79164552233");
    });
    expect(screen.getByText(/\+7 \(916\) \*\*\*-\*\*-33/)).toBeInTheDocument();
  });

  it("subscriberDigits/toE164: префиксы 7 и 8 отбрасываются", () => {
    expect(subscriberDigits("89164552233")).toBe("9164552233");
    expect(subscriberDigits("+7 916 455-22-33")).toBe("9164552233");
    expect(toE164("9164552233")).toBe("+79164552233");
    expect(toE164("916")).toBeNull();
  });
});
