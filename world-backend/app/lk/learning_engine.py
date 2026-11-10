"""Pure learning rules used by the server-side vocabulary engine."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Literal

INTERVALS_DAYS = (1, 1, 3, 7, 14, 30)
Skill = Literal["recognition", "listening", "recall", "spelling", "usage"]
TaskType = Literal["recognition", "listening", "translation", "spell", "usage"]


@dataclass(frozen=True)
class SkillState:
    recognition: int = 0
    listening: int = 0
    recall: int = 0
    spelling: int = 0
    usage: int = 0


@dataclass(frozen=True)
class AnswerResult:
    state: SkillState
    next_review: date
    retry: bool


@dataclass(frozen=True)
class TaskSpec:
    task_type: TaskType
    word_id: int
    prompt: str
    options: tuple[str, ...]
    correct_index: int


def _clamp(value: int) -> int:
    return max(0, min(len(INTERVALS_DAYS) - 1, value))


def apply_answer(state: SkillState, skill: Skill, correct: bool, today: date) -> AnswerResult:
    """Apply one answer to exactly one skill and compute the next review date."""
    current = getattr(state, skill)
    updated = _clamp(current + (1 if correct else -1))
    next_state = replace(state, **{skill: updated})
    if not correct:
        return AnswerResult(next_state, today, True)
    return AnswerResult(next_state, today + timedelta(days=INTERVALS_DAYS[updated]), False)


def choose_task_type(state: SkillState, *, has_image: bool, has_example: bool) -> TaskType:
    """Choose the weakest available skill, with content-aware fallbacks."""
    candidates: list[tuple[int, TaskType]] = []
    if has_image:
        candidates.append((state.recognition, "recognition"))
    candidates.append((state.listening, "listening"))
    candidates.append((state.recall, "translation"))
    candidates.append((state.spelling, "spell"))
    if has_example:
        candidates.append((state.usage, "usage"))
    return min(candidates, key=lambda item: (item[0], item[1]))[1]


def make_task(
    *,
    task_type: TaskType,
    word_id: int,
    prompt: str,
    correct: str,
    options: list[str],
    confusable: set[str] | None = None,
) -> TaskSpec:
    """Normalize options so a multiple-choice task has unique safe answers."""
    blocked = confusable or set()
    normalized: list[str] = []
    seen: set[str] = set()
    for option in options:
        key = option.casefold().strip()
        if not key or key in seen:
            continue
        if option != correct and key in {item.casefold().strip() for item in blocked}:
            continue
        seen.add(key)
        normalized.append(option)
    if correct.casefold().strip() not in seen:
        normalized.insert(0, correct)
    correct_index = next(i for i, option in enumerate(normalized) if option.casefold() == correct.casefold())
    return TaskSpec(task_type, word_id, prompt, tuple(normalized), correct_index)
