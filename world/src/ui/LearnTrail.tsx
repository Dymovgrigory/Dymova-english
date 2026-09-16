"use client";

import Link from "next/link";
import type { LearnUnit } from "@/lib/api";
import { Stars } from "@/ui/Marks";

type Props = {
  units: LearnUnit[];
  here: string | null;
};

const plaque = {
  clipPath: "polygon(3% 0, 97% 0, 100% 8%, 100% 92%, 97% 100%, 3% 100%, 0 92%, 0 8%)",
} as const;

const nodeClip = {
  clipPath: "polygon(15% 0, 85% 0, 100% 15%, 100% 85%, 85% 100%, 15% 100%, 0 85%, 0 15%)",
} as const;

export function LearnTrail({ units, here }: Props) {
  return (
    <ol className="mt-10 space-y-10">
      {units.map((unit, ui) => (
        <li key={unit.id} className="relative">
          {ui < units.length - 1 ? (
            <span
              aria-hidden
              className="absolute left-[1.65rem] top-16 bottom-[-2.5rem] w-1 rounded-full bg-gradient-to-b from-[#7fd8c9]/40 to-[#f5ed75]/45"
            />
          ) : null}
          <div
            className={`relative overflow-hidden border p-5 ${
              unit.locked
                ? "border-white/10 bg-[#241a30]/55 opacity-55"
                : "border-[#f5ed75]/35 bg-[#241a30] shadow-[0_12px_0_rgba(0,0,0,0.25)]"
            }`}
            style={plaque}
          >
            <span
              aria-hidden
              className="pointer-events-none absolute inset-0"
              style={{
                backgroundImage: "url(/world/ui/frames/atlas-frames.png)",
                backgroundSize: "160% auto",
                backgroundPosition: "88% 42%",
                backgroundRepeat: "no-repeat",
              }}
            />
            <span
              aria-hidden
              className="pointer-events-none absolute inset-0 bg-[linear-gradient(165deg,rgba(58,41,83,0.62),rgba(36,26,48,0.78))]"
            />
            <div
              className="pointer-events-none absolute -right-8 -top-10 h-32 w-32 rounded-full opacity-25 blur-2xl"
              style={{ background: unit.accent || "#f5ed75" }}
            />
            <p className="relative text-[11px] font-bold uppercase tracking-[0.2em] text-[#7fd8c9]/75">
              {unit.book_ru || "Модуль"} · {ui + 1}/{units.length}
            </p>
            <h2 className="relative mt-1 font-[family-name:var(--font-display)] text-2xl font-extrabold text-[#f5ed75]">
              {unit.title_ru}
            </h2>
            <p className="relative mt-1 text-sm text-white/60">{unit.topic_ru}</p>
            <div className="relative mt-5 flex flex-wrap justify-center gap-x-6 gap-y-5">
              {unit.lessons.map((lesson, i) => {
                const now = here === lesson.id;
                const done = lesson.stars > 0;
                const locked = lesson.locked || unit.locked;
                const exam = lesson.kind === "checkpoint";
                const bump = i % 2 === 1 ? "mt-7" : "";
                const inner = (
                  <span className={`grid justify-items-center gap-1 ${bump}`}>
                    <span
                      className={`grid h-16 w-16 place-items-center border-2 text-lg font-black transition ${
                        now
                          ? "animate-pulse border-[#f5ed75] bg-[#3a2953] text-[#f5ed75] shadow-[0_0_0_5px_rgba(245,237,117,0.35)]"
                          : done
                            ? "border-[#7fd8c9] bg-[#7fd8c9] text-[#13332c]"
                            : locked
                              ? "border-white/15 bg-white/10 text-white/30"
                              : exam
                                ? "border-[#ee7349] bg-[#3a2953] text-[#f5ed75]"
                                : "border-[#f5ed75]/55 bg-[#f5ed75] text-[#241a30]"
                      }`}
                      style={nodeClip}
                    >
                      {locked ? "·" : done ? "★" : exam ? "★" : i + 1}
                    </span>
                    <span className="max-w-[5.5rem] text-center text-[11px] font-extrabold leading-tight text-white/90">
                      {lesson.title_ru}
                    </span>
                    <Stars count={lesson.stars} onDark />
                  </span>
                );
                if (locked) {
                  return <span key={lesson.id}>{inner}</span>;
                }
                return (
                  <Link key={lesson.id} href={`/learn/${lesson.id}`} className="hover:brightness-110">
                    {inner}
                  </Link>
                );
              })}
            </div>
          </div>
        </li>
      ))}
    </ol>
  );
}
