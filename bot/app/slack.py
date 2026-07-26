"""Optional Slack notifications via incoming webhook."""
from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def notify_slack(text: str) -> bool:
    webhook = settings.SLACK_WEBHOOK_URL.strip()
    if not webhook:
        return False

    payload = {"text": text[:4000]}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook, json=payload)
        resp.raise_for_status()
    except Exception:
        logger.exception("Slack notification failed")
        return False
    return True
