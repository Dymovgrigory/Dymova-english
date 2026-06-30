"""Клиент интеграции с BigBen CRM («интеграция с сайтом через API»).

Заявки отправляются GET-запросом с обязательными полями key, pipeline_id,
pipeline_status_id и данными лида (fio, fio_parent, birthday, phone, source,
user_note и др.). Документация:
https://bigbencrm.sitehelp.me/upravlenie_shkoloy/integratsii/integratsiya_s_saytom_cherez_api.html
"""
from __future__ import annotations

import logging

import httpx

from app.config import settings
from app.memory import Lead

logger = logging.getLogger(__name__)


class BigBenClient:
    @property
    def configured(self) -> bool:
        return bool(
            settings.BIGBEN_API_URL
            and settings.BIGBEN_API_KEY
            and settings.BIGBEN_PIPELINE_ID
            and settings.BIGBEN_PIPELINE_STATUS_ID
        )

    async def create_lead(
        self,
        lead: Lead,
        source: str,
        note: str = "",
        utm: dict | None = None,
    ) -> bool:
        if not self.configured:
            logger.warning("BigBen не настроен — заявка не отправлена (lead=%s)", lead.fio_parent)
            return False

        params = build_params(lead, source, note, utm)

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(settings.BIGBEN_API_URL, params=params)
            if resp.status_code == 200:
                logger.info("BigBen lead создан: %s", lead.fio_parent)
                return True
            logger.error("BigBen ошибка: status=%s body=%s", resp.status_code, resp.text[:300])
            return False
        except Exception:
            logger.exception("BigBen запрос не удался")
            return False


_UTM_KEYS = (
    "utm_source", "utm_medium", "utm_campaign", "utm_term",
    "utm_content", "fbclid", "fbp", "fbc",
)


def build_params(lead: Lead, source: str, note: str = "", utm: dict | None = None) -> dict:
    """Формирует словарь GET-параметров для BigBen API (без секретов в логах)."""
    params = {
        "key": settings.BIGBEN_API_KEY,
        "pipeline_id": settings.BIGBEN_PIPELINE_ID,
        "pipeline_status_id": settings.BIGBEN_PIPELINE_STATUS_ID,
        "source": source[:255],
    }
    if lead.fio_child:
        params["fio"] = lead.fio_child[:255]
    if lead.fio_parent:
        params["fio_parent"] = lead.fio_parent[:255]
    if lead.phone:
        params["phone"] = lead.phone[:20]
    if lead.birthday:
        params["birthday"] = lead.birthday
    if lead.email:
        params["email"] = lead.email[:255]
    if lead.city:
        params["city"] = lead.city[:255]
    if lead.comment:
        params["phone_comment"] = lead.comment[:255]

    # UTM-метки/атрибуция — пробрасываем только поддерживаемые ключи.
    for key in _UTM_KEYS:
        val = (utm or {}).get(key)
        if val:
            params[key] = str(val)[:300]

    user_note = note or _build_note(lead)
    if user_note:
        params["user_note"] = user_note[:1000]
    return params


def _build_note(lead: Lead) -> str:
    parts = []
    if lead.course:
        parts.append(f"Курс: {lead.course}")
    if lead.branch:
        parts.append(f"Филиал: {lead.branch}")
    interest = lead.interest_label()
    if interest:
        parts.append(f"Интерес: {interest}")
    if lead.age:
        parts.append(f"Возраст ребёнка: {lead.age}")
    parts.append("Заявка из MAX-бота Фоксинбург")
    return ". ".join(parts)


_client: BigBenClient | None = None


def get_bigben() -> BigBenClient:
    global _client
    if _client is None:
        _client = BigBenClient()
    return _client
