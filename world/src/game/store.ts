"use client";

import { create } from "zustand";
import {
  ApiError,
  worldApi,
  type AnswerResult,
  type ChallengeSession,
  type CompleteResult,
  type FinishResult,
  type Player,
  type Quest,
} from "@/lib/api";
import { phaseForStep, transition, type Phase } from "./phases";

export const QUEST_ID = "first-day-at-foxinburg";
export const ACTIVITY_ID = "vocabulary-challenge-1";

type GameState = {
  phase: Phase;
  player: Player | null;
  quest: Quest | null;
  session: ChallengeSession | null;
  answers: Record<number, AnswerResult>;
  finish: FinishResult | null;
  /** Награда за сам квест (60 XP, 30 монет, значок, разблокировки) — отдельно от награды челленджа. */
  questComplete: CompleteResult | null;
  error: string | null;
  /** Идёт сетевой запрос игрового действия — повторные клики игнорируются. */
  busy: boolean;
  boot: (displayName: string) => Promise<void>;
  clickSchool: () => Promise<void>;
  finishDialogue: () => Promise<void>;
  answerQuestion: (index: number, choice: number) => Promise<void>;
  finishChallenge: () => Promise<void>;
  closeReward: () => Promise<void>;
};

/** Шаг квеста считает сервер; 409 значит «шаг уже пройден» — не ошибка. */
async function advance(action: string, target: string): Promise<void> {
  try {
    await worldApi.advanceStep(QUEST_ID, action, target);
  } catch (err) {
    if (!(err instanceof ApiError && err.status === 409)) throw err;
  }
}

export const useGame = create<GameState>((set, get) => ({
  phase: "boot",
  player: null,
  quest: null,
  session: null,
  answers: {},
  finish: null,
  questComplete: null,
  error: null,
  busy: false,

  boot: async (displayName) => {
    if (get().busy) return;
    set({ busy: true });
    try {
      const player = await worldApi.ensurePlayer(displayName);
      const quests = await worldApi.getQuests();
      const quest = quests.find((q) => q.id === QUEST_ID) ?? null;
      if (quest && quest.status === "available") await worldApi.startQuest(QUEST_ID);
      const step = quest?.step ?? 0;
      const status = quest?.status ?? "active";
      const totalSteps = quest?.config.steps.length ?? 0;
      let phase = phaseForStep(step, status, totalSteps);
      let session: ChallengeSession | null = null;
      let error: string | null = null;

      // Восстановились в challenge, но сессии активности у нас ещё нет — без неё
      // в этой фазе нечего рисовать (оверлей, диалог, трекер — всё возвращает null).
      // Поднимаем сессию сами; если не вышло — честно откатываемся в explore, а не
      // оставляем ребёнка на пустом экране без единой кликабельной точки.
      if (phase === "challenge") {
        try {
          session = await worldApi.startActivity(ACTIVITY_ID);
        } catch {
          phase = "explore";
          error = "Не получилось поднять задание. Загляни в школу ещё раз.";
        }
      }

      set({ player, quest, phase, session, error });
    } catch {
      set({ error: "Фоксинбург не отвечает. Проверь соединение и попробуй снова." });
    } finally {
      set({ busy: false });
    }
  },

  clickSchool: async () => {
    if (get().phase !== "explore" || get().busy) return;
    set({ busy: true });
    try {
      await advance("visit", "school-hub");
      set((s) => ({ phase: transition(s.phase, "school-clicked"), error: null }));
    } catch {
      set({ error: "Не получилось войти в школу. Попробуй ещё раз." });
    } finally {
      set({ busy: false });
    }
  },

  finishDialogue: async () => {
    if (get().phase !== "dialogue" || get().busy) return;
    set({ busy: true });
    try {
      await advance("talk", "foxi");
      const session = await worldApi.startActivity(ACTIVITY_ID);
      set((s) => ({
        session,
        answers: {},
        phase: transition(s.phase, "dialogue-done"),
        error: null,
      }));
    } catch {
      set({ error: "Фокси не может начать задание. Попробуй ещё раз." });
    } finally {
      set({ busy: false });
    }
  },

  answerQuestion: async (index, choice) => {
    const session = get().session;
    if (!session || get().answers[index] || get().busy) return;
    set({ busy: true });
    try {
      const result = await worldApi.answer(session.session_id, index, choice);
      set((s) => ({ answers: { ...s.answers, [index]: result }, error: null }));
    } catch {
      set({ error: "Ответ не отправился. Проверь соединение и попробуй снова." });
    } finally {
      set({ busy: false });
    }
  },

  finishChallenge: async () => {
    const session = get().session;
    if (!session || get().busy) return;
    set({ busy: true });
    try {
      const finish = await worldApi.finishActivity(session.session_id);
      let player = finish.player;
      let questComplete: CompleteResult | null = null;

      // Квест сам себя не завершает: finish активности только отмечает шаг пройденным.
      // Награду квеста (60 XP, 30 монет, значок, разблокировка зоны) нужно забрать отдельным вызовом.
      if (finish.quest?.all_steps_done) {
        try {
          questComplete = await worldApi.completeQuest(QUEST_ID);
          player = questComplete.player;
        } catch {
          // Награда челленджа уже начислена и будет показана; награду квеста
          // покажем в следующий раз, когда complete пройдёт успешно — не обманываем
          // экраном, который обещает то, чего сервер не подтвердил.
        }
      }

      set((s) => ({
        finish,
        questComplete,
        player,
        phase: transition(s.phase, "challenge-done"),
        error: null,
      }));
    } catch {
      set({ error: "Не получилось забрать награду. Попробуй ещё раз." });
    } finally {
      set({ busy: false });
    }
  },

  closeReward: async () => {
    set((s) => ({
      phase: transition(s.phase, "reward-done"),
      session: null,
      finish: null,
      questComplete: null,
    }));

    // Перечитываем квест с сервера: без этого HUD и подсветка школы продолжают
    // показывать первый шаг после завершения квеста, и цикл идёт по кругу.
    try {
      const quests = await worldApi.getQuests();
      const quest = quests.find((q) => q.id === QUEST_ID) ?? null;
      set({ quest });
    } catch {
      // Локальное состояние квеста останется прежним до следующей успешной синхронизации.
    }
  },
}));
