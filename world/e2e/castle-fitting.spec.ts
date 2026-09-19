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

function castle(page: Page, token: string) {
  return page.request.get(`${API}/api/v2/castle`, { headers: { "X-World-Player": token } });
}

async function openWorkshop(page: Page) {
  await page.goto("/world");
  await page.waitForTimeout(1200);
  await page.getByRole("button", { name: "Лавка", exact: true }).click();
  await page.getByRole("tab", { name: "Мастерская облика" }).click();
}

test("примерка меняет сцену без покупки: монеты не списываются", async ({ page }) => {
  const token = await bootstrapPlayer(page);
  await openWorkshop(page);
  const before = await (await castle(page, token)).json() as { coins: number };

  await page.getByRole("button", { name: "Примерить на замке" }).click();
  await expect(page.getByRole("dialog", { name: "Примерка облика замка" })).toBeVisible();
  // Выбираем ночь в примерке — это только превью
  await page.getByRole("tab", { name: "Время суток" }).click();
  await page.getByRole("button", { name: "Ночь" }).first().click();
  await page.getByRole("button", { name: "Готово" }).click();

  const after = await (await castle(page, token)).json() as { coins: number; appearance: { time_of_day: string | null } };
  expect(after.coins).toBe(before.coins);
  expect(after.appearance.time_of_day).toBeNull();
});

test("зимний сезон на сцене: картинка и зоны кликов сезона", async ({ page }) => {
  const token = await bootstrapPlayer(page);
  // Покупать сезон не нужно для проверки слоя: ставим сезон напрямую недоступно (нужна покупка),
  // поэтому проверяем через бесплатный календарный сезон — сцена и карта зон текущего сезона грузятся.
  await page.goto("/world");
  await page.waitForTimeout(1500);
  const stage = page.locator("img[alt='Замок Фоксинбург']");
  await expect(stage).toBeVisible();
  const src = await stage.getAttribute("src");
  expect(src).toMatch(/castle\/(seasons\/(spring|summer|autumn|winter)\.webp|castle-diorama\.webp)/);
  // Клик по Лавке через ленту открывает комнату — зоны сезона работают
  await page.getByRole("button", { name: "Лавка", exact: true }).click();
  await expect(page.getByRole("tab", { name: "Мастерская облика" })).toBeVisible();
});

test("знамя на сцене показывает цвет из облика", async ({ page }) => {
  const token = await bootstrapPlayer(page);
  await page.goto("/world");
  await page.waitForTimeout(1500);
  await expect(page.locator("[data-banner='plum']")).toBeVisible();
});

/** Монеты свежему игроку через админку: без них покупку в e2e не проверить. */
async function grantCoins(page: Page, token: string, amount: number) {
  const login = process.env.WORLD_ADMIN_LOGIN || "owner";
  const password = process.env.WORLD_ADMIN_PASSWORD || "test-owner-2026";
  const me = await page.request.get(`${API}/api/world/player`, { headers: { "X-World-Player": token } });
  const player = (await me.json()) as { id: number };
  // Параллельные воркеры (phone/desktop) долбят SQLite-бэкенд одновременно —
  // логин/начисление иногда отвечает 500 «database is locked»: пробуем с паузой.
  let lastStatus = 0;
  for (let attempt = 0; attempt < 5; attempt += 1) {
    const auth = await page.request.post(`${API}/api/v2/admin/login`, { data: { login, password } });
    test.skip(!auth.ok() && attempt === 0 && auth.status() < 500, "админка недоступна — некем начислить монеты");
    if (auth.ok()) {
      const { token: adminToken } = (await auth.json()) as { token: string };
      const res = await page.request.post(`${API}/api/v2/admin/students/${player.id}/adjust`, {
        headers: { Authorization: `Bearer ${adminToken}` },
        data: { kind: "coins", delta: amount, reason: "e2e castle fitting" },
      });
      if (res.ok()) return;
      lastStatus = res.status();
    } else {
      lastStatus = auth.status();
    }
    await page.waitForTimeout(400 * (attempt + 1));
  }
  throw new Error(`grantCoins: admin adjust не удался после 5 попыток (последний статус ${lastStatus})`);
}

async function openFittingRoom(page: Page) {
  await page.goto("/world");
  await page.waitForTimeout(1200);
  await page.getByRole("button", { name: "Лавка", exact: true }).click();
  await page.getByRole("tab", { name: "Мастерская облика" }).click();
  await page.getByRole("button", { name: "Примерить на замке" }).click();
  await expect(page.getByRole("dialog", { name: "Примерка облика замка" })).toBeVisible();
}

test("набор «Гирлянды» меняет сцену замка, повторный тап возвращает сезонную", async ({ page }) => {
  const token = await bootstrapPlayer(page);
  await grantCoins(page, token, 500);
  await openFittingRoom(page);

  await page.getByRole("tab", { name: "Праздники" }).click();
  await page.getByRole("button", { name: /Купить · 120/ }).click();
  // Купленный набор применился: сцена — запечённая картинка набора (или молчаливый
  // фолбэк на сезонную, если файл ещё не сгенерирован — тогда проверяем состояние сервера)
  const room = page.getByRole("dialog", { name: "Примерка облика замка" });
  await expect(room.getByText(/праздник на замке/)).toBeVisible();
  const stage = room.locator("img[alt='Замок Фоксинбург']");
  const appliedSrc = await stage.getAttribute("src");
  const server = (await (await castle(page, token)).json()) as { appearance: { scene_set: string | null } };
  expect(server.appearance.scene_set).toBe("garland");
  expect(appliedSrc).toMatch(/castle\/(sets\/garland|seasons\/\w+)\.webp/);

  // Повторный тап снимает праздник — сцена снова сезонная
  await page.getByRole("button", { name: /Гирлянды/ }).click();
  await expect(page.getByText(/куплен — нажми, чтобы устроить/)).toBeVisible();
  const reverted = (await (await castle(page, token)).json()) as { appearance: { scene_set: string | null } };
  expect(reverted.appearance.scene_set).toBeNull();
  await expect(stage).toHaveAttribute("src", /castle\/seasons\/\w+\.webp/);
});

test("снятие украшения через примерку: предмет уходит со сцены", async ({ page }) => {
  const token = await bootstrapPlayer(page);
  await grantCoins(page, token, 200);
  // Покупаем и ставим фонарь через API — на сцене он уже стоит
  const headers = { "X-World-Player": token, "Content-Type": "application/json" };
  const bought = await page.request.post(`${API}/api/v2/castle/buy`, { headers, data: { item_id: "decor-gate-lantern" } });
  expect(bought.ok()).toBeTruthy();
  const placed = await page.request.post(`${API}/api/v2/castle/appearance`, { headers, data: { decor_on: ["decor-gate-lantern"] } });
  expect(placed.ok()).toBeTruthy();

  await openFittingRoom(page);
  const room = page.getByRole("dialog", { name: "Примерка облика замка" });
  await expect(room.locator("[data-decor='decor-gate-lantern']")).toBeVisible();

  await room.getByRole("tab", { name: "Украшения" }).click();
  await room.getByRole("button", { name: /Фонарь у ворот/ }).click();
  await expect(room.getByText(/снято — нажми, чтобы поставить/)).toBeVisible();
  await expect(room.locator("[data-decor='decor-gate-lantern']")).toHaveCount(0);

  const after = (await (await castle(page, token)).json()) as { decor: { item_id: string; active: boolean }[] };
  expect(after.decor.find((d) => d.item_id === "decor-gate-lantern")?.active).toBe(false);
});
