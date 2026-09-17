"use client";

import { motion, useReducedMotion } from "motion/react";

/** Латунная трубка с тёплым светящимся наполнением. */
export function ProgressBar({ value, label }: { value: number; label: string }) {
  const reduce = useReducedMotion();
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <div
      className="relative h-5 w-full overflow-hidden rounded-full bg-[#1a1224] p-[3px] shadow-[inset_0_2px_5px_rgb(0_0_0/0.8),0_0_0_2px_#b9852c,0_0_0_3px_#5a3a10]"
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={pct}
    >
      <motion.div
        className="relative h-full rounded-full bg-[linear-gradient(180deg,#fff2b0,#ffc44d_45%,#e08a1e)] shadow-[0_0_14px_rgb(255_180_60/0.8)]"
        initial={false}
        animate={{ width: `${Math.max(pct, 4)}%` }}
        transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 140, damping: 22 }}
      >
        <span className="absolute inset-x-2 top-[2px] h-[3px] rounded-full bg-white/70" />
      </motion.div>
    </div>
  );
}
