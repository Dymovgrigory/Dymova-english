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
  streak_days: number;
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

const API = process.env.NEXT_PUBLIC_WORLD_API ?? "http://localhost:8010";

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
  let key = window.localStorage.getItem("world.playerKey");
  if (!key) {
    key = `explorer-${crypto.randomUUID()}`;
    window.localStorage.setItem("world.playerKey", key);
  }
  return key;
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-World-Player": playerKey(),
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) throw new ApiError(res.status, `${path}: ${res.status} ${await res.text()}`);
  return (await res.json()) as T;
}

export const worldApi = {
  ensurePlayer: (name: string) =>
    call<Player>("/api/world/players", {
      method: "POST",
      body: JSON.stringify({ display_name: name }),
    }),
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
};
