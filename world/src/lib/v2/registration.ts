/** Клиент регистрации с верификацией телефона родителя (/api/v2/registration). */
import { ApiError, playerKey } from "@/lib/api";
import type { ConsentType } from "@/lib/legal";

const API = (process.env.NEXT_PUBLIC_WORLD_API || "").replace(/\/$/, "");
const TIMEOUT_MS = 12000;

export type RegistrationChannel = "sms" | "call";

export type Consent = { type: ConsentType; version: string; accepted_at?: string };

export type RegistrationStartBody = {
  first_name: string;
  last_name: string;
  birth_date: string; // "YYYY-MM-DD"
  school_number: string;
  class_grade: number;
  class_letter?: string;
  parent_email: string;
  parent_phone: string; // "+7XXXXXXXXXX"
  channel: RegistrationChannel;
  consents: Consent[];
};

export type RegistrationStartResult = {
  status: "code_sent";
  channel: RegistrationChannel;
  phone_masked: string;
  cooldown_sec: number;
  /** Только в dev-окружении; в UI не показывать. */
  dev_code?: string;
};

export type RegistrationIdentity = {
  first_name: string;
  last_name: string;
  birth_date: string;
  school_number: string;
  class_grade: number;
  class_letter: string | null;
  parent_email: string;
  parent_phone_masked: string;
  phone_verified: boolean;
};

export type RegistrationStatus = {
  identity: RegistrationIdentity | null;
  consents: Consent[];
  /** Анкета заполнена, согласия приняты, телефон подтверждён. */
  is_registered?: boolean;
};

/** Ошибка регистрации: у code_invalid сервер шлёт attempts_left отдельным полем. */
export class RegistrationError extends ApiError {
  readonly attemptsLeft?: number;

  constructor(status: number, message: string, attemptsLeft?: number) {
    super(status, message);
    this.name = "RegistrationError";
    this.attemptsLeft = attemptsLeft;
  }
}

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
      let attemptsLeft: number | undefined;
      try {
        const body = (await res.json()) as { detail?: string; attempts_left?: number };
        if (typeof body.detail === "string") detail = body.detail;
        if (typeof body.attempts_left === "number") attemptsLeft = body.attempts_left;
      } catch {
        /* пустое тело ответа */
      }
      throw new RegistrationError(res.status, detail, attemptsLeft);
    }
    return (await res.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

const post = <T>(path: string, body: unknown) =>
  call<T>(path, { method: "POST", body: JSON.stringify(body) });

export const registrationApi = {
  start: (body: RegistrationStartBody) => post<RegistrationStartResult>("/api/v2/registration/start", body),
  verify: (code: string) => post<{ status: "verified" }>("/api/v2/registration/verify", { code }),
  status: () => call<RegistrationStatus>("/api/v2/registration/status"),
};
