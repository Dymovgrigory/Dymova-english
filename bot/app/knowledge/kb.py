"""База знаний: загрузка структурированных данных и интеллектуальный поиск.

KB загружает data.yaml и строит коллекцию «документов» (заголовок + текст).
Поиск — лёгкий лексический скоринг по совпадению слов запроса с документами,
устойчивый к русской морфологии за счёт усечения слов до основы.

Найденные фрагменты передаются LLM как контекст (RAG-lite), а структурированные
объекты (филиалы, курсы, форматы) используются детерминированными сценариями.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.config import settings

_DEFAULT_PATH = Path(__file__).with_name("data.yaml")
_WORD_RE = re.compile(r"[а-яёa-z0-9]+", re.IGNORECASE)
# Очень короткие/служебные слова не несут смысла для поиска.
_STOPWORDS = {
    "и", "в", "на", "с", "по", "для", "от", "до", "не", "а", "что", "как",
    "это", "у", "о", "за", "ли", "же", "бы", "то", "из", "мы", "вы", "я",
}


def _stem(word: str) -> str:
    """Грубое усечение русских окончаний, чтобы «курсы»~«курс», «детей»~«дет»."""
    word = word.lower()
    if len(word) <= 4:
        return word
    for suf in ("ями", "иями", "ого", "его", "ому", "ему", "ыми", "ими",
                "ах", "ях", "ов", "ев", "ей", "ам", "ям", "ом", "ем",
                "ая", "яя", "ое", "ее", "ы", "и", "а", "я", "е", "о", "у", "ю"):
        if word.endswith(suf) and len(word) - len(suf) >= 3:
            return word[: -len(suf)]
    return word


def _tokens(text: str) -> list[str]:
    return [_stem(w) for w in _WORD_RE.findall(text or "") if w.lower() not in _STOPWORDS]


@dataclass
class Document:
    category: str
    title: str
    text: str
    tokens: set[str] = field(default_factory=set)
    title_tokens: set[str] = field(default_factory=set)

    def render(self) -> str:
        return f"[{self.title}]\n{self.text}".strip()


class KnowledgeBase:
    def __init__(self, path: Path | None = None) -> None:
        if path is None:
            path = Path(settings.DATA_DIR) if settings.DATA_DIR else _DEFAULT_PATH
        self.path = path
        self.raw: dict[str, Any] = {}
        self.documents: list[Document] = []
        self.load()

    # ---------- загрузка ----------
    def load(self) -> None:
        with open(self.path, encoding="utf-8") as f:
            self.raw = yaml.safe_load(f) or {}
        self.documents = []
        self._build_documents()

    def _add(self, category: str, title: str, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        doc = Document(category=category, title=title, text=text)
        doc.tokens = set(_tokens(f"{title} {text}"))
        doc.title_tokens = set(_tokens(title))
        self.documents.append(doc)

    def _build_documents(self) -> None:
        r = self.raw
        company = r.get("company", {})
        if company:
            self._add("company", "О школе",
                      f"{company.get('name','')}. {company.get('description','')} "
                      f"{company.get('philosophy','')} Слоган: {company.get('slogan','')}")
            self._add("methodology", "Методика обучения", company.get("methodology", ""))
            self._add("company", "Режим работы", company.get("work_hours", ""))
            self._add("company", "Руководители и основатели", company.get("founders", ""))

        for adv in r.get("advantages", []):
            self._add("advantages", adv.get("title", ""), adv.get("text", ""))

        for b in r.get("branches", []):
            self._add("branches", b.get("name", "Филиал"),
                      f"Адрес: {b.get('address','')}. Телефон: {b.get('phone','')}. "
                      f"Часы работы: {b.get('work_hours','')}. Маршрут: {b.get('maps','')}")

        for fmt in r.get("formats", []):
            self._add("formats", fmt.get("name", ""),
                      f"{fmt.get('location','')}. " + "; ".join(fmt.get("details", []))
                      + f". Стоимость: {fmt.get('price','')}")

        for p in r.get("age_programs", []):
            self._add("age_programs", p.get("name", ""),
                      f"Возраст {p.get('age','')}. {p.get('text','')} Подробнее: {p.get('url','')}")

        _COURSE_LABELS = {
            "language": "Язык",
            "ages": "Возраст",
            "teacher": "Преподаватель",
            "format": "Формат",
            "price": "Стоимость",
            "trial_price": "Пробный урок",
        }
        for c in r.get("courses", []):
            parts = [c.get("description", ""), c.get("note", "")]
            meta = []
            for k, label in _COURSE_LABELS.items():
                if c.get(k):
                    meta.append(f"{label}: {c[k]}")
            if c.get("url"):
                meta.append(f"Подробнее на сайте: {c['url']}")
            self._add("courses", c.get("name", ""),
                      " ".join([p for p in parts if p]) + " " + "; ".join(meta))

        tb = r.get("textbooks")
        if tb:
            levels = tb.get("levels", [])
            overview = tb.get("summary", "") + " Уровни: " + "; ".join(
                f"{lv.get('level','')} ({lv.get('age','')}, {lv.get('year','')}, {lv.get('cefr','')})"
                for lv in levels
            )
            self._add("textbooks", tb.get("name", "Учебники"), overview)
            for lv in levels:
                self._add(
                    "textbooks",
                    f"{lv.get('level','')} — {lv.get('age','')}",
                    f"{lv.get('year','')}, уровень {lv.get('cefr','')}. {lv.get('detail','')}",
                )

        sa = r.get("summer_academy")
        if sa:
            self._add("summer_academy", sa.get("name", "Летняя Академия"),
                      f"{sa.get('note','')} Время: {sa.get('time','')}. Возраст: {sa.get('ages','')}. "
                      f"Стоимость: {sa.get('price','')}. Смены: " + "; ".join(sa.get("shifts", [])))

        for step in r.get("enrollment_steps", []):
            self._add("enrollment", f"Шаг {step.get('step')}: {step.get('title','')}",
                      step.get("text", ""))

        for item in r.get("faq", []):
            self._add("faq", item.get("q", ""), item.get("a", ""))

        for promo in r.get("promos", []):
            self._add("promos", "Акция", promo)

        social = r.get("social", {})
        if social:
            self._add("social", "Соцсети и контакты",
                      f"ВКонтакте: {social.get('vk','')}. MAX-бот: {social.get('max_bot','')}. "
                      f"MAX-канал: {social.get('max_channel','')}")

    # ---------- поиск ----------
    def search_scored(self, query: str, limit: int = 5) -> list[tuple[float, Document]]:
        q_tokens = set(_tokens(query))
        if not q_tokens:
            return []
        scored: list[tuple[float, Document]] = []
        for doc in self.documents:
            if not doc.tokens:
                continue
            overlap = q_tokens & doc.tokens
            if not overlap:
                continue
            # нормируем на длину запроса + небольшой бонус за FAQ/курсы
            score = len(overlap) / len(q_tokens)
            if doc.category in ("faq", "courses", "formats"):
                score += 0.1
            # бонус за совпадение с заголовком: профильные документы
            # («Летняя Академия», конкретные FAQ) поднимаются выше болтливых.
            title_overlap = q_tokens & doc.title_tokens
            if title_overlap:
                score += 0.4 * len(title_overlap) / len(q_tokens)
                if doc.category != "faq":
                    score += 0.3
            scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:limit]

    def search(self, query: str, limit: int = 5) -> list[Document]:
        return [d for _, d in self.search_scored(query, limit=limit)]

    def best_score(self, query: str) -> float:
        scored = self.search_scored(query, limit=1)
        return scored[0][0] if scored else 0.0

    def context_for(self, query: str, limit: int = 5) -> str:
        docs = self.search(query, limit=limit)
        return "\n\n".join(d.render() for d in docs)

    # ---------- структурированные геттеры ----------
    @property
    def branches(self) -> list[dict]:
        return self.raw.get("branches", [])

    @property
    def courses(self) -> list[dict]:
        return self.raw.get("courses", [])

    @property
    def formats(self) -> list[dict]:
        return self.raw.get("formats", [])

    @property
    def age_programs(self) -> list[dict]:
        return self.raw.get("age_programs", [])

    @property
    def social(self) -> dict:
        return self.raw.get("social", {})

    @property
    def company(self) -> dict:
        return self.raw.get("company", {})

    @property
    def faq(self) -> list[dict]:
        return self.raw.get("faq", [])

    @property
    def promos(self) -> list:
        return self.raw.get("promos", [])

    @property
    def summer_academy(self) -> dict:
        return self.raw.get("summer_academy", {})

    @property
    def enrollment_steps(self) -> list[dict]:
        return self.raw.get("enrollment_steps", [])

    @property
    def advantages(self) -> list[dict]:
        return self.raw.get("advantages", [])

    def objection(self, key: str) -> str | None:
        for o in self.raw.get("objections", []):
            if o.get("key") == key:
                return (o.get("response") or "").strip()
        return None


_kb: KnowledgeBase | None = None


def get_kb() -> KnowledgeBase:
    global _kb
    if _kb is None:
        _kb = KnowledgeBase()
    return _kb
