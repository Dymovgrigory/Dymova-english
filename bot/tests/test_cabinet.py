"""Личный кабинет мини-приложения: хранилище, доступ, импорт расписания.

Каждый тест привязан к пункту приёмки из задания на кабинет.
"""
import io
import json
import logging
import zipfile
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import cabinet, importer, scheduler
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


CSV = "Ученик;Телефон;День;Время;Программа;Педагог;Филиал\n" \
      "Маша;8 (926) 111-22-33;понедельник;17:30;Kids;Aнна;Лихачёвский\n" \
      "Петя;;вторник;18:00;Teens;Олег;Ракетостроителей\n"


def import_csv(store, client, content: str = CSV) -> dict:
    response = client.post(
        "/admin/import/commit",
        headers={"X-Admin-Token": ADMIN},
        files={"file": ("schedule.csv", content.encode(), "text/csv")},
        data={"mapping": json.dumps({
            "student": "Ученик", "phone": "Телефон", "weekday": "День",
            "time": "Время", "program": "Программа", "teacher": "Педагог",
            "filial": "Филиал",
        })},
    )
    assert response.status_code == 200, response.text
    return response.json()["report"]


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


# --- 2. Повторный импорт не удваивает занятия ------------------------------

def test_reimport_does_not_duplicate_lessons():
    client = TestClient(main_module.app)
    store = get_store()
    make_conv(store, "tg:111", fio_child="Маша", phone="8 (926) 111-22-33")

    import_csv(store, client)
    first = cabinet.schedule_for(store, "telegram", "tg:111")
    assert len(first["lessons"]) == 1

    import_csv(store, client)  # тот же файл ещё раз
    second = cabinet.schedule_for(store, "telegram", "tg:111")
    assert len(second["lessons"]) == 1
    assert cabinet.latest_batch(store)["rows_matched"] == 1


# --- 3. Строки без совпадения не теряются ----------------------------------

def test_unmatched_rows_land_in_report_and_manual_match():
    client = TestClient(main_module.app)
    store = get_store()
    make_conv(store, "tg:111", fio_child="Маша", phone="+7 926 111 22 33")

    report = import_csv(store, client)
    assert report["rows_total"] == 2
    assert report["rows_matched"] == 1
    assert report["rows_unmatched"] == 1
    assert report["unmatched"][0]["student"] == "Петя"

    # Ручное сопоставление: Петя → родитель tg:222.
    make_conv(store, "tg:222", fio_child="Петя")
    response = client.post(
        "/admin/import/match",
        headers={"X-Admin-Token": ADMIN},
        json={"batch_id": report["batch_id"], "row_index": 1,
              "platform": "telegram", "user_id": "tg:222"},
    )
    assert response.status_code == 200
    assert response.json()["report"]["rows_unmatched"] == 0
    lessons = cabinet.schedule_for(store, "telegram", "tg:222")["lessons"]
    assert [l["student_name"] for l in lessons] == ["Петя"]


# --- 4. Без импорта — честный блок, а не пустая сетка ----------------------

def test_cabinet_without_import_is_honest():
    client = TestClient(main_module.app)
    store = get_store()
    make_conv(store, "tg:111", fio_child="Маша")

    data = client.get("/api/miniapp/cabinet", headers=auth(111)).json()
    assert data["schedule"]["has_import"] is False
    assert data["schedule"]["lessons"] == []


def test_honest_schedule_block_in_frontend():
    js = (main_module._TGAPP_DIR / "app.js").read_text(encoding="utf-8")
    assert "Расписание появится, когда администратор загрузит его в бота" in js
    assert "Спросить расписание" in js


# --- 5. Правка карточки ребёнка меняет то, чем пользуется бот --------------

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

    answers = {"q1": 1, "q2": 1, "q3": 2, "q4": 1, "q5": 1}
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


# --- 8. Стареющие данные помечены, администратор получает напоминание ------

def test_stale_import_is_marked_and_reminder_text_exists():
    store = get_store()
    make_conv(store, "tg:111", fio_child="Маша", phone="8 (926) 111-22-33")
    client = TestClient(main_module.app)
    import_csv(store, client)

    assert cabinet.schedule_for(store, "telegram", "tg:111")["stale"] is False
    # «Уезжаем» в будущее: импорту 10 дней.
    with store._lock:
        store._conn.execute(
            "UPDATE import_batches SET uploaded_at = ?",
            ((datetime.now(timezone.utc) - timedelta(days=10)).isoformat(timespec="seconds"),),
        )
    assert cabinet.schedule_for(store, "telegram", "tg:111")["stale"] is True
    assert importer.status(store)["needs_import"] is True
    text = scheduler.import_reminder_text(cabinet.import_age_days(store))
    assert text is not None and "10" in text
    # Совсем без импорта — тоже напоминание.
    assert scheduler.import_reminder_text(None) is not None
    # Свежий импорт — тишина.
    assert scheduler.import_reminder_text(2.0) is None


# --- 9. Разметка кабинета видна при выключенном JS -------------------------

def test_cabinet_markup_visible_without_js():
    html = (main_module._TGAPP_DIR / "index.html").read_text(encoding="utf-8")
    css = (main_module._TGAPP_DIR / "app.css").read_text(encoding="utf-8")
    assert 'id="cabinet"' in html
    assert 'id="cab-child"' in html and 'id="cab-progress"' in html
    # Появление задаёт CSS-анимация, а не класс из скрипта.
    assert "@keyframes cab-in" in css
    # В каждом блоке есть осмысленный текст до прихода данных.
    assert "cab__loading" in html


# --- 10. В логах нет телефонов и имён детей ---------------------------------

def test_import_logs_contain_no_pii(caplog):
    client = TestClient(main_module.app)
    store = get_store()
    make_conv(store, "tg:111", fio_child="Маша", phone="8 (926) 111-22-33")
    with caplog.at_level(logging.INFO):
        import_csv(store, client)
    assert "Маша" not in caplog.text
    assert "9261112233" not in caplog.text.replace(" ", "")
    # Журнал аудита — только счётчики.
    with store._lock:
        rows = store._conn.execute("SELECT details FROM admin_audit").fetchall()
    assert rows
    for row in rows:
        assert "Маша" not in row["details"]
        assert "926" not in row["details"]


# --- Расписание чужого ученика невидимо -------------------------------------

def test_imported_lessons_visible_only_to_matched_parent():
    client = TestClient(main_module.app)
    store = get_store()
    make_conv(store, "tg:111", fio_child="Маша", phone="8 (926) 111-22-33")
    make_conv(store, "tg:222", fio_child="Вася")
    import_csv(store, client)

    own = client.get("/api/miniapp/cabinet", headers=auth(111)).json()
    assert own["schedule"]["has_import"] is True
    assert len(own["schedule"]["lessons"]) == 1
    assert own["schedule"]["next"]["time"] == "17:30"

    other = client.get("/api/miniapp/cabinet", headers=auth(222)).json()
    assert other["schedule"]["lessons"] == []


# --- Разбор файлов ------------------------------------------------------------

def _xlsx_bytes(rows: list[list[str]]) -> bytes:
    """Минимальный XLSX с inline-строками — ровно то, что читает importer."""
    sheet_rows = "".join(
        "<row>" + "".join(
            f'<c r="{chr(65 + i)}{n}" t="inlineStr"><is><t>{v}</t></is></c>'
            for i, v in enumerate(row)
        ) + "</row>"
        for n, row in enumerate(rows, start=1)
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("xl/worksheets/sheet1.xml",
                   f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                   f"<sheetData>{sheet_rows}</sheetData></worksheet>")
    return buffer.getvalue()


def test_parse_xlsx():
    content = _xlsx_bytes([
        ["Ученик", "День", "Время"],
        ["Маша", "Среда", "16:00"],
    ])
    headers, rows = importer.parse_upload("schedule.xlsx", content)
    assert headers == ["Ученик", "День", "Время"]
    assert rows == [{"Ученик": "Маша", "День": "Среда", "Время": "16:00"}]


def test_parse_csv_cp1251_and_semicolon():
    content = "Ученик;День\nМаша;Пятница\n".encode("cp1251")
    headers, rows = importer.parse_upload("schedule.csv", content)
    assert headers[0] == "Ученик"
    assert rows[0]["Ученик"] == "Маша"


def test_guess_mapping_finds_columns():
    mapping = importer.guess_mapping(["ФИО ученика", "Телефон", "День недели", "Время занятия"])
    assert mapping["student"] == "ФИО ученика"
    assert mapping["phone"] == "Телефон"
    assert mapping["weekday"] == "День недели"


def test_import_requires_admin_token():
    client = TestClient(main_module.app)
    response = client.post(
        "/admin/import/commit",
        files={"file": ("s.csv", CSV.encode(), "text/csv")},
        data={"mapping": "{}"},
    )
    assert response.status_code == 401
    response = client.get("/admin/import/status")
    assert response.status_code == 401


def test_preview_remembers_saved_mapping():
    client = TestClient(main_module.app)
    get_store()
    import_csv(get_store(), client)
    response = client.post(
        "/admin/import/preview",
        headers={"X-Admin-Token": ADMIN},
        files={"file": ("schedule.csv", CSV.encode(), "text/csv")},
    )
    data = response.json()
    assert data["mapping"]["student"] == "Ученик"
    assert data["mapping"]["weekday"] == "День"


# --- Разбор домашки: фронт и сервер говорят по одному контракту -------------

def test_homework_frontend_matches_server_contract():
    """Раньше фронт слал поле `photo` и читал `reply`, а сервер ждал `image`
    и отдавал `explanation` — разбор фото в мини-приложении молча не работал."""
    js = (main_module._TGAPP_DIR / "app.js").read_text(encoding="utf-8")
    assert 'form.append("image"' in js
    assert "data.explanation" in js
    assert 'form.append("photo"' not in js
