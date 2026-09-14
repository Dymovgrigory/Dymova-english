"use client";

import { Glass } from "@/ui/Glass";
import { GameButton } from "@/ui/Button";
import { useGame } from "@/game/store";

export function RewardCinematic() {
  const { phase, finish, closeReward } = useGame();
  if (phase !== "reward" || !finish) return null;

  return (
    <div className="absolute inset-0 flex items-end justify-center p-6 sm:items-center">
      <Glass className="w-full max-w-md p-7 text-center">
        <p className="text-[10px] uppercase tracking-widest text-[#f5ed75]">
          {finish.perfect ? "Безошибочно!" : "Челлендж пройден"}
        </p>
        <p className="mt-2 font-[family-name:var(--font-display)] text-2xl font-extrabold">
          {finish.score} из {finish.total}
        </p>

        <div className="mt-6 flex items-center justify-center gap-8">
          <div>
            <p className="font-[family-name:var(--font-display)] text-4xl font-extrabold text-[#f5ed75]">
              +{finish.xp_delta}
            </p>
            <p className="text-[10px] uppercase tracking-widest text-white/50">XP</p>
          </div>
          <div>
            <p className="font-[family-name:var(--font-display)] text-4xl font-extrabold text-[#f5ed75]">
              +{finish.coins_delta}
            </p>
            <p className="text-[10px] uppercase tracking-widest text-white/50">FoxCoins</p>
          </div>
        </div>

        {finish.level_up ? (
          <p className="mt-6 rounded-2xl bg-[#f5ed75]/15 px-4 py-3 font-[family-name:var(--font-display)] text-sm font-bold text-[#f5ed75]">
            Новый уровень {finish.new_level} — {finish.new_title}
          </p>
        ) : null}

        {finish.quest?.all_steps_done ? (
          <p className="mt-3 text-sm text-[#7fd8c9]">
            Открыт Библиотечный двор — загляни туда в следующий раз.
          </p>
        ) : null}

        <div className="mt-7">
          <GameButton onClick={closeReward}>Вернуться в Фоксинбург</GameButton>
        </div>
      </Glass>
    </div>
  );
}
