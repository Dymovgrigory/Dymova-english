import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { ApiError } from "@/lib/api";
import { adminApi, adminToken, clearAdminToken, rememberAdminToken } from "./admin";

const store = new Map<string, string>();
const localStorageMock = {
  getItem: (k: string) => store.get(k) ?? null,
  setItem: (k: string, v: string) => void store.set(k, v),
  removeItem: (k: string) => void store.delete(k),
};

function mockFetch(body: unknown, status = 200) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(body), { status })),
  );
}

function lastCall(): [string, RequestInit] {
  const calls = (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls;
  return calls[calls.length - 1] as [string, RequestInit];
}

describe("adminApi", () => {
  beforeEach(() => {
    store.clear();
    vi.stubGlobal("localStorage", localStorageMock);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("login сохраняет токен в localStorage", async () => {
    mockFetch({ token: "adm.t1", role: "admin", login: "boss" });
    const res = await adminApi.login("boss", "secret");
    expect(res.token).toBe("adm.t1");
    expect(adminToken()).toBe("adm.t1");
    const [url, init] = lastCall();
    expect(String(url)).toContain("/api/v2/admin/login");
    expect(JSON.parse(String(init.body))).toEqual({ login: "boss", password: "secret" });
  });

  it("401 на me чистит токен и пробрасывает ApiError", async () => {
    rememberAdminToken("adm.dead");
    mockFetch({ detail: "admin_unauthorized" }, 401);
    await expect(adminApi.me()).rejects.toMatchObject({ status: 401 });
    expect(adminToken()).toBe("");
  });

  it("students собирает query-string и шлёт Bearer", async () => {
    rememberAdminToken("adm.t2");
    mockFetch({ items: [], total: 0, page: 2, per_page: 20 });
    await adminApi.students({ q: "иван", class_grade: 5, verified: true, page: 2 });
    const [url, init] = lastCall();
    const u = new URL(String(url), "http://x");
    expect(u.pathname).toBe("/api/v2/admin/students");
    expect(u.searchParams.get("q")).toBe("иван");
    expect(u.searchParams.get("class_grade")).toBe("5");
    expect(u.searchParams.get("verified")).toBe("true");
    expect(u.searchParams.get("page")).toBe("2");
    expect(u.searchParams.get("per_page")).toBe("20");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer adm.t2");
  });

  it("adjust шлёт kind, delta и reason", async () => {
    mockFetch({ coins: 90, xp: 10 });
    await adminApi.adjust(7, "coins", -10, "списание за нарушение");
    const [url, init] = lastCall();
    expect(String(url)).toContain("/api/v2/admin/students/7/adjust");
    expect(JSON.parse(String(init.body))).toEqual({
      kind: "coins",
      delta: -10,
      reason: "списание за нарушение",
    });
  });

  it("player_not_found пробрасывается как ApiError 404", async () => {
    mockFetch({ detail: "player_not_found" }, 404);
    const err = await adminApi.student(999).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(404);
    expect(err.message).toBe("player_not_found");
  });

  it("patchIdentity шлёт поля и обязательную reason", async () => {
    mockFetch({ identity: { first_name: "Иван" } });
    await adminApi.patchIdentity(3, { first_name: "Иван" }, "просьба родителя");
    const [url, init] = lastCall();
    expect(String(url)).toContain("/api/v2/admin/students/3");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(String(init.body))).toEqual({ first_name: "Иван", reason: "просьба родителя" });
  });

  it("logout чистит токен", async () => {
    rememberAdminToken("adm.t3");
    mockFetch({ ok: true });
    await adminApi.logout();
    expect(adminToken()).toBe("");
    clearAdminToken();
  });
});
