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
      type="button"
      className="relative w-full overflow-hidden border border-[#fff6a8]/70 bg-[linear-gradient(180deg,#fff6a8,#f5ed75_35%,#e8b93e)] px-6 py-3.5 font-[family-name:var(--font-display)] text-base font-extrabold tracking-wide text-[#241a30] shadow-[0_5px_0_#9a7a18] transition active:translate-y-0.5 active:shadow-none disabled:opacity-40"
      style={{ clipPath: "polygon(6% 0, 94% 0, 100% 50%, 94% 100%, 6% 100%, 0 50%)" }}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}
