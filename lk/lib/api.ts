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
  icon?: string;
  color?: string;
  preview?: string[];
};
export type PoolWord = { id: number; text_en: string; text_ru: string; image_url: string; example_en?: string };
export type Rank = { index: number; total: number; title: string; from: number; to: number; next_title: string; learned: number };
export type Quest = { code: string; title: string; progress: number; target: number; done: boolean; claimed: boolean; reward: number };
export type Postcard = { topic: string; title: string; set_id: number; total: number; learned: number; cover: string; percent: number; unlocked: boolean };
export type CambridgeMedal = { code: string; name: string; cefr: string; set_id: number; total: number; learned: number; percent: number; earned: boolean };
/** Награды «Фоксинбурга»: монеты Мира, звание, календарь, сундук недели, задание дня, коллекция. */
export type GameStats = {
  coins_today: number;
  coins_earned: number;
  wallet: number;
  learned_words: number;
  rank: Rank;
  days_total: number;
  month: { year: number; month: number; days: { day: string; active: boolean; coins: number }[]; active_days: number };
  week: { days: { day: string; active: boolean }[]; active_days: number; need: number; chest_ready: boolean; chest_claimed: boolean; reward: number };
  quest: Quest;
  postcards: Postcard[];
  postcards_unlocked: number;
  medals: CambridgeMedal[];
  collection_cards?: { id: string; title: string; rarity: string; condition: string }[];
  collection_total?: number;
  achievements?: { id: string; title: string; unlocked: boolean }[];
};
export type MyWord = SetWord & { strength: number; mistakes: number };
export type SetWord = {
  id: number;
  text_en: string;
  text_ru: string;
  example_en?: string;
  transcription: string;
  image_url: string;
  strength?: number | null;
};
export type WordCard = {
  id: number;
  text_en: string;
  transcription: string;
  image_url: string;
  audio_url: string;
  example_en?: string;
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
  pool?: PoolWord[];
  pool_far?: PoolWord[];
  icon?: string;
  color?: string;
  code?: string;
  title?: string;
  topic?: string;
};
export type LearningUnit = {
  id: string;
  level: "pre-a1" | "a1" | "a2" | "b1";
  topic: string;
  title_ru: string;
  title_en: string;
  skills: string[];
  order: number;
};
export type LearningChallenge = {
  id: string; index: number; kind: string; prompt: string; options: string[]; graded: boolean; audio?: string;
};
export type LearningSession = {
  session_id: string; unit: LearningUnit; challenges: LearningChallenge[]; graded_total: number;
};
export type LearningAnswer = { correct: boolean; attempt_no: number; remaining: number; solution: string | null };
export type LearningResult = { session_id: string; unit_id: string; accuracy: number; attempts: number; correct: number; points: number };
export type LearningRank = { index: number; title: string; points: number; next_title: string; next_points: number | null };
export type WordStats = {
  seen_words: number;
  learned_words: number;
  due_today: number;
  answers_total: number;
  answers_correct: number;
} & Partial<GameStats>;
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
  login: (phone: string, password: string) =>
    request<SessionOut>("/api/lk/auth/login", { method: "POST", body: { phone, password } }),
  register: (body: { phone: string; password: string; parent_name: string; child_name: string; child_age: string; consents: Consent[] }) =>
    request<SessionOut & { crm_lead?: boolean }>("/api/lk/auth/register", { method: "POST", body }),
  setPassword: (token: string, password: string) =>
    request<{ status: string }>("/api/lk/auth/password", { method: "POST", token, body: { password } }),
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
  learningCatalog: (token: string, level?: string, topic?: string) => request<{ units: LearningUnit[] }>(
    `/api/lk/learning/catalog?${new URLSearchParams({ ...(level ? { level } : {}), ...(topic ? { topic } : {}) }).toString()}`,
    { token },
  ),
  learningStart: (token: string, studentId: number, unitId: string) => request<LearningSession>("/api/lk/learning/sessions", {
    method: "POST", token, body: { student_id: studentId, unit_id: unitId },
  }),
  learningAnswer: (token: string, studentId: number, sessionId: string, challengeId: string, answer: Record<string, unknown>) =>
    request<LearningAnswer>(`/api/lk/learning/sessions/${sessionId}/answer`, {
      method: "POST", token, body: { student_id: studentId, challenge_id: challengeId, answer },
    }),
  learningFinish: (token: string, studentId: number, sessionId: string) => request<LearningResult>(`/api/lk/learning/sessions/${sessionId}/finish`, {
    method: "POST", token, body: { student_id: studentId },
  }),
  learningProgress: (token: string, studentId: number) => request<LearningRank>(`/api/lk/learning/progress?student_id=${studentId}`, { token }),
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
  wordAnswer: (token: string, studentId: number, wordId: number, correct: boolean, mode = "", eventKey = "") =>
    request<{ status: string; strength: number; coins?: number }>("/api/lk/words/answer", {
      method: "POST",
      token,
      body: { student_id: studentId, word_id: wordId, correct, mode, event_key: eventKey },
    }),
  wordFinish: (token: string, studentId: number, setId: number, correct: number, total: number) =>
    request<GameStats & { bonus_coins: number; perfect: boolean }>("/api/lk/words/finish", {
      method: "POST",
      token,
      body: { student_id: studentId, set_id: setId, correct, total },
    }),
  wordGoal: (token: string, studentId: number, goal: number) =>
    request<{ daily_goal: number }>("/api/lk/words/goal", {
      method: "POST",
      token,
      body: { student_id: studentId, goal },
    }),
  wordClaim: (token: string, studentId: number, kind: "quest" | "chest") =>
    request<GameStats & { coins: number }>("/api/lk/words/claim", {
      method: "POST",
      token,
      body: { student_id: studentId, kind },
    }),
  foxi: (token: string, studentId: number) =>
    request<{ foxi: FoxiLook | null }>(`/api/lk/words/foxi?student_id=${studentId}`, { token }),
  saveFoxi: (token: string, studentId: number, foxi: FoxiLook) =>
    request<{ foxi: FoxiLook }>("/api/lk/words/foxi", { method: "POST", token, body: { student_id: studentId, foxi } }),
  myWords: (token: string, studentId: number) =>
    request<{ words: MyWord[]; hard_ids: number[]; learned: number; learning: number }>(
      `/api/lk/words/my?student_id=${studentId}`,
      { token },
    ),
  setWords: (token: string, studentId: number, setId: number) =>
    request<{ set_id: number; words: SetWord[] }>(
      `/api/lk/words/sets/${setId}?student_id=${studentId}`,
      { token },
    ),
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

/** «Создай своего Фокси»: облик 3D-Фокси (движок — /public/foxi3d/foxi-studio.js). */
export type FoxiLook = {
  fur?: string; eyes?: string; top?: string; pattern?: string; patternColor?: string; logo?: boolean;
  bottom?: string; bag?: string; shoes?: string; hat?: string; hatColor?: string; hair?: string;
  glasses?: string; neck?: string; neckColor?: string; back?: string; scene?: string; name?: string;
};
