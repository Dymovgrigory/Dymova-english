import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

export const API = process.env.WORLD_API || "http://127.0.0.1:8010";
export const CONSENT_VERSION = "2026-09-19";

/** Свежий игрок через API. На проде WORLD_PLAYER_SECRET не пускает сырые ключи — берём выданный токен. */
export async function createPlayer(request: APIRequestContext, name = "Ева"): Promise<{ key: string; token: string }> {
  const key = `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const created = await request.post(`${API}/api/world/players`, {
    headers: { "X-World-Player": key, "Content-Type": "application/json" },
    data: { display_name: name },
  });
  expect(created.ok()).toBeTruthy();
  const { token } = (await created.json()) as { token: string };
  return { key, token };
}

export function authHeaders(token: string) {
  return { "X-World-Player": token, "Content-Type": "application/json" };
}

/**
 * Обязательная регистрация (гейт): start → verify(dev_code).
 * В прод-режиме PHONE_VERIFICATION_REQUIRED=1 dev_code не отдаётся — тест пропускается.
 */
export async function registerPlayer(request: APIRequestContext, token: string): Promise<void> {
  const headers = authHeaders(token);
  const start = await request.post(`${API}/api/v2/registration/start`, {
    headers,
    data: {
      first_name: "Ева",
      last_name: "Тестова",
      birth_date: "2015-05-12",
      school_number: "12",
      class_grade: 1,
      class_letter: "А",
      parent_email: "e2e-parent@example.ru",
      parent_phone: `+7916${String(Math.floor(Math.random() * 1e7)).padStart(7, "0")}`,
      channel: "sms",
      consents: [
        { type: "pd_child", version: CONSENT_VERSION },
        { type: "privacy", version: CONSENT_VERSION },
      ],
    },
  });
  expect(start.status()).toBe(200);
  const sent = await start.json();
  test.skip(!sent.dev_code, "прод-режим верификации телефона: dev_code не отдаётся");
  const verify = await request.post(`${API}/api/v2/registration/verify`, {
    headers,
    data: { code: sent.dev_code },
  });
  expect(verify.status()).toBe(200);
}

/**
 * Зарегистрированный игрок с профилем учебника и токеном в localStorage страницы.
 * Без регистрации гейт (AppGate + 403 registration_required) не пускает в мир.
 */
export async function bootstrapRegisteredPlayer(page: Page, bookId = "sp1", moduleId = "sp1.m1"): Promise<string> {
  const { key, token } = await createPlayer(page.request);
  await registerPlayer(page.request, token);
  const profile = await page.request.put(`${API}/api/v2/profile`, {
    headers: authHeaders(token),
    data: { book_id: bookId, module_id: moduleId, daily_goal_xp: 20 },
  });
  expect(profile.ok()).toBeTruthy();
  await page.addInitScript(
    ([t, k]) => {
      window.localStorage.setItem("world.playerToken", t);
      window.localStorage.setItem("world.playerKey", k);
    },
    [token, key] as const,
  );
  return token;
}

/**
 * Полное прохождение анкеты в UI (режим gate — без «Заполню позже»).
 * Код подтверждения берём из ответа /registration/start (dev-режим).
 */
export async function completeRegistrationUi(page: Page): Promise<void> {
  const phoneDigits = `916${String(Math.floor(Math.random() * 1e7)).padStart(7, "0")}`;
  await page.getByLabel("Имя ребёнка").fill("Ева");
  await page.getByLabel("Фамилия").fill("Тестова");
  await page.getByLabel("Дата рождения").fill("2015-05-12");
  await page.getByLabel("Номер школы").fill("12");
  await page.locator("button[aria-pressed]").filter({ hasText: /^1$/ }).first().click();
  await page.getByRole("button", { name: "Дальше" }).click();

  await page.getByLabel("Телефон родителя").fill(phoneDigits);
  await page.getByLabel("Email родителя").fill("e2e-parent@example.ru");
  await page.getByRole("button", { name: "Дальше" }).click();

  // Обязательные согласия: ПД ребёнка + политика конфиденциальности.
  await page.getByRole("checkbox").nth(0).click();
  await page.getByRole("checkbox").nth(1).click();
  const sentPromise = page.waitForResponse(
    (r) => r.url().includes("/api/v2/registration/start") && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Получить код" }).click();
  const sent = await sentPromise;
  const body = (await sent.json()) as { dev_code?: string };
  test.skip(!body.dev_code, "прод-режим верификации телефона: код приходит только на реальный номер");

  await page.getByLabel("Код подтверждения").fill(body.dev_code!);
  await page.getByRole("button", { name: "Подтвердить" }).click();
  await page.getByRole("button", { name: "Продолжить" }).click();
}
