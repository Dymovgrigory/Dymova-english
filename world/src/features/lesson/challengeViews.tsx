"use client";

import { useEffect, useMemo, useState } from "react";

import { Choice, type ChoiceState } from "@/design/Choice";
import { ContentImage } from "@/design/ContentImage";
import { Icon } from "@/design/Icon";
import { Sound } from "@/design/Sound";
import { Tile } from "@/design/Tile";
import { speakEnglish } from "@/lib/speak";
import type { Answer, AnswerReply, Challenge } from "@/lib/v2/types";

export type ViewProps = {
  challenge: Challenge;
  draft: Answer | null;
  locked: boolean;
  reveal: AnswerReply | null;
  onDraft: (answer: Answer | null) => void;
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
  return <h1 className="text-[23px] font-extrabold leading-8 text-ink sm:text-[26px]">{children}</h1>;
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
      <p className="rounded-full bg-crown px-4 py-1 text-[14px] font-extrabold text-royal-deep">Новое слово</p>
      {challenge.image && (
        <ContentImage path={challenge.image} alt={challenge.en ?? ""} className="size-52 rounded-3xl bg-white p-3 shadow-[0_6px_0_var(--color-line)]" />
      )}
      <div className="flex items-center gap-4">
        <span className="font-heading text-[52px] font-extrabold leading-none text-royal">{challenge.en}</span>
        <Sound text={challenge.en ?? ""} />
      </div>
      <p className="text-[24px] font-bold text-ink-soft">{challenge.ru}</p>
    </div>
  );
}

export function TeachRule({ challenge }: { challenge: Challenge }) {
  return (
    <div className="flex flex-col gap-6">
      <p className="w-fit rounded-full bg-crown px-4 py-1 text-[14px] font-extrabold text-royal-deep">Правило</p>
      <h1 className="font-heading text-[30px] font-extrabold leading-9 text-royal">{challenge.title_ru}</h1>
      <p className="max-w-prose text-[20px] font-semibold leading-8 text-ink">{challenge.rule_ru}</p>
      <ul className="flex flex-col gap-3">
        {challenge.examples?.map((example) => (
          <li key={example.en} className="flex items-center gap-4 rounded-2xl border-2 border-line bg-white px-4 py-3">
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
      <p className="rounded-full bg-crown px-4 py-1 text-[14px] font-extrabold text-royal-deep">Новый звук</p>
      <span className="font-heading text-[128px] font-extrabold leading-none text-royal">{challenge.grapheme}</span>
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
    <div className="grid grid-cols-3 gap-3">
      {options.map((option, index) => (
        <Choice
          key={`${option.image}-${index}`}
          hotkey={index + 1}
          label={`Вариант ${index + 1}`}
          state={choiceState(draft, index, locked, reveal)}
          disabled={locked}
          onPick={() => onDraft({ index })}
          className="aspect-square flex-col justify-center p-2"
        >
          <ContentImage path={option.image} alt={`Картинка ${index + 1}`} className="h-full w-full" fallback="?" />
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
          <ContentImage path={challenge.image} alt="Что на картинке?" className="size-44 rounded-3xl bg-white p-3 shadow-[0_6px_0_var(--color-line)]" fallback="?" />
        </div>
      );
      break;
    case "read_word_pick_image":
    case "read_phrase_pick_image":
      prompt = (
        <p className="py-3 text-center font-heading text-[44px] font-extrabold leading-tight text-royal">{challenge.text}</p>
      );
      break;
    case "blend_sounds":
      prompt = (
        <div className="flex justify-center gap-2 py-3" aria-label={`Звуки: ${challenge.segments?.join(", ")}`}>
          {challenge.segments?.map((segment, i) => (
            <span key={`${segment}-${i}`} className="flex h-20 min-w-16 items-center justify-center rounded-2xl border-2 border-royal/20 bg-white px-3 font-heading text-[44px] font-extrabold text-royal shadow-[0_5px_0_var(--color-line)]">
              {segment}
            </span>
          ))}
        </div>
      );
      break;
    case "translate_pick":
      prompt = (
        <div className="flex items-center gap-4 rounded-3xl border-2 border-line bg-white px-5 py-4">
          {challenge.audio && <Sound text={challenge.audio} />}
          <p className="text-[26px] font-extrabold leading-8 text-ink">{challenge.text}</p>
        </div>
      );
      break;
    case "sound_letter":
      prompt = (
        <p className="py-2 text-center font-heading text-[110px] font-extrabold leading-none text-royal">{challenge.grapheme}</p>
      );
      break;
    case "grammar_pick": {
      const [before, after] = (challenge.sentence ?? "").split("___");
      const pickedIndex = selectedIndex(props.draft);
      const picked = pickedIndex !== null ? (options[pickedIndex] as string) : null;
      prompt = (
        <div className="rounded-3xl border-2 border-line bg-white px-5 py-5">
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
        {challenge.image && <ContentImage path={challenge.image} alt={challenge.ru ?? ""} className="size-28 rounded-2xl bg-white p-2 shadow-[0_5px_0_var(--color-line)]" fallback={challenge.ru ?? "?"} />}
        {challenge.audio && <Sound text={challenge.audio} size={challenge.type === "listen_build" ? "lg" : "sm"} />}
        {challenge.ru && challenge.type !== "spell_tiles" && (
          <p className="rounded-3xl border-2 border-line bg-white px-5 py-3 text-[23px] font-extrabold text-ink">{challenge.ru}</p>
        )}
        {challenge.type === "spell_tiles" && <p className="text-[21px] font-bold text-ink-soft">{challenge.ru}</p>}
      </div>

      <div className="flex min-h-20 flex-wrap content-start items-center gap-2 border-b-2 border-line pb-3" aria-label="Твой ответ">
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

const PAIR_COLORS = ["bg-[#efe9fb] border-royal", "bg-sky/60 border-[#5b8fd6]", "bg-crown/50 border-crown-edge", "bg-mint-wash border-mint-edge", "bg-coral-wash border-coral-edge"];

export function PairsChallenge({ challenge, locked, onDraft }: ViewProps) {
  const left = challenge.left ?? [];
  const right = challenge.right ?? [];
  const [pairs, setPairs] = useState<[string, string][]>([]);
  const [activeLeft, setActiveLeft] = useState<string | null>(null);

  useEffect(() => {
    onDraft(pairs.length === left.length && left.length ? { pairs } : null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pairs]);

  const pairIndex = (id: string) => pairs.findIndex(([l, r]) => l === id || r === id);

  const pressLeft = (id: string) => {
    if (pairIndex(id) >= 0) {
      setPairs((prev) => prev.filter(([l]) => l !== id));
      return;
    }
    setActiveLeft(id === activeLeft ? null : id);
  };

  const pressRight = (id: string) => {
    if (pairIndex(id) >= 0) {
      setPairs((prev) => prev.filter(([, r]) => r !== id));
      return;
    }
    if (activeLeft) {
      setPairs((prev) => [...prev, [activeLeft, id]]);
      setActiveLeft(null);
    }
  };

  const tone = (id: string) => {
    const index = pairIndex(id);
    if (index >= 0) return PAIR_COLORS[index % PAIR_COLORS.length];
    if (id === activeLeft) return "bg-white border-royal ring-4 ring-royal/20";
    return "bg-white border-line";
  };

  return (
    <div className="flex flex-col gap-6">
      <Instruction>{challenge.instruction_ru ?? ""}</Instruction>
      <p className="-mt-3 text-[16px] font-semibold text-ink-soft">Нажми слева, потом справа. Нажми ещё раз, чтобы разъединить.</p>
      <div className="grid grid-cols-2 gap-3">
        <div className="flex flex-col gap-3">
          {left.map((item) => (
            <button
              key={item.id}
              type="button"
              disabled={locked}
              onClick={() => {
                if (item.audio) void speakEnglish(item.audio);
                pressLeft(item.id);
              }}
              className={`press flex min-h-16 items-center justify-center gap-2 rounded-2xl border-2 px-3 text-[19px] font-bold shadow-[0_4px_0_var(--color-line)] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-royal/30 ${tone(item.id)}`}
            >
              {item.audio ? <Icon name="speaker" size={30} className="text-royal" /> : item.label}
            </button>
          ))}
        </div>
        <div className="flex flex-col gap-3">
          {right.map((item) => (
            <button
              key={item.id}
              type="button"
              disabled={locked}
              onClick={() => pressRight(item.id)}
              className={`press flex min-h-16 items-center justify-center rounded-2xl border-2 px-3 text-[19px] font-bold shadow-[0_4px_0_var(--color-line)] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-royal/30 ${tone(item.id)}`}
            >
              {item.image ? <ContentImage path={item.image} alt="Картинка" className="h-14 w-14" fallback="?" /> : item.label}
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
        {challenge.image && <ContentImage path={challenge.image} alt={challenge.ru ?? ""} className="size-28 rounded-2xl bg-white p-2 shadow-[0_5px_0_var(--color-line)]" fallback={challenge.ru ?? "?"} />}
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
        className="h-16 rounded-2xl border-2 border-line bg-white px-5 text-[24px] font-bold text-ink shadow-[inset_0_2px_0_var(--color-grid)] outline-none placeholder:text-ink-soft/50 focus:border-royal"
      />
    </div>
  );
}
