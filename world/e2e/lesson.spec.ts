import { expect, test } from "@playwright/test";

const API = process.env.WORLD_API || "http://127.0.0.1:8010";

test("API: профиль, путь и старт урока тренажёра", async ({ request }) => {
  const bootstrap = { "X-World-Player": `e2e-${Date.now()}`, "Content-Type": "application/json" };
  const created = await request.post(`${API}/api/world/players`, { headers: bootstrap, data: { display_name: "Ева" } });
  expect(created.ok()).toBeTruthy();
  // Дальше — как настоящий клиент: с выданным сервером токеном сессии.
  const headers = { ...bootstrap, "X-World-Player": (await created.json()).token };

  const courses = await (await request.get(`${API}/api/v2/courses`)).json();
  const book = courses.books[0];
  expect(book.modules.length).toBeGreaterThan(0);

  const profile = await request.put(`${API}/api/v2/profile`, {
    headers,
    data: { book_id: book.id, module_id: book.modules[0].id, daily_goal_xp: 20 },
  });
  expect(profile.ok()).toBeTruthy();

  const home = await (await request.get(`${API}/api/v2/home`, { headers })).json();
  expect(home.current_node.id).toBeTruthy();

  const started = await request.post(`${API}/api/v2/sessions`, {
    headers,
    data: { node_id: home.current_node.id, allow_speak: false },
  });
  expect(started.ok()).toBeTruthy();
  const session = await started.json();
  expect(session.graded_total).toBeGreaterThanOrEqual(8);
  expect(session.challenges.every((c: Record<string, unknown>) => !("solution" in c))).toBeTruthy();

  const teach = session.challenges.find((c: { graded: boolean }) => !c.graded);
  const reply = await request.post(`${API}/api/v2/sessions/${session.session_id}/answer`, {
    headers,
    data: { index: teach.index, answer: {} },
  });
  expect((await reply.json()).correct).toBe(true);
});

test("UI: знакомство → первый урок → путь", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));

  await page.goto("/");
  await expect(page).toHaveURL(/onboarding/);
  await page.getByRole("textbox", { name: "Как тебя зовут?" }).fill("Ева");
  await page.getByRole("button", { name: "Дальше" }).click();
  await page.getByRole("button", { name: /1 класс/ }).click();
  await page.getByRole("button", { name: "Дальше" }).click();
  await page.getByRole("button", { name: /My Family!/ }).click();
  await page.getByRole("button", { name: "Дальше" }).click();
  await page.getByRole("button", { name: /Нормально/ }).click();
  await page.getByRole("button", { name: "Начать первый урок" }).click();

  await expect(page).toHaveURL(/lesson\/sp1\.m1\.n1/);
  await expect(page.getByText("Новое слово")).toBeVisible();
  await page.getByRole("button", { name: "Дальше" }).click();
  // Следующее задание случайно: оценивается кнопкой «Проверить» или микрофоном.
  await expect(page.getByRole("button", { name: /Проверить|Нажми и говори/ })).toBeVisible();

  await page.getByRole("button", { name: "Выйти из урока" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Выйти", exact: true }).click();
  await expect(page).toHaveURL(/learn/);
  await expect(page.getByRole("heading", { name: "My Family!" })).toBeVisible();
  await expect(page.getByRole("button", { name: /начать/ }).first()).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Разделы" })).toBeVisible();

  await page.getByRole("link", { name: "Словарь" }).click();
  await expect(page.getByRole("heading", { name: "Мой словарь" })).toBeVisible();
  expect(errors).toEqual([]);
});
