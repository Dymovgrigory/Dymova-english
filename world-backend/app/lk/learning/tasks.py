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
        Challenge("family-read-1", "read_true_false", "Read: This is my mum. Is it about a family member?", (), None, True, ()),
        Challenge("family-write-1", "write", "Напиши по-английски: мама", (), None, None, ("mum", "mother")),
    ),
    "pre-a1.school": (
        Challenge("school-vocab-1", "translate_choice", "Выбери перевод: book", ("книга", "ручка", "стол"), 0, None, ()),
        Challenge("school-grammar-1", "grammar_choice", "This ___ my schoolbag.", ("is", "are", "am"), 0, None, ()),
        Challenge("school-listen-1", "listen_choice", "Послушай и выбери слово", ("book", "bag", "pen"), 0, None, ()),
        Challenge("school-write-1", "write", "Напиши по-английски: ручка", (), None, None, ("pen",)),
    ),
}


def tasks_for(unit_id: str) -> tuple[Challenge, ...]:
    return TASKS.get(unit_id, TASKS["pre-a1.family"])
