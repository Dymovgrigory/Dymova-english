/** Клиент замка: облик, витрина и звания (/api/v2/castle). Авторизация — токен игрока, как в тренажёре. */
import { ApiError, playerKey } from "@/lib/api";

const API = (process.env.NEXT_PUBLIC_WORLD_API || "").replace(/\/$/, "");
const TIMEOUT_MS = 12000;

export type Appearance = {
  season: string | null;
  time_of_day: string | null;
  weather: string | null;
  banner_color: string;
  banner_emblem: string;
};

export type CastleItem = {
  id: string;
  kind: "season" | "time" | "weather" | "banner" | "decor";
  title_ru: string;
  value: string;
  price: number;
  purchasable: boolean;
  owned: boolean;
  unlocked: boolean;
  requires_track: string | null;
  requires_level: number;
  anchor: string | null;
};

export type TitleRow = {
  track: string;
  track_title_ru: string;
  building: string;
  unit_ru: string;
  level: number;
  title_ru: string | null;
  value: number;
  next_threshold: number | null;
  worn: boolean;
};

export type DecorItem = { item_id: string; anchor: string; title_ru: string; active: boolean };

export type CastleView = {
  appearance: Appearance;
  catalog: CastleItem[];
  owned: string[];
  decor: DecorItem[];
  titles: TitleRow[];
  coins: number;
};

/** Сундук слов Сокровищницы (/api/v2/castle/lexicon-chest). */
export type LexiconChestStatus = {
  words: number;
  per_chest: number;
  opened: number;
  ready: number;
  progress: number;
};

export type LexiconChestOpen = { chest_index: number; coins: number; item_id: string | null };

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(`${API}${path}`, {
      ...init,
      cache: "no-store",
      signal: controller.signal,
      headers: { "Content-Type": "application/json", "X-World-Player": playerKey(), ...(init?.headers ?? {}) },
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

export const castleApi = {
  get: () => call<CastleView>("/api/v2/castle"),
  buy: (itemId: string) =>
    call<CastleView>("/api/v2/castle/buy", { method: "POST", body: JSON.stringify({ item_id: itemId }) }),
  apply: (fields: Partial<Appearance> & { decor_on?: string[]; decor_off?: string[] }) =>
    call<CastleView>("/api/v2/castle/appearance", { method: "POST", body: JSON.stringify(fields) }),
  wear: (track: string) =>
    call<CastleView>("/api/v2/castle/title", { method: "POST", body: JSON.stringify({ track }) }),
  lexiconChestStatus: () => call<LexiconChestStatus>("/api/v2/castle/lexicon-chest"),
  lexiconChestOpen: () => call<LexiconChestOpen>("/api/v2/castle/lexicon-chest/open", { method: "POST" }),
};
