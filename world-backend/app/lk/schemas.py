"""Pydantic-схемы ЛК: старт авторизации, статус, сессия."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.identity.schemas import normalize_phone

NAME_RE_CHARS = 120


class ConsentIn(BaseModel):
    type: str = Field(min_length=1, max_length=40)
    version: str = Field(min_length=1, max_length=40)


class StartAuth(BaseModel):
    """Старт регистрации/входа: телефон родителя + имя + согласия."""
    phone: str
    parent_name: str = Field(min_length=1, max_length=NAME_RE_CHARS)
    consents: list[ConsentIn] = Field(default_factory=list)

    @field_validator("phone")
    @classmethod
    def _phone_ok(cls, v: str) -> str:
        return normalize_phone(v)

    @field_validator("parent_name")
    @classmethod
    def _name_ok(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("name required")
        return v


class ConfirmBot(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def _phone_ok(cls, v: str) -> str:
        return normalize_phone(v)


class StatusOut(BaseModel):
    status: str  # pending|active
    phone_masked: str
    phone_confirmed: bool
    has_pending: bool
    cooldown_sec: int = 0


class ProfileOut(BaseModel):
    id: int
    student_id: int | None          # id ученика в BigBen; None = гостевой
    child_name: str
    source: str                     # crm|guest
    active_groups: list[dict] = Field(default_factory=list)


class SessionOut(BaseModel):
    status: str                     # awaiting_bot|verified|already_active
    token: str | None = None
    token_expires_at: str | None = None
    profiles: list[ProfileOut] = Field(default_factory=list)
    guest: bool = False             # True — номера нет в CRM, гостевой доступ
    phone_masked: str


class MeOut(BaseModel):
    account: dict
    profiles: list[ProfileOut]
