"""Быстрый тест уровня английского для мини-приложения.

Зачем он в продукте: родитель почти никогда не может назвать уровень
ребёнка, а без уровня подбор программы превращается в гадание. Спрашивать
«какой у вас уровень?» бесполезно — человек не знает. Пять заданий за
минуту дают ответ, который понятен обеим сторонам, и заодно превращают
витрину в инструмент: приложением начинают пользоваться, а не листать.

Вопросы живут здесь, а не в вёрстке: их правит методист, а не верстальщик,
и правка не требует пересборки фронтенда. Правильные ответы наружу не
уходят — иначе тест решается открытием исходника страницы.

Это не языковая сертификация: шкала грубая (A0–B1+) и honest-by-design —
результат прямо говорит, что точный уровень покажет диагностика с
методистом.
"""
from __future__ import annotations

from dataclasses import dataclass

# Порядок важен: задания идут от простого к сложному, чтобы человек не
# упёрся в стену на первом же вопросе и не бросил тест.
QUESTIONS: list[dict] = [
    {
        "id": "q1",
        "prompt": "She ___ to school every day.",
        "hint": "Простое настоящее время",
        "options": ["go", "goes", "going", "gone"],
        "answer": 1,
    },
    {
        "id": "q2",
        "prompt": "I ___ my homework yesterday.",
        "hint": "Прошедшее время",
        "options": ["do", "did", "does", "done"],
        "answer": 1,
    },
    {
        "id": "q3",
        "prompt": "There ___ many books on the shelf.",
        "hint": "Единственное и множественное",
        "options": ["is", "am", "are", "be"],
        "answer": 2,
    },
    {
        "id": "q4",
        "prompt": "If it ___ tomorrow, we will stay home.",
        "hint": "Условное предложение",
        "options": ["rain", "rains", "rained", "will rain"],
        "answer": 1,
    },
    {
        "id": "q5",
        "prompt": "He has ___ in London since 2019.",
        "hint": "Совершённое время",
        "options": ["live", "lived", "living", "lives"],
        "answer": 1,
    },
]


@dataclass(frozen=True)
class Level:
    code: str
    title: str
    text: str


# Границы намеренно широкие: пять заданий не различают A2 и B1 точно, и
# делать вид, что различают, — обман.
_LEVELS = (
    (0, Level(
        "A0–A1",
        "Начальный уровень",
        "Базовые конструкции ещё не закрепились — это нормально для старта. "
        "Начинаем с базы и говорения с первого занятия.",
    )),
    (2, Level(
        "A1–A2",
        "Уверенное начало",
        "База есть, но времена пока путаются. Это самый частый уровень у "
        "школьников: разберём системно и добавим практику речи.",
    )),
    (4, Level(
        "A2–B1",
        "Хорошая база",
        "Основные времена вы держите. Дальше растёт разговорная свобода и "
        "объём лексики — здесь помогает среда без перехода на русский.",
    )),
    (5, Level(
        "B1+",
        "Сильный уровень",
        "Задания такого типа даются легко. Подойдёт группа посильнее или "
        "подготовка к экзаменам — точнее скажет методист.",
    )),
)


def public_questions() -> list[dict]:
    """Задания без правильных ответов — то, что уходит в приложение."""
    return [
        {"id": q["id"], "prompt": q["prompt"], "hint": q["hint"], "options": q["options"]}
        for q in QUESTIONS
    ]


def grade(answers: dict) -> dict:
    """Итог теста по ответам вида {"q1": 1, ...}.

    Неизвестные и пропущенные ответы считаются неверными: подсказывать, что
    вопрос можно не отвечать, смысла нет, а падать из-за кривого запроса —
    тем более.
    """
    correct = 0
    per_question: list[dict] = []
    for question in QUESTIONS:
        given = answers.get(question["id"])
        ok = isinstance(given, int) and given == question["answer"]
        correct += 1 if ok else 0
        per_question.append(
            {
                "id": question["id"],
                "correct": ok,
                "right_option": question["options"][question["answer"]],
            }
        )

    level = _LEVELS[0][1]
    for threshold, candidate in _LEVELS:
        if correct >= threshold:
            level = candidate

    return {
        "correct": correct,
        "total": len(QUESTIONS),
        "level": level.code,
        "title": level.title,
        "text": level.text,
        "details": per_question,
        # Честная оговорка едет вместе с результатом, а не мелким шрифтом в
        # вёрстке: пять заданий не заменяют диагностику.
        "disclaimer": "Это быстрая проверка, а не диагностика. Точный уровень "
        "и план занятий определит методист на бесплатной встрече.",
    }


__all__ = ["QUESTIONS", "grade", "public_questions"]
