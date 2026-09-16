"use client";

import { speakEnglish } from "@/lib/speak";
import { ChromeIcon } from "@/ui/fantasy/Chrome";
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
      ? "border-[#f5ed75]/45 bg-[linear-gradient(180deg,rgba(58,41,83,0.98),rgba(36,26,48,1))] text-[#f5ed75] shadow-[0_4px_0_#1a1230]"
      : tone === "orange"
        ? "border-[#ee7349]/55 bg-[linear-gradient(180deg,#ee7349,#c45a38)] text-white shadow-[0_4px_0_#7a2e1c]"
        : "border-[#fff6a8]/70 bg-[linear-gradient(180deg,#fff6a8,#f5ed75_35%,#e8b93e)] text-[#241a30] shadow-[0_4px_0_#9a7a18]";
  return (
    <button
      type="button"
      disabled={busy}
      onClick={() => {
        setBusy(true);
        void speakEnglish(text).finally(() => setBusy(false));
      }}
      className={`inline-flex min-h-[44px] items-center gap-2 border px-5 py-3 text-sm font-extrabold transition-transform active:translate-y-0.5 active:shadow-none disabled:opacity-60 ${colors}`}
      style={{ clipPath: "polygon(8% 0, 92% 0, 100% 50%, 92% 100%, 8% 100%, 0 50%)" }}
    >
      {busy ? (
        <span className="flex h-4 items-end gap-0.5" aria-hidden>
          <i className="fx-bar h-2 w-1 rounded-full bg-current" />
          <i className="fx-bar fx-bar-2 h-4 w-1 rounded-full bg-current" />
          <i className="fx-bar fx-bar-3 h-3 w-1 rounded-full bg-current" />
          <i className="fx-bar h-4 w-1 rounded-full bg-current" />
        </span>
      ) : (
        <ChromeIcon name="audio" className="h-5 w-5" />
      )}
      {busy ? "Говорит Foxy" : label}
    </button>
  );
}
