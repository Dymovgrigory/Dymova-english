"use client";

import { foxiSrc } from "@/lib/foxiPoses";

type Props = {
  line: string;
  kicker?: string;
  pose?: string;
  size?: "sm" | "md";
};

export function FoxiGuide({ line, kicker, pose = "wave", size = "md" }: Props) {
  const fox = size === "sm" ? "h-[5.5rem]" : "h-[8.25rem]";
  return (
    <div className="flex items-end gap-0">
      <img
        src={foxiSrc(pose)}
        alt="Foxy"
        className={`${fox} relative z-[1] -mb-1 -mr-1 w-auto shrink-0 origin-bottom object-contain object-bottom drop-shadow-sm`}
      />
      <div className="relative mb-5 min-w-0 flex-1">
        <div className="rounded-2xl border-2 border-[#3a2953]/10 bg-white/90 px-4 py-3 shadow-[0_6px_0_rgba(58,41,83,0.06)] backdrop-blur">
          {kicker ? (
            <p className="text-[11px] font-bold text-[#3a2953]/45">{kicker}</p>
          ) : null}
          <p className={`font-[family-name:var(--font-display)] font-extrabold leading-snug text-[#3c3c3c] ${kicker ? "mt-1" : ""}`}>
            {line}
          </p>
        </div>
        <span
          className="absolute bottom-6 -left-[9px] h-4 w-4 rotate-45 border-b-2 border-l-2 border-[#3a2953]/10 bg-white"
          aria-hidden
        />
      </div>
    </div>
  );
}
