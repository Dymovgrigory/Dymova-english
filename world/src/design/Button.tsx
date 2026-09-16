import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "crown" | "royal" | "mint" | "coral" | "paper" | "ghost";

const VARIANTS: Record<Variant, string> = {
  crown: "bg-crown text-royal-deep shadow-[0_5px_0_var(--color-crown-edge)] hover:brightness-[1.03]",
  royal: "bg-royal text-white shadow-[0_5px_0_var(--color-royal-edge)] hover:bg-[#46345f]",
  mint: "bg-mint text-royal-deep shadow-[0_5px_0_var(--color-mint-edge)]",
  coral: "bg-coral text-white shadow-[0_5px_0_var(--color-coral-edge)]",
  paper: "bg-white text-royal border-2 border-line shadow-[0_4px_0_var(--color-line)] hover:bg-[#f6f3fc]",
  ghost: "bg-transparent text-royal hover:bg-grid/60",
};

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: "md" | "lg";
  block?: boolean;
  children: ReactNode;
};

export function Button({ variant = "crown", size = "lg", block = false, className = "", children, ...rest }: ButtonProps) {
  const sizing = size === "lg" ? "min-h-14 px-7 text-[17px]" : "min-h-12 px-5 text-[15px]";
  return (
    <button
      type="button"
      {...rest}
      className={[
        "press inline-flex items-center justify-center gap-2 rounded-2xl font-extrabold tracking-[0.01em]",
        "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-royal/35",
        "disabled:cursor-not-allowed disabled:bg-grid disabled:text-ink-soft/60 disabled:shadow-[0_5px_0_var(--color-line)]",
        VARIANTS[variant],
        sizing,
        block ? "w-full" : "",
        className,
      ].join(" ")}
    >
      {children}
    </button>
  );
}
