import { expect, test, type Page } from "@playwright/test";

import { bootstrapRegisteredPlayer } from "./helpers";

/** Свежий зарегистрированный игрок: гейт регистрации не пускает в мир без анкеты. */
const bootstrapPlayer = bootstrapRegisteredPlayer;

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
