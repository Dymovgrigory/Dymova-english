/** Шильдик навыка на карточке задания (контракт этапа 5, docs/world/reading-contract.md). */

import type { Challenge } from "./types";

export type Skill = "Слушаем" | "Говорим" | "Пишем" | "Читаем" | "Грамматика" | "Звуки" | "Слова";

/** Явные «письменные» типы — до префиксных правил (listen_build — пишем, хотя начинается с listen_). */
const WRITING = new Set<Challenge["type"]>(["spell_tiles", "type_word", "build_phrase", "listen_build"]);
const GRAMMAR = new Set<Challenge["type"]>(["grammar_pick", "teach_rule"]);
const SOUNDS = new Set<Challenge["type"]>(["teach_grapheme", "letter_sound", "sound_letter", "blend_sounds"]);

export function skillFor(type: Challenge["type"]): Skill {
  if (WRITING.has(type)) return "Пишем";
  if (GRAMMAR.has(type)) return "Грамматика";
  if (SOUNDS.has(type)) return "Звуки";
  if (type === "speak") return "Говорим";
  if (type.startsWith("listen_")) return "Слушаем";
  if (type.startsWith("read_") || type === "word_in_context") return "Читаем";
  return "Слова";
}
