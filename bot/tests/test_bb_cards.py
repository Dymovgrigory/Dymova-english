"""Карточки учеников BigBen из внутреннего API: имя ребёнка, имя родителя,
все телефоны. Точное сопоставление по номеру — братья и сёстры на одном номере."""
import re

import pytest

from app.config import settings
from app.platform import bb_cards, bb_store, student_cards_sync


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DB_PATH", str(tmp_path / "bb.db"))
    bb_store._local.conn = None
    yield
    bb_store._local.conn = None


def _raw(sid, fio, parent="", phone="", main="", phone1="", parent_phone=None, **extra):
    row = {
        "id": sid, "fio": fio, "parentname": parent, "phone": phone, "main_phone": main,
        "phone1": phone1, "parent_phone": parent_phone, "phone_comment": "", "phone1_comment": "",
        "email": "", "birthday": "", "ages": None, "filial": {"id": 1, "name": "Лихачевский"},
        "active_groups": [], "is_active": True, "archived": False, "deleted": False,
        "debt_sum": 0, "balance_sum_total": 0, "important_comment": "", "reg_date": "2026-01-01",
        # то, чего в нашей базе быть не должно:
        "password_raw": "secret1", "passport": "4500 123456", "home_address": "ул. Секретная, 1",
        "parent_password": "secret2",
    }
    row.update(extra)
    return row


def test_siblings_on_one_phone_are_all_found_in_any_phone_format():
    bb_cards.replace_all([
        bb_cards.from_api(_raw(1, "Сидоров Пётр", "Ольга", phone="89251112233")),
        bb_cards.from_api(_raw(2, "Сидорова Соня", "Ольга", phone="+7 (925) 111-22-33")),
        bb_cards.from_api(_raw(3, "Чужой Ребёнок", "Ирина", phone="89990000000")),
    ])
    found = bb_cards.find_by_phone("+79251112233")
    assert [c["id"] for c in found] == [1, 2]
    assert bb_cards.find_by_phone("8 925 111 22 33")[0]["parentname"] == "Ольга"
    assert bb_cards.find_by_phone("+79250000000") == []
    assert bb_cards.find_by_phone("") == []


def test_every_phone_of_the_student_matches_with_comment():
    card = bb_cards.from_api(_raw(
        5, "Егорова Аня", "Марина", phone="89251110000", main="89252220000",
        phone1="89253330000", phone_comment="мама Марина", phone1_comment="папа Олег",
        parent_phone="89254440000"))
    bb_cards.replace_all([card])
    for number in ("89251110000", "89252220000", "89253330000", "89254440000"):
        assert [c["id"] for c in bb_cards.find_by_phone(number)] == [5]
    comments = {p["phone"]: p["comment"] for p in bb_cards.find_by_phone("89253330000")[0]["phones"]}
    assert comments["89251110000"] == "мама Марина"
    assert comments["89253330000"] == "папа Олег"
    assert comments["89252220000"] == ""


def test_secrets_are_never_stored():
    bb_cards.replace_all([bb_cards.from_api(_raw(7, "Тест Тестов", "Мама", phone="89251110000"))])
    dump = str(bb_store._db().execute("SELECT * FROM bb_student_cards").fetchall()[0][:])
    dump += str([tuple(r) for r in bb_store._db().execute("SELECT * FROM bb_student_phones")])
    for secret in ("secret1", "secret2", "4500 123456", "Секретная"):
        assert secret not in dump


def test_card_fields_age_groups_status():
    card = bb_cards.from_api(_raw(
        9, "Львов Лев", "Анна", phone="89251110000", ages=8.4, birthday="2018-05-01",
        active_groups=[{"id": 3, "name": "Get Involved A2", "start_date": "2026-09-01",
                        "timefinish": None, "is_debtor": False}],
        debt_sum=1500, is_active=True))
    assert card["age"] == "8"
    assert card["groups"][0]["name"] == "Get Involved A2"
    assert card["debt_rub"] == 1500
    assert card["filial"] == "Лихачевский"


@pytest.mark.asyncio
async def test_sync_paginates_and_replaces_everything(monkeypatch):
    pages = {
        1: {"data": [_raw(1, "Один Раз", "Мама", phone="89251110001")],
            "meta": {"last_page": 2, "current_page": 1}},
        2: {"data": [_raw(2, "Два Раза", "Папа", phone="89251110002", archived=True)],
            "meta": {"last_page": 2, "current_page": 2}},
    }

    async def fake_request(method, path, json_body=None):
        page = int(re.search(r"[?&]page=(\d+)", path).group(1))
        return pages[page]

    monkeypatch.setattr(student_cards_sync.bigben_internal, "_request", fake_request)
    bb_cards.replace_all([bb_cards.from_api(_raw(99, "Старый Ученик", phone="89990001111"))])
    assert await student_cards_sync.sync_student_cards() == 2
    assert bb_cards.find_by_phone("89990001111") == []
    archived = bb_cards.find_by_phone("89251110002")[0]
    assert archived["archived"] is True


@pytest.mark.asyncio
async def test_failed_page_keeps_old_data(monkeypatch):
    bb_cards.replace_all([bb_cards.from_api(_raw(1, "Остаётся", phone="89251110001"))])

    async def broken(method, path, json_body=None):
        if re.search(r"[?&]page=2\b", path):
            raise student_cards_sync.bigben_internal.BigBenInternalError("401")
        return {"data": [_raw(2, "Новый", phone="89251110002")], "meta": {"last_page": 2}}

    monkeypatch.setattr(student_cards_sync.bigben_internal, "_request", broken)
    with pytest.raises(student_cards_sync.bigben_internal.BigBenInternalError):
        await student_cards_sync.sync_student_cards()
    assert [c["fio"] for c in bb_cards.find_by_phone("89251110001")] == ["Остаётся"]
    assert bb_cards.find_by_phone("89251110002") == []
