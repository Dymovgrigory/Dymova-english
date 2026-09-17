import type { ReactNode } from "react";

/** Glass-панель Game OS: purple-dark 70% + blur, скругление 20px. */
export function Glass({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={`overflow-hidden border border-[#f5ed75]/35 bg-[#241a30]/80 backdrop-blur-md shadow-[0_18px_50px_rgba(0,0,0,0.45)] ${className}`}
      style={{ clipPath: "polygon(3% 0, 97% 0, 100% 8%, 100% 92%, 97% 100%, 3% 100%, 0 92%, 0 8%)" }}
    >
      {children}
    </div>
  );
}
