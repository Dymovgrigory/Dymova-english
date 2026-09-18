"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";

import { Button } from "@/design/Button";
import { Foxy } from "@/design/Foxy";
import { Icon, type IconName } from "@/design/Icon";
import { ProgressBar } from "@/design/ProgressBar";
import type { SessionResult } from "@/lib/v2/types";

type FinishProps = { result: SessionResult; onContinue: () => void; onRetry: () => void };

function formatDuration(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(seconds % 60).padStart(2, "0")}`;
}

function headline(result: SessionResult): { title: string; line: string } {
  if (result.kind === "trial") {
    return result.trial_passed
      ? { title: "Испытание пройдено!", line: "+5 монет — быстро и с первой попытки." }
      : { title: "Не успел — попробуй ещё раз сегодня", line: "Правило испытания: 5 слов, 15 секунд на ответ, с первой попытки." };
  }
  if (result.kind === "module_test") {
    return result.passed
      ? { title: "Контрольная сдана!", line: "Модуль пройден. Следующий уже открыт." }
      : { title: "Почти получилось", line: "Нужно хотя бы 60 % верных ответов. Повтори модуль и попробуй ещё раз." };
  }
  if (result.accuracy === 1) return { title: "Без единой ошибки!", line: "Ты знаешь эти слова на отлично." };
  if (result.kind === "practice") return { title: "Тренировка закончена", line: "Слабые слова стали крепче." };
  return { title: "Урок пройден!", line: "Ошибки мы повторили — теперь они запомнятся." };
}

function Stat({ icon, value, label, tone }: { icon: IconName; value: string; label: string; tone: string }) {
  return (
    <div className={`mat-enamel flex flex-1 flex-col items-center gap-1 rounded-2xl px-3 py-3 ${tone}`}>
      <Icon name={icon} size={24} filled={icon === "bolt"} />
      <span className="text-[24px] font-extrabold tabular-nums text-ink">{value}</span>
      <span className="text-[13px] font-bold text-ink-soft">{label}</span>
    </div>
  );
}

export function FinishScreen({ result, onContinue, onRetry }: FinishProps) {
  const reduce = useReducedMotion();
  const { title, line } = headline(result);
  const failed = (result.kind === "module_test" && !result.passed) || (result.kind === "trial" && !result.trial_passed);
  return (
    <div className="study flex min-h-dvh flex-col">
      <main className="mx-auto flex w-full max-w-xl flex-1 flex-col items-center gap-6 px-4 pb-8 pt-10 text-center"><div className="mat-parchment flex w-full flex-col items-center gap-6 rounded-[28px] px-5 pb-6 pt-4">
        <motion.div
          initial={reduce ? false : { scale: 0.6, opacity: 0, y: 20 }}
          animate={{ scale: 1, opacity: 1, y: 0 }}
          transition={{ type: "spring", stiffness: 220, damping: 16 }}
        >
          <Foxy pose={failed ? "think" : "cheer"} size={190} />
        </motion.div>
        <div>
          <h1 className="font-fairy text-[36px] font-black leading-10 text-[#4a2a66]">{title}</h1>
          <p className="mt-2 text-[18px] font-semibold text-ink-soft">{line}</p>
        </div>

        {result.kind === "module_test" && (
          <div className="flex gap-2 text-crown-edge" aria-label={`Звёзд: ${result.stars} из 3`}>
            {[1, 2, 3].map((n) => (
              <motion.span
                key={n}
                initial={reduce ? false : { scale: 0, rotate: -30 }}
                animate={{ scale: 1, rotate: 0 }}
                transition={{ delay: 0.25 + n * 0.15, type: "spring", stiffness: 300, damping: 14 }}
              >
                <Icon name="star" size={48} filled={n <= result.stars} className={n <= result.stars ? "" : "text-line"} />
              </motion.span>
            ))}
          </div>
        )}

        <div className="flex w-full gap-3">
          <Stat icon="bolt" value={`+${result.xp}`} label="опыт" tone="text-[#b7791f]" />
          <Stat icon="target" value={`${Math.round(result.accuracy * 100)}%`} label="точность" tone="text-[#1f6f60]" />
          <Stat icon="clock" value={formatDuration(result.duration_sec)} label="время" tone="text-[#4a2a66]" />
        </div>

        <section className="mat-enamel w-full rounded-3xl px-5 py-4 text-left">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-2 text-[18px] font-extrabold text-ink">
              <Icon name="flame" size={24} filled className="text-[#ff8a3d]" />
              {result.streak_days} {result.streak_days === 1 ? "день" : result.streak_days < 5 ? "дня" : "дней"} подряд
            </span>
            <span className="flex items-center gap-1 text-[16px] font-extrabold text-ink-soft">
              <Icon name="coin" size={20} className="text-[#d69e00]" />+{result.coins}
            </span>
          </div>
          {Object.keys(result.coins_breakdown).length > 1 ? (
            <p className="mt-2 text-[13px] font-bold text-ink-soft">
              {[
                ["lesson", "урок"],
                ["perfect", "без ошибок"],
                ["daily_goal", "цель дня"],
                ["practice", "тренировка"],
                ["module_test", "контрольная"],
              ]
                .filter(([key]) => (result.coins_breakdown[key] ?? 0) > 0)
                .map(([key, label]) => `${label} +${result.coins_breakdown[key]}`)
                .join(" · ")}
            </p>
          ) : null}
          <div className="mt-4">
            <div className="mb-2 flex justify-between text-[15px] font-bold text-ink-soft">
              <span>{result.goal_reached ? "Цель дня выполнена" : "Цель дня"}</span>
              <span className="tabular-nums">
                {Math.min(result.today_xp, result.daily_goal_xp)} / {result.daily_goal_xp}
              </span>
            </div>
            <ProgressBar value={result.today_xp / result.daily_goal_xp} label="Цель дня" />
          </div>
        </section>

        {result.titles_gained.length > 0 ? (
          <div className="mat-brass mx-auto w-full max-w-sm rounded-2xl px-4 py-3 text-center">
            <p className="text-[12px] font-bold uppercase tracking-[0.24em] text-[#5a3d12]">Новое звание</p>
            {result.titles_gained.map((title) => (
              <p key={title.track} className="text-[18px] font-extrabold text-ink">
                {title.title_ru} · +{title.coins}
              </p>
            ))}
          </div>
        ) : null}
      </div></main>
      <footer className="glass-dusk sticky bottom-0 px-4 pb-[max(1.25rem,env(safe-area-inset-bottom))] pt-4 lg:bottom-10 lg:mx-auto lg:w-full lg:max-w-xl lg:rounded-[28px] lg:pb-4">
        <div className="mx-auto flex max-w-xl flex-col gap-3 sm:flex-row-reverse">
          <Button block onClick={failed ? onRetry : onContinue} autoFocus>
            {failed ? "Пройти ещё раз" : "Продолжить"}
          </Button>
          {failed ? (
            <Button block variant="paper" onClick={onContinue}>
              К пути
            </Button>
          ) : result.coins > 0 ? (
            <Link
              href="/world?pulse=shop"
              className="mat-enamel inline-flex min-h-14 w-full items-center justify-center gap-2 rounded-2xl px-7 text-[18px] font-extrabold text-ink"
            >
              В замок · +{result.coins}
            </Link>
          ) : null}
        </div>
      </footer>
    </div>
  );
}
