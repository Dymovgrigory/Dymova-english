/** Картинки контента лежат в public/content (генерация — world-pipeline). */
export function contentImage(path: string | null | undefined): string | null {
  return path ? `/content/${path.replace(/^\/+/, "")}` : null;
}

const SPEAK_OFF_KEY = "study.speakOffUntil";
export const SPEAK_PAUSE_MS = 15 * 60 * 1000;

/** «Не могу говорить» выключает задания на речь на 15 минут. */
export function speakAllowed(now = Date.now()): boolean {
  if (typeof window === "undefined") return false;
  try {
    return Number(window.localStorage.getItem(SPEAK_OFF_KEY) || 0) < now;
  } catch {
    return true;
  }
}

export function pauseSpeaking(now = Date.now()) {
  try {
    window.localStorage.setItem(SPEAK_OFF_KEY, String(now + SPEAK_PAUSE_MS));
  } catch {
    /* private mode */
  }
}
