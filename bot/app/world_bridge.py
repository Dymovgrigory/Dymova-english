"""Bridge-endpoint для единой регистрации бот ↔ платформа «Мир Фоксинбурга».

World-backend запрашивает данные лида бота, чтобы предзаполнить анкету мира
(родитель/ребёнок уже представлялись в диалоге с ботом — заставлять их
вводить то же самое второй раз было бы потерей конверсии).

Угроза: endpoint отдаёт персональные данные (ФИО, телефон, дата рождения),
поэтому доступ закрыт связкой «HMAC-подпись + свежесть timestamp (±5 минут)».
Секрет должен жить только в общей docker-сети бота и world-backend'а;
подписанный запрос без знания секрета подделать нельзя. Без заданного
WORLD_BRIDGE_SECRET фича выключена и endpoint отвечает 404.

Контракт (зафиксирован с world-backend):
    GET /world-bridge/profile?provider=telegram&user_id=123&ts=<unix>&sign=<hex>
    sign = HMAC_SHA256(key=WORLD_BRIDGE_SECRET,
                       msg=f"{provider}\\n{user_id}\\n{ts}").hexdigest()
    200 {"found": bool, "lead": {...} | null}  — lead содержит только
        непустые поля из {fio_parent, fio_child, birthday, phone}.
    400 {"detail": "bad_provider"}  — provider ∉ {telegram, max}.
    401 {"detail": "stale"}         — |now - ts| > 300 сек.
    401 {"detail": "bad_signature"} — подпись не сошлась.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import settings
from app.memory import get_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["world-bridge"])

_PROVIDERS = ("telegram", "max")
_LEAD_FIELDS = ("fio_parent", "fio_child", "birthday", "phone")
_MAX_SKEW_SEC = 300


def _sign(secret: str, provider: str, user_id: str, ts: int) -> str:
    msg = f"{provider}\n{user_id}\n{ts}".encode()
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


@router.get("/world-bridge/profile")
def world_bridge_profile(
    provider: str = "",
    user_id: str = "",
    ts: str = "",
    sign: str = "",
) -> JSONResponse:
    secret = settings.WORLD_BRIDGE_SECRET
    if not secret:
        return JSONResponse({"detail": "Not Found"}, status_code=404)

    if provider not in _PROVIDERS:
        return JSONResponse({"detail": "bad_provider"}, status_code=400)

    try:
        ts_int = int(ts)
    except (TypeError, ValueError):
        return JSONResponse({"detail": "stale"}, status_code=401)
    if abs(time.time() - ts_int) > _MAX_SKEW_SEC:
        return JSONResponse({"detail": "stale"}, status_code=401)

    if not hmac.compare_digest(_sign(secret, provider, user_id, ts_int), sign):
        return JSONResponse({"detail": "bad_signature"}, status_code=401)

    try:
        lead = get_store().get(user_id, platform=provider).lead
        data = {f: getattr(lead, f).strip() for f in _LEAD_FIELDS if getattr(lead, f).strip()}
    except Exception:
        # Fail-open: мост не должен ронять регистрацию в мире из-за сбоя
        # хранилища бота — world покажет пустую анкету, как для новичка.
        logger.exception("world-bridge: ошибка чтения лида user_id=%r", user_id)
        data = {}

    return JSONResponse({"found": bool(data), "lead": data or None})
