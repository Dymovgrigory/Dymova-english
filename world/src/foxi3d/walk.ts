/**
 * Чистая математика перехода Фокси от окна к окну.
 * Смещения — в CSS-пикселях: (dx, dy) = позиция старого окна минус нового,
 * то есть стартовый translate контейнера маскота; цель — (0, 0).
 */

export const WALK_MIN_MS = 600;
export const WALK_MAX_MS = 2500;
/** Естественная скорость маскота, px/сек. */
export const WALK_SPEED_PX_PER_SEC = 220;

export interface WalkOffset {
  dx: number;
  dy: number;
}

/** Длительность перехода пропорциональна расстоянию, в рамках [min, max]. */
export function walkDurationMs(offset: WalkOffset): number {
  const dist = Math.hypot(offset.dx, offset.dy);
  if (!Number.isFinite(dist) || dist < 1) return 0;
  return Math.min(WALK_MAX_MS, Math.max(WALK_MIN_MS, Math.round((dist / WALK_SPEED_PX_PER_SEC) * 1000)));
}

/**
 * Куда смотрит лис во время перехода: 1 — вправо, -1 — влево.
 * Движение идёт из точки (dx, dy) в (0, 0), значит вектор движения = (-dx, -dy).
 * При чисто вертикальном переходе смотрит вправо (к следующему окну башни).
 */
export function walkFacing(offset: WalkOffset): 1 | -1 {
  return offset.dx > 0 ? -1 : 1;
}

/** Стартовый CSS-transform контейнера маскота для FLIP-анимации. */
export function walkStartTransform(offset: WalkOffset): string {
  return `translate(${Math.round(offset.dx)}px, ${Math.round(offset.dy)}px)`;
}
