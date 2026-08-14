"""AI Critic: проверка ответа до того, как его увидит человек.

Модель может нарушить любое правило промпта — не по злому умыслу, а потому
что промпт это текст, а не гарантия. Здесь стоит второй слой: ответ
проверяется по списку запретов из ТЗ и либо чинится, либо переписывается.

Проверки разделены осознанно:

* **Детерминированные** — работают всегда, стоят ноль и ловят ровно то, что
  ТЗ называет недопустимым: дежурные восторги, предложение записаться до
  выявления потребности, простыня вопросов, повтор предыдущей реплики,
  утечка служебных маркеров. Часть из них чинится на месте: вырезать
  «Отличный вопрос!» дешевле и надёжнее, чем просить модель переписать.
* **Модельная** — необязательная, работает быстрой моделью и оценивает то,
  что регуляркой не поймать: естественность, эмпатию, соответствие вопросу.

Критик никогда не блокирует ответ: если починить нельзя, а переписать не
вышло, пользователь получает исходный текст. Молчание хуже неидеальной
реплики.
"""
from __future__ import annotations

import difflib
import logging
import re

from app.llm_gateway import ROLE_CRITIC, get_gateway
from app.pii import PiiVault

logger = logging.getLogger(__name__)

# --- 1. Дежурные восторги. ТЗ запрещает их прямым списком. ---
_CANNED_RE = re.compile(
    r"(?:^|(?<=[.!?…]\s))\s*(?:"
    r"Отличный вопрос!?|Прекрасный вопрос!?|Хороший вопрос!?|"
    r"С удовольствием помогу!?|С радостью помогу!?|Буду рад помочь!?|"
    r"Замечательно!?|Прекрасно!?|Великолепно!?|"
    r"Это прекрасная возможность!?|У нас есть отличное предложение!?"
    r")\s*",
    re.IGNORECASE,
)

# --- 2. Призывы к действию: запрещены, пока потребность не выявлена. ---
_CTA_RE = re.compile(
    r"запиш[уеё]м?\s+вас|запишитесь|записать\s+вас|хотите\s+записаться|"
    r"предлагаю\s+записаться|приходите\s+на\s+диагностик|оставьте\s+заявк|"
    r"запишу\s+на\s+(?:бесплатн\w+\s+)?диагностик|"
    r"давайте\s+запишем|записать\s+на\s+пробн",
    re.IGNORECASE,
)

# --- 3. Служебные маркеры, которые не должны попасть к человеку. ---
_LEAK_RE = re.compile(
    r"\[UNKNOWN\]|\{\{[A-Z_]+(?::[а-я]+)?\}\}|"
    r"ЭТАП:|КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ|ЧТО МЫ УЖЕ ПОНЯЛИ О КЛИЕНТЕ|"
    r"СИСТЕМНЫЙ ПРОМПТ|system prompt|ИЗ ИНТЕРНЕТА",
    re.IGNORECASE,
)

_EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF☀-➿]")

# Три и больше вопросительных знака — это уже анкета, а не реплика.
MAX_QUESTIONS = 2
# Больше двух эмодзи в одном сообщении читается как навязчивая бодрость.
MAX_EMOJI = 2
# Насколько ответ должен совпасть с прошлым, чтобы считаться повтором.
REPEAT_RATIO = 0.92

# Проблемы, которые можно устранить прямо в тексте.
FIXABLE = frozenset({"canned_phrase", "too_many_emoji", "leaked_marker"})


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?…])\s+", text.strip()) if s]


def inspect(reply: str, conv, sales_allowed: bool) -> list[str]:
    """Список проблем ответа. Пустой список — ответ можно отправлять."""
    issues: list[str] = []
    if not reply or not reply.strip():
        return ["empty"]

    if _CANNED_RE.search(reply):
        issues.append("canned_phrase")

    if not sales_allowed and _CTA_RE.search(reply):
        issues.append("premature_sales")

    if reply.count("?") > MAX_QUESTIONS:
        issues.append("too_many_questions")

    if len(_EMOJI_RE.findall(reply)) > MAX_EMOJI:
        issues.append("too_many_emoji")

    if _LEAK_RE.search(reply):
        issues.append("leaked_marker")

    if _repeats_previous(reply, conv):
        issues.append("repeats_previous")

    return issues


def _repeats_previous(reply: str, conv) -> bool:
    """Не повторяет ли бот сам себя почти дословно.

    Повтор — самая заметная для человека поломка: он видит, что его не
    слышат. Сравниваем с последними ответами бота, а не только с последним:
    чередование двух одинаковых реплик выглядит так же плохо.
    """
    history = getattr(conv, "history", None) or []
    previous = [
        m.get("content", "") for m in history[-6:] if m.get("role") == "assistant"
    ]
    normalized = " ".join(reply.lower().split())
    for item in previous:
        other = " ".join((item or "").lower().split())
        if not other:
            continue
        if difflib.SequenceMatcher(None, normalized, other).ratio() >= REPEAT_RATIO:
            return True
    return False


def repair(reply: str, issues: list[str]) -> str:
    """Чинит то, что чинится текстом. Остальное оставляет вызывающему.

    Вырезать дежурную фразу дешевле и надёжнее, чем просить модель
    переписать весь ответ: меньше задержка и нет риска потерять факты.
    """
    fixed = reply
    if "canned_phrase" in issues:
        fixed = _CANNED_RE.sub("", fixed)
    if "leaked_marker" in issues:
        fixed = _LEAK_RE.sub("", fixed)
    if "too_many_emoji" in issues:
        fixed = _trim_emoji(fixed, MAX_EMOJI)
    # Чистим следы вырезанного: двойные пробелы, пробел перед знаком и
    # осиротевшую пунктуацию. Без этого вырезанный токен оставлял дыру:
    # «А сколько лет ?» вместо «А сколько лет Маше?».
    fixed = re.sub(r"[ \t]{2,}", " ", fixed)
    fixed = re.sub(r"\s+([,.!?;:…])", r"\1", fixed)
    fixed = re.sub(r"\n{3,}", "\n\n", fixed)
    fixed = re.sub(r"^\s*[,.;:!]\s*", "", fixed)
    fixed = fixed.strip()
    if not fixed:
        # Ответ состоял из одних нарушений — чинить нечего, пусть решает
        # вызывающий (обычно это означает регенерацию).
        return reply.strip()
    return fixed[0].upper() + fixed[1:] if fixed[0].islower() else fixed


def _trim_emoji(text: str, keep: int) -> str:
    seen = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal seen
        seen += 1
        return match.group(0) if seen <= keep else ""

    return _EMOJI_RE.sub(replace, text)


def needs_rewrite(issues: list[str]) -> bool:
    """Есть ли среди проблем такие, что текстом их не исправить."""
    return bool(set(issues) - FIXABLE)


def feedback(issues: list[str]) -> str:
    """Замечания для повторной генерации — человеческим языком, не кодами."""
    notes = {
        "premature_sales": (
            "не предлагай записаться, диагностику или пробное занятие — "
            "потребность собеседника ещё не выяснена"
        ),
        "too_many_questions": "задай не больше одного вопроса",
        "repeats_previous": "не повторяй свой предыдущий ответ, скажи иначе",
        "canned_phrase": "без дежурных восторгов вроде «Отличный вопрос!»",
        "too_many_emoji": "не больше одного-двух эмодзи",
        "leaked_marker": "не вставляй служебные пометки и токены",
        "empty": "дай содержательный ответ",
    }
    listed = [notes[i] for i in issues if i in notes]
    if not listed:
        return ""
    return "Перепиши предыдущий ответ: " + "; ".join(listed) + "."


# ---------------------------- модельная оценка ----------------------------

_SCORE_SCHEMA = {
    "type": "object",
    "properties": {
        "natural": {"type": "integer"},
        "relevant": {"type": "integer"},
        "empathy": {"type": "integer"},
        "sales_pressure": {"type": "integer"},
        "verdict": {"type": "string", "enum": ["ok", "rewrite"]},
        "reason": {"type": "string"},
    },
    "required": ["natural", "relevant", "sales_pressure", "verdict"],
}

_SCORE_PROMPT = """\
Ты — придирчивый редактор переписки языковой школы. Оцени ПОСЛЕДНИЙ ответ \
консультанта по шкале 1-5:

- natural: похоже на живого человека, а не на шаблон;
- relevant: отвечает именно на то, о чём спросили;
- empathy: уместно реагирует на эмоцию собеседника;
- sales_pressure: насколько давит продажей (1 — не давит, 5 — навязчив).

verdict = "rewrite", только если ответ действительно плохой: не отвечает на \
вопрос, давит продажей, звучит шаблонно или повторяет предыдущую реплику. \
В остальных случаях "ok". В reason — одна короткая фраза, что поправить.
"""


async def score(
    reply: str, user_text: str, vault: PiiVault | None = None
) -> dict | None:
    """Оценка ответа быстрой моделью. None — оценить не удалось.

    Необязательна: вызывающий обязан работать и без неё.
    """
    gateway = get_gateway()
    if not gateway.enabled:
        return None
    messages = [
        {"role": "system", "content": _SCORE_PROMPT},
        {
            "role": "user",
            "content": f"ВОПРОС КЛИЕНТА:\n{user_text}\n\nОТВЕТ КОНСУЛЬТАНТА:\n{reply}",
        },
    ]
    try:
        return await gateway.structured(
            ROLE_CRITIC, messages, _SCORE_SCHEMA, name="reply_score", vault=vault
        )
    except Exception:
        logger.exception("critic: оценка ответа не удалась")
        return None


__all__ = [
    "FIXABLE",
    "MAX_EMOJI",
    "MAX_QUESTIONS",
    "feedback",
    "inspect",
    "needs_rewrite",
    "repair",
    "score",
]
