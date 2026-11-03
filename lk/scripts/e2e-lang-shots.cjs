// Скриншоты Этапа 5: переключатель RU/EN (Экран входа + основные страницы).
const { chromium } = require("/Users/grigory/Dymova-english/world/node_modules/playwright");

const PHONE = "+79999996707";

async function getToken() {
  const res = await fetch("http://127.0.0.1:8010/api/lk/auth/confirm-bot", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone: PHONE }),
  });
  const body = await res.json();
  if (!body.token) throw new Error("no token: " + JSON.stringify(body));
  return body.token;
}

(async () => {
  const browser = await chromium.launch();
  const errors = [];
  const token = await getToken();
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  page.on("pageerror", (e) => errors.push("page: " + e));
  page.on("console", (m) => m.type() === "error" && errors.push("console: " + m.text()));

  // 1. Экран входа: RU по умолчанию → переключение на EN
  await page.goto("http://localhost:7100/auth", { waitUntil: "networkidle" });
  await page.waitForTimeout(400);
  await page.screenshot({ path: "/tmp/lk_auth_ru.png" });
  await page.click('.lang-chip:has-text("EN")');
  await page.waitForTimeout(300);
  await page.screenshot({ path: "/tmp/lk_auth_en.png" });

  // 2. EN: дашборд, расписание, словари, Мир (токен + язык в localStorage)
  await page.evaluate(
    ([tok]) => {
      window.localStorage.setItem("lk_token", tok);
      window.localStorage.setItem("lk_lang", "en");
    },
    [token],
  );
  for (const [route, shot] of [
    ["/dashboard", "lk_dash_en"],
    ["/schedule", "lk_sched_en"],
    ["/words", "lk_words_en"],
    ["/world", "lk_world_en"],
  ]) {
    await page.goto(`http://localhost:7100${route}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(900);
    await page.screenshot({ path: `/tmp/${shot}.png`, fullPage: true });
    console.log(shot, "url:", page.url());
  }

  // 3. Обратно на RU через переключатель (world page)
  await page.click('.lang-chip:has-text("RU")');
  await page.waitForTimeout(400);
  await page.screenshot({ path: "/tmp/lk_world_ru_back.png", fullPage: true });
  console.log("lang after RU click:", await page.evaluate(() => window.localStorage.getItem("lk_lang")));

  await browser.close();
  console.log("errors:", errors.length ? errors : "none");
})();
