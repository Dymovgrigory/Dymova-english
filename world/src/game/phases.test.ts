import { describe, expect, it } from "vitest";
import { phaseForStep, transition } from "./phases";

describe("transition", () => {
  it("проводит игрока по полному циклу первого дня", () => {
    expect(transition("boot", "loaded")).toBe("explore");
    expect(transition("explore", "school-clicked")).toBe("dialogue");
    expect(transition("dialogue", "dialogue-done")).toBe("challenge");
    expect(transition("challenge", "challenge-done")).toBe("reward");
    expect(transition("reward", "reward-done")).toBe("explore");
  });

  it("игнорирует события не из текущей фазы", () => {
    expect(transition("boot", "challenge-done")).toBe("boot");
    expect(transition("explore", "reward-done")).toBe("explore");
    expect(transition("challenge", "school-clicked")).toBe("challenge");
  });
});

describe("phaseForStep", () => {
  it("восстанавливает фазу по прогрессу с сервера", () => {
    expect(phaseForStep(0, "active")).toBe("explore");
    expect(phaseForStep(1, "active")).toBe("dialogue");
    expect(phaseForStep(2, "active")).toBe("challenge");
    expect(phaseForStep(3, "completed")).toBe("explore");
  });
});
