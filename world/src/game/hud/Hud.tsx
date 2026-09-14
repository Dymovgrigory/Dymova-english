"use client";

import { Glass } from "@/ui/Glass";
import { useGame } from "@/game/store";

const STEP_LABELS = [
  "Найди школу Фоксинбурга",
  "Поговори с Фокси",
  "Пройди первый английский челлендж",
];

export function Hud() {
  const { player, quest, phase } = useGame();
  if (!player) return null;

  const total = player.xp_into_level + (player.xp_to_next ?? 0);
  const progress = total > 0 ? (player.xp_into_level / total) * 100 : 100;
  const step = quest?.step ?? 0;
  const label = quest?.status === "completed" ? "Квест пройден" : STEP_LABELS[step] ?? "";

  return (
    <div className="pointer-events-none absolute inset-x-0 top-0 flex flex-col gap-3 p-4 sm:flex-row sm:items-start sm:justify-between">
      <Glass className="pointer-events-auto w-full max-w-sm p-4">
        <div className="flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-full bg-[#f5ed75] font-[family-name:var(--font-display)] text-lg font-extrabold text-[#241a30]">
            {player.level}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate font-[family-name:var(--font-display)] text-sm font-bold">
              {player.display_name} · {player.level_title}
            </p>
            <div className="mt-1 h-2 overflow-hidden rounded-full bg-white/10">
              <div
                className="h-full rounded-full bg-[#f5ed75] transition-[width] duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="mt-1 text-xs text-white/60">
              {player.xp} XP{player.xp_to_next ? ` · до уровня ${player.xp_to_next}` : ""}
            </p>
          </div>
          <div className="text-right">
            <p className="font-[family-name:var(--font-display)] text-lg font-extrabold text-[#f5ed75]">
              {player.coins}
            </p>
            <p className="text-[10px] uppercase tracking-wide text-white/50">FoxCoins</p>
          </div>
        </div>
      </Glass>

      {phase === "explore" && label ? (
        <Glass className="pointer-events-auto max-w-xs p-4">
          <p className="text-[10px] uppercase tracking-widest text-[#f5ed75]">Квест</p>
          <p className="mt-1 text-sm">{label}</p>
        </Glass>
      ) : null}
    </div>
  );
}
