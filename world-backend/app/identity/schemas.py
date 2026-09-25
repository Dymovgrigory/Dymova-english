"""Pydantic-схемы регистрации: анкета, нормализация телефона, согласия."""
from __future__ import annotations

import re
from datetime import date

from pydantic import BaseModel, Field, field_validator, model_validator

NAME_RE = re.compile(r"^[A-Za-zА-Яа-яЁё]+([ -][A-Za-zА-Яа-яЁё]+)*$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_phone(raw: str) -> str:
    """8 916 123-45-67 / +7... / 7... → +7XXXXXXXXXX. ValueError при мусоре."""
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) == 10:
        digits = "7" + digits
    if len(digits) != 11 or not digits.startswith("7"):
        raise ValueError("phone must be a RU mobile (+7XXXXXXXXXX)")
    return "+" + digits


def mask_phone(phone_e164: str) -> str:
    """+79161234567 → +7 916 ***-**-67."""
    d = re.sub(r"\D", "", phone_e164)
    if len(d) == 11:
        return f"+7 {d[1:4]} ***-**-{d[9:11]}"
    return "***"


def format_phone(phone_e164: str) -> str:
    """+79161234567 → +7 916 123-45-67 (полный номер для админки)."""
    d = re.sub(r"\D", "", phone_e164 or "")
    if len(d) == 11 and d.startswith("7"):
        return f"+7 {d[1:4]} {d[4:7]}-{d[7:9]}-{d[9:11]}"
    return (phone_e164 or "").strip() or "***"


def mask_email(email: str) -> str:
    """mama@example.com → m***a@example.com."""
    local, _, domain = email.partition("@")
    if not domain or not local:
        return "***"
    if len(local) <= 2:
        return f"{local[:1]}***@{domain}"
    return f"{local[0]}***{local[-1]}@{domain}"


def age_on(birth: date, today: date) -> int:
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


def _require_email(v: str) -> str:
    v = v.strip().lower()
    if not EMAIL_RE.match(v):
        raise ValueError("bad email")
    return v


def _optional_email(v: str | None) -> str | None:
    if v is None or not str(v).strip():
        return None
    return _require_email(str(v))


def _optional_phone(v: str | None) -> str | None:
    if v is None or not str(v).strip():
        return None
    return normalize_phone(v)


def _require_password(v: str) -> str:
    if len(v) < 8:
        raise ValueError("password too short")
    return v


class ConsentIn(BaseModel):
    type: str = Field(min_length=1, max_length=40)
    version: str = Field(min_length=1, max_length=40)


class RegistrationStart(BaseModel):
    first_name: str = Field(min_length=1, max_length=60)
    last_name: str = Field(min_length=1, max_length=60)
    birth_date: str
    school_number: str = Field(min_length=1, max_length=20)
    class_grade: int = Field(ge=1, le=11)
    class_letter: str | None = Field(default=None, max_length=3)
    parent_email: str = Field(max_length=120)
    parent_phone: str
    password: str = Field(min_length=8, max_length=128)
    channel: str = "email"
    consents: list[ConsentIn] = Field(default_factory=list)

    @field_validator("first_name", "last_name")
    @classmethod
    def _name_ok(cls, v: str) -> str:
        v = v.strip()
        if not v or not NAME_RE.match(v):
            raise ValueError("only letters, hyphen and space")
        return v

    @field_validator("birth_date")
    @classmethod
    def _birth_ok(cls, v: str) -> str:
        try:
            d = date.fromisoformat(v)
        except ValueError:
            raise ValueError("birth_date must be YYYY-MM-DD")
        if not 3 <= age_on(d, date.today()) <= 17:
            raise ValueError("age must be between 3 and 17")
        return v

    @field_validator("parent_email")
    @classmethod
    def _email_ok(cls, v: str) -> str:
        return _require_email(v)

    @field_validator("parent_phone")
    @classmethod
    def _phone_ok(cls, v: str) -> str:
        return normalize_phone(v)

    @field_validator("password")
    @classmethod
    def _password_ok(cls, v: str) -> str:
        return _require_password(v)

    @field_validator("channel")
    @classmethod
    def _channel_ok(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in ("email", "telegram"):
            raise ValueError("channel must be email or telegram")
        return v

    @field_validator("class_letter")
    @classmethod
    def _letter_ok(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


class VerifyBody(BaseModel):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class LoginBody(BaseModel):
    email: str = Field(max_length=120)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _email_ok(cls, v: str) -> str:
        return _require_email(v)


class _RecoveryContact(BaseModel):
    """Общий контакт для recovery start/verify: email и/или телефон."""
    email: str | None = Field(default=None, max_length=120)
    phone: str | None = None

    @field_validator("email")
    @classmethod
    def _email_ok(cls, v: str | None) -> str | None:
        return _optional_email(v)

    @field_validator("phone")
    @classmethod
    def _phone_ok(cls, v: str | None) -> str | None:
        return _optional_phone(v)

    @model_validator(mode="after")
    def _one_contact(self) -> _RecoveryContact:
        if not self.email and not self.phone:
            raise ValueError("email or phone required")
        return self


class RecoveryStart(_RecoveryContact):
    """Восстановление: email из анкеты и/или телефон родителя (код уйдёт на email)."""


class RecoveryVerify(_RecoveryContact):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class RecoveryPassword(BaseModel):
    reset_token: str = Field(min_length=8, max_length=64)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def _password_ok(cls, v: str) -> str:
        return _require_password(v)


class IdentityPatch(BaseModel):
    """PATCH анкеты из админки: любой поднабор полей + обязательная reason."""
    first_name: str | None = Field(default=None, min_length=1, max_length=60)
    last_name: str | None = Field(default=None, min_length=1, max_length=60)
    birth_date: str | None = None
    school_number: str | None = Field(default=None, min_length=1, max_length=20)
    class_grade: int | None = Field(default=None, ge=1, le=11)
    class_letter: str | None = Field(default=None, max_length=3)
    parent_email: str | None = Field(default=None, max_length=120)
    parent_phone: str | None = None
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("first_name", "last_name")
    @classmethod
    def _name_ok(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v or not NAME_RE.match(v):
            raise ValueError("only letters, hyphen and space")
        return v

    @field_validator("birth_date")
    @classmethod
    def _birth_ok(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return RegistrationStart._birth_ok(v)

    @field_validator("parent_email")
    @classmethod
    def _email_ok(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return _require_email(v)

    @field_validator("parent_phone")
    @classmethod
    def _phone_ok(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return normalize_phone(v)
