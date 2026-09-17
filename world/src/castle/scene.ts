export type Size = { width: number; height: number };
export type Rect = { left: number; top: number; width: number; height: number };

const MAX_COVER_ZOOM = 1.3;

/**
 * Как положить диораму на экран: замок (`castle`, доли картинки) целиком и как можно крупнее
 * вписан в свободную область `free` (между заголовком и лентой), а пейзаж вокруг по возможности
 * закрывает весь экран `view` без пустых полей.
 */
export function fitScene(view: Size, free: Rect, image: Size, castle: Rect): { scale: number; left: number; top: number } {
  const fit = Math.min(free.width / (castle.width * image.width), free.height / (castle.height * image.height));
  const cover = Math.max(view.width / image.width, view.height / image.height);
  const fitsAcross = castle.width * image.width * cover <= free.width;
  // Крупнее вписанного, чтобы пейзаж закрыл экран без полос: флаги башен могут зайти под прозрачный
  // заголовок, но по ширине замок обязан остаться в свободной области (не под боковым меню).
  const scale = cover > fit && cover <= fit * MAX_COVER_ZOOM && fitsAcross ? cover : fit;
  const width = image.width * scale;
  const height = image.height * scale;
  let left = free.left + free.width / 2 - (castle.left + castle.width / 2) * width;
  let top = free.top + free.height / 2 - (castle.top + castle.height / 2) * height;
  // По ширине: закрыть экран, но замок важнее — не под меню. По высоте: пейзаж без полос важнее.
  if (width >= view.width) left = clamp(left, view.width - width, 0);
  left = clamp(left, free.left - castle.left * width, free.left + free.width - (castle.left + castle.width) * width);
  if (height >= view.height) top = clamp(top, view.height - height, 0);
  return { scale, left, top };
}

function clamp(value: number, min: number, max: number): number {
  return min > max ? (min + max) / 2 : Math.min(max, Math.max(min, value));
}
