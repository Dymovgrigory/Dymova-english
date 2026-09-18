"use client";

import { useEffect, useMemo, useState } from "react";

import { Choice, type ChoiceState } from "@/design/Choice";
import { ContentImage } from "@/design/ContentImage";
import { Icon } from "@/design/Icon";
import { Sound } from "@/design/Sound";
import { Tile } from "@/design/Tile";
import { playCorrect, playWrong } from "@/lib/sfx";
import { speakEnglish } from "@/lib/speak";
import type { Answer, AnswerReply, Challenge } from "@/lib/v2/types";

export type ViewProps = {
  challenge: Challenge;
  draft: Answer | null;
  locked: boolean;
  reveal: AnswerReply | null;
  onDraft: (answer: Answer | null) => void;
  onCheckPair?: (left: string, right: string) => Promise<boolean>;
  onSubmit?: (answer: Answer) => void;
};

const AUTOPLAY = new Set<Challenge["type"]>([
  "teach_word",
  "teach_grapheme",
  "listen_pick_image",
  "letter_sound",
  "listen_build",
  "spell_tiles",
]);

export function useAutoplay(challenge: Challenge) {
  useEffect(() => {
    const text = challenge.audio ?? (challenge.type === "teach_word" ? challenge.en : undefined);
    if (text && AUTOPLAY.has(challenge.type)) void speakEnglish(text);
  }, [challenge]);
}

function Instruction({ children }: { children: string }) {
  return <h1 className="font-fairy text-[25px] font-black leading-8 text-ink sm:text-[28px]">{children}</h1>;
}

function selectedIndex(draft: Answer | null): number | null {
  return draft && "index" in draft ? draft.index : null;
}

function choiceState(draft: Answer | null, index: number, locked: boolean, reveal: AnswerReply | null): ChoiceState {
  const selected = selectedIndex(draft) === index;
  if (reveal) {
    if (reveal.solution_index === index || (selected && reveal.correct)) return "correct";
    return selected ? "wrong" : "muted";
  }
  if (selected) return "selected";
  return locked ? "muted" : "idle";
}

/* ----------------------------- знакомство ----------------------------- */

export function TeachWord({ challenge }: { challenge: Challenge }) {
  return (
    <div className="flex flex-col items-center gap-6 text-center">
      <p className="mat-brass rounded-full px-4 py-1 text-[14px] font-extrabold">Новое слово</p>
      {challenge.image && (
        <ContentImage path={challenge.image} alt={challenge.en ?? ""} className="size-56 overflow-hidden rounded-3xl sm:size-72 lg:size-80 shadow-[0_0_0_4px_#c9a86a,0_8px_0_#a8844a,0_18px_28px_-10px_rgb(40_20_5/0.6)]" />
      )}
      <div className="flex items-center gap-4">
        <span className="font-fairy text-[56px] font-black leading-none text-[#4a2a66]">{challenge.en}</span>
        <Sound text={challenge.en ?? ""} />
      </div>
      <p className="text-[24px] font-bold text-ink-soft">{challenge.ru}</p>
    </div>
  );
}

export function TeachRule({ challenge }: { challenge: Challenge }) {
  return (
    <div className="flex flex-col gap-6">
      <p className="w-fit mat-brass rounded-full px-4 py-1 text-[14px] font-extrabold">Правило</p>
      <h1 className="font-fairy text-[32px] font-black leading-9 text-[#4a2a66]">{challenge.title_ru}</h1>
      <p className="max-w-prose text-[20px] font-semibold leading-8 text-ink">{challenge.rule_ru}</p>
      <ul className="flex flex-col gap-3">
        {challenge.examples?.map((example) => (
          <li key={example.en} className="flex items-center gap-4 mat-enamel rounded-2xl px-4 py-3">
            <Sound text={example.en} />
            <span>
              <span className="block text-[20px] font-extrabold text-ink">{example.en}</span>
              <span className="block text-[16px] font-semibold text-ink-soft">{example.ru}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function TeachGrapheme({ challenge }: { challenge: Challenge }) {
  return (
    <div className="flex flex-col items-center gap-6 text-center">
      <p className="mat-brass rounded-full px-4 py-1 text-[14px] font-extrabold">Новый звук</p>
      <span className="font-fairy text-[132px] font-black leading-none text-[#4a2a66]">{challenge.grapheme}</span>
      <div className="flex items-center gap-3 text-[24px] font-bold text-ink-soft">
        как в слове <span className="font-extrabold text-ink">{challenge.sound_word}</span>
        <Sound text={challenge.sound_word ?? ""} />
      </div>
    </div>
  );
}

/* ----------------------------- выбор варианта ----------------------------- */

function OptionsList({ challenge, draft, locked, reveal, onDraft, big = false }: ViewProps & { big?: boolean }) {
  const options = (challenge.options ?? []) as string[];
  return (
    <div className="grid gap-3">
      {options.map((label, index) => (
        <Choice
          key={`${label}-${index}`}
          hotkey={index + 1}
          state={choiceState(draft, index, locked, reveal)}
          disabled={locked}
          onPick={() => onDraft({ index })}
          className={big ? "justify-center text-[34px]" : ""}
        >
          <span className={big ? "font-heading font-extrabold" : ""}>{label}</span>
        </Choice>
      ))}
    </div>
  );
}

function ImageOptions({ challenge, draft, locked, reveal, onDraft }: ViewProps) {
  const options = (challenge.options ?? []) as { image?: string }[];
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4">
      {options.map((option, index) => (
        <Choice
          key={`${option.image}-${index}`}
          hotkey={index + 1}
          label={`Вариант ${index + 1}`}
          state={choiceState(draft, index, locked, reveal)}
          disabled={locked}
          onPick={() => onDraft({ index })}
          className="aspect-square flex-col justify-center !p-1.5"
        >
          <ContentImage path={option.image} alt={`Картинка ${index + 1}`} className="h-full w-full rounded-xl" fallback="?" />
        </Choice>
      ))}
    </div>
  );
}

function AudioOptions({ challenge, draft, locked, reveal, onDraft }: ViewProps) {
  const options = (challenge.options ?? []) as { audio?: string }[];
  return (
    <div className="grid grid-cols-3 gap-3">
      {options.map((option, index) => (
        <Choice
          key={`${option.audio}-${index}`}
          hotkey={index + 1}
          label={`Слово ${index + 1}`}
          state={choiceState(draft, index, locked, reveal)}
          disabled={locked}
          onPick={() => {
            void speakEnglish(option.audio ?? "");
            onDraft({ index });
          }}
          className="aspect-square flex-col justify-center"
        >
          <Icon name="speaker" size={40} className="text-royal" />
        </Choice>
      ))}
    </div>
  );
}

export function ChoiceChallenge(props: ViewProps) {
  const { challenge } = props;
  useAutoplay(challenge);
  const options = challenge.options ?? [];
  const pictureOptions = typeof options[0] === "object" && options[0] !== null && "image" in options[0];

  let prompt: React.ReactNode = null;
  switch (challenge.type) {
    case "listen_pick_image":
    case "letter_sound":
      prompt = (
        <div className="flex justify-center py-2">
          <Sound text={challenge.audio ?? ""} size="lg" />
        </div>
      );
      break;
    case "image_pick_word":
      prompt = (
        <div className="flex justify-center">
          <ContentImage path={challenge.image} alt="Что на картинке?" className="size-52 overflow-hidden rounded-3xl sm:size-64 lg:size-72 shadow-[0_0_0_4px_#c9a86a,0_8px_0_#a8844a,0_18px_28px_-10px_rgb(40_20_5/0.6)]" fallback="?" />
        </div>
      );
      break;
    case "read_word_pick_image":
    case "read_phrase_pick_image":
      prompt = (
        <p className="py-3 text-center font-fairy text-[46px] font-black leading-tight text-[#4a2a66]">{challenge.text}</p>
      );
      break;
    case "blend_sounds":
      prompt = (
        <div className="flex justify-center gap-2 py-3" aria-label={`Звуки: ${challenge.segments?.join(", ")}`}>
          {challenge.segments?.map((segment, i) => (
            <span key={`${segment}-${i}`} className="flex h-20 min-w-16 items-center justify-center mat-enamel rounded-2xl px-3 font-fairy text-[44px] font-extrabold text-royal shadow-[0_5px_0_var(--color-line)]">
              {segment}
            </span>
          ))}
        </div>
      );
      break;
    case "translate_pick":
      prompt = (
        <div className="flex items-center gap-4 mat-enamel rounded-3xl px-5 py-4">
          {challenge.audio && <Sound text={challenge.audio} />}
          <p className="text-[26px] font-extrabold leading-8 text-ink">{challenge.text}</p>
        </div>
      );
      break;
    case "sound_letter":
      prompt = (
        <p className="py-2 text-center font-fairy text-[112px] font-black leading-none text-[#4a2a66]">{challenge.grapheme}</p>
      );
      break;
    case "grammar_pick": {
      const [before, after] = (challenge.sentence ?? "").split("___");
      const pickedIndex = selectedIndex(props.draft);
      const picked = pickedIndex !== null ? (options[pickedIndex] as string) : null;
      prompt = (
        <div className="mat-enamel rounded-3xl px-5 py-5">
          <p className="text-[27px] font-extrabold leading-10 text-ink">
            {before}
            <span className={`mx-1 inline-block min-w-24 border-b-4 text-center ${picked ? "border-royal text-royal" : "border-line text-transparent"}`}>
              {picked ?? "___"}
            </span>
            {after}
          </p>
          <p className="mt-2 text-[17px] font-semibold text-ink-soft">{challenge.ru}</p>
        </div>
      );
      break;
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <Instruction>{challenge.instruction_ru ?? ""}</Instruction>
      {prompt}
      {challenge.type === "sound_letter" ? (
        <AudioOptions {...props} />
      ) : pictureOptions ? (
        <ImageOptions {...props} />
      ) : (
        <OptionsList {...props} big={challenge.type === "letter_sound"} />
      )}
    </div>
  );
}

/* ----------------------------- плитки («Пазл», буквы) ----------------------------- */

export function TilesChallenge({ challenge, locked, onDraft }: ViewProps) {
  useAutoplay(challenge);
  const tiles = useMemo(() => challenge.tiles ?? [], [challenge]);
  const [picked, setPicked] = useState<number[]>([]);
  const letters = challenge.type === "spell_tiles";

  useEffect(() => {
    onDraft(picked.length ? { tiles: picked.map((i) => tiles[i]) } : null);
    // onDraft стабилен в рамках задания; зависим только от выбора
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [picked]);

  return (
    <div className="flex flex-col gap-6">
      <Instruction>{challenge.instruction_ru ?? ""}</Instruction>
      <div className="flex items-center gap-4">
        {challenge.image && <ContentImage path={challenge.image} alt={challenge.ru ?? ""} className="size-36 overflow-hidden rounded-2xl sm:size-44 shadow-[0_0_0_4px_#c9a86a,0_8px_0_#a8844a,0_18px_28px_-10px_rgb(40_20_5/0.6)]" fallback={challenge.ru ?? "?"} />}
        {challenge.audio && <Sound text={challenge.audio} size={challenge.type === "listen_build" ? "lg" : "sm"} />}
        {challenge.ru && challenge.type !== "spell_tiles" && (
          <p className="mat-enamel rounded-3xl px-5 py-3 text-[23px] font-extrabold text-ink">{challenge.ru}</p>
        )}
        {challenge.type === "spell_tiles" && <p className="text-[21px] font-bold text-ink-soft">{challenge.ru}</p>}
      </div>

      <div className="flex min-h-20 flex-wrap content-start items-center gap-2 rounded-2xl bg-[#e3d0a8]/60 p-3 shadow-[inset_0_2px_6px_rgb(92_60_30/0.25)]" aria-label="Твой ответ">
        {picked.map((tileIndex, position) => (
          <Tile
            key={`${tileIndex}-${position}`}
            size={letters ? "letter" : "word"}
            label={tiles[tileIndex]}
            disabled={locked}
            onPress={() => setPicked((prev) => prev.filter((_, i) => i !== position))}
          />
        ))}
      </div>

      <div className="flex flex-wrap justify-center gap-2">
        {tiles.map((label, index) => (
          <Tile
            key={`${label}-${index}`}
            size={letters ? "letter" : "word"}
            label={label}
            used={picked.includes(index)}
            disabled={locked}
            onPress={() => setPicked((prev) => [...prev, index])}
          />
        ))}
      </div>
    </div>
  );
}

/* ----------------------------- пары ----------------------------- */

type PairSide = "left" | "right";

const PAIR_BASE =
  "press relative flex w-full items-center justify-center overflow-hidden rounded-2xl font-bold text-ink transition focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[#ffd36e]/70";

/** «Найди пары»: выбор сразу подсвечивается, верная пара мгновенно фиксируется, неверная вспыхивает красным. */
export function PairsChallenge({ challenge, locked, onCheckPair, onSubmit }: ViewProps) {
  const left = challenge.left ?? [];
  const right = challenge.right ?? [];
  const pictures = challenge.mode === "audio_image";
  const [matched, setMatched] = useState<[string, string][]>([]);
  const [selected, setSelected] = useState<{ side: PairSide; id: string } | null>(null);
  const [wrong, setWrong] = useState<string[]>([]);
  const [checking, setChecking] = useState(false);

  const isMatched = (id: string) => matched.some(([l, r]) => l === id || r === id);

  const tryPair = async (leftId: string, rightId: string) => {
    setChecking(true);
    const correct = onCheckPair ? await onCheckPair(leftId, rightId) : false;
    setChecking(false);
    setSelected(null);
    if (correct) {
      playCorrect();
      const next: [string, string][] = [...matched, [leftId, rightId]];
      setMatched(next);
      if (next.length === left.length) onSubmit?.({ pairs: next });
    } else {
      playWrong();
      setWrong([leftId, rightId]);
      window.setTimeout(() => setWrong([]), 650);
    }
  };

  const press = (side: PairSide, id: string, audio?: string) => {
    if (locked || checking || isMatched(id)) return;
    if (audio) void speakEnglish(audio);
    if (!selected || selected.side === side) {
      setSelected(selected?.id === id ? null : { side, id });
      return;
    }
    const leftId = side === "left" ? id : selected.id;
    const rightId = side === "right" ? id : selected.id;
    void tryPair(leftId, rightId);
  };

  const look = (id: string) => {
    if (isMatched(id))
      return "text-[#07302a] bg-[linear-gradient(180deg,#e2fbf4,#a6ead9)] shadow-[inset_0_1px_0_#fff,0_0_0_3px_#3fae98,0_3px_0_#1f6f60] opacity-80";
    if (wrong.includes(id))
      return "animate-[pair-shake_0.45s_ease] text-[#5a120c] bg-[linear-gradient(180deg,#fff0ec,#f6b9ae)] shadow-[inset_0_1px_0_#fff,0_0_0_3px_#d9483c,0_5px_0_#7c1f17]";
    if (selected?.id === id)
      return "mat-enamel -translate-y-1 !shadow-[inset_0_1px_0_#fff,0_0_0_4px_#3fae98,0_6px_0_#1f6f60,0_0_28px_-2px_rgb(63_174_152/0.85)]";
    return "mat-enamel hover:-translate-y-0.5";
  };

  const tick = (id: string) =>
    isMatched(id) ? (
      <span className="absolute right-1 top-1 flex size-6 items-center justify-center rounded-full bg-[#3fae98] text-white shadow">
        <Icon name="check" size={14} />
      </span>
    ) : null;

  return (
    <div className="flex flex-col gap-5">
      <Instruction>{challenge.instruction_ru ?? ""}</Instruction>
      <p className="-mt-3 text-[16px] font-semibold text-ink-soft">
        {pictures ? "Нажми на звук, потом на подходящую картинку." : "Нажми на слово, потом на его перевод."}
      </p>
      <div className={pictures ? "flex flex-col gap-4" : "grid grid-cols-2 gap-3"}>
        <div className={pictures ? "grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-5" : "flex flex-col gap-3"}>
          {left.map((item) => (
            <button
              key={item.id}
              type="button"
              disabled={locked || isMatched(item.id)}
              aria-pressed={selected?.id === item.id}
              aria-label={item.audio ? "Послушать слово" : item.label}
              onClick={() => press("left", item.id, item.audio)}
              className={`${PAIR_BASE} ${pictures ? "aspect-square" : "min-h-16 px-3 text-[19px]"} ${look(item.id)}`}
            >
              {item.audio ? <Icon name="speaker" size={30} className="text-[#4a2a66]" /> : item.label}
              {tick(item.id)}
            </button>
          ))}
        </div>
        <div className={pictures ? "grid grid-cols-3 gap-3" : "flex flex-col gap-3"}>
          {right.map((item) => (
            <button
              key={item.id}
              type="button"
              disabled={locked || isMatched(item.id)}
              aria-pressed={selected?.id === item.id}
              aria-label={item.image ? "Картинка" : item.label}
              onClick={() => press("right", item.id)}
              className={`${PAIR_BASE} ${pictures ? "aspect-square p-1.5" : "min-h-16 px-3 text-[19px]"} ${look(item.id)}`}
            >
              {item.image ? <ContentImage path={item.image} alt="Картинка" className="h-full w-full rounded-xl" fallback="?" /> : item.label}
              {tick(item.id)}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ----------------------------- ввод слова ----------------------------- */

export function TypeChallenge({ challenge, draft, locked, onDraft }: ViewProps) {
  const value = draft && "text" in draft ? draft.text : "";
  return (
    <div className="flex flex-col gap-6">
      <Instruction>{challenge.instruction_ru ?? ""}</Instruction>
      <div className="flex items-center gap-4">
        {challenge.image && <ContentImage path={challenge.image} alt={challenge.ru ?? ""} className="size-36 overflow-hidden rounded-2xl sm:size-44 shadow-[0_0_0_4px_#c9a86a,0_8px_0_#a8844a,0_18px_28px_-10px_rgb(40_20_5/0.6)]" fallback={challenge.ru ?? "?"} />}
        {challenge.audio && <Sound text={challenge.audio} />}
        <p className="text-[24px] font-extrabold text-ink">{challenge.ru}</p>
      </div>
      <input
        autoFocus
        value={value}
        disabled={locked}
        onChange={(event) => onDraft(event.target.value.trim() ? { text: event.target.value } : null)}
        autoCapitalize="off"
        autoCorrect="off"
        spellCheck={false}
        lang="en"
        aria-label="Ответ по-английски"
        placeholder="Пиши по-английски"
        className="h-16 rounded-2xl bg-[#fffaf0] px-5 text-[24px] font-bold text-ink shadow-[inset_0_3px_6px_rgb(92_60_30/0.25),0_0_0_2px_#c9a86a] outline-none placeholder:text-ink-soft/50 focus:shadow-[inset_0_3px_6px_rgb(92_60_30/0.25),0_0_0_3px_#3fae98]"
      />
    </div>
  );
}
