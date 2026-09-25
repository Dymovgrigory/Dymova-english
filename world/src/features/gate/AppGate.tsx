"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Foxy } from "@/design/Foxy";
import { LoginFlow } from "@/features/login/LoginFlow";
import { RecoveryFlow } from "@/features/recovery/RecoveryFlow";
import { RegistrationFlow } from "@/features/registration/RegistrationFlow";
import {
  buildRegistrationPrefill,
  detectMessenger,
  messengerLogin,
  prepareMessengerUi,
  type RegistrationPrefill,
} from "@/lib/messenger";
import { rememberPlayerToken } from "@/lib/token";
import { hasPlayer } from "@/lib/v2/client";
import { registrationApi } from "@/lib/v2/registration";

/** Маршруты без гейта: админка (своя авторизация), тексты политик, вход и онбординг. */
const OPEN_PREFIXES = ["/admin", "/legal"];
const OPEN_PATHS = new Set(["/", "/onboarding"]);

type GateState = "checking" | "open" | "register";
type AuthPanel = "register" | "login" | "recovery";

/**
 * Обязательная регистрация: без завершённой анкеты мир недоступен.
 * В мини-приложении Telegram/MAX сначала входим по initData мессенджера.
 * Бэкенд дублирует проверку: 403 {"detail": {"code": "registration_required"}}.
 */
export function AppGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() ?? "/";
  const router = useRouter();
  const isOpen = OPEN_PATHS.has(pathname) || OPEN_PREFIXES.some((p) => pathname.startsWith(p));
  const [gate, setGate] = useState<{ path: string; state: GateState }>({ path: "", state: "checking" });
  const [prefill, setPrefill] = useState<RegistrationPrefill>({});
  const [panel, setPanel] = useState<AuthPanel>("register");
  const state: GateState = gate.path === pathname ? gate.state : "checking";

  useEffect(() => {
    prepareMessengerUi();
  }, []);

  useEffect(() => {
    if (isOpen) return;
    let alive = true;
    const finish = (registered: boolean, nextPrefill?: RegistrationPrefill) => {
      if (!alive) return;
      if (nextPrefill) setPrefill(nextPrefill);
      setGate({ path: pathname, state: registered ? "open" : "register" });
    };
    const messenger = detectMessenger();
    if (messenger) {
      prepareMessengerUi();
      messengerLogin(messenger.provider, messenger.initData)
        .then((res) => {
          rememberPlayerToken(res.token, res.external_key);
          finish(res.is_registered, buildRegistrationPrefill(res.display_name, res.prefill));
        })
        .catch(() => finish(false));
      return () => {
        alive = false;
      };
    }
    if (!hasPlayer()) {
      router.replace("/onboarding");
      return () => {
        alive = false;
      };
    }
    registrationApi
      .status()
      .then((s) => finish(s.is_registered === true))
      .catch(() => finish(false));
    return () => {
      alive = false;
    };
  }, [isOpen, pathname, router]);

  if (isOpen || state === "open") return <>{children}</>;

  if (state === "register") {
    const reload = () => window.location.reload();
    return (
      <div className="study mx-auto flex min-h-dvh w-full max-w-xl flex-col gap-5 px-4 py-8 pb-[max(2rem,env(safe-area-inset-bottom))]">
        <div className="flex flex-col items-center gap-3 text-center">
          <Foxy pose="wave" size={120} />
          <h1 className="font-fairy text-[28px] font-black text-[#ffd36e]">Осталось совсем чуть-чуть!</h1>
          <p className="max-w-md text-[16px] font-semibold text-[#c9bfd8]">
            Чтобы играть в Фоксинбург и не потерять прогресс, маме или папе нужно заполнить
            короткую анкету и подтвердить контакт. Это займёт пару минут.
          </p>
        </div>
        {panel === "recovery" && (
          <RecoveryFlow onDone={reload} onCancel={() => setPanel("login")} />
        )}
        {panel === "login" && (
          <LoginFlow
            onDone={reload}
            onForgot={() => setPanel("recovery")}
            onCancel={() => setPanel("register")}
          />
        )}
        {panel === "register" && (
          <>
            <RegistrationFlow
              mode="gate"
              prefill={prefill}
              onDone={() => setGate({ path: pathname, state: "open" })}
            />
            <button
              type="button"
              onClick={() => setPanel("login")}
              className="min-h-11 px-4 text-[15px] font-bold text-[#c9bfd8] underline"
            >
              Уже есть аккаунт? Войти
            </button>
          </>
        )}
      </div>
    );
  }

  return (
    <div className="study flex min-h-dvh items-center justify-center">
      <p className="font-heading text-[28px] font-extrabold text-royal" role="status">
        Фоксинбург
      </p>
    </div>
  );
}
