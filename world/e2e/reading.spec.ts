import { expect, test, type Page } from "@playwright/test";

import { authHeaders, createPlayer, registerPlayer } from "./helpers";

const API = process.env.WORLD_API || "http://127.0.0.1:8010";

/** Контрактные ответы этапа 5 (docs/world/reading-contract.md) — мок сети, бэк не нужен. */
const READING_SESSION = {
  session_id: "e2e-reading",
  node_id: "sp2.m1.n9",
  kind: "reading",
  graded_total: 3,
  challenges: [
    {
      index: 0,
      type: "read_text",
      atom_id: "sp2.m1.t1",
      graded: false,
      text_id: "sp2.m1.t1",
      title_en: "Foxy at School",
      title_ru: "Фокси в школе",
      sentences: ["Foxy runs to school.", "He likes books.", "His bag is red."],
    },
    {
      index: 1,
      type: "read_text_truefalse",
      atom_id: "sp2.m1.t1",
      graded: true,
      text_id: "sp2.m1.t1",
      sentence_en: "Foxy likes books.",
      q_ru: "Фокси нравятся книги.",
      sentences: ["Foxy runs to school.", "He likes books.", "His bag is red."],
    },
    {
      index: 2,
      type: "read_text_answer",
      atom_id: "sp2.m1.t1",
      graded: true,
      text_id: "sp2.m1.t1",
      q_en: "What does Foxy like?",
      q_ru: "Что нравится Фокси?",
      options: ["books", "cats", "milk"],
      sentences: ["Foxy runs to school.", "He likes books.", "His bag is red."],
    },
    {
      index: 3,
      type: "word_in_context",
      atom_id: "sp2.m1.t1",
      graded: true,
      text_id: "sp2.m1.t1",
      sentence_en: "Foxy has a red ___.",
      options: ["bag", "cat", "pen"],
    },
  ],
};

const ANSWER_OK = { correct: true, typo: false, skipped: false, solution: "true", solution_index: 0, requeued: false, remaining: 0 };

const FINISH = {
  node_id: "sp2.m1.n9",
  kind: "reading",
  xp: 12,
  coins: 6,
  stars: 3,
  passed: true,
  accuracy: 1,
  mistakes: 0,
  duration_sec: 42,
  streak_days: 1,
  today_xp: 12,
  daily_goal_xp: 20,
  goal_reached: false,
  node_completed: true,
  next_node_id: null,
  player: { xp: 12, coins: 6, level: 1 },
  coins_breakdown: { lesson: 6 },
  titles_gained: [],
};

async function mockReadingSession(page: Page) {
  await page.route("**/api/v2/sessions", (route) =>
    route.request().method() === "POST" ? route.fulfill({ json: READING_SESSION }) : route.fallback(),
  );
  await page.route("**/api/v2/sessions/*/answer", (route) => route.fulfill({ json: ANSWER_OK }));
  await page.route("**/api/v2/sessions/*/finish", (route) => route.fulfill({ json: FINISH }));
  await page.route("**/api/world/tts**", (route) => route.fulfill({ status: 404 }));
}

test("API: узел чтения на пути и сессия чтения", async ({ request }) => {
  const { token } = await createPlayer(request);
  // Гейт регистрации: без анкеты /api/v2/* отвечает 403 registration_required.
  await registerPlayer(request, token);
  const headers = authHeaders(token);

  const courses = await (await request.get(`${API}/api/v2/courses`)).json();
  const book = courses.books[0];
  // Профиль на следующую книгу: книга ниже класса открыта целиком — узел reading доступен без прохождения.
  const nextBook = courses.books[1];
  await request.put(`${API}/api/v2/profile`, { headers, data: { book_id: nextBook.id, module_id: nextBook.modules[0].id, daily_goal_xp: 20 } });

  const path = await (await request.get(`${API}/api/v2/path?book_id=${book.id}`, { headers })).json();
  const readingNode = path.modules.flatMap((m: { nodes: { kind: string }[] }) => m.nodes).find((n: { kind: string }) => n.kind === "reading");
  test.skip(!readingNode, "на бэке ещё нет узлов kind=reading (этап 5 в работе)");

  await request.post(`${API}/api/v2/sessions`, { headers, data: { node_id: readingNode.id, allow_speak: false } }).then(async (started) => {
    expect(started.ok()).toBeTruthy();
    const session = await started.json();
    expect(session.kind).toBe("reading");
    expect(session.challenges[0].type).toBe("read_text");
    expect(session.challenges[0].graded).toBe(false);
    expect(session.challenges[0].sentences.length).toBeGreaterThan(0);
    const types = session.challenges.map((c: { type: string }) => c.type);
    expect(types).toContain("read_text_truefalse");
    expect(types).toContain("read_text_answer");
  });
});

test("UI: сессия чтения на моке сети", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  // Гейт регистрации: без зарегистрированного игрока AppGate уводит на /onboarding.
  const { key, token } = await createPlayer(page.request);
  await registerPlayer(page.request, token);
  await page.addInitScript(
    ([t, k]) => {
      window.localStorage.setItem("world.playerToken", t);
      window.localStorage.setItem("world.playerKey", k);
    },
    [token, key] as const,
  );
  await mockReadingSession(page);
  await page.goto("/lesson/sp2.m1.n9");

  // Шаг 1: книжный разворот, шильдик навыка, TTS-кнопка.
  await expect(page.getByRole("region", { name: "Книжный разворот" })).toBeVisible();
  await expect(page.getByText("Читаем").first()).toBeVisible();
  await expect(page.getByRole("button", { name: /Слушать/ })).toBeVisible();
  await page.getByRole("button", { name: "Я прочитал(а)" }).click();

  // Шаг 2: Правда/Неправда, текст доступен во время ответа.
  await expect(page.getByRole("button", { name: "Правда", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Показать текст" }).click();
  await expect(page.getByRole("region", { name: "Текст для чтения" })).toBeVisible();
  await page.getByRole("button", { name: "Скрыть текст" }).click();
  await page.getByRole("button", { name: "Правда", exact: true }).click();
  await page.getByRole("button", { name: "Проверить" }).click();
  await page.getByRole("button", { name: "Дальше" }).click();

  // Шаг 3: вопрос с выбором из трёх.
  await expect(page.getByText("What does Foxy like?")).toBeVisible();
  await page.getByRole("button", { name: /books/ }).click();
  await page.getByRole("button", { name: "Проверить" }).click();
  await page.getByRole("button", { name: "Дальше" }).click();

  // Шаг 4: слово в пропуске.
  await expect(page.getByText(/Foxy has a red/)).toBeVisible();
  await page.getByRole("button", { name: /bag/ }).click();
  await page.getByRole("button", { name: "Проверить" }).click();
  await page.getByRole("button", { name: "Дальше" }).click();

  // Финиш сессии.
  await expect(page.getByText(/Урок пройден|Без единой ошибки|Молодец|Готово/i).first()).toBeVisible({ timeout: 10000 });
  expect(errors).toEqual([]);
});
