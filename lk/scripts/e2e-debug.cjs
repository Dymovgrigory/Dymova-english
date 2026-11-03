const { chromium } = require("/Users/grigory/Dymova-english/world/node_modules/playwright");

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 860 } });
  const logs = [];
  page.on("pageerror", (e) => logs.push("PAGEERROR: " + String(e)));
  page.on("console", (m) => logs.push(m.type() + ": " + m.text()));
  page.on("requestfailed", (r) => logs.push("REQFAIL: " + r.url() + " " + (r.failure() || {}).errorText));
  page.on("response", (r) => r.status() >= 400 && logs.push("HTTP" + r.status() + ": " + r.url()));

  await page.goto("http://127.0.0.1:7100/auth", { waitUntil: "networkidle" });
  await page.fill('input[type="tel"]', "8 916 123-45-67");
  await page.fill('input[type="text"]', "Ольга Иванова");
  await page.check('input[type="checkbox"] >> nth=0');
  await page.check('input[type="checkbox"] >> nth=1');
  await page.click('button[type="submit"]');
  await page.waitForTimeout(4000);
  console.log("URL after submit:", page.url());
  const alert = await page.$(".alert");
  console.log("alert:", alert ? await alert.innerText() : "none");
  console.log("logs:\n" + logs.join("\n"));
  await browser.close();
})();
