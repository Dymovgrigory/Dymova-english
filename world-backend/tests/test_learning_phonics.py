"""Линия чтения: разбиение слова на графемы и «можно ли прочитать»."""
from app.learning import phonics

INVENTORY = ["s", "h", "i", "p", "sh", "c", "a", "t", "m", "u", "ee", "e"]


def test_segment_prefers_longest_grapheme():
    assert phonics.segment("ship", INVENTORY) == ["sh", "i", "p"]
    assert phonics.segment("Cat", INVENTORY) == ["c", "a", "t"]


def test_segment_rejects_unknown_letters_and_spaces():
    assert phonics.segment("dog", INVENTORY) is None
    assert phonics.segment("ice cream", INVENTORY) is None
    assert phonics.segment("", INVENTORY) is None


def test_readable_needs_every_grapheme_known():
    assert phonics.readable("cat", {"c", "a", "t"}, INVENTORY) == ["c", "a", "t"]
    assert phonics.readable("mum", {"m"}, INVENTORY) is None
    assert phonics.readable("ship", {"s", "h", "i", "p"}, INVENTORY) is None
