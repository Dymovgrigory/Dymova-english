import { describe, expect, it } from "vitest";

import { skillFor } from "./skills";
import type { Challenge } from "./types";

describe("skillFor — шильдики навыков по контракту этапа 5", () => {
  it("listen_* → Слушаем", () => {
    expect(skillFor("listen_pick_image")).toBe("Слушаем");
  });

  it("speak → Говорим", () => {
    expect(skillFor("speak")).toBe("Говорим");
  });

  it("письменные типы → Пишем (listen_build включительно)", () => {
    for (const t of ["spell_tiles", "type_word", "build_phrase", "listen_build"] as Challenge["type"][]) {
      expect(skillFor(t)).toBe("Пишем");
    }
  });

  it("read_* и word_in_context → Читаем", () => {
    for (const t of [
      "read_text",
      "read_text_truefalse",
      "read_text_answer",
      "word_in_context",
      "read_word_pick_image",
      "read_phrase_pick_image",
    ] as Challenge["type"][]) {
      expect(skillFor(t)).toBe("Читаем");
    }
  });

  it("grammar_pick и teach_rule → Грамматика", () => {
    expect(skillFor("grammar_pick")).toBe("Грамматика");
    expect(skillFor("teach_rule")).toBe("Грамматика");
  });

  it("остальные словные → Слова", () => {
    for (const t of [
      "teach_word",
      "teach_grapheme",
      "image_pick_word",
      "blend_sounds",
      "translate_pick",
      "match_pairs",
      "letter_sound",
      "sound_letter",
    ] as Challenge["type"][]) {
      expect(skillFor(t)).toBe("Слова");
    }
  });
});
