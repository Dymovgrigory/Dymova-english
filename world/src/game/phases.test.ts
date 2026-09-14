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
  it("восстанавливает фазу по прогрессу с сервера (квест из 3 шагов)", () => {
    expect(phaseForStep(0, "active", 3)).toBe("explore");
    expect(phaseForStep(1, "active", 3)).toBe("dialogue");
    expect(phaseForStep(2, "active", 3)).toBe("challenge");
    expect(phaseForStep(3, "completed", 3)).toBe("explore");
  });

  it("шаг, равный числу шагов квеста, всегда explore — даже пока сервер ещё не проставил completed", () => {
    // Ровно это состояние ловило игрока в тупике: finish активности уже прошёл
    // (step === totalSteps), а quest.status ещё "active", потому что complete
    // квеста — отдельный запрос. phaseForStep не должен в этот момент отдавать
    // challenge, для которого boot ещё не поднял сессию.
    expect(phaseForStep(3, "active", 3)).toBe("explore");
    expect(phaseForStep(2, "active", 2)).toBe("explore");
  });

  it("шаг больше числа шагов квеста тоже не уводит в challenge", () => {
    expect(phaseForStep(4, "active", 3)).toBe("explore");
  });
});
