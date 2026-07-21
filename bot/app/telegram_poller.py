"""Telegram polling worker for deployments without a public webhook URL.

Run only when TELEGRAM_WEBHOOK_URL is empty. In Docker Compose this is the
optional `polling` profile so it does not fight with webhook mode.
"""
from __future__ import annotations

import asyncio
import logging

from app.main import _telegram_poll_loop
from app.telegram_client import get_telegram

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    telegram = get_telegram()
    if not telegram.configured:
        logger.warning("TELEGRAM_BOT_TOKEN is empty — polling worker stopped")
        return
    await _telegram_poll_loop(telegram)


if __name__ == "__main__":
    asyncio.run(main())
