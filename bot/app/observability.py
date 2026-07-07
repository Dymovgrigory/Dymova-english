"""Optional observability hooks."""
from __future__ import annotations

import logging

from app.config import settings

logger = logging.getLogger(__name__)

_SENTRY_INITIALIZED = False


def init_sentry() -> bool:
    global _SENTRY_INITIALIZED
    if _SENTRY_INITIALIZED:
        return True

    dsn = settings.SENTRY_DSN.strip()
    if not dsn:
        return False

    try:
        import sentry_sdk
    except Exception:
        logger.exception("Sentry SDK is unavailable")
        return False

    kwargs: dict[str, object] = {
        "dsn": dsn,
        "environment": settings.SENTRY_ENVIRONMENT.strip() or None,
        "traces_sample_rate": float(settings.SENTRY_TRACES_SAMPLE_RATE),
    }
    kwargs = {key: value for key, value in kwargs.items() if value not in ("", None)}
    sentry_sdk.init(**kwargs)
    _SENTRY_INITIALIZED = True
    logger.info("Sentry initialized")
    return True
