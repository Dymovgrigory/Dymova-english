import { describe, expect, it } from "vitest";

import { initLesson, lessonReducer, progressOf } from "./lessonState";
import type { AnswerReply, Challenge } from "./types";

const teach = (index: number): Challenge => ({ index, type: "teach_word", atom_id: `w${index}`, graded: false });
const pick = (index: number): Challenge => ({ index, type: "image_pick_word", atom_id: `w${index}`, graded: true });

const reply = (patch: Partial<AnswerReply>): AnswerReply => ({
  correct: true,
  typo: false,
  skipped: false,
  solution: "cat",
  requeued: false,
  remaining: 0,
  ...patch,
});

describe("lessonReducer", () => {
  it("starts with the first challenge and no draft", () => {
    const state = initLesson([teach(0), pick(1), pick(2)]);
    expect(state.queue).toEqual([0, 1, 2]);
    expect(state.phase).toBe("answering");
    expect(state.draft).toBeNull();
    expect(progressOf(state)).toBe(0);
  });

  it("walks a draft through checking and feedback", () => {
    let state = initLesson([pick(0), pick(1)]);
    state = lessonReducer(state, { type: "draft", answer: { index: 2 } });
    expect(state.draft).toEqual({ index: 2 });
    state = lessonReducer(state, { type: "checking" });
    expect(state.phase).toBe("checking");
    state = lessonReducer(state, { type: "answered", reply: reply({}) });
    expect(state.phase).toBe("feedback");
    expect(state.feedback?.correct).toBe(true);
    state = lessonReducer(state, { type: "continue" });
    expect(state.queue).toEqual([1]);
    expect(state.phase).toBe("answering");
    expect(state.draft).toBeNull();
    expect(progressOf(state)).toBe(0.5);
  });

  it("moves a wrong answer to the end of the queue", () => {
    let state = initLesson([pick(0), pick(1), pick(2)]);
    state = lessonReducer(state, { type: "answered", reply: reply({ correct: false, requeued: true }) });
    state = lessonReducer(state, { type: "continue" });
    expect(state.queue).toEqual([1, 2, 0]);
    expect(progressOf(state)).toBe(0);
  });

  it("does not count teach cards in progress and finishes when the queue is empty", () => {
    let state = initLesson([teach(0), pick(1)]);
    state = lessonReducer(state, { type: "answered", reply: reply({ solution: null }) });
    state = lessonReducer(state, { type: "continue" });
    expect(progressOf(state)).toBe(0);
    state = lessonReducer(state, { type: "answered", reply: reply({}) });
    state = lessonReducer(state, { type: "continue" });
    expect(state.phase).toBe("done");
    expect(progressOf(state)).toBe(1);
  });

  it("returns to answering when the request fails", () => {
    let state = initLesson([pick(0)]);
    state = lessonReducer(state, { type: "draft", answer: { index: 1 } });
    state = lessonReducer(state, { type: "checking" });
    state = lessonReducer(state, { type: "failed", message: "Нет связи" });
    expect(state.phase).toBe("answering");
    expect(state.error).toBe("Нет связи");
    expect(state.draft).toEqual({ index: 1 });
  });
});
