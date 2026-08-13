"""Понимание намерения там, где ключевых слов не хватило.

Регулярки разбирают большинство сообщений мгновенно и бесплатно, поэтому
остаются первым слоем. Но они видят слова, а не смысл: «хотелось бы уже
начать, только не знаю, с чего» не содержит ни одного слова из списка и
уходит в общий ответ, хотя человек фактически просится записаться.

Второй слой включается ровно там, где первый ничего не понял, — когда
`detect_intent` вернул общий QUESTION. Это важно и по деньгам, и по
задержке: за разбор платим только в неоднозначных случаях, а поведение всех
уже работающих сценариев не меняется.

Модель не может «перебить» уверенный разбор регуляркой и не может выдумать
своё намерение: ответ принимается, только если это одна из известных меток
и уверенность выше порога. Всё остальное трактуется как «непонятно» —
общий консультативный ответ безопаснее неверного маршрута.
"""
from __future__ import annotations

import logging

from app import intent as I
from app.llm_gateway import ROLE_FAST, get_gateway
from app.pii import PiiVault

logger = logging.getLogger(__name__)

# Ниже этого порога маршрут не меняем: неверно понятое намерение уводит
# разговор в сторону заметнее, чем общий ответ по существу.
MIN_CONFIDENCE = 0.6
# Совсем короткие реплики («ок», «а это как?») разбирать нечего.
MIN_TEXT_LEN = 15
# Сколько последних реплик показать модели: намерение часто ясно только в
# контексте предыдущего вопроса бота.
CONTEXT_MESSAGES = 4

_LABELS = (
    I.PRICE,
    I.COURSES,
    I.CONTACTS,
    I.ABOUT,
    I.WANT_SIGNUP,
    I.REGISTER,
    I.HOMEWORK,
    I.OBJECTION,
    I.HANDOFF,
    I.GREETING,
    I.QUESTION,
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": list(_LABELS)},
        "confidence": {"type": "number"},
    },
    "required": ["intent", "confidence"],
}

_PROMPT = """\
Определи, чего человек хочет от языковой школы. Верни одну метку:

- price — спрашивает про стоимость, оплату, скидки;
- courses — спрашивает про программы, направления, уровни, форматы;
- contacts — адрес, филиал, телефон, время работы;
- about — школа, методика, педагоги, лицензия, результаты, отзывы;
- want_signup — хочет начать заниматься, записаться, попробовать;
- register — просит доступ в личный кабинет;
- homework — просит помочь с домашним заданием;
- objection — сомневается, считает дорогим, хочет подумать;
- handoff — просит живого человека, жалуется, требует решения;
- greeting — просто здоровается;
- question — всё остальное или непонятно.

confidence — от 0 до 1, насколько ты уверен. Если сомневаешься, ставь \
question с низкой уверенностью. Не выдумывай меток вне списка.
"""


async def refine(
    text: str, history: list[dict] | None = None, vault: PiiVault | None = None
) -> str | None:
    """Намерение по смыслу или None, если разобрать не удалось.

    Никогда не бросает: слой необязательный, и вызывающий обязан работать
    без него ровно так же, как работал до его появления.
    """
    if len(text.strip()) < MIN_TEXT_LEN:
        return None
    gateway = get_gateway()
    if not gateway.enabled:
        return None

    messages = [{"role": "system", "content": _PROMPT}]
    messages.extend(_context(history))
    messages.append({"role": "user", "content": f"СООБЩЕНИЕ:\n{text}"})

    try:
        result = await gateway.structured(
            ROLE_FAST, messages, _SCHEMA, name="intent", vault=vault
        )
    except Exception:
        logger.exception("intent_ai: разбор намерения не удался")
        return None
    if not result:
        return None

    label = str(result.get("intent") or "")
    if label not in _LABELS or label == I.QUESTION:
        return None
    try:
        confidence = float(result.get("confidence") or 0.0)
    except (TypeError, ValueError):
        return None
    return label if confidence >= MIN_CONFIDENCE else None


def _context(history: list[dict] | None) -> list[dict]:
    """Последние реплики как есть: намерение часто читается только в контексте."""
    if not history:
        return []
    recent = [m for m in history[-CONTEXT_MESSAGES:] if m.get("content")]
    if not recent:
        return []
    lines = [
        f"{'Клиент' if m.get('role') == 'user' else 'Консультант'}: {m['content']}"
        for m in recent
    ]
    return [{"role": "user", "content": "КОНТЕКСТ РАЗГОВОРА:\n" + "\n".join(lines)}]


__all__ = ["MIN_CONFIDENCE", "refine"]
