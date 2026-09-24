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
