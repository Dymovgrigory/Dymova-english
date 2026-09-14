"use client";

import type { ReactNode } from "react";

type Props = {
  children: ReactNode;
  onClick: () => void;
  variant?: "primary" | "ghost";
  disabled?: boolean;
};

export function GameButton({ children, onClick, variant = "primary", disabled }: Props) {
  const base =
    "rounded-full px-6 py-3 font-[family-name:var(--font-display)] text-sm font-extrabold uppercase tracking-wide transition-transform duration-150 active:scale-[0.96] disabled:opacity-40";
  const skin =
    variant === "primary"
      ? "bg-[#f5ed75] text-[#241a30] hover:brightness-110"
      : "border border-white/20 text-white hover:bg-white/10";
  return (
    <button className={`${base} ${skin}`} onClick={onClick} disabled={disabled}>
      {children}
    </button>
  );
}
