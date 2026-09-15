"use client";

import { SpeakButton } from "@/ui/SpeakButton";
import { EchoMic } from "@/ui/EchoMic";

type Props = {
  en?: string;
  ru?: string;
  speak?: string;
  onEchoPass?: () => void;
  onEchoBlocked?: (reason: string) => void;
};

export function PhraseCard({ en, speak, onEchoPass, onEchoBlocked }: Props) {
  return (
    <article className="mt-2 overflow-hidden rounded-[28px] bg-white px-5 py-8 text-center shadow-[0_10px_0_rgba(58,41,83,0.08)]">
      <p className="text-sm font-bold text-[#3a2953]/45">Фраза урока</p>
      <p className="mt-3 font-[family-name:var(--font-display)] text-4xl font-extrabold leading-tight text-[#3a2953]">
        {en}
      </p>
      <p className="mt-3 text-sm font-semibold text-[#3a2953]/70">Скажи целиком, как Foxy. Не перевод по словам.</p>
      <div className="mt-6 grid justify-items-center gap-2">
        <SpeakButton text={speak || en} label="Слушать фразу" tone="yellow" />
        <EchoMic key={speak || en} target={speak || en} onPass={onEchoPass} onBlocked={onEchoBlocked} />
      </div>
    </article>
  );
}
