"use client";

import Link from "next/link";
import type { Player } from "@/lib/api";
import { Hearts } from "@/ui/Marks";

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
        className="rounded-full border border-white/20 bg-[#241a30]/65 px-3 py-1.5 text-sm font-extrabold text-[#f5ed75] shadow-[0_3px_0_rgba(0,0,0,0.25)] backdrop-blur-md"
      >
        ← Замок
      </Link>
      <div className="flex flex-wrap items-center gap-2 text-sm font-extrabold">
        <Hearts count={hearts} onDark />
        <span className="rounded-full bg-[#f5ed75] px-3 py-1 text-[#241a30] shadow-[0_3px_0_rgba(0,0,0,0.25)]">🪙 {showCoins}</span>
        <span className="rounded-full border border-white/15 bg-[#241a30]/65 px-3 py-1 text-white shadow-[0_3px_0_rgba(0,0,0,0.2)] backdrop-blur-md">
          ⚡ {showXp}
        </span>
        <span className="rounded-full border border-white/15 bg-[#241a30]/65 px-3 py-1 text-white shadow-[0_3px_0_rgba(0,0,0,0.2)] backdrop-blur-md">
          🔥 {showStreak}
        </span>
        <Link
          href="/learn/album"
          className="rounded-full border border-white/15 bg-[#241a30]/65 px-3 py-1 text-white shadow-[0_3px_0_rgba(0,0,0,0.2)] backdrop-blur-md"
        >
          ★ {stickers}
        </Link>
      </div>
    </div>
  );
}
