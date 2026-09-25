"use client";

import { useState } from "react";

import { Button } from "@/design/Button";
import { Foxy } from "@/design/Foxy";
import { subscriberDigits, toE164 } from "@/features/registration/phone";
import { humanizeError } from "@/lib/api";
import { rememberPlayerToken } from "@/lib/token";
import { registrationApi } from "@/lib/v2/registration";

const inputCls =
  "h-14 w-full rounded-2xl bg-[#fffaf0] px-4 text-[18px] font-bold text-ink shadow-[inset_0_3px_6px_rgb(92_60_30/0.25),0_0_0_2px_#c9a86a] outline-none focus:shadow-[inset_0_3px_6px_rgb(92_60_30/0.25),0_0_0_3px_#3fae98]";

const labelCls = "text-[15px] font-extrabold text-[#f6efe2]";

/**
 * Восстановление: телефон или email → код на почту → новый пароль → сессия.
 */
export function RecoveryFlow({
  onDone,
  onCancel,
}: {
  onDone: () => void;
  onCancel?: () => void;
}) {
  const [mode, setMode] = useState<"phone" | "email">("email");
  const [step, setStep] = useState<"contact" | "code" | "password" | "done">("contact");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [emailMasked, setEmailMasked] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  const emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
  const phoneE164 = toE164(subscriberDigits(phone));
  const contactOk = mode === "email" ? emailOk : Boolean(phoneE164);
  const passwordOk = password.length >= 8 && password === password2;

  const contact =
    mode === "email" ? { email: email.trim() } : phoneE164 ? { phone: phoneE164 } : null;

  const sendCode = async () => {
    if (!contact) return;
    setBusy(true);
    setProblem(null);
    try {
      const res = await registrationApi.recoveryStart(contact);
      setEmailMasked(res.email_masked);
      setDevCode(res.dev_code ?? null);
      setCode("");
      setStep("code");
    } catch (err) {
      setProblem(humanizeError(err, "Не получилось отправить код. Попробуйте ещё раз."));
    } finally {
      setBusy(false);
    }
  };

  const verify = async () => {
    if (code.length !== 6 || !contact) return;
    setBusy(true);
    setProblem(null);
    try {
      const res = await registrationApi.recoveryVerify(contact, code);
      setResetToken(res.reset_token);
      setPassword("");
      setPassword2("");
      setStep("password");
    } catch (err) {
      setProblem(humanizeError(err, "Не получилось проверить код. Попробуйте ещё раз."));
    } finally {
      setBusy(false);
    }
  };

  const setNewPassword = async () => {
    if (!passwordOk || !resetToken) return;
    setBusy(true);
    setProblem(null);
    try {
      const res = await registrationApi.recoveryPassword(resetToken, password);
      rememberPlayerToken(res.token, res.external_key);
      setStep("done");
    } catch (err) {
      setProblem(humanizeError(err, "Не получилось сохранить пароль. Попробуйте ещё раз."));
    } finally {
      setBusy(false);
    }
  };

  const title =
    step === "done" ? "Готово!" : step === "password" ? "Новый пароль" : "Восстановление доступа";

  return (
    <div className="flex w-full flex-col gap-4">
      <h2 className="font-fairy text-[26px] font-black text-[#ffd36e]">{title}</h2>

      {step === "contact" && (
        <>
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              aria-pressed={mode === "email"}
              onClick={() => setMode("email")}
              className={`press min-h-11 rounded-xl text-[15px] font-extrabold ${
                mode === "email" ? "mat-brass" : "mat-enamel"
              }`}
            >
              Email
            </button>
            <button
              type="button"
              aria-pressed={mode === "phone"}
              onClick={() => setMode("phone")}
              className={`press min-h-11 rounded-xl text-[15px] font-extrabold ${
                mode === "phone" ? "mat-brass" : "mat-enamel"
              }`}
            >
              Телефон
            </button>
          </div>
          {mode === "email" ? (
            <label className="flex flex-col gap-1.5">
              <span className={labelCls}>Email из анкеты</span>
              <input
                type="email"
                className={inputCls}
                value={email}
                autoComplete="email"
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
          ) : (
            <label className="flex flex-col gap-1.5">
              <span className={labelCls}>Телефон родителя</span>
              <input
                className={inputCls}
                value={phone}
                inputMode="tel"
                autoComplete="tel"
                placeholder="+7 916 123-45-67"
                onChange={(e) => setPhone(e.target.value)}
              />
            </label>
          )}
          <p className="text-[15px] font-semibold text-[#c9bfd8]">
            Пришлём код на email из анкеты — затем зададите новый пароль.
          </p>
          <Button block disabled={!contactOk || busy} onClick={sendCode}>
            {busy ? "Отправляем…" : "Получить код"}
          </Button>
        </>
      )}

      {step === "code" && (
        <>
          <p className="text-[16px] font-semibold text-[#c9bfd8]">
            Код отправили на {emailMasked || "email из анкеты"}.
          </p>
          <label className="flex flex-col gap-1.5">
            <span className={labelCls}>Код из письма</span>
            <input
              className={`${inputCls} h-16 text-center text-[28px] tracking-[0.4em]`}
              value={code}
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              aria-label="Код из письма"
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              onKeyDown={(e) => e.key === "Enter" && verify()}
            />
          </label>
          {devCode && (
            <p role="note" className="rounded-2xl bg-[#fff3c4] px-4 py-3 text-center text-[15px] font-bold text-[#6b4e00]">
              Тестовый режим. Код: {devCode}
            </p>
          )}
          <Button block disabled={code.length !== 6 || busy} onClick={verify}>
            {busy ? "Проверяем…" : "Дальше"}
          </Button>
          <button
            type="button"
            onClick={() => setStep("contact")}
            className="min-h-11 text-[15px] font-bold text-[#c9bfd8] underline"
          >
            Изменить контакт
          </button>
        </>
      )}

      {step === "password" && (
        <>
          <label className="flex flex-col gap-1.5">
            <span className={labelCls}>Новый пароль (мин. 8 символов)</span>
            <input
              type="password"
              className={inputCls}
              value={password}
              autoComplete="new-password"
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className={labelCls}>Повторите пароль</span>
            <input
              type="password"
              className={inputCls}
              value={password2}
              autoComplete="new-password"
              onChange={(e) => setPassword2(e.target.value)}
            />
          </label>
          {password.length > 0 && password2.length > 0 && password !== password2 && (
            <p className="text-[14px] font-bold text-[#ffb3a6]">Пароли не совпадают</p>
          )}
          <Button block disabled={!passwordOk || busy} onClick={setNewPassword}>
            {busy ? "Сохраняем…" : "Сохранить и войти"}
          </Button>
        </>
      )}

      {step === "done" && (
        <div className="mat-parchment flex flex-col items-center gap-4 rounded-3xl px-6 py-8 text-center">
          <Foxy pose="cheer" size={140} />
          <p className="max-w-sm text-[15px] font-semibold text-ink-soft">
            Пароль обновлён. Можно играть с того же аккаунта.
          </p>
          <Button block onClick={onDone}>
            Продолжить
          </Button>
        </div>
      )}

      {problem && (
        <p role="alert" className="text-[16px] font-bold text-[#ffb3a6]">
          {problem}
        </p>
      )}

      {onCancel && step !== "done" && (
        <button type="button" onClick={onCancel} className="min-h-11 text-[15px] font-bold text-[#c9bfd8] underline">
          Отмена
        </button>
      )}
    </div>
  );
}
