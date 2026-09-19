"use client";

import { useEffect, useMemo, useState } from "react";

import { Button } from "@/design/Button";
import { Choice } from "@/design/Choice";
import { Foxy } from "@/design/Foxy";
import { humanizeError } from "@/lib/api";
import { CONSENT_LABELS, CONSENT_LINKS, LEGAL_VERSION, type ConsentType } from "@/lib/legal";
import {
  RegistrationError,
  registrationApi,
  type RegistrationChannel,
  type RegistrationStartBody,
} from "@/lib/v2/registration";

import { formatPhone, subscriberDigits, toE164 } from "./phone";

type FlowStep = "profile" | "contacts" | "consents" | "code" | "success";

const STEP_TITLES: Record<FlowStep, string> = {
  profile: "Анкета ученика",
  contacts: "Контакты родителя",
  consents: "Согласия",
  code: "Код подтверждения",
  success: "Готово!",
};

const inputCls =
  "h-14 w-full rounded-2xl bg-[#fffaf0] px-4 text-[18px] font-bold text-ink shadow-[inset_0_3px_6px_rgb(92_60_30/0.25),0_0_0_2px_#c9a86a] outline-none focus:shadow-[inset_0_3px_6px_rgb(92_60_30/0.25),0_0_0_3px_#3fae98]";

const labelCls = "text-[15px] font-extrabold text-[#f6efe2]";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className={labelCls}>{label}</span>
      {children}
    </label>
  );
}

function ConsentRow({
  type,
  checked,
  required,
  onToggle,
}: {
  type: ConsentType;
  checked: boolean;
  required: boolean;
  onToggle: () => void;
}) {
  const link = CONSENT_LINKS[type];
  return (
    <div className="mat-enamel flex min-h-11 w-full items-start gap-3 rounded-2xl px-4 py-3">
      <button
        type="button"
        role="checkbox"
        aria-checked={checked}
        onClick={onToggle}
        className="press flex flex-1 items-start gap-3 text-left focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[#ffd36e]/70"
      >
        <span
          aria-hidden
          className={`mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg text-[16px] font-black ${
            checked ? "bg-[#3fae98] text-white shadow-[inset_0_-2px_0_#1f6f60]" : "bg-[#fffaf0] shadow-[inset_0_0_0_2px_#c9a86a]"
          }`}
        >
          {checked ? "✓" : ""}
        </span>
        <span className="text-[15px] font-bold leading-5 text-ink">
          {CONSENT_LABELS[type]}
          {required && <span className="text-[#c73c30]"> *</span>}
        </span>
      </button>
      {link && (
        <a
          href={link}
          target="_blank"
          rel="noreferrer"
          className="mt-0.5 inline-flex min-h-11 shrink-0 items-center text-[14px] font-bold text-ink underline"
        >
          Читать
        </a>
      )}
    </div>
  );
}

export function RegistrationFlow({
  mode,
  onDone,
  onCancel,
  prefillFirstName = "",
}: {
  /** gate — обязательная регистрация: без кнопки «Заполню позже». */
  mode: "onboarding" | "edit" | "gate";
  onDone: () => void;
  onCancel?: () => void;
  /** Имя из профиля мессенджера — предзаполнение анкеты. */
  prefillFirstName?: string;
}) {
  const [step, setStep] = useState<FlowStep>("profile");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  const [firstName, setFirstName] = useState(prefillFirstName);
  const [lastName, setLastName] = useState("");
  const [birthDate, setBirthDate] = useState("");
  const [schoolNumber, setSchoolNumber] = useState("");
  const [classGrade, setClassGrade] = useState<number | null>(null);
  const [classLetter, setClassLetter] = useState("");
  const [phoneDigits, setPhoneDigits] = useState("");
  const [email, setEmail] = useState("");
  const [channel, setChannel] = useState<RegistrationChannel>("sms");
  const [consents, setConsents] = useState<Record<ConsentType, boolean>>({
    pd_child: false,
    privacy: false,
    marketing: false,
  });
  const [code, setCode] = useState("");
  const [phoneMasked, setPhoneMasked] = useState("");
  const [cooldown, setCooldown] = useState(0);

  // В режиме редактирования (и на всякий случай в онбординге) предзаполняем анкету.
  useEffect(() => {
    let alive = true;
    registrationApi
      .status()
      .then((status) => {
        if (!alive || !status.identity) return;
        const id = status.identity;
        setFirstName(id.first_name);
        setLastName(id.last_name);
        setBirthDate(id.birth_date);
        setSchoolNumber(id.school_number);
        setClassGrade(id.class_grade);
        setClassLetter(id.class_letter ?? "");
        setEmail(id.parent_email);
        const accepted = new Set(status.consents.map((c) => c.type));
        setConsents({
          pd_child: accepted.has("pd_child"),
          privacy: accepted.has("privacy"),
          marketing: accepted.has("marketing"),
        });
      })
      .catch(() => {
        /* анкеты ещё нет — начинаем с пустой */
      })
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (step !== "code" || cooldown <= 0) return;
    const timer = setInterval(() => setCooldown((v) => Math.max(0, v - 1)), 1000);
    return () => clearInterval(timer);
  }, [step, cooldown > 0]); // eslint-disable-line react-hooks/exhaustive-deps

  const e164 = toE164(phoneDigits);
  const emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());

  const profileOk =
    firstName.trim().length > 0 && lastName.trim().length > 0 && birthDate.length === 10 &&
    schoolNumber.trim().length > 0 && classGrade !== null;
  const contactsOk = e164 !== null && emailOk;
  const consentsOk = consents.pd_child && consents.privacy;

  const startBody = useMemo<RegistrationStartBody | null>(() => {
    if (!e164 || classGrade === null) return null;
    return {
      first_name: firstName.trim(),
      last_name: lastName.trim(),
      birth_date: birthDate,
      school_number: schoolNumber.trim(),
      class_grade: classGrade,
      ...(classLetter.trim() ? { class_letter: classLetter.trim() } : {}),
      parent_email: email.trim(),
      parent_phone: e164,
      channel,
      consents: (Object.keys(consents) as ConsentType[])
        .filter((type) => consents[type])
        .map((type) => ({ type, version: LEGAL_VERSION })),
    };
  }, [e164, classGrade, firstName, lastName, birthDate, schoolNumber, classLetter, email, channel, consents]);

  const sendCode = async () => {
    if (!startBody) return;
    setBusy(true);
    setProblem(null);
    try {
      const res = await registrationApi.start(startBody);
      setPhoneMasked(res.phone_masked);
      setCooldown(res.cooldown_sec || 60);
      setCode("");
      setStep("code");
    } catch (err) {
      setProblem(humanizeError(err, "Не получилось отправить код. Попробуйте ещё раз."));
    } finally {
      setBusy(false);
    }
  };

  const verifyCode = async () => {
    if (code.length !== 6) return;
    setBusy(true);
    setProblem(null);
    try {
      await registrationApi.verify(code);
      setStep("success");
    } catch (err) {
      if (err instanceof RegistrationError && err.message === "code_invalid") {
        setProblem(
          err.attemptsLeft !== undefined
            ? `Неверный код. Осталось попыток: ${err.attemptsLeft}`
            : "Неверный код",
        );
      } else {
        setProblem(humanizeError(err, "Не получилось проверить код. Попробуйте ещё раз."));
      }
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <p role="status" className="py-10 text-center text-[17px] font-extrabold text-[#c9bfd8]">
        Загружаем анкету…
      </p>
    );
  }

  return (
    <div className="flex w-full flex-col gap-4">
      <h2 className="font-fairy text-[26px] font-black text-[#ffd36e]">{STEP_TITLES[step]}</h2>

      {step === "profile" && (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Field label="Имя ребёнка">
              <input className={inputCls} value={firstName} maxLength={40} onChange={(e) => setFirstName(e.target.value)} placeholder="Аня" />
            </Field>
            <Field label="Фамилия">
              <input className={inputCls} value={lastName} maxLength={40} onChange={(e) => setLastName(e.target.value)} placeholder="Иванова" />
            </Field>
          </div>
          <Field label="Дата рождения">
            <input type="date" className={inputCls} value={birthDate} min="2005-01-01" max="2022-12-31" onChange={(e) => setBirthDate(e.target.value)} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Номер школы">
              <input className={inputCls} value={schoolNumber} maxLength={10} inputMode="numeric" onChange={(e) => setSchoolNumber(e.target.value)} placeholder="12" />
            </Field>
            <Field label="Буква класса (если есть)">
              <input className={inputCls} value={classLetter} maxLength={2} onChange={(e) => setClassLetter(e.target.value)} placeholder="А" />
            </Field>
          </div>
          <span className={labelCls}>Класс</span>
          <div className="grid grid-cols-4 gap-2">
            {Array.from({ length: 11 }, (_, i) => i + 1).map((grade) => (
              <button
                key={grade}
                type="button"
                aria-pressed={classGrade === grade}
                onClick={() => setClassGrade(grade)}
                className={`press flex min-h-11 items-center justify-center rounded-xl text-[18px] font-extrabold focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[#ffd36e]/70 ${
                  classGrade === grade
                    ? "mat-brass"
                    : "mat-enamel"
                }`}
              >
                {grade}
              </button>
            ))}
          </div>
          <Button block disabled={!profileOk} onClick={() => setStep("contacts")}>
            Дальше
          </Button>
        </>
      )}

      {step === "contacts" && (
        <>
          <Field label="Телефон родителя">
            <input
              className={inputCls}
              value={formatPhone(phoneDigits)}
              inputMode="tel"
              autoComplete="tel"
              placeholder="+7 (___) ___-__-__"
              onChange={(e) => setPhoneDigits(subscriberDigits(e.target.value))}
            />
          </Field>
          <Field label="Email родителя">
            <input
              type="email"
              className={inputCls}
              value={email}
              inputMode="email"
              autoComplete="email"
              placeholder="parent@example.ru"
              onChange={(e) => setEmail(e.target.value)}
            />
          </Field>
          <span className={labelCls}>Как удобнее получить код?</span>
          <div className="grid grid-cols-2 gap-3">
            <Choice state={channel === "sms" ? "selected" : "idle"} onPick={() => setChannel("sms")}>
              <span className="flex flex-col">
                <span className="text-[18px] font-extrabold">SMS</span>
                <span className="text-[13px] font-semibold text-ink-soft">Код в сообщении</span>
              </span>
            </Choice>
            <Choice state={channel === "call" ? "selected" : "idle"} onPick={() => setChannel("call")}>
              <span className="flex flex-col">
                <span className="text-[18px] font-extrabold">Позвонить</span>
                <span className="text-[13px] font-semibold text-ink-soft">Код голосом</span>
              </span>
            </Choice>
          </div>
          <div className="flex gap-3">
            <Button variant="ghost" size="md" onClick={() => setStep("profile")}>
              Назад
            </Button>
            <Button block disabled={!contactsOk} onClick={() => setStep("consents")}>
              Дальше
            </Button>
          </div>
        </>
      )}

      {step === "consents" && (
        <>
          <ConsentRow type="pd_child" required checked={consents.pd_child} onToggle={() => setConsents((c) => ({ ...c, pd_child: !c.pd_child }))} />
          <ConsentRow type="privacy" required checked={consents.privacy} onToggle={() => setConsents((c) => ({ ...c, privacy: !c.privacy }))} />
          <ConsentRow type="marketing" required={false} checked={consents.marketing} onToggle={() => setConsents((c) => ({ ...c, marketing: !c.marketing }))} />
          <div className="flex gap-3">
            <Button variant="ghost" size="md" onClick={() => setStep("contacts")}>
              Назад
            </Button>
            <Button block disabled={!consentsOk || busy} onClick={sendCode}>
              {busy ? "Отправляем код…" : "Получить код"}
            </Button>
          </div>
        </>
      )}

      {step === "code" && (
        <>
          <p className="text-[16px] font-semibold text-[#c9bfd8]">
            {channel === "call" ? "Позвоним" : "Отправили SMS"} на номер {phoneMasked || formatPhone(phoneDigits)}.{" "}
            <button type="button" className="font-bold text-[#7fd8c9] underline" onClick={() => setStep("contacts")}>
              Изменить номер
            </button>
          </p>
          <label className="flex flex-col gap-1.5">
            <span className={labelCls}>Код из {channel === "call" ? "звонка" : "SMS"}</span>
            <input
              className={`${inputCls} h-16 text-center text-[28px] tracking-[0.4em]`}
              value={code}
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              placeholder="••••••"
              aria-label="Код подтверждения"
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              onKeyDown={(e) => e.key === "Enter" && verifyCode()}
            />
          </label>
          <Button block disabled={code.length !== 6 || busy} onClick={verifyCode}>
            {busy ? "Проверяем…" : "Подтвердить"}
          </Button>
          <div className="text-center">
            {cooldown > 0 ? (
              <p className="text-[15px] font-bold text-[#c9bfd8]">Отправить повторно через {cooldown}…</p>
            ) : (
              <button
                type="button"
                disabled={busy}
                onClick={sendCode}
                className="min-h-11 px-4 text-[15px] font-bold text-[#7fd8c9] underline disabled:opacity-50"
              >
                Отправить код ещё раз
              </button>
            )}
          </div>
        </>
      )}

      {step === "success" && (
        <div className="mat-parchment flex flex-col items-center gap-4 rounded-3xl px-6 py-8 text-center">
          <Foxy pose="cheer" size={140} />
          <p className="text-[20px] font-extrabold text-ink">Телефон подтверждён, анкета сохранена!</p>
          <p className="max-w-sm text-[15px] font-semibold text-ink-soft">
            Теперь прогресс ученика не потеряется, а родитель сможет восстановить доступ по номеру телефона.
          </p>
          <Button block onClick={onDone}>{mode === "edit" ? "Готово" : "Продолжить"}</Button>
        </div>
      )}

      {problem && (
        <p role="alert" className="text-[16px] font-bold text-[#ffb3a6]">
          {problem}
        </p>
      )}

      {mode === "onboarding" && step !== "success" && (
        <button
          type="button"
          aria-label="Заполню позже — пропустить анкету"
          onClick={onDone}
          className="min-h-11 px-4 text-[15px] font-bold text-[#c9bfd8] underline"
        >
          Заполню позже
        </button>
      )}

      {mode === "edit" && onCancel && step !== "success" && (
        <button type="button" onClick={onCancel} className="min-h-11 text-[15px] font-bold text-[#c9bfd8] underline">
          Отмена
        </button>
      )}
    </div>
  );
}
