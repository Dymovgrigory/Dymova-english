/** Клиент API тренажёра (/api/v2). Авторизация — тот же токен игрока, что и в замке. */

import { ApiError, playerKey, worldApi } from "@/lib/api";
import { clearPlayerToken, readPlayerToken } from "@/lib/token";

import type {
  Answer,
  AnswerReply,
  Courses,
  Home,
  LearningPath,
  Profile,
  SessionResult,
  SessionStart,
  WordsBook,
} from "./types";

const API = (process.env.NEXT_PUBLIC_WORLD_API || "").replace(/\/$/, "");
const TIMEOUT_MS = 12000;

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
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error("Сервер не отвечает. Проверь интернет и попробуй ещё раз.");
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

const post = <T>(path: string, body?: unknown) =>
  call<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export function hasPlayer(): boolean {
  return readPlayerToken().startsWith("wses.");
}

/** Токен есть и сервер его принимает. Протухший токен стираем. */
export async function verifiedPlayer(): Promise<boolean> {
  if (!hasPlayer()) return false;
  try {
    await worldApi.getPlayer();
    return true;
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      clearPlayerToken();
      return false;
    }
    return true;
  }
}

export function isProfileMissing(err: unknown): boolean {
  return err instanceof ApiError && err.status === 409 && err.message === "profile_required";
}

export function isUnauthorized(err: unknown): boolean {
  return err instanceof ApiError && err.status === 401;
}

export const v2 = {
  ensurePlayer: (name: string) => worldApi.ensurePlayer(name),
  courses: () => call<Courses>("/api/v2/courses"),
  profile: () => call<Profile>("/api/v2/profile"),
  saveProfile: (profile: Profile) => call<Profile>("/api/v2/profile", { method: "PUT", body: JSON.stringify(profile) }),
  home: () => call<Home>("/api/v2/home"),
  path: (bookId: string) => call<LearningPath>(`/api/v2/path?book_id=${encodeURIComponent(bookId)}`),
  startSession: (nodeId: string, allowSpeak: boolean) =>
    post<SessionStart>("/api/v2/sessions", { node_id: nodeId, allow_speak: allowSpeak }),
  startPractice: (allowSpeak: boolean) => post<SessionStart>("/api/v2/practice", { allow_speak: allowSpeak }),
  answer: (sessionId: string, index: number, answer: Answer, responseMs: number) =>
    post<AnswerReply>(`/api/v2/sessions/${sessionId}/answer`, { index, answer, response_ms: responseMs }),
  checkPair: (sessionId: string, index: number, left: string, right: string) =>
    post<{ correct: boolean }>(`/api/v2/sessions/${sessionId}/pair`, { index, left, right }),
  finish: (sessionId: string) => post<SessionResult>(`/api/v2/sessions/${sessionId}/finish`),
  openChest: (nodeId: string) => post<{ coins: number; next_node_id: string | null }>(`/api/v2/nodes/${nodeId}/chest`),
  words: (bookId: string) => call<WordsBook>(`/api/v2/words?book_id=${encodeURIComponent(bookId)}`),
};
