"""Перенос данных диалога в карточку клиента и сопоставление с BigBen."""
import pytest

from app import crm_store, customer_sync
from app.config import settings
from app.memory import Conversation, Lead
from app.platform import bb_store


@pytest.fixture(autouse=True)
def stores(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DB_PATH", str(tmp_path / "crm.db"))
    monkeypatch.setattr(settings, "STATE_FILE", "")
    crm_store.reset()
    bb_store._local.conn = None
    yield
    crm_store.reset()
    bb_store._local.conn = None


def _student(sid, fio, phone, email=""):
    bb_store.upsert_student({"id": sid, "fio": fio, "phone": phone, "email": email,
                             "balance_kopecks": 0})


def _conv(user_id="777", platform="max", **lead):
    conv = Conversation(user_id=user_id, platform=platform)
    conv.lead = Lead(**lead)
    return conv


def _customer(conv_user="777", channel="max", **fields):
    return crm_store.upsert_customer_for_identity(channel, conv_user, **fields)


def test_sync_moves_lead_fields_into_card():
    cid = _customer()
    conv = _conv(fio_parent="Иванова Анна", fio_child="Миша", phone="+79251112233", age="9")
    assert customer_sync.sync_conversation(conv) == cid
    card = crm_store.get_customer(cid)
    assert card["name"] == "Иванова Анна"
    assert card["child_name"] == "Миша"
    assert card["phone"] == "+79251112233"
    assert card["child_age"] == "9"


def test_sync_never_overwrites_manager_edits():
    cid = _customer(name="Анна Петровна (менеджер)", phone="+79990000000")
    conv = _conv(fio_parent="Иванова Анна", phone="+79251112233")
    customer_sync.sync_conversation(conv)
    card = crm_store.get_customer(cid)
    assert card["name"] == "Анна Петровна (менеджер)"
    assert card["phone"] == "+79990000000"


def test_sync_creates_card_for_unknown_identity():
    conv = _conv(user_id="tg:55", platform="telegram", phone="+79250001122")
    cid = customer_sync.sync_conversation(conv)
    assert cid and crm_store.get_customer(cid)["phone"] == "+79250001122"


def test_sync_skips_empty_conversation():
    assert customer_sync.sync_conversation(_conv()) is None


def test_enrich_fills_empty_fields_from_bigben_and_tags():
    _student(42, "Петров Миша", "89251112233", "mama@x.ru")
    cid = _customer(phone="+7 925 111-22-33")
    students = customer_sync.enrich_from_bigben(cid)
    assert [s["id"] for s in students] == [42]
    card = crm_store.get_customer(cid)
    assert card["child_name"] == "Петров Миша"
    assert card["email"] == "mama@x.ru"
    assert card["metadata"]["bb_student_ids"] == [42]
    assert "ученик школы" in [t["name"] for t in card["tags"]]


def test_enrich_does_not_overwrite_existing_child_name():
    _student(42, "Петров Миша", "89251112233")
    cid = _customer(phone="+79251112233", child_name="Мишенька")
    customer_sync.enrich_from_bigben(cid)
    assert crm_store.get_customer(cid)["child_name"] == "Мишенька"


def test_enrich_siblings_share_one_phone():
    _student(1, "Сидоров Пётр", "89251112233")
    _student(2, "Сидорова Соня", "89251112233")
    cid = _customer(phone="+79251112233")
    students = customer_sync.enrich_from_bigben(cid)
    assert {s["id"] for s in students} == {1, 2}
    assert crm_store.get_customer(cid)["child_name"] == "Сидоров Пётр, Сидорова Соня"


def test_status_reasons():
    no_phone = _customer(conv_user="1")
    assert customer_sync.bigben_status(no_phone)["reason"] == "no_phone"
    stranger = _customer(conv_user="2", phone="+79990001122")
    assert customer_sync.bigben_status(stranger)["reason"] == "phone_not_in_bigben"
    _student(9, "Кузнецова Даша", "89257778899")
    known = _customer(conv_user="3", phone="+79257778899")
    status = customer_sync.bigben_status(known)
    assert status["reason"] == "linked" and status["students"][0]["id"] == 9


def test_candidates_by_child_name_and_manual_link_fills_phone():
    _student(5, "Морозова Маша", "89253334455", "m@x.ru")
    _student(6, "Волков Иван", "89256667788")
    cid = _customer(child_name="Маша", name="Морозова Елена")
    found = customer_sync.bb_candidates(cid)
    assert [c["id"] for c in found] == [5]
    assert "3334455"[-4:] in found[0]["phone_hint"]  # только последние цифры
    assert customer_sync.link_bigben(cid, 5, actor="admin")
    card = crm_store.get_customer(cid)
    assert card["phone"].endswith("9253334455") or card["phone"] == "89253334455"
    assert card["metadata"]["bb_linked_ids"] == [5]
    assert customer_sync.bigben_status(cid)["reason"] == "linked"


def test_candidates_empty_without_names_and_link_unknown_student():
    cid = _customer()
    assert customer_sync.bb_candidates(cid) == []
    assert customer_sync.link_bigben(cid, 12345, actor="admin") is False


def test_backfill_walks_conversations(monkeypatch):
    _customer(conv_user="10")
    convs = [_conv(user_id="10", phone="+79251110000", fio_parent="Орлова Ольга")]
    monkeypatch.setattr(customer_sync, "_all_conversations", lambda: convs)
    result = customer_sync.backfill()
    assert result["synced"] == 1
    card = crm_store.find_customer_by_phone("+79251110000")
    assert card and card["name"] == "Орлова Ольга"


@pytest.mark.asyncio
async def test_phone_from_chat_lands_in_card_and_finds_bigben_student(monkeypatch):
    from app import ai_core
    from app import memory as memory_module

    memory_module._store = None
    monkeypatch.setattr(settings, "REGISTRATION_REQUIRED", False, raising=False)
    monkeypatch.setattr(settings, "IDENTIFICATION_REQUIRED", False, raising=False)
    _student(77, "Белова Лиза", "89261234567", "b@x.ru")
    await ai_core.handle_message("901", "Мой номер 89261234567", platform="max")
    card = crm_store.find_customer_by_phone("+79261234567")
    assert card is not None
    assert card["child_name"] == "Белова Лиза"
    assert card["email"] == "b@x.ru"
    memory_module._store = None
