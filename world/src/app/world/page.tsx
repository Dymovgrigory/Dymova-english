"use client";

import { useEffect } from "react";
import { Stage } from "@/engine/Stage";
import { Lighting } from "@/engine/Lighting";
import { Ground } from "@/engine/Ground";
import { SchoolBuilding } from "@/engine/SchoolBuilding";
import { Fireflies } from "@/engine/Fireflies";
import { CameraRig, type CameraShot } from "@/engine/CameraRig";
import { Foxi, type FoxiClip } from "@/engine/Foxi";
import { FoxCoin } from "@/engine/FoxCoin";
import { FIREFLIES, qualityProfile } from "@/engine/quality";
import { Hud } from "@/game/hud/Hud";
import { FoxiDialogue } from "@/game/dialogue/FoxiDialogue";
import { VocabularyChallenge } from "@/game/activities/VocabularyChallenge";
import { RewardCinematic } from "@/game/reward/RewardCinematic";
import { Glass } from "@/ui/Glass";
import { GameButton } from "@/ui/Button";
import { useGame } from "@/game/store";
import type { Phase } from "@/game/phases";

const SHOT_BY_PHASE: Record<Phase, CameraShot> = {
  boot: "courtyard",
  explore: "courtyard",
  dialogue: "foxi",
  challenge: "school",
  reward: "reward",
};

const CLIP_BY_PHASE: Record<Phase, FoxiClip> = {
  boot: "idle",
  explore: "idle",
  dialogue: "wave",
  challenge: "idle",
  reward: "cheer",
};

function resolvePlayerName(): string {
  if (typeof window === "undefined") return "Исследователь";
  return window.localStorage.getItem("world.name") || "Исследователь";
}

export default function WorldPage() {
  const { phase, player, quest, error, boot, clickSchool, finish } = useGame();
  const fireflies = FIREFLIES[qualityProfile()];

  useEffect(() => {
    if (!player) void boot(resolvePlayerName());
  }, [boot, player]);

  const retryBoot = () => void boot(resolvePlayerName());

  const rewardCoins = phase === "reward" && finish && !finish.practice ? Math.min(finish.coins_delta, 12) : 0;
  const questActive = phase === "explore" && quest?.status !== "completed";

  return (
    <main className="relative h-dvh w-full overflow-hidden bg-[#241a30]">
      <Stage>
        <Lighting />
        <CameraRig shot={SHOT_BY_PHASE[phase]} />
        <Ground />
        <SchoolBuilding highlighted={questActive} onClick={() => void clickSchool()} />
        <Foxi clip={CLIP_BY_PHASE[phase]} />
        {Array.from({ length: rewardCoins }).map((_, i) => (
          <FoxCoin key={i} position={[2.4, 1.2, -0.4]} swirl seed={i * 0.7} />
        ))}
        <Fireflies count={fireflies} />
      </Stage>

      <Hud />
      <FoxiDialogue />
      <VocabularyChallenge />
      <RewardCinematic />

      {phase === "boot" ? (
        <div className="absolute inset-0 grid place-items-center bg-[#241a30] p-6">
          {error ? (
            <Glass className="w-full max-w-md p-6 text-center">
              <p className="font-[family-name:var(--font-display)] text-lg font-extrabold tracking-wide text-[#f5ed75]">
                Фоксинбург не отвечает
              </p>
              <p className="mt-2 text-sm text-white/70">{error}</p>
              <div className="mt-5 flex justify-center">
                <GameButton onClick={retryBoot}>Попробовать снова</GameButton>
              </div>
            </Glass>
          ) : (
            <p className="font-[family-name:var(--font-display)] text-lg font-extrabold tracking-wide text-[#f5ed75]">
              Фоксинбург просыпается…
            </p>
          )}
        </div>
      ) : null}

      {error && phase !== "boot" ? (
        <div className="absolute inset-x-0 bottom-0 bg-[#c96f4a] p-3 text-center text-sm">
          Мир недоступен: {error}
        </div>
      ) : null}
    </main>
  );
}
