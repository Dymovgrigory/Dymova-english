"use client";

import { useState } from "react";

import { speakEnglish } from "@/lib/speak";

import { Icon } from "./Icon";

type SoundProps = { text: string; size?: "sm" | "lg"; label?: string };

/** Кнопка озвучки английского слова или фразы. */
export function Sound({ text, size = "sm", label = "Послушать" }: SoundProps) {
  const [playing, setPlaying] = useState(false);
  const big = size === "lg";
  return (
    <button
      type="button"
      aria-label={label}
      onClick={async () => {
        setPlaying(true);
        try {
          await speakEnglish(text);
        } finally {
          setPlaying(false);
        }
      }}
      className={[
        "press inline-flex shrink-0 items-center justify-center rounded-2xl bg-sky text-royal",
        "shadow-[0_4px_0_#9dbfe8] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-royal/30",
        big ? "size-24" : "size-12",
        playing ? "ring-4 ring-sky/70" : "",
      ].join(" ")}
    >
      <Icon name="speaker" size={big ? 44 : 24} />
    </button>
  );
}
