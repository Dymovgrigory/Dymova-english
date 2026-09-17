"use client";

import Link from "next/link";
import type { Player } from "@/lib/api";
import { BrandIcon, ChromeIcon, FantasyHudChip } from "@/ui/RoomChrome";

type Props = {
  hearts?: number;
  coins?: number;
  xp?: number;
  streak?: number;
  stickers?: number;
  player?: Player | null;
};

export function WorldBar({ hearts = 5, coins = 0, xp = 0, streak = 0, stickers = 0, player }: Props) {
  const showCoins = player?.coins ?? coins;
  const showXp = player?.xp ?? xp;
  const showStreak = player?.streak_days ?? streak;
  return (
    <div className="mx-auto flex max-w-2xl flex-wrap items-center justify-between gap-2">
      <Link
        href="/world"
        className="relative inline-flex min-h-[40px] items-center gap-1.5 overflow-hidden border border-[#f5ed75]/35 bg-[linear-gradient(180deg,rgba(58,41,83,0.95),rgba(36,26,48,0.98))] px-3 py-2 text-sm font-extrabold text-[#f5ed75]"
        style={{
          clipPath: "polygon(8% 0, 92% 0, 100% 50%, 92% 100%, 8% 100%, 0 50%)",
          backgroundImage: "url(/world/ui/frames/atlas-buttons.png)",
          backgroundSize: "400% 600%",
          backgroundPosition: "0% 60%",
          backgroundRepeat: "no-repeat",
        }}
      >
        <span aria-hidden className="pointer-events-none absolute inset-0 bg-[#241a30]/45" />
        <ChromeIcon name="back" className="relative z-[1] h-5 w-5" />
        <span className="relative z-[1]">Замок</span>
      </Link>
      <div className="flex flex-wrap items-center justify-end gap-1.5">
        <FantasyHudChip icon={<BrandIcon name="heart" className="!h-6 !w-6" />} value={hearts} />
        <FantasyHudChip icon={<BrandIcon name="coin" className="!h-6 !w-6" />} value={showCoins} gold />
        <FantasyHudChip icon={<BrandIcon name="xp" className="!h-6 !w-6" />} value={showXp} />
        <FantasyHudChip icon={<BrandIcon name="streak" className="!h-6 !w-6" />} value={showStreak} />
        <FantasyHudChip icon={<BrandIcon name="star" className="!h-6 !w-6" />} value={stickers} href="/world" />
      </div>
    </div>
  );
}
