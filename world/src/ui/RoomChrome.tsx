/**
 * Room chrome — fantasy castle standard for Foxinburg World.
 * Re-exports proportional plaques, CTAs, stats, icons.
 */
export {
  FantasyDock as RoomSheet,
  FantasyTitlePlate as RoomHeader,
  FantasyButton as RoomCta,
  FantasyStat as RoomTile,
  FantasyPanel,
  FantasyButton,
  FantasyStat,
  FantasyDock,
  FantasyTitlePlate,
  FantasyNavChip,
  FantasyHudChip,
  BrandIcon,
  ChromeIcon,
} from "@/ui/fantasy/Chrome";

export { FantasyKicker as RoomKicker, FantasyTitle as RoomTitle } from "@/ui/fantasy/StickerDrawer";

export function RoomLead({ children }: { children: React.ReactNode }) {
  return (
    <p className="mx-auto max-w-[18rem] text-center text-[12px] font-medium leading-snug text-white/80">{children}</p>
  );
}

export function RoomRelic({
  children,
  active = false,
  muted = false,
  className = "",
}: {
  children: React.ReactNode;
  active?: boolean;
  muted?: boolean;
  className?: string;
}) {
  return (
    <div
      className={`relative overflow-hidden border p-2.5 text-center ${
        active
          ? "border-[#f5ed75]/65 bg-[#f5ed75]/12 shadow-[0_0_14px_rgba(245,237,117,0.28)]"
          : muted
            ? "border-white/10 bg-white/5 opacity-45 grayscale"
            : "border-[#7fd8c9]/25 bg-[#3a2953]/65"
      } ${className}`}
      style={{ clipPath: "polygon(8% 0, 92% 0, 100% 12%, 100% 88%, 92% 100%, 8% 100%, 0 88%, 0 12%)" }}
    >
      {children}
    </div>
  );
}
