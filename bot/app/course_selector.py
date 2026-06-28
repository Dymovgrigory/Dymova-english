"""Course Selector: подбор подходящих курсов/программ по данным клиента."""
from __future__ import annotations

from app.knowledge.kb import KnowledgeBase


def _age_to_int(age: str) -> int | None:
    try:
        return int(str(age).strip())
    except (TypeError, ValueError):
        return None


def recommend(kb: KnowledgeBase, age: str | None = None, fmt: str | None = None) -> list[dict]:
    """Возвращает 2-3 наиболее подходящие программы по возрасту."""
    programs = kb.age_programs
    age_int = _age_to_int(age) if age else None

    if age_int is not None:
        matched = []
        for p in programs:
            lo, hi = _parse_age_range(p.get("age", ""))
            if lo is not None and lo <= age_int <= hi:
                matched.append(p)
        if matched:
            return matched
        # вне диапазона детских программ — взрослые/основные группы
        if age_int > 16:
            return [{
                "name": "Английский для подростков и взрослых",
                "age": "16+",
                "text": "Разговорная практика, грамматика, подготовка к экзаменам.",
                "url": kb.company.get("website", ""),
            }]
    return programs[:3]


def _parse_age_range(text: str) -> tuple[int | None, int]:
    import re

    nums = [int(x) for x in re.findall(r"\d+", text or "")]
    if len(nums) >= 2:
        return nums[0], nums[1]
    if len(nums) == 1:
        return nums[0], nums[0]
    return None, 0


def format_recommendations(items: list[dict]) -> str:
    if not items:
        return ""
    lines = ["Вот что отлично подойдёт:"]
    for p in items:
        age = f" ({p.get('age')})" if p.get("age") else ""
        lines.append(f"• {p.get('name')}{age} — {p.get('text','').strip()}")
    return "\n".join(lines)
