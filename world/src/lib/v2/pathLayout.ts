/** Раскладка пути: узлы змейкой и их подписи. */

import type { NodeKind } from "./types";

/** Горизонтальное смещение узла: плавная синусоида, полный период — 8 узлов. */
export function nodeOffset(position: number, amplitude: number): number {
  return Math.round(Math.sin((position * Math.PI) / 4) * amplitude) || 0;
}

export const NODE_LABELS: Record<NodeKind, string> = {
  words: "Слова",
  phonics: "Читаем",
  grammar: "Правило",
  chest: "Сундук",
  review: "Повторение",
  module_test: "Контрольная",
};
