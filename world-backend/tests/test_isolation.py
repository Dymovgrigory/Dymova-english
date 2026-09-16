"""Мир не связан со школьной CRM и ботом."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = ("bigben", "crm_store", "miniapp_auth", "app.crm")


def test_world_backend_has_no_crm_or_bot_imports():
    hits: list[str] = []
    for path in ROOT.rglob("*.py"):
        if "__pycache__" in path.parts or path.name == "test_isolation.py":
            continue
        text = path.read_text(encoding="utf-8").lower()
        for token in FORBIDDEN:
            if token.lower() in text:
                hits.append(f"{path.relative_to(ROOT)}: {token}")
    assert hits == []
