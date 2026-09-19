import { expect, test, type Page } from "@playwright/test";

import { bootstrapRegisteredPlayer } from "./helpers";

/** Свежий зарегистрированный игрок: гейт регистрации не пускает в мир без анкеты. */
const bootstrapPlayer = bootstrapRegisteredPlayer;

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
