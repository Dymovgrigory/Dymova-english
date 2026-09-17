"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/design/Button";
import { ContentImage } from "@/design/ContentImage";
import { Foxy } from "@/design/Foxy";
import { Icon } from "@/design/Icon";
import { ProgressBar } from "@/design/ProgressBar";
import { Shell } from "@/design/Shell";
import { Sound } from "@/design/Sound";
import { isProfileMissing, isUnauthorized, v2 } from "@/lib/v2/client";
import type { Courses, Home, WordsBook } from "@/lib/v2/types";

type Status<T> = { state: "loading" } | { state: "error"; message: string } | { state: "ready"; data: T };

/** Загрузка данных раздела; без профиля ученика — на знакомство. */
function useSection<T>(load: () => Promise<T>): Status<T> {
  const router = useRouter();
  const [status, setStatus] = useState<Status<T>>({ state: "loading" });
  useEffect(() => {
    let alive = true;
    load()
      .then((data) => alive && setStatus({ state: "ready", data }))
      .catch((err) => {
        if (!alive) return;
        if (isProfileMissing(err) || isUnauthorized(err)) router.replace("/onboarding");
        else setStatus({ state: "error", message: err instanceof Error ? err.message : "Не получилось загрузить." });
      });
    return () => {
      alive = false;
    };
    // load — стабильная функция модуля
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);
  return status;
}

function SectionTitle({ title, line }: { title: string; line: string }) {
  return (
    <div className="mb-6">
      <h1 className="font-fairy text-[36px] font-black leading-10 text-[#ffd36e]">{title}</h1>
      <p className="mt-1 text-[17px] font-semibold text-[#c9bfd8]">{line}</p>
    </div>
  );
}

function Pending<T>({ status }: { status: Status<T> }) {
  if (status.state === "loading") return <p className="py-16 text-center text-[18px] font-extrabold text-[#c9bfd8]" role="status">Загружаем…</p>;
  if (status.state === "error") return <p className="py-16 text-center text-[18px] font-extrabold text-[#ffb3a6]" role="alert">{status.message}</p>;
  return null;
}

const strengthLabel = (strength: number) => (strength >= 4 ? "Знаю твёрдо" : strength >= 2 ? "Запоминаю" : "Нужно повторить");

export function PracticeScreen() {
  const router = useRouter();
  const status = useSection(() => v2.home());
  return (
    <Shell>
      <div className="mx-auto max-w-2xl px-4 py-8">
        <SectionTitle title="Тренировка" line="Foxy собирает слова, которые начали забываться, и слова с ошибками." />
        <Pending status={status} />
        {status.state === "ready" && (
          <section className="mat-parchment flex flex-col items-center gap-5 rounded-3xl px-6 py-8 text-center">
            <Foxy pose="think" size={140} />
            <p className="text-[22px] font-extrabold text-ink">
              {status.data.due_count > 0 ? `Ждут повторения: ${status.data.due_count}` : "Всё свежее в памяти"}
            </p>
            <p className="max-w-sm text-[16px] font-semibold text-ink-soft">
              {status.data.due_count > 0
                ? "Короткая тренировка из 12 заданий — примерно 3 минуты."
                : "Можно всё равно потренировать самые слабые слова."}
            </p>
            <Button onClick={() => router.push("/lesson/practice")}>Начать тренировку</Button>
          </section>
        )}
      </div>
    </Shell>
  );
}

export function WordsScreen() {
  const status = useSection<{ home: Home; words: WordsBook }>(async () => {
    const home = await v2.home();
    return { home, words: await v2.words(home.profile.book_id) };
  });
  return (
    <Shell>
      <div className="mx-auto max-w-2xl px-4 py-8">
        <SectionTitle title="Мой словарь" line="Слова из пройденных модулей учебника и то, насколько крепко ты их помнишь." />
        <Pending status={status} />
        {status.state === "ready" && !status.data.words.modules.length && (
          <div className="mat-parchment flex flex-col items-center gap-3 rounded-3xl px-6 py-10 text-center">
            <Icon name="book" size={40} className="text-royal" />
            <p className="text-[18px] font-extrabold text-ink">Словарь пока пуст</p>
            <p className="text-[16px] font-semibold text-ink-soft">Пройди первый урок — слова появятся здесь.</p>
          </div>
        )}
        {status.state === "ready" &&
          status.data.words.modules.map((module) => (
            <section key={module.id} className="mb-8">
              <h2 className="mb-3 font-fairy text-[22px] font-black text-[#ffd36e]">
                {module.title_en} <span className="text-[16px] font-semibold text-[#c9bfd8]">{module.title_ru}</span>
              </h2>
              <ul className="mat-parchment overflow-hidden rounded-3xl">
                {module.words.map((word) => (
                  <li key={word.id} className="flex items-center gap-4 border-b border-[#cdb58a]/60 px-4 py-3 last:border-b-0">
                    <ContentImage path={word.image} alt={word.en} className="size-12 shrink-0 rounded-xl text-[12px]" fallback="" />
                    <span className="flex-1">
                      <span className="block text-[19px] font-extrabold text-ink">{word.en}</span>
                      <span className="block text-[15px] font-semibold text-ink-soft">{word.ru}</span>
                    </span>
                    <span className="hidden w-32 flex-col gap-1 sm:flex">
                      <span className="text-[12px] font-bold text-ink-soft">{strengthLabel(word.strength)}</span>
                      <ProgressBar value={word.strength / 5} label={`Сила слова ${word.en}`} />
                    </span>
                    <Sound text={word.en} />
                  </li>
                ))}
              </ul>
            </section>
          ))}
      </div>
    </Shell>
  );
}

export function ProfileScreen() {
  const router = useRouter();
  const status = useSection<{ home: Home; courses: Courses }>(async () => {
    const [home, courses] = await Promise.all([v2.home(), v2.courses()]);
    return { home, courses };
  });
  const ready = status.state === "ready" ? status.data : null;
  const book = ready?.courses.books.find((b) => b.id === ready.home.profile.book_id);
  const schoolModule = book?.modules.find((m) => m.id === ready?.home.profile.module_id);
  return (
    <Shell>
      <div className="mx-auto max-w-2xl px-4 py-8">
        <Pending status={status} />
        {ready && (
          <>
            <div className="mb-8 flex items-center gap-4">
              <span className="mat-brass flex size-20 items-center justify-center rounded-full font-fairy text-[34px] font-black">
                {ready.home.player.display_name.slice(0, 1).toUpperCase()}
              </span>
              <div>
                <h1 className="font-fairy text-[32px] font-black text-[#ffd36e]">{ready.home.player.display_name}</h1>
                <p className="text-[16px] font-semibold text-[#c9bfd8]">
                  {book ? `${book.grade} класс · ${book.title}` : ""}
                </p>
              </div>
            </div>
            <div className="mb-8 grid grid-cols-3 gap-3">
              {[
                { icon: "flame" as const, value: ready.home.streak_days, label: "дней подряд", tone: "text-[#ff8a3d]" },
                { icon: "bolt" as const, value: ready.home.player.xp, label: "опыта всего", tone: "text-[#c9a400]" },
                { icon: "coin" as const, value: ready.home.player.coins, label: "монет", tone: "text-[#d69e00]" },
              ].map((stat) => (
                <div key={stat.label} className="mat-enamel flex flex-col items-center gap-1 rounded-2xl py-4">
                  <Icon name={stat.icon} size={26} filled={stat.icon !== "coin"} className={stat.tone} />
                  <span className="text-[24px] font-extrabold tabular-nums text-ink">{stat.value}</span>
                  <span className="text-[13px] font-bold text-ink-soft">{stat.label}</span>
                </div>
              ))}
            </div>
            <section className="mat-parchment rounded-3xl p-5">
              <h2 className="text-[18px] font-extrabold text-ink">Мой класс</h2>
              <p className="mt-1 text-[16px] font-semibold text-ink-soft">
                Сейчас в школе: {schoolModule ? `${schoolModule.title_en} (${schoolModule.title_ru})` : "—"}. Цель дня: {ready.home.daily_goal_xp} опыта.
              </p>
              <Button variant="paper" size="md" className="mt-4" onClick={() => router.push("/onboarding")}>
                Сменить класс или модуль
              </Button>
            </section>
          </>
        )}
      </div>
    </Shell>
  );
}
