"use client";

import { useEffect, useRef, useState } from "react";

import { Button } from "@/design/Button";
import type { ChoiceState } from "@/design/Choice";
import { Icon } from "@/design/Icon";
import { speakEnglish, stopSpeaking } from "@/lib/speak";
import type { Answer, AnswerReply } from "@/lib/v2/types";

import { Instruction, OptionsList, type ViewProps } from "./challengeViews";

/* Задания чтения (этап 5): книжный разворот и вопросы по тексту. */

/** Сворачиваемая плашка с текстом — доступна, пока ребёнок отвечает на вопрос. */
export function TextToggle({ sentences }: { sentences: string[] }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button
        type="button"
        aria-expanded={open}
        aria-controls="reading-text"
        onClick={() => setOpen((v) => !v)}
        className="press inline-flex min-h-10 items-center gap-2 rounded-full bg-[#e3d0a8]/70 px-4 text-[15px] font-extrabold text-ink shadow-[inset_0_1px_0_#fff,0_2px_0_#a8844a] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[#ffd36e]/70"
      >
        <Icon name="book" size={18} />
        {open ? "Скрыть текст" : "Показать текст"}
      </button>
      {open && (
        <div id="reading-text" role="region" aria-label="Текст для чтения" className="mt-3 rounded-2xl bg-[#fffaf0]/80 px-5 py-4 shadow-[inset_0_2px_6px_rgb(92_60_30/0.18)]">
          {sentences.map((sentence, i) => (
            <p key={i} className="text-[18px] font-semibold leading-8 text-ink">
              {sentence}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

function hasText(challenge: ViewProps["challenge"]): boolean {
  return Boolean(challenge.sentences?.length);
}

/** read_text (неоцениваемый): разворот книги, «Слушать» с подсветкой предложения, «Я прочитал(а)». */
export function ReadText({ challenge, locked, onSubmit }: ViewProps) {
  const sentences = challenge.sentences ?? [];
  const [active, setActive] = useState<number | null>(null);
  const cancelled = useRef(false);
  const listening = active !== null;

  useEffect(
    () => () => {
      cancelled.current = true;
      stopSpeaking();
    },
    [],
  );

  const listen = async () => {
    if (listening) {
      cancelled.current = true;
      stopSpeaking();
      setActive(null);
      return;
    }
    cancelled.current = false;
    for (let i = 0; i < sentences.length; i++) {
      if (cancelled.current) break;
      setActive(i);
      await speakEnglish(sentences[i]);
    }
    if (!cancelled.current) setActive(null);
  };

  return (
    <div className="flex flex-col gap-6">
      <p className="w-fit mat-brass rounded-full px-4 py-1 text-[14px] font-extrabold">Читаем текст</p>
      <div role="region" aria-label="Книжный разворот" className="rounded-3xl bg-[#fffaf0]/70 px-5 py-5 shadow-[inset_0_2px_8px_rgb(92_60_30/0.22),0_0_0_2px_#c9a86a]">
        <div className="mb-4 flex items-center gap-3 border-b-2 border-[#c9a86a]/60 pb-3">
          <Icon name="book" size={30} className="shrink-0 text-[#4a2a66]" />
          <div>
            <h1 className="font-fairy text-[28px] font-black leading-8 text-[#4a2a66]">{challenge.title_en}</h1>
            <p className="text-[15px] font-bold text-ink-soft">{challenge.title_ru}</p>
          </div>
        </div>
        <div aria-live="polite">
          {sentences.map((sentence, i) => (
            <p
              key={i}
              aria-current={active === i ? "true" : undefined}
              className={`rounded-xl px-3 py-1.5 text-[20px] font-semibold leading-9 transition-colors ${
                active === i ? "bg-[#ffe89a]/80 text-[#3a2208] shadow-[0_0_0_2px_#e3a93a]" : "text-ink"
              }`}
            >
              {sentence}
            </p>
          ))}
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-center gap-4">
        <Button variant="royal" onClick={() => void listen()} aria-pressed={listening}>
          <Icon name="speaker" size={22} />
          {listening ? "Стоп" : "Слушать"}
        </Button>
        <Button onClick={() => onSubmit?.({})} disabled={locked}>
          Я прочитал(а)
        </Button>
      </div>
    </div>
  );
}

function boolChoiceState(draft: Answer | null, value: boolean, locked: boolean, reveal: AnswerReply | null): ChoiceState {
  const selected = draft !== null && "answer" in draft && draft.answer === value;
  if (reveal) {
    const solution = reveal.solution === "true";
    if (solution === value) return "correct";
    return selected ? "wrong" : "muted";
  }
  if (selected) return "selected";
  return locked ? "muted" : "idle";
}

/** read_text_truefalse: утверждение по тексту, крупные «Правда»/«Неправда». */
export function ReadTrueFalse({ challenge, draft, locked, reveal, onDraft }: ViewProps) {
  const options: { value: boolean; label: string }[] = [
    { value: true, label: "Правда" },
    { value: false, label: "Неправда" },
  ];
  return (
    <div className="flex flex-col gap-6">
      <Instruction>{challenge.instruction_ru ?? "Правда или неправда?"}</Instruction>
      {hasText(challenge) && <TextToggle sentences={challenge.sentences ?? []} />}
      <div className="mat-enamel rounded-3xl px-5 py-5">
        <p className="text-[24px] font-extrabold leading-9 text-ink">{challenge.sentence_en}</p>
        <p className="mt-2 text-[16px] font-semibold text-ink-soft">{challenge.q_ru}</p>
      </div>
      <div className="grid grid-cols-2 gap-3" role="group" aria-label="Варианты ответа">
        {options.map((option) => (
          <button
            key={option.label}
            type="button"
            disabled={locked}
            aria-pressed={draft !== null && "answer" in draft && draft.answer === option.value}
            onClick={() => onDraft({ answer: option.value })}
            className={[
              "press flex min-h-20 items-center justify-center rounded-2xl px-4 py-3 font-heading text-[24px] font-extrabold transition",
              "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[#ffd36e]/70",
              {
                idle: "mat-enamel hover:-translate-y-0.5",
                selected:
                  "mat-enamel -translate-y-0.5 !shadow-[inset_0_1px_0_#fff,0_0_0_3px_#3fae98,0_5px_0_#1f6f60,0_0_24px_-2px_rgb(63_174_152/0.75)]",
                correct:
                  "text-[#07302a] bg-[linear-gradient(180deg,#e2fbf4,#a6ead9)] shadow-[inset_0_1px_0_#fff,0_0_0_3px_#3fae98,0_5px_0_#1f6f60,0_0_26px_-2px_rgb(63_174_152/0.8)]",
                wrong:
                  "text-[#5a120c] bg-[linear-gradient(180deg,#fff0ec,#f6b9ae)] shadow-[inset_0_1px_0_#fff,0_0_0_3px_#d9483c,0_5px_0_#7c1f17]",
                muted: "mat-enamel opacity-55",
              }[boolChoiceState(draft, option.value, locked, reveal)],
            ].join(" ")}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}

/** read_text_answer: вопрос по тексту, выбор из трёх вариантов. */
export function ReadAnswer(props: ViewProps) {
  const { challenge } = props;
  return (
    <div className="flex flex-col gap-6">
      <Instruction>{challenge.instruction_ru ?? "Ответь на вопрос"}</Instruction>
      {hasText(challenge) && <TextToggle sentences={challenge.sentences ?? []} />}
      <div className="mat-enamel rounded-3xl px-5 py-4">
        <p className="text-[24px] font-extrabold leading-9 text-ink">{challenge.q_en}</p>
        <p className="mt-1 text-[16px] font-semibold text-ink-soft">{challenge.q_ru}</p>
      </div>
      <OptionsList {...props} />
    </div>
  );
}

/** word_in_context: предложение с пропуском, выбрать слово из трёх. */
export function WordInContext(props: ViewProps) {
  const { challenge, draft } = props;
  const [before, after] = (challenge.sentence_en ?? "").split("___");
  const pickedIndex = draft && "index" in draft ? draft.index : null;
  const picked = pickedIndex !== null ? ((challenge.options ?? [])[pickedIndex] as string) : null;
  return (
    <div className="flex flex-col gap-6">
      <Instruction>{challenge.instruction_ru ?? "Какое слово подходит?"}</Instruction>
      {hasText(challenge) && <TextToggle sentences={challenge.sentences ?? []} />}
      <div className="mat-enamel rounded-3xl px-5 py-5">
        <p className="text-[26px] font-extrabold leading-10 text-ink">
          {before}
          <span className={`mx-1 inline-block min-w-24 border-b-4 text-center ${picked ? "border-royal text-royal" : "border-line text-transparent"}`}>
            {picked ?? "___"}
          </span>
          {after}
        </p>
      </div>
      <OptionsList {...props} />
    </div>
  );
}
