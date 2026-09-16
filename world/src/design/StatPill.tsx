import { Icon, type IconName } from "./Icon";

const TONES = {
  flame: "text-[#ff8a3d]",
  bolt: "text-[#c9a400]",
  coin: "text-[#d69e00]",
} as const;

type StatPillProps = { icon: keyof typeof TONES & IconName; value: number | string; label: string; dim?: boolean };

export function StatPill({ icon, value, label, dim = false }: StatPillProps) {
  return (
    <span className={`inline-flex items-center gap-1.5 text-[17px] font-extrabold ${dim ? "text-ink-soft/60" : "text-ink"}`} title={label}>
      <span className={dim ? "text-ink-soft/50" : TONES[icon]}>
        <Icon name={icon} size={22} filled={icon !== "coin"} />
      </span>
      <span className="tabular-nums">{value}</span>
      <span className="sr-only">{label}</span>
    </span>
  );
}
