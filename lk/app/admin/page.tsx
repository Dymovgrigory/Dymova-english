"use client";

// Админка школы в ЛК: пароли родителей. Вход — учётная запись сотрудника (та же, что в админке Мира).
// Пароли хранятся зашифрованными (хеш): администратор задаёт новый пароль и сообщает его родителю.
import { FormEvent, useCallback, useEffect, useState } from "react";
import { formatPhoneInput, phoneComplete } from "@/lib/api";

type Account = {
  id: number; phone: string; parent_name: string; kids: string; status: string;
  verified: boolean; has_password: boolean; registered_at: string; crm_lead: boolean;
};
const KEY = "lk_admin_token";

async function call<T>(path: string, token: string | null, body?: unknown): Promise<T> {
  const res = await fetch(`/api/v2/admin${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(String((data as { detail?: unknown }).detail ?? res.status)), { status: res.status });
  return data as T;
}

function genPassword() {
  const abc = "abcdefghjkmnpqrstuvwxyz23456789";
  const a = new Uint32Array(8);
  crypto.getRandomValues(a);
  return Array.from(a, (n) => abc[n % abc.length]).join("");
}

export default function AdminPage() {
  const [token, setToken] = useState<string | null>(null);
  const [login, setLogin] = useState("");
  const [pass, setPass] = useState("");
  const [err, setErr] = useState("");
  const [rows, setRows] = useState<Account[]>([]);
  const [q, setQ] = useState("");
  const [phone, setPhone] = useState("");
  const [name, setName] = useState("");
  const [newPass, setNewPass] = useState("");
  const [done, setDone] = useState("");

  useEffect(() => { try { setToken(sessionStorage.getItem(KEY)); } catch { /* нет хранилища */ } }, []);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      setRows((await call<{ accounts: Account[] }>(`/lk/accounts?q=${encodeURIComponent(q)}`, token)).accounts);
    } catch (e) {
      if ((e as { status?: number }).status === 401) { setToken(null); try { sessionStorage.removeItem(KEY); } catch { /* */ } }
    }
  }, [token, q]);
  useEffect(() => { void load(); }, [load]);

  async function onLogin(e: FormEvent) {
    e.preventDefault();
    setErr("");
    try {
      const r = await call<{ token: string }>("/login", null, { login, password: pass });
      setToken(r.token);
      try { sessionStorage.setItem(KEY, r.token); } catch { /* */ }
    } catch {
      setErr("Неверный логин или пароль сотрудника.");
    }
  }

  async function onSet(e: FormEvent) {
    e.preventDefault();
    setDone(""); setErr("");
    if (!phoneComplete(phone)) return setErr("Введите телефон полностью.");
    if (newPass.length < 6) return setErr("Пароль — от 6 символов.");
    try {
      await call("/lk/password", token, { phone, password: newPass, parent_name: name });
      setDone(`Готово. Сообщите родителю: логин ${phone}, пароль ${newPass}`);
      setPhone(""); setName(""); setNewPass("");
      void load();
    } catch {
      setErr("Не получилось сохранить пароль.");
    }
  }

  if (!token) {
    return (
      <main className="shell-main">
        <form className="card center-card" onSubmit={onLogin}>
          <h1 className="card-title">Админка школы</h1>
          <p className="card-sub">Вход сотрудника — те же логин и пароль, что в админке Мира.</p>
          {err && <div className="alert alert-error">{err}</div>}
          <label className="field"><span>Логин</span><input type="text" value={login} onChange={(e) => setLogin(e.target.value)} autoComplete="username" /></label>
          <label className="field"><span>Пароль</span><input type="password" value={pass} onChange={(e) => setPass(e.target.value)} autoComplete="current-password" /></label>
          <button className="btn btn-primary">Войти</button>
        </form>
      </main>
    );
  }

  return (
    <main className="adm">
      <header className="adm-head">
        <h1>Пароли родителей в личном кабинете</h1>
        <button className="k-btn k-btn-light" onClick={() => { setToken(null); try { sessionStorage.removeItem(KEY); } catch { /* */ } }}>Выйти</button>
      </header>
      <form className="adm-card" onSubmit={onSet}>
        <h2>Выдать или сменить пароль</h2>
        <p>Логин родителя — телефон из карточки BigBen. После выдачи пароля в кабинете появятся дети с этим номером из CRM.</p>
        {err && <div className="alert alert-error">{err}</div>}
        {done && <div className="alert adm-ok">{done}</div>}
        <div className="adm-row">
          <label className="field"><span>Телефон</span><input type="tel" value={phone} placeholder="+7 (___) ___-__-__" onChange={(e) => setPhone(formatPhoneInput(e.target.value))} /></label>
          <label className="field"><span>Имя родителя</span><input type="text" value={name} onChange={(e) => setName(e.target.value)} /></label>
          <label className="field"><span>Пароль</span><input type="text" value={newPass} onChange={(e) => setNewPass(e.target.value)} /></label>
          <button type="button" className="k-btn k-btn-light" onClick={() => setNewPass(genPassword())}>Придумать</button>
          <button className="k-btn k-btn-go">Сохранить</button>
        </div>
      </form>
      <section className="adm-card">
        <div className="adm-row"><h2>Аккаунты</h2>
          <input className="adm-search" placeholder="Поиск: имя или телефон" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <table className="adm-table">
          <thead><tr><th>Телефон</th><th>Родитель</th><th>Дети</th><th>Пароль</th><th>Номер</th><th>Заявка в CRM</th><th>Создан</th><th /></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.phone}</td><td>{r.parent_name}</td><td>{r.kids}</td>
                <td>{r.has_password ? "задан" : "—"}</td>
                <td>{r.verified ? "подтверждён" : "не подтверждён"}</td>
                <td>{r.crm_lead ? "отправлена" : "—"}</td>
                <td>{r.registered_at.slice(0, 10)}</td>
                <td><button className="k-btn k-btn-light adm-sm" onClick={() => { setPhone(formatPhoneInput(r.phone)); setName(r.parent_name); setNewPass(genPassword()); window.scrollTo({ top: 0, behavior: "smooth" }); }}>Сменить пароль</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}
