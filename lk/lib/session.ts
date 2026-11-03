export const TOKEN_KEY = "lk_token";
export const PHONE_KEY = "lk_phone";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setSession(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function setPendingPhone(phone: string): void {
  window.localStorage.setItem(PHONE_KEY, phone);
}

export function getPendingPhone(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(PHONE_KEY);
}

export function clearSession(): void {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(PHONE_KEY);
}
