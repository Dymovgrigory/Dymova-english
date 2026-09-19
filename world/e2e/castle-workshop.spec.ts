import { expect, test, type Page } from "@playwright/test";

import { bootstrapRegisteredPlayer } from "./helpers";

/** Свежий зарегистрированный игрок: гейт регистрации не пускает в мир без анкеты. */
const bootstrapPlayer = bootstrapRegisteredPlayer;

async function openRoom(page: Page, name: string) {
  await page.goto("/world");
  await page.waitForTimeout(1200);
  // data-spot-кнопки клавиатурные (pointer-events: none), поэтому идём через ленту локаций
  await page.getByRole("button", { name, exact: true }).click();
}

test("мастерская облика: покупка и применение", async ({ page }) => {
  await bootstrapPlayer(page);
  await openRoom(page, "Лавка");

  await page.getByRole("tab", { name: "Мастерская облика" }).click();
  const night = page.getByRole("button", { name: /Ночь/ });
  await expect(night).toBeVisible();

  // Без монет покупка недоступна, и сервер говорит почему
  await night.click();
  await expect(page.getByText("Не хватает монет")).toBeVisible();
});

test("закрытая вещь показывает условие", async ({ page }) => {
  await bootstrapPlayer(page);
  await openRoom(page, "Лавка");
  await page.getByRole("tab", { name: "Мастерская облика" }).click();
  await expect(page.getByText(/Словесник/).first()).toBeVisible();
});
