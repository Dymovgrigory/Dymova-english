"use client";

import { useState } from "react";

import { Icon } from "@/design/Icon";
import { Sound } from "@/design/Sound";
import { listenOnce } from "@/lib/v2/speech";

import type { ViewProps } from "./challengeViews";

type SpeakProps = ViewProps & { onSkip: () => void; onHeard: (transcript: string) => void };

export function SpeakChallenge({ challenge, locked, onSkip, onHeard }: SpeakProps) {
  const [listening, setListening] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  const listen = async () => {
    setProblem(null);
    setListening(true);
    try {
      const transcript = await listenOnce();
      if (!transcript.trim()) {
        setProblem("Не расслышали. Нажми и скажи ещё раз, погромче.");
        return;
      }
      onHeard(transcript);
    } catch (err) {
      const blocked = err instanceof Error && /not-allowed|service-not-allowed/.test(err.message);
      setProblem(blocked ? "Разреши доступ к микрофону в браузере или нажми «Не могу говорить»." : "Микрофон не сработал. Попробуй ещё раз.");
    } finally {
      setListening(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-[23px] font-extrabold leading-8 text-ink sm:text-[26px]">{challenge.instruction_ru}</h1>
      <div className="flex items-center gap-4 rounded-3xl border-2 border-line bg-white px-5 py-4">
        <Sound text={challenge.audio ?? challenge.text ?? ""} />
        <p className="text-[28px] font-extrabold leading-9 text-royal">{challenge.text}</p>
      </div>
      <button
        type="button"
        onClick={listen}
        disabled={locked || listening}
        aria-live="polite"
        className={`press mx-auto flex h-20 w-full max-w-sm items-center justify-center gap-3 rounded-3xl text-[19px] font-extrabold focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-royal/30 ${
          listening ? "bg-coral text-white shadow-[0_5px_0_var(--color-coral-edge)]" : "bg-sky text-royal shadow-[0_5px_0_#9dbfe8]"
        }`}
      >
        <Icon name="mic" size={30} />
        {listening ? "Слушаю…" : "Нажми и говори"}
      </button>
      {problem && <p className="text-center text-[16px] font-bold text-coral-ink">{problem}</p>}
      <button type="button" onClick={onSkip} disabled={locked} className="mx-auto text-[15px] font-extrabold text-ink-soft underline-offset-4 hover:underline">
        Не могу говорить сейчас
      </button>
    </div>
  );
}
