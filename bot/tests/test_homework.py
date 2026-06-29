import pytest
from fastapi.testclient import TestClient

import app.main as main


class FakeVisionLLM:
    def __init__(self, reply: str | None = ""):
        self.reply = reply
        self.calls = []

    async def complete_vision(self, messages, temperature=None):
        self.calls.append((messages, temperature))
        return self.reply


@pytest.fixture
def client():
    return TestClient(main.app)


def test_homework_missing_file(client):
    resp = client.post("/api/miniapp/homework", files={"note": (None, "Проверить")})
    assert resp.status_code == 400
    assert "фото" in resp.json()["detail"].lower()


def test_homework_bad_content_type(client):
    resp = client.post(
        "/api/miniapp/homework",
        files={"image": ("homework.txt", b"abc", "text/plain")},
    )
    assert resp.status_code == 400
    assert "формате" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_homework_success_uses_vision_llm(monkeypatch, client):
    fake = FakeVisionLLM("1) Это задание просит вставить am/is/are.\n2) Подставьте am для I.\n3) I am nine.\n4) Проверьте с учителем.")
    monkeypatch.setattr(main, "get_llm", lambda: fake)

    resp = client.post(
        "/api/miniapp/homework",
        files={"image": ("homework.png", b"\x89PNG\r\n\x1a\n123", "image/png")},
        data={"note": "Ребёнок не понял пример"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["explanation"].startswith("1) Это задание")
    assert fake.calls
    messages, temperature = fake.calls[0]
    assert temperature == 0.2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    parts = messages[1]["content"]
    assert parts[0]["type"] == "text"
    assert "Ребёнок не понял пример" in parts[0]["text"]
    assert parts[1]["type"] == "image_url"
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")
