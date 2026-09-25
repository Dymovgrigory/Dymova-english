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
        /** Bot API 7.10+: системные отступы (чёлка, home indicator). */
        safeAreaInset?: { top?: number; bottom?: number; left?: number; right?: number };
        /** Bot API 7.10+: отступы под UI Telegram (шапка с крестиком и т.п.). */
        contentSafeAreaInset?: { top?: number; bottom?: number; left?: number; right?: number };
        onEvent?: (event: string, handler: () => void) => void;
        offEvent?: (event: string, handler: () => void) => void;
        /** Bot API 6.9+: системный запрос «поделиться номером» — замена SMS-коду. */
        requestContact?: (
          callback?: (sent: boolean, response?: { responseUnsafe?: { contact?: { phone_number?: string } } }) => void,
        ) => void;
      };
    };
    /** JS-бридж MAX mini apps. */
    WebApp?: { initData?: string; ready?: () => void; expand?: () => void; platform?: string };
  }
}

/** Подтверждение номера через Telegram доступно только внутри его WebApp. */
export function supportsTelegramContact(): boolean {
  if (typeof window === "undefined") return false;
  return typeof window.Telegram?.WebApp?.requestContact === "function";
}

const CONTACT_TIMEOUT_MS = 90_000;

/**
 * Системный запрос Telegram «поделиться номером телефона».
 * Таймаут: на части клиентов колбэк не вызывается при закрытии попапа —
 * без него кнопка зависала бы в busy навсегда.
 */
export function requestTelegramContact(): Promise<boolean> {
  return new Promise((resolve) => {
    const request = window.Telegram?.WebApp?.requestContact;
    if (typeof request !== "function") {
      resolve(false);
      return;
    }
    let done = false;
    const finish = (sent: boolean) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      resolve(sent);
    };
    const timer = setTimeout(() => finish(false), CONTACT_TIMEOUT_MS);
    try {
      request.call(window.Telegram?.WebApp, (sent: boolean) => finish(sent === true));
    } catch {
      finish(false);
    }
  });
}

/**
 * Пишет CSS-переменные --fox-safe-* из inset'ов Telegram.
 * Класс html.fox-messenger + пол ~200px: иначе на широком WebView lg:pt-0
 * обнулял отступ, и шапка TG перекрывала кнопки/заголовки.
 */
export function syncMessengerSafeArea(): void {
  if (typeof window === "undefined" || typeof document === "undefined") return;
  const root = document.documentElement;
  const tg = window.Telegram?.WebApp;
  if (!tg) return;

  root.classList.add("fox-messenger");

  const safe = tg.safeAreaInset ?? {};
  const content = tg.contentSafeAreaInset ?? {};
  const top = Math.max(0, Number(safe.top) || 0) + Math.max(0, Number(content.top) || 0);
  const bottom = Math.max(0, Number(safe.bottom) || 0) + Math.max(0, Number(content.bottom) || 0);
  const left = Math.max(0, Number(safe.left) || 0) + Math.max(0, Number(content.left) || 0);
  const right = Math.max(0, Number(safe.right) || 0) + Math.max(0, Number(content.right) || 0);

  const TOP_FLOOR = 200;
  const TOP_EXTRA = 56;
  const topPx = Math.max(top + TOP_EXTRA, TOP_FLOOR);
  const bottomPx = Math.max(bottom, 16);

  root.style.setProperty("--fox-safe-top", `${topPx}px`);
  root.style.setProperty("--fox-safe-bottom", `${bottomPx}px`);
  root.style.setProperty("--fox-safe-left", `${left}px`);
  root.style.setProperty("--fox-safe-right", `${right}px`);
}

/** Сообщить клиенту Telegram, что мини-приложение готово; развернуть на весь экран. */
export function prepareMessengerUi(): void {
  if (typeof window === "undefined") return;
  const tg = window.Telegram?.WebApp;
  if (tg) {
    try {
      tg.ready?.();
      tg.expand?.();
    } catch {
      /* клиент без ready/expand */
    }
    syncMessengerSafeArea();
    const resync = () => syncMessengerSafeArea();
    try {
      tg.onEvent?.("safeAreaChanged", resync);
      tg.onEvent?.("contentSafeAreaChanged", resync);
      tg.onEvent?.("viewportChanged", resync);
    } catch {
      /* старый клиент без onEvent */
    }
    // Insets и initData часто появляются после expand / загрузки bridge.
    window.setTimeout(resync, 50);
    window.setTimeout(resync, 300);
    window.setTimeout(resync, 1000);
    return;
  }
  const max = window.WebApp;
  if (max) {
    try {
      max.ready?.();
      max.expand?.();
    } catch {
      /* ignore */
    }
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
