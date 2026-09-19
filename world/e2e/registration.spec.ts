import { expect, test, type APIRequestContext } from "@playwright/test";

const API = process.env.WORLD_API || "http://127.0.0.1:8010";
const CONSENT_VERSION = "2026-09-19";

const run = Date.now();
const phone = `+7916${String(run).slice(-7)}`;

const anketa = {
  first_name: "Ева",
  last_name: "Тестова",
  birth_date: "2015-05-12",
  school_number: "12",
  class_grade: 1,
  class_letter: "А",
  parent_email: "e2e-parent@example.ru",
  parent_phone: phone,
  channel: "sms",
};

/**
 * Заголовки с валидной сессией: на проде WORLD_PLAYER_SECRET не пускает сырые ключи,
 * поэтому сначала создаём игрока и берём выданный токен (как в castle-спеках).
 */
async function authHeaders(request: APIRequestContext, key: string) {
  const created = await request.post(`${API}/api/world/players`, {
    headers: { "X-World-Player": key, "Content-Type": "application/json" },
    data: { display_name: "Ева" },
  });
  expect(created.ok()).toBeTruthy();
  const { token } = (await created.json()) as { token: string };
  return { "X-World-Player": token, "Content-Type": "application/json" };
}

test("API: регистрация — start → verify(dev_code) → status", async ({ request }) => {
  const headers = await authHeaders(request, `e2e-reg-${run}`);
  const start = await request.post(`${API}/api/v2/registration/start`, {
    headers,
    data: {
      ...anketa,
      consents: [
        { type: "pd_child", version: CONSENT_VERSION },
        { type: "privacy", version: CONSENT_VERSION },
      ],
    },
  });
  expect(start.status()).toBe(200);
  const sent = await start.json();
  expect(sent.status).toBe("code_sent");
  expect(sent.phone_masked).toBeTruthy();

  // В проде (PHONE_VERIFICATION_REQUIRED=1) dev_code не отдаётся — тогда verify пропускаем.
  test.skip(!sent.dev_code, "dev_code отсутствует — прод-режим верификации телефона");

  const verify = await request.post(`${API}/api/v2/registration/verify`, {
    headers,
    data: { code: sent.dev_code },
  });
  expect(verify.status()).toBe(200);
  expect((await verify.json()).status).toBe("verified");

  const status = await request.get(`${API}/api/v2/registration/status`, { headers });
  expect(status.ok()).toBeTruthy();
  const body = await status.json();
  expect(body.identity).toBeTruthy();
  expect(body.identity.phone_verified).toBe(true);
  expect(body.identity.first_name).toBe("Ева");
});

test("API: регистрация — без обязательных согласий 409 consent_required", async ({ request }) => {
  const headers = await authHeaders(request, `e2e-reg-no-consent-${run}`);
  const start = await request.post(`${API}/api/v2/registration/start`, {
    headers,
    data: { ...anketa, parent_phone: `+7917${String(run).slice(-7)}`, consents: [] },
  });
  expect(start.status()).toBe(409);
  expect((await start.json()).detail).toMatch(/^consent_required/);
});
