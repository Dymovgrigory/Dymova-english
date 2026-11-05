// Оформление наборов слов: иконка (lucide) и цвет темы. Без эмодзи.
import type { LucideIcon } from "lucide-react";
import {
  Activity, Apple, Backpack, BookOpenText, Briefcase, Building2, CalendarDays, Car, CloudSun, Gamepad2,
  GraduationCap, Hand, HeartPulse, House, Laptop, Library, MessageCircle, Music, Palette, PawPrint, Plane,
  Rocket, Shirt, ShoppingBag, Smile, Sparkles, Sprout, Trees, Trophy, Type, UserRound, Users, WandSparkles,
} from "lucide-react";

export type TopicLook = { Icon: LucideIcon; color: string; ink: string };

const T: Record<string, TopicLook> = {
  animals: { Icon: PawPrint, color: "#F2994A", ink: "#5A2E06" },
  food: { Icon: Apple, color: "#EB5757", ink: "#5C0F12" },
  family: { Icon: Users, color: "#D85AA8", ink: "#4D0C33" },
  body: { Icon: Hand, color: "#F2C94C", ink: "#4D3A00" },
  clothes: { Icon: Shirt, color: "#2F80ED", ink: "#06244D" },
  home: { Icon: House, color: "#27AE60", ink: "#063D1E" },
  school: { Icon: Backpack, color: "#6C47D9", ink: "#1E0B57" },
  toys: { Icon: Gamepad2, color: "#E0609B", ink: "#4D0B2A" },
  nature: { Icon: Trees, color: "#219653", ink: "#05361A" },
  weather: { Icon: CloudSun, color: "#2D9CDB", ink: "#062F47" },
  transport: { Icon: Car, color: "#E04F3B", ink: "#4A0D04" },
  city: { Icon: Building2, color: "#56647A", ink: "#11161F" },
  jobs: { Icon: Briefcase, color: "#0F9BB0", ink: "#032F36" },
  sport: { Icon: Trophy, color: "#F08A24", ink: "#4D2402" },
  hobbies: { Icon: Music, color: "#B2457A", ink: "#3D0A23" },
  colours: { Icon: Palette, color: "#E8A317", ink: "#4A3000" },
  numbers: { Icon: Type, color: "#3B6FD8", ink: "#0B2257" },
  time: { Icon: CalendarDays, color: "#7B52D3", ink: "#21094F" },
  feelings: { Icon: Smile, color: "#F0883E", ink: "#4D2002" },
  actions: { Icon: Activity, color: "#20A464", ink: "#04361F" },
  describing: { Icon: Sparkles, color: "#9C5BE0", ink: "#2C0C52" },
  health: { Icon: HeartPulse, color: "#E2445C", ink: "#4D0712" },
  travel: { Icon: Plane, color: "#2B8BD6", ink: "#062B47" },
  shopping: { Icon: ShoppingBag, color: "#EE7B30", ink: "#4D2003" },
  technology: { Icon: Laptop, color: "#4A6CF0", ink: "#0B1A57" },
  people: { Icon: UserRound, color: "#D9603F", ink: "#4D1607" },
  space: { Icon: Rocket, color: "#3F3FB8", ink: "#0C0C40" },
  fairy: { Icon: WandSparkles, color: "#A445C9", ink: "#36064A" },
  phrases: { Icon: MessageCircle, color: "#22A876", ink: "#04392A" },
  "little-words": { Icon: Type, color: "#6E7A91", ink: "#141A26" },
  general: { Icon: Library, color: "#4B6584", ink: "#0E1824" },
};

export function topicLook(code: string, topic?: string): TopicLook {
  if (code === "level:pre-a1") return { Icon: Sprout, color: "#F2994A", ink: "#5A2E06" };
  if (code === "level:a1") return { Icon: GraduationCap, color: "#27AE60", ink: "#063D1E" };
  if (code === "level:a2") return { Icon: GraduationCap, color: "#2F80ED", ink: "#06244D" };
  if (code.startsWith("book:")) return { Icon: BookOpenText, color: "#0F9BB0", ink: "#032F36" };
  const t = topic || code.split(":")[1] || "";
  return T[t] ?? { Icon: BookOpenText, color: "#5B4BDB", ink: "#1A1352" };
}
