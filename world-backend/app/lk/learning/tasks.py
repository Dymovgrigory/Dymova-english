"""Versioned starter task bank for the LMS catalog.

The bank is deliberately server-owned: answer fields never leave this module.
Content is expanded by adding versioned units, not by changing client logic.
"""
from __future__ import annotations

from .core import Challenge

TASKS: dict[str, tuple[Challenge, ...]] = {
    "pre-a1.family": (
        Challenge("family-vocab-1", "translate_choice", "Выбери перевод: mum", ("мама", "папа", "брат"), 0, None, ()),
        Challenge("family-listen-1", "listen_choice", "Послушай и выбери слово", ("mum", "dad", "sister"), 0, None, ()),
        Challenge("family-grammar-1", "grammar_choice", "This ___ my mum.", ("is", "are", "am"), 0, None, ()),
        Challenge("family-read-1", "read_true_false", "Read: This is my mum. Is it about a family member?", (), None, True, ()),
        Challenge("family-write-1", "write", "Напиши по-английски: мама", (), None, None, ("mum", "mother")),
    ),
    "pre-a1.school": (
        Challenge("school-vocab-1", "translate_choice", "Выбери перевод: book", ("книга", "ручка", "стол"), 0, None, ()),
        Challenge("school-grammar-1", "grammar_choice", "This ___ my schoolbag.", ("is", "are", "am"), 0, None, ()),
        Challenge("school-listen-1", "listen_choice", "Послушай и выбери слово", ("book", "bag", "pen"), 0, None, ()),
        Challenge("school-write-1", "write", "Напиши по-английски: ручка", (), None, None, ("pen",)),
    ),
    "a1.family": (
        Challenge("a1-family-vocab-1", "translate_choice", "Выбери перевод: cousin", ("двоюродный брат / сестра", "сосед", "учитель"), 0),
        Challenge("a1-family-grammar-1", "grammar_choice", "My sister ___ ten years old.", ("is", "are", "am"), 0),
        Challenge("a1-family-read-1", "read_true_false", "Read: Tom lives with his parents and one sister. Does Tom have a sister?", (), None, True),
        Challenge("a1-family-speak-1", "speak", "Скажи по-английски и отправь расшифровку: У меня есть брат.", (), None, None, ("I have a brother", "I've got a brother")),
    ),
    "a1.home": (
        Challenge("a1-home-vocab-1", "translate_choice", "Выбери перевод: kitchen", ("кухня", "ванная", "спальня"), 0),
        Challenge("a1-home-grammar-1", "grammar_choice", "There ___ two chairs in the room.", ("are", "is", "am"), 0),
        Challenge("a1-home-listen-1", "listen_choice", "Послушай и выбери слово: window", ("window", "door", "garden"), 0),
        Challenge("a1-home-write-1", "write", "Напиши по-английски: стол", (), None, None, ("table",)),
    ),
    "a2.travel": (
        Challenge("a2-travel-vocab-1", "translate_choice", "Выбери перевод: journey", ("путешествие", "билет", "багаж"), 0),
        Challenge("a2-travel-grammar-1", "grammar_choice", "We ___ to Spain last summer.", ("went", "go", "have gone"), 0),
        Challenge("a2-travel-read-1", "read_choice", "Read: The train leaves at 8:30 from platform 4. Where does it leave from?", ("platform 4", "platform 8", "the airport"), 0),
        Challenge("a2-travel-write-1", "write", "Напиши по-английски: Я забронировал номер.", (), None, None, ("I booked a room",)),
    ),
    "a2.health": (
        Challenge("a2-health-vocab-1", "translate_choice", "Выбери перевод: headache", ("головная боль", "боль в животе", "температура"), 0),
        Challenge("a2-health-grammar-1", "grammar_choice", "You ___ drink more water.", ("should", "should to", "are"), 0),
        Challenge("a2-health-read-1", "read_true_false", "Read: Emma has a cold, so she is staying at home today. Is Emma at school today?", (), None, False),
        Challenge("a2-health-speak-1", "speak", "Скажи по-английски: Мне нужно записаться к врачу.", (), None, None, ("I need to make an appointment with a doctor", "I need to book a doctor's appointment")),
    ),
    "b1.adventures": (
        Challenge("b1-adventures-vocab-1", "translate_choice", "Выбери перевод: breathtaking", ("захватывающий дух", "опасный", "обычный"), 0),
        Challenge("b1-adventures-grammar-1", "grammar_choice", "If I had more time, I ___ around the world.", ("would travel", "will travel", "travelled"), 0),
        Challenge("b1-adventures-read-1", "read_choice", "Read: Maya turned back because the path was covered with ice. Why did Maya turn back?", ("The path was icy", "She was tired", "It was dark"), 0),
        Challenge("b1-adventures-write-1", "write", "Напиши по-английски: Мы никогда не видели ничего подобного.", (), None, None, ("We have never seen anything like this",)),
    ),
}


def tasks_for(unit_id: str) -> tuple[Challenge, ...]:
    return TASKS.get(unit_id, TASKS["pre-a1.family"])
