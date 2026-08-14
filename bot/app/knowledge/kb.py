"""База знаний: загрузка структурированных данных и интеллектуальный поиск.

KB загружает data.yaml и строит коллекцию «документов» (заголовок + текст).
Поиск — лёгкий лексический скоринг по совпадению слов запроса с документами,
устойчивый к русской морфологии за счёт усечения слов до основы.

Найденные фрагменты передаются LLM как контекст (RAG-lite), а структурированные
объекты (филиалы, курсы, форматы) используются детерминированными сценариями.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.config import settings

_DEFAULT_PATH = Path(__file__).with_name("data.yaml")
_WORD_RE = re.compile(r"[а-яёa-z0-9]+", re.IGNORECASE)
# Насколько сильнее совпадение в заголовке документа, чем в его тексте.
_TITLE_BONUS = 0.4
# Служебные слова не несут смысла для поиска. Местоимения и вопросительные
# слова здесь особенно важны: они редкие, поэтому при взвешивании по
# редкости именно они начинали перевешивать содержательные слова —
# «Кто у вас педагоги?» находило «У вас есть носитель языка?» по слову «вас».
_STOPWORDS = {
    "и", "в", "на", "с", "по", "для", "от", "до", "не", "а", "что", "как",
    "это", "у", "о", "за", "ли", "же", "бы", "то", "из", "мы", "вы", "я",
    "кто", "кого", "кому", "кем", "чем", "чём", "чего", "чему",
    "вас", "вам", "вами", "ваш", "ваша", "ваше", "ваши",
    "нас", "нам", "нами", "наш", "наша", "наше", "наши",
    "мне", "меня", "мной", "он", "она", "оно", "они", "его", "её", "ее",
    "их", "им", "ими", "ему", "ей", "там", "тут", "здесь", "там",
    "есть", "был", "была", "было", "были", "быть", "ещё", "еще",
    "или", "но", "если", "когда", "где", "куда", "почему", "зачем",
}


def _stem(word: str) -> str:
    """Грубое усечение русских окончаний, чтобы «курсы»~«курс», «детей»~«дет»,
    «работаете»~«работы» (глагольные окончания тоже срезаем)."""
    word = word.lower()
    if len(word) <= 4:
        return word
    for suf in ("иями", "ями", "ами", "ого", "его", "ому", "ему", "ыми", "ими",
                "овать", "ировать", "аете", "ете", "ает", "ять", "ать", "ить",
                "уть", "ыть", "оть", "ете", "ит", "ет", "ат",
                "ах", "ях", "ов", "ев", "ей", "ам", "ям", "ом", "ем", "ой", "ёй",
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
        self.live_documents: list[Document] = []
        # Веса слов считаются лениво и сбрасываются при смене документов.
        self._idf: dict[str, float] = {}
        self._unknown_weight: float = 1.0
        self.load()

    # ---------- загрузка ----------
    def load(self) -> None:
        with open(self.path, encoding="utf-8") as f:
            self.raw = yaml.safe_load(f) or {}
        self.documents = []
        self._idf = {}
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
            self._add("company", "Опыт и история школы", company.get("founded", ""))

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

        for c in r.get("courses", []):
            parts = [c.get("description", ""), c.get("note", "")]
            meta = []
            for k in ("language", "ages", "teacher", "format", "price", "trial_price"):
                if c.get(k):
                    meta.append(f"{k}: {c[k]}")
            self._add("courses", c.get("name", ""),
                      " ".join([p for p in parts if p]) + " " + "; ".join(meta))

        sa = r.get("summer_academy")
        if sa:
            self._add("summer_academy", sa.get("name", "Летняя Академия"),
                      f"{sa.get('note','')} Время: {sa.get('time','')}. Возраст: {sa.get('ages','')}. "
                      f"Стоимость: {sa.get('price','')}. Смены: " + "; ".join(sa.get("shifts", [])))

        for step in r.get("enrollment_steps", []):
            self._add("enrollment", f"Шаг {step.get('step')}: {step.get('title','')}",
                      step.get("text", ""))

        team = r.get("team", [])
        for person in team:
            parts = [person.get("role", ""), person.get("about", "")]
            if person.get("video_intro"):
                parts.append(f"Видеовизитка: {person['video_intro']}")
            if person.get("video_lesson"):
                parts.append(f"Фрагмент урока: {person['video_lesson']}")
            self._add("team", person.get("name", ""), ". ".join(p for p in parts if p))
        if team:
            teachers = [p for p in team if p.get("role") == "Педагог"]
            self._add(
                "team",
                "Команда: педагоги, методист, администраторы, руководители",
                "Педагоги школы: "
                + "; ".join(f"{p.get('name','')} ({p.get('about','')})" for p in teachers)
                + ". Полный список команды с видеовизитками — на сайте, раздел «Команда».",
            )

        for item in r.get("faq", []):
            self._add("faq", item.get("q", ""), item.get("a", ""))

        for promo in r.get("promos", []):
            self._add("promos", "Акция", promo)

        social = r.get("social", {})
        if social:
            self._add("social", "Соцсети и контакты",
                      f"ВКонтакте: {social.get('vk','')}. MAX-бот: {social.get('max_bot','')}. "
                      f"MAX-канал: {social.get('max_channel','')}")

        for src in r.get("sources", []):
            title = src.get("title", "Источник").strip()
            url = src.get("url", "").strip()
            text = src.get("text", "").strip()
            parts = [p for p in (text, f"URL: {url}" if url else "") if p]
            self._add("sources", title, " ".join(parts))

    def set_live_documents(self, docs: list[Document]) -> None:
        """Заменяет «живые» документы, полученные синхронизацией с сайта."""
        self.live_documents = docs
        self._idf = {}

    # ---------- поиск ----------
    def _weights(self) -> dict[str, float]:
        """Вес каждого слова: чем реже слово, тем больше оно значит.

        Без этого «сколько стоит английский» и «расписание английского»
        считались одинаково похожими на любой документ со словом
        «английский» — оно есть почти везде. Совпадение по слову «рассрочка»
        должно весить намного больше совпадения по слову «занятие».
        """
        if self._idf:
            return self._idf
        docs = self.documents + self.live_documents
        total = len(docs) or 1
        frequency: dict[str, int] = {}
        for doc in docs:
            for token in doc.tokens:
                frequency[token] = frequency.get(token, 0) + 1
        self._idf = {
            token: math.log(1 + total / count) for token, count in frequency.items()
        }
        # Слово, которого нет ни в одном документе, весит как самое редкое:
        # именно из-за него ответа в базе может не быть, и занижать его вес
        # значило бы завышать уверенность в неподходящем документе.
        self._unknown_weight = math.log(1 + total)
        return self._idf

    def _weight_of(self, token: str, weights: dict[str, float]) -> float:
        return weights.get(token, self._unknown_weight)

    def search_scored(self, query: str, limit: int = 5) -> list[tuple[float, Document]]:
        q_tokens = set(_tokens(query))
        if not q_tokens:
            return []
        weights = self._weights()
        total_weight = sum(self._weight_of(t, weights) for t in q_tokens) or 1.0
        scored: list[tuple[float, Document]] = []
        for doc in self.documents + self.live_documents:
            if not doc.tokens:
                continue
            overlap = q_tokens & doc.tokens
            if not overlap:
                continue
            # Доля «смысловой массы» запроса, которую покрыл документ,
            # плюс небольшой бонус разделам, где чаще лежит прямой ответ.
            score = sum(self._weight_of(t, weights) for t in overlap) / total_weight
            # Совпадение в заголовке — куда более сильное свидетельство, чем
            # то же слово где-то в тексте: заголовок это и есть тема
            # документа. Без этого запрос из одного слова давал одинаковый
            # балл всем документам, где оно вообще встречается.
            in_title = q_tokens & doc.title_tokens
            if in_title:
                score += _TITLE_BONUS * (
                    sum(self._weight_of(t, weights) for t in in_title) / total_weight
                )
            if doc.category in ("faq", "courses", "formats", "team"):
                score += 0.1
            scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:limit]

    def search(self, query: str, limit: int = 5) -> list[Document]:
        return [d for _, d in self.search_scored(query, limit=limit)]

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
    def sources(self) -> list[dict]:
        return self.raw.get("sources", [])

    @property
    def company(self) -> dict:
        return self.raw.get("company", {})

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
