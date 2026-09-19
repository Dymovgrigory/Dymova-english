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
    Telegram?: {
      WebApp?: {
        initData?: string;
        ready?: () => void;
        expand?: () => void;
        /** Bot API 6.9+: системный запрос «поделиться номером» — замена SMS-коду. */
        requestContact?: (callback?: (sent: boolean) => void) => void;
      };
    };
    /** JS-бридж MAX mini apps. */
    WebApp?: { initData?: string; ready?: () => void; platform?: string };
  }
}

/** Подтверждение номера через Telegram доступно только внутри его WebApp. */
export function supportsTelegramContact(): boolean {
  if (typeof window === "undefined") return false;
  return typeof window.Telegram?.WebApp?.requestContact === "function";
}

/** Системный запрос Telegram «поделиться номером телефона». */
export function requestTelegramContact(): Promise<boolean> {
  return new Promise((resolve) => {
    const request = window.Telegram?.WebApp?.requestContact;
    if (typeof request !== "function") {
      resolve(false);
      return;
    }
    request.call(window.Telegram?.WebApp, (sent: boolean) => resolve(sent === true));
  });
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

/** Данные лида из школьного бота (мост /world-bridge/profile) — предзаполнение анкеты. */
export type MessengerPrefill = {
  fio_parent?: string;
  fio_child?: string;
  birthday?: string;
  phone?: string;
};

export type MessengerAuthResult = {
  id: number;
  external_key: string;
  display_name: string;
  token: string;
  is_registered: boolean;
  /** null — игрок уже зарегистрирован, мост выключен или лид в боте не найден. */
  prefill?: MessengerPrefill | null;
};

/** Предзаполнение анкеты регистрации (поля RegistrationFlow). */
export type RegistrationPrefill = {
  firstName?: string;
  lastName?: string;
  /** YYYY-MM-DD для <input type="date">. */
  birthDate?: string;
  phone?: string;
};

/** ДД.ММ.ГГГГ или ГГГГ-ММ-ДД → ГГГГ-ММ-ДД; возраст («9 лет») и мусор → undefined. */
function normalizeBirthDate(raw?: string): string | undefined {
  const value = (raw ?? "").trim();
  const dotted = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(value);
  if (dotted) return `${dotted[3]}-${dotted[2]}-${dotted[1]}`;
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  return undefined;
}

/**
 * Собирает предзаполнение анкеты: приоритет у данных лида из бота
 * (fio_child — ребёнок), имя из профиля мессенджера — запасной вариант.
 */
export function buildRegistrationPrefill(
  displayName: string,
  prefill?: MessengerPrefill | null,
): RegistrationPrefill {
  const childWords = (prefill?.fio_child ?? "").trim().split(/\s+/).filter(Boolean);
  const [childFirst, ...childRest] = childWords;
  const fallbackFirst = displayName.trim().split(/\s+/)[0] ?? "";
  return {
    firstName: childFirst || fallbackFirst || undefined,
    lastName: childRest.length ? childRest.join(" ") : undefined,
    birthDate: normalizeBirthDate(prefill?.birthday),
    phone: (prefill?.phone ?? "").trim() || undefined,
  };
}

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
