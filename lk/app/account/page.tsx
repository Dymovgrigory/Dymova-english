"use client";

// Пароль для входа: родитель задаёт или меняет пароль (логин — телефон).
import { FormEvent, useState } from "react";
import CabinetPage from "@/components/cabinet-page";
import { useCabinet } from "@/lib/cabinet";
import { useI18n } from "@/lib/i18n";
import { api } from "@/lib/api";

export default function AccountPage() {
  return (
    <CabinetPage>
      <Account />
    </CabinetPage>
  );
}

function Account() {
  const { lang } = useI18n();
  const ru = lang === "ru";
  const { token } = useCabinet();
  const [p1, setP1] = useState("");
  const [p2, setP2] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (p1.length < 6) return setMsg({ ok: false, text: ru ? "Пароль должен быть не короче 6 символов." : "At least 6 characters." });
    if (p1 !== p2) return setMsg({ ok: false, text: ru ? "Пароли не совпадают." : "Passwords don't match." });
    if (!token) return;
    setBusy(true);
    try {
      await api.setPassword(token, p1);
      setMsg({ ok: true, text: ru ? "Пароль сохранён. Теперь входите по телефону и этому паролю." : "Saved. Log in with your phone and this password." });
      setP1(""); setP2("");
    } catch {
      setMsg({ ok: false, text: ru ? "Не получилось сохранить. Попробуйте ещё раз." : "Could not save. Try again." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="k-dict">
      <section className="k-dict-head"><div>
        <h1>{ru ? "Пароль для входа" : "Login password"}</h1>
        <p>{ru ? "Логин — номер телефона родителя. Задайте пароль, чтобы входить без бота." : "Your login is the parent's phone number."}</p>
      </div></section>
      <form className="k-panel k-form" onSubmit={onSubmit}>
        <label className="k-field"><span>{ru ? "Новый пароль" : "New password"}</span>
          <input type="password" autoComplete="new-password" value={p1} onChange={(e) => setP1(e.target.value)} maxLength={200} /></label>
        <label className="k-field"><span>{ru ? "Повторите пароль" : "Repeat"}</span>
          <input type="password" autoComplete="new-password" value={p2} onChange={(e) => setP2(e.target.value)} maxLength={200} /></label>
        {msg && <p className={msg.ok ? "g-done" : "k-err"} role="status">{msg.text}</p>}
        <button className="k-btn k-btn-go" disabled={busy}>{ru ? "Сохранить пароль" : "Save password"}</button>
      </form>
    </div>
  );
}
