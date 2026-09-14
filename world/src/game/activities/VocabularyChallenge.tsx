"use client";

import { useState } from "react";
import { Glass } from "@/ui/Glass";
import { GameButton } from "@/ui/Button";
import { useGame } from "@/game/store";

export function VocabularyChallenge() {
  const { phase, session, answers, answerQuestion, finishChallenge } = useGame();
  const [index, setIndex] = useState(0);
  const [chosen, setChosen] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  if (phase !== "challenge" || !session) return null;

  const question = session.questions[index];
  const answer = answers[index];
  const last = index === session.questions.length - 1;

  const choose = async (choice: number) => {
    if (answer || busy) return;
    setBusy(true);
    setChosen(choice);
    try {
      await answerQuestion(index, choice);
    } finally {
      setBusy(false);
    }
  };

  const next = async () => {
    if (!last) {
      setIndex(index + 1);
      setChosen(null);
      return;
    }
    setBusy(true);
    try {
      await finishChallenge();
    } finally {
      setBusy(false);
    }
  };

  const optionSkin = (option: number): string => {
    if (!answer) return "border-white/15 hover:border-[#f5ed75] hover:bg-white/5";
    if (option === answer.correct_index) return "border-[#7fd8c9] bg-[#7fd8c9]/15";
    if (option === chosen && !answer.correct) return "border-[#c96f4a] bg-[#c96f4a]/10";
    return "border-white/10 opacity-50";
  };

  return (
    <div className="absolute inset-0 flex items-center justify-center bg-[#241a30]/45 p-4 backdrop-blur-[2px]">
      <Glass className="w-full max-w-lg p-6">
        <div className="flex items-center justify-between text-[10px] uppercase tracking-widest text-[#f5ed75]">
          <span>{session.title_ru}</span>
          <span>
            {index + 1} / {session.total}
          </span>
        </div>

        <p className="mt-5 font-[family-name:var(--font-display)] text-4xl font-extrabold">
          {question.en}
        </p>
        <p className="mt-1 text-sm text-white/50">{question.ipa}</p>

        <div className="mt-5 grid gap-2">
          {question.options.map((option, i) => (
            <button
              key={option}
              onClick={() => choose(i)}
              disabled={Boolean(answer) || busy}
              className={`rounded-2xl border px-4 py-3 text-left text-base transition-colors ${optionSkin(i)}`}
            >
              {option}
            </button>
          ))}
        </div>

        {answer ? (
          <div className="mt-4 rounded-2xl bg-white/5 p-4">
            <p className="font-[family-name:var(--font-display)] text-sm font-bold text-[#f5ed75]">
              {answer.correct ? "Верно!" : "Правильный ответ подсвечен"}
            </p>
            <p className="mt-2 text-sm text-white/80">{answer.example_en}</p>
            <p className="text-sm text-white/50">{answer.example_ru}</p>
          </div>
        ) : null}

        <div className="mt-5 flex justify-end">
          <GameButton onClick={next} disabled={!answer || busy}>
            {last ? "Забрать награду" : "Дальше"}
          </GameButton>
        </div>
      </Glass>
    </div>
  );
}
