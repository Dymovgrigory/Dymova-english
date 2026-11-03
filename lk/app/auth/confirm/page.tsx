"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { getPendingPhone, getToken, setSession } from "@/lib/session";
import { useI18n } from "@/lib/i18n";
import LangSwitch from "@/components/lang-switch";

const BOT_LINKS = {
  max: { url: "https://max.ru/id611904726658_bot", abbr: "MAX" },
  telegram: { url: "https://t.me/foxinburg", abbr: "TG" },
};

export default function ConfirmPage() {
  const router = useRouter();
  const { t } = useI18n();
  const phone = typeof window !== "undefined" ? getPendingPhone() : null;
  const [masked, setMasked] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    if (getToken()) {
      router.replace("/dashboard");
      return;
    }
    if (!phone) {
      router.replace("/auth");
      return;
    }
    api
      .status(phone)
      .then((s) => setMasked(s.phone_masked))
      .catch(() => setMasked(null));
  }, [phone, router]);

  async function check(): Promise<boolean> {
    if (!phone) return false;
    try {
      const out = await api.confirmBot(phone);
      if (out.token) {
        setSession(out.token);
        router.replace("/dashboard");
        return true;
      }
      return false;
    } catch (err) {
      const code = (err as { code?: string }).code || "";
      if (code === "bot_phone_unconfirmed") {
        setNotice(t.confirm.noticeUnconfirmed);
      } else if (code === "too_many_attempts") {
        setNotice(t.confirm.noticeMany);
      } else if ((err as { status?: number }).status === 502) {
        setNotice(t.confirm.noticeBot);
      } else {
        setNotice(t.confirm.noticeGeneric);
      }
      return false;
    }
  }

  // Автопроверка раз в 7 секунд, пока экран открыт.
  useEffect(() => {
    if (!phone) return;
    let stopped = false;
    async function tick() {
      if (stopped) return;
      const ok = await check();
      if (!ok && !stopped) {
        pollRef.current = window.setTimeout(() => void tick(), 7000);
      }
    }
    pollRef.current = window.setTimeout(() => void tick(), 4000);
    return () => {
      stopped = true;
      if (pollRef.current) window.clearTimeout(pollRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phone]);

  async function onCheckClick() {
    setBusy(true);
    setNotice("");
    await check();
    setBusy(false);
  }

  if (!phone) return null;

  return (
    <main className="shell-main">
      <div className="card center-card">
        <div className="auth-lang">
          <LangSwitch />
        </div>
        <h1 className="card-title">{t.confirm.title}</h1>
        <p className="card-sub">
          <strong>{masked || phone}</strong>. {t.confirm.sub}
        </p>
        <ol className="steps">
          <li>{t.confirm.step1}</li>
          <li>{t.confirm.step2}</li>
          <li>{t.confirm.step3}</li>
        </ol>
        <div className="bot-links">
          {Object.entries(BOT_LINKS).map(([key, b]) => (
            <a
              key={b.abbr}
              className="bot-link"
              href={b.url}
              target="_blank"
              rel="noopener"
            >
              <span className="bot-dot" style={{ background: "var(--purple-2)" }}>
                {b.abbr}
              </span>
              {key === "max" ? t.confirm.botMax : t.confirm.botTg}
            </a>
          ))}
        </div>
        {notice && <div className="alert alert-info">{notice}</div>}
        <button className="btn btn-primary" onClick={onCheckClick} disabled={busy}>
          {busy ? <span className="spin" aria-hidden="true" /> : null}
          {busy ? t.confirm.checking : t.confirm.check}
        </button>
        <p className="form-note">{t.confirm.note}</p>
      </div>
    </main>
  );
}
