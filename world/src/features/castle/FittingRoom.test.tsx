import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { CastleItem, CastleView } from "@/lib/v2/castle";

const { apply, buy } = vi.hoisted(() => ({ apply: vi.fn(), buy: vi.fn() }));

vi.mock("@/lib/v2/castle", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/v2/castle")>();
  return { ...original, castleApi: { ...original.castleApi, apply, buy } };
});

vi.mock("@/features/castle/CastleStage", () => ({
  CastleStage: (props: { appearance: { time_of_day: string | null } }) => (
    <div data-testid="stage">{JSON.stringify(props.appearance)}</div>
  ),
}));

import { FittingRoom } from "./FittingRoom";

function timeItem(over: Partial<CastleItem> = {}): CastleItem {
  return {
    id: "time-night",
    kind: "time",
    title_ru: "Ночь",
    value: "night",
    price: 40,
    purchasable: true,
    owned: false,
    unlocked: true,
    requires_track: null,
    requires_level: 0,
    anchor: null,
    ...over,
  };
}

function decorItem(over: Partial<CastleItem> = {}): CastleItem {
  return {
    id: "decor-gate-lantern",
    kind: "decor",
    title_ru: "Фонарь у ворот",
    value: "decor-gate-lantern",
    price: 60,
    purchasable: true,
    owned: false,
    unlocked: true,
    requires_track: null,
    requires_level: 0,
    anchor: "gate",
    ...over,
  };
}

function viewWith(...items: CastleItem[]): CastleView {
  return {
    appearance: { season: null, time_of_day: null, weather: null, banner_color: "gold", banner_emblem: "fox", scene_set: null },
    catalog: items,
    owned: items.filter((i) => i.owned).map((i) => i.id),
    decor: [],
    titles: [],
    coins: 0,
  };
}

describe("FittingRoom: облик без украшений и праздников", () => {
  beforeEach(() => {
    apply.mockReset();
    buy.mockReset();
  });

  it("в ленте нет вкладок «Украшения» и «Праздники», предметы декора не показываются", () => {
    render(<FittingRoom view={viewWith(timeItem(), decorItem())} onChange={() => undefined} onClose={() => undefined} />);

    expect(screen.queryByRole("tab", { name: "Украшения" })).toBeNull();
    expect(screen.queryByRole("tab", { name: "Праздники" })).toBeNull();
    expect(screen.queryByText("Фонарь у ворот")).toBeNull();
  });

  it("примерка времени суток — локальная, сервер не трогаем", () => {
    render(<FittingRoom view={viewWith(timeItem())} onChange={() => undefined} onClose={() => undefined} />);

    fireEvent.click(screen.getByRole("tab", { name: "Время суток" }));
    fireEvent.click(screen.getByRole("button", { name: "Ночь" }));

    expect(screen.getByTestId("stage").textContent).toContain('"time_of_day":"night"');
    expect(apply).not.toHaveBeenCalled();
    expect(buy).not.toHaveBeenCalled();
  });

  it("покупка применяет облик на сервере сразу", async () => {
    const item = timeItem();
    const view = viewWith(item);
    buy.mockResolvedValue({ ...view, owned: [item.id], catalog: [{ ...item, owned: true }] });
    apply.mockResolvedValue({
      ...view,
      owned: [item.id],
      catalog: [{ ...item, owned: true }],
      appearance: { ...view.appearance, time_of_day: "night" },
    });
    render(<FittingRoom view={view} onChange={() => undefined} onClose={() => undefined} />);

    fireEvent.click(screen.getByRole("tab", { name: "Время суток" }));
    fireEvent.click(screen.getByRole("button", { name: /Купить · 40/ }));

    await waitFor(() => expect(buy).toHaveBeenCalledWith("time-night"));
    await waitFor(() => expect(apply).toHaveBeenCalledWith({ time_of_day: "night" }));
  });
});
