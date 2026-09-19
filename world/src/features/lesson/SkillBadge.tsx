import { skillFor } from "@/lib/v2/skills";
import type { Challenge } from "@/lib/v2/types";

/** Маленький шильдик навыка в углу карточки задания (выступает над краем, контент не перекрывает). */
export function SkillBadge({ type }: { type: Challenge["type"] }) {
  return (
    <span className="pointer-events-none absolute -top-3 right-4 rounded-full bg-[#4a2a66] px-3 py-1 text-[12px] font-extrabold tracking-wide text-[#f6efe2] shadow-[0_3px_0_#2a1a3d,0_8px_14px_-6px_rgb(0_0_0/0.6)] ring-2 ring-[#ffd36e]/50">
      {skillFor(type)}
    </span>
  );
}
