"use client";

import { create } from "zustand";
import {
  worldApi,
  type AnswerResult,
  type ChallengeSession,
  type FinishResult,
  type Player,
  type Quest,
} from "@/lib/api";
import { phaseForStep, transition, type GameEvent, type Phase } from "./phases";

export const QUEST_ID = "first-day-at-foxinburg";
export const ACTIVITY_ID = "vocabulary-challenge-1";

type GameState = {
  phase: Phase;
  player: Player | null;
  quest: Quest | null;
  session: ChallengeSession | null;
  answers: Record<number, AnswerResult>;
  finish: FinishResult | null;
  error: string | null;
  boot: (displayName: string) => Promise<void>;
  clickSchool: () => Promise<void>;
  finishDialogue: () => Promise<void>;
  answerQuestion: (index: number, choice: number) => Promise<void>;
  finishChallenge: () => Promise<void>;
  closeReward: () => void;
};

/** Шаг квеста считает сервер; 409 значит «шаг уже пройден» — не ошибка. */
async function advance(action: string, target: string): Promise<void> {
  try {
    await worldApi.advanceStep(QUEST_ID, action, target);
  } catch (err) {
    if (!String(err).includes("409")) throw err;
  }
}

export const useGame = create<GameState>((set, get) => ({
  phase: "boot",
  player: null,
  quest: null,
  session: null,
  answers: {},
  finish: null,
  error: null,

  boot: async (displayName) => {
    try {
      const player = await worldApi.ensurePlayer(displayName);
      const quests = await worldApi.getQuests();
      const quest = quests.find((q) => q.id === QUEST_ID) ?? null;
      if (quest && quest.status === "available") await worldApi.startQuest(QUEST_ID);
      const step = quest?.step ?? 0;
      const status = quest?.status ?? "active";
      set({
        player,
        quest,
        phase: step === 0 ? transition("boot", "loaded") : phaseForStep(step, status),
        error: null,
      });
    } catch (err) {
      set({ error: String(err) });
    }
  },

  clickSchool: async () => {
    if (get().phase !== "explore") return;
    await advance("visit", "school-hub");
    set((s) => ({ phase: transition(s.phase, "school-clicked") }));
  },

  finishDialogue: async () => {
    if (get().phase !== "dialogue") return;
    await advance("talk", "foxi");
    const session = await worldApi.startActivity(ACTIVITY_ID);
    set((s) => ({ session, answers: {}, phase: transition(s.phase, "dialogue-done") }));
  },

  answerQuestion: async (index, choice) => {
    const session = get().session;
    if (!session || get().answers[index]) return;
    const result = await worldApi.answer(session.session_id, index, choice);
    set((s) => ({ answers: { ...s.answers, [index]: result } }));
  },

  finishChallenge: async () => {
    const session = get().session;
    if (!session) return;
    const finish = await worldApi.finishActivity(session.session_id);
    set((s) => ({
      finish,
      player: finish.player,
      phase: transition(s.phase, "challenge-done"),
    }));
  },

  closeReward: () => {
    set((s) => ({ phase: transition(s.phase, "reward-done"), session: null }));
  },
}));

/** Событие для отладки сцены из консоли браузера. */
export function debugEvent(event: GameEvent): void {
  useGame.setState((s) => ({ phase: transition(s.phase, event) }));
}
