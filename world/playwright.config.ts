import { defineConfig, devices } from "@playwright/test";

const ui = process.env.WORLD_E2E_UI === "1";

export default defineConfig({
  testDir: "./e2e",
  timeout: 45_000,
  use: { baseURL: process.env.WORLD_APP || "http://127.0.0.1:3002" },
  // UI-тест тянет браузер — без WORLD_E2E_UI=1 оставляем только API-смоук.
  grep: ui ? undefined : /API/,
  projects: [
    { name: "phone", use: { ...devices["iPhone 13"], browserName: "chromium" } },
    { name: "desktop", use: { viewport: { width: 1440, height: 900 } } },
  ],
});
