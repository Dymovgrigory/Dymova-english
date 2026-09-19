/** Вход через мини-приложения мессенджеров (Telegram / MAX).
 *
 * Telegram: window.Telegram.WebApp.initData.
 * MAX (max.ru): window.WebApp.initData — тот же формат initData + hash.
 * Бэкенд: POST /api/world/auth/{provider} {init_data} → {token, player…, is_registered}.
 */
import { ApiError } from "@/lib/api";

export type MessengerProvider = "telegram" | "max";

declare global {
  interface Window {
    Telegram?: { WebApp?: { initData?: string; ready?: () => void; expand?: () => void } };
    /** JS-бридж MAX mini apps. */
    WebApp?: { initData?: string; ready?: () => void; platform?: string };
  }
}

/** Возвращает провайдера и сырую initData, если приложение открыто в мессенджере. */
export function detectMessenger(): { provider: MessengerProvider; initData: string } | null {
  if (typeof window === "undefined") return null;
  const tg = window.Telegram?.WebApp?.initData;
  if (tg) return { provider: "telegram", initData: tg };
  const max = window.WebApp?.initData;
  if (max) return { provider: "max", initData: max };
  return null;
}

export type MessengerAuthResult = {
  id: number;
  external_key: string;
  display_name: string;
  token: string;
  is_registered: boolean;
};

const API = (process.env.NEXT_PUBLIC_WORLD_API || "").replace(/\/$/, "");
const TIMEOUT_MS = 12000;

/** Вход по initData мессенджера. 503 provider_not_configured — провайдер не настроен на сервере. */
export async function messengerLogin(
  provider: MessengerProvider,
  initData: string,
): Promise<MessengerAuthResult> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(`${API}/api/world/auth/${provider}`, {
      method: "POST",
      cache: "no-store",
      signal: controller.signal,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ init_data: initData }),
    });
    if (!res.ok) {
      let detail = `${res.status}`;
      try {
        const body = (await res.json()) as { detail?: string | { code?: string } };
        if (typeof body.detail === "string") detail = body.detail;
        else if (body.detail?.code) detail = body.detail.code;
      } catch {
        /* тело не JSON */
      }
      throw new ApiError(res.status, detail);
    }
    return (await res.json()) as MessengerAuthResult;
  } finally {
    clearTimeout(timer);
  }
}
