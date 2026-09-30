"""Перенос данных диалога в карточку клиента и сопоставление с BigBen."""
import pytest

from app import crm_store, customer_sync
from app.config import settings
from app.memory import Conversation, Lead
from app.platform import bb_cards, bb_store


@pytest.fixture(autouse=True)
def stores(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DB_PATH", str(tmp_path / "crm.db"))
    monkeypatch.setattr(settings, "STATE_FILE", "")
    crm_store.reset()
    bb_store._local.conn = None
    _CARDS.clear()
    yield
    crm_store.reset()
    bb_store._local.conn = None


_CARDS: list[dict] = []


def _student(sid, fio, phone, email="", parent="", age=None, **extra):
    """Ученик в справочнике BigBen (карточки внутреннего API)."""
    raw = {"id": sid, "fio": fio, "parentname": parent, "phone": phone, "main_phone": "",
           "phone1": "", "parent_phone": None, "phone_comment": "", "phone1_comment": "",
           "email": email, "ages": age, "filial": {"id": 1, "name": "Лихачевский"},
           "active_groups": [], "is_active": True, "archived": False, "deleted": False}
    raw.update(extra)
    _CARDS.append(bb_cards.from_api(raw))
    bb_cards.replace_all(list(_CARDS))


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


def test_parent_name_age_and_email_come_from_bigben():
    _student(42, "Петров Миша", "89251112233", "mama@x.ru", parent="Ольга", age=8.3)
    cid = _customer(phone="+79251112233")
    customer_sync.enrich_from_bigben(cid)
    card = crm_store.get_customer(cid)
    assert card["name"] == "Ольга"
    assert card["child_age"] == "8"
    assert card["child_name"] == "Петров Миша"


def test_siblings_get_all_ages_and_one_parent():
    _student(1, "Сидоров Пётр", "89251112233", parent="Ольга", age=11.2)
    _student(2, "Сидорова Соня", "89251112233", parent="Ольга", age=8.9)
    cid = _customer(phone="+79251112233")
    customer_sync.enrich_from_bigben(cid)
    card = crm_store.get_customer(cid)
    assert card["name"] == "Ольга"
    assert card["child_age"] == "11, 8"


def test_no_guessing_by_name_only():
    """Имя без номера — это не совпадение: карточка остаётся несвязанной."""
    _student(5, "Морозова Маша", "89253334455", parent="Елена")
    cid = _customer(child_name="Маша", name="Елена")
    assert customer_sync.enrich_from_bigben(cid) == []
    assert customer_sync.bigben_status(cid)["reason"] == "no_phone"


def test_former_student_is_tagged_differently():
    _student(8, "Бывший Ученик", "89250009988", archived=True, is_active=False)
    cid = _customer(phone="+79250009988")
    customer_sync.enrich_from_bigben(cid)
    names = [t["name"] for t in crm_store.get_customer(cid)["tags"]]
    assert "бывший ученик" in names and "ученик школы" not in names


def test_falls_back_to_public_api_rows_when_cards_not_synced():
    bb_store.upsert_student({"id": 3, "fio": "Публичный Ученик", "phone": "89257776655",
                             "email": "p@x.ru", "balance_kopecks": 0})
    cid = _customer(phone="+79257776655")
    students = customer_sync.enrich_from_bigben(cid)
    assert [s["id"] for s in students] == [3]
    assert crm_store.get_customer(cid)["child_name"] == "Публичный Ученик"


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
