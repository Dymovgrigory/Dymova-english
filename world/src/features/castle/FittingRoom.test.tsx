import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { CastleItem, CastleView } from "@/lib/v2/castle";

const { apply, buy } = vi.hoisted(() => ({ apply: vi.fn(), buy: vi.fn() }));

vi.mock("@/lib/v2/castle", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/v2/castle")>();
  return { ...original, castleApi: { ...original.castleApi, apply, buy } };
});

vi.mock("@/features/castle/CastleStage", () => ({
  CastleStage: (props: { decor: { item_id: string; active: boolean }[] }) => (
    <div data-testid="stage">{JSON.stringify(props.decor)}</div>
  ),
}));

import { FittingRoom } from "./FittingRoom";

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

function viewWith(item: CastleItem, placed: boolean): CastleView {
  return {
    appearance: { season: null, time_of_day: null, weather: null, banner_color: "gold", banner_emblem: "fox" },
    catalog: [item],
    owned: item.owned ? [item.id] : [],
    decor: item.owned ? [{ item_id: item.id, anchor: "gate", title_ru: item.title_ru, active: placed }] : [],
    titles: [],
    coins: 0,
  };
}

function openDecor(view: CastleView) {
  render(<FittingRoom view={view} onChange={() => undefined} onClose={() => undefined} />);
  fireEvent.click(screen.getByRole("tab", { name: "Украшения" }));
}

describe("FittingRoom: украшения можно снимать и ставить обратно", () => {
  beforeEach(() => {
    apply.mockReset();
    buy.mockReset();
  });

  it("купленный предмет на сцене — клик снимает его (decor_off на сервер)", async () => {
    const item = decorItem({ owned: true });
    apply.mockResolvedValue(viewWith(item, false));
    openDecor(viewWith(item, true));

    const thumb = screen.getByRole("button", { name: /Фонарь у ворот/ });
    expect(screen.getByText(/стоит на замке/)).toBeTruthy();
    fireEvent.click(thumb);

    await waitFor(() => expect(apply).toHaveBeenCalledWith({ decor_off: ["decor-gate-lantern"] }));
  });

  it("купленный снятый предмет — клик ставит обратно (decor_on на сервер)", async () => {
    const item = decorItem({ owned: true });
    apply.mockResolvedValue(viewWith(item, true));
    openDecor(viewWith(item, false));

    expect(screen.getByText(/снято/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Фонарь у ворот/ }));

    await waitFor(() => expect(apply).toHaveBeenCalledWith({ decor_on: ["decor-gate-lantern"] }));
  });

  it("некупленный предмет — примерка локальная: ставится и убирается без сервера", async () => {
    const item = decorItem();
    openDecor(viewWith(item, false));

    const thumb = screen.getByRole("button", { name: /Фонарь у ворот/ });
    fireEvent.click(thumb);
    expect(screen.getByTestId("stage").textContent).toContain('"active":true');

    fireEvent.click(thumb);
    expect(screen.getByTestId("stage").textContent).toContain('"active":false');
    expect(apply).not.toHaveBeenCalled();
  });
});
