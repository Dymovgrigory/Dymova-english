"use client";

import { useState } from "react";

import { Button } from "@/design/Button";
import { humanizeError } from "@/lib/api";
import { rememberPlayerToken } from "@/lib/token";
import { registrationApi } from "@/lib/v2/registration";

const inputCls =
  "h-14 w-full rounded-2xl bg-[#fffaf0] px-4 text-[18px] font-bold text-ink shadow-[inset_0_3px_6px_rgb(92_60_30/0.25),0_0_0_2px_#c9a86a] outline-none focus:shadow-[inset_0_3px_6px_rgb(92_60_30/0.25),0_0_0_3px_#3fae98]";

const labelCls = "text-[15px] font-extrabold text-[#f6efe2]";

/** Вход в браузере: email + пароль. */
export function LoginFlow({
  onDone,
  onForgot,
  onCancel,
}: {
  onDone: () => void;
  onForgot: () => void;
  onCancel?: () => void;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  const emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
  const canSubmit = emailOk && password.length >= 1;

  const submit = async () => {
    if (!canSubmit) return;
    setBusy(true);
    setProblem(null);
    try {
      const res = await registrationApi.login(email.trim(), password);
      rememberPlayerToken(res.token, res.external_key);
      onDone();
    } catch (err) {
      setProblem(humanizeError(err, "Не получилось войти. Проверьте email и пароль."));
    } finally {
      setBusy(false);
    }
  };

  const onEnter = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") void submit();
  };

  return (
    <div className="flex w-full flex-col gap-4">
      <h2 className="font-fairy text-[26px] font-black text-[#ffd36e]">Вход</h2>
      <label className="flex flex-col gap-1.5">
        <span className={labelCls}>Email родителя</span>
        <input
          type="email"
          className={inputCls}
          value={email}
          autoComplete="email"
          placeholder="parent@example.ru"
          onChange={(e) => setEmail(e.target.value)}
          onKeyDown={onEnter}
        />
      </label>
      <label className="flex flex-col gap-1.5">
        <span className={labelCls}>Пароль</span>
        <input
          type="password"
          className={inputCls}
          value={password}
          autoComplete="current-password"
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={onEnter}
        />
      </label>
      <Button block disabled={!canSubmit || busy} onClick={submit}>
        {busy ? "Входим…" : "Войти"}
      </Button>
      <button
        type="button"
        onClick={onForgot}
        className="min-h-11 px-4 text-[15px] font-bold text-[#7fd8c9] underline"
      >
        Забыли пароль?
      </button>
      {onCancel && (
        <button
          type="button"
          onClick={onCancel}
          className="min-h-11 text-[15px] font-bold text-[#c9bfd8] underline"
        >
          Назад к регистрации
        </button>
      )}
      {problem && (
        <p role="alert" className="text-[16px] font-bold text-[#ffb3a6]">
          {problem}
        </p>
      )}
    </div>
  );
}
