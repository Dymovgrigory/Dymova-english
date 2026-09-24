# Анкета-форма в мини-приложении — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Вместо 4 вопросов в переписке новый клиент Telegram/MAX получает одну кнопку «📝 Заполнить анкету», заполняет короткую форму с согласиями в мини-приложении, и данные уходят в BigBen и в админку бота.

**Architecture:** Новый модуль `app/consents.py` хранит согласия в БД CRM (таблица `consents`). Новый модуль `app/registration_form.py` валидирует форму и применяет её к `Conversation`, переиспользуя валидаторы из `app/registration.py`. Ручка `POST /api/miniapp/register` (только подписанный initData) связывает всё вместе: лид → BigBen, клиент → CRM, подтверждение → чат мессенджера. Чат-гейт в `ai_core` для платформ telegram/max вместо вопросов отвечает приглашением; транспорты цепляют к нему кнопку формы (TG — `web_app`, MAX — link). Фронт (`app/tgapp`, общий для TG и MAX) показывает полноэкранную форму, пока `access.locked` или `access.needs_consents`.

**Tech Stack:** Python 3.11, FastAPI, SQLite (`crm_store`), pytest + `fastapi.testclient`, ванильный JS мини-приложения.

**Spec:** `docs/superpowers/specs/2026-09-24-bot-miniapp-upgrade-design.md`, раздел «Подпроект 0».

## Global Constraints

- Все команды тестов — из каталога `bot/`: `cd /Users/grigory/Dymova-english/bot && python -m pytest …`.
- Версия юр. текстов: `LEGAL_VERSION = "2026-09-19"` (как `world/src/lib/legal.ts`).
- Ссылки на полные тексты: `https://new.dymova-english.ru/legal/pd-consent`, `https://new.dymova-english.ru/legal/privacy` (проверено: 200).
- Формулировки согласий — дословно:
  - `pd_child`: «Я являюсь родителем/законным представителем ребёнка и даю согласие на обработку его персональных данных» (обязательно)
  - `privacy`: «Принимаю политику конфиденциальности» (обязательно)
  - `marketing`: «Хочу получать новости и акции школы (необязательно)» — **чекбокс отмечен по умолчанию**; сохраняем `default_checked=1`.
- Форма принимается только при `identity.verified == True`.
- Веб-виджет сайта (platform `web`) остаётся на старом пошаговом опросе.
- В рабочем дереве есть чужие незакоммиченные правки `bot/app/main.py`, `bot/app/tgapp/*`, `bot/tests/test_tgapp.py`, `bot/tests/test_world_bridge.py` (Menu Button «Кабинет», мир внутри мини-приложения). Их не откатывать и не коммитить в рамках этих задач: коммитить только свои hunks (`git add -p`), либо сначала согласовать с владельцем отдельный коммит этих правок.
- Коммиты — Conventional Commits, `feat(bot): …`, с трейлером `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- Комментарии в коде — по-русски, в стиле файла («почему», а не «что»).

---

### Task 1: Хранилище согласий

**Files:**
- Create: `bot/app/consents.py`
- Modify: `bot/app/crm_store.py` (добавить таблицу в `_SCHEMA`, ~стр. 236)
- Test: `bot/tests/test_consents.py`

**Interfaces:**
- Produces:
  - `consents.LEGAL_VERSION: str`
  - `consents.CONSENT_LABELS: dict[str, str]`, `consents.CONSENT_LINKS: dict[str, str]`, `consents.REQUIRED: tuple[str, ...] = ("pd_child", "privacy")`
  - `consents.record(platform: str, user_id: str, accepted: dict[str, bool], channel: str, default_checked: frozenset[str] = frozenset({"marketing"})) -> None`
  - `consents.latest(platform: str, user_id: str) -> dict[str, dict]` — `{type: {"accepted": bool, "legal_version": str, "channel": str, "default_checked": bool, "created_at": str}}`
  - `consents.has_required(platform: str, user_id: str) -> bool`
  - `consents.summary_line(platform: str, user_id: str) -> str` — одна строка для заметки BigBen

- [ ] **Step 1: Write the failing test** — `bot/tests/test_consents.py`

```python
"""Согласия на обработку ПД: хранение, версия, отметка по умолчанию."""
import pytest

from app import consents, crm_store


@pytest.fixture(autouse=True)
def fresh_db():
    crm_store.reset()
    yield
    crm_store.reset()


def test_required_consents_missing_by_default():
    assert consents.has_required("telegram", "tg:1") is False


def test_record_and_read_back_with_version_and_default_flag():
    consents.record("telegram", "tg:1",
                    {"pd_child": True, "privacy": True, "marketing": True},
                    channel="miniapp")
    got = consents.latest("telegram", "tg:1")
    assert got["pd_child"]["accepted"] is True
    assert got["pd_child"]["legal_version"] == consents.LEGAL_VERSION
    assert got["marketing"]["default_checked"] is True
    assert got["pd_child"]["default_checked"] is False
    assert consents.has_required("telegram", "tg:1") is True


def test_unchecked_marketing_is_stored_as_declined():
    consents.record("max", "42",
                    {"pd_child": True, "privacy": True, "marketing": False},
                    channel="miniapp")
    assert consents.latest("max", "42")["marketing"]["accepted"] is False
    assert consents.has_required("max", "42") is True


def test_latest_record_wins():
    consents.record("max", "42", {"pd_child": True, "privacy": True, "marketing": True}, channel="miniapp")
    consents.record("max", "42", {"pd_child": True, "privacy": True, "marketing": False}, channel="miniapp")
    assert consents.latest("max", "42")["marketing"]["accepted"] is False


def test_summary_line_mentions_every_type_and_version():
    consents.record("telegram", "tg:1", {"pd_child": True, "privacy": True, "marketing": True}, channel="miniapp")
    line = consents.summary_line("telegram", "tg:1")
    assert "ПД ребёнка: да" in line
    assert "политика: да" in line
    assert "рассылки: да" in line
    assert consents.LEGAL_VERSION in line
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/grigory/Dymova-english/bot && python -m pytest tests/test_consents.py -v`
Expected: FAIL — `ImportError: cannot import name 'consents'`

- [ ] **Step 3: Add table to CRM schema** — в `bot/app/crm_store.py` перед `CREATE TABLE IF NOT EXISTS crm_meta` вставить:

```sql
CREATE TABLE IF NOT EXISTS consents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    user_id TEXT NOT NULL,
    type TEXT NOT NULL,
    accepted INTEGER NOT NULL,
    legal_version TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT '',
    default_checked INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_consents_user ON consents(platform, user_id, type, id);
```

- [ ] **Step 4: Write `bot/app/consents.py`**

```python
"""Согласия на обработку персональных данных (152-ФЗ) и на рассылки.

Раньше бот собирал ФИО, телефон и дату рождения ребёнка без единого
согласия. Формулировки и версия — те же, что в Мире Фоксинбурга
(world/src/lib/legal.ts): юридически у школы один набор текстов.

Храним журнал, а не флаг: каждое принятие — отдельная строка с версией
текста и датой. При претензии нужно показать, ЧТО человек видел и КОГДА.
"""
from __future__ import annotations

from app import crm_store

LEGAL_VERSION = "2026-09-19"

CONSENT_LABELS: dict[str, str] = {
    "pd_child": (
        "Я являюсь родителем/законным представителем ребёнка и даю согласие "
        "на обработку его персональных данных"
    ),
    "privacy": "Принимаю политику конфиденциальности",
    "marketing": "Хочу получать новости и акции школы (необязательно)",
}

CONSENT_LINKS: dict[str, str] = {
    "pd_child": "https://new.dymova-english.ru/legal/pd-consent",
    "privacy": "https://new.dymova-english.ru/legal/privacy",
}

REQUIRED: tuple[str, ...] = ("pd_child", "privacy")

_SUMMARY_NAMES = {"pd_child": "ПД ребёнка", "privacy": "политика", "marketing": "рассылки"}


def record(
    platform: str,
    user_id: str,
    accepted: dict[str, bool],
    channel: str,
    default_checked: frozenset[str] = frozenset({"marketing"}),
) -> None:
    """Пишет по строке на каждый известный тип согласия.

    default_checked — какие чекбоксы были показаны уже отмеченными: для
    рассылок это важно, заранее поставленная галочка оценивается иначе,
    чем поставленная самим человеком.
    """
    conn = crm_store.get_conn()
    now = crm_store._now()
    with crm_store._tx(conn):
        for kind in CONSENT_LABELS:
            conn.execute(
                "INSERT INTO consents (platform, user_id, type, accepted, legal_version,"
                " channel, default_checked, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (platform, user_id, kind, int(bool(accepted.get(kind))), LEGAL_VERSION,
                 channel, int(kind in default_checked), now),
            )


def latest(platform: str, user_id: str) -> dict[str, dict]:
    conn = crm_store.get_conn()
    rows = conn.execute(
        "SELECT type, accepted, legal_version, channel, default_checked, created_at"
        " FROM consents WHERE platform = ? AND user_id = ? ORDER BY id",
        (platform, user_id),
    ).fetchall()
    result: dict[str, dict] = {}
    for row in rows:
        result[row["type"]] = {
            "accepted": bool(row["accepted"]),
            "legal_version": row["legal_version"],
            "channel": row["channel"],
            "default_checked": bool(row["default_checked"]),
            "created_at": row["created_at"],
        }
    return result


def has_required(platform: str, user_id: str) -> bool:
    got = latest(platform, user_id)
    return all(got.get(kind, {}).get("accepted") for kind in REQUIRED)


def summary_line(platform: str, user_id: str) -> str:
    got = latest(platform, user_id)
    if not got:
        return ""
    parts = [
        f"{_SUMMARY_NAMES[kind]}: {'да' if got.get(kind, {}).get('accepted') else 'нет'}"
        for kind in CONSENT_LABELS
    ]
    stamp = max(item["created_at"] for item in got.values())[:16].replace("T", " ")
    return f"Согласия ({', '.join(parts)}; версия {LEGAL_VERSION}; {stamp} UTC)"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/grigory/Dymova-english/bot && python -m pytest tests/test_consents.py tests/test_crm_store.py -v`
Expected: все PASS (если `crm_store.reset` не существует под этим именем в фикстуре — проверить `crm_store.reset()` на стр. 331, он есть).

- [ ] **Step 6: Commit**

```bash
cd /Users/grigory/Dymova-english
git add bot/app/consents.py bot/app/crm_store.py bot/tests/test_consents.py
git commit -m "feat(bot): журнал согласий на обработку ПД и рассылки

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Валидация и применение формы

**Files:**
- Create: `bot/app/registration_form.py`
- Test: `bot/tests/test_registration_form.py`

**Interfaces:**
- Consumes: `registration._looks_like_name`, `registration._plausible_age`, `registration._plausible_birthday`, `app.intent.extract_phone`, `app.memory.Conversation`
- Produces:
  - `registration_form.FormData` (dataclass: `fio_parent: str, fio_child: str, birthday: str, age: str, phone: str, consents: dict[str, bool]`)
  - `registration_form.validate(payload: dict) -> tuple[FormData | None, dict[str, str]]` — вторым элементом ошибки по полям (ключи: `fio_parent`, `fio_child`, `child_birth`, `phone`, `consents`)
  - `registration_form.apply(conv: Conversation, form: FormData) -> None` — пишет в `conv.lead`, ставит `conv.registered = True`, `conv.registration_step = ""`, `conv.stage = STAGE_LEAD`-эквивалент не трогает

Поле `child_birth` в payload — одна строка: «15.03.2016», «2016-03-15» или «9» / «9 лет».

- [ ] **Step 1: Write the failing test** — `bot/tests/test_registration_form.py`

```python
"""Серверная валидация анкеты мини-приложения."""
from app import registration_form as rf
from app.memory import Conversation

OK = {
    "fio_parent": "Анна Петрова",
    "fio_child": "Маша",
    "child_birth": "15.03.2016",
    "phone": "+7 (916) 123-45-67",
    "consents": {"pd_child": True, "privacy": True, "marketing": True},
}


def test_valid_form_passes():
    form, errors = rf.validate(OK)
    assert errors == {}
    assert form.fio_parent == "Анна Петрова"
    assert form.birthday == "2016-03-15"
    assert form.age == ""
    assert form.phone.endswith("9161234567")


def test_age_instead_of_birthday():
    form, errors = rf.validate({**OK, "child_birth": "9 лет"})
    assert errors == {}
    assert form.age == "9" and form.birthday == ""


def test_garbage_names_rejected():
    _, errors = rf.validate({**OK, "fio_parent": "привет", "fio_child": "ааа"})
    assert set(errors) >= {"fio_parent", "fio_child"}


def test_bad_phone_and_birth_rejected():
    _, errors = rf.validate({**OK, "phone": "123", "child_birth": "1890-01-01"})
    assert set(errors) >= {"phone", "child_birth"}


def test_required_consents_enforced_marketing_optional():
    _, errors = rf.validate({**OK, "consents": {"pd_child": True, "privacy": False}})
    assert "consents" in errors
    form, errors = rf.validate({**OK, "consents": {"pd_child": True, "privacy": True}})
    assert errors == {} and form.consents["marketing"] is False


def test_apply_marks_registered_and_fills_lead():
    conv = Conversation(user_id="tg:1")
    form, _ = rf.validate(OK)
    rf.apply(conv, form)
    assert conv.registered is True
    assert conv.registration_step == ""
    assert conv.lead.fio_child == "Маша"
    assert conv.lead.birthday == "2016-03-15"


def test_apply_keeps_confirmed_phone_when_same_number():
    conv = Conversation(user_id="tg:1")
    conv.lead.set_phone("+79161234567", confirmed=True)
    form, _ = rf.validate(OK)
    rf.apply(conv, form)
    assert conv.lead.phone_confirmed is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/grigory/Dymova-english/bot && python -m pytest tests/test_registration_form.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.registration_form'`

- [ ] **Step 3: Check `Conversation` constructor and phone format**

Run: `cd /Users/grigory/Dymova-english/bot && grep -n "class Conversation" -A6 app/memory.py && python -c "from app.intent import extract_phone; print(extract_phone('+7 (916) 123-45-67'))"`
Expected: видно, что `Conversation(user_id=...)` допустим; `extract_phone` возвращает нормализованный номер. Если конструктор требует другие аргументы — поправить тест под фактическую сигнатуру.

- [ ] **Step 4: Write `bot/app/registration_form.py`**

```python
"""Анкета мини-приложения: серверная валидация и запись в диалог.

Форма заменяет четыре вопроса в переписке. Правила проверки — те же, что
у пошаговой анкеты (registration.py): в CRM не должны уезжать «Привет»
вместо имени и 1890 год вместо даты рождения, откуда бы ни пришли данные.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app import consents
from app.intent import extract_age, extract_birthday, extract_phone
from app.memory import Conversation
from app.registration import _looks_like_name, _plausible_age, _plausible_birthday


@dataclass
class FormData:
    fio_parent: str
    fio_child: str
    birthday: str
    age: str
    phone: str
    consents: dict[str, bool] = field(default_factory=dict)


def _clean(value: object, limit: int = 255) -> str:
    return " ".join(str(value or "").split())[:limit]


def _child_birth(raw: str) -> tuple[str, str]:
    """(birthday ISO, age) — заполнено ровно одно, либо оба пустые."""
    birthday = extract_birthday(raw)
    if birthday and _plausible_birthday(birthday):
        return birthday, ""
    age = extract_age(raw) or (raw if raw.isdigit() and len(raw) <= 2 else "")
    if age and _plausible_age(age):
        return "", str(int(age))
    return "", ""


def validate(payload: dict) -> tuple[FormData | None, dict[str, str]]:
    errors: dict[str, str] = {}
    fio_parent = _clean(payload.get("fio_parent"))
    fio_child = _clean(payload.get("fio_child"))
    if not _looks_like_name(fio_parent):
        errors["fio_parent"] = "Укажите имя и фамилию родителя"
    if not _looks_like_name(fio_child):
        errors["fio_child"] = "Укажите имя ребёнка"
    birthday, age = _child_birth(_clean(payload.get("child_birth"), 40))
    if not birthday and not age:
        errors["child_birth"] = "Укажите дату рождения (15.03.2016) или возраст (9)"
    phone = extract_phone(_clean(payload.get("phone"), 40)) or ""
    if not phone:
        errors["phone"] = "Укажите телефон в формате +7 900 123-45-67"
    raw_consents = payload.get("consents") if isinstance(payload.get("consents"), dict) else {}
    accepted = {kind: bool(raw_consents.get(kind)) for kind in consents.CONSENT_LABELS}
    if not all(accepted[kind] for kind in consents.REQUIRED):
        errors["consents"] = "Без обязательных согласий мы не можем сохранить анкету"
    if errors:
        return None, errors
    return FormData(fio_parent, fio_child, birthday, age, phone, accepted), {}


def apply(conv: Conversation, form: FormData) -> None:
    lead = conv.lead
    lead.fio_parent = form.fio_parent
    lead.fio_child = form.fio_child
    lead.birthday = form.birthday
    lead.age = form.age
    # set_phone сам сохранит подтверждение, если номер совпал с тем, что
    # человек уже отдал нативным контактом Telegram.
    lead.set_phone(form.phone)
    conv.registered = True
    conv.registration_step = ""
```

- [ ] **Step 5: Run tests**

Run: `cd /Users/grigory/Dymova-english/bot && python -m pytest tests/test_registration_form.py tests/test_registration.py tests/test_registration_strict.py -v`
Expected: все PASS.

- [ ] **Step 6: Commit**

```bash
cd /Users/grigory/Dymova-english
git add bot/app/registration_form.py bot/tests/test_registration_form.py
git commit -m "feat(bot): серверная валидация анкеты мини-приложения

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Ручка `POST /api/miniapp/register` и состояние доступа

**Files:**
- Modify: `bot/app/main.py` — `_miniapp_access_state` (~стр. 283), новая ручка рядом с `/api/miniapp/lead` (~стр. 1774)
- Modify: `bot/app/registration.py` — `_submit_registration` принимает `source` и `extra_note`
- Test: `bot/tests/test_miniapp_register.py`

**Interfaces:**
- Consumes: `consents.record/has_required/summary_line/CONSENT_LABELS/CONSENT_LINKS/LEGAL_VERSION`, `registration_form.validate/apply`
- Produces:
  - `POST /api/miniapp/register` body `{fio_parent, fio_child, child_birth, phone, consents:{pd_child,privacy,marketing}}` → `200 {"ok":true,"access":{...}}` | `400 {"ok":false,"errors":{field:msg}}` | `401` без подписи
  - `POST /api/miniapp/consents` body `{consents:{...}}` — только согласия для уже зарегистрированных → `200 {"ok":true}` | `400`
  - `_miniapp_access_state(...)` дополнительно отдаёт: `"needs_consents": bool`, `"legal": {"version", "labels", "links"}`, `"prefill": {"fio_parent", "fio_child", "child_birth", "phone", "phone_confirmed"}`
  - `registration._submit_registration(conv, bigben, source: str = "MAX-бот Фоксинбург — регистрация", extra_note: str = "")`

- [ ] **Step 1: Write the failing test** — `bot/tests/test_miniapp_register.py`

```python
"""Анкета мини-приложения: ручка регистрации и согласий."""
import pytest
from fastapi.testclient import TestClient

from app import consents, crm_store, registration
from app import main as main_module
from app import memory as memory_module
from app.config import settings
from app.memory import get_store
from tests.conftest import make_telegram_init_data

TOKEN = "123456:AA-test-token"
FORM = {
    "fio_parent": "Анна Петрова",
    "fio_child": "Маша",
    "child_birth": "9",
    "phone": "+79161234567",
    "consents": {"pd_child": True, "privacy": True, "marketing": True},
}


def auth(uid: int = 777) -> dict:
    return {
        "X-Miniapp-Init-Data": make_telegram_init_data(TOKEN, telegram_user_id=uid),
        "X-Miniapp-Platform": "telegram",
    }


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    memory_module._store = None
    crm_store.reset()
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", TOKEN, raising=False)
    monkeypatch.setattr(settings, "MINIAPP_AUTH_REQUIRED", True, raising=False)
    monkeypatch.setattr(settings, "MINIAPP_REQUIRE_REGISTRATION", True, raising=False)
    monkeypatch.setattr(settings, "REGISTRATION_REQUIRED", True, raising=False)
    sent_leads: list[dict] = []

    async def fake_submit(conv, bigben, source="", extra_note=""):
        sent_leads.append({"user": conv.user_id, "source": source, "note": extra_note})

    monkeypatch.setattr(registration, "_submit_registration", fake_submit)
    chat_messages: list[tuple] = []

    async def fake_notify(identity, text):
        chat_messages.append((identity.user_id, text))

    monkeypatch.setattr(main_module, "_notify_registered_in_chat", fake_notify)
    main_module._test_sent_leads = sent_leads
    main_module._test_chat_messages = chat_messages
    yield
    memory_module._store = None
    crm_store.reset()


def test_register_requires_signed_identity():
    client = TestClient(main_module.app)
    resp = client.post("/api/miniapp/register", json=FORM)
    assert resp.status_code == 401


def test_access_state_locked_with_legal_texts_before_form():
    client = TestClient(main_module.app)
    access = client.get("/api/miniapp/access", headers=auth()).json()
    assert access["locked"] is True
    assert access["legal"]["version"] == consents.LEGAL_VERSION
    assert set(access["legal"]["labels"]) == {"pd_child", "privacy", "marketing"}


def test_register_happy_path_unlocks_and_sends_everywhere():
    client = TestClient(main_module.app)
    resp = client.post("/api/miniapp/register", json=FORM, headers=auth())
    body = resp.json()
    assert resp.status_code == 200 and body["ok"] is True
    assert body["access"]["locked"] is False
    conv = get_store().get("tg:777", platform="telegram")
    assert conv.registered and conv.lead.fio_child == "Маша"
    assert consents.has_required("telegram", "tg:777")
    lead = main_module._test_sent_leads[0]
    assert "Согласия" in lead["note"] and "мини-приложение" in lead["source"]
    assert main_module._test_chat_messages[0][0] == "tg:777"
    row = crm_store.get_conn().execute(
        "SELECT c.name, c.child_name FROM customers c JOIN customer_identities i"
        " ON i.customer_id = c.id WHERE i.channel = 'telegram' AND i.external_id = 'tg:777'"
    ).fetchone()
    assert row is not None and row["child_name"] == "Маша"


def test_register_validation_errors_returned_per_field():
    client = TestClient(main_module.app)
    bad = {**FORM, "fio_parent": "привет", "consents": {"pd_child": True}}
    resp = client.post("/api/miniapp/register", json=bad, headers=auth())
    assert resp.status_code == 400
    assert set(resp.json()["errors"]) >= {"fio_parent", "consents"}
    assert not get_store().get("tg:777", platform="telegram").registered


def test_old_registered_user_needs_consents_only():
    store = get_store()
    conv = store.get("tg:777", platform="telegram")
    conv.registered = True
    store.save(conv)
    client = TestClient(main_module.app)
    access = client.get("/api/miniapp/access", headers=auth()).json()
    assert access["locked"] is False and access["needs_consents"] is True
    resp = client.post("/api/miniapp/consents",
                       json={"consents": {"pd_child": True, "privacy": True, "marketing": True}},
                       headers=auth())
    assert resp.status_code == 200
    access = client.get("/api/miniapp/access", headers=auth()).json()
    assert access["needs_consents"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/grigory/Dymova-english/bot && python -m pytest tests/test_miniapp_register.py -v`
Expected: FAIL — 404/405 на `/api/miniapp/register`, `KeyError: 'legal'`, `AttributeError: _notify_registered_in_chat`.

- [ ] **Step 3: Extend `_submit_registration` in `bot/app/registration.py`**

Заменить сигнатуру и сборку заметки:

```python
async def _submit_registration(
    conv: Conversation,
    bigben: BigBenClient,
    source: str = "MAX-бот Фоксинбург — регистрация",
    extra_note: str = "",
) -> None:
    """Submit registration data as a lead to BigBen CRM."""
    lead = conv.lead
    note = (
        f"Регистрация в боте. "
        f"Родитель: {lead.fio_parent}. "
        f"Ребёнок: {lead.fio_child}. "
        f"{'Дата рождения: ' + lead.birthday if lead.birthday else 'Возраст: ' + (lead.age or '—')}. "
        f"Телефон: {lead.phone}{' (подтверждён Telegram)' if lead.phone_confirmed else ''}."
    )
    if extra_note:
        note = f"{note} {extra_note}"
```

(остальное тело функции без изменений; `source` теперь параметр).

- [ ] **Step 4: Extend `_miniapp_access_state` in `bot/app/main.py`**

Добавить `from app import consents, registration_form` к импортам `from app import …` в начале файла. В `_miniapp_access_state` после вычисления `registered`:

```python
    needs_consents = False
    prefill: dict = {}
    if identity is not None:
        conv = get_store().get(identity.user_id, platform=identity.platform)
        needs_consents = registered and not consents.has_required(
            identity.platform, identity.user_id
        )
        lead = conv.lead
        prefill = {
            "fio_parent": lead.fio_parent or identity.display_name or "",
            "fio_child": lead.fio_child,
            "child_birth": lead.birthday or lead.age,
            "phone": lead.phone,
            "phone_confirmed": bool(lead.phone_confirmed),
        }
```

Сообщение для locked заменить на `"Заполните короткую анкету — и всё откроется."`. В возвращаемый dict добавить:

```python
        "needs_consents": needs_consents,
        "prefill": prefill,
        "legal": {
            "version": consents.LEGAL_VERSION,
            "labels": consents.CONSENT_LABELS,
            "links": consents.CONSENT_LINKS,
        },
```

- [ ] **Step 5: Add endpoints and chat notifier to `bot/app/main.py`** (рядом с `/api/miniapp/lead`)

```python
REGISTERED_CHAT_TEXT = (
    "Спасибо! Анкета заполнена ✅ Всё открыто 🦊\n\n"
    "Спрашивайте про курсы, расписание и цены, присылайте домашку — помогу."
)


async def _notify_registered_in_chat(identity, text: str) -> None:
    """Подтверждение в нативный чат мессенджера: человек вернётся в чат и
    должен видеть, что анкета дошла, а не гадать, нажалась ли кнопка."""
    try:
        if identity.platform == TELEGRAM_PLATFORM:
            chat_id = identity.user_id.removeprefix("tg:")
            await get_telegram().send_message(chat_id, text, buttons=_telegram_menu_buttons(identity.user_id) or None)
        else:
            await get_max().send_message(identity.user_id, text, buttons=_main_menu(identity.user_id))
    except Exception:
        logger.exception("miniapp: не удалось отправить подтверждение анкеты в чат")


def _verified_identity_or_401(request: Request):
    identity = _identity_from_request(request)
    if identity is None or not identity.verified:
        return None, JSONResponse(
            {"ok": False, "error": "Откройте анкету внутри Telegram или MAX"}, status_code=401
        )
    return identity, None


@app.post("/api/miniapp/register")
async def miniapp_register(request: Request, data: dict) -> dict:
    """Анкета мини-приложения вместо четырёх вопросов в переписке."""
    identity, error = _verified_identity_or_401(request)
    if error:
        return error
    form, errors = registration_form.validate(data if isinstance(data, dict) else {})
    if errors:
        return JSONResponse({"ok": False, "errors": errors}, status_code=400)
    store = get_store()
    conv = store.get(identity.user_id, platform=identity.platform)
    registration_form.apply(conv, form)
    conv.add("assistant", "[анкета мини-приложения заполнена]")
    store.save(conv)
    consents.record(identity.platform, identity.user_id, form.consents, channel="miniapp")
    crm_store.upsert_customer_for_identity(
        identity.platform, identity.user_id,
        name=form.fio_parent, phone=conv.lead.phone,
        child_name=form.fio_child, child_age=form.age or form.birthday,
        source="анкета мини-приложения",
    )
    platform_name = "Telegram" if identity.platform == TELEGRAM_PLATFORM else "MAX"
    await registration._submit_registration(
        conv, get_bigben(),
        source=f"{platform_name} мини-приложение — анкета",
        extra_note=consents.summary_line(identity.platform, identity.user_id),
    )
    await _notify_registered_in_chat(identity, REGISTERED_CHAT_TEXT)
    return {"ok": True, "access": _miniapp_access_state(identity)}


@app.post("/api/miniapp/consents")
async def miniapp_consents(request: Request, data: dict) -> dict:
    """Только согласия — для клиентов, прошедших старую анкету в чате."""
    identity, error = _verified_identity_or_401(request)
    if error:
        return error
    raw = data.get("consents") if isinstance(data.get("consents"), dict) else {}
    accepted = {kind: bool(raw.get(kind)) for kind in consents.CONSENT_LABELS}
    if not all(accepted[kind] for kind in consents.REQUIRED):
        return JSONResponse({"ok": False, "errors": {"consents": "Нужны обязательные согласия"}}, status_code=400)
    consents.record(identity.platform, identity.user_id, accepted, channel="miniapp")
    return {"ok": True}
```

Проверить, что в `main.py` уже импортированы `crm_store`, `get_bigben`, `get_max`, `get_telegram`, `logger`: `grep -n "^from app.bigben\|^from app import crm_store\|crm_store" app/main.py | head -3`. Недостающее — добавить в импорты.

- [ ] **Step 6: Run tests**

Run: `cd /Users/grigory/Dymova-english/bot && python -m pytest tests/test_miniapp_register.py tests/test_cabinet.py tests/test_max_miniapp.py tests/test_miniapp_auth.py tests/test_registration.py -v`
Expected: все PASS.

- [ ] **Step 7: Commit** (только свои hunks `main.py`)

```bash
cd /Users/grigory/Dymova-english
git add bot/app/registration.py bot/tests/test_miniapp_register.py
git add -p bot/app/main.py   # принять только hunks этой задачи
git commit -m "feat(bot): ручка анкеты мини-приложения — лид в BigBen, согласия, CRM, подтверждение в чат

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Приглашение с кнопкой вместо вопросов в чате

**Files:**
- Modify: `bot/app/registration.py` — константа `FORM_INVITE`, функция `start_registration(conv, platform="")`
- Modify: `bot/app/ai_core.py` — гейт ~стр. 596–650 и `/start` ~стр. 1230
- Modify: `bot/app/main.py` — `_telegram_buttons`, `_telegram_start_buttons`, `_link_button_rows`, `_start_buttons`
- Test: `bot/tests/test_registration_invite.py`

**Interfaces:**
- Consumes: `settings.telegram_miniapp_url`, `settings.MINIAPP_BASE_URL`
- Produces:
  - `registration.FORM_INVITE: str` (содержит маркер `registration.FORM_INVITE_MARK = "📝 Заполнить анкету"`)
  - `registration.FORM_PLATFORMS = ("telegram", "max")`
  - `registration.uses_form(platform: str) -> bool` — True для TG/MAX, если задан URL мини-приложения
  - `main._register_button_rows(platform: str) -> list[list[dict]]`

- [ ] **Step 1: Write the failing test** — `bot/tests/test_registration_invite.py`

```python
"""Незарегистрированный клиент TG/MAX получает кнопку анкеты, а не вопросы."""
import pytest

from app import ai_core, registration
from app import main as main_module
from app import memory as memory_module
from app.config import settings


@pytest.fixture(autouse=True)
def gate_on(monkeypatch):
    memory_module._store = None
    monkeypatch.setattr(settings, "REGISTRATION_REQUIRED", True, raising=False)
    monkeypatch.setattr(settings, "MINIAPP_BASE_URL", "https://bot.example.ru/app/", raising=False)
    yield
    memory_module._store = None


@pytest.mark.asyncio
@pytest.mark.parametrize("platform,user", [("telegram", "tg:5"), ("max", "55")])
async def test_first_message_gets_form_invite(platform, user):
    reply = await ai_core.handle_message(user, "Здравствуйте, сколько стоит?", platform=platform)
    assert registration.FORM_INVITE_MARK in reply
    assert "Как вас зовут" not in reply


@pytest.mark.asyncio
async def test_web_widget_keeps_step_by_step():
    reply = await ai_core.handle_message("web:1", "привет", platform="web")
    assert registration.FORM_INVITE_MARK not in reply


def test_telegram_invite_gets_webapp_button_to_register():
    rows = main_module._telegram_buttons("привет", registration.FORM_INVITE)
    button = rows[0][0]
    assert button["type"] == "web_app"
    assert button["web_app"].endswith("/tg/#register")


def test_max_invite_gets_link_to_register():
    rows = main_module._link_button_rows("привет", registration.FORM_INVITE)
    assert "#register" in str(rows[0][0])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/grigory/Dymova-english/bot && python -m pytest tests/test_registration_invite.py -v`
Expected: FAIL — `AttributeError: module 'app.registration' has no attribute 'FORM_INVITE_MARK'`. (Если `pytest.mark.asyncio` не настроен — посмотреть, как async-тесты пишутся в `tests/test_registration.py`, и повторить тот же приём.)

- [ ] **Step 3: Add invite to `bot/app/registration.py`**

```python
FORM_INVITE_MARK = "📝 Заполнить анкету"
FORM_PLATFORMS = ("telegram", "max")

FORM_INVITE = (
    "Привет! 🦊 Я — Фокси из языковой школы «Фоксинбург».\n\n"
    "Заполните, пожалуйста, короткую анкету — 30 секунд, и всё откроется: "
    "подбор курса, расписание, запись и помощь с домашкой 😊\n\n"
    f"Нажмите кнопку «{FORM_INVITE_MARK}» ниже 👇"
)


def uses_form(platform: str) -> bool:
    """Анкета-форма живёт в мини-приложении: есть только в Telegram и MAX
    и только когда URL приложения настроен. Веб-виджет сайта остаётся
    на пошаговом опросе в чате."""
    return platform in FORM_PLATFORMS and bool(settings.MINIAPP_BASE_URL.strip())
```

- [ ] **Step 4: Switch the gate in `bot/app/ai_core.py`**

В `_handle_message_locked`, сразу после строки `if not registration.is_registered(conv):` (стр. ~596) вставить первым делом:

```python
        if registration.uses_form(platform) and intent != I.HANDOFF:
            # Анкета — форма в мини-приложении: вопросы по одному в чате
            # занимали несколько минут, люди бросали на середине.
            reply = registration.FORM_INVITE
            conv.add("assistant", reply)
            store.save(conv)
            convlog.log_turn(user_id, text, reply, intent, conv.stage, "registration_form_invite")
            return reply
```

В обработчике `/start` (стр. ~1230) заменить `reply = registration.start_registration(conv)` на:

```python
        reply = (registration.FORM_INVITE if registration.uses_form(platform)
                 else registration.start_registration(conv))
```

(проверить имя параметра платформы в этой функции: `sed -n 1215,1232p app/ai_core.py`).

- [ ] **Step 5: Attach the button in `bot/app/main.py`**

```python
def _register_button_rows(platform: str) -> list[list[dict]]:
    """Кнопка анкеты. В Telegram — web_app: только так мини-приложение
    получает подписанный initData и может принять форму."""
    if platform == TELEGRAM_PLATFORM:
        url = settings.telegram_miniapp_url
        if not url.startswith("https://"):
            return []
        return [[{"type": "web_app", "text": registration.FORM_INVITE_MARK,
                  "web_app": f"{url.split('#', 1)[0]}#register"}]]
    base = _miniapp_url()
    return [[link_button(registration.FORM_INVITE_MARK, f"{base}/#register")]] if base else []
```

В начале `_telegram_buttons(text, reply)`:

```python
    if registration.FORM_INVITE_MARK in (reply or ""):
        return _register_button_rows(TELEGRAM_PLATFORM)
```

В начале `_link_button_rows(text, reply)`:

```python
    if registration.FORM_INVITE_MARK in (reply or ""):
        return _register_button_rows(PLATFORM)
```

В `_telegram_start_buttons(text, reply, user_id)` первой строкой:

```python
    if registration.FORM_INVITE_MARK in (reply or ""):
        return _register_button_rows(TELEGRAM_PLATFORM)
```

В `_start_buttons(user_id, platform)` перед `return menu`:

```python
    if not registration.is_registered(get_store().get(user_id, platform=platform)) and registration.uses_form(platform):
        return _register_button_rows(platform)
```

- [ ] **Step 6: Run tests**

Run: `cd /Users/grigory/Dymova-english/bot && python -m pytest tests/test_registration_invite.py tests/test_registration.py tests/test_registration_strict.py tests/test_telegram_adapter.py tests/test_bot.py -v`
Expected: все PASS. Если старые тесты регистрации проверяли вопросы в чате для telegram/max при заданном `MINIAPP_BASE_URL` — в этих тестах явно выставить `MINIAPP_BASE_URL=""` (пошаговый путь остаётся валидным фолбэком), не удалять их.

- [ ] **Step 7: Commit**

```bash
cd /Users/grigory/Dymova-english
git add bot/app/registration.py bot/app/ai_core.py bot/tests/test_registration_invite.py
git add -p bot/app/main.py
git commit -m "feat(bot): приглашение с кнопкой анкеты вместо вопросов в чате TG/MAX

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Экран анкеты в мини-приложении

**Files:**
- Modify: `bot/app/tgapp/index.html` — секция `#register` перед `<main id="root">`, bump `app.js?v=` и `app.css?v=`
- Modify: `bot/app/tgapp/app.js` — `renderRegister()`, `submitRegister()`, вызов из `loadInfo()`
- Modify: `bot/app/tgapp/app.css` — стили формы
- Test: `bot/tests/test_tgapp.py` (статические проверки контракта фронт↔сервер)

**Interfaces:**
- Consumes: `GET /api/miniapp/info` → `access.locked`, `access.needs_consents`, `access.prefill`, `access.legal`; `POST /api/miniapp/register`, `POST /api/miniapp/consents`
- Produces: DOM `#register` (form `#register-form`, поля `name="fio_parent|fio_child|child_birth|phone"`, чекбоксы `name="consent_pd_child|consent_privacy|consent_marketing"`), класс `body.is-registering`

- [ ] **Step 1: Write the failing test** — дописать в `bot/tests/test_tgapp.py`:

```python
def test_register_form_matches_server_contract():
    html = (TGAPP / "index.html").read_text(encoding="utf-8")
    js = (TGAPP / "app.js").read_text(encoding="utf-8")
    assert 'id="register"' in html and 'id="register-form"' in html
    for field in ("fio_parent", "fio_child", "child_birth", "phone"):
        assert f'name="{field}"' in html
    assert 'name="consent_marketing" checked' in html
    assert "/api/miniapp/register" in js and "/api/miniapp/consents" in js
    assert "requestContact" in js
    assert "needs_consents" in js
```

(если в файле нет константы `TGAPP` — посмотреть, как соседние тесты читают `app/tgapp/index.html`, и сделать так же).

- [ ] **Step 2: Run to verify it fails**

Run: `cd /Users/grigory/Dymova-english/bot && python -m pytest tests/test_tgapp.py::test_register_form_matches_server_contract -v`
Expected: FAIL — `assert 'id="register"' in html`.

- [ ] **Step 3: Markup** — в `index.html` сразу перед `<main id="root" …>`:

```html
  <!-- ===================== АНКЕТА ===================== -->
  <section id="register" class="register" hidden aria-labelledby="register-title">
    <h1 id="register-title" class="register__title">Давайте познакомимся</h1>
    <p class="register__lede">30 секунд — и откроются курсы, расписание, запись и помощь с домашкой.</p>
    <form id="register-form" novalidate>
      <div data-register-profile>
        <label class="field"><span>ФИО родителя</span>
          <input name="fio_parent" autocomplete="name" required /></label>
        <p class="field__error" data-error="fio_parent"></p>
        <label class="field"><span>Имя ребёнка</span>
          <input name="fio_child" required /></label>
        <p class="field__error" data-error="fio_child"></p>
        <label class="field"><span>Дата рождения или возраст ребёнка</span>
          <input name="child_birth" placeholder="15.03.2016 или 9" inputmode="text" required /></label>
        <p class="field__error" data-error="child_birth"></p>
        <label class="field"><span>Телефон</span>
          <input name="phone" type="tel" autocomplete="tel" placeholder="+7 900 123-45-67" required /></label>
        <button type="button" id="register-share-phone" class="ghost" hidden>📞 Поделиться номером из Telegram</button>
        <p class="field__error" data-error="phone"></p>
      </div>
      <fieldset class="consents">
        <label class="consent"><input type="checkbox" name="consent_pd_child" />
          <span data-consent-label="pd_child"></span></label>
        <label class="consent"><input type="checkbox" name="consent_privacy" />
          <span data-consent-label="privacy"></span></label>
        <label class="consent"><input type="checkbox" name="consent_marketing" checked />
          <span data-consent-label="marketing"></span></label>
        <p class="field__error" data-error="consents"></p>
      </fieldset>
      <button type="submit" class="primary register__submit">Готово</button>
      <p id="register-status" class="status" hidden></p>
    </form>
  </section>
```

Поднять версии: `app.js?v=8` → `v=9`, `app.css?v=…` → +1.

- [ ] **Step 4: JS** — в `app.js` добавить (рядом с блоком «загрузка»):

```js
  /* ------------------------------------------------------------- анкета */

  /** Анкета вместо вопросов в чате. Показывается поверх приложения, пока
   *  сервер говорит locked (нет регистрации) или needs_consents (старый
   *  клиент без согласий — тогда только чекбоксы). */
  function renderRegister(access) {
    var box = $("#register");
    var consentsOnly = !access.locked && access.needs_consents;
    if (!access.has_identity || (!access.locked && !access.needs_consents)) {
      box.hidden = true;
      document.body.classList.remove("is-registering");
      return;
    }
    var legal = access.legal || { labels: {}, links: {} };
    all("[data-consent-label]", box).forEach(function (node) {
      var kind = node.dataset.consentLabel;
      node.textContent = legal.labels[kind] || "";
      if (legal.links[kind]) {
        var link = document.createElement("a");
        link.href = legal.links[kind];
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = " (текст)";
        node.appendChild(link);
      }
    });
    var profile = $("[data-register-profile]", box);
    profile.hidden = consentsOnly;
    $("#register-title").textContent = consentsOnly ? "Остался один шаг" : "Давайте познакомимся";
    var prefill = access.prefill || {};
    var form = $("#register-form");
    ["fio_parent", "fio_child", "child_birth", "phone"].forEach(function (name) {
      if (prefill[name] && !form.elements[name].value) form.elements[name].value = prefill[name];
    });
    var share = $("#register-share-phone");
    share.hidden = !(bridge && typeof bridge.requestContact === "function") || !!prefill.phone_confirmed;
    box.hidden = false;
    document.body.classList.add("is-registering");
    state.registerConsentsOnly = consentsOnly;
  }

  function sharePhone() {
    // Telegram присылает контакт и боту (вебхук помечает номер
    // подтверждённым), и в колбэк — им заполняем поле сразу.
    bridge.requestContact(function (shared, response) {
      var phone = shared && response && response.responseUnsafe &&
        response.responseUnsafe.contact && response.responseUnsafe.contact.phone_number;
      if (phone) $("#register-form").elements.phone.value = "+" + String(phone).replace(/^\+/, "");
    });
  }

  function submitRegister(event) {
    event.preventDefault();
    var form = event.target;
    var status = $("#register-status");
    all("[data-error]", form).forEach(function (n) { n.textContent = ""; });
    var consents = {
      pd_child: form.elements.consent_pd_child.checked,
      privacy: form.elements.consent_privacy.checked,
      marketing: form.elements.consent_marketing.checked,
    };
    var path = state.registerConsentsOnly ? "/api/miniapp/consents" : "/api/miniapp/register";
    var body = state.registerConsentsOnly ? { consents: consents } : {
      fio_parent: form.elements.fio_parent.value.trim(),
      fio_child: form.elements.fio_child.value.trim(),
      child_birth: form.elements.child_birth.value.trim(),
      phone: form.elements.phone.value.trim(),
      consents: consents,
    };
    status.hidden = false;
    status.textContent = "Сохраняю…";
    postJSON(path, body)
      .then(function (data) {
        if (data && data.ok) {
          haptic("success");
          status.hidden = true;
          loadInfo();
          return;
        }
        status.textContent = "Проверьте поля, отмеченные ниже.";
        var errors = (data && data.errors) || {};
        Object.keys(errors).forEach(function (key) {
          var slot = $('[data-error="' + key + '"]', form);
          if (slot) slot.textContent = errors[key];
        });
        haptic("error");
      })
      .catch(function () {
        status.textContent = "Нет связи. Попробуйте ещё раз.";
      });
  }
```

В `loadInfo()` после `state.access = data.access || null;` добавить `if (state.access) renderRegister(state.access);`.
В `bind()` добавить:

```js
    $("#register-form").addEventListener("submit", submitRegister);
    $("#register-share-phone").addEventListener("click", sharePhone);
    if (location.hash === "#register") history.replaceState(null, "", location.pathname);
```

Проверить, что `postJSON` возвращает тело при 4xx (ищем `__status` в `request`): `sed -n 180,215p app/tgapp/app.js`. Если 400 отдаётся как `{…, __status:400}` — код выше работает как есть.

- [ ] **Step 5: CSS** — в `app.css`, в конец:

```css
/* Анкета: полноэкранный слой поверх приложения до регистрации. */
body.is-registering #root { display: none; }
.register { padding: 24px 16px 40px; max-width: 520px; margin: 0 auto; }
.register__title { font-size: 28px; line-height: 1.15; margin: 8px 0 6px; }
.register__lede { color: var(--muted, #6b6b6b); margin: 0 0 20px; }
.register .field { display: flex; flex-direction: column; gap: 6px; margin-top: 12px; font-weight: 600; }
.register .field input { font: inherit; font-weight: 400; padding: 12px 14px; border-radius: 12px;
  border: 1px solid rgba(0,0,0,.14); background: #fff; }
.field__error { color: #c0392b; font-size: 13px; margin: 4px 0 0; min-height: 0; }
.field__error:empty { display: none; }
.consents { border: 0; padding: 0; margin: 20px 0 0; display: grid; gap: 12px; }
.consent { display: grid; grid-template-columns: 22px 1fr; gap: 10px; align-items: start; font-size: 14px; line-height: 1.35; }
.consent input { width: 20px; height: 20px; margin-top: 1px; }
.register__submit { width: 100%; margin-top: 22px; }
```

(перед этим проверить имена CSS-переменных цвета в начале `app.css`: `sed -n 1,40p app/tgapp/app.css` и использовать существующую переменную приглушённого текста вместо `--muted`, если она называется иначе).

- [ ] **Step 6: Run tests**

Run: `cd /Users/grigory/Dymova-english/bot && python -m pytest tests/test_tgapp.py tests/test_max_miniapp.py tests/test_maxapp_design.py -v && node --check app/tgapp/app.js`
Expected: PASS, `node --check` без вывода.

- [ ] **Step 7: Browser check** — локальный сервер + Playwright:

Run: `cd /Users/grigory/Dymova-english/bot && MINIAPP_AUTH_REQUIRED=false REGISTRATION_REQUIRED=true MINIAPP_BASE_URL=http://127.0.0.1:8099/app/ uvicorn app.main:app --port 8099` (в фоне), открыть `http://127.0.0.1:8099/tg/?user_id=tg:1#register` на ширине 390px.
Expected: видна форма, чекбокс рассылок отмечен, ссылки «(текст)» у двух обязательных; без обязательных галочек «Готово» показывает ошибку у согласий. (Без подписи initData отправка вернёт 401 — это ожидаемо; полный путь проверяется на проде в Task 7.)

- [ ] **Step 8: Commit**

```bash
cd /Users/grigory/Dymova-english
git add -p bot/app/tgapp/index.html bot/app/tgapp/app.js bot/app/tgapp/app.css bot/tests/test_tgapp.py
git commit -m "feat(bot): экран анкеты с согласиями в мини-приложении

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Согласия в карточке клиента админки

**Files:**
- Modify: `bot/app/crm_store.py` — `get_customer` (~стр. 836)
- Modify: `bot/app/adminapp/app.js` — `customerCardHtml` (~стр. 745)
- Test: `bot/tests/test_client_card.py`

**Interfaces:**
- Consumes: таблица `consents`, `customer_identities`
- Produces: `get_customer(id)["consents"]: list[dict]` — `{type, accepted, legal_version, default_checked, created_at, channel}` по последней записи каждого типа по всем идентичностям клиента

- [ ] **Step 1: Write the failing test** — дописать в `bot/tests/test_client_card.py`:

```python
def test_customer_card_shows_consents():
    from app import consents, crm_store
    crm_store.reset()
    cid = crm_store.upsert_customer_for_identity("telegram", "tg:9", name="Анна")
    consents.record("telegram", "tg:9", {"pd_child": True, "privacy": True, "marketing": True}, channel="miniapp")
    card = crm_store.get_customer(cid)
    kinds = {c["type"]: c for c in card["consents"]}
    assert kinds["pd_child"]["accepted"] is True
    assert kinds["marketing"]["default_checked"] is True
    crm_store.reset()
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /Users/grigory/Dymova-english/bot && python -m pytest tests/test_client_card.py::test_customer_card_shows_consents -v`
Expected: FAIL — `KeyError: 'consents'`.

- [ ] **Step 3: Implement in `get_customer`** — перед `customer["counts"] = {`:

```python
    latest_by_type: dict[str, dict] = {}
    for ident in customer["identities"]:
        for row in conn.execute(
            "SELECT type, accepted, legal_version, channel, default_checked, created_at"
            " FROM consents WHERE platform = ? AND user_id = ? ORDER BY id",
            (ident["channel"], ident["external_id"]),
        ):
            item = dict(row)
            item["accepted"] = bool(item["accepted"])
            item["default_checked"] = bool(item["default_checked"])
            prev = latest_by_type.get(item["type"])
            if prev is None or item["created_at"] >= prev["created_at"]:
                latest_by_type[item["type"]] = item
    customer["consents"] = list(latest_by_type.values())
```

- [ ] **Step 4: Render in admin** — в `customerCardHtml` после секции «Ребёнок»:

```js
    <div class="c360__section">
      <h4>Согласия</h4>
      ${(c.consents || []).length ? `<dl class="kv">${c.consents.map((k) => `
        <dt>${esc(CONSENT_NAMES[k.type] || k.type)}</dt>
        <dd>${k.accepted ? "✅ да" : "— нет"}${k.default_checked ? " <span class=\"muted\">(галочка стояла по умолчанию)</span>" : ""}
          <div class="muted">${esc(fmtTime(k.created_at))} · версия ${esc(k.legal_version)}</div></dd>`).join("")}</dl>`
        : `<span class="muted">Анкета с согласиями ещё не заполнена</span>`}
    </div>
```

И над функцией:

```js
const CONSENT_NAMES = { pd_child: "ПД ребёнка", privacy: "Политика конф.", marketing: "Рассылки" };
```

- [ ] **Step 5: Run tests**

Run: `cd /Users/grigory/Dymova-english/bot && python -m pytest tests/test_client_card.py tests/test_customer360.py tests/test_admin_api.py tests/test_adminapp.py -v && node --check app/adminapp/app.js`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd /Users/grigory/Dymova-english
git add bot/app/crm_store.py bot/app/adminapp/app.js bot/tests/test_client_card.py
git commit -m "feat(bot): согласия в карточке клиента админки

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Полная проверка, деплой, живой прогон

**Files:**
- Modify: `DEVLOG.md` (запись о сессии)

- [ ] **Step 1: Full test suite**

Run: `cd /Users/grigory/Dymova-english/bot && python -m pytest -q -x --ignore=tests/benchmark`
Expected: 0 failed. Упавшие тесты чинить по сути (не ослаблять), особенно `test_bot.py`/`test_e2e_flows.py`, где мог жёстко ожидаться пошаговый опрос для telegram/max.

- [ ] **Step 2: Review** — `superpowers:requesting-code-review` по диффу задач 1–6; устранить замечания.

- [ ] **Step 3: Deploy** — по `bot/DEPLOY.md` (прочитать перед выполнением). Владелец разрешил мерж и деплой без отдельного подтверждения. Перед деплоем убедиться, что чужие незакоммиченные правки из Global Constraints либо закоммичены владельцем, либо не попадают в сборку неожиданно (сборка идёт из рабочего дерева сервера — проверить по DEPLOY.md, откуда).

- [ ] **Step 4: Live check on prod**

Run: `ssh yc-user@89.169.132.104 'docker exec bot-bot-1 python -c "from app import consents; print(consents.LEGAL_VERSION)"; docker logs --since 5m bot-bot-1 2>&1 | grep -ciE "error|traceback"'`
Expected: `2026-09-19`, число ошибок 0 (или только известные до деплоя).
Вручную (владелец или через тестовый аккаунт): написать боту в Telegram новым аккаунтом → пришла кнопка «📝 Заполнить анкету» → форма → «Готово» → в чате «Спасибо! Анкета заполнена ✅», в BigBen новый лид с «Согласия (…)» в заметке, в админке в карточке блок «Согласия».

- [ ] **Step 5: DEVLOG + commit**

```bash
cd /Users/grigory/Dymova-english
git add DEVLOG.md
git commit -m "docs(bot): журнал — анкета-форма с согласиями в мини-приложении

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```
