import type { BuildingId } from "@/castle/buildings";

const KEY = "world.journey.v1";

export type JourneyState = {
  name: string;
  firstEnteredAt: string | null;
  lessonsFinished: number;
  lastFinishAt: string | null;
  lastRewardBuilding: BuildingId | null;
  seenCastleIntro: boolean;
  lastKnownLevel: number;
};

export type Mission = {
  kind: "lesson" | "practice" | "castle";
  href: string;
  title: string;
  hint: string;
};

const EMPTY: JourneyState = {
  name: "",
  firstEnteredAt: null,
  lessonsFinished: 0,
  lastFinishAt: null,
  lastRewardBuilding: null,
  seenCastleIntro: false,
  lastKnownLevel: 0,
};

/** In-memory mirror so tests / SSR share state within a process. */
let memory: JourneyState = { ...EMPTY };

function canUseStorage() {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

export function loadJourney(): JourneyState {
  if (canUseStorage()) {
    try {
      const raw = window.localStorage.getItem(KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as Partial<JourneyState>;
        memory = {
          ...EMPTY,
          ...parsed,
          name: typeof parsed.name === "string" ? parsed.name : "",
          lessonsFinished: Number(parsed.lessonsFinished) || 0,
          lastKnownLevel: Number(parsed.lastKnownLevel) || 0,
        };
        return { ...memory };
      }
    } catch {
      /* private mode */
    }
  }
  return { ...memory };
}

export function saveJourney(patch: Partial<JourneyState>): JourneyState {
  const prev = loadJourney();
  const next: JourneyState = {
    ...prev,
    ...patch,
    name: (patch.name ?? prev.name).trim(),
  };
  if (!next.firstEnteredAt && next.name) {
    next.firstEnteredAt = new Date().toISOString();
  }
  memory = next;
  if (canUseStorage()) {
    try {
      window.localStorage.setItem(KEY, JSON.stringify(next));
      if (next.name) window.localStorage.setItem("world.name", next.name);
    } catch {
      /* private mode */
    }
  }
  return { ...next };
}

export function resetJourneyForTests() {
  memory = { ...EMPTY };
  if (canUseStorage()) {
    try {
      window.localStorage.removeItem(KEY);
    } catch {
      /* ignore */
    }
  }
}

export function isFirstSession(j: JourneyState = loadJourney()): boolean {
  return j.lessonsFinished === 0;
}

export function greetingLine(
  name: string,
  opts: { isFirstSession: boolean; streak: number },
): string {
  const who = name.trim() || "друг";
  if (opts.isFirstSession) {
    return `${who}, я Foxy. Сегодня скажем первые слова вслух — и замок оживёт.`;
  }
  if (opts.streak >= 2) {
    return `${who}, день ${opts.streak} подряд! Foxy уже ждёт у доски.`;
  }
  return `${who}, снова здесь — продолжим путь.`;
}

export function missionFor(input: { due: number; nextLessonId: string | null; lessonsFinished?: number }): Mission {
  if (input.due > 0) {
    return {
      kind: "practice",
      href: "/learn/practice",
      title: "Повторить слова",
      hint: `Foxy отложил ${input.due} ${pluralWords(input.due)} на сегодня`,
    };
  }
  const id = input.nextLessonId || "family-L1";
  return {
    kind: "lesson",
    href: `/learn/${id}`,
    title: input.lessonsFinished === 0 && id === "family-L1" ? "Первый урок" : "Продолжить урок",
    hint: "Скажи слова вслух — и получишь награду в замке",
  };
}

function pluralWords(n: number): string {
  const n10 = n % 10;
  const n100 = n % 100;
  if (n10 === 1 && n100 !== 11) return "слово";
  if (n10 >= 2 && n10 <= 4 && (n100 < 10 || n100 >= 20)) return "слова";
  return "слов";
}

function pickRewardBuilding(
  input: { practice: boolean; itemsGranted: boolean; dueAfter: number; streakDays?: number },
  opts: { firstTriumph: boolean; leveledUp: boolean; nextCount: number },
): BuildingId {
  if (input.practice) return "yard";
  if (input.itemsGranted) return "stickers";
  if (opts.firstTriumph) return "school";
  if (opts.leveledUp) return "nest";
  if ((input.streakDays ?? 0) >= 3 && opts.nextCount % 2 === 0) return "nest";
  if (input.dueAfter > 0) return "yard";
  if (opts.nextCount % 3 === 0) return "glory";
  return "lexicon";
}

export function recordLessonFinish(input: {
  practice: boolean;
  itemsGranted: boolean;
  dueAfter: number;
  level?: number;
  streakDays?: number;
}): JourneyState {
  const prev = loadJourney();
  const nextCount = prev.lessonsFinished + 1;
  const level = input.level ?? prev.lastKnownLevel;
  const leveledUp = Boolean(input.level != null && input.level > prev.lastKnownLevel && prev.lastKnownLevel > 0);
  const firstTriumph = prev.lessonsFinished === 0 && !input.practice;

  return saveJourney({
    lessonsFinished: nextCount,
    lastFinishAt: new Date().toISOString(),
    lastRewardBuilding: pickRewardBuilding(input, { firstTriumph, leveledUp, nextCount }),
    lastKnownLevel: level,
  });
}

/** Soft copy when castle opens before the first spoken lesson. */
export function castleNudgeLine(j: JourneyState = loadJourney()): string | null {
  if (j.lessonsFinished > 0) return null;
  return "Сначала скажи слово в уроке — потом замок ответит наградой.";
}

export function markCastleIntroSeen(): JourneyState {
  return saveJourney({ seenCastleIntro: true });
}
