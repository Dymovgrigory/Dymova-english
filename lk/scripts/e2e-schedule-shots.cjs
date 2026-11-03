// Скриншоты Этапа 2: дашборд + расписание (десктоп и 390px).
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

  // Десктоп
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  page.on("pageerror", (e) => errors.push("desktop: " + e));
  await login(page);
  await page.waitForTimeout(600);
  await page.screenshot({ path: "/tmp/lk_dashboard_desktop.png", fullPage: true });
  await page.goto("http://localhost:7100/schedule", { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  await page.screenshot({ path: "/tmp/lk_schedule_desktop.png", fullPage: true });
  await page.click('button:has-text("Неделя назад")');
  await page.waitForTimeout(800);
  await page.screenshot({ path: "/tmp/lk_schedule_past.png", fullPage: true });
  await page.close();

  // Мобильный 390px
  const mob = await browser.newPage({ viewport: { width: 390, height: 844 } });
  mob.on("pageerror", (e) => errors.push("mobile: " + e));
  await login(mob);
  await mob.waitForTimeout(600);
  await mob.screenshot({ path: "/tmp/lk_schedule_mobile_empty.png" });
  await mob.goto("http://localhost:7100/schedule", { waitUntil: "networkidle" });
  await mob.waitForTimeout(800);
  await mob.screenshot({ path: "/tmp/lk_schedule_mobile.png", fullPage: true });
  await mob.close();

  await browser.close();
  console.log("errors:", errors.length ? errors : "none");
})();
