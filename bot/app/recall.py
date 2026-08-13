"""Долгосрочная память: то, что человек рассказал давно.

Окно истории — двадцать сообщений. Раньше всё, что за него выходило, просто
удалялось: клиент рассказывал про ребёнка в начале разговора, а через
полчаса бот спрашивал возраст заново. Здесь выпавшие сообщения не теряются,
а сворачиваются в короткий пересказ, который дальше едет в системном промпте.

Три уровня памяти разделены по назначению:

* **краткосрочная** — `conv.history`, дословные последние реплики;
* **долгосрочная** — `conv.digest`, сжатый пересказ давнего;
* **смысловая** — `conv.need` (профиль SMART) и карточка клиента: не текст
  разговора, а извлечённые из него факты.

Сжатие делает быстрая модель, но работать обязано и без неё: если модель
недоступна, остаётся детерминированный пересказ реплик клиента. Потерять
факты хуже, чем сохранить их некрасиво.
"""
from __future__ import annotations

import logging
import re

from app.llm_gateway import ROLE_FAST, get_gateway
from app.morph import decline
from app.pii import PiiVault

logger = logging.getLogger(__name__)

# Пересказ живёт в каждом системном промпте, поэтому платный: держим его
# коротким намеренно, а не «сколько получится».
DIGEST_LIMIT = 700
# Сколько давних реплик клиента сохранит запасной пересказ.
FALLBACK_LINES = 6
FALLBACK_LINE_LIMIT = 140

_FOLD_PROMPT = """\
Ты ведёшь заметки консультанта языковой школы. Сожми историю переписки в \
короткую памятку для себя же.

Правила:
- только факты, которые сообщил клиент: про кого занятия, возраст, уровень, \
цели, сложности, формат, время, бюджет, сомнения, договорённости;
- 3-6 строк, каждая с новой строки, без нумерации;
- третье лицо, спокойный тон, без оценок и без рекламы;
- без дат, времени и цитат — только суть;
- если фактов нет, ответь одним словом: нет.
"""


def needs_fold(conv) -> bool:
    """Есть ли что сворачивать в долгосрочную память."""
    return bool(getattr(conv, "dropped", None))


async def fold(conv, vault: PiiVault | None = None) -> None:
    """Сворачивает выпавшие сообщения в `conv.digest`.

    Ничего не возвращает и никогда не бросает: сжатие памяти — фоновая
    работа, из-за которой человек не должен остаться без ответа.
    """
    if not needs_fold(conv):
        return
    dropped = list(conv.dropped)
    digest = await _fold_with_model(conv, dropped, vault)
    if not digest:
        digest = _fallback_digest(conv.digest, dropped)
    conv.digest = _trim(digest)
    conv.dropped = []


async def _fold_with_model(conv, dropped: list[dict], vault) -> str:
    gateway = get_gateway()
    if not gateway.enabled:
        return ""
    body = _transcript(dropped)
    if not body:
        return ""
    previous = f"РАНЕЕ ЗАПИСАНО:\n{conv.digest}\n\n" if conv.digest else ""
    messages = [
        {"role": "system", "content": _FOLD_PROMPT},
        {"role": "user", "content": f"{previous}ПЕРЕПИСКА:\n{body}"},
    ]
    try:
        text = await gateway.complete(ROLE_FAST, messages, vault=vault, temperature=0.1)
    except Exception:
        logger.exception("recall: сжатие памяти не удалось user_id=%s", conv.user_id)
        return ""
    text = (text or "").strip()
    if not text or text.lower().strip(" .") == "нет":
        return ""
    return text


def _transcript(messages: list[dict]) -> str:
    lines = []
    for item in messages:
        content = (item.get("content") or "").strip()
        if not content:
            continue
        who = "Клиент" if item.get("role") == "user" else "Консультант"
        lines.append(f"{who}: {content}")
    return "\n".join(lines)


def _fallback_digest(previous: str, dropped: list[dict]) -> str:
    """Пересказ без модели: реплики клиента, коротко и по порядку.

    Читается суше, чем пересказ модели, но сохраняет ровно то, ради чего всё
    затевалось, — сказанные человеком факты.
    """
    said = [
        _shorten(item.get("content") or "")
        for item in dropped
        if item.get("role") == "user" and (item.get("content") or "").strip()
    ]
    if not said:
        return previous
    block = "Клиент рассказывал: " + "; ".join(said[-FALLBACK_LINES:])
    return f"{previous}\n{block}".strip() if previous else block


def _shorten(text: str) -> str:
    flat = " ".join(text.split())
    if len(flat) <= FALLBACK_LINE_LIMIT:
        return flat
    return flat[:FALLBACK_LINE_LIMIT].rstrip() + "…"


def _trim(text: str) -> str:
    flat = text.strip()
    if len(flat) <= DIGEST_LIMIT:
        return flat
    # Режем по границе строки, чтобы не обрывать факт на половине слова.
    head = flat[:DIGEST_LIMIT]
    cut = head.rfind("\n")
    return (head[:cut] if cut > DIGEST_LIMIT // 2 else head).rstrip() + "…"


def digest_block(conv) -> str:
    """Блок долгосрочной памяти для системного промпта."""
    digest = (getattr(conv, "digest", "") or "").strip()
    if not digest:
        return ""
    return "\nИЗ ПРОШЛЫХ СООБЩЕНИЙ (помни, но не пересказывай вслух):\n" + digest


# ------------------------- возвращение клиента -------------------------

# Из «Английский для школьников» получается «английский для школьников» —
# в живой фразе название курса звучит как обычные слова, а не как заголовок.
_COURSE_CLEAN_RE = re.compile(r"\s*\(.*?\)\s*")


def returning_line(conv) -> str:
    """Чем напомнить о прошлом разговоре, если человек вернулся.

    ТЗ требует помнить по-человечески: «мы с вами обсуждали занятия для
    Маши», а не «11 августа в 14:35 вы сообщили». Поэтому здесь нет ни дат,
    ни времени, ни счётчиков — только предмет разговора.
    """
    child = (conv.child_label() or "").strip()
    subject = _subject(conv)
    if child:
        # «для Маша» выдало бы бота с головой, поэтому родительный падеж.
        whose = decline(child, "род")
        # Курс договариваем через тире, а не «про …»: приложение в
        # именительном падеже читается верно при любом названии курса.
        return f"Мы с вами обсуждали занятия для {whose}" + (
            f" — {subject}." if subject else "."
        )
    if subject:
        return f"В прошлый раз мы подбирали курс — {subject}."
    return ""


def _subject(conv) -> str:
    course = conv.recommended_program or conv.selected_course or conv.lead.course
    course = _COURSE_CLEAN_RE.sub(" ", course or "").strip()
    if course:
        return course[0].lower() + course[1:]
    need = getattr(conv, "need", None)
    if need is not None and need.child_age:
        return f"английский для ребёнка {need.child_age}"
    return ""


__all__ = [
    "DIGEST_LIMIT",
    "digest_block",
    "fold",
    "needs_fold",
    "returning_line",
]
