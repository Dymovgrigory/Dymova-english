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
            className={`border-t-2 px-4 pb-[max(1.25rem,env(safe-area-inset-bottom))] pt-4 ${
              good ? "border-mint-edge/40 bg-mint-wash" : "border-coral-edge/40 bg-coral-wash"
            }`}
          >
            <div className="mx-auto flex max-w-2xl flex-col gap-4 sm:flex-row sm:items-center">
              <div className="flex flex-1 items-start gap-3">
                <span
                  className={`flex size-11 shrink-0 items-center justify-center rounded-full bg-white ${
                    good ? "text-mint-ink" : "text-coral-ink"
                  }`}
                >
                  <Icon name={good ? "check" : "close"} size={26} />
                </span>
                <div className={good ? "text-mint-ink" : "text-coral-ink"}>
                  <p className="text-[21px] font-extrabold leading-7">{title}</p>
                  {reply.solution && (!good || reply.typo) && (
                    <p className="mt-0.5 text-[18px] font-bold leading-6">{reply.solution}</p>
                  )}
                </div>
              </div>
              <Button variant={good ? "mint" : "coral"} onClick={onContinue} className="sm:min-w-44" block autoFocus>
                Дальше
              </Button>
            </div>
          </motion.section>
        ) : (
          <motion.div key="footer" className="border-t-2 border-line bg-paper/95 px-4 pb-[max(1.25rem,env(safe-area-inset-bottom))] pt-4 backdrop-blur">
            <div className="mx-auto max-w-2xl">{footer}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
