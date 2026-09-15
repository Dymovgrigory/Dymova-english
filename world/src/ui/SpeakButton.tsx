"use client";

import { speakEnglish } from "@/lib/speak";
import { useState } from "react";

type Props = {
  text?: string;
  label?: string;
  tone?: "yellow" | "blue" | "orange";
};

export function SpeakButton({ text, label = "Слушать", tone = "yellow" }: Props) {
  const [busy, setBusy] = useState(false);
  if (!text) return null;
  const colors =
    tone === "blue"
      ? "bg-[#3a2953] text-[#f5ed75]"
      : tone === "orange"
        ? "bg-[#ee7349] text-white"
        : "bg-[#f5ed75] text-[#241a30]";
  return (
    <button
      type="button"
      disabled={busy}
      onClick={() => {
        setBusy(true);
        void speakEnglish(text).finally(() => setBusy(false));
      }}
      className={`inline-flex items-center gap-2 rounded-full px-5 py-3 text-sm font-extrabold shadow-[0_4px_0_rgba(36,26,48,0.12)] transition-transform active:translate-y-0.5 active:shadow-none disabled:opacity-60 ${colors}`}
    >
      {busy ? (
        <span className="flex h-4 items-end gap-0.5" aria-hidden>
          <i className="fx-bar h-2 w-1 rounded-full bg-current" />
          <i className="fx-bar fx-bar-2 h-4 w-1 rounded-full bg-current" />
          <i className="fx-bar fx-bar-3 h-3 w-1 rounded-full bg-current" />
          <i className="fx-bar h-4 w-1 rounded-full bg-current" />
        </span>
      ) : (
        <span aria-hidden>▶</span>
      )}
      {busy ? "Говорит Foxy" : label}
    </button>
  );
}
