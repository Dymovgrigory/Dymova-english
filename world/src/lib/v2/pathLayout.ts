/** Подписи узлов пути — окон башни. */

import type { NodeKind } from "./types";

export const NODE_LABELS: Record<NodeKind, string> = {
  words: "Слова",
  phonics: "Звуки",
  grammar: "Правило",
  reading: "Читаем",
  chest: "Сундук",
  review: "Повторение",
  module_test: "Контрольная",
};
