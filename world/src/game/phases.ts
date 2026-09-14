/** Фазы игрового цикла первого дня в Фоксинбурге. */
export type Phase = "boot" | "explore" | "dialogue" | "challenge" | "reward";

export type GameEvent =
  | "loaded"
  | "school-clicked"
  | "dialogue-done"
  | "challenge-done"
  | "reward-done";

const TRANSITIONS: Record<Phase, Partial<Record<GameEvent, Phase>>> = {
  boot: { loaded: "explore" },
  explore: { "school-clicked": "dialogue" },
  dialogue: { "dialogue-done": "challenge" },
  challenge: { "challenge-done": "reward" },
  reward: { "reward-done": "explore" },
};

/** Событие не из текущей фазы игнорируется — фаза не меняется. */
export function transition(phase: Phase, event: GameEvent): Phase {
  return TRANSITIONS[phase][event] ?? phase;
}

/** Восстановление фазы по прогрессу квеста с сервера (перезагрузка страницы). */
export function phaseForStep(step: number, status: string): Phase {
  if (status === "completed") return "explore";
  if (step <= 0) return "explore";
  if (step === 1) return "dialogue";
  return "challenge";
}
