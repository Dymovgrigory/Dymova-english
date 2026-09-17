/** Состояние урока на клиенте: очередь заданий, черновик ответа, лист результата. */

import type { Answer, AnswerReply, Challenge } from "./types";

export type LessonPhase = "answering" | "checking" | "feedback" | "done";

export type LessonState = {
  challenges: Challenge[];
  queue: number[];
  solved: number[];
  gradedTotal: number;
  draft: Answer | null;
  phase: LessonPhase;
  feedback: AnswerReply | null;
  error: string | null;
};

export type LessonAction =
  | { type: "draft"; answer: Answer | null }
  | { type: "checking" }
  | { type: "answered"; reply: AnswerReply }
  | { type: "failed"; message: string }
  | { type: "continue" };

export function initLesson(challenges: Challenge[]): LessonState {
  return {
    challenges,
    queue: challenges.map((c) => c.index),
    solved: [],
    gradedTotal: challenges.filter((c) => c.graded).length,
    draft: null,
    phase: challenges.length ? "answering" : "done",
    feedback: null,
    error: null,
  };
}

export function currentChallenge(state: LessonState): Challenge | null {
  const head = state.queue[0];
  return head === undefined ? null : state.challenges[head];
}

export function progressOf(state: LessonState): number {
  return state.gradedTotal ? state.solved.length / state.gradedTotal : 1;
}

export function lessonReducer(state: LessonState, action: LessonAction): LessonState {
  switch (action.type) {
    case "draft":
      return state.phase === "answering" ? { ...state, draft: action.answer, error: null } : state;
    case "checking":
      return { ...state, phase: "checking", error: null };
    case "failed":
      return { ...state, phase: "answering", error: action.message };
    case "answered":
      return { ...state, phase: "feedback", feedback: action.reply };
    case "continue": {
      const [head, ...rest] = state.queue;
      if (head === undefined) return { ...state, phase: "done" };
      const reply = state.feedback;
      const current = state.challenges[head];
      const queue = reply?.requeued ? [...rest, head] : rest;
      const solved = current.graded && reply && !reply.requeued ? [...state.solved, head] : state.solved;
      return {
        ...state,
        queue,
        solved,
        draft: null,
        feedback: null,
        error: null,
        phase: queue.length ? "answering" : "done",
      };
    }
  }
}
