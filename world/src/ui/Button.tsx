"use client";

import type { ReactNode } from "react";

type Props = {
  children: ReactNode;
  onClick: () => void;
  disabled?: boolean;
};

export function GameButton({ children, onClick, disabled }: Props) {
  return (
    <button
      className="rounded-full bg-[#f5ed75] px-6 py-3 font-[family-name:var(--font-display)] text-sm font-extrabold uppercase tracking-wide text-[#241a30] transition-transform duration-150 hover:brightness-110 active:scale-[0.96] disabled:opacity-40"
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}
