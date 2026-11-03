// Скриншоты Этапа 4: Мир Фоксинбурга в ЛК + SSO (десктоп/мобайл).
const { chromium } = require("/Users/grigory/Dymova-english/world/node_modules/playwright");

const PHONE = "+79999996707";

async function login(page) {
  await page.goto("http://localhost:7100/auth", { waitUntil: "networkidle" });
  await page.fill('input[type="tel"]', PHONE);
  await page.fill('input[type="text"]', "Тестовый Родитель");
  const checks = page.locator(".consent input");
  const n = await checks.count();
  for (let i = 0; i < n; i++) await checks.nth(i).check();
  await page.click('button[type="submit"]');
  await page.waitForURL(/confirm/, { timeout: 15000 });
  await page.click('button:has-text("Проверить подтверждение")');
  await page.waitForURL(/dashboard/, { timeout: 15000 });
}

(async () => {
  const browser = await chromium.launch();
  const errors = [];

  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  page.on("pageerror", (e) => errors.push("desktop: " + e));
  page.on("console", (m) => m.type() === "error" && errors.push("console: " + m.text()));
  await login(page);
  await page.goto("http://localhost:7100/world", { waitUntil: "networkidle" });
  await page.waitForTimeout(900);
  await page.screenshot({ path: "/tmp/lk_world_desktop.png", fullPage: true });

  // SSO: клик по «Войти в Мир» открывает новую вкладку Мира
  const [worldTab] = await Promise.all([
    page.waitForEvent("popup", { timeout: 15000 }),
    page.click('button:has-text("Войти в Мир Фоксинбурга")'),
  ]);
  worldTab.on("pageerror", (e) => errors.push("world: " + e));
  await worldTab.waitForLoadState("networkidle");
  await worldTab.waitForTimeout(1200);
  console.log("URL после SSO:", worldTab.url());
  await worldTab.screenshot({ path: "/tmp/world_onboarding.png", fullPage: true });

  // Онбординг: класс → модуль → цель → первый урок
  await worldTab.locator("main button").first().click(); // выбор класса
  await worldTab.waitForTimeout(400);
  await worldTab.getByRole("button", { name: "Дальше", exact: true }).click();
  await worldTab.waitForTimeout(500);
  await worldTab.locator("main button").first().click(); // выбор модуля
  await worldTab.waitForTimeout(400);
  await worldTab.getByRole("button", { name: "Дальше", exact: true }).click();
  await worldTab.waitForTimeout(500);
  await worldTab.screenshot({ path: "/tmp/world_onboarding_goal.png", fullPage: true });
  await worldTab.getByRole("button", { name: /Начать первый урок/ }).click();
  await worldTab.waitForTimeout(2500);
  console.log("URL после онбординга:", worldTab.url());
  await worldTab.screenshot({ path: "/tmp/world_after_sso.png", fullPage: true });

  // Обратно в ЛК: прогресс Мира теперь связан
  await page.bringToFront();
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForTimeout(900);
  await page.screenshot({ path: "/tmp/lk_world_linked.png", fullPage: true });
  await page.close();
  await worldTab.close();

  const mob = await browser.newPage({ viewport: { width: 390, height: 844 } });
  mob.on("pageerror", (e) => errors.push("mobile: " + e));
  await login(mob);
  await mob.goto("http://localhost:7100/world", { waitUntil: "networkidle" });
  await mob.waitForTimeout(900);
  await mob.screenshot({ path: "/tmp/lk_world_mobile.png", fullPage: true });
  await mob.close();

  await browser.close();
  console.log("errors:", errors.length ? errors : "none");
})();
