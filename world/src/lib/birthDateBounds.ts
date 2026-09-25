/** Границы даты рождения под правило бэкенда: возраст 3–17 лет. */

export function birthDateBounds(today: Date = new Date()): { min: string; max: string } {
  const max = new Date(today.getFullYear() - 3, today.getMonth(), today.getDate());
  const min = new Date(today.getFullYear() - 17, today.getMonth(), today.getDate());
  return { min: toIsoDate(min), max: toIsoDate(max) };
}

function toIsoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}
