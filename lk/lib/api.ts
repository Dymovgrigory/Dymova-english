export type Consent = { type: string; version: string };
export type Profile = {
  id: number;
  student_id: number | null;
  child_name: string;
  source: string;
  active_groups: { id: number; caption: string }[];
};
export type Lesson = {
  id: number;
  date: string;
  starts_at: string;
  ends_at: string;
  group: { id: number; caption: string };
  filial: { id: number; caption: string };
  attendance: "visited" | "missed" | "unknown";
};
export type Schedule = {
  student_id: number;
  child_name: string;
  from: string;
  to: string;
  lessons: Lesson[];
};
export type WordSetProgress = {
  total: number;
  seen: number;
  learned: number;
  due: number;
};
export type WordSet = {
  id: number;
  code: string;
  title: string;
  kind: string;
  book: string;
  cefr: string;
  topic: string;
  is_public: boolean;
  progress: WordSetProgress;
};
export type WordCard = {
  id: number;
  text_en: string;
  transcription: string;
  image_url: string;
  audio_url: string;
  position: number;
  strength?: number | null;
  distractors: string[];
};
export type Training = {
  set_id: number;
  child_name: string;
  cards: WordCard[];
  answers: Record<number, string>;
  review_count: number;
  new_count: number;
};
export type WordStats = {
  seen_words: number;
  learned_words: number;
  due_today: number;
  answers_total: number;
  answers_correct: number;
};
export type WorldProgress = {
  linked: boolean;
  child_name: string;
  display_name?: string;
  level?: number;
  xp?: number;
  coins?: number;
  streak_days?: number;
  tracks?: { track: string; level: number }[];
  league?: { rank: number; weekly_xp: number } | null;
};
export type WorldSession = {
  session: string;
  external_key: string;
  display_name: string;
};

export const WORLD_URL =
  process.env.NEXT_PUBLIC_WORLD_URL || "http://localhost:3000";
export type SessionOut = {
  status: string;
  token?: string | null;
  profiles?: Profile[];
  guest?: boolean;
  phone_masked: string;
};

export const CONSENT_VERSION = "2026-11-02";

async function request<T>(
  path: string,
  options: { method?: string; body?: unknown; token?: string | null } = {},
): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (options.token) headers["Authorization"] = `Bearer ${options.token}`;
  const res = await fetch(path, {
    method: options.method || "GET",
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error((data as { detail?: string }).detail || `HTTP ${res.status}`) as Error & {
      status: number;
      code: string;
    };
    err.status = res.status;
    err.code = String((data as { detail?: string }).detail || res.status);
    throw err;
  }
  return data as T;
}

export const api = {
  start: (phone: string, parent_name: string, consents: Consent[]) =>
    request<SessionOut>("/api/lk/auth/start", {
      method: "POST",
      body: { phone, parent_name, consents },
    }),
  status: (phone: string) =>
    request<{ status: string; phone_masked: string }>(
      `/api/lk/auth/status?phone=${encodeURIComponent(phone)}`,
    ),
  confirmBot: (phone: string) =>
    request<SessionOut>("/api/lk/auth/confirm-bot", {
      method: "POST",
      body: { phone },
    }),
  me: (token: string) =>
    request<{ account: Record<string, unknown>; profiles: Profile[] }>("/api/lk/me", {
      token,
    }),
  schedule: (token: string, studentId: number, dateFrom: string, dateTo: string) =>
    request<Schedule>(
      `/api/lk/schedule?student_id=${studentId}&date_from=${encodeURIComponent(dateFrom)}&date_to=${encodeURIComponent(dateTo)}`,
      { token },
    ),
  // ---------- тренажёр слов ----------
  wordSets: (token: string, studentId: number) =>
    request<{ student_id: number; child_name: string; sets: WordSet[] }>(
      `/api/lk/words/sets?student_id=${studentId}`,
      { token },
    ),
  wordStats: (token: string, studentId: number) =>
    request<WordStats>(`/api/lk/words/stats?student_id=${studentId}`, { token }),
  startTraining: (token: string, studentId: number, setId: number) =>
    request<Training>("/api/lk/words/train", {
      method: "POST",
      token,
      body: { student_id: studentId, set_id: setId },
    }),
  wordAnswer: (token: string, studentId: number, wordId: number, correct: boolean) =>
    request<{ status: string; strength: number }>("/api/lk/words/answer", {
      method: "POST",
      token,
      body: { student_id: studentId, word_id: wordId, correct },
    }),
  // ---------- Мир Фоксинбурга (Этап 4) ----------
  worldSession: (token: string, studentId: number) =>
    request<WorldSession>("/api/lk/world/session", {
      method: "POST",
      token,
      body: { student_id: studentId },
    }),
  worldProgress: (token: string, studentId: number) =>
    request<WorldProgress>(
      `/api/lk/world/progress?student_id=${studentId}`,
      { token },
    ),
  /** Озвучка слова: fetch с Bearer → blob → objectURL (audio-тег не шлёт заголовки). */
  async speak(token: string, text: string): Promise<string> {
    const res = await fetch(
      `/api/lk/words/tts?q=${encodeURIComponent(text)}`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    if (!res.ok) throw new Error(`tts ${res.status}`);
    return URL.createObjectURL(await res.blob());
  },
  logout: (token: string) =>
    request<{ status: string }>("/api/lk/auth/logout", { method: "POST", token }),
};

/** Форматирование ввода телефона: цифры → +7 (916) 123-45-67. */
export function formatPhoneInput(raw: string): string {
  let digits = raw.replace(/\D/g, "");
  if (digits.startsWith("8")) digits = "7" + digits.slice(1);
  if (digits.startsWith("9") && digits.length <= 10) digits = "7" + digits;
  digits = digits.slice(0, 11);
  if (!digits) return "";
  const p = [digits.slice(1, 4), digits.slice(4, 7), digits.slice(7, 9), digits.slice(9, 11)]
    .map((s) => s || "")
    .filter(Boolean);
  let out = "+7";
  if (p[0]) out += ` (${p[0]}`;
  if (p[0] && p[0].length === 3) out += ")";
  if (p[1]) out += ` ${p[1]}`;
  if (p[2]) out += `-${p[2]}`;
  if (p[3]) out += `-${p[3]}`;
  return out;
}

export function phoneComplete(formatted: string): boolean {
  return formatted.replace(/\D/g, "").length === 11;
}
