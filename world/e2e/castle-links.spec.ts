import { expect, test, type Page } from "@playwright/test";

const API = process.env.WORLD_API || "http://127.0.0.1:8010";

/** Свежий игрок с профилем: без него замок показывает знакомство, а не комнаты. */
async function bootstrapPlayer(page: Page): Promise<string> {
  const key = `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const created = await page.request.post(`${API}/api/world/players`, {
    headers: { "X-World-Player": key, "Content-Type": "application/json" },
    data: { display_name: "Ева" },
  });
  expect(created.ok()).toBeTruthy();
  const { token } = (await created.json()) as { token: string };
  const profile = await page.request.put(`${API}/api/v2/profile`, {
    headers: { "X-World-Player": token, "Content-Type": "application/json" },
    data: { book_id: "sp1", module_id: "sp1.m1", daily_goal_xp: 20 },
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

async function openRoom(page: Page, short: string) {
  await page.goto("/world");
  await page.waitForTimeout(1200);
  await page.getByRole("button", { name: short, exact: true }).click();
}

test("в Сокровищнице виден прогресс сундука слов", async ({ page }) => {
  await bootstrapPlayer(page);
  await openRoom(page, "Слова");
  await expect(page.getByText("Сундук слов")).toBeVisible();
  await expect(page.getByText(/Слов до сундука: 0\/25/)).toBeVisible();
});

test("в Беседке видны секции дня и недели и переход у задания", async ({ page }) => {
  await bootstrapPlayer(page);
  await openRoom(page, "Задания");
  await expect(page.getByRole("heading", { name: "Сегодня" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Эта неделя" })).toBeVisible();
  await expect(page.getByText("Пройди урок")).toBeVisible();
  await expect(page.getByRole("button", { name: "Перейти: Пройди урок" })).toBeVisible();
});

test("в Башне Славы виден блок трофеев", async ({ page }) => {
  await bootstrapPlayer(page);
  await openRoom(page, "Слава");
  await expect(page.getByRole("heading", { name: "Трофеи" })).toBeVisible();
  await expect(page.getByText("Закрой неделю в лиге, и трофей появится здесь.")).toBeVisible();
});

test("во Дворе видна карточка испытания дня", async ({ page }) => {
  await bootstrapPlayer(page);
  await openRoom(page, "Двор");
  await expect(page.getByText("Испытание дня")).toBeVisible();
  await expect(page.getByText(/15 секунд на ответ/)).toBeVisible();
  // У нового игрока нет выученных слов — испытание закрыто.
  await expect(page.getByText("Сначала выучи слова на уроках")).toBeVisible();
});
