import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { stickerArt, StickerCard } from "./StickerDrawer";

describe("stickerArt", () => {
  it("известный id — webp по конвенции", () => {
    expect(stickerArt("sticker-family")).toBe("/world/ui/stickers/sticker-family.webp");
  });

  it("неизвестный фронту, но валидный id (sticker-{unit} с бэкенда) — путь по конвенции", () => {
    expect(stickerArt("sticker-aiee")).toBe("/world/ui/stickers/sticker-aiee.webp");
  });

  it("опасный id (слэши, точки) — null, никакого path traversal", () => {
    expect(stickerArt("../etc/passwd")).toBeNull();
    expect(stickerArt("sticker/../secret")).toBeNull();
    expect(stickerArt("")).toBeNull();
  });
});

describe("StickerCard", () => {
  it("полученный стикер с битой картинкой (404) показывает emoji, а не сломанный img", () => {
    const { container } = render(
      <StickerCard item={{ id: "sticker-family", title_ru: "Семья", emoji: "👨‍👩‍👧", owned: true }} />,
    );
    const img = container.querySelector("img");
    expect(img).toBeTruthy();
    fireEvent.error(img!);
    expect(screen.getByText("👨‍👩‍👧")).toBeTruthy();
  });

  it("полученный стикер без emoji и без картинки — звезда-заглушка", () => {
    render(<StickerCard item={{ id: "../bad", title_ru: "Тест", owned: true }} />);
    expect(screen.getByText("★")).toBeTruthy();
  });

  it("неполученный стикер — знак вопроса (сюрприз)", () => {
    render(<StickerCard item={{ id: "sticker-family", title_ru: "Семья", owned: false }} />);
    expect(screen.getByText("?")).toBeTruthy();
  });
});
