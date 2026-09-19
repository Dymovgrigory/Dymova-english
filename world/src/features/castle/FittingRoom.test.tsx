import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { CastleItem, CastleView, DecorItem } from "@/lib/v2/castle";

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

import { needsSlotPicker, slotOptions } from "./decorPlacement";
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

function sceneItem(over: Partial<CastleItem> = {}): CastleItem {
  return {
    id: "scene-garland",
    kind: "scene",
    title_ru: "Гирлянды",
    value: "garland",
    price: 120,
    purchasable: true,
    owned: false,
    unlocked: true,
    requires_track: null,
    requires_level: 0,
    anchor: null,
    ...over,
  };
}

function viewWith(item: CastleItem, placed: boolean): CastleView {
  return {
    appearance: { season: null, time_of_day: null, weather: null, banner_color: "gold", banner_emblem: "fox", scene_set: null },
    catalog: [item],
    owned: item.owned ? [item.id] : [],
    decor:
      item.owned && item.kind === "decor"
        ? [{ item_id: item.id, anchor: item.anchor ?? "gate", title_ru: item.title_ru, active: placed, slot: null }]
        : [],
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

  it("дефолтный слот занят — показывается выбор места, сервер не трогаем", () => {
    const lantern = decorItem({ owned: true });
    const pots = decorItem({ id: "decor-gate-pots", title_ru: "Цветочные кашпо", value: "decor-gate-pots", owned: true });
    const view = viewWith(lantern, false);
    view.catalog.push(pots);
    view.decor.push({ item_id: pots.id, anchor: "gate", title_ru: pots.title_ru, active: true, slot: "gate-left" });
    openDecor(view);

    fireEvent.click(screen.getByRole("button", { name: /Фонарь у ворот/ }));

    expect(screen.getByRole("dialog", { name: /Куда поставить/ })).toBeTruthy();
    expect(screen.getByText(/здесь стоит «Цветочные кашпо»/)).toBeTruthy();
    expect(apply).not.toHaveBeenCalled();
  });

  it("выбор свободного слота — decor_place на сервер", async () => {
    const lantern = decorItem({ owned: true });
    const pots = decorItem({ id: "decor-gate-pots", title_ru: "Цветочные кашпо", value: "decor-gate-pots", owned: true });
    const view = viewWith(lantern, false);
    view.catalog.push(pots);
    view.decor.push({ item_id: pots.id, anchor: "gate", title_ru: pots.title_ru, active: true, slot: "gate-left" });
    apply.mockResolvedValue(view);
    openDecor(view);

    fireEvent.click(screen.getByRole("button", { name: /Фонарь у ворот/ }));
    fireEvent.click(screen.getByRole("button", { name: /Справа у ворот/ }));

    await waitFor(() =>
      expect(apply).toHaveBeenCalledWith({ decor_place: [{ item_id: "decor-gate-lantern", slot: "gate-right" }] }),
    );
  });

  it("тап по занятому слоту — замена: occupant уходит в decor_off, предмет в decor_place", async () => {
    const lantern = decorItem({ owned: true });
    const pots = decorItem({ id: "decor-gate-pots", title_ru: "Цветочные кашпо", value: "decor-gate-pots", owned: true });
    const view = viewWith(lantern, false);
    view.catalog.push(pots);
    view.decor.push({ item_id: pots.id, anchor: "gate", title_ru: pots.title_ru, active: true, slot: "gate-left" });
    apply.mockResolvedValue(view);
    openDecor(view);

    fireEvent.click(screen.getByRole("button", { name: /Фонарь у ворот/ }));
    fireEvent.click(screen.getByRole("button", { name: /Слева у ворот/ }));

    await waitFor(() =>
      expect(apply).toHaveBeenCalledWith({
        decor_off: ["decor-gate-pots"],
        decor_place: [{ item_id: "decor-gate-lantern", slot: "gate-left" }],
      }),
    );
  });

  it("сервер ответил slot_occupied — открывается выбор места", async () => {
    const item = decorItem({ owned: true });
    const { ApiError } = await import("@/lib/api");
    apply.mockRejectedValue(new ApiError(409, "slot_occupied"));
    openDecor(viewWith(item, false));

    fireEvent.click(screen.getByRole("button", { name: /Фонарь у ворот/ }));

    await waitFor(() => expect(screen.getByRole("dialog", { name: /Куда поставить/ })).toBeTruthy());
  });
});

describe("FittingRoom: праздничные наборы", () => {
  beforeEach(() => {
    apply.mockReset();
    buy.mockReset();
  });

  function openScenes(view: CastleView) {
    render(<FittingRoom view={view} onChange={() => undefined} onClose={() => undefined} />);
    fireEvent.click(screen.getByRole("tab", { name: "Праздники" }));
  }

  it("купленный набор применяется (scene_set), повторный тап снимает (scene_set null)", async () => {
    const item = sceneItem({ owned: true });
    const view = viewWith(item, false);
    apply.mockImplementation(async (fields: { scene_set?: string | null }) => ({
      ...view,
      appearance: { ...view.appearance, scene_set: fields.scene_set ?? null },
    }));
    openScenes(view);

    fireEvent.click(screen.getByRole("button", { name: /Гирлянды/ }));
    await waitFor(() => expect(apply).toHaveBeenCalledWith({ scene_set: "garland" }));

    fireEvent.click(screen.getByRole("button", { name: /Гирлянды/ }));
    await waitFor(() => expect(apply).toHaveBeenCalledWith({ scene_set: null }));
  });

  it("применённый набор подсвечен в ленте", async () => {
    const item = sceneItem({ owned: true });
    const view = viewWith(item, false);
    view.appearance.scene_set = "garland";
    openScenes(view);

    expect(screen.getByText(/праздник на замке/)).toBeTruthy();
  });

  it("некупленный набор — только локальное превью, сервер не трогаем", () => {
    const item = sceneItem();
    openScenes(viewWith(item, false));

    fireEvent.click(screen.getByRole("button", { name: /Гирлянды/ }));
    expect(screen.getByText(/на сцене · примерка/)).toBeTruthy();
    expect(apply).not.toHaveBeenCalled();
  });

  it("покупка набора сразу применяет его на замке", async () => {
    const item = sceneItem();
    const view = viewWith(item, false);
    buy.mockResolvedValue({ ...view, owned: [item.id], catalog: [{ ...item, owned: true }] });
    apply.mockResolvedValue({
      ...view,
      owned: [item.id],
      catalog: [{ ...item, owned: true }],
      appearance: { ...view.appearance, scene_set: "garland" },
    });
    openScenes(view);

    fireEvent.click(screen.getByRole("button", { name: /Купить · 120/ }));

    await waitFor(() => expect(buy).toHaveBeenCalledWith("scene-garland"));
    await waitFor(() => expect(apply).toHaveBeenCalledWith({ scene_set: "garland" }));
  });
});

describe("decorPlacement", () => {
  const standing = (item_id: string, slot: string): DecorItem => ({
    item_id,
    anchor: "gate",
    title_ru: item_id,
    active: true,
    slot,
  });

  it("needsSlotPicker: дефолтный слот занят другим — нужен выбор", () => {
    const lantern = decorItem({ owned: true });
    expect(needsSlotPicker(lantern, [])).toBe(false);
    expect(needsSlotPicker(lantern, [standing("decor-gate-pots", "gate-left")])).toBe(true);
    expect(needsSlotPicker(lantern, [standing("decor-gate-pots", "gate-right")])).toBe(false);
    // Свой же предмет в дефолтном слоте — не помеха
    expect(needsSlotPicker(lantern, [standing("decor-gate-lantern", "gate-left")])).toBe(false);
  });

  it("slotOptions: свободные слоты и occupant'ы по именам", () => {
    const options = slotOptions("gate", [standing("decor-gate-pots", "gate-far-left")]);
    expect(options).toHaveLength(4);
    expect(options.find((o) => o.id === "gate-far-left")?.occupant?.item_id).toBe("decor-gate-pots");
    expect(options.find((o) => o.id === "gate-left")?.occupant).toBeNull();
  });
});
