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

export default function WorldPage() {
  const { phase, player, error, boot, clickSchool, finish } = useGame();
  const fireflies = FIREFLIES[qualityProfile()];

  useEffect(() => {
    if (!player) {
      const name =
        (typeof window !== "undefined" && window.localStorage.getItem("world.name")) ||
        "Исследователь";
      void boot(name);
    }
  }, [boot, player]);

  const rewardCoins = phase === "reward" && finish ? Math.min(finish.coins_delta, 12) : 0;

  return (
    <main className="relative h-dvh w-full overflow-hidden bg-[#241a30]">
      <Stage>
        <Lighting />
        <CameraRig shot={SHOT_BY_PHASE[phase]} />
        <Ground />
        <SchoolBuilding highlighted={phase === "explore"} onClick={() => void clickSchool()} />
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
        <div className="absolute inset-0 grid place-items-center bg-[#241a30]">
          <p className="font-[family-name:var(--font-display)] text-lg font-extrabold tracking-wide text-[#f5ed75]">
            Фоксинбург просыпается…
          </p>
        </div>
      ) : null}

      {error ? (
        <div className="absolute inset-x-0 bottom-0 bg-[#c96f4a] p-3 text-center text-sm">
          Мир недоступен: {error}
        </div>
      ) : null}
    </main>
  );
}
