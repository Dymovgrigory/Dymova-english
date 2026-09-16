import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const chromePath = join(__dirname, "Chrome.tsx");
const src = readFileSync(chromePath, "utf8");

describe("fantasy Chrome kit", () => {
  it("wires atlas faces for panels, buttons, nav, and dock", () => {
    expect(src).toContain("/world/ui/frames/panel-plaque.png");
    expect(src).toContain("/world/ui/frames/atlas-frames.png");
    expect(src).toContain("/world/ui/frames/atlas-buttons.png");
    expect(src).toContain("/world/ui/frames/quest-plaque.png");
    expect(src).toContain('backgroundSize: "400% 600%"');
  });

  it("exports HUD + chrome icons used by WorldBar / RoomChrome", () => {
    for (const name of ["FantasyHudChip", "FantasyNavChip", "FantasyButton", "ChromeIcon", "BrandIcon"]) {
      expect(src).toContain(`export function ${name}`);
    }
  });
});
