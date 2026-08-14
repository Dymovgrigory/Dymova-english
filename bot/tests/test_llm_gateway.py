"""LLM Gateway: роли моделей, structured output и защита персональных данных."""
from __future__ import annotations

import json

import pytest

from app import llm_gateway
from app.config import settings
from app.llm_gateway import (
    ROLE_CRITIC,
    ROLE_FAST,
    ROLE_REASONING,
    LLMGateway,
    _extract_object,
    _matches,
    _parse_json,
)
from app.memory import Conversation, Lead
from app.pii import PiiVault, redact_messages, vault_for


class FakeLLM:
    """Заглушка транспорта: пишет вызовы и отдаёт заготовленные ответы."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls: list[dict] = []
        self.enabled = True

    async def complete(self, messages, temperature=None, **kwargs):
        self.calls.append({"messages": messages, "temperature": temperature, **kwargs})
        if not self.replies:
            return None
        return self.replies.pop(0)


@pytest.fixture
def gateway(monkeypatch):
    llm_gateway.reset_gateway()

    def install(replies):
        fake = FakeLLM(replies)
        monkeypatch.setattr(llm_gateway, "get_llm", lambda: fake)
        return LLMGateway(), fake

    return install


SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string"},
        "confidence": {"type": "number"},
        "sales_allowed": {"type": "boolean"},
    },
    "required": ["intent", "confidence", "sales_allowed"],
}


# --------------------------- PII ---------------------------

def test_vault_hides_and_restores_names():
    vault = PiiVault()
    vault.hide("CHILD_NAME", "Маша")
    redacted = vault.redact("Маша уже занималась английским")
    assert "Маша" not in redacted
    assert "{{CHILD_NAME}}" in redacted
    assert vault.restore("Запишем {{CHILD_NAME:вин}}?") == "Запишем Машу?"
    assert vault.restore("Это {{CHILD_NAME}}") == "Это Маша"


def test_vault_hides_phone_typed_inline():
    """Телефон прячется, даже если его ещё нет в лиде."""
    vault = PiiVault()
    redacted = vault.redact("мой номер 8 916 732-31-69, звоните")
    assert "916" not in redacted
    assert "{{PHONE}}" in redacted
    assert "732-31-69" in vault.restore(redacted)


def test_vault_prefers_longer_values():
    """«Иванова Анна» не должна разваливаться на подмену только фамилии."""
    vault = PiiVault()
    vault.hide("PARENT_LAST", "Иванова")
    vault.hide("PARENT_NAME", "Иванова Анна")
    redacted = vault.redact("Здравствуйте, Иванова Анна")
    assert "Анна" not in redacted


def test_vault_ignores_too_short_values():
    """Двухбуквенное значение искалечило бы обычный текст."""
    vault = PiiVault()
    assert vault.hide("CHILD_NAME", "Ян") == "Ян"
    assert vault.redact("Январь начнётся с диагностики") == "Январь начнётся с диагностики"


def test_vault_for_conversation_covers_lead_fields():
    conv = Conversation(user_id="u1")
    conv.lead = Lead(fio_parent="Иванова Анна", fio_child="Маша", phone="+79161112233")
    vault = vault_for(conv)
    redacted = vault.redact("Иванова Анна записывает Машу, телефон +79161112233")
    assert "Иванова" not in redacted and "Маша" not in redacted and "9161112233" not in redacted
    assert vault.restore(redacted) == "Иванова Анна записывает Машу, телефон +79161112233"


def test_redact_messages_passes_multimodal_content_through():
    """Картинку редактировать нечем — блок должен пройти нетронутым."""
    vault = PiiVault()
    vault.hide("CHILD_NAME", "Маша")
    image_block = {"role": "user", "content": [{"type": "image_url", "image_url": {"url": "data:x"}}]}
    result = redact_messages(vault, [{"role": "user", "content": "Маша"}, image_block])
    assert result[0]["content"] == "{{CHILD_NAME}}"
    assert result[1] is image_block


async def test_complete_never_leaks_pii_and_restores_reply(gateway):
    gw, fake = gateway(["Отлично, записываю {{CHILD_NAME:вин}} на диагностику"])
    vault = PiiVault()
    vault.hide("CHILD_NAME", "Маша")

    reply = await gw.complete(
        ROLE_REASONING, [{"role": "user", "content": "Маша хочет заниматься"}], vault=vault
    )

    sent = json.dumps(fake.calls[0]["messages"], ensure_ascii=False)
    assert "Маша" not in sent
    assert reply == "Отлично, записываю Машу на диагностику"


# --------------------------- роли ---------------------------

def test_role_model_read_from_settings(monkeypatch, gateway):
    gw, _ = gateway([])
    monkeypatch.setattr(settings, "LLM_ROLE_FAST", "claude-haiku-4-5")
    monkeypatch.setattr(settings, "LLM_ROLE_REASONING", "")
    assert gw.model_for(ROLE_FAST) == "claude-haiku-4-5"
    assert gw.model_for(ROLE_REASONING) is None


async def test_role_model_passed_to_transport(monkeypatch, gateway):
    gw, fake = gateway(["ок"])
    monkeypatch.setattr(settings, "LLM_ROLE_CRITIC", "claude-haiku-4-5")
    await gw.complete(ROLE_CRITIC, [{"role": "user", "content": "оцени"}])
    assert fake.calls[0]["model"] == "claude-haiku-4-5"


async def test_fast_roles_get_smaller_time_budget(monkeypatch, gateway):
    """Служебная роль не должна съедать бюджет, отведённый на ответ клиенту."""
    gw, fake = gateway(["ок", "ок"])
    await gw.complete(ROLE_REASONING, [{"role": "user", "content": "?"}])
    await gw.complete(ROLE_FAST, [{"role": "user", "content": "?"}])
    assert fake.calls[1]["budget_scale"] < fake.calls[0]["budget_scale"]


# --------------------------- structured output ---------------------------

async def test_structured_uses_native_schema_first(gateway):
    gw, fake = gateway(['{"intent":"price","confidence":0.9,"sales_allowed":false}'])
    result = await gw.structured(ROLE_FAST, [{"role": "user", "content": "сколько стоит"}], SCHEMA)
    assert result == {"intent": "price", "confidence": 0.9, "sales_allowed": False}
    assert fake.calls[0]["extra_payload"]["response_format"]["type"] == "json_schema"
    assert fake.calls[0]["raw"] is True


async def test_structured_falls_back_to_prompt_when_schema_rejected(gateway):
    """Провайдер отверг response_format — переходим на инструкцию в промпте."""
    gw, fake = gateway([None, '{"intent":"faq","confidence":0.5,"sales_allowed":true}'])
    result = await gw.structured(ROLE_FAST, [{"role": "user", "content": "а где вы"}], SCHEMA)
    assert result["intent"] == "faq"
    assert len(fake.calls) == 2
    assert "extra_payload" not in fake.calls[1] or fake.calls[1]["extra_payload"] is None
    assert "ТОЛЬКО валидным JSON" in fake.calls[1]["messages"][-1]["content"]


async def test_structured_remembers_schema_is_unsupported(gateway):
    """Второй запрос не тратит попытку на заведомо неподдерживаемую схему."""
    gw, fake = gateway([None, '{"intent":"faq","confidence":0.5,"sales_allowed":true}',
                        '{"intent":"price","confidence":0.4,"sales_allowed":false}'])
    await gw.structured(ROLE_FAST, [{"role": "user", "content": "1"}], SCHEMA)
    fake.calls.clear()
    await gw.structured(ROLE_FAST, [{"role": "user", "content": "2"}], SCHEMA)
    assert len(fake.calls) == 1
    assert fake.calls[0].get("extra_payload") is None


async def test_structured_returns_none_when_answer_unparseable(gateway):
    gw, _ = gateway(["я не понял вопроса", "тоже не понял"])
    assert await gw.structured(ROLE_FAST, [{"role": "user", "content": "?"}], SCHEMA) is None


async def test_structured_rejects_answer_missing_required_field(gateway):
    """Неполный объект хуже отсутствия ответа: вызывающий примет решение вслепую."""
    gw, _ = gateway(['{"intent":"price"}', '{"intent":"price"}'])
    assert await gw.structured(ROLE_FAST, [{"role": "user", "content": "?"}], SCHEMA) is None


async def test_structured_restores_pii_inside_parsed_object(gateway):
    gw, fake = gateway(['{"intent":"signup","confidence":1.0,"sales_allowed":true,'
                        '"note":"записать {{CHILD_NAME:вин}}"}'])
    vault = PiiVault()
    vault.hide("CHILD_NAME", "Маша")
    result = await gw.structured(
        ROLE_FAST, [{"role": "user", "content": "запишите Машу"}], SCHEMA, vault=vault
    )
    assert result["note"] == "записать Машу"
    assert "Маша" not in json.dumps(fake.calls[0]["messages"], ensure_ascii=False)


async def test_gateway_survives_transport_exception(monkeypatch, gateway):
    """Падение транспорта — это None, а не исключение наверх."""
    gw, fake = gateway([])

    async def boom(*args, **kwargs):
        raise RuntimeError("сеть отвалилась")

    monkeypatch.setattr(fake, "complete", boom)
    assert await gw.complete(ROLE_FAST, [{"role": "user", "content": "?"}]) is None
    assert gw.stats()[ROLE_FAST]["failures"] == 1


# --------------------------- разбор JSON ---------------------------

def test_parse_json_handles_markdown_fence():
    assert _parse_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_parse_json_ignores_text_after_object():
    """Модель любит дописывать фразу после JSON — она не должна ломать разбор."""
    assert _parse_json('{"a": 1}\n\nНадеюсь, это помогло!') == {"a": 1}


def test_parse_json_handles_braces_inside_strings():
    assert _extract_object('{"text": "скобка } внутри", "n": 2}') == {
        "text": "скобка } внутри",
        "n": 2,
    }


def test_parse_json_rejects_non_object():
    assert _parse_json("[1, 2, 3]") is None
    assert _parse_json("") is None
    assert _parse_json(None) is None


def test_matches_rejects_bool_for_number_field():
    """True прошло бы как int — bool в Python наследник int."""
    schema = {"type": "object", "properties": {"n": {"type": "number"}}, "required": ["n"]}
    assert _matches({"n": 0.5}, schema)
    assert not _matches({"n": True}, schema)


def test_matches_allows_extra_fields():
    schema = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}
    assert _matches({"a": "x", "b": 1}, schema)
