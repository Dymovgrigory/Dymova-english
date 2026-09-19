/** Телефон родителя: маска +7 (___) ___-__-__ и нормализация в E.164. */

/** Из любого ввода выделяет 10 значащих цифр абонента (8 и 7 в начале — префикс РФ). */
export function subscriberDigits(input: string): string {
  let digits = input.replace(/\D/g, "");
  if (digits.startsWith("8") || digits.startsWith("7")) digits = digits.slice(1);
  return digits.slice(0, 10);
}

/** 9164552233 → "+79164552233". Пусто, если цифр не 10. */
export function toE164(digits: string): string | null {
  return digits.length === 10 ? `+7${digits}` : null;
}

/** 9164552 → "+7 (916) 455-2"; пустой ввод → "". */
export function formatPhone(digits: string): string {
  if (!digits) return "";
  const a = digits.slice(0, 3);
  const b = digits.slice(3, 6);
  const c = digits.slice(6, 8);
  const d = digits.slice(8, 10);
  let out = `+7 (${a}`;
  if (a.length === 3) out += ")";
  if (b) out += ` ${b}`;
  if (c) out += `-${c}`;
  if (d) out += `-${d}`;
  return out;
}
