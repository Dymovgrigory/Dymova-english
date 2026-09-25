"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/design/Button";
import { Choice } from "@/design/Choice";
import { Foxy } from "@/design/Foxy";
import { Icon } from "@/design/Icon";
import { ProgressBar } from "@/design/ProgressBar";
import { LoginFlow } from "@/features/login/LoginFlow";
import { RecoveryFlow } from "@/features/recovery/RecoveryFlow";
import { RegistrationFlow } from "@/features/registration/RegistrationFlow";
import { hasPlayer, v2, verifiedPlayer } from "@/lib/v2/client";
import type { BookSummary, Courses } from "@/lib/v2/types";

type Step = "name" | "registration" | "grade" | "module" | "goal";
type AuthPanel = "none" | "login" | "recovery";

const GOALS = [
  { xp: 10, title: "Легко", note: "5 минут в день" },
  { xp: 20, title: "Нормально", note: "10 минут в день" },
  { xp: 30, title: "Всерьёз", note: "15 минут в день" },
];

const FOXY_LINES: Record<Step, string> = {
  name: "Привет! Я Foxy. Помогу подтянуть английский по твоему школьному учебнику.",
  registration: "Теперь попроси маму или папу заполнить анкету — так мы сохраним твой прогресс.",
  grade: "В каком ты классе? Откроем твой учебник Spotlight.",
  module: "Какой модуль сейчас проходите в школе? Начнём прямо с него.",
  goal: "Сколько будем заниматься каждый день?",
};

export function Onboarding() {
  const router = useRouter();
  const reduce = useReducedMotion();
  const [courses, setCourses] = useState<Courses | null>(null);
  const [step, setStep] = useState<Step>("name");
  const [name, setName] = useState("");
  const [book, setBook] = useState<BookSummary | null>(null);
  const [moduleId, setModuleId] = useState<string | null>(null);
  const [goal, setGoal] = useState(20);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [returning, setReturning] = useState(false);
  const [authPanel, setAuthPanel] = useState<AuthPanel>("none");

  useEffect(() => {
    let alive = true;
    Promise.all([v2.courses(), verifiedPlayer()])
      .then(([data, known]) => {
        if (!alive) return;
        setCourses(data);
        setReturning(known);
        if (known) setStep("grade");
      })
      .catch(() => alive && setProblem("Не получилось загрузить учебники. Проверь интернет и обнови страницу."));
    return () => {
      alive = false;
    };
  }, []);

  const steps: Step[] = returning
    ? ["grade", "module", "goal"]
    : ["name", "registration", "grade", "module", "goal"];
  const position = steps.indexOf(step);

  const finish = async () => {
    if (!book || !moduleId) return;
    setBusy(true);
    setProblem(null);
    try {
      if (!hasPlayer()) await v2.ensurePlayer(name.trim() || "Ученик");
      await v2.saveProfile({ book_id: book.id, module_id: moduleId, daily_goal_xp: goal });
      const home = await v2.home();
      router.replace(home.current_node ? `/lesson/${home.current_node.id}` : "/learn");
    } catch (err) {
      setProblem(err instanceof Error ? err.message : "Не получилось сохранить. Попробуй ещё раз.");
      setBusy(false);
    }
  };

  const firstStep = 0;
  const back = () => setStep(steps[Math.max(position - 1, firstStep)]);

  if (authPanel === "recovery") {
    return (
      <div className="study mx-auto flex min-h-dvh w-full max-w-xl flex-col gap-5 px-4 py-8">
        <RecoveryFlow onDone={() => window.location.reload()} onCancel={() => setAuthPanel("login")} />
      </div>
    );
  }

  if (authPanel === "login") {
    return (
      <div className="study mx-auto flex min-h-dvh w-full max-w-xl flex-col gap-5 px-4 py-8">
        <LoginFlow
          onDone={() => window.location.reload()}
          onForgot={() => setAuthPanel("recovery")}
          onCancel={() => setAuthPanel("none")}
        />
      </div>
    );
  }

  return (
    <div className="study flex min-h-dvh flex-col">
      <header className="mx-auto flex w-full max-w-xl items-center gap-4 px-4 pt-5">
        <button
          type="button"
          onClick={back}
          disabled={position <= firstStep}
          aria-label="Назад"
          className="flex size-11 items-center justify-center rounded-full text-[#f6efe2] hover:bg-white/10 disabled:invisible"
        >
          <Icon name="back" size={28} />
        </button>
        <ProgressBar value={(position + 1) / steps.length} label="Шаги знакомства" />
      </header>

      <main className="mx-auto flex w-full max-w-xl flex-1 flex-col gap-6 px-4 pb-6 pt-6">
        <div className="flex items-end gap-3">
          <Foxy pose="wave" size={112} className="-mb-2 shrink-0" />
          <p className="mat-parchment relative mb-4 rounded-3xl rounded-bl-md px-4 py-3 text-[18px] font-bold leading-6">
            {FOXY_LINES[step]}
          </p>
        </div>

        <AnimatePresence mode="wait" initial={false}>
          <motion.section
            key={step}
            initial={reduce ? false : { opacity: 0, x: 24 }}
            animate={{ opacity: 1, x: 0 }}
            exit={reduce ? undefined : { opacity: 0, x: -24 }}
            transition={{ duration: 0.2 }}
            className="flex flex-col gap-3"
          >
            {step === "name" && (
              <label className="flex flex-col gap-2">
                <span className="text-[16px] font-extrabold text-[#f6efe2]">Как тебя зовут?</span>
                <input
                  autoFocus
                  value={name}
                  maxLength={24}
                  onChange={(e) => setName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && name.trim() && setStep("registration")}
                  placeholder="Имя"
                  className="h-16 rounded-2xl bg-[#fffaf0] px-5 text-[22px] font-bold text-ink shadow-[inset_0_3px_6px_rgb(92_60_30/0.25),0_0_0_2px_#c9a86a] outline-none focus:shadow-[inset_0_3px_6px_rgb(92_60_30/0.25),0_0_0_3px_#3fae98]"
                />
              </label>
            )}

            {step === "registration" && (
              <RegistrationFlow mode="gate" onDone={() => setStep("grade")} />
            )}

            {step === "grade" &&
              courses?.books.map((item) => (
                <Choice
                  key={item.id}
                  state={book?.id === item.id ? "selected" : "idle"}
                  onPick={() => {
                    setBook(item);
                    setModuleId(null);
                  }}
                >
                  <span className="mat-brass flex size-12 shrink-0 items-center justify-center rounded-full font-fairy text-[24px] font-black">
                    {item.grade}
                  </span>
                  <span className="flex flex-col">
                    <span className="text-[20px] font-extrabold">{item.grade} класс</span>
                    <span className="text-[15px] font-semibold text-ink-soft">
                      {item.title} · уровень {item.cefr}
                    </span>
                  </span>
                </Choice>
              ))}

            {step === "module" && book && (
              book.modules.length ? (
                book.modules.map((module) => (
                  <Choice key={module.id} state={moduleId === module.id ? "selected" : "idle"} onPick={() => setModuleId(module.id)}>
                    <span className="flex flex-col">
                      <span className="text-[13px] font-bold text-ink-soft">{module.label ?? `Модуль ${module.order}`}</span>
                      <span className="text-[20px] font-extrabold">{module.title_en}</span>
                      <span className="text-[15px] font-semibold text-ink-soft">{module.title_ru}</span>
                    </span>
                  </Choice>
                ))
              ) : (
                <p className="mat-parchment rounded-2xl p-4 text-[17px] font-bold">
                  Уроки для {book.title} скоро появятся. Выбери другой класс.
                </p>
              )
            )}

            {step === "goal" &&
              GOALS.map((option) => (
                <Choice key={option.xp} state={goal === option.xp ? "selected" : "idle"} onPick={() => setGoal(option.xp)}>
                  <span className="flex flex-1 items-center justify-between">
                    <span className="text-[20px] font-extrabold">{option.title}</span>
                    <span className="text-[16px] font-bold text-ink-soft">{option.note}</span>
                  </span>
                </Choice>
              ))}
          </motion.section>
        </AnimatePresence>
        {problem && <p role="alert" className="text-[16px] font-bold text-[#ffb3a6]">{problem}</p>}
      </main>

      <footer className="glass-dusk sticky bottom-0 px-4 pb-[max(1.25rem,env(safe-area-inset-bottom))] pt-4 lg:bottom-10 lg:mx-auto lg:w-full lg:max-w-xl lg:rounded-[28px] lg:pb-4">
        <div className="mx-auto max-w-xl">
          {step === "name" && <Button block disabled={!name.trim()} onClick={() => setStep("registration")}>Дальше</Button>}
          {step === "grade" && <Button block disabled={!book} onClick={() => setStep("module")}>Дальше</Button>}
          {step === "module" && <Button block disabled={!moduleId} onClick={() => setStep("goal")}>Дальше</Button>}
          {step === "goal" && (
            <Button block disabled={busy} onClick={finish}>
              {busy ? "Открываем учебник…" : "Начать первый урок"}
            </Button>
          )}
          {step === "name" && !returning && (
            <button
              type="button"
              onClick={() => setAuthPanel("login")}
              className="mt-2 min-h-11 w-full px-4 text-center text-[15px] font-bold text-[#c9bfd8] underline"
            >
              Уже есть аккаунт? Войти
            </button>
          )}
        </div>
      </footer>
    </div>
  );
}
