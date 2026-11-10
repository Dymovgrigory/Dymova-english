"""Server-owned LMS challenge model and answer grading."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

ChallengeKind = Literal[
    "grammar_choice", "translate_choice", "listen_choice", "read_choice",
    "read_true_false", "write", "speak",
]


@dataclass(frozen=True)
class Challenge:
    id: str
    kind: ChallengeKind
    prompt: str
    options: tuple[str, ...] = ()
    answer_index: int | None = None
    answer_bool: bool | None = None
    accepted: tuple[str, ...] = ()


@dataclass(frozen=True)
class Grade:
    correct: bool
    normalized_answer: str = ""


def _normalize(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9а-яё']+", " ", value.casefold()).split())


def grade(challenge: Challenge, answer: dict) -> Grade:
    if challenge.kind in {"grammar_choice", "translate_choice", "listen_choice", "read_choice"}:
        index = answer.get("index")
        return Grade(isinstance(index, int) and index == challenge.answer_index, str(index))
    if challenge.kind == "read_true_false":
        value = answer.get("value")
        return Grade(isinstance(value, bool) and value is challenge.answer_bool, str(value))
    if challenge.kind in {"write", "speak"}:
        text = answer.get("text") if challenge.kind == "write" else answer.get("transcript")
        normalized = _normalize(text) if isinstance(text, str) else ""
        accepted = {_normalize(value) for value in challenge.accepted}
        return Grade(bool(normalized) and normalized in accepted, normalized)
    return Grade(False)
