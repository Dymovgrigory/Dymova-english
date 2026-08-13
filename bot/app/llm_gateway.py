"""LLM Gateway: выбор модели под задачу, structured output, защита ПДн.

Зачем слой поверх `app.llm`:

1. **Роли вместо одной модели.** Диалог с клиентом и классификация намерения —
   разные задачи: первой нужна лучшая модель, второй хватит быстрой и дешёвой.
   Роль задаётся переменной окружения, поэтому смена модели — правка `.env`,
   а не кода.
2. **Structured output.** Внутренние решения бота (намерение, потребность,
   оценка ответа) должны приходить объектом, а не текстом, который потом
   разбирают регулярками. Провайдеры поддерживают JSON-схемы неодинаково,
   поэтому здесь есть деградация: схема → инструкция в промпте → устойчивый
   разбор ответа.
3. **ПДн не уходят наружу.** Имена, телефоны и даты подменяются
   плейсхолдерами до отправки и восстанавливаются после (см. `app.pii`).

Gateway никогда не бросает исключение: любая неудача — это `None`, который
вызывающий обязан обработать так же, как отсутствие LLM.
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field

from app.config import settings
from app.llm import get_llm
from app.pii import PiiVault, redact_messages

logger = logging.getLogger(__name__)

ROLE_REASONING = "reasoning"
ROLE_FAST = "fast"
ROLE_VISION = "vision"
ROLE_CRITIC = "critic"

_ROLE_SETTING = {
    ROLE_REASONING: "LLM_ROLE_REASONING",
    ROLE_FAST: "LLM_ROLE_FAST",
    ROLE_VISION: "LLM_ROLE_VISION",
    ROLE_CRITIC: "LLM_ROLE_CRITIC",
}

# Быстрым ролям незачем занимать весь бюджет каскада: они обслуживают
# служебные решения, а не ответ пользователю, и обязаны уступить время
# основной генерации.
_ROLE_BUDGET_SCALE = {
    ROLE_REASONING: 1.0,
    ROLE_FAST: 0.35,
    ROLE_CRITIC: 0.35,
    ROLE_VISION: 2.0,
}

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)

_JSON_INSTRUCTION = (
    "Ответь ТОЛЬКО валидным JSON-объектом по схеме ниже. Без markdown, без "
    "пояснений, без текста до или после JSON.\n\nСХЕМА:\n{schema}"
)


@dataclass
class RoleStats:
    """Счётчики по роли — попадают в /health и логи, а не в отдельную систему."""

    calls: int = 0
    failures: int = 0
    total_seconds: float = 0.0

    def as_dict(self) -> dict:
        avg = self.total_seconds / self.calls if self.calls else 0.0
        return {
            "calls": self.calls,
            "failures": self.failures,
            "avg_seconds": round(avg, 2),
        }


@dataclass
class LLMGateway:
    _stats: dict[str, RoleStats] = field(default_factory=dict)
    # Провайдер один раз ответил отказом на JSON-схему — больше не тратим на
    # неё попытку в каждом запросе, сразу идём инструкцией в промпте.
    _schema_unsupported: bool = False

    @property
    def enabled(self) -> bool:
        return get_llm().enabled

    def model_for(self, role: str) -> str | None:
        """Модель для роли. None — использовать модель провайдера по умолчанию."""
        name = _ROLE_SETTING.get(role)
        if not name:
            return None
        return (getattr(settings, name, "") or "").strip() or None

    async def complete(
        self,
        role: str,
        messages: list[dict],
        *,
        vault: PiiVault | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str | None:
        """Свободный текстовый ответ модели, назначенной на роль."""
        outgoing = redact_messages(vault, messages) if vault else messages
        reply = await self._call(
            role,
            outgoing,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if reply is None:
            return None
        return vault.restore(reply) if vault else reply

    async def structured(
        self,
        role: str,
        messages: list[dict],
        schema: dict,
        *,
        name: str = "result",
        vault: PiiVault | None = None,
        temperature: float = 0.0,
    ) -> dict | None:
        """Ответ модели, разобранный в объект по схеме. None — не получилось.

        Порядок попыток: нативная JSON-схема провайдера → та же схема
        инструкцией в промпте. Вторая попытка нужна, потому что часть
        OpenAI-совместимых провайдеров либо игнорирует `response_format`,
        либо отвечает на него 400.
        """
        outgoing = redact_messages(vault, messages) if vault else messages

        if not self._schema_unsupported:
            payload = {
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": name, "strict": True, "schema": schema},
                }
            }
            raw = await self._call(
                role, outgoing, temperature=temperature, extra_payload=payload, raw=True
            )
            parsed = _parse_json(raw)
            if parsed is not None and _matches(parsed, schema):
                return _restore_values(parsed, vault)
            if raw is None:
                # Провайдер не принял запрос со схемой — дальше не пробуем.
                self._schema_unsupported = True
                logger.info("gateway: провайдер не принял json_schema, перехожу на промпт")

        instructed = list(outgoing) + [
            {
                "role": "user",
                "content": _JSON_INSTRUCTION.format(
                    schema=json.dumps(schema, ensure_ascii=False)
                ),
            }
        ]
        raw = await self._call(role, instructed, temperature=temperature, raw=True)
        parsed = _parse_json(raw)
        if parsed is None or not _matches(parsed, schema):
            self._mark_failure(role)
            return None
        return _restore_values(parsed, vault)

    async def vision(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1200,
    ) -> str | None:
        """Мультимодальный запрос. Картинки редакции не подлежат — только текст."""
        model = self.model_for(ROLE_VISION)
        started = time.monotonic()
        stats = self._stats.setdefault(ROLE_VISION, RoleStats())
        stats.calls += 1
        try:
            llm = get_llm()
            if model:
                reply = await llm.complete(
                    messages,
                    temperature,
                    model=model,
                    max_tokens=max_tokens,
                    raw=True,
                    budget_scale=_ROLE_BUDGET_SCALE[ROLE_VISION],
                )
            else:
                # Без явной vision-модели остаёмся на исторической реализации:
                # она уже умеет удваивать бюджет и не фильтровать язык.
                reply = await llm.complete_vision(
                    messages, temperature=temperature, max_tokens=max_tokens
                )
        except Exception:
            logger.exception("gateway: vision-запрос упал")
            reply = None
        finally:
            stats.total_seconds += time.monotonic() - started
        if reply is None:
            stats.failures += 1
        return reply

    async def _call(
        self,
        role: str,
        messages: list[dict],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        extra_payload: dict | None = None,
        raw: bool = False,
    ) -> str | None:
        stats = self._stats.setdefault(role, RoleStats())
        stats.calls += 1
        started = time.monotonic()
        try:
            reply = await get_llm().complete(
                messages,
                temperature,
                model=self.model_for(role),
                max_tokens=max_tokens,
                extra_payload=extra_payload,
                raw=raw,
                budget_scale=_ROLE_BUDGET_SCALE.get(role, 1.0),
            )
        except Exception:
            logger.exception("gateway: запрос роли %s упал", role)
            reply = None
        finally:
            stats.total_seconds += time.monotonic() - started
        if reply is None:
            stats.failures += 1
        return reply

    def _mark_failure(self, role: str) -> None:
        self._stats.setdefault(role, RoleStats()).failures += 1

    def stats(self) -> dict:
        return {role: value.as_dict() for role, value in self._stats.items()}


def _parse_json(raw: str | None) -> dict | None:
    """Достаёт JSON-объект из ответа модели, что бы она вокруг него ни написала."""
    if not raw:
        return None
    text = raw.strip()
    fenced = _JSON_FENCE_RE.search(text)
    if fenced:
        text = fenced.group(1).strip()
    try:
        value = json.loads(text)
    except (ValueError, TypeError):
        value = _extract_object(text)
    return value if isinstance(value, dict) else None


def _extract_object(text: str) -> dict | None:
    """Первый сбалансированный {...} в тексте.

    Считать скобки, а не искать первую `{` и последнюю `}`, обязательно:
    модель часто добавляет фразу после JSON, и жадный срез захватывает её.
    """
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    value = json.loads(text[start : index + 1])
                except (ValueError, TypeError):
                    return None
                return value if isinstance(value, dict) else None
    return None


_TYPE_CHECKS = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
}


def _matches(value: dict, schema: dict) -> bool:
    """Проверка обязательных полей и их типов.

    Намеренно не полная реализация JSON Schema: тащить зависимость ради
    проверки «пришли ли required-ключи нужного типа» не окупается, а более
    строгая валидация отбраковывала бы годные ответы из-за мелочей.
    """
    required = schema.get("required") or []
    properties = schema.get("properties") or {}
    for key in required:
        if key not in value:
            logger.info("gateway: в ответе нет обязательного поля %s", key)
            return False
        expected = (properties.get(key) or {}).get("type")
        checker = _TYPE_CHECKS.get(expected) if isinstance(expected, str) else None
        if checker is None:
            continue
        item = value[key]
        # bool — подкласс int в Python, поэтому True прошло бы как integer.
        if expected in ("integer", "number") and isinstance(item, bool):
            logger.info("gateway: поле %s пришло булевым вместо числа", key)
            return False
        if not isinstance(item, checker):
            logger.info("gateway: поле %s имеет неожиданный тип %s", key, type(item).__name__)
            return False
    return True


def _restore_values(value: dict, vault: PiiVault | None):
    """Разворачивает плейсхолдеры внутри разобранного объекта."""
    if not vault:
        return value
    if isinstance(value, dict):
        return {key: _restore_values(item, vault) for key, item in value.items()}
    if isinstance(value, list):
        return [_restore_values(item, vault) for item in value]
    if isinstance(value, str):
        return vault.restore(value)
    return value


_gateway: LLMGateway | None = None


def get_gateway() -> LLMGateway:
    global _gateway
    if _gateway is None:
        _gateway = LLMGateway()
    return _gateway


def reset_gateway() -> None:
    """Сброс между тестами."""
    global _gateway
    _gateway = None


__all__ = [
    "LLMGateway",
    "ROLE_CRITIC",
    "ROLE_FAST",
    "ROLE_REASONING",
    "ROLE_VISION",
    "get_gateway",
    "reset_gateway",
]
