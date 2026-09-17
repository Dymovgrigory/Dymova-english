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

test("в Гнезде видно пять веток званий и прогресс", async ({ page }) => {
  await bootstrapPlayer(page);
  await page.goto("/world");
  await page.waitForTimeout(1200);
  await page.getByRole("button", { name: "Гнездо", exact: true }).click();

  for (const track of ["Словесник", "Тренер", "Хранитель огня", "Чемпион", "Собиратель"]) {
    await expect(page.getByText(track, { exact: false })).toBeVisible();
  }
});

test("звание без уровня надеть нельзя", async ({ page }) => {
  await bootstrapPlayer(page);
  await page.goto("/world");
  await page.waitForTimeout(1200);
  await page.getByRole("button", { name: "Гнездо", exact: true }).click();
  const wear = page.getByRole("button", { name: /Носить/ }).first();
  await expect(wear).toBeDisabled();
});
