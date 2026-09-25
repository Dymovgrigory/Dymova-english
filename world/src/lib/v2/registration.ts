/** Клиент регистрации и входа (/api/v2/registration, /api/v2/auth/login). */
import { ApiError, playerKey } from "@/lib/api";
import type { ConsentType } from "@/lib/legal";

const API = (process.env.NEXT_PUBLIC_WORLD_API || "").replace(/\/$/, "");
const TIMEOUT_MS = 12000;

export type RegistrationChannel = "email" | "telegram";

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
  password: string;
  channel: RegistrationChannel;
  consents: Consent[];
};

export type RegistrationStartResult = {
  /** code_sent — код отправлен на email; awaiting_bot — ждём подтверждения в боте. */
  status: "code_sent" | "awaiting_bot";
  channel: RegistrationChannel;
  email_masked?: string;
  phone_masked?: string;
  cooldown_sec: number;
  /** Пока почта не настроена (dev/переходный период): код приходит прямо в ответе. */
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
  email_verified?: boolean;
  /** Подтверждён хотя бы один контакт (email или телефон через бота). */
  verified?: boolean;
};

export type RegistrationStatus = {
  identity: RegistrationIdentity | null;
  consents: Consent[];
  /** Анкета заполнена, согласия приняты, контакт подтверждён. */
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

type ErrorBody = { detail?: string; attempts_left?: number };

async function readError(res: Response): Promise<RegistrationError> {
  let detail = `${res.status}`;
  let attemptsLeft: number | undefined;
  try {
    const body = (await res.json()) as ErrorBody;
    if (typeof body.detail === "string") detail = body.detail;
    if (typeof body.attempts_left === "number") attemptsLeft = body.attempts_left;
  } catch {
    /* пустое тело ответа */
  }
  return new RegistrationError(res.status, detail, attemptsLeft);
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(`${API}${path}`, {
      ...init,
      cache: "no-store",
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        "X-World-Player": playerKey(),
        ...(init?.headers ?? {}),
      },
    });
    if (!res.ok) throw await readError(res);
    return (await res.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

const post = <T>(path: string, body: unknown) =>
  call<T>(path, { method: "POST", body: JSON.stringify(body) });

/** Восстановление: код на email → reset_token → новый пароль → сессия. */
export type RecoveryStartResult = {
  status: "code_sent";
  email_masked: string;
  phone_masked?: string;
  dev_code?: string;
};

export type RecoveryVerifyResult = {
  status: "code_ok";
  reset_token: string;
  email_masked: string;
};

export type SessionResult = {
  status: "verified" | "ok";
  token: string;
  external_key: string;
  display_name: string;
};

export type RecoveryContact = { email?: string; phone?: string };

export const registrationApi = {
  start: (body: RegistrationStartBody) =>
    post<RegistrationStartResult>("/api/v2/registration/start", body),
  verify: (code: string) => post<SessionResult>("/api/v2/registration/verify", { code }),
  confirmBot: () => post<SessionResult>("/api/v2/registration/confirm-bot", {}),
  status: () => call<RegistrationStatus>("/api/v2/registration/status"),
  login: (email: string, password: string) =>
    post<SessionResult>("/api/v2/auth/login", { email, password }),
  recoveryStart: (contact: RecoveryContact) =>
    post<RecoveryStartResult>("/api/v2/registration/recovery/start", contact),
  recoveryVerify: (contact: RecoveryContact, code: string) =>
    post<RecoveryVerifyResult>("/api/v2/registration/recovery/verify", { ...contact, code }),
  recoveryPassword: (resetToken: string, password: string) =>
    post<SessionResult>("/api/v2/registration/recovery/password", {
      reset_token: resetToken,
      password,
    }),
};
