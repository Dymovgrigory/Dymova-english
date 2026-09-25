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

function queueStart(result: unknown = { status: "code_sent", channel: "email", email_masked: "m***a@example.ru", cooldown_sec: 60 }) {
  replies.push(jsonResponse(200, result));
}

beforeEach(() => {
  replies.length = 0;
  calls.length = 0;
  // по умолчанию: status() → анкеты нет; bootstrap игрока → wses-токен
  vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    calls.push({ url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    if (url.includes("/registration/status")) return jsonResponse(200, { identity: null, consents: [] });
    if (url.includes("/api/world/players")) {
      return jsonResponse(200, {
        id: 1,
        external_key: "explorer-test",
        display_name: "Ученик",
        token: "wses.test.token",
      });
    }
    if (url.includes("/api/world/player")) return jsonResponse(200, { id: 1, external_key: "explorer-test" });
    return replies.shift() ?? jsonResponse(200, { identity: null, consents: [] });
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

/** Проходит анкету → контакты (с паролем) → согласия и нажимает «Получить код». */
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
  fireEvent.change(screen.getByLabelText(/Пароль \(мин\. 8/), { target: { value: "secret123" } });
  fireEvent.change(screen.getByLabelText(/Повторите пароль/), { target: { value: "secret123" } });
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
      channel: "email",
      class_grade: 3,
      password: "secret123",
    });
    expect(start?.body?.consents).toEqual(
      expect.arrayContaining([
        { type: "pd_child", version: expect.any(String) },
        { type: "privacy", version: expect.any(String) },
      ]),
    );

    fireEvent.change(screen.getByLabelText("Код подтверждения"), { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: "Подтвердить" }));

    await waitFor(() => expect(screen.getByText(/Контакт подтверждён/)).toBeInTheDocument());
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

  it("email_recently_sent: просит подождать минуту", async () => {
    replies.push(jsonResponse(409, { detail: "email_recently_sent" }));
    await reachConsents("9164552233");

    fireEvent.click(screen.getByRole("checkbox", { name: /законным представителем/ }));
    fireEvent.click(screen.getByRole("checkbox", { name: /политику конфиденциальности/ }));
    fireEvent.click(screen.getByRole("button", { name: "Получить код" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Код уже отправлен, подождите минуту"),
    );
    expect(screen.queryByLabelText("Код подтверждения")).not.toBeInTheDocument();
  });

  it("422 age_out_of_range: показывает понятную ошибку возраста", async () => {
    replies.push(
      jsonResponse(422, {
        detail: [
          {
            type: "value_error",
            loc: ["body", "birth_date"],
            msg: "Value error, age must be between 3 and 17",
          },
        ],
      }),
    );
    await reachConsents("9164552233");

    fireEvent.click(screen.getByRole("checkbox", { name: /законным представителем/ }));
    fireEvent.click(screen.getByRole("checkbox", { name: /политику конфиденциальности/ }));
    fireEvent.click(screen.getByRole("button", { name: "Получить код" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Возраст ученика должен быть от 3 до 17 лет"),
    );
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
    expect(screen.getByText(/m\*\*\*a@example\.ru/)).toBeInTheDocument();
  });

  it("prefill от моста бота: анкета и телефон предзаполнены", async () => {
    render(
      <RegistrationFlow
        mode="gate"
        onDone={() => {}}
        prefill={{ firstName: "Миша", lastName: "Петров", birthDate: "2016-03-15", phone: "+79164552233" }}
      />,
    );
    await waitFor(() => expect(screen.getByPlaceholderText("Аня")).toBeInTheDocument());
    expect(screen.getByPlaceholderText("Аня")).toHaveValue("Миша");
    expect(screen.getByPlaceholderText("Иванова")).toHaveValue("Петров");
    expect(screen.getByLabelText(/Дата рождения/)).toHaveValue("2016-03-15");

    // школа/класс предзаполнить нельзя — их нет в боте
    fireEvent.change(screen.getByPlaceholderText("12"), { target: { value: "12" } });
    fireEvent.click(screen.getByRole("button", { name: "3" }));
    fireEvent.click(screen.getByRole("button", { name: "Дальше" }));

    // телефон подставлен и отформатирован
    expect(screen.getByPlaceholderText("+7 (___) ___-__-__")).toHaveValue("+7 (916) 455-22-33");
  });

  it("subscriberDigits/toE164: префиксы 7 и 8 отбрасываются", () => {
    expect(subscriberDigits("89164552233")).toBe("9164552233");
    expect(subscriberDigits("+7 916 455-22-33")).toBe("9164552233");
    expect(toE164("9164552233")).toBe("+79164552233");
    expect(toE164("916")).toBeNull();
  });
});

describe("RegistrationFlow: канал telegram (без SMS)", () => {
  const requestContact = vi.fn((cb?: (sent: boolean) => void) => cb?.(true));

  beforeEach(() => {
    requestContact.mockClear();
    vi.stubGlobal("Telegram", {
      WebApp: { initData: "query_id=AAE&user=%7B%22id%22%3A1%7D", requestContact },
    });
  });

  it("в Telegram шлёт awaiting_bot → шаг бота (без кода на email)", async () => {
    queueStart({ status: "awaiting_bot", channel: "telegram", phone_masked: "+7 (916) ***-**-33", cooldown_sec: 0 });
    await reachConsents("+7 (916) 455-22-33");

    fireEvent.click(screen.getByRole("checkbox", { name: /законным представителем/ }));
    fireEvent.click(screen.getByRole("checkbox", { name: /политику конфиденциальности/ }));
    fireEvent.click(screen.getByRole("button", { name: "Продолжить" }));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Поделиться номером в Telegram" })).toBeInTheDocument(),
    );
    const start = calls.find((c) => c.url.includes("/registration/start"));
    expect(start?.body?.channel).toBe("telegram");
    expect(start?.body?.password).toBe("secret123");
    expect(screen.queryByLabelText("Код подтверждения")).not.toBeInTheDocument();
  });

  it("поделиться номером → confirm-bot → успех", async () => {
    queueStart({ status: "awaiting_bot", channel: "telegram", phone_masked: "+7 (916) ***-**-33", cooldown_sec: 0 });
    replies.push(jsonResponse(200, { status: "verified" }));
    const onDone = vi.fn();
    await reachConsents("+7 (916) 455-22-33", onDone);

    fireEvent.click(screen.getByRole("checkbox", { name: /законным представителем/ }));
    fireEvent.click(screen.getByRole("checkbox", { name: /политику конфиденциальности/ }));
    fireEvent.click(screen.getByRole("button", { name: "Продолжить" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Поделиться номером в Telegram" })).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "Поделиться номером в Telegram" }));
    await waitFor(() => expect(screen.getByText(/Контакт подтверждён/)).toBeInTheDocument());
    expect(requestContact).toHaveBeenCalled();
    expect(calls.some((c) => c.url.includes("/registration/confirm-bot"))).toBe(true);

    fireEvent.click(screen.getByRole("button", { name: "Продолжить" }));
    expect(onDone).toHaveBeenCalled();
  });

  it("phone_mismatch: понятная ошибка про другой номер", async () => {
    queueStart({ status: "awaiting_bot", channel: "telegram", phone_masked: "+7 (916) ***-**-33", cooldown_sec: 0 });
    replies.push(jsonResponse(409, { detail: "phone_mismatch" }));
    await reachConsents("+7 (916) 455-22-33");

    fireEvent.click(screen.getByRole("checkbox", { name: /законным представителем/ }));
    fireEvent.click(screen.getByRole("checkbox", { name: /политику конфиденциальности/ }));
    fireEvent.click(screen.getByRole("button", { name: "Продолжить" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Поделиться номером в Telegram" })).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "Поделиться номером в Telegram" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/другим номером/));
  });

  it("отказ делиться номером: просим нажать ещё раз, confirm-bot не зовём", async () => {
    requestContact.mockImplementationOnce((cb?: (sent: boolean) => void) => cb?.(false));
    queueStart({ status: "awaiting_bot", channel: "telegram", phone_masked: "+7 (916) ***-**-33", cooldown_sec: 0 });
    await reachConsents("+7 (916) 455-22-33");

    fireEvent.click(screen.getByRole("checkbox", { name: /законным представителем/ }));
    fireEvent.click(screen.getByRole("checkbox", { name: /политику конфиденциальности/ }));
    fireEvent.click(screen.getByRole("button", { name: "Продолжить" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Поделиться номером в Telegram" })).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "Поделиться номером в Telegram" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/Номер не отправлен/));
    expect(calls.some((c) => c.url.includes("/registration/confirm-bot"))).toBe(false);
  });
});
