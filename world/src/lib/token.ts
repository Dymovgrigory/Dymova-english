/** Opaque wses.* session token: сервер отдаёт token, клиент кладёт его в X-World-Player. */

const KEY = "world.playerKey";
const TOKEN = "world.playerToken";

export function readPlayerToken(): string {
  if (typeof window === "undefined") return "guest";
  try {
    return window.localStorage.getItem(TOKEN) || window.localStorage.getItem(KEY) || "guest";
  } catch {
    return "guest";
  }
}

export function rememberPlayerToken(token: string, externalKey?: string) {
  if (typeof window === "undefined") return;
  try {
    if (token) window.localStorage.setItem(TOKEN, token);
    if (externalKey) window.localStorage.setItem(KEY, externalKey);
  } catch {
    /* private mode */
  }
}

export function clearPlayerToken() {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(TOKEN);
  } catch {
    /* private mode */
  }
}
