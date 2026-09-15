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
  const c = player?.coins ?? coins;
  const x = player?.xp ?? xp;
  const s = player?.streak_days ?? streak;
  return (
    <div className="mx-auto flex max-w-2xl flex-wrap items-center justify-between gap-2">
      <Link href="/world" className="text-sm text-[#241a30]/55">
        ← Замок
      </Link>
      <div className="flex flex-wrap items-center gap-2 text-sm font-extrabold">
        <Hearts count={hearts} />
        <span className="rounded-full bg-[#f5ed75] px-3 py-1 text-[#241a30] shadow-[0_3px_0_rgba(36,26,48,0.12)]">🪙 {c}</span>
        <span className="rounded-full bg-white px-3 py-1 text-[#3a2953] shadow-[0_3px_0_rgba(36,26,48,0.06)]">⚡ {x}</span>
        <span className="rounded-full bg-white px-3 py-1 shadow-[0_3px_0_rgba(36,26,48,0.06)]">🔥 {s}</span>
        <Link href="/learn/album" className="rounded-full bg-white px-3 py-1 shadow-[0_3px_0_rgba(36,26,48,0.06)]">
          ★ {stickers}
        </Link>
      </div>
    </div>
  );
}
