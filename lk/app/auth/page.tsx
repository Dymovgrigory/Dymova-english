"use client";

// Вход в личный кабинет: телефон + пароль. Новые клиенты регистрируются здесь же —
// аккаунт создаётся сразу, а в CRM школы уходит заявка. Пароль родитель придумывает сам.
// Ученикам школы пароль выдаёт администратор; можно и подтвердить номер через бота.
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { api, CONSENT_VERSION, formatPhoneInput, phoneComplete } from "@/lib/api";
import { setSession } from "@/lib/session";
import { useI18n } from "@/lib/i18n";
import LangSwitch from "@/components/lang-switch";

type Mode = "login" | "register";

const ERR_RU: Record<string, string> = {
  bad_credentials: "Неверный телефон или пароль.",
  too_many_attempts: "Слишком много попыток. Подождите 15 минут или попросите администратора сменить пароль.",
  already_registered: "Этот телефон уже зарегистрирован. Войдите с паролем.",
  already_client: "Этот номер уже есть в базе школы. Войдите с паролем из приложения школы (он же — в «Данных для входа» у администратора). Не помните пароль — спросите администратора.",
  crm_unavailable: "Не получилось создать карточку в школе. Попробуйте через пару минут или позвоните нам.",
  password_too_short: "Пароль должен быть не короче 6 символов.",
  daily_limit: "Слишком много попыток за сутки. Попробуйте завтра или позвоните в школу.",
  name_required: "Укажите имя родителя и ребёнка.",
  bad_phone: "Проверьте номер телефона.",
};
const ERR_EN: Record<string, string> = {
  bad_credentials: "Wrong phone or password.",
  too_many_attempts: "Too many attempts. Wait 15 minutes or ask the school to reset your password.",
  already_registered: "This phone is already registered. Please log in.",
  already_client: "This number is already in the school database. Log in with your school app password, or ask the administrator.",
  crm_unavailable: "Could not create your school record. Try again in a few minutes or call us.",
  password_too_short: "The password must be at least 6 characters.",
  daily_limit: "Too many attempts today. Try tomorrow or call the school.",
  name_required: "Please enter the parent's and the child's names.",
  bad_phone: "Please check the phone number.",
};

export default function AuthPage() {
  const router = useRouter();
  const { lang } = useI18n();
  const ru = lang === "ru";
  const [mode, setMode] = useState<Mode>("login");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [parent, setParent] = useState("");
  const [child, setChild] = useState("");
  const [age, setAge] = useState("");
  const [pd, setPd] = useState(false);
  const [privacy, setPrivacy] = useState(false);
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const errText = (code: string) => (ru ? ERR_RU : ERR_EN)[code.split(":")[0]]
    ?? (code.startsWith("consent_required") ? (ru ? "Нужно согласие на обработку данных." : "Please accept the consents.")
      : ru ? "Что-то пошло не так. Попробуйте ещё раз." : "Something went wrong. Please try again.");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (!phoneComplete(phone)) return setError(ru ? "Введите номер полностью." : "Enter the full phone number.");
    if (password.length < 6) return setError(errText("password_too_short"));
    if (mode === "register") {
      if (!parent.trim() || !child.trim()) return setError(errText("name_required"));
      if (password !== password2) return setError(ru ? "Пароли не совпадают." : "Passwords don't match.");
      if (!pd || !privacy) return setError(ru ? "Отметьте оба согласия." : "Please tick both consents.");
    }
    setBusy(true);
    try {
      const out = mode === "login"
        ? await api.login(phone, password)
        : await api.register({
          phone, password, parent_name: parent.trim(), child_name: child.trim(), child_age: age.trim(),
          consents: [{ type: "pd_child", version: CONSENT_VERSION }, { type: "privacy", version: CONSENT_VERSION }],
        });
      if (out.token) {
        setSession(out.token);
        router.replace("/dashboard");
      }
    } catch (err) {
      setError(errText((err as { code?: string }).code || ""));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="shell-main">
      <div className="card center-card auth-card">
        <div className="auth-lang"><LangSwitch /></div>
        <img className="auth-fox" src="/foxi/guide.webp" alt="" width={70} height={115} />
        <h1 className="card-title">{ru ? "Личный кабинет Фоксинбурга" : "Foxinburg personal account"}</h1>
        <div className="auth-tabs" role="tablist">
          <button role="tab" aria-selected={mode === "login"} className={mode === "login" ? "is-on" : ""} onClick={() => { setMode("login"); setError(""); }}>
            {ru ? "Вход" : "Log in"}
          </button>
          <button role="tab" aria-selected={mode === "register"} className={mode === "register" ? "is-on" : ""} onClick={() => { setMode("register"); setError(""); }}>
            {ru ? "Регистрация" : "Sign up"}
          </button>
        </div>
        <p className="card-sub">
          {mode === "login"
            ? ru ? "Логин — номер телефона. Пароль тот же, что в приложении школы (его выдаёт администратор), или тот, что вы придумали при регистрации."
              : "Your login is the parent's phone number. The password comes from the school or the one you chose when signing up."
            : ru ? "Для новых учеников. Мы создадим карточку ученика в школе, а кабинет откроется сразу."
              : "For new students. The school gets your request and will contact you; the account opens right away."}
        </p>
        {error && <div className="alert alert-error" role="alert">{error}</div>}
        <form onSubmit={onSubmit} noValidate>
          {mode === "register" && (
            <>
              <label className="field">
                <span>{ru ? "Имя родителя" : "Parent's name"}</span>
                <input type="text" autoComplete="name" value={parent} onChange={(e) => setParent(e.target.value)} maxLength={120} />
              </label>
              <div className="field-row">
                <label className="field">
                  <span>{ru ? "Имя ребёнка" : "Child's name"}</span>
                  <input type="text" value={child} onChange={(e) => setChild(e.target.value)} maxLength={120} />
                </label>
                <label className="field field-age">
                  <span>{ru ? "Возраст" : "Age"}</span>
                  <input type="text" inputMode="numeric" value={age} onChange={(e) => setAge(e.target.value.replace(/[^\d]/g, "").slice(0, 2))} />
                </label>
              </div>
            </>
          )}
          <label className="field">
            <span>{ru ? "Телефон" : "Phone"}</span>
            <input type="tel" inputMode="tel" autoComplete="username" placeholder="+7 (___) ___-__-__" value={phone}
              onChange={(e) => setPhone(formatPhoneInput(e.target.value))} />
          </label>
          <label className="field">
            <span>{mode === "login" ? (ru ? "Пароль" : "Password") : (ru ? "Придумайте пароль (от 6 символов)" : "Create a password (6+ characters)")}</span>
            <span className="field-pass">
              <input type={show ? "text" : "password"} autoComplete={mode === "login" ? "current-password" : "new-password"}
                value={password} onChange={(e) => setPassword(e.target.value)} maxLength={200} />
              <button type="button" className="field-eye" onClick={() => setShow(!show)}>{show ? (ru ? "Скрыть" : "Hide") : (ru ? "Показать" : "Show")}</button>
            </span>
          </label>
          {mode === "register" && (
            <>
              <label className="field">
                <span>{ru ? "Повторите пароль" : "Repeat the password"}</span>
                <input type={show ? "text" : "password"} autoComplete="new-password" value={password2} onChange={(e) => setPassword2(e.target.value)} maxLength={200} />
              </label>
              <label className="consent">
                <input type="checkbox" checked={pd} onChange={(e) => setPd(e.target.checked)} />
                <span>{ru ? "Согласен(на) на обработку персональных данных — моих и ребёнка" : "I agree to the processing of my and my child's personal data"}</span>
              </label>
              <label className="consent">
                <input type="checkbox" checked={privacy} onChange={(e) => setPrivacy(e.target.checked)} />
                <span>{ru ? "Принимаю " : "I accept the "}
                  <a href="https://dymova-english.ru/policy" target="_blank" rel="noopener">{ru ? "политику конфиденциальности" : "privacy policy"}</a></span>
              </label>
            </>
          )}
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? <span className="spin" aria-hidden="true" /> : null}
            {mode === "login" ? (ru ? "Войти" : "Log in") : (ru ? "Зарегистрироваться" : "Sign up")}
          </button>
        </form>
        <p className="form-note">
          {ru ? "Не помните пароль? Его подскажет администратор школы, или " : "A student but no password? Ask the administrator or "}
          <a href="/auth/bot">{ru ? "подтвердите номер через бота" : "confirm your number with the bot"}</a>.
        </p>
      </div>
    </main>
  );
}
