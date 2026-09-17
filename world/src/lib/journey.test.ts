import { describe, expect, it, beforeEach } from "vitest";
import {
  greetingLine,
  loadJourney,
  missionFor,
  recordLessonFinish,
  resetJourneyForTests,
  saveJourney,
  syncProgressFromServer,
  type JourneyState,
} from "./journey";

describe("journey", () => {
  beforeEach(() => {
    resetJourneyForTests();
  });

  it("starts empty then remembers name and first entry", () => {
    expect(loadJourney().name).toBe("");
    saveJourney({ name: "Мира" });
    const j = loadJourney();
    expect(j.name).toBe("Мира");
    expect(j.firstEnteredAt).toBeTruthy();
  });

  it("greets first session and return streak", () => {
    expect(greetingLine("Мира", { isFirstSession: true, streak: 0 })).toContain("Мира");
    expect(greetingLine("Мира", { isFirstSession: false, streak: 3 })).toMatch(/3|три|день/i);
  });

  it("picks practice mission when words are due", () => {
    expect(missionFor({ due: 4, nextLessonId: "family-L1" })).toEqual({
      kind: "practice",
      href: "/learn/practice",
      title: "Повторить слова",
      hint: "Foxy отложил 4 слова на сегодня",
    });
  });

  it("sends claimable dailies to the quest gazebo first", () => {
    expect(missionFor({ due: 4, nextLessonId: "family-L1", claimable: 1 })).toEqual({
      kind: "castle",
      href: "/world?pulse=quests",
      title: "Награда дня готова",
      hint: "Забери поручение в беседке — XP уже ждёт",
    });
  });

  it("picks next lesson when nothing is due", () => {
    expect(missionFor({ due: 0, nextLessonId: "family-L2" }).href).toBe("/learn/family-L2");
  });

  it("calls it the first lesson until one is finished", () => {
    expect(missionFor({ due: 0, nextLessonId: "family-L1", lessonsFinished: 0 }).title).toBe("Первый урок");
    expect(missionFor({ due: 0, nextLessonId: "family-L2", lessonsFinished: 1 }).title).toBe("Продолжить урок");
  });

  it("records finish and suggests a castle building", () => {
    saveJourney({ name: "Мира" });
    const j = recordLessonFinish({
      practice: false,
      itemsGranted: true,
      dueAfter: 0,
    });
    expect(j.lessonsFinished).toBe(1);
    expect(j.lastRewardBuilding).toBe("stickers");
    expect(j.lastFinishAt).toBeTruthy();
  });

  it("suggests yard after practice finish", () => {
    const j = recordLessonFinish({ practice: true, itemsGranted: false, dueAfter: 0 });
    expect(j.lastRewardBuilding).toBe("yard");
  });

  it("suggests lexicon when no sticker drop", () => {
    saveJourney({ name: "Мира", lessonsFinished: 1 });
    const j = recordLessonFinish({ practice: false, itemsGranted: false, dueAfter: 0 });
    expect(j.lastRewardBuilding).toBe("lexicon");
  });

  it("suggests school on the first lesson triumph", () => {
    saveJourney({ name: "Мира" });
    const j = recordLessonFinish({ practice: false, itemsGranted: false, dueAfter: 0 });
    expect(j.lastRewardBuilding).toBe("school");
  });

  it("suggests nest on level up", () => {
    saveJourney({ name: "Мира", lessonsFinished: 2, lastKnownLevel: 1 });
    const j = recordLessonFinish({
      practice: false,
      itemsGranted: false,
      dueAfter: 0,
      level: 2,
    });
    expect(j.lastRewardBuilding).toBe("nest");
    expect(j.lastKnownLevel).toBe(2);
  });

  it("suggests glory every third lesson without other rewards", () => {
    saveJourney({ name: "Мира", lessonsFinished: 2, lastKnownLevel: 1 });
    const j = recordLessonFinish({ practice: false, itemsGranted: false, dueAfter: 0, level: 1 });
    expect(j.lastRewardBuilding).toBe("glory");
  });

  it("exports a stable empty shape", () => {
    const empty: JourneyState = loadJourney();
    expect(empty.seenCastleIntro).toBe(false);
    expect(empty.lessonsFinished).toBe(0);
  });

  it("syncs lessonsFinished from server stars without shrinking", () => {
    saveJourney({ name: "Мира", lessonsFinished: 2 });
    const up = syncProgressFromServer({ lessonsStarred: 5, name: "Мира", level: 2 });
    expect(up.lessonsFinished).toBe(5);
    expect(up.lastKnownLevel).toBe(2);
    const keep = syncProgressFromServer({ lessonsStarred: 1 });
    expect(keep.lessonsFinished).toBe(5);
  });
});
