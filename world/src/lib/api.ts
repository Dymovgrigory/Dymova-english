import { clearPlayerToken, readPlayerToken, rememberPlayerToken } from "@/lib/token";

export type NextBestAction = {
  kind: "quest" | "review" | "lesson";
  href: string;
  title: string;
  hint: string;
  why: string;
  analytic_id: string;
  lesson_id?: string;
  due?: number;
  weak_words?: { word_en: string; unit_id?: string; strength?: number; wrong_count?: number }[];
};

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

export type LeagueHistoryRow = {
  week_start: string;
  rank: number;
  weekly_xp: number;
  coins_awarded: number;
};

export type League = {
  tier: string;
  weekly_xp: number;
  rank: number;
  size: number;
  top?: LeagueRow[];
  history?: LeagueHistoryRow[];
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

/** Машинные коды API → фразы для игрока. Неизвестное никогда не показываем сырым. */
const ERROR_TEXTS: Record<string, string> = {
  "not enough coins": "Не хватает монет",
  "item not found": "Товар не найден",
  item_not_for_sale: "Это не продаётся",
  title_required: "Сначала нужно звание",
  item_not_owned: "Сначала нужно купить",
  "quest not complete": "Задание ещё не выполнено",
  nothing_to_practice: "Пока нечего тренировать — сначала пройди урок",
  phone_recently_sent: "Код уже отправлен, подождите минуту",
  email_recently_sent: "Код уже отправлен, подождите минуту",
  email_daily_limit: "Слишком много писем за день — попробуйте завтра",
  code_invalid: "Неверный код",
  code_expired: "Код истёк — отправьте новый",
  too_many_attempts: "Слишком много попыток",
  no_pending_verification: "Сначала запросите код",
  consent_required: "Нужны обязательные согласия",
  phone_taken: "Этот телефон уже зарегистрирован — восстановите доступ",
  email_taken: "Этот email уже зарегистрирован — войдите или восстановите пароль",
  bad_credentials: "Неверный email или пароль",
  email_not_verified: "Сначала подтвердите почту — код из письма",
  registration_required: "Сначала завершите регистрацию",
  "signed player token required": "Сессия устарела — обновите страницу и попробуйте снова",
  password_required: "Укажите пароль (минимум 8 символов)",
  password_too_short: "Пароль слишком короткий — минимум 8 символов",
  age_out_of_range: "Возраст ученика должен быть от 3 до 17 лет",
  bad_name: "Имя и фамилия — только буквы, дефис или пробел",
  bad_email: "Проверьте email — похоже, он написан с ошибкой",
  bad_phone: "Проверьте телефон — нужен российский номер +7",
  validation_error: "Проверьте анкету — какое-то поле заполнено неверно",
};

export function humanizeError(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    // коды вида "consent_required:privacy" — смотрим по части до двоеточия
    return ERROR_TEXTS[err.message] ?? ERROR_TEXTS[err.message.split(":")[0]] ?? fallback;
  }
  if (err instanceof Error) return err.message;
  return fallback;
}

export function playerKey(): string {
  if (typeof window === "undefined") return "guest";
  try {
    const token = readPlayerToken();
    if (token && token !== "guest") return token;
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
    if (!res.ok) {
      let detail = `${res.status}`;
      try {
        const body = (await res.json()) as { detail?: string };
        if (typeof body.detail === "string") detail = body.detail;
      } catch {
        /* тело не JSON — остаётся статус */
      }
      throw new ApiError(res.status, detail);
    }
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
    const existing = readPlayerToken();
    if (existing.startsWith("wses.")) {
      try {
        return await call<Player>("/api/world/player");
      } catch (err) {
        if (!(err instanceof ApiError) || err.status !== 401) throw err;
        clearPlayerToken();
      }
    }
    const player = await call<Player & { token?: string }>("/api/world/players", {
      method: "POST",
      body: JSON.stringify({ display_name: name }),
    });
    if (player.token) {
      rememberPlayerToken(player.token, player.external_key);
    }
    return player;
  },
  logout: async () => {
    try {
      await call<{ ok: boolean }>("/api/world/session/logout", { method: "POST" });
    } catch {
      /* already dead session */
    }
    clearPlayerToken();
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
    quests: {
      id: string;
      title_ru: string;
      progress: number;
      target: number;
      done: boolean;
      claimed?: boolean;
      claimable?: boolean;
    }[];
    stickers: { owned: number; total: number; items: { id: string; title_ru: string; emoji: string; owned: boolean }[] };
    current_lesson_id: string;
    league?: League;
    next_best_action?: NextBestAction;
    lessons_starred?: number;
  }>("/api/world/learn/home"),
  getLeague: () => call<League>("/api/world/learn/league"),
  getReview: () => call<ReviewQueue>("/api/world/learn/review"),
  getWords: (unitId: string) =>
    call<{ unit_id: string; words: { en: string; ru: string; ipa: string; image?: string; strength: number }[] }>(
      `/api/world/learn/words/${unitId}`,
    ),
  claimDailyQuest: (questId: string) =>
    call<{ quest_id: string; ok: boolean; xp_delta?: number }>("/api/world/learn/quests/claim", {
      method: "POST",
      body: JSON.stringify({ quest_id: questId }),
    }),
  getStickers: () =>
    call<{ owned: number; total: number; items: { id: string; title_ru: string; emoji: string; owned: boolean }[] }>(
      "/api/world/learn/stickers",
    ),
  getShop: () => call<{ items: { sku: string; coins: number; title_ru: string }[] }>("/api/world/learn/shop"),
  buyShop: (sku: string) =>
    call<{ ok: boolean; player: Player; items_granted?: string[]; hearts?: number; hearts_max?: number }>("/api/world/learn/shop/buy", {
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
    call<{
      session_id: string;
      unit_id: string;
      title_ru: string;
      words: { en: string; ru: string; image: string }[];
    }>("/api/world/learn/sprint"),
  answerSprint: (sessionId: string, en: string, choice: string) =>
    call<{ en: string; correct: boolean; score: number; answered: number; total: number }>(
      `/api/world/learn/sprint/sessions/${sessionId}/answer`,
      {
        method: "POST",
        body: JSON.stringify({ en, choice }),
      },
    ),
  finishSprint: (sessionId: string, score?: number, total?: number) =>
    call<{
      score: number;
      total: number;
      xp_delta: number;
      coins_delta: number;
      player: Player;
      daily_xp?: number;
      daily_goal?: number;
      cosmetic_only?: boolean;
      session_id?: string;
    }>("/api/world/learn/sprint/finish", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, score, total }),
    }),
  finishLesson: (sessionId: string) =>
    call<LessonFinish>(`/api/world/learn/sessions/${sessionId}/finish`, { method: "POST" }),
};
