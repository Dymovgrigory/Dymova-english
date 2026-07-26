"""Секреты с случайными пробелами не должны ломать HTTP-заголовки."""
from app.config import Settings


def test_secrets_stripped(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-or-v1-abc ")
    monkeypatch.setenv("MAX_BOT_TOKEN", " token\n")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "\t123:abc ")
    s = Settings(_env_file=None)
    assert s.LLM_API_KEY == "sk-or-v1-abc"
    assert s.MAX_BOT_TOKEN == "token"
    assert s.TELEGRAM_BOT_TOKEN == "123:abc"
