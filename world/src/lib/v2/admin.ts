/** Клиент админ-панели участников (/api/v2/admin). Авторизация — Bearer-токен в localStorage. */
import { ApiError } from "@/lib/api";

const API = (process.env.NEXT_PUBLIC_WORLD_API || "").replace(/\/$/, "");
const TIMEOUT_MS = 12000;
const TOKEN_KEY = "world.adminToken";

export function adminToken(): string {
  try {
    return globalThis.localStorage?.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

export function rememberAdminToken(token: string): void {
  try {
    globalThis.localStorage?.setItem(TOKEN_KEY, token);
  } catch {
    /* приватный режим — токен живёт только в памяти вкладки */
  }
}

export function clearAdminToken(): void {
  try {
    globalThis.localStorage?.removeItem(TOKEN_KEY);
  } catch {
    /* окружение без localStorage */
  }
}

export type AdminLoginResult = { token: string; role: string; login: string };
export type AdminMe = { login: string; role: string };

export type AdminStudentRow = {
  player_id: number;
  display_name: string;
  first_name: string | null;
  last_name: string | null;
  class_grade: number | null;
  school_number: string | null;
  phone_masked: string | null;
  phone_verified: boolean;
  xp: number;
  coins: number;
  streak_days: number;
  last_active_day: string | null;
};

export type AdminStudentList = { items: AdminStudentRow[]; total: number; page: number; per_page: number };

export type AdminIdentity = {
  first_name: string | null;
  last_name: string | null;
  birth_date: string | null;
  school_number: string | null;
  class_grade: number | null;
  class_letter: string | null;
  parent_email: string | null;
  parent_phone_masked: string | null;
  phone_verified: boolean;
};

export type AdminConsent = { type: string; version: string; accepted_at: string };
export type AdminProfile = { book_id: string | null; module_id: string | null; daily_goal_xp: number | null };
export type AdminTitle = { track: string; level: number; title_ru: string | null; worn: boolean };
export type AdminWeakAtom = { atom_id: string; strength: number; wrong_count: number };
export type AdminMistake = { unit_id: string; item: string };
export type AdminDayActivity = { day: string; xp: number; sessions: number };

export type AdminStudentDetail = {
  player: {
    id: number;
    display_name: string;
    xp: number;
    coins: number;
    level: number;
    streak_days: number;
    hearts?: number;
    [key: string]: unknown;
  };
  identity: AdminIdentity | null;
  consents: AdminConsent[];
  profile: AdminProfile | null;
  titles: AdminTitle[];
  weakest_atoms: AdminWeakAtom[];
  mistakes: AdminMistake[];
  daily_activity: AdminDayActivity[];
  counters: { inventory: number; castle_owned: number; sessions_total: number };
};

export type AdminAuditItem = {
  actor: string;
  action: string;
  entity: string;
  payload: unknown;
  created_at: string;
};

export type StudentsQuery = {
  q?: string;
  class_grade?: number;
  verified?: boolean;
  page?: number;
  per_page?: number;
};

export type IdentityPatch = Partial<{
  first_name: string;
  last_name: string;
  birth_date: string;
  school_number: string;
  class_grade: number;
  class_letter: string;
  parent_email: string;
}>;

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(`${API}${path}`, {
      ...init,
      cache: "no-store",
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${adminToken()}`,
        ...(init?.headers ?? {}),
      },
    });
    if (!res.ok) {
      let detail = `${res.status}`;
      try {
        const body = (await res.json()) as { detail?: string };
        if (typeof body.detail === "string") detail = body.detail;
      } catch {
        /* пустое тело ответа */
      }
      throw new ApiError(res.status, detail);
    }
    return (await res.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

export const adminApi = {
  login: (login: string, password: string) =>
    call<AdminLoginResult>("/api/v2/admin/login", {
      method: "POST",
      body: JSON.stringify({ login, password }),
    }).then((res) => {
      rememberAdminToken(res.token);
      return res;
    }),

  logout: async () => {
    try {
      await call<{ ok: boolean }>("/api/v2/admin/logout", { method: "POST" });
    } finally {
      clearAdminToken();
    }
  },

  me: async () => {
    try {
      return await call<AdminMe>("/api/v2/admin/me");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) clearAdminToken();
      throw err;
    }
  },

  students: (query: StudentsQuery = {}) => {
    const params = new URLSearchParams();
    if (query.q) params.set("q", query.q);
    if (query.class_grade != null) params.set("class_grade", String(query.class_grade));
    if (query.verified != null) params.set("verified", query.verified ? "true" : "false");
    params.set("page", String(query.page ?? 1));
    params.set("per_page", String(query.per_page ?? 20));
    return call<AdminStudentList>(`/api/v2/admin/students?${params.toString()}`);
  },

  student: (id: number | string) => call<AdminStudentDetail>(`/api/v2/admin/students/${id}`),

  patchIdentity: (id: number | string, patch: IdentityPatch, reason: string) =>
    call<{ identity: AdminIdentity }>(`/api/v2/admin/students/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ ...patch, reason }),
    }),

  adjust: (id: number | string, kind: "coins" | "xp", delta: number, reason: string) =>
    call<{ coins: number; xp: number }>(`/api/v2/admin/students/${id}/adjust`, {
      method: "POST",
      body: JSON.stringify({ kind, delta, reason }),
    }),

  mastery: (id: number | string, atomId: string, action: "reset" | "master", reason: string) =>
    call<{ ok: boolean }>(`/api/v2/admin/students/${id}/mastery`, {
      method: "POST",
      body: JSON.stringify({ atom_id: atomId, action, reason }),
    }),

  items: (id: number | string, itemId: string, action: "grant" | "revoke", reason: string) =>
    call<{ ok: boolean }>(`/api/v2/admin/students/${id}/items`, {
      method: "POST",
      body: JSON.stringify({ item_id: itemId, action, reason }),
    }),

  audit: (playerId?: number | string, limit = 50) => {
    const params = new URLSearchParams();
    if (playerId != null) params.set("player_id", String(playerId));
    params.set("limit", String(limit));
    return call<{ items: AdminAuditItem[] }>(`/api/v2/admin/audit?${params.toString()}`);
  },
};
