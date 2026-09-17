import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { SessionResult } from "@/lib/v2/types";

import { FinishScreen } from "./FinishScreen";

const base: SessionResult = {
  node_id: "sp1.m1.n1",
  kind: "words",
  xp: 10,
  coins: 8,
  stars: 0,
  passed: true,
  accuracy: 1,
  mistakes: 0,
  duration_sec: 60,
  streak_days: 1,
  today_xp: 10,
  daily_goal_xp: 20,
  goal_reached: false,
  node_completed: true,
  next_node_id: null,
  player: { xp: 10, coins: 8, level: 1 },
  coins_breakdown: { lesson: 5, perfect: 3 },
  titles_gained: [{ track: "lexicon", level: 1, title_ru: "Собиратель слов", coins: 25 }],
};

describe("FinishScreen", () => {
  it("показывает новое звание", () => {
    render(<FinishScreen result={base} onContinue={() => {}} onRetry={() => {}} />);
    expect(screen.getByText(/Собиратель слов/)).toBeInTheDocument();
    expect(screen.getByText(/\+25/)).toBeInTheDocument();
  });

  it("без нового звания плашки нет", () => {
    render(
      <FinishScreen result={{ ...base, titles_gained: [] }} onContinue={() => {}} onRetry={() => {}} />,
    );
    expect(screen.queryByText("Новое звание")).not.toBeInTheDocument();
  });
});
