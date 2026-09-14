"use client";

import { Glass } from "@/ui/Glass";
import { GameButton } from "@/ui/Button";
import { useGame } from "@/game/store";

/** Русские названия зон для честного сообщения о разблокировке — только по факту unlocks_granted. */
const ZONE_LABELS_RU: Record<string, string> = {
  "library-courtyard": "Библиотечный двор",
};

export function RewardCinematic() {
  const { phase, finish, questComplete, closeReward } = useGame();
  if (phase !== "reward" || !finish) return null;

  const unlocks = questComplete?.unlocks_granted ?? [];

  return (
    <div className="absolute inset-0 flex items-end justify-center p-6 sm:items-center">
      <Glass className="w-full max-w-md p-7 text-center">
        <p className="text-[10px] uppercase tracking-widest text-[#f5ed75]">
          {finish.practice ? "Тренировка" : finish.perfect ? "Безошибочно!" : "Челлендж пройден"}
        </p>
        <p className="mt-2 font-[family-name:var(--font-display)] text-2xl font-extrabold">
          {finish.score} из {finish.total}
        </p>

        {finish.practice ? (
          <p className="mt-4 text-sm text-white/70">
            Это повтор — квест уже пройден, награда за него не начисляется снова.
          </p>
        ) : (
          <>
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

            {questComplete ? (
              <div className="mt-4 rounded-2xl bg-[#7fd8c9]/10 p-4">
                <p className="text-[10px] uppercase tracking-widest text-[#7fd8c9]">Награда за квест</p>
                <p className="mt-1 font-[family-name:var(--font-display)] text-lg font-extrabold text-[#7fd8c9]">
                  +{questComplete.xp_delta} XP · +{questComplete.coins_delta} FoxCoins
                </p>
                {questComplete.level_up ? (
                  <p className="mt-2 text-sm text-[#7fd8c9]">
                    Новый уровень {questComplete.new_level} — {questComplete.new_title}
                  </p>
                ) : null}
              </div>
            ) : null}

            {unlocks.length > 0 ? (
              <p className="mt-3 text-sm text-[#7fd8c9]">
                Открыт{unlocks.length > 1 ? "ы" : ""}: {unlocks.map((id) => ZONE_LABELS_RU[id] ?? id).join(", ")} —
                загляни туда в следующий раз.
              </p>
            ) : null}
          </>
        )}

        <div className="mt-7">
          <GameButton onClick={() => void closeReward()}>Вернуться в Фоксинбург</GameButton>
        </div>
      </Glass>
    </div>
  );
}
