import { describe, expect, it } from "vitest";
import { echoPass, echoScore, needsEchoFor, normalizeEcho } from "./echo";

describe("echoScore", () => {
  it("gives 100 for the same word", () => {
    expect(echoScore("Hello!", "hello")).toBe(100);
  });

  it("accepts a close child attempt", () => {
    expect(echoScore("helo", "hello")).toBeGreaterThanOrEqual(55);
    expect(echoPass(echoScore("helo", "hello"))).toBe(true);
  });

  it("rejects a different word", () => {
    expect(echoPass(echoScore("cat", "hello"))).toBe(false);
    expect(echoPass(echoScore("yes", "cat"))).toBe(false);
    expect(echoPass(echoScore("red", "This is a cat."))).toBe(false);
  });

  it("rejects a stub of a longer word (pen ≠ pencil)", () => {
    expect(echoPass(echoScore("Pen", "pencil"))).toBe(false);
    expect(echoPass(echoScore("pen", "This is a pencil."))).toBe(false);
  });

  it("accepts a child spelling of the full word", () => {
    expect(echoPass(echoScore("pensil", "pencil"))).toBe(true);
    expect(echoPass(echoScore("pencil", "pencil"))).toBe(true);
    expect(echoPass(echoScore("cat", "This is a cat."))).toBe(true);
  });

  it("normalizes punctuation", () => {
    expect(normalizeEcho("No, thank you.")).toBe("no thank you");
  });
});

describe("needsEchoFor", () => {
  it("gates every talking card", () => {
    expect(needsEchoFor("word_card")).toBe(true);
    expect(needsEchoFor("phrase_card")).toBe(true);
    expect(needsEchoFor("listen")).toBe(true);
  });

  it("does not gate written drills", () => {
    expect(needsEchoFor("explain")).toBe(false);
    expect(needsEchoFor("type_en")).toBe(false);
    expect(needsEchoFor("match")).toBe(false);
    expect(needsEchoFor("mcq_en_ru")).toBe(false);
    expect(needsEchoFor(undefined)).toBe(false);
  });
});
