"""Тест уровня английского для мини-приложения.

Зачем он в продукте: родитель почти никогда не может назвать уровень
ребёнка, а без уровня подбор программы превращается в гадание. Спрашивать
«какой у вас уровень?» бесполезно — человек не знает. Десять коротких
заданий дают ответ, который понятен обеим сторонам, и заодно превращают
витрину в инструмент: приложением начинают пользоваться, а не листать.

Задания разных типов, а не только «вставь пропуск»: с картинкой (svg рисует
само приложение, системных emoji нет), «выбери лишнее», «собери предложение»
и классический выбор формы. Порядок — от простого к сложному, чтобы человек
не упёрся в стену на первом же вопросе и не бросил тест.

Вопросы живут здесь, а не в вёрстке: их правит методист, а не верстальщик,
и правка не требует пересборки фронтенда. Правильные ответы наружу не
уходят — иначе тест решается открытием исходника страницы.

Это не языковая сертификация: шкала грубая (A0–B1+) и honest-by-design —
результат прямо говорит, что точный уровень покажет диагностика с
методистом.
"""
from __future__ import annotations

from dataclasses import dataclass

# Картинки — крошечные фирменные SVG. Не emoji: системные смайлы запрещены
# дизайн-контрактом приложения.
_ART_CAT = (
    '<svg viewBox="0 0 120 100" aria-hidden="true">'
    '<circle cx="60" cy="58" r="30" fill="#ffb703"/>'
    '<path d="M36 42 L30 20 L52 32 Z" fill="#ffb703"/>'
    '<path d="M84 42 L90 20 L68 32 Z" fill="#ffb703"/>'
    '<circle cx="50" cy="54" r="4" fill="#14110c"/>'
    '<circle cx="70" cy="54" r="4" fill="#14110c"/>'
    '<path d="M55 66 Q60 71 65 66" stroke="#14110c" stroke-width="3" fill="none" stroke-linecap="round"/>'
    "</svg>"
)
_ART_APPLES = (
    '<svg viewBox="0 0 120 100" aria-hidden="true">'
    '<g><circle cx="30" cy="62" r="16" fill="#ff6b8b"/>'
    '<path d="M30 46 q2 -8 8 -10" stroke="#4a4238" stroke-width="3" fill="none" stroke-linecap="round"/></g>'
    '<g><circle cx="62" cy="52" r="16" fill="#ff6b8b"/>'
    '<path d="M62 36 q2 -8 8 -10" stroke="#4a4238" stroke-width="3" fill="none" stroke-linecap="round"/></g>'
    '<g><circle cx="92" cy="66" r="16" fill="#ff6b8b"/>'
    '<path d="M92 50 q2 -8 8 -10" stroke="#4a4238" stroke-width="3" fill="none" stroke-linecap="round"/></g>'
    "</svg>"
)
_ART_SUN = (
    '<svg viewBox="0 0 120 100" aria-hidden="true">'
    '<circle cx="60" cy="50" r="20" fill="#ffb703"/>'
    '<g stroke="#f08a00" stroke-width="4" stroke-linecap="round">'
    '<path d="M60 16 v10 M60 74 v10 M26 50 h10 M84 50 h10 M36 26 l7 7 M77 67 l7 7 M84 26 l-7 7 M43 67 l-7 7"/>'
    "</g></svg>"
)
_ART_RAIN = (
    '<svg viewBox="0 0 120 100" aria-hidden="true">'
    '<ellipse cx="60" cy="40" rx="30" ry="16" fill="#6b4de6" opacity=".85"/>'
    '<g stroke="#24c6a0" stroke-width="4" stroke-linecap="round">'
    '<path d="M42 62 l-4 12 M60 62 l-4 12 M78 62 l-4 12"/>'
    "</g></svg>"
)

# Порядок важен: задания идут от простого к сложному, чтобы человек не
# упёрся в стену на первом же вопросе и не бросил тест.
# type: choice — выбор варианта; picture — картинка + варианты;
# order — собрать предложение из слов (answer — индексы options в верном
# порядке).
QUESTIONS: list[dict] = [
    {
        "id": "q1",
        "type": "picture",
        "art": _ART_CAT,
        "prompt": "What is it?",
        "hint": "Посмотри на картинку",
        "options": ["a cat", "a dog", "a bird", "a fish"],
        "answer": 0,
    },
    {
        "id": "q2",
        "type": "picture",
        "art": _ART_APPLES,
        "prompt": "How many apples are there?",
        "hint": "Сосчитай по-английски",
        "options": ["Five", "Two", "Three", "Ten"],
        "answer": 2,
    },
    {
        "id": "q3",
        "type": "picture",
        "art": _ART_SUN,
        "prompt": "Как по-английски «солнце»?",
        "hint": "Перевод слова",
        "options": ["Moon", "Sun", "Star", "Rain"],
        "answer": 1,
    },
    {
        "id": "q4",
        "type": "choice",
        "prompt": "Какое слово лишнее?",
        "hint": "Три слова — про одно, одно — про другое",
        "options": ["apple", "banana", "carrot", "orange"],
        "answer": 2,
    },
    {
        "id": "q5",
        "type": "choice",
        "prompt": "She ___ to school every day.",
        "hint": "Простое настоящее время",
        "options": ["go", "goes", "going", "gone"],
        "answer": 1,
    },
    {
        "id": "q6",
        "type": "order",
        "prompt": "Собери предложение",
        "hint": "Нажимай слова по порядку",
        "options": ["like", "I", "apples"],
        "answer": [1, 0, 2],
    },
    {
        "id": "q7",
        "type": "choice",
        "prompt": "I ___ my homework yesterday.",
        "hint": "Прошедшее время",
        "options": ["do", "did", "does", "done"],
        "answer": 1,
    },
    {
        "id": "q8",
        "type": "picture",
        "art": _ART_RAIN,
        "prompt": "What's the weather like?",
        "hint": "Опиши погоду на картинке",
        "options": ["It is sunny", "It is rainy", "It is snowy", "It is windy"],
        "answer": 1,
    },
    {
        "id": "q9",
        "type": "choice",
        "prompt": "There ___ many books on the shelf.",
        "hint": "Единственное и множественное",
        "options": ["is", "am", "are", "be"],
        "answer": 2,
    },
    {
        "id": "q10",
        "type": "choice",
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


# Границы намеренно широкие: десять заданий не различают A2 и B1 точно, и
# делать вид, что различают, — обман.
_LEVELS = (
    (0, Level(
        "A0–A1",
        "Начальный уровень",
        "Базовые слова и конструкции ещё не закрепились — это нормально для "
        "старта. Начинаем с базы и говорения с первого занятия.",
    )),
    (4, Level(
        "A1–A2",
        "Уверенное начало",
        "Простые слова и база есть, но времена пока путаются. Это самый частый "
        "уровень у школьников: разберём системно и добавим практику речи.",
    )),
    (7, Level(
        "A2–B1",
        "Хорошая база",
        "Основные времена вы держите. Дальше растёт разговорная свобода и "
        "объём лексики — здесь помогает среда без перехода на русский.",
    )),
    (9, Level(
        "B1+",
        "Сильный уровень",
        "Задания такого типа даются легко. Подойдёт группа посильнее или "
        "подготовка к экзаменам — точнее скажет методист.",
    )),
)


def public_questions() -> list[dict]:
    """Задания без правильных ответов — то, что уходит в приложение."""
    return [
        {
            "id": q["id"],
            "type": q["type"],
            "prompt": q["prompt"],
            "hint": q["hint"],
            "options": q["options"],
            # Картинка уходит наружу: это наша же разметка, не ответ.
            **({"art": q["art"]} if q.get("art") else {}),
        }
        for q in QUESTIONS
    ]


def _right_text(question: dict) -> str:
    answer = question["answer"]
    if isinstance(answer, list):
        return " ".join(question["options"][i] for i in answer)
    return question["options"][answer]


def _is_correct(question: dict, given) -> bool:
    answer = question["answer"]
    if isinstance(answer, list):
        return isinstance(given, list) and list(given) == answer
    return isinstance(given, int) and given == answer


def grade(answers: dict) -> dict:
    """Итог теста по ответам вида {"q1": 1, "q6": [1, 0, 2]}.

    Неизвестные и пропущенные ответы считаются неверными: подсказывать, что
    вопрос можно не отвечать, смысла нет, а падать из-за кривого запроса —
    тем более.
    """
    correct = 0
    per_question: list[dict] = []
    for question in QUESTIONS:
        given = answers.get(question["id"])
        ok = _is_correct(question, given)
        correct += 1 if ok else 0
        per_question.append(
            {
                "id": question["id"],
                "correct": ok,
                "right_option": _right_text(question),
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
        # вёрстке: десять заданий не заменяют диагностику.
        "disclaimer": "Это быстрая проверка, а не диагностика. Точный уровень "
        "и план занятий определит методист на бесплатной встрече.",
    }


__all__ = ["QUESTIONS", "grade", "public_questions"]
