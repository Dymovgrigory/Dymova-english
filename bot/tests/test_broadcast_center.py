"""Тесты Broadcast Center: сегменты, preview, отправка, retry, история."""
import asyncio

import pytest
from fastapi.testclient import TestClient

from app import crm_store
from app import main as main_module
from app.config import settings

TOKEN = "test-admin-token"
AUTH = {"X-Admin-Token": TOKEN}


@pytest.fixture(autouse=True)
def reset_state(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DB_PATH", str(tmp_path / "crm.db"))
    monkeypatch.setattr(settings, "STATE_FILE", "")
    monkeypatch.setattr(settings, "ADMIN_TOKEN", TOKEN, raising=False)
    crm_store.reset()
    main_module._BACKGROUND_TASKS.clear()
    yield
    crm_store.reset()
    main_module._BACKGROUND_TASKS.clear()



def _wait_done(client, broadcast_id, max_client=None, telegram_client=None):
    """Endpoint создаёт фоновую задачу на loop TestClient, который гаснет
    сразу после ответа. Догоняем рассылку тем же раннером синхронно —
    run_broadcast идемпотентен (непризнанные pending доотправляются)."""
    from app import broadcast_runner

    asyncio.run(broadcast_runner.run_broadcast(
        broadcast_id, max_client=max_client, telegram_client=telegram_client))
    return crm_store.get_broadcast(broadcast_id)


@pytest.fixture
def client():
    return TestClient(main_module.app)


class FakeMax:
    def __init__(self, ok=True):
        self.sent = []
        self.ok = ok

    async def send_message(self, user_id, text, buttons=None):
        self.sent.append(user_id)
        return self.ok


class FakeTg:
    def __init__(self, ok=True):
        self.sent = []
        self.ok = ok

    async def send_message(self, chat_id, text, buttons=None):
        self.sent.append(chat_id)
        return self.ok


def _customer(channel, external_id, name, **kwargs):
    cid = crm_store.upsert_customer_for_identity(channel, external_id, name=name, **kwargs)
    conv = crm_store.get_or_create_conversation(cid, channel, external_id)
    return cid, conv


def test_resolve_segment_rules():
    cid1, _ = _customer("max", "u1", "Анна", child_age="9")
    cid2, _ = _customer("telegram", "tg:2", "Борис", child_age="15")
    crm_store.assign_tag(cid1, "vip")
    crm_store.update_customer(cid1, {"lead_status": "qualified"})

    assert len(crm_store.resolve_segment([])["recipients"]) == 2
    by_channel = crm_store.resolve_segment([{"field": "channel", "value": "max"}])
    assert [r["customer_id"] for r in by_channel["recipients"]] == [cid1]
    by_tag = crm_store.resolve_segment([{"field": "tag", "value": "vip"}])
    assert [r["customer_id"] for r in by_tag["recipients"]] == [cid1]
    by_lead = crm_store.resolve_segment([{"field": "lead_status", "value": "qualified"}])
    assert [r["customer_id"] for r in by_lead["recipients"]] == [cid1]
    by_age = crm_store.resolve_segment([{"field": "child_age", "value": {"from": "5", "to": "12"}}])
    assert [r["customer_id"] for r in by_age["recipients"]] == [cid1]
    by_age_gte = crm_store.resolve_segment([{"field": "child_age", "op": "gte", "value": "10"}])
    assert [r["customer_id"] for r in by_age_gte["recipients"]] == [cid2]
    by_search = crm_store.resolve_segment([{"field": "search", "value": "борис"}])
    assert [r["customer_id"] for r in by_search["recipients"]] == [cid2]
    # AND: тег + канал одновременно.
    both = crm_store.resolve_segment([
        {"field": "tag", "value": "vip"}, {"field": "channel", "value": "telegram"}])
    assert both["recipients"] == []


def test_web_only_customers_are_skipped():
    _customer("web", "web:only", "Веб")
    _customer("max", "u-push", "Макс")
    resolved = crm_store.resolve_segment([])
    assert len(resolved["recipients"]) == 1
    assert resolved["skipped_web"] == 1


def test_preview_counts_without_sending(client, monkeypatch):
    max_client = FakeMax()
    monkeypatch.setattr("app.broadcast_runner._deliver", max_client)  # не должен вызываться
    _customer("max", "u1", "Анна")
    _customer("telegram", "tg:2", "Борис")
    _customer("web", "web:w", "Веб")

    resp = client.post("/admin/api/broadcasts/preview", headers=AUTH, json={"rules": []})
    data = resp.json()
    assert data["total"] == 2
    assert data["by_channel"] == {"max": 1, "telegram": 1}
    assert data["skipped_web"] == 1
    assert len(data["sample"]) == 2
    assert max_client.sent == []  # preview ничего не отправил


def test_segments_crud(client):
    assert client.post("/admin/api/segments", headers=AUTH, json={
        "name": "ЕГЭ-шники", "rules": [{"field": "course", "value": "ЕГЭ"}],
    }).json()["ok"]
    items = client.get("/admin/api/segments", headers=AUTH).json()["items"]
    assert items[0]["name"] == "ЕГЭ-шники"
    assert items[0]["rules"][0]["field"] == "course"
    # Preview по сохранённому сегменту.
    _customer("max", "u1", "Анна", interests="Подготовка к ЕГЭ")
    resp = client.post("/admin/api/broadcasts/preview", headers=AUTH,
                       json={"segment_id": items[0]["id"]})
    assert resp.json()["total"] == 1
    assert client.delete(f"/admin/api/segments/{items[0]['id']}", headers=AUTH).json()["ok"]
    assert client.get("/admin/api/segments", headers=AUTH).json()["items"] == []


def test_send_flow_with_mock_clients(client, monkeypatch):
    max_client, tg_client = FakeMax(), FakeTg()
    monkeypatch.setattr("app.max_client.get_max", lambda: max_client)
    monkeypatch.setattr("app.telegram_client.get_telegram", lambda: tg_client)
    cid1, _ = _customer("max", "u1", "Анна")
    cid2, _ = _customer("telegram", "tg:2", "Борис")

    created = client.post("/admin/api/broadcasts", headers=AUTH,
                          json={"title": "Тест", "text": "Привет!", "rules": []}).json()
    # Без confirm — отказ.
    assert client.post(f"/admin/api/broadcasts/{created['id']}/send",
                       headers=AUTH, json={}).status_code == 400
    resp = client.post(f"/admin/api/broadcasts/{created['id']}/send",
                       headers=AUTH, json={"confirm": True})
    assert resp.json()["total"] == 2

    detail = _wait_done(client, created["id"], max_client=max_client, telegram_client=tg_client)
    assert detail["status"] == "done"
    assert detail["delivered"] == 2
    assert max_client.sent == ["u1"] and tg_client.sent == ["2"]

    # Исходящие записаны в историю клиентов как system.
    msgs = crm_store.get_conn().execute(
        "SELECT sender_type, status FROM crm_messages WHERE direction = 'out'").fetchall()
    assert len(msgs) == 2
    assert all(m["sender_type"] == "system" and m["status"] == "sent" for m in msgs)

    # Повторный send заблокирован.
    again = client.post(f"/admin/api/broadcasts/{created['id']}/send",
                        headers=AUTH, json={"confirm": True})
    assert again.status_code == 409


def test_failed_recipient_and_retry_limit(client, monkeypatch):
    max_client = FakeMax(ok=False)
    monkeypatch.setattr("app.max_client.get_max", lambda: max_client)
    cid, _ = _customer("max", "u-fail", "Анна")

    created = client.post("/admin/api/broadcasts", headers=AUTH,
                          json={"title": "Фейл", "text": "х", "rules": []}).json()
    client.post(f"/admin/api/broadcasts/{created['id']}/send", headers=AUTH, json={"confirm": True})
    _wait_done(client, created["id"], max_client=FakeMax(ok=False))

    recipients = crm_store.list_recipients(created["id"], status="failed")
    assert len(recipients) == 1
    rid = recipients[0]["id"]

    # Доставка чинится — retry успешен.
    max_client.ok = True
    resp = client.post(f"/admin/api/broadcasts/{created['id']}/recipients/{rid}/retry",
                       headers=AUTH)
    assert resp.json()["ok"]
    assert crm_store.get_recipient(rid)["status"] == "sent"
    assert crm_store.get_broadcast(created["id"])["delivered"] == 1

    # Retry не-failed запрещён; лимит срабатывает на failed.
    assert client.post(f"/admin/api/broadcasts/{created['id']}/recipients/{rid}/retry",
                       headers=AUTH).status_code == 400
    max_client.ok = False
    conn = crm_store.get_conn()
    conn.execute("UPDATE broadcast_recipients SET status = 'failed' WHERE id = ?", (rid,))
    for attempt in range(3):
        client.post(f"/admin/api/broadcasts/{created['id']}/recipients/{rid}/retry", headers=AUTH)
    last = client.post(f"/admin/api/broadcasts/{created['id']}/recipients/{rid}/retry", headers=AUTH)
    assert last.status_code == 400
    assert "лимит" in last.json()["detail"]
    assert crm_store.get_recipient(rid)["retry_count"] == 3


def test_history_and_detail_api(client, monkeypatch):
    monkeypatch.setattr("app.max_client.get_max", lambda: FakeMax())
    _customer("max", "u1", "Анна")
    created = client.post("/admin/api/broadcasts", headers=AUTH,
                          json={"title": "История", "text": "текст", "rules": []}).json()
    client.post(f"/admin/api/broadcasts/{created['id']}/send", headers=AUTH, json={"confirm": True})
    _wait_done(client, created["id"], max_client=FakeMax())

    history = client.get("/admin/api/broadcasts", headers=AUTH).json()["items"]
    assert history[0]["title"] == "История"
    assert history[0]["delivered"] == 1

    detail = client.get(f"/admin/api/broadcasts/{created['id']}", headers=AUTH).json()
    assert detail["recipients"][0]["customer_name"] == "Анна"
    sent_only = client.get(f"/admin/api/broadcasts/{created['id']}?status=sent", headers=AUTH).json()
    assert len(sent_only["recipients"]) == 1
