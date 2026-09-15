"""Экспорт словаря сайта в данные World и сборка вопросов челленджа."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "export_world_vocabulary.py"


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    out = tmp_path_factory.mktemp("vocab") / "vocabulary.json"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--out", str(out)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(out.read_text(encoding="utf-8"))


def test_export_has_all_sixteen_themes(exported):
    ids = [t["id"] for t in exported["themes"]]
    assert len(ids) == 16
    assert "zhivotnye" in ids and "vremya-i-chisla" in ids and "prazdniki" in ids
    assert len(set(ids)) == 16


def test_export_word_shape_and_volume(exported):
    total = sum(len(t["words"]) for t in exported["themes"])
    assert total >= 400
    animals = next(t for t in exported["themes"] if t["id"] == "zhivotnye")
    assert animals["title_ru"] == "Животные"
    cat = next(w for w in animals["words"] if w["en"] == "cat")
    assert cat == {
        "en": "cat", "ipa": "[kæt]", "ru": "кошка",
        "example_en": "The cat sleeps on the sofa.",
        "example_ru": "Кошка спит на диване.",
    }


def test_every_theme_has_enough_words_for_a_question(exported):
    for theme in exported["themes"]:
        assert len(theme["words"]) >= 10, theme["id"]


from app.world import vocabulary


def test_build_questions_shape():
    questions = vocabulary.build_questions("zhivotnye", count=5, seed=42)
    assert len(questions) == 5
    for q in questions:
        assert len(q["options"]) == 4
        assert len(set(q["options"])) == 4
        assert 0 <= q["correct_index"] < 4
        assert q["en"] and q["ipa"]


def test_build_questions_correct_option_is_the_translation():
    themes = vocabulary.load_themes()
    by_en = {w["en"]: w["ru"] for w in themes["zhivotnye"]["words"]}
    for q in vocabulary.build_questions("zhivotnye", count=5, seed=7):
        assert q["options"][q["correct_index"]] == by_en[q["en"]]


def test_build_questions_deterministic_with_seed():
    a = vocabulary.build_questions("eda", count=5, seed=1)
    b = vocabulary.build_questions("eda", count=5, seed=1)
    c = vocabulary.build_questions("eda", count=5, seed=2)
    assert a == b
    assert a != c


def test_build_questions_unknown_theme():
    with pytest.raises(vocabulary.ThemeNotFound):
        vocabulary.build_questions("dragons")
