/** Облик замка: что показать, если ребёнок ничего не выбрал, и как красить слой света. */
import type { Appearance } from "@/lib/v2/castle";

export function seasonByDate(date: Date): string {
  const month = date.getMonth() + 1;
  if (month === 12 || month <= 2) return "winter";
  if (month <= 5) return "spring";
  if (month <= 8) return "summer";
  return "autumn";
}

export function timeByClock(date: Date): string {
  const hour = date.getHours();
  if (hour < 5 || hour >= 22) return "night";
  if (hour < 9) return "dawn";
  if (hour < 18) return "day";
  return "dusk";
}

export function effectiveAppearance(
  appearance: Appearance,
  now: Date,
): { season: string; time: string; weather: string | null } {
  return {
    season: appearance.season ?? seasonByDate(now),
    time: appearance.time_of_day ?? timeByClock(now),
    weather: appearance.weather,
  };
}

/** Слой света поверх диорамы: плёнка цвета, а не перерисовка картинки. */
export function lightLayer(time: string): { background: string; mixBlendMode: string } {
  const layers: Record<string, string> = {
    dawn: "linear-gradient(180deg, rgb(255 190 140 / 0.28), rgb(120 90 160 / 0.18))",
    day: "linear-gradient(180deg, transparent, transparent)",
    dusk: "linear-gradient(180deg, rgb(255 140 90 / 0.22), rgb(70 40 110 / 0.30))",
    night: "linear-gradient(180deg, rgb(20 24 70 / 0.55), rgb(10 12 40 / 0.62))",
  };
  return { background: layers[time] ?? layers.day, mixBlendMode: time === "night" ? "multiply" : "soft-light" };
}
