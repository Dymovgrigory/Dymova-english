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

/** Темы оформления Мира: какие слои ставит тема и её цветовое настроение (плёнка поверх сцены). */
export const THEME_LOOK: Record<string, { season: string; time_of_day: string; weather: string | null; mood: string; swatch: string }> = {
  "winter-tale": { season: "winter", time_of_day: "night", weather: "snow",
    mood: "radial-gradient(120% 80% at 50% 10%, rgb(170 210 255 / 0.30), rgb(40 60 140 / 0.25))", swatch: "linear-gradient(135deg,#cfe6ff,#3a4f9e)" },
  "lantern-fest": { season: "autumn", time_of_day: "dusk", weather: "fireflies",
    mood: "radial-gradient(120% 90% at 50% 70%, rgb(255 170 60 / 0.32), rgb(120 40 80 / 0.22))", swatch: "linear-gradient(135deg,#ffc56b,#8c2f5e)" },
  blossom: { season: "spring", time_of_day: "dawn", weather: "petals",
    mood: "linear-gradient(180deg, rgb(255 190 220 / 0.30), rgb(255 240 200 / 0.12))", swatch: "linear-gradient(135deg,#ffd1e6,#fff0c4)" },
  "golden-summer": { season: "summer", time_of_day: "day", weather: null,
    mood: "linear-gradient(180deg, rgb(255 220 120 / 0.26), rgb(255 180 60 / 0.10))", swatch: "linear-gradient(135deg,#ffe48a,#f2a93b)" },
  "misty-autumn": { season: "autumn", time_of_day: "dawn", weather: "fog",
    mood: "linear-gradient(180deg, rgb(200 170 140 / 0.30), rgb(110 90 80 / 0.20))", swatch: "linear-gradient(135deg,#d8c3a5,#6e5a50)" },
  "magic-dusk": { season: "summer", time_of_day: "dusk", weather: "fireflies",
    mood: "radial-gradient(130% 90% at 50% 20%, rgb(190 120 255 / 0.30), rgb(40 20 90 / 0.30))", swatch: "linear-gradient(135deg,#c79bff,#2a1a5e)" },
  "rainy-day": { season: "spring", time_of_day: "day", weather: "rain",
    mood: "linear-gradient(180deg, rgb(120 150 180 / 0.32), rgb(80 110 140 / 0.18))", swatch: "linear-gradient(135deg,#a9c2d8,#4f6e8c)" },
  "polar-night": { season: "winter", time_of_day: "night", weather: "aurora",
    mood: "radial-gradient(140% 70% at 50% 0%, rgb(80 255 200 / 0.28), rgb(10 30 70 / 0.35))", swatch: "linear-gradient(135deg,#5effc8,#0a1e46)" },
};
