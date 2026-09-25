import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "crown" | "royal" | "mint" | "coral" | "paper" | "ghost";

/* Объёмные кнопки из «материалов» миниатюры: латунь, эмаль, тёмный бархат. */
const VARIANTS: Record<Variant, string> = {
  crown: "mat-brass",
  royal:
    "text-[#fff6e3] bg-[linear-gradient(180deg,#6b4f96,#3a2953)] shadow-[inset_0_1px_0_rgb(255_255_255/0.35),0_6px_0_#231733,0_12px_22px_-6px_rgb(0_0_0/0.55)]",
  mint:
    "text-[#07302a] bg-[linear-gradient(180deg,rgb(255_255_255/0.45)_0%,transparent_40%),linear-gradient(180deg,#9ff0dd,#3fae98)] shadow-[inset_0_1px_0_#fff,0_6px_0_#1f6f60,0_12px_22px_-6px_rgb(0_0_0/0.5)]",
  coral:
    "text-[#fff3ef] bg-[linear-gradient(180deg,rgb(255_255_255/0.35)_0%,transparent_40%),linear-gradient(180deg,#ff8b7a,#c73c30)] shadow-[inset_0_1px_0_rgb(255_255_255/0.6),0_6px_0_#7c1f17,0_12px_22px_-6px_rgb(0_0_0/0.5)]",
  paper: "mat-enamel",
  ghost: "bg-transparent text-[#f6efe2] hover:bg-white/10",
};

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: "md" | "lg";
  block?: boolean;
  children: ReactNode;
};

export function Button({ variant = "crown", size = "lg", block = false, className = "", children, ...rest }: ButtonProps) {
  const sizing = size === "lg" ? "min-h-14 px-7 text-[18px]" : "min-h-12 px-5 text-[15px]";
  return (
    <button
      type="button"
      {...rest}
      className={[
        "press relative z-10 inline-flex items-center justify-center gap-2 rounded-2xl font-extrabold tracking-[0.01em]",
        "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[#ffd36e]/70",
        "disabled:cursor-not-allowed disabled:bg-none disabled:bg-[#4a3f58] disabled:text-[#c9bfd8]/70 disabled:shadow-[inset_0_1px_0_rgb(255_255_255/0.12),0_6px_0_#2c2437]",
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
