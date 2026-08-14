"""Падеж имени по месту в предложении.

Из живой переписки: «Это поможет Аделина лучше понять материал», «уровень
английского у Аделина», «детям, как Аделина». Имя разворачивалось всегда в
именительном — и это первое, что выдаёт робота. Здесь проверяется, что
падеж выбирается по предлогу и управляющему слову, а сомнительные случаи
остаются нетронутыми: исказить имя хуже, чем оставить исходную форму.
"""
from __future__ import annotations

import pytest

from app import grammar
from app.morph import NOMINATIVE
from app.pii import PiiVault


@pytest.mark.parametrize(
    "prefix,expected",
    [
        ("уровень английского у ", "род"),
        ("это для ", "род"),
        ("подойдёт ли это ", "дат"),
        ("Это поможет ", "дат"),
        ("Сколько лет ", "дат"),
        ("Запишем ", "вин"),
        ("Расскажите про ", "вин"),
        ("вместе с ", "твор"),
        ("поговорим о ", "пред"),
        ("Детям, как ", NOMINATIVE),
        ("", NOMINATIVE),
        ("Занятия идут по вторникам. ", NOMINATIVE),
    ],
)
def test_case_is_taken_from_the_governing_word(prefix, expected):
    assert grammar.case_for(prefix) == expected


# ------------------------- разворачивание плейсхолдера -------------------------


def _vault() -> PiiVault:
    vault = PiiVault()
    vault.hide("CHILD_NAME", "Аделина")
    return vault


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Это поможет {{CHILD_NAME}} лучше понять", "Это поможет Аделине лучше понять"),
        ("Какой уровень у {{CHILD_NAME}}?", "Какой уровень у Аделины?"),
        ("Запишем {{CHILD_NAME}} на диагностику", "Запишем Аделину на диагностику"),
        ("{{CHILD_NAME}} уже изучала язык?", "Аделина уже изучала язык?"),
        ("Детям, как {{CHILD_NAME}}, нравится", "Детям, как Аделина, нравится"),
    ],
)
def test_placeholder_is_restored_in_the_right_case(text, expected):
    assert _vault().restore(text) == expected


def test_explicit_case_mark_wins_over_context():
    """Пометка модели точнее догадки по соседнему слову."""
    assert _vault().restore("Ждём {{CHILD_NAME:твор}}") == "Ждём Аделиной"


# ------------------------- подстраховка для голого имени -------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Это поможет Аделина понять", "Это поможет Аделине понять"),
        ("уровень английского у Аделина", "уровень английского у Аделины"),
        ("Запишем Аделина на пробное", "Запишем Аделину на пробное"),
    ],
)
def test_bare_name_is_declined(text, expected):
    assert grammar.fix_names(text, ["Аделина"]) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Аделина уже изучала язык",
        "Это поможет Аделине понять",
        "Детям, как Аделина, обычно нравится",
    ],
)
def test_correct_forms_are_left_alone(text):
    assert grammar.fix_names(text, ["Аделина"]) == text


def test_name_inside_another_word_is_not_touched():
    assert grammar.fix_names("Аделинапарк", ["Аделина"]) == "Аделинапарк"


def test_compound_names_are_not_touched():
    """У имени и фамилии разные правила — ошибка была бы заметнее."""
    text = "Это поможет Иванова Анна понять"
    assert grammar.fix_names(text, ["Иванова Анна"]) == text


def test_no_names_means_no_changes():
    assert grammar.fix_names("Занятия по вторникам", []) == "Занятия по вторникам"
