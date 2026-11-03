const { chromium } = require("/Users/grigory/Dymova-english/world/node_modules/playwright");

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 860 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));

  await page.goto("http://127.0.0.1:7100/auth", { waitUntil: "networkidle" });
  await page.fill('input[type="tel"]', "8 916 123-45-67");
  await page.fill('input[type="text"]', "Ольга Иванова");
  await page.check('input[type="checkbox"] >> nth=0');
  await page.check('input[type="checkbox"] >> nth=1');
  await page.click('button[type="submit"]');
  await page.waitForURL("**/auth/confirm", { timeout: 15000 });
  await page.waitForTimeout(1200);
  await page.screenshot({ path: "/tmp/lk2_confirm.png" });

  await page.click("text=Проверить подтверждение");
  await page.waitForURL("**/dashboard", { timeout: 15000 });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: "/tmp/lk2_dashboard.png" });

  // Мобильный вид дашборда
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(600);
  await page.screenshot({ path: "/tmp/lk2_dashboard_mobile.png" });

  console.log("errors:", errors.length ? errors : "none");
  await browser.close();
})();
