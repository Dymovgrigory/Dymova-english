"""Линия чтения: можно ли прочитать слово уже изученными графемами."""
from __future__ import annotations

import re

_LETTERS = re.compile(r"[a-z]+")


def segment(word: str, inventory: list[str]) -> list[str] | None:
    """Разбивает слово на графемы, выбирая самую длинную подходящую (sh раньше s)."""
    text = word.lower()
    if not _LETTERS.fullmatch(text):
        return None
    graphemes = sorted(set(inventory), key=len, reverse=True)
    parts: list[str] = []
    position = 0
    while position < len(text):
        for grapheme in graphemes:
            if text.startswith(grapheme, position):
                parts.append(grapheme)
                position += len(grapheme)
                break
        else:
            return None
    return parts


def readable(word: str, known: set[str], inventory: list[str]) -> list[str] | None:
    parts = segment(word, inventory)
    if parts is None or any(part not in known for part in parts):
        return None
    return parts
