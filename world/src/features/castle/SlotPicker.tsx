"use client";

import { SLOT_TITLES } from "@/castle/decor";
import type { SlotOption } from "./decorPlacement";

/**
 * Выбор места для украшения: свободные слоты и занятые (с именем того, кто стоит —
 * тап по занятому заменяет предмет). Общий для примерки и мастерской.
 */
export function SlotPicker({
  title,
  options,
  busy,
  onPick,
  onCancel,
}: {
  title: string;
  options: SlotOption[];
  busy: boolean;
  onPick: (option: SlotOption) => void;
  onCancel: () => void;
}) {
  return (
    <div
      role="dialog"
      aria-label={`Куда поставить: ${title}`}
      className="fixed inset-0 z-[70] flex items-end justify-center bg-[#1a1230]/60 p-4"
      onClick={onCancel}
    >
      <div
        className="w-full max-w-sm space-y-2 rounded-3xl bg-[#241a40] p-4 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <p className="text-center text-[15px] font-extrabold text-[#f6efe2]">Куда поставить «{title}»?</p>
        <ul className="space-y-1.5">
          {options.map((option) => (
            <li key={option.id}>
              <button
                type="button"
                disabled={busy}
                onClick={() => onPick(option)}
                className="w-full rounded-2xl bg-white/10 px-4 py-2.5 text-left text-[14px] font-bold text-[#f6efe2] press"
              >
                {SLOT_TITLES[option.id] ?? option.id}
                <span className="block text-[12px] font-bold text-[#c9b8e8]">
                  {option.occupant ? `здесь стоит «${option.occupant.title_ru}» — заменить` : "свободно"}
                </span>
              </button>
            </li>
          ))}
        </ul>
        <button
          type="button"
          onClick={onCancel}
          className="w-full rounded-full bg-white/10 py-2 text-[13px] font-extrabold text-[#c9b8e8] press"
        >
          Отмена
        </button>
      </div>
    </div>
  );
}
