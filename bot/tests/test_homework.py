import pytest
from fastapi.testclient import TestClient

import app.main as main
from app import llm_gateway
from app.config import settings
from tests.conftest import make_telegram_init_data


class FakeVisionLLM:
    # Критик домашки (app/homework._critic_check) читает gateway.enabled,
    # которое читает get_llm().enabled — без атрибута заглушка падала бы
    # AttributeError вместо штатного «критик недоступен».
    enabled = True

    def __init__(self, reply: str | None = ""):
        self.reply = reply
        self.calls = []

    async def complete_vision(self, messages, temperature=None, max_tokens=None):
        self.calls.append((messages, temperature, max_tokens))
        return self.reply


TOKEN = "123456:AA-test-token"


def auth(uid: int = 777) -> dict:
    return {
        "X-Miniapp-Init-Data": make_telegram_init_data(TOKEN, telegram_user_id=uid),
        "X-Miniapp-Platform": "telegram",
    }


@pytest.fixture
def client(monkeypatch):
    # /api/miniapp/homework требует подписанную личность (финальное ревью,
    # важное #7 — эта ручка была третьей с той же дырой анонимного доступа,
    # что уже закрыли у /homework/check и /homework/voice). Тесты ниже,
    # которые проверяют штатное поведение ручки (а не саму 401-защиту),
    # ходят с подписанным initData, как и остальные тесты мини-приложения.
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", TOKEN, raising=False)
    monkeypatch.setattr(settings, "MINIAPP_AUTH_REQUIRED", True, raising=False)
    monkeypatch.setattr(settings, "MINIAPP_REQUIRE_REGISTRATION", False, raising=False)
    return TestClient(main.app)


def test_homework_missing_file(client):
    resp = client.post(
        "/api/miniapp/homework", files={"note": (None, "Проверить")}, headers=auth()
    )
    assert resp.status_code == 400
    assert "фото" in resp.json()["detail"].lower()


def test_homework_bad_content_type(client):
    resp = client.post(
        "/api/miniapp/homework",
        files={"image": ("homework.txt", b"abc", "text/plain")},
        headers=auth(),
    )
    assert resp.status_code == 400
    assert "формате" in resp.json()["detail"].lower()


def test_homework_requires_auth_before_saving_or_calling_model(monkeypatch, client):
    """Финальное ревью, важное #7 (третья ручка): анонимный запрос не должен
    доходить ни до сохранения файла, ни до платного vision-вызова."""
    fake = FakeVisionLLM("не должно вызваться")
    monkeypatch.setattr(main, "get_llm", lambda: fake)
    monkeypatch.setattr(llm_gateway, "get_llm", lambda: fake)

    resp = client.post(
        "/api/miniapp/homework",
        files={"image": ("homework.png", b"\x89PNG\r\n\x1a\n123", "image/png")},
        data={"note": "Ребёнок не понял пример"},
    )
    assert resp.status_code == 401
    assert not fake.calls


@pytest.mark.asyncio
async def test_homework_success_uses_vision_llm(monkeypatch, client):
    fake = FakeVisionLLM("1) Это задание просит вставить am/is/are.\n2) Подставьте am для I.\n3) I am nine.\n4) Проверьте с учителем.")
    monkeypatch.setattr(main, "get_llm", lambda: fake)
    # Разбор фото идёт через LLM Gateway — у него собственный шов вызова.
    monkeypatch.setattr(llm_gateway, "get_llm", lambda: fake)

    resp = client.post(
        "/api/miniapp/homework",
        files={"image": ("homework.png", b"\x89PNG\r\n\x1a\n123", "image/png")},
        data={"note": "Ребёнок не понял пример"},
        headers=auth(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["explanation"].startswith("1) Это задание")
    assert fake.calls
    messages, temperature, max_tokens = fake.calls[0]
    assert temperature == 0.2
    assert max_tokens and max_tokens >= 1000
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    parts = messages[1]["content"]
    assert parts[0]["type"] == "text"
    assert "Ребёнок не понял пример" in parts[0]["text"]
    assert parts[1]["type"] == "image_url"
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")
