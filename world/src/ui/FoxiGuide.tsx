"use client";

import { foxiSrc } from "@/lib/foxiPoses";

type Props = {
  line: string;
  kicker?: string;
  pose?: string;
  size?: "sm" | "md";
  /** light = cream bubble (lesson sheet); dark = glass on cinematic wash */
  tone?: "light" | "dark";
};

export function FoxiGuide({ line, kicker, pose = "wave", size = "md", tone = "light" }: Props) {
  const foxHeight = size === "sm" ? "h-[5.5rem]" : "h-[8.25rem]";
  const dark = tone === "dark";
  const bubble = dark
    ? "border border-[#f5ed75]/35 bg-[linear-gradient(165deg,rgba(58,41,83,0.9),rgba(36,26,48,0.95))] shadow-[0_12px_40px_rgba(0,0,0,0.35)]"
    : "border-2 border-[#3a2953]/10 bg-white/90 shadow-[0_6px_0_rgba(58,41,83,0.06)]";
  const tail = dark
    ? "border-b border-l border-[#f5ed75]/35 bg-[#241a30]"
    : "border-b-2 border-l-2 border-[#3a2953]/10 bg-white";

  return (
    <div className="flex items-end gap-0">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={foxiSrc(pose)}
        alt="Foxy"
        className={`${foxHeight} relative z-[1] -mb-1 -mr-1 w-auto shrink-0 origin-bottom object-contain object-bottom drop-shadow-[0_8px_24px_rgba(0,0,0,0.35)]`}
      />
      <div className="relative mb-5 min-w-0 flex-1">
        <div
          className={`px-4 py-3 backdrop-blur-md ${bubble}`}
          style={
            dark
              ? { clipPath: "polygon(4% 0, 96% 0, 100% 14%, 100% 86%, 96% 100%, 4% 100%, 0 86%, 0 14%)" }
              : undefined
          }
        >
          {kicker ? (
            <p className={`text-[11px] font-bold ${dark ? "text-[#7fd8c9]" : "text-[#3a2953]/45"}`}>{kicker}</p>
          ) : null}
          <p
            className={`font-[family-name:var(--font-display)] font-extrabold leading-snug ${
              dark ? "text-white" : "text-[#3c3c3c]"
            } ${kicker ? "mt-1" : ""}`}
          >
            {line}
          </p>
        </div>
        {!dark ? <span className={`absolute bottom-6 -left-[9px] h-4 w-4 rotate-45 ${tail}`} aria-hidden /> : null}
      </div>
    </div>
  );
}
