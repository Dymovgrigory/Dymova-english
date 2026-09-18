/** Форматирование недельных трофеев лиги (Башня Славы). */

const MONTHS_RU = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"];

/** «2026-09-07» → «7–13 сен»; при переходе через месяц — «28 сен – 4 окт». */
export function formatWeekRange(weekStart: string): string {
  const start = new Date(`${weekStart}T00:00:00`);
  if (Number.isNaN(start.getTime())) return weekStart;
  const end = new Date(start);
  end.setDate(end.getDate() + 6);
  if (start.getMonth() === end.getMonth()) return `${start.getDate()}–${end.getDate()} ${MONTHS_RU[start.getMonth()]}`;
  return `${start.getDate()} ${MONTHS_RU[start.getMonth()]} – ${end.getDate()} ${MONTHS_RU[end.getMonth()]}`;
}

/** Медаль за 1–3 место, иначе null. */
export function medalForRank(rank: number): string | null {
  return rank === 1 ? "🥇" : rank === 2 ? "🥈" : rank === 3 ? "🥉" : null;
}
