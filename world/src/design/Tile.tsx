type TileProps = {
  label: string;
  used?: boolean;
  onPress: () => void;
  disabled?: boolean;
  size?: "word" | "letter";
};

/** Плитка слова или буквы для «Пазла». Использованная плитка оставляет пустое место. */
export function Tile({ label, used = false, onPress, disabled, size = "word" }: TileProps) {
  const sizing = size === "letter" ? "min-w-12 h-14 text-[24px] lowercase" : "h-12 px-4 text-[18px]";
  if (used) {
    return <span aria-hidden className={`${sizing} inline-block rounded-xl bg-grid`} >&nbsp;</span>;
  }
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onPress}
      className={[
        "press inline-flex items-center justify-center rounded-xl border-2 border-line bg-white font-bold text-ink",
        "shadow-[0_3px_0_var(--color-line)] hover:bg-[#f7f4fd]",
        "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-royal/30",
        sizing,
      ].join(" ")}
    >
      {label}
    </button>
  );
}
