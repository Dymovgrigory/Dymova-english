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
