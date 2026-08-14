"""Личный кабинет мини-приложения: хранилище, доступ, импорт расписания.

Каждый тест привязан к пункту приёмки из задания на кабинет.
"""
import json
import logging

import pytest
from fastapi.testclient import TestClient

from app import cabinet
from app import main as main_module
from app import memory as memory_module
from app.config import settings
from app.memory import get_store

from tests.conftest import make_telegram_init_data

TOKEN = "123456:AA-test-token"
ADMIN = "test-admin-token"


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    memory_module._store = None
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", TOKEN, raising=False)
    monkeypatch.setattr(settings, "MINIAPP_AUTH_REQUIRED", True, raising=False)
    monkeypatch.setattr(settings, "MINIAPP_REQUIRE_REGISTRATION", False, raising=False)
    monkeypatch.setattr(settings, "ADMIN_TOKEN", ADMIN, raising=False)
    yield
    memory_module._store = None


def auth(user_id: int, first_name: str = "Аня") -> dict:
    return {
        "X-Miniapp-Init-Data": make_telegram_init_data(
            TOKEN, telegram_user_id=user_id, first_name=first_name
        ),
        "X-Miniapp-Platform": "telegram",
    }


def make_conv(store, user_id: str, **lead):
    conv = store.get(user_id, platform="telegram")
    conv.registered = True
    for key, value in lead.items():
        setattr(conv.lead, key, value)
    store.save(conv)
    return conv


# --- 1. Чужой кабинет не отдаётся ни при каком user_id в запросе ----------

def test_cabinet_requires_signed_identity():
    client = TestClient(main_module.app)
    store = get_store()
    make_conv(store, "tg:111", fio_child="Маша")

    # Совсем без initData — 401, даже с user_id.
    assert client.get("/api/miniapp/cabinet?user_id=tg:111").status_code == 401

    # Чужая подпись + user_id владельца — виден только свой (пустой) кабинет.
    response = client.get("/api/miniapp/cabinet?user_id=tg:111", headers=auth(222))
    assert response.status_code == 200
    assert response.json()["children"] == []

    # Свой кабинет — виден.
    own = client.get("/api/miniapp/cabinet", headers=auth(111))
    assert own.status_code == 200
    assert [c["name"] for c in own.json()["children"]] == ["Маша"]


def test_child_edit_of_stranger_is_impossible():
    client = TestClient(main_module.app)
    store = get_store()
    make_conv(store, "tg:111", fio_child="Маша")
    child = cabinet.ensure_children(store, store.get("tg:111", platform="telegram"))[0]

    response = client.post(
        "/api/miniapp/cabinet/child",
        headers=auth(222),
        json={"id": child["id"], "name": "Взломано"},
    )
    assert response.status_code == 404
    assert cabinet.list_children(store, "telegram", "tg:111")[0]["name"] == "Маша"


# --- 5.# --- 5. Правка карточки ребёнка меняет то, чем пользуется бот --------------

def test_child_edit_flows_into_conversation():
    client = TestClient(main_module.app)
    store = get_store()
    conv = make_conv(store, "tg:111", fio_child="Маша", age="7")

    child = cabinet.ensure_children(store, store.get("tg:111", platform="telegram"))[0]
    response = client.post(
        "/api/miniapp/cabinet/child",
        headers=auth(111),
        json={"id": child["id"], "name": "Маша", "age": "9", "level": "A2–B1",
              "program": "Kids English"},
    )
    assert response.status_code == 200

    fresh = store.get("tg:111", platform="telegram")
    assert fresh.lead.age == "9"
    assert fresh.need.child_age == "9"
    assert fresh.need.level == "A2–B1"
    assert fresh.selected_course == "Kids English"


# --- 6. Попытки теста хранятся на сервере ----------------------------------

def test_level_attempts_live_on_server():
    client = TestClient(main_module.app)
    store = get_store()
    make_conv(store, "tg:111", fio_child="Маша")

    # Все верные ответы нового десятивопросного теста → максимальный уровень.
    from app import leveltest

    answers = {q["id"]: q["answer"] for q in leveltest.QUESTIONS}
    response = client.post("/api/miniapp/level-test", headers=auth(111),
                           json={"answers": answers})
    assert response.status_code == 200

    attempts = cabinet.list_attempts(store, "telegram", "tg:111")
    assert len(attempts) == 1
    assert attempts[0]["level"] == "B1+"
    assert attempts[0]["answers"] == answers
    # Чистка кэша браузера серверную историю не трогает: новый «заход»
    # (другой client) видит ту же попытку.
    fresh = TestClient(main_module.app)
    data = fresh.get("/api/miniapp/cabinet", headers=auth(111)).json()
    assert data["attempts"]["kind"] == "single"
    assert data["attempts"]["points"][0]["level"] == "B1+"
    # Уровень из теста сам попал в карточку ребёнка.
    assert data["children"][0]["level"] == "B1+"


def test_progress_phrases_by_level_codes():
    store = get_store()
    one = cabinet.record_attempt(store, "telegram", "tg:1",
                                 {"correct": 2, "total": 5, "level": "A1–A2"}, {})
    assert cabinet.progress_summary([one])["kind"] == "single"
    two = cabinet.record_attempt(store, "telegram", "tg:1",
                                 {"correct": 4, "total": 5, "level": "A2–B1"}, {})
    summary = cabinet.progress_summary([one, two])
    assert summary["kind"] == "series"
    assert "A1–A2" in summary["phrase"] and "A2–B1" in summary["phrase"]
    assert summary["grew"] is True


# --- 7. Родитель с двумя детьми видит обоих --------------------------------

def test_two_children_both_visible():
    client = TestClient(main_module.app)
    make_conv(get_store(), "tg:111", fio_child="Маша", age="7")

    client.post("/api/miniapp/cabinet/child", headers=auth(111),
                json={"name": "Петя", "age": "12"})
    data = client.get("/api/miniapp/cabinet", headers=auth(111)).json()
    names = [c["name"] for c in data["children"]]
    assert sorted(names) == ["Маша", "Петя"]


# --- 10.# --- 10. В логах нет телефонов и имён детей ---------------------------------

def test_cabinet_endpoints_log_no_pii(caplog):
    client = TestClient(main_module.app)
    store = get_store()
    make_conv(store, "tg:111", fio_child="Маша", phone="8 (926) 111-22-33")
    with caplog.at_level(logging.INFO):
        client.get("/api/miniapp/cabinet", headers=auth(111))
        client.post("/api/miniapp/cabinet/child", headers=auth(111),
                    json={"name": "Петя", "age": "12"})
    assert "Маша" not in caplog.text
    assert "9261112233" not in caplog.text.replace(" ", "")




def test_homework_frontend_matches_server_contract():
    """Раньше фронт слал поле `photo` и читал `reply`, а сервер ждал `image`
    и отдавал `explanation` — разбор фото в мини-приложении молча не работал."""
    js = (main_module._TGAPP_DIR / "app.js").read_text(encoding="utf-8")
    assert 'form.append("image"' in js
    assert "data.explanation" in js
    assert 'form.append("photo"' not in js
