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
