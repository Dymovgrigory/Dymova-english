import { describe, expect, it } from "vitest";
import { fitScene } from "./scene";

const image = { width: 1600, height: 900 };
const castle = { left: 0.25, top: 0.25, width: 0.5, height: 0.5 };

describe("fitScene", () => {
  it("scales the castle to fill the free area and centers it there", () => {
    const view = { width: 1600, height: 900 };
    const free = { left: 0, top: 100, width: 1600, height: 700 };
    const fit = fitScene(view, free, image, castle);
    expect(fit.scale).toBeCloseTo(700 / 450);
    const castleTop = fit.top + castle.top * image.height * fit.scale;
    const castleLeft = fit.left + castle.left * image.width * fit.scale;
    expect(castleTop).toBeCloseTo(100);
    expect(castleLeft + castle.width * image.width * fit.scale / 2).toBeCloseTo(800);
  });

  it("keeps the landscape covering the whole screen when the image is big enough", () => {
    const view = { width: 1440, height: 900 };
    const free = { left: 240, top: 90, width: 1200, height: 720 };
    const fit = fitScene(view, free, image, { left: 0.3, top: 0.3, width: 0.2, height: 0.3 });
    expect(fit.left).toBeLessThanOrEqual(0);
    expect(fit.top).toBeLessThanOrEqual(0);
    expect(fit.left + image.width * fit.scale).toBeGreaterThanOrEqual(1440);
    expect(fit.top + image.height * fit.scale).toBeGreaterThanOrEqual(900);
  });

  it("zooms in slightly so the landscape covers the screen instead of leaving bands", () => {
    const view = { width: 1440, height: 900 };
    const free = { left: 240, top: 150, width: 1200, height: 650 };
    const fit = fitScene(view, free, { width: 1536, height: 864 }, { left: 0.16, top: 0.13, width: 0.7, height: 0.76 });
    expect(fit.top).toBeLessThanOrEqual(0);
    expect(fit.top + 864 * fit.scale).toBeGreaterThanOrEqual(900);
  });

  it("never pushes the castle under the side menu to hide a band", () => {
    const view = { width: 1024, height: 768 };
    const free = { left: 240, top: 180, width: 784, height: 500 };
    const image = { width: 1536, height: 864 };
    const focus = { left: 0.16, top: 0.13, width: 0.7, height: 0.76 };
    const fit = fitScene(view, free, image, focus);
    const castleLeft = fit.left + focus.left * image.width * fit.scale;
    const castleRight = castleLeft + focus.width * image.width * fit.scale;
    expect(castleLeft).toBeGreaterThanOrEqual(240 - 0.01);
    expect(castleRight).toBeLessThanOrEqual(1024.01);
  });

  it("keeps the whole castle visible on a narrow phone even if the image cannot cover", () => {
    const view = { width: 390, height: 844 };
    const free = { left: 0, top: 110, width: 390, height: 520 };
    const fit = fitScene(view, free, image, castle);
    const castleLeft = fit.left + castle.left * image.width * fit.scale;
    const castleWidth = castle.width * image.width * fit.scale;
    expect(castleLeft).toBeGreaterThanOrEqual(-0.01);
    expect(castleLeft + castleWidth).toBeLessThanOrEqual(390.01);
  });
});
