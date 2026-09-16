export type Player = {
  id: number;
  external_key: string;
  display_name: string;
  role: string;
  xp: number;
  coins: number;
  level: number;
  level_title: string;
  xp_into_level: number;
  xp_to_next: number | null;
  hearts?: number;
  streak_days?: number;
  level_title_ru?: string;
};

export type Quest = {
  id: string;
  kind: string;
  title_ru: string;
  status: string;
  step: number;
  config: {
    steps: { action: string; target: string; label_ru: string }[];
    rewards: { xp: number; coins: number; items?: string[]; unlocks?: string[] };
  };
};

export type CompleteResult = {
  quest_id: string;
  status: string;
  xp_delta: number;
  coins_delta: number;
  items_granted: string[];
  unlocks_granted: string[];
  level_up: boolean;
  new_level: number;
  new_title: string;
  player: Player;
};

export type InventoryItem = {
  id: string;
  category: string;
  rarity: string;
  title_ru: string;
  asset_id: string | null;
  source: string;
  acquired_at: string;
};

export type ChallengeQuestion = {
  index: number;
  en: string;
  ipa: string;
  example_en: string;
  options: string[];
};

export type ChallengeSession = {
  session_id: string;
  activity_id: string;
  title_ru: string;
  total: number;
  questions: ChallengeQuestion[];
};

export type AnswerResult = {
  index: number;
  correct: boolean;
  correct_index: number;
  example_en: string;
  example_ru: string;
  answered: number;
  total: number;
};

export type QuestStepResult = {
  quest_id: string;
  step: number;
  steps_total: number;
  all_steps_done: boolean;
};

export type FinishResult = {
  session_id: string;
  activity_id: string;
  score: number;
  total: number;
  perfect: boolean;
  xp_delta: number;
  coins_delta: number;
  level_up: boolean;
  new_level: number;
  new_title: string;
  player: Player;
  quest: QuestStepResult | null;
  /** true — повторное прохождение уже пройденной активности: тренировка, xp_delta/coins_delta равны нулю. */
  practice: boolean;
};

export type LearnLessonNode = {
  id: string;
  index: number;
  title_ru: string;
  stars: number;
  locked: boolean;
  kind?: "lesson" | "checkpoint";
};

export type LearnUnit = {
  id: string;
  title_ru: string;
  topic_ru?: string;
  goal_ru?: string;
  book?: string;
  book_ru?: string;
  accent?: string;
  locked: boolean;
  lessons: LearnLessonNode[];
};

export type LearnPath = {
  language: string;
  hearts_max: number;
  hearts?: number;
  program_ru?: string;
  next_book_ru?: string;
  player?: Player;
  stickers_owned?: number;
  unlock_all?: boolean;
  units: LearnUnit[];
};

export type LeagueRow = {
  rank: number;
  display_name: string;
  weekly_xp: number;
  tier: string;
  is_me: boolean;
};

export type League = {
  tier: string;
  weekly_xp: number;
  rank: number;
  size: number;
  top?: LeagueRow[];
};

export type ReviewQueue = {
  due: number;
  words: { en: string; ru: string; unit_id: string; unit_ru: string; strength: number }[];
};

export type LessonItem = {
  index: number;
  kind: "explain" | "word_card" | "phrase_card" | "mcq_en_ru" | "mcq_ru_en" | "type_en" | "match" | "listen" | "fill_blank" | "tap_build";
  prompt?: string;
  hint_ru?: string;
  ipa?: string;
  options?: string[];
  speak?: string;
  left?: string[];
  right?: string[];
  bank?: string[];
  foxi_ru?: string;
  foxi_pose?: string;
  stage?: "warmup" | "theory" | "words" | "listen" | "practice" | "wrap";
  visual_id?: string;
  title_ru?: string;
  body_ru?: string;
  example_en?: string;
  example_ru?: string;
  en?: string;
  ru?: string;
  image?: string;
  teach_ru?: string;
  steps?: string[];
  gpc?: string;
  sound?: string;
  speak_sound?: string;
  audio?: string;
};

export type LessonSession = {
  session_id: string;
  lesson_id: string;
  title_ru: string;
  place_ru?: string;
  spot_ru?: string;
  accent?: string;
  hearts: number;
  hearts_max: number;
  total: number;
  items: LessonItem[];
  review_due?: number;
};

export type LessonAnswerResult = {
  index: number;
  correct: boolean;
  hearts: number;
  failed: boolean;
  answered: number;
  total: number;
  example_en: string;
  example_ru: string;
  correct_index?: number;
  correct_text?: string;
  pairs?: { en: string; ru: string }[];
  tokens_correct?: string[];
};

export type LessonFinish = {
  session_id: string;
  lesson_id: string;
  score: number;
  total: number;
  stars: number;
  perfect: boolean;
  xp_delta: number;
  coins_delta: number;
  practice: boolean;
  items_granted?: string[];
  daily_xp?: number;
  daily_goal?: number;
  player: Player;
};

const API = (process.env.NEXT_PUBLIC_WORLD_API || "").replace(/\/$/, "");

/** Ошибка ответа API с числовым HTTP-статусом — не парсить статус из текста сообщения. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function playerKey(): string {
  if (typeof window === "undefined") return "guest";
  try {
    const token = window.localStorage.getItem("world.playerToken");
    if (token) return token;
    let key = window.localStorage.getItem("world.playerKey");
    if (!key) {
      key = `explorer-${crypto.randomUUID()}`;
      window.localStorage.setItem("world.playerKey", key);
    }
    return key;
  } catch {
    return "guest";
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const ac = new AbortController();
  const timer = setTimeout(() => ac.abort(), 15000);
  try {
    const res = await fetch(`${API}${path}`, {
      ...init,
      signal: init?.signal ?? ac.signal,
      headers: {
        "Content-Type": "application/json",
        "X-World-Player": playerKey(),
        ...(init?.headers ?? {}),
      },
    });
    if (!res.ok) throw new ApiError(res.status, `${path}: ${res.status} ${await res.text()}`);
    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error("Сервер мира не ответил. Открой http://127.0.0.1:3002 и API на :8010 (make world-dev).");
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

export const worldApi = {
  ensurePlayer: async (name: string) => {
    const player = await call<Player & { token?: string }>("/api/world/players", {
      method: "POST",
      body: JSON.stringify({ display_name: name }),
    });
    if (player.token && typeof window !== "undefined") {
      window.localStorage.setItem("world.playerToken", player.token);
    }
    return player;
  },
  getPlayer: () => call<Player>("/api/world/player"),
  getQuests: () => call<Quest[]>("/api/world/quests"),
  startQuest: (id: string) =>
    call<{ quest_id: string; status: string }>(`/api/world/quests/${id}/start`, { method: "POST" }),
  completeQuest: (id: string) =>
    call<CompleteResult>(`/api/world/quests/${id}/complete`, {
      method: "POST",
      body: JSON.stringify({ idempotency_key: crypto.randomUUID() }),
    }),
  getInventory: () => call<InventoryItem[]>("/api/world/inventory"),
  getUnlocks: () => call<string[]>("/api/world/unlocks"),
  advanceStep: (questId: string, action: string, target: string) =>
    call<QuestStepResult>(`/api/world/quests/${questId}/step`, {
      method: "POST",
      body: JSON.stringify({ action, target }),
    }),
  startActivity: (activityId: string) =>
    call<ChallengeSession>("/api/world/activities/start", {
      method: "POST",
      body: JSON.stringify({ activity_id: activityId }),
    }),
  answer: (sessionId: string, index: number, choice: number) =>
    call<AnswerResult>(`/api/world/activities/${sessionId}/answer`, {
      method: "POST",
      body: JSON.stringify({ index, choice }),
    }),
  finishActivity: (sessionId: string) =>
    call<FinishResult>(`/api/world/activities/${sessionId}/finish`, {
      method: "POST",
      body: JSON.stringify({ idempotency_key: crypto.randomUUID() }),
    }),
  getLearnPath: () => call<LearnPath>("/api/world/learn/path"),
  getLearnHome: () => call<{
    player: Player;
    hearts: { current: number };
    streak: { days: number };
    quests: { id: string; title_ru: string; progress: number; target: number; done: boolean }[];
    stickers: { owned: number; total: number; items: { id: string; title_ru: string; emoji: string; owned: boolean }[] };
    current_lesson_id: string;
    league?: League;
  }>("/api/world/learn/home"),
  getLeague: () => call<League>("/api/world/learn/league"),
  getReview: () => call<ReviewQueue>("/api/world/learn/review"),
  getWords: (unitId: string) =>
    call<{ unit_id: string; words: { en: string; ru: string; ipa: string; image?: string; strength: number }[] }>(
      `/api/world/learn/words/${unitId}`,
    ),
  getStickers: () =>
    call<{ owned: number; total: number; items: { id: string; title_ru: string; emoji: string; owned: boolean }[] }>(
      "/api/world/learn/stickers",
    ),
  getShop: () => call<{ items: { sku: string; coins: number; title_ru: string }[] }>("/api/world/learn/shop"),
  buyShop: (sku: string) =>
    call<{ ok: boolean; player: Player; items_granted?: string[] }>("/api/world/learn/shop/buy", {
      method: "POST",
      body: JSON.stringify({ sku }),
    }),
    startLesson: (lessonId: string) =>
    call<LessonSession>("/api/world/learn/lessons/start", {
      method: "POST",
      body: JSON.stringify({ lesson_id: lessonId }),
    }),
  startPractice: () =>
    call<LessonSession>("/api/world/learn/practice/start", { method: "POST" }),
  restoreHearts: () =>
    call<{ hearts: number; hearts_max: number }>("/api/world/learn/hearts/restore", { method: "POST" }),
  answerLesson: (sessionId: string, index: number, value: Record<string, unknown>) =>
    call<LessonAnswerResult>(`/api/world/learn/sessions/${sessionId}/answer`, {
      method: "POST",
      body: JSON.stringify({ index, value }),
    }),
  getSprint: () =>
    call<{ unit_id: string; title_ru: string; words: { en: string; ru: string; image: string }[] }>(
      "/api/world/learn/sprint",
    ),
  finishSprint: (score: number, total: number) =>
    call<{ score: number; total: number; xp_delta: number; coins_delta: number; player: Player }>(
      "/api/world/learn/sprint/finish",
      { method: "POST", body: JSON.stringify({ score, total }) },
    ),
  finishLesson: (sessionId: string) =>
    call<LessonFinish>(`/api/world/learn/sessions/${sessionId}/finish`, { method: "POST" }),
};
