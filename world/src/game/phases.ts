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

/**
 * Восстановление фазы по прогрессу квеста с сервера (перезагрузка страницы).
 * totalSteps — число шагов квеста (quest.config.steps.length). Шаг, равный
 * totalSteps или больше, значит «все шаги пройдены» — это explore, а не challenge,
 * независимо от status: сервер может ещё не успеть проставить quest.status="completed"
 * (например, между finish активности и complete квеста), и без этой проверки игрок
 * попадал в challenge без сессии — тупик без единой кликабельной точки.
 */
export function phaseForStep(step: number, status: string, totalSteps: number): Phase {
  if (status === "completed") return "explore";
  if (step >= totalSteps) return "explore";
  if (step <= 0) return "explore";
  if (step === 1) return "dialogue";
  return "challenge";
}
