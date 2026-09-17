"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/design/Button";
import { Choice } from "@/design/Choice";
import { Foxy } from "@/design/Foxy";
import { Icon } from "@/design/Icon";
import { ProgressBar } from "@/design/ProgressBar";
import { hasPlayer, v2, verifiedPlayer } from "@/lib/v2/client";
import type { BookSummary, Courses } from "@/lib/v2/types";

type Step = "name" | "grade" | "module" | "goal";

const GOALS = [
  { xp: 10, title: "Легко", note: "5 минут в день" },
  { xp: 20, title: "Нормально", note: "10 минут в день" },
  { xp: 30, title: "Всерьёз", note: "15 минут в день" },
];

const FOXY_LINES: Record<Step, string> = {
  name: "Привет! Я Foxy. Помогу подтянуть английский по твоему школьному учебнику.",
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

  const steps: Step[] = ["name", "grade", "module", "goal"];
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

  const firstStep = returning ? 1 : 0;
  const back = () => setStep(steps[Math.max(position - 1, firstStep)]);

  return (
    <div className="study flex min-h-dvh flex-col">
      <header className="mx-auto flex w-full max-w-xl items-center gap-4 px-4 pt-5">
        <button
          type="button"
          onClick={back}
          disabled={position <= firstStep}
          aria-label="Назад"
          className="flex size-11 items-center justify-center rounded-xl text-ink-soft hover:bg-grid disabled:invisible"
        >
          <Icon name="back" size={28} />
        </button>
        <ProgressBar value={(position + 1) / steps.length} label="Шаги знакомства" />
      </header>

      <main className="mx-auto flex w-full max-w-xl flex-1 flex-col gap-6 px-4 pb-6 pt-6">
        <div className="flex items-end gap-3">
          <Foxy pose="wave" size={112} className="-mb-2 shrink-0" />
          <p className="relative mb-4 rounded-3xl rounded-bl-md border-2 border-line bg-white px-4 py-3 text-[18px] font-bold leading-6 text-ink">
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
                <span className="text-[16px] font-extrabold text-ink-soft">Как тебя зовут?</span>
                <input
                  autoFocus
                  value={name}
                  maxLength={24}
                  onChange={(e) => setName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && name.trim() && setStep("grade")}
                  placeholder="Имя"
                  className="h-16 rounded-2xl border-2 border-line bg-white px-5 text-[22px] font-bold text-ink outline-none focus:border-royal"
                />
              </label>
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
                  <span className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-royal font-heading text-[24px] font-extrabold text-crown">
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
                      <span className="text-[20px] font-extrabold">{module.title_en}</span>
                      <span className="text-[15px] font-semibold text-ink-soft">{module.title_ru}</span>
                    </span>
                  </Choice>
                ))
              ) : (
                <p className="rounded-2xl border-2 border-line bg-white p-4 text-[17px] font-bold text-ink-soft">
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
        {problem && <p role="alert" className="text-[16px] font-bold text-coral-ink">{problem}</p>}
      </main>

      <footer className="sticky bottom-0 border-t-2 border-line bg-paper/95 px-4 pb-[max(1.25rem,env(safe-area-inset-bottom))] pt-4 backdrop-blur">
        <div className="mx-auto max-w-xl">
          {step === "name" && <Button block disabled={!name.trim()} onClick={() => setStep("grade")}>Дальше</Button>}
          {step === "grade" && <Button block disabled={!book} onClick={() => setStep("module")}>Дальше</Button>}
          {step === "module" && <Button block disabled={!moduleId} onClick={() => setStep("goal")}>Дальше</Button>}
          {step === "goal" && (
            <Button block disabled={busy} onClick={finish}>
              {busy ? "Открываем учебник…" : "Начать первый урок"}
            </Button>
          )}
        </div>
      </footer>
    </div>
  );
}
