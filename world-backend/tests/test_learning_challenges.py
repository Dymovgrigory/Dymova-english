"""Типы заданий: payload для ученика, эталон и проверка."""
import random

import pytest

from app.learning import challenges
from app.learning.errors import BadAnswer


def _word(course, atom_id):
    return course.atom(atom_id)[1]


def test_public_view_hides_solution(learn_course):
    cat = _word(learn_course, "sp1.m1.cat")
    ch = challenges.image_pick_word(cat, learn_course.word_pool("sp1.m1"), random.Random(1))
    public = ch.public(4)
    assert public["index"] == 4 and public["type"] == "image_pick_word"
    assert "solution" not in public and "index" not in ch.prompt
    assert public["options"][ch.solution["index"]] == "cat"


def test_roundtrip_dict(learn_course):
    cat = _word(learn_course, "sp1.m1.cat")
    ch = challenges.type_word(cat)
    assert challenges.Challenge.from_dict(ch.to_dict()) == ch


def test_listen_pick_image_needs_images(learn_course):
    pool = learn_course.word_pool("sp1.m1")
    assert challenges.listen_pick_image(_word(learn_course, "sp1.m1.hello"), pool, random.Random(1)) is None
    ch = challenges.listen_pick_image(_word(learn_course, "sp1.m1.dog"), pool, random.Random(1))
    assert len(ch.prompt["options"]) == 3
    assert ch.prompt["options"][ch.solution["index"]]["image"] == "words/dog.webp"
    assert challenges.grade(ch, {"index": ch.solution["index"]}).correct


def test_match_pairs_ids_do_not_leak_answer(learn_course):
    words = [_word(learn_course, i) for i in ("sp1.m1.cat", "sp1.m1.dad", "sp1.m1.mum", "sp1.m1.dog")]
    leaks = 0
    for seed in range(20):
        ch = challenges.match_pairs(words, random.Random(seed), "en_ru")
        pairs = ch.solution["pairs"]
        leaks += all(left[1:] == right[1:] for left, right in pairs)
        assert challenges.grade(ch, {"pairs": list(reversed(pairs))}).correct
        assert not challenges.grade(ch, {"pairs": pairs[:-1]}).correct
    assert leaks < 3
    assert challenges.match_pairs(words[:2], random.Random(1), "en_ru") is None


def test_match_pairs_falls_back_to_text_without_images(learn_course):
    words = [_word(learn_course, i) for i in ("sp1.m1.cat", "sp1.m1.dad", "sp1.m1.hello")]
    ch = challenges.match_pairs(words, random.Random(1), "audio_image")
    assert ch.prompt["mode"] == "en_ru"


def test_build_phrase_tiles_and_grading(learn_course):
    phrase = _word(learn_course, "sp3.m1.p1")
    ch = challenges.build_phrase(phrase, [w.en for w in learn_course.word_pool("sp3.m1")], random.Random(3))
    tiles = ch.prompt["tiles"]
    assert {"This", "is", "my", "bag"} <= set(tiles)
    assert 4 <= len(tiles) <= 6
    assert challenges.grade(ch, {"tiles": ["This", "is", "my", "bag"]}).correct
    assert not challenges.grade(ch, {"tiles": ["is", "This", "my", "bag"]}).correct


def test_spell_tiles_has_no_typo_tolerance(learn_course):
    ch = challenges.spell_tiles(_word(learn_course, "sp3.m1.pencil"), random.Random(2))
    assert all(letter in ch.prompt["tiles"] for letter in "pencil")
    assert challenges.grade(ch, {"tiles": list("pencil")}).correct
    assert not challenges.grade(ch, {"tiles": list("pencl")}).correct


def test_type_word_accepts_typo_and_alternatives(learn_course):
    ch = challenges.type_word(_word(learn_course, "sp3.m1.rubber"))
    assert challenges.grade(ch, {"text": "eraser"}).correct
    verdict = challenges.grade(ch, {"text": "rubbr"})
    assert verdict.correct and verdict.typo


def test_grammar_pick_display(learn_course):
    item = _word(learn_course, "sp3.m1.g-this.2")
    ch = challenges.grammar_pick(item, random.Random(5))
    assert ch.prompt["options"][ch.solution["index"]] == "These"
    assert ch.solution["display"] == "These are my pencils."


def test_reading_tasks_require_known_graphemes(learn_course):
    inventory = learn_course.grapheme_inventory()
    pool = learn_course.word_pool("sp1.m1")
    mum = _word(learn_course, "sp1.m1.mum")
    cat = _word(learn_course, "sp1.m1.cat")
    known = set(learn_course.known_graphemes("sp1.m1.n3"))
    assert challenges.read_word_pick_image(mum, pool, random.Random(1), known, inventory) is None
    ch = challenges.read_word_pick_image(cat, pool, random.Random(1), known, inventory)
    assert ch.prompt["text"] == "cat" and "audio" not in ch.prompt
    blend = challenges.blend_sounds(cat, pool, random.Random(1), known, inventory)
    assert blend.prompt["segments"] == ["c", "a", "t"]


def test_read_phrase_pick_image(learn_course):
    inventory = learn_course.grapheme_inventory() + ["i"]
    phrases = learn_course.phrase_pool("sp1.m2")
    known = set(learn_course.known_graphemes("sp1.m2.n2")) | {"i", "s"}
    tricks = learn_course.trick_words("sp1.m2")
    phrase = _word(learn_course, "sp1.m1.p3")  # "It is a cat."
    ch = challenges.read_phrase_pick_image(phrase, phrases, random.Random(1), known, inventory, tricks)
    assert ch is not None and ch.prompt["text"] == "It is a cat."
    assert challenges.read_phrase_pick_image(
        phrase, phrases, random.Random(1), {"c", "a", "t"}, inventory, tricks
    ) is None


def test_letter_and_sound_tasks(learn_course):
    graphemes = [g for m in learn_course.modules_up_to("sp1.m1") for g in m.graphemes]
    gr_c = learn_course.grapheme("sp1.m1.gr-c")
    ch = challenges.letter_sound(gr_c, graphemes, random.Random(1))
    assert ch.prompt["audio"] == "cup" and ch.prompt["options"][ch.solution["index"]] == "c"
    assert "u" not in ch.prompt["options"] and "p" not in ch.prompt["options"]
    ch = challenges.sound_letter(gr_c, graphemes, random.Random(1))
    assert ch.prompt["options"][ch.solution["index"]] == {"audio": "cup"}


def test_speak_grading_and_malformed_answers(learn_course):
    ch = challenges.speak(_word(learn_course, "sp3.m1.p1"))
    assert challenges.grade(ch, {"transcript": "this is my bag"}).correct
    with pytest.raises(BadAnswer):
        challenges.grade(ch, {})
    with pytest.raises(BadAnswer):
        challenges.grade(challenges.teach_word(_word(learn_course, "sp1.m1.cat")), {})
