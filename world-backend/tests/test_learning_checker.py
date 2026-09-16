"""Проверка ответов: нормализация, сокращения, опечатки, пары, речь."""
from app.learning import checker
from app.learning.checker import Verdict


def test_normalize_strips_case_punctuation_and_expands_contractions():
    assert checker.normalize("It’s a CAT!") == "it is a cat"
    assert checker.normalize("  I'm   Dad. ") == "i am dad"
    assert checker.normalize("Hello, Mum!") == "hello mum"
    assert checker.normalize("It isn't") == "it is not"


def test_check_text_accepts_variants():
    assert checker.check_text("eraser", ["rubber", "eraser"], allow_typo=True) == Verdict(True)
    assert checker.check_text("Where's the cat", ["Where is the cat?"], allow_typo=False) == Verdict(True)


def test_check_text_typo_tolerance_only_for_long_answers():
    assert checker.check_text("pencl", ["pencil"], allow_typo=True) == Verdict(True, typo=True)
    assert checker.check_text("cot", ["cat"], allow_typo=True) == Verdict(False)
    assert checker.check_text("pencl", ["pencil"], allow_typo=False) == Verdict(False)


def test_check_text_rejects_empty():
    assert checker.check_text("  !! ", ["cat"], allow_typo=True) == Verdict(False)


def test_check_choice():
    assert checker.check_choice(2, 2) == Verdict(True)
    assert checker.check_choice(1, 2) == Verdict(False)


def test_check_pairs_ignores_order_but_needs_all():
    pairs = [["l0", "r2"], ["l1", "r0"], ["l2", "r1"]]
    assert checker.check_pairs([["l2", "r1"], ["l0", "r2"], ["l1", "r0"]], pairs) == Verdict(True)
    assert checker.check_pairs([["l2", "r1"], ["l0", "r2"]], pairs) == Verdict(False)


def test_check_speech_threshold():
    assert checker.check_speech("this is my", "This is my bag.") == Verdict(True)
    assert checker.check_speech("bag", "This is my bag.") == Verdict(False)
    assert checker.check_speech("", "cat") == Verdict(False)


def test_levenshtein():
    assert checker.levenshtein("kitten", "sitting") == 3
    assert checker.levenshtein("", "ab") == 2
