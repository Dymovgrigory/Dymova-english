import { expect, test } from "@playwright/test";

test("мастерская облика: покупка и применение", async ({ page }) => {
  await page.goto("/world");
  await page.waitForTimeout(1200);
  await page.locator('[data-spot="shop"]').click();

  await page.getByRole("button", { name: "Мастерская облика" }).click();
  const night = page.getByRole("button", { name: /Ночь/ });
  await expect(night).toBeVisible();

  // Без монет покупка недоступна, и сервер говорит почему
  await night.click();
  await expect(page.getByText("Не хватает монет")).toBeVisible();
});

test("закрытая вещь показывает условие", async ({ page }) => {
  await page.goto("/world");
  await page.waitForTimeout(1200);
  await page.locator('[data-spot="shop"]').click();
  await page.getByRole("button", { name: "Мастерская облика" }).click();
  await expect(page.getByText(/Словесник/)).toBeVisible();
});
