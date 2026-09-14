import type { ReactNode } from "react";

/** Glass-панель Game OS: purple-dark 70% + blur, скругление 20px. */
export function Glass({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-[20px] border border-white/10 bg-[#241a30]/70 backdrop-blur-md shadow-[0_18px_50px_rgba(0,0,0,0.45)] ${className}`}
    >
      {children}
    </div>
  );
}
