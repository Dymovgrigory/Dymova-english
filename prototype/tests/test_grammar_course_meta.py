"""Title и description курса грамматики не должны обещать «пробелы».

Страница /grammar перехватывала запросы «пробелы по английскому в N классе» (GSC, 90 дней):
позиции 23–36 при сотнях показов, тогда как профильные статьи о пробелах по классам
ранжировались выше. Слово «пробелы» в title и description курса перетягивало эти запросы.
Тест фиксирует, что в метаданных курса его нет.
"""
import json
import os

PROTOTYPE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _grammar_meta():
    with open(os.path.join(PROTOTYPE_DIR, "seo_meta_live.json"), encoding="utf-8") as f:
        return json.load(f)["grammar"]


def test_grammar_title_does_not_target_gaps_queries():
    assert "пробел" not in _grammar_meta()["title"].lower()


def test_grammar_description_does_not_target_gaps_queries():
    assert "пробел" not in _grammar_meta()["description"].lower()


def test_grammar_title_stays_within_serp_limit():
    assert len(_grammar_meta()["title"]) <= 65
