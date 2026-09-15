import { expect, test } from "@playwright/test";

const API = process.env.WORLD_API || "http://127.0.0.1:8010";
const APP = process.env.WORLD_APP || "http://127.0.0.1:3002";
const KEY = "e2e-child";

test("урок проходит от старта до финиша по API", async ({ request }) => {
  const headers = { "X-World-Player": KEY, "Content-Type": "application/json" };
  const player = await request.post(`${API}/api/world/players`, {
    headers,
    data: { display_name: "Ева" },
  });
  expect(player.ok()).toBeTruthy();

  const review = await request.get(`${API}/api/world/learn/review`, { headers });
  expect(review.ok()).toBeTruthy();

  const league = await request.get(`${API}/api/world/learn/league`, { headers });
  expect(league.ok()).toBeTruthy();
  const leagueBody = await league.json();
  expect(leagueBody.rank).toBeGreaterThan(0);
  expect(leagueBody.size).toBeGreaterThan(0);

  const started = await request.post(`${API}/api/world/learn/lessons/start`, {
    headers,
    data: { lesson_id: "family-L1" },
  });
  expect(started.ok()).toBeTruthy();
  const session = await started.json();
  expect(session.total).toBeGreaterThan(6);
  expect(session.items?.length).toBe(session.total);

  // Первые карточки (explain / word) — всегда верные; дальше стопаемся на первом drill.
  for (const item of session.items.slice(0, 6)) {
    const value =
      item.kind === "listen"
        ? {
            choice: Math.max(
              0,
              (item.options as string[]).findIndex(
                (o) => String(o).toLowerCase() === String(item.speak || "").toLowerCase(),
              ),
            ),
          }
        : {};
    const ans = await request.post(
      `${API}/api/world/learn/sessions/${session.session_id}/answer`,
      { headers, data: { index: item.index, value } },
    );
    expect(ans.ok()).toBeTruthy();
    const body = await ans.json();
    expect(body.correct).toBeTruthy();
  }

  const health = await request.get(`${API}/health`);
  expect(health.ok()).toBeTruthy();
});


test("замок открывается", async ({ page }) => {
  await page.goto(`${APP}/world`);
  await expect(page.getByRole("heading", { name: /Замок/ })).toBeVisible();
});
