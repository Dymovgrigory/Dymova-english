"""Контент Spotlight: загрузка, индекс курса, инварианты."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from app.learning import content
from app.learning.errors import NotFound
from tests.conftest import FIXTURE_CONTENT


def _copy_fixture(tmp_path: Path) -> Path:
    target = tmp_path / "spotlight"
    shutil.copytree(FIXTURE_CONTENT, target)
    return target


def _edit(path: Path, fn) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    fn(data)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _errors(directory: Path) -> str:
    with pytest.raises(content.ContentError) as exc:
        content.load_course(directory)
    return str(exc.value)


def test_fixture_course_is_valid(learn_course):
    assert content.validate(learn_course) == []
    assert [b.id for b in learn_course.books] == ["sp1", "sp3"]
    assert [m.id for m in learn_course.modules] == ["sp1.m1", "sp1.m2", "sp3.m1"]


def test_nodes_in_book_order(learn_course):
    ids = [n.id for _, n in learn_course.nodes_of("sp1")]
    assert ids[:3] == ["sp1.m1.n1", "sp1.m1.n2", "sp1.m1.n3"]
    assert ids[-1] == "sp1.m2.n5"


def test_lookup_helpers(learn_course):
    module, atom = learn_course.atom("sp3.m1.g-this.2")
    assert module.id == "sp3.m1" and atom.answer == 1
    module, node = learn_course.node("sp1.m1.n4")
    assert node.kind == "chest"
    with pytest.raises(NotFound):
        learn_course.node("sp9.m1.n1")


def test_known_graphemes_grow_along_the_path(learn_course):
    assert learn_course.known_graphemes("sp1.m1.n1") == []
    assert learn_course.known_graphemes("sp1.m1.n3") == ["a", "t", "c", "d", "m"]
    assert learn_course.known_graphemes("sp1.m2.n2")[-5:] == ["o", "g", "u", "n", "s"]


def test_word_pool_is_same_book_up_to_module(learn_course):
    pool = [w.en for w in learn_course.word_pool("sp1.m2")]
    assert pool[:4] == ["ball", "car", "doll", "teddy"]
    assert "cat" in pool
    assert "school" not in pool
    assert [w.en for w in learn_course.word_pool("sp3.m1")][0] == "school"
    assert "cat" not in [w.en for w in learn_course.word_pool("sp3.m1")]


def test_trick_words(learn_course):
    assert learn_course.trick_words("sp1.m2") == {"hello"}


def test_validate_catches_duplicate_ids(tmp_path):
    root = _copy_fixture(tmp_path)
    _edit(root / "sp1" / "m2.json", lambda d: d["words"][0].update(id="sp1.m1.cat"))
    assert "duplicate id sp1.m1.cat" in _errors(root)


def test_validate_catches_unknown_word_in_node(tmp_path):
    root = _copy_fixture(tmp_path)
    _edit(root / "sp1" / "m1.json", lambda d: d["nodes"][0]["word_ids"].append("sp1.m1.zebra"))
    assert "unknown word sp1.m1.zebra" in _errors(root)


def test_validate_catches_untaught_phrase_word(tmp_path):
    root = _copy_fixture(tmp_path)
    _edit(root / "sp1" / "m1.json", lambda d: d["phrases"][0].update(en="Hello, Granny!"))
    assert "'granny' not taught yet" in _errors(root)


def test_validate_requires_module_test_last(tmp_path):
    root = _copy_fixture(tmp_path)
    _edit(root / "sp1" / "m1.json", lambda d: d["nodes"].reverse())
    assert "module_test must be the single last node" in _errors(root)


def test_validate_requires_phonics_in_starter(tmp_path):
    root = _copy_fixture(tmp_path)

    def drop_phonics(d):
        d["nodes"] = [n for n in d["nodes"] if n["kind"] != "phonics"]

    _edit(root / "sp1" / "m2.json", drop_phonics)
    assert "sp1.m2: starter module needs a phonics node" in _errors(root)


def test_validate_requires_word_in_some_words_node(tmp_path):
    root = _copy_fixture(tmp_path)
    _edit(root / "sp1" / "m2.json", lambda d: d["nodes"][0]["word_ids"].pop())
    assert "sp1.m2.teddy: not in any words node" in _errors(root)


def test_validate_requires_two_phrases_per_grammar(tmp_path):
    root = _copy_fixture(tmp_path)

    def drop(d):
        for p in d["phrases"][1:]:
            p["grammar_id"] = None

    _edit(root / "sp3" / "m1.json", drop)
    assert "grammar needs >=2 phrases" in _errors(root)


def test_real_content_dir_loads():
    course = content.load_course(content.DEFAULT_DIR)
    assert [b.id for b in course.books] == ["sp1", "sp2", "sp3", "sp4"]


def test_real_course_builds_every_session():
    """Каждый узел реального курса собирается в урок, соблюдая раскладку."""
    from app.learning import builder
    from tests.test_learning_builder import _assert_layout

    course = content.load_course(content.DEFAULT_DIR)
    for book in course.books:
        for _, node in course.nodes_of(book.id):
            if node.kind == "chest":
                continue
            for seed in range(6):
                plan = builder.build_session(course, node.id, player_id=None, seed=seed, allow_speak=True)
                graded = [c for c in plan.challenges if c.graded]
                if node.kind == "reading":  # текст + 4–5 вопросов по контракту
                    assert 4 <= len(graded) <= 5, (node.id, seed, len(graded))
                else:
                    assert len(graded) >= 8, (node.id, seed, len(graded))
                _assert_layout(plan)


@pytest.mark.parametrize(
    "token,known",
    [
        ("books", "book"), ("tomatoes", "tomato"), ("cities", "city"), ("playing", "play"),
        ("skating", "skate"), ("running", "run"), ("laughed", "laugh"), ("liked", "like"),
        ("studied", "study"), ("bigger", "big"), ("taller", "tall"), ("strongest", "strong"),
        ("mum's", "mum"), ("prettiest", "pretty"),
    ],
)
def test_word_forms_count_as_taught(token, known):
    assert content.is_taught(token, {known})


def test_unrelated_word_is_not_taught():
    assert not content.is_taught("granny", {"grandma"})
