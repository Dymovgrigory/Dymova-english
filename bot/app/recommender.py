"""Что именно предложить этому человеку — и почему.

Подбор по возрасту (`course_selector`) отвечает на вопрос «что подходит по
формальному признаку». Этого мало: две семьи с девятилетними детьми приходят
с разными задачами, и предлагать им одно и то же — то же самое, что читать
прайс вслух.

Здесь решение собирается из того, что человек рассказал: возраст, формат,
цель, сложность, время. Вместе с программой возвращается уверенность (на
скольких фактах решение построено), человеческое обоснование со ссылкой на
слова клиента и следующий шаг. Если фактов мало, честный ответ — не
«предложить хоть что-то», а спросить.

Слой детерминированный: он решает, что предлагать, а формулирует ответ
модель. Так предложение не зависит от настроения генерации и его можно
проверить тестом.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app import sales
from app.knowledge.kb import KnowledgeBase
from app.profile import UserProfile

# Следующий шаг: что делать с этим человеком дальше.
NEXT_ASK = "ask"  # рано предлагать, нужен ещё один вопрос
NEXT_DIAGNOSTIC = "diagnostic"  # позвать на бесплатную диагностику
NEXT_LEAD = "lead"  # собирать заявку, человек готов
NEXT_HANDOFF = "handoff"  # случай не для бота

# Ниже этого порога предложение звучит как угадывание.
MIN_CONFIDENCE = 0.45

_AGE_RE = re.compile(r"\d+")

# Слова цели/сложности → слова, которые ищем в описании программы. Список
# намеренно короткий: он про то, чем программы реально отличаются друг от
# друга, а не про все возможные формулировки клиента.
_GOAL_HINTS = {
    "говор": ("разговор", "speaking", "речь", "общен"),
    "экзамен": ("экзамен", "огэ", "егэ", "ielts", "подготовк"),
    "школ": ("школьн", "грамматик", "программ"),
    "чтен": ("чтен", "read"),
    "олимпиад": ("олимпиад", "hippo"),
    "малыш": ("дошкол", "малыш", "3-6", "2-6"),
}


@dataclass
class Recommendation:
    """Решение о том, что предложить, вместе с его обоснованием."""

    program: str
    confidence: float
    reason: str
    next_best_action: str
    alternatives: list[str] = field(default_factory=list)

    def as_text(self) -> str:
        """Предложение человеческим языком — одна связная реплика."""
        lines = [f"{self.reason} — думаю, вам подойдёт «{self.program}»."]
        if self.alternatives:
            lines.append("Как вариант — ещё " + " или ".join(
                f"«{name}»" for name in self.alternatives[:2]
            ) + ".")
        if self.next_best_action == NEXT_DIAGNOSTIC:
            lines.append(
                "Точный уровень покажет бесплатная диагностика — она ни к чему "
                "не обязывает. Подобрать время?"
            )
        return " ".join(lines)


def _language_of(card: UserProfile, conv) -> str:
    """Какой язык интересует человека: «китайск» / «немецк» / «английск» / "".

    Без этого измерения подбор для «китайский с нуля для шестилетней»
    честно находил лучшее совпадение по возрасту — «Для дошкольников»,
    то есть английский. Рекомендация не по тому языку хуже, чем её
    отсутствие.
    """
    haystack = " ".join(
        [
            getattr(conv, "selected_course", "") or "",
            " ".join(card.goals),
            " ".join(card.motivations),
            " ".join(card.pain_points),
            # Язык часто назван только вслух в переписке и не попадает ни в
            # одно поле профиля — смотрим последние реплики человека.
            " ".join(
                m.get("content", "")
                for m in getattr(conv, "history", [])[-6:]
                if m.get("role") == "user"
            ),
        ]
    ).lower()
    for marker in ("китайск", "немецк", "английск"):
        if marker in haystack:
            return marker
    return ""


def _filter_by_language(programs: list[dict], language: str) -> list[dict]:
    """Кандидаты только по названному языку.

    Английский — язык школы по умолчанию: возрастные программы («Для
    дошкольников») его в тексте не называют, но про него. Поэтому для
    английского отсекаем явно немецкое/китайское, а для китайского и
    немецкого — всё, где язык не упомянут.
    """
    if not language:
        return programs

    def text_of(program: dict) -> str:
        return f"{program.get('name', '')} {program.get('text', '')}".lower()

    if language == "английск":
        return [
            p for p in programs
            if "китайск" not in text_of(p) and "немецк" not in text_of(p)
        ]
    return [p for p in programs if language in text_of(p)]


def suggest(kb: KnowledgeBase, conv) -> Recommendation | None:
    """Что предложить этому человеку. None — предлагать пока нечего.

    None означает ровно одно: фактов недостаточно, чтобы предложение не было
    угадыванием. Вызывающий в этом случае продолжает выяснять потребность.
    """
    card = UserProfile.of(conv)
    programs = _candidates(kb)
    if not programs:
        return None
    programs = _filter_by_language(programs, _language_of(card, conv))
    if not programs:
        return None

    ranked = sorted(
        ((_score(program, card), program) for program in programs),
        key=lambda pair: pair[0],
        reverse=True,
    )
    best_score, best = ranked[0]
    if best_score <= 0:
        return None

    confidence = _confidence(card, best_score)
    if confidence < MIN_CONFIDENCE:
        return None

    return Recommendation(
        program=str(best.get("name") or "").strip(),
        confidence=round(confidence, 2),
        reason=_reason(card),
        next_best_action=_next_action(conv, confidence),
        alternatives=[
            str(item.get("name") or "").strip()
            for score, item in ranked[1:3]
            if score > 0
        ],
    )


def _candidates(kb: KnowledgeBase) -> list[dict]:
    """Возрастные программы плюс курсы — у них разные поля, приводим к одному."""
    items: list[dict] = []
    for program in kb.age_programs:
        items.append(
            {
                "name": program.get("name", ""),
                "age": program.get("age", ""),
                "text": program.get("text", ""),
                "format": "",
            }
        )
    for course in kb.courses:
        items.append(
            {
                "name": course.get("name", ""),
                "age": course.get("ages", ""),
                "text": " ".join(
                    str(course.get(key, "")) for key in ("description", "note")
                ),
                "format": course.get("format", ""),
            }
        )
    return [item for item in items if item["name"]]


def _score(program: dict, card: UserProfile) -> float:
    """Насколько программа отвечает тому, что человек рассказал."""
    score = 0.0
    age = _age_of(card)
    if age is not None:
        low, high = _age_range(program.get("age", ""))
        if low is None:
            # Программа без указанного возраста подходит любому, но это
            # слабое совпадение — предпочтение у явного попадания.
            score += 0.2
        elif low <= age <= high:
            score += 1.0
        else:
            # Возраст назван и не подходит — это не кандидат.
            return 0.0

    haystack = f"{program.get('name', '')} {program.get('text', '')}".lower()
    if card.preferred_format:
        fmt = card.preferred_format.lower()
        if fmt[:5] in haystack or fmt[:5] in str(program.get("format", "")).lower():
            score += 0.5

    for phrase in list(card.goals) + list(card.pain_points) + list(card.motivations):
        for marker, hints in _GOAL_HINTS.items():
            if marker in phrase.lower() and any(hint in haystack for hint in hints):
                score += 0.6
                break
    return score


def _confidence(card: UserProfile, best_score: float) -> float:
    """На скольких известных фактах построено решение.

    Уверенность растёт и от совпадения программы с задачей, и от того,
    сколько мы вообще знаем: подобрать «по возрасту и больше ни по чему» —
    это не то же самое, что подобрать под названную цель.
    """
    known = sum(
        1
        for value in (
            card.child_age,
            card.english_level,
            card.preferred_format,
            card.goals,
            card.pain_points,
            card.schedule,
        )
        if value
    )
    return min(1.0, 0.25 * min(best_score, 2.0) + 0.14 * known)


def _next_action(conv, confidence: float) -> str:
    if conv.handed_off:
        return NEXT_HANDOFF
    if not sales.offer_allowed(conv):
        # Ворота продажи закрыты: либо потребность не выяснена, либо человек
        # не в том состоянии. Предложение подождёт.
        return NEXT_ASK
    if conv.lead.phone or conv.lead_submitted:
        return NEXT_LEAD
    return NEXT_DIAGNOSTIC if confidence >= 0.6 else NEXT_ASK


def _reason(card: UserProfile) -> str:
    """Обоснование со ссылкой на слова клиента, а не на нашу логику."""
    bits: list[str] = []
    if card.child_age:
        bits.append(f"ребёнку {card.child_age}")
    if card.english_level:
        bits.append(f"уровень — {card.english_level}")
    if card.goals:
        bits.append(f"цель — {card.goals[0]}")
    elif card.pain_points:
        bits.append(f"сложность — {card.pain_points[0]}")
    if card.preferred_format:
        bits.append(f"формат — {card.preferred_format}")
    if not bits:
        return "Судя по тому, что вы рассказали"
    return "Судя по тому, что вы рассказали (" + ", ".join(bits) + ")"


def _age_of(card: UserProfile) -> int | None:
    match = _AGE_RE.search(card.child_age or "")
    return int(match.group()) if match else None


def _age_range(text: str) -> tuple[int | None, int]:
    numbers = [int(x) for x in _AGE_RE.findall(text or "")]
    if len(numbers) >= 2:
        return numbers[0], numbers[1]
    if len(numbers) == 1:
        # «16+» и «с 7 лет» читаем как открытый диапазон вверх.
        return numbers[0], 99 if "+" in text or "от" in text.lower() else numbers[0]
    return None, 0


__all__ = [
    "MIN_CONFIDENCE",
    "NEXT_ASK",
    "NEXT_DIAGNOSTIC",
    "NEXT_HANDOFF",
    "NEXT_LEAD",
    "Recommendation",
    "suggest",
]
