import { expect, test } from "@playwright/test";

test("в Гнезде видно пять веток званий и прогресс", async ({ page }) => {
  await page.goto("/world");
  await page.waitForTimeout(1200);
  await page.locator('[data-spot="nest"]').click();

  for (const track of ["Словесник", "Тренер", "Хранитель огня", "Чемпион", "Собиратель"]) {
    await expect(page.getByText(track, { exact: false })).toBeVisible();
  }
});

test("звание без уровня надеть нельзя", async ({ page }) => {
  await page.goto("/world");
  await page.waitForTimeout(1200);
  await page.locator('[data-spot="nest"]').click();
  const wear = page.getByRole("button", { name: /Носить/ }).first();
  await expect(wear).toBeDisabled();
});
