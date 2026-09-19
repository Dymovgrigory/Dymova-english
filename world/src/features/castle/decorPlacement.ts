/** Расстановка украшений по слотам: где свободно, где кто-то стоит, нужен ли выбор места. */
import { defaultSlotFor, slotsForAnchor } from "@/castle/decor";
import type { CastleItem, DecorItem } from "@/lib/v2/castle";

export type SlotOption = { id: string; occupant: DecorItem | null };

/** Слоты якоря предмета с occupant'ами: кто уже стоит в каждом. */
export function slotOptions(anchor: string | null, decor: DecorItem[]): SlotOption[] {
  const bySlot = new Map(decor.filter((d) => d.active && d.slot).map((d) => [d.slot as string, d]));
  return slotsForAnchor(anchor ?? "").map((id) => ({ id, occupant: bySlot.get(id) ?? null }));
}

/** Дефолтный слот предмета занят другим — нужно спросить, куда поставить. */
export function needsSlotPicker(item: CastleItem, decor: DecorItem[]): boolean {
  const target = defaultSlotFor(item.id, item.anchor);
  if (!target) return true;
  return decor.some((d) => d.active && d.slot === target && d.item_id !== item.id);
}
