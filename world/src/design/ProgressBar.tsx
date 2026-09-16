"use client";

import { motion, useReducedMotion } from "motion/react";

export function ProgressBar({ value, label }: { value: number; label: string }) {
  const reduce = useReducedMotion();
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <div
      className="relative h-4 w-full overflow-hidden rounded-full bg-grid"
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={pct}
    >
      <motion.div
        className="absolute inset-y-0 left-0 rounded-full bg-mint"
        initial={false}
        animate={{ width: `${pct}%` }}
        transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 140, damping: 22 }}
      >
        <span className="absolute inset-x-2 top-[3px] h-[4px] rounded-full bg-white/45" />
      </motion.div>
    </div>
  );
}
