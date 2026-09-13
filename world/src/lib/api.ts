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

const API = process.env.NEXT_PUBLIC_WORLD_API ?? "http://localhost:8000";

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
  if (!res.ok) throw new Error(`${path}: ${res.status} ${await res.text()}`);
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
};
