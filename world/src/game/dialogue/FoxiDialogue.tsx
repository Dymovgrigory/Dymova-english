"use client";

import { useState } from "react";
import { Glass } from "@/ui/Glass";
import { GameButton } from "@/ui/Button";
import { useGame } from "@/game/store";

const LINES = [
  "Привет! Я Фокси. Добро пожаловать в Фоксинбург!",
  "Здесь всё держится на английских словах — они открывают двери.",
  "Проверим, сколько ты уже знаешь? Пять слов, это быстро.",
];

export function FoxiDialogue() {
  const { phase, finishDialogue } = useGame();
  const [line, setLine] = useState(0);
  if (phase !== "dialogue") return null;

  const last = line === LINES.length - 1;

  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-0 flex justify-center p-4">
      <Glass className="pointer-events-auto w-full max-w-md p-5">
        <p className="text-[10px] uppercase tracking-widest text-[#f5ed75]">Фокси</p>
        <p className="mt-2 min-h-[3.5rem] text-base leading-relaxed">{LINES[line]}</p>
        <div className="mt-4 flex justify-end">
          <GameButton onClick={() => (last ? finishDialogue() : setLine(line + 1))}>
            {last ? "Погнали" : "Дальше"}
          </GameButton>
        </div>
      </Glass>
    </div>
  );
}
