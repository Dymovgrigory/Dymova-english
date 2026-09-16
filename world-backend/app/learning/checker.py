"""Проверка ответов ученика.

Сравниваем нормализованный текст: регистр, пунктуация, типографские апострофы и
сокращения (it's = it is) не считаются ошибкой. Опечатка в одну букву в словах от
5 символов засчитывается как верный ответ с пометкой typo.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

CONTRACTIONS = {
    "i'm": "i am", "it's": "it is", "he's": "he is", "she's": "she is",
    "that's": "that is", "what's": "what is", "where's": "where is", "who's": "who is",
    "there's": "there is", "you're": "you are", "we're": "we are", "they're": "they are",
    "isn't": "is not", "aren't": "are not", "don't": "do not", "doesn't": "does not",
    "can't": "can not", "cannot": "can not", "haven't": "have not", "hasn't": "has not",
    "i've": "i have", "you've": "you have", "we've": "we have", "they've": "they have",
    "i'll": "i will", "let's": "let us",
}
TYPO_MIN_LENGTH = 5
SPEECH_THRESHOLD = 0.75

_NOT_WORD = re.compile(r"[^a-z0-9а-яё' ]+")


@dataclass(frozen=True)
class Verdict:
    correct: bool
    typo: bool = False


def normalize(text: str) -> str:
    lowered = text.lower().replace("’", "'").replace("`", "'")
    words = [w.strip("'") for w in _NOT_WORD.sub(" ", lowered).split()]
    expanded = [CONTRACTIONS.get(w, w) for w in words if w]
    return " ".join(" ".join(expanded).split())


def tokens(text: str) -> list[str]:
    return normalize(text).split()


def levenshtein(a: str, b: str) -> int:
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current = [i]
        for j, char_b in enumerate(b, start=1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (char_a != char_b)))
        previous = current
    return previous[-1]


def check_text(answer: str, accepted: list[str], *, allow_typo: bool) -> Verdict:
    given = normalize(answer)
    if not given:
        return Verdict(False)
    targets = [normalize(a) for a in accepted]
    if given in targets:
        return Verdict(True)
    if allow_typo and any(len(t) >= TYPO_MIN_LENGTH and levenshtein(given, t) == 1 for t in targets):
        return Verdict(True, typo=True)
    return Verdict(False)


def check_choice(answer: int, correct: int) -> Verdict:
    return Verdict(answer == correct)


def check_pairs(answer: list[list[str]], pairs: list[list[str]]) -> Verdict:
    return Verdict({tuple(p) for p in answer} == {tuple(p) for p in pairs})


def check_speech(transcript: str, target: str) -> Verdict:
    wanted = tokens(target)
    heard = set(tokens(transcript))
    if not wanted:
        return Verdict(False)
    hits = sum(1 for word in wanted if word in heard)
    return Verdict(hits / len(wanted) >= SPEECH_THRESHOLD)
