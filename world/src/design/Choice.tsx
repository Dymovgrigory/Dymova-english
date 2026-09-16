import type { ReactNode } from "react";

export type ChoiceState = "idle" | "selected" | "correct" | "wrong" | "muted";

const STATES: Record<ChoiceState, string> = {
  idle: "border-line bg-white shadow-[0_4px_0_var(--color-line)] hover:bg-[#f7f4fd]",
  selected: "border-royal bg-[#efe9fb] shadow-[0_4px_0_var(--color-royal)]",
  correct: "border-mint-edge bg-mint-wash shadow-[0_4px_0_var(--color-mint-edge)] text-mint-ink",
  wrong: "border-coral-edge bg-coral-wash shadow-[0_4px_0_var(--color-coral-edge)] text-coral-ink",
  muted: "border-line bg-white/70 opacity-60",
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

/** Вариант ответа: крупная нажимаемая плитка с цифрой-подсказкой для клавиатуры. */
export function Choice({ state, hotkey, disabled, onPick, children, className = "", label }: ChoiceProps) {
  return (
    <button
      type="button"
      aria-pressed={state === "selected"}
      aria-label={label}
      disabled={disabled}
      onClick={onPick}
      className={[
        "press relative flex min-h-16 w-full items-center gap-3 rounded-2xl border-2 px-4 py-3 text-left text-[19px] font-bold text-ink",
        "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-royal/30",
        STATES[state],
        className,
      ].join(" ")}
    >
      {hotkey !== undefined && (
        <span className="hidden size-7 shrink-0 items-center justify-center rounded-lg border-2 border-line text-[13px] font-extrabold text-ink-soft sm:flex">
          {hotkey}
        </span>
      )}
      {children}
    </button>
  );
}
