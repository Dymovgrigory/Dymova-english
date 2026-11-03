"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { api, CONSENT_VERSION, formatPhoneInput, phoneComplete } from "@/lib/api";
import { setPendingPhone } from "@/lib/session";
import { useI18n } from "@/lib/i18n";
import LangSwitch from "@/components/lang-switch";

export default function AuthPage() {
  const router = useRouter();
  const { t } = useI18n();
  const [phone, setPhone] = useState("");
  const [name, setName] = useState("");
  const [pd, setPd] = useState(false);
  const [privacy, setPrivacy] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (!phoneComplete(phone)) {
      setError(t.auth.errIncompletePhone);
      return;
    }
    if (!name.trim()) {
      setError(t.auth.errEmptyName);
      return;
    }
    if (!pd || !privacy) {
      setError(t.auth.errNeedConsents);
      return;
    }
    setBusy(true);
    try {
      await api.start(phone, name.trim(), [
        { type: "pd_child", version: CONSENT_VERSION },
        { type: "privacy", version: CONSENT_VERSION },
      ]);
      setPendingPhone(phone);
      router.push("/auth/confirm");
    } catch (err) {
      const code = (err as { code?: string }).code || "";
      // Даже при повторном старте (cooldown) отправляем на экран ожидания —
      // аккаунт уже создан, там можно нажать «Проверить».
      if (code === "recently_sent" || code === "daily_limit") {
        setPendingPhone(phone);
        router.push("/auth/confirm");
        return;
      }
      setError(
        code === "recently_sent"
          ? t.auth.recently_sent
          : code === "daily_limit"
            ? t.auth.daily_limit
            : code === "consent_required"
              ? t.auth.consent_required
              : t.auth.generic,
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="shell-main">
      <div className="card center-card">
        <div className="auth-lang">
          <LangSwitch />
        </div>
        <h1 className="card-title">{t.auth.title}</h1>
        <p className="card-sub">{t.auth.sub}</p>
        {error && <div className="alert alert-error">{error}</div>}
        <form onSubmit={onSubmit} noValidate>
          <label className="field">
            <span>{t.auth.phoneLabel}</span>
            <input
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              placeholder="+7 (___) ___-__-__"
              value={phone}
              onChange={(e) => setPhone(formatPhoneInput(e.target.value))}
              aria-required="true"
            />
          </label>
          <label className="field">
            <span>{t.auth.nameLabel}</span>
            <input
              type="text"
              autoComplete="name"
              placeholder={t.auth.namePlaceholder}
              value={name}
              onChange={(e) => setName(e.target.value)}
              aria-required="true"
              maxLength={120}
            />
          </label>
          <label className="consent">
            <input type="checkbox" checked={pd} onChange={(e) => setPd(e.target.checked)} />
            <span>{t.auth.consentPd}</span>
          </label>
          <label className="consent">
            <input
              type="checkbox"
              checked={privacy}
              onChange={(e) => setPrivacy(e.target.checked)}
            />
            <span>
              {t.auth.consentPrivacy}{" "}
              <a href="https://dymova-english.ru/policy" target="_blank" rel="noopener">
                {t.auth.privacyLink}
              </a>
            </span>
          </label>
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? <span className="spin" aria-hidden="true" /> : null}
            {busy ? t.auth.submitting : t.auth.submit}
          </button>
          <p className="form-note">{t.auth.note}</p>
        </form>
      </div>
    </main>
  );
}
