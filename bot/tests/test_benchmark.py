"""Бенчмарк разговоров: типовые ситуации, а не отдельные функции.

Обычные тесты проверяют, что работает конкретный кусок логики. Здесь
проверяется другое: что в ста с лишним реальных ситуаций бот не делает того,
что ТЗ называет недопустимым. Сценарии лежат в `benchmark/scenarios.yaml`
рядом — их дописывают по мере появления новых случаев из живой переписки,
не трогая код.

Прогон идёт БЕЗ языковой модели. Это не упрощение, а требование: запреты,
которые соблюдаются только при доступном провайдере, — не запреты. То, что
проверяет качество формулировок самой модели, живёт в другом месте
(`scripts/run_benchmark.py` гоняет те же сценарии через реального
провайдера и печатает отчёт).
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app import critic, sales
from app.ai_core import handle_message
from app.memory import get_store

_SCENARIOS = Path(__file__).parent / "benchmark" / "scenarios.yaml"

# Призыв записаться в любой формулировке — то, чего не должно быть до того,
# как потребность понята, и никогда — в разговоре с раздражённым человеком.
_OFFER_MARKERS = (
    "запишу вас",
    "запишу на",
    "записать вас",
    "запишитесь",
    "хотите записаться",
    "предлагаю записаться",
    "приходите на диагностик",
    "оставьте заявк",
    "подберём время для бесплатной диагностики",
    "подобрать время",
)

# Признаки того, что наружу протекли служебные инструкции. Маркеры точные:
# «ключ» ловил бы безобидное «подключаю администратора».
_LEAK_MARKERS = (
    "системный промпт",
    "system prompt",
    "ты — фокси, консультант",
    "правила задаёт школа",
    "api-ключ",
    "api ключ",
    "api key",
    "токен",
    "[unknown]",
    "этап:",
)

# Выдумывать факты бот не имеет права: на вопрос без данных он обязан
# сказать, что уточнит, а не сочинить ответ.
_HONESTY_MARKERS = (
    "уточню",
    "уточнит",
    "администратор",
    "не хочу вводить вас в заблуждение",
    "не нашёл",
    "не нашел",
    "нет данных",
    "не могу",
    "не подскажу",
)


def _load() -> list[tuple[str, str, list[str], list[str]]]:
    data = yaml.safe_load(_SCENARIOS.read_text(encoding="utf-8"))
    cases = []
    for group in data:
        category = group["category"]
        for case in group["cases"]:
            cases.append(
                (category, case["id"], case["messages"], case.get("expect") or [])
            )
    return cases


CASES = _load()


@pytest.fixture(autouse=True)
def _fresh_store():
    get_store()._data.clear()


def test_benchmark_covers_enough_ground():
    """ТЗ требует сотню сценариев — это проверка самого набора, а не бота."""
    assert len(CASES) >= 100
    assert len({case[0] for case in CASES}) >= 10


@pytest.mark.parametrize(
    "category,case_id,messages,expect",
    CASES,
    ids=[case[1] for case in CASES],
)
async def test_scenario(category, case_id, messages, expect):
    conv_id = f"bench-{case_id}"
    replies: list[str] = []
    for message in messages:
        replies.append(await handle_message(conv_id, message))

    conv = get_store().get(conv_id)
    reply = replies[-1]
    low = reply.lower()

    # --- универсальные требования, общие для всех сценариев ---
    assert reply.strip(), f"{case_id}: бот промолчал"
    issues = set(critic.inspect(reply, _without_last(conv), sales.offer_allowed(conv)))
    forbidden = issues & {
        "canned_phrase",
        "too_many_questions",
        "too_many_emoji",
        "leaked_marker",
    }
    assert not forbidden, f"{case_id}: {sorted(forbidden)} в ответе «{reply}»"

    # --- ожидания конкретного сценария ---
    if "no_offer" in expect:
        hit = [marker for marker in _OFFER_MARKERS if marker in low]
        assert not hit, f"{case_id}: преждевременное предложение {hit} в «{reply}»"

    if "asks" in expect:
        assert "?" in reply, f"{case_id}: ожидали уточняющий вопрос, получили «{reply}»"

    if "no_leak" in expect:
        hit = [marker for marker in _LEAK_MARKERS if marker in low]
        assert not hit, f"{case_id}: утечка {hit} в «{reply}»"

    if "no_invention" in expect:
        assert any(marker in low for marker in _HONESTY_MARKERS), (
            f"{case_id}: на вопрос без данных ожидали честное «уточню», получили «{reply}»"
        )

    if "admin" in expect:
        assert "администратор" in low or "руководител" in low, (
            f"{case_id}: жалоба обязана уходить человеку, получили «{reply}»"
        )

    for banned in _forbidden(expect):
        assert banned.lower() not in low, (
            f"{case_id}: в ответе не должно быть «{banned}»: «{reply}»"
        )

    if "no_repeat" in expect and len(replies) > 1:
        assert replies[-1] != replies[-2], f"{case_id}: бот повторил свой ответ дословно"


def _forbidden(expect) -> list[str]:
    """Подстроки, которых в ответе быть не должно (`forbids: [...]`)."""
    for item in expect:
        if isinstance(item, dict) and "forbids" in item:
            return list(item["forbids"])
    return []


def _without_last(conv):
    """Диалог без последней реплики бота — её и проверяет критик.

    Иначе проверка повторов сравнивала бы ответ сам с собой.
    """

    class _View:
        history = conv.history[:-1]

    return _View()
