import type { NodeKind, NodeStatus } from "@/lib/v2/types";

import { Icon, type IconName } from "./Icon";

const KIND_ICON: Record<NodeKind, IconName> = {
  words: "star",
  phonics: "letters",
  grammar: "rule",
  chest: "chest",
  review: "repeat",
  module_test: "crown",
};

const STATUS: Record<NodeStatus, string> = {
  completed: "bg-royal text-crown shadow-[0_6px_0_var(--color-royal-edge)]",
  current: "seal-current bg-crown text-royal-deep shadow-[0_6px_0_var(--color-crown-edge)]",
  open: "bg-white text-royal border-[3px] border-royal/25 shadow-[0_6px_0_var(--color-line)]",
  locked: "bg-grid text-ink-soft/50 shadow-[0_6px_0_var(--color-line)]",
};

type SealProps = {
  kind: NodeKind;
  status: NodeStatus;
  stars: number;
  label: string;
  onPress: () => void;
};

/** Узел пути — «королевская печать». Контрольная крупнее, сундук без круга-печати. */
export function Seal({ kind, status, stars, label, onPress }: SealProps) {
  const big = kind === "module_test";
  const locked = status === "locked";
  return (
    <button
      type="button"
      onClick={onPress}
      aria-label={`${label}${locked ? ", закрыто" : status === "completed" ? ", пройдено" : ""}`}
      className={[
        "press relative flex items-center justify-center rounded-full",
        "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-royal/35",
        big ? "size-[92px]" : "size-[76px]",
        STATUS[status],
      ].join(" ")}
    >
      <span className="pointer-events-none absolute inset-[7px] rounded-full border-2 border-dashed border-current opacity-25" />
      <Icon name={locked ? "lock" : KIND_ICON[kind]} size={big ? 40 : 32} filled={!locked && (kind === "words" || kind === "module_test")} />
      {kind === "module_test" && stars > 0 && (
        <span className="absolute -bottom-3 flex gap-0.5 rounded-full bg-white px-2 py-0.5 text-crown-edge shadow-sm">
          {[1, 2, 3].map((n) => (
            <Icon key={n} name="star" size={14} filled={n <= stars} className={n <= stars ? "" : "text-line"} />
          ))}
        </span>
      )}
    </button>
  );
}
