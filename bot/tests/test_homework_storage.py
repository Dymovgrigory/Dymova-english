"""Хранилище обращений за помощью с ДЗ: своя таблица + общая переписка CRM."""
import pytest

from app import crm_store
from app.homework import save_homework_image


@pytest.fixture(autouse=True)
def fresh_db():
    crm_store.reset()
    yield
    crm_store.reset()


def test_record_and_get_homework_request():
    req_id = crm_store.record_homework_request(
        platform="telegram", user_id="tg:1", conversation_id=None,
        channel="telegram", mode="explain", input_type="text",
        task_text="I ... nine", reply="📘 Правило...",
    )
    item = crm_store.get_homework_request(req_id)
    assert item["mode"] == "explain"
    assert item["input_type"] == "text"
    assert item["task_text"] == "I ... nine"
    assert item["created_at"]


def test_homework_request_shows_customer_name_via_join():
    customer_id = crm_store.upsert_customer_for_identity("telegram", "tg:9", name="Анна Петрова")
    req_id = crm_store.record_homework_request(
        platform="telegram", user_id="tg:9", customer_id=customer_id, conversation_id=None,
        channel="telegram", mode="explain", input_type="text", task_text="a", reply="r",
    )
    item = crm_store.get_homework_request(req_id)
    assert item["customer_name"] == "Анна Петрова"
    assert crm_store.list_homework_requests()[0]["customer_name"] == "Анна Петрова"


def test_list_homework_requests_filters_by_mode():
    crm_store.record_homework_request(
        platform="telegram", user_id="tg:1", conversation_id=None,
        channel="telegram", mode="explain", input_type="text", task_text="a", reply="r",
    )
    crm_store.record_homework_request(
        platform="max", user_id="42", conversation_id=None,
        channel="max", mode="check", input_type="image", image_path="homework/x.jpg", reply="r2",
    )
    only_check = crm_store.list_homework_requests(mode="check")
    assert len(only_check) == 1
    assert only_check[0]["mode"] == "check"
    assert len(crm_store.list_homework_requests()) == 2


def test_list_homework_requests_filters_by_date_range():
    crm_store.record_homework_request(
        platform="telegram", user_id="tg:1", conversation_id=None,
        channel="telegram", mode="explain", input_type="text", task_text="a", reply="r",
    )
    future_only = crm_store.list_homework_requests(date_from="2099-01-01")
    assert future_only == []


def test_save_homework_image_writes_file_under_data_homework(tmp_path, monkeypatch):
    monkeypatch.setattr("app.homework.HOMEWORK_IMAGE_DIR", str(tmp_path / "homework"))
    rel_path = save_homework_image(b"fake-jpeg-bytes", ext="jpg")
    assert rel_path.startswith("homework/") and rel_path.endswith(".jpg")
    # HOMEWORK_IMAGE_DIR замокан как tmp_path/"homework" (как в проде —
    # data/homework внутри data), поэтому tmp_path играет роль корня "data":
    # rel_path уже содержит сегмент "homework/", просто join с tmp_path.
    full = tmp_path / rel_path
    assert full.exists()
    assert full.read_bytes() == b"fake-jpeg-bytes"


def test_ingest_inbound_stores_payload():
    ctx = crm_store  # noqa: F841 — просто проверяем сигнатуру ниже
    from app import crm_ingest

    result = crm_ingest.ingest_inbound(
        "telegram", "tg:1", "[фото] задание",
        external_event_id="evt-1",
        payload={"image_path": "homework/abc.jpg"},
    )
    assert result is not None
    messages = crm_store.get_messages(result["conversation_id"])
    assert messages[0]["payload_json"] and "abc.jpg" in messages[0]["payload_json"]
