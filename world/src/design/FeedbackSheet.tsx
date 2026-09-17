"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";

import type { AnswerReply } from "@/lib/v2/types";

import { Button } from "./Button";
import { Icon } from "./Icon";

type FeedbackSheetProps = {
  reply: AnswerReply | null;
  onContinue: () => void;
  footer: ReactNode;
};

const PRAISE = ["Верно!", "Отлично!", "Так держать!", "Супер!"];

/** Нижняя панель урока: «Проверить» или лист результата с правильным ответом. */
export function FeedbackSheet({ reply, onContinue, footer }: FeedbackSheetProps) {
  const reduce = useReducedMotion();
  const good = reply?.correct ?? false;
  const title = !reply
    ? ""
    : reply.skipped
      ? "Потренируем в другой раз"
      : good
        ? reply.typo
          ? "Верно, но проверь написание"
          : PRAISE[(reply.remaining + 1) % PRAISE.length]
        : "Правильный ответ:";

  return (
    <div className="sticky bottom-0 z-20">
      <AnimatePresence initial={false} mode="wait">
        {reply ? (
          <motion.section
            key="result"
            role="status"
            aria-live="assertive"
            initial={reduce ? false : { y: 40, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={reduce ? undefined : { y: 40, opacity: 0 }}
            transition={{ type: "spring", stiffness: 420, damping: 34 }}
            className={`mat-wood rounded-t-[28px] px-4 pb-[max(1.25rem,env(safe-area-inset-bottom))] pt-5 ${
              good ? "shadow-[inset_0_3px_0_#3fae98,0_-10px_40px_-6px_rgb(63_174_152/0.45)]" : "shadow-[inset_0_3px_0_#d9483c,0_-10px_40px_-6px_rgb(217_72_60/0.4)]"
            }`}
          >
            <div className="mx-auto flex max-w-2xl flex-col gap-4 sm:flex-row sm:items-center">
              <div className="flex flex-1 items-start gap-3">
                <span
                  className={`flex size-12 shrink-0 items-center justify-center rounded-full shadow-[inset_0_1px_0_rgb(255_255_255/0.7),0_4px_0_rgb(0_0_0/0.35)] ${
                    good ? "bg-[radial-gradient(circle_at_35%_30%,#c9fbee,#3fae98)] text-[#07302a]" : "bg-[radial-gradient(circle_at_35%_30%,#ffc1b6,#c73c30)] text-[#fff3ef]"
                  }`}
                >
                  <Icon name={good ? "check" : "close"} size={26} />
                </span>
                <div className={good ? "text-[#9ff0dd]" : "text-[#ffb3a6]"}>
                  <p className="font-fairy text-[23px] font-black leading-7">{title}</p>
                  {reply.solution && (!good || reply.typo) && (
                    <p className="mt-0.5 text-[19px] font-extrabold leading-6 text-[#fff6e3]">{reply.solution}</p>
                  )}
                </div>
              </div>
              <Button variant={good ? "mint" : "coral"} onClick={onContinue} className="sm:min-w-44" block autoFocus>
                Дальше
              </Button>
            </div>
          </motion.section>
        ) : (
          <motion.div key="footer" className="glass-dusk px-4 pb-[max(1.25rem,env(safe-area-inset-bottom))] pt-4">
            <div className="mx-auto max-w-2xl">{footer}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
