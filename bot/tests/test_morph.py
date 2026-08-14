"""Склонение имён при развороте плейсхолдеров ПДн."""
from __future__ import annotations

import pytest

from app.morph import decline
from app.pii import PiiVault, placeholder_hint


@pytest.mark.parametrize(
    "name,case,expected",
    [
        # женские на «-а» с шипящей основой
        ("Маша", "род", "Маши"),
        ("Маша", "дат", "Маше"),
        ("Маша", "вин", "Машу"),
        ("Маша", "твор", "Машей"),
        ("Маша", "пред", "Маше"),
        # женские на «-а» с твёрдой основой
        ("Анна", "род", "Анны"),
        ("Анна", "вин", "Анну"),
        ("Анна", "твор", "Анной"),
        # заднеязычная основа: «Ольги», а не «Ольгы»
        ("Ольга", "род", "Ольги"),
        ("Ольга", "твор", "Ольгой"),
        # мужские на «-а» склоняются так же, как женские
        ("Никита", "вин", "Никиту"),
        ("Никита", "твор", "Никитой"),
        # на «-я»
        ("Настя", "вин", "Настю"),
        ("Настя", "твор", "Настей"),
        ("Женя", "дат", "Жене"),
        # «-ия» — особый случай: дательный и предложный на «-ии»
        ("Мария", "дат", "Марии"),
        ("Мария", "вин", "Марию"),
        ("Мария", "пред", "Марии"),
        # мужские на согласный
        ("Иван", "род", "Ивана"),
        ("Иван", "дат", "Ивану"),
        ("Иван", "твор", "Иваном"),
        ("Иван", "пред", "Иване"),
        # мужские на «-й» и «-ь»
        ("Андрей", "вин", "Андрея"),
        ("Андрей", "твор", "Андреем"),
        ("Игорь", "дат", "Игорю"),
        ("Игорь", "твор", "Игорем"),
    ],
)
def test_decline_common_names(name, case, expected):
    assert decline(name, case) == expected


def test_nominative_returns_name_unchanged():
    assert decline("Маша", "им") == "Маша"


@pytest.mark.parametrize("name", ["Отто", "Мери", "Анеле", "Masha"])
def test_indeclinable_names_left_alone(name):
    """Исказить имя хуже, чем оставить его в исходной форме."""
    assert decline(name, "вин") == name


def test_multiword_values_not_declined():
    """У фамилии и имени разные правила — составное значение не трогаем."""
    assert decline("Иванова Анна", "вин") == "Иванова Анна"


def test_unknown_case_label_returns_nominative():
    assert decline("Маша", "звательный") == "Маша"


def test_restore_declines_only_names():
    """Телефон и дата в падежах не нуждаются."""
    vault = PiiVault()
    vault.hide("CHILD_NAME", "Маша")
    vault.hide("PHONE", "+79161112233")
    assert vault.restore("звоните {{PHONE:дат}}") == "звоните +79161112233"
    assert vault.restore("скажите {{CHILD_NAME:дат}}") == "скажите Маше"


def test_restore_keeps_unknown_placeholder_visible():
    """Выдуманный моделью токен должен быть заметен, а не исчезать молча."""
    vault = PiiVault()
    vault.hide("CHILD_NAME", "Маша")
    assert vault.restore("привет {{TEACHER_NAME}}") == "привет {{TEACHER_NAME}}"


def test_placeholder_hint_lists_only_name_tokens():
    vault = PiiVault()
    vault.hide("CHILD_NAME", "Маша")
    vault.hide("PHONE", "+79161112233")
    hint = placeholder_hint(vault)
    assert "{{CHILD_NAME}}" in hint
    assert "PHONE" not in hint
    assert "{{CHILD_NAME:вин}}" in hint


def test_placeholder_hint_empty_without_names():
    assert placeholder_hint(PiiVault()) == ""
