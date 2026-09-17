import type { ReactNode } from "react";

export type ChoiceState = "idle" | "selected" | "correct" | "wrong" | "muted";

/* Эмалевые плашки с латунным ободком; выбранная — с бирюзовым свечением. */
const STATES: Record<ChoiceState, string> = {
  idle: "mat-enamel hover:-translate-y-0.5",
  selected:
    "mat-enamel -translate-y-0.5 !shadow-[inset_0_1px_0_#fff,0_0_0_3px_#3fae98,0_5px_0_#1f6f60,0_0_24px_-2px_rgb(63_174_152/0.75)]",
  correct:
    "text-[#07302a] bg-[linear-gradient(180deg,#e2fbf4,#a6ead9)] shadow-[inset_0_1px_0_#fff,0_0_0_3px_#3fae98,0_5px_0_#1f6f60,0_0_26px_-2px_rgb(63_174_152/0.8)]",
  wrong:
    "text-[#5a120c] bg-[linear-gradient(180deg,#fff0ec,#f6b9ae)] shadow-[inset_0_1px_0_#fff,0_0_0_3px_#d9483c,0_5px_0_#7c1f17]",
  muted: "mat-enamel opacity-55",
};

type ChoiceProps = {
  state: ChoiceState;
  hotkey?: number;
  disabled?: boolean;
  onPick: () => void;
  children: ReactNode;
  className?: string;
  label?: string;
};

export function Choice({ state, hotkey, disabled, onPick, children, className = "", label }: ChoiceProps) {
  return (
    <button
      type="button"
      aria-pressed={state === "selected"}
      aria-label={label}
      disabled={disabled}
      onClick={onPick}
      className={[
        "press relative flex min-h-16 w-full items-center gap-3 rounded-2xl px-4 py-3 text-left text-[19px] font-bold transition",
        "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[#ffd36e]/70",
        STATES[state],
        className,
      ].join(" ")}
    >
      {hotkey !== undefined && (
        <span className="hidden size-7 shrink-0 items-center justify-center rounded-full bg-[radial-gradient(circle_at_35%_30%,#fff2b8,#d9a13a)] text-[13px] font-extrabold text-[#3a2208] shadow-[0_2px_0_#8a5412] sm:flex">
          {hotkey}
        </span>
      )}
      {children}
    </button>
  );
}
