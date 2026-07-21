"""One-shot Telegram webhook bootstrap for deploys.

Runs after the API container is healthy. If TELEGRAM_WEBHOOK_URL is set,
registers the webhook with the matching secret. If it is empty, deletes the
webhook so a separate polling worker can own updates.
"""
from __future__ import annotations

import asyncio
import logging

from app.config import settings
from app.telegram_client import get_telegram

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> int:
    telegram = get_telegram()
    if not telegram.configured:
        logger.warning("TELEGRAM_BOT_TOKEN is empty — Telegram bootstrap skipped")
        return 0

    if settings.TELEGRAM_WEBHOOK_URL:
        ok = await telegram.set_webhook(
            settings.TELEGRAM_WEBHOOK_URL,
            settings.TELEGRAM_WEBHOOK_SECRET or None,
        )
        logger.info("Telegram setWebhook ok=%s url=%s", ok, settings.TELEGRAM_WEBHOOK_URL)
        return 0 if ok else 1

    ok = await telegram.delete_webhook()
    logger.info("TELEGRAM_WEBHOOK_URL is empty — webhook deleted ok=%s; use polling profile", ok)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
