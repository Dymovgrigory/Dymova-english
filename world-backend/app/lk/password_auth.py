"""Вход в ЛК по телефону и паролю + регистрация новых клиентов.

Основной путь (2026-11-05): логин и пароль — те же, что во вкладке «Данные для входа»
карточки ученика в BigBen (внутренний API пульта, см. bigben_internal.py). Регистрация
нового клиента создаёт карточку ученика в BigBen и записывает туда телефон и пароль.
Ниже — запасной путь, если доступа к пульту нет.

Почему не пароль из BigBen: открытый API BigBen v1 (developers.bigbencrm.ru) не отдаёт
и не проверяет «Данные для входа» ученика и не создаёт учеников — только лиды.
Поэтому пароль хранится в ЛК (pbkdf2-хеш), а BigBen получает заявку о новом клиенте.
Когда BigBen добавит проверку логина/пароля, здесь достаточно заменить verify().

Безопасность: аккаунт, созданный самостоятельной регистрацией, не подтверждает
владение номером. Поэтому дети из CRM к нему не подтягиваются, пока номер не подтвердят
бот (как раньше) или администратор (задав пароль в админке) — иначе, указав чужой номер,
можно было бы увидеть чужого ребёнка и его расписание.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from app.identity.passwords import hash_password, verify_password
from app.identity.schemas import mask_phone, normalize_phone
from app.world import core
from app.world.db import get_conn

from . import bigben, bigben_internal, service

log = logging.getLogger("world.lk.password")

MIN_PASSWORD = 6
LOGIN_FAILS_LIMIT = 8          # неудачных входов на номер за окно
LOGIN_FAILS_WINDOW_MIN = 15
REGISTER_DAILY_LIMIT = 5


def _check_password(password: str) -> None:
    if len(password or "") < MIN_PASSWORD:
        raise core.Conflict("password_too_short")
    if len(password) > 200:
        raise core.Conflict("password_too_long")


def _fails(phone: str) -> int:
    since = service._ts(service._now() - timedelta(minutes=LOGIN_FAILS_WINDOW_MIN))
    return int(get_conn().execute(
        "SELECT COUNT(*) AS c FROM lk_auth_attempts WHERE phone=? AND kind='login_fail' AND created_at>?",
        (phone, since)).fetchone()["c"])


def _session_payload(account, status: str) -> dict:
    token, expires = service._issue_session(account["id"])
    profiles = service._sync_profiles(account)
    return {
        "status": status,
        "token": token,
        "token_expires_at": expires,
        "profiles": profiles,
        "guest": all(p["source"] == "guest" for p in profiles),
        "phone_masked": mask_phone(account["phone"]),
    }


def _crm_account(phone: str, parent_name: str = ""):
    """Аккаунт ЛК для номера, подтверждённого CRM (вход по данным из карточки BigBen)."""
    conn = get_conn()
    now = service._ts(service._now())
    account = service._account_by_phone(phone)
    if account is None:
        conn.execute("INSERT INTO lk_accounts (phone, parent_name, status, phone_confirmed_at) VALUES (?,?,?,?)",
                     (phone, parent_name, "active", now))
    else:
        conn.execute("UPDATE lk_accounts SET status='active', phone_confirmed_at=COALESCE(phone_confirmed_at, ?),"
                     " parent_name=CASE WHEN parent_name='' THEN ? ELSE parent_name END, updated_at=datetime('now')"
                     " WHERE id=?", (now, parent_name, account["id"]))
    return service._account_by_phone(phone)


def login(phone: str, password: str) -> dict:
    """Вход: телефон + пароль из «Данных для входа» в карточке BigBen.

    Если карточки нет или пульт недоступен — пароль, заданный в самом ЛК (запасной путь).
    """
    phone = normalize_phone(phone)
    if _fails(phone) >= LOGIN_FAILS_LIMIT:
        raise core.Conflict("too_many_attempts")
    if bigben_internal.configured():
        try:
            cards = bigben_internal.check_login(phone, password or "")
        except bigben_internal.BigBenInternalError as exc:
            log.warning("login: пульт BigBen недоступен (%s), проверяем пароль ЛК", exc)
            cards = []
        if cards:
            parent = next((c.get("parentname") for c in cards if c.get("parentname")), "") or ""
            return _session_payload(_crm_account(phone, parent), "logged_in")
    account = service._account_by_phone(phone)
    ok = bool(account and account["password_hash"] and account["status"] == "active"
              and verify_password(password or "", account["password_hash"]))
    if not ok:
        service._record_attempt(phone, "login_fail")
        # одна и та же ошибка для «нет такого номера» и «неверный пароль»
        raise core.Conflict("bad_credentials")
    return _session_payload(account, "logged_in")


def register(phone: str, password: str, parent_name: str, child_name: str, child_age: str,
             consents, ip: str | None = None) -> dict:
    """Новый клиент (номера нет в CRM): карточка ученика в BigBen с «Данными для входа» —
    телефон и пароль, который придумал родитель (администратор видит его в карточке)."""
    phone = normalize_phone(phone)
    service._check_consents(consents)
    _check_password(password)
    parent_name = " ".join((parent_name or "").split())[:120]
    child_name = " ".join((child_name or "").split())[:120]
    child_age = " ".join((child_age or "").split())[:20]
    if not parent_name or not child_name:
        raise core.Conflict("name_required")
    conn = get_conn()
    day_ago = service._ts(service._now() - timedelta(hours=24))
    if int(conn.execute("SELECT COUNT(*) AS c FROM lk_auth_attempts WHERE phone=? AND kind='register'"
                        " AND created_at>?", (phone, day_ago)).fetchone()["c"]) >= REGISTER_DAILY_LIMIT:
        raise core.Conflict("daily_limit")
    service._record_attempt(phone, "register")

    account = service._account_by_phone(phone)
    if account is not None and account["password_hash"]:
        raise core.Conflict("already_registered")
    comment = f"Регистрация в личном кабинете. Ребёнок: {child_name}" + (f", возраст: {child_age}" if child_age else "")

    if bigben_internal.configured():
        # Номер уже есть в CRM — входить нужно с данными из карточки.
        try:
            if bigben_internal.find_students_by_phone(phone):
                raise core.Conflict("already_client")
            card = bigben_internal.create_student(fio=child_name, phone=phone, parentname=parent_name, comment=comment)
            bigben_internal.set_login_data(int(card["id"]), phone, password)
        except bigben_internal.BigBenInternalError as exc:
            log.warning("register: карточка в BigBen не создана: %s", exc)
            raise core.Conflict("crm_unavailable") from exc
        account = _crm_account(phone, parent_name)
        conn.execute("UPDATE lk_accounts SET crm_lead_id=? WHERE id=?", (f"student:{card['id']}", account["id"]))
        conn.execute(
            "INSERT INTO lk_profiles (account_id, student_id, child_name, source) VALUES (?,?,?,'crm')"
            " ON CONFLICT(account_id, student_id) DO NOTHING", (account["id"], int(card["id"]), child_name))
        out = _session_payload(account, "registered")
        out["crm_card"] = True
        return out

    # Запасной путь (нет доступа к пульту): аккаунт с паролем в ЛК + заявка через публичный API.
    try:
        if bigben.configured() and bigben.students_by_phone(phone):
            raise core.Conflict("already_client")
    except bigben.BigBenUnavailable:
        log.warning("register: BigBen недоступен, проверка клиента пропущена")
    if account is None:
        conn.execute(
            "INSERT INTO lk_accounts (phone, parent_name, status, password_hash) VALUES (?,?,?,?)",
            (phone, parent_name, "active", hash_password(password)))
    else:
        conn.execute(
            "UPDATE lk_accounts SET parent_name=?, status='active', password_hash=?,"
            " updated_at=datetime('now') WHERE id=?", (parent_name, hash_password(password), account["id"]))
    account = service._account_by_phone(phone)
    conn.execute(
        "INSERT INTO lk_profiles (account_id, student_id, child_name, source) VALUES (?,NULL,?,'guest')",
        (account["id"], child_name))
    lead_id = None
    try:
        if bigben.configured():
            lead_id = bigben.create_lead(parent_name, phone, comment, source="Личный кабинет")
    except Exception as exc:  # noqa: BLE001 — заявка не должна ломать регистрацию
        log.warning("register: заявка в BigBen не создана: %s", exc)
    conn.execute("UPDATE lk_accounts SET crm_lead_id=? WHERE id=?", (str(lead_id or ""), account["id"]))
    out = _session_payload(account, "registered")
    out["crm_lead"] = bool(lead_id)
    return out


def set_password(token: str, password: str) -> dict:
    """Задать/сменить пароль из кабинета (после входа через бота или по старому паролю)."""
    account = service.resolve_session(token)
    if account is None:
        raise core.Conflict("unauthorized")
    _check_password(password)
    get_conn().execute("UPDATE lk_accounts SET password_hash=?, updated_at=datetime('now') WHERE id=?",
                       (hash_password(password), account["id"]))
    return {"status": "ok"}


# ---------- администратор ----------

def admin_set_password(phone: str, password: str, parent_name: str = "") -> dict:
    """Администратор задаёт родителю пароль. Это подтверждает номер (администратор знает клиента)."""
    phone = normalize_phone(phone)
    _check_password(password)
    conn = get_conn()
    account = service._account_by_phone(phone)
    now = service._ts(service._now())
    if account is None:
        conn.execute(
            "INSERT INTO lk_accounts (phone, parent_name, status, phone_confirmed_at, password_hash)"
            " VALUES (?,?,?,?,?)", (phone, parent_name.strip(), "active", now, hash_password(password)))
    else:
        conn.execute(
            "UPDATE lk_accounts SET status='active', password_hash=?,"
            " phone_confirmed_at=COALESCE(phone_confirmed_at, ?),"
            " parent_name=CASE WHEN ?<>'' THEN ? ELSE parent_name END, updated_at=datetime('now') WHERE id=?",
            (hash_password(password), now, parent_name.strip(), parent_name.strip(), account["id"]))
    account = service._account_by_phone(phone)
    # пароль сменили — старые сессии закрываем
    conn.execute("UPDATE lk_sessions SET revoked_at=? WHERE account_id=? AND revoked_at IS NULL", (now, account["id"]))
    return {"status": "ok", "phone_masked": mask_phone(phone)}


def admin_accounts(q: str = "") -> dict:
    q = (q or "").strip()
    digits = "".join(ch for ch in q if ch.isdigit())
    sql = ("SELECT a.id, a.phone, a.parent_name, a.status, a.phone_confirmed_at, a.password_hash, a.created_at,"
           " a.crm_lead_id FROM lk_accounts a")
    args: tuple = ()
    if q:
        sql += " WHERE a.parent_name LIKE ? OR a.phone LIKE ?"
        args = (f"%{q}%", f"%{digits or q}%")
    sql += " ORDER BY a.created_at DESC LIMIT 200"
    conn = get_conn()
    rows = conn.execute(sql, args).fetchall()
    kids: dict[int, list[str]] = {}
    for p in conn.execute("SELECT account_id, child_name FROM lk_profiles").fetchall():
        kids.setdefault(int(p["account_id"]), []).append(p["child_name"])
    return {"accounts": [{
        "id": int(r["id"]), "phone": r["phone"], "parent_name": r["parent_name"],
        "kids": ", ".join(kids.get(int(r["id"]), [])),
        "status": r["status"], "verified": bool(r["phone_confirmed_at"]), "has_password": bool(r["password_hash"]),
        "registered_at": r["created_at"], "crm_lead": bool(r["crm_lead_id"]),
    } for r in rows]}
