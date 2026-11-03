// Скриншоты Этапа 3: библиотека словарей + тренировка (десктоп/мобайл).
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
  await page.goto("http://localhost:7100/words", { waitUntil: "networkidle" });
  await page.waitForTimeout(900);
  await page.screenshot({ path: "/tmp/lk_words_desktop.png", fullPage: true });

  // Первая карточка набора → тренировка
  await page.click(".set-train-btn");
  await page.waitForTimeout(1500);
  await page.screenshot({ path: "/tmp/lk_train_desktop.png" });
  // Клик по варианту ответа
  await page.click(".train-opt >> nth=0");
  await page.waitForTimeout(400);
  await page.screenshot({ path: "/tmp/lk_train_answer.png" });
  await page.close();

  const mob = await browser.newPage({ viewport: { width: 390, height: 844 } });
  mob.on("pageerror", (e) => errors.push("mobile: " + e));
  await login(mob);
  await mob.goto("http://localhost:7100/words", { waitUntil: "networkidle" });
  await mob.waitForTimeout(900);
  await mob.screenshot({ path: "/tmp/lk_words_mobile.png", fullPage: true });
  await mob.click(".set-train-btn");
  await mob.waitForTimeout(1500);
  await mob.screenshot({ path: "/tmp/lk_train_mobile.png" });
  await mob.close();

  await browser.close();
  console.log("errors:", errors.length ? errors : "none");
})();
