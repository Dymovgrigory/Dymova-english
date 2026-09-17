type TileProps = {
  label: string;
  used?: boolean;
  onPress: () => void;
  disabled?: boolean;
  size?: "word" | "letter";
};

/** Плитка слова или буквы для «Пазла» — эмалевый брусочек; использованная оставляет углубление. */
export function Tile({ label, used = false, onPress, disabled, size = "word" }: TileProps) {
  const sizing = size === "letter" ? "min-w-12 h-14 text-[24px] lowercase" : "h-12 px-4 text-[18px]";
  if (used) {
    return (
      <span aria-hidden className={`${sizing} inline-block rounded-xl bg-[#d9c59c] shadow-[inset_0_3px_6px_rgb(92_60_30/0.35)]`}>
        &nbsp;
      </span>
    );
  }
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onPress}
      className={[
        "press mat-enamel inline-flex items-center justify-center rounded-xl font-bold",
        "hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[#ffd36e]/70",
        sizing,
      ].join(" ")}
    >
      {label}
    </button>
  );
}
