"""Настройки внешних источников: живой веб-поиск и синхронизация соцсетей в KB.

Отдельный класс Settings (в стиле app.config.Settings), чтобы не трогать
основной config.py. Все значения берутся из переменных окружения.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class SourcesSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Синхронизация внешних источников (VK, Яндекс.Карты, Telegram) ---
    SOURCES_SYNC_ENABLED: bool = True
    VK_GROUP_URL: str = "https://vk.com/foxyfoxclub"
    YANDEX_MAPS_URL: str = "https://yandex.ru/maps/org/foxinburg/162408588499/"
    TELEGRAM_CHANNEL_URL: str = "https://t.me/s/foxinburg"

    # --- Живой веб-поиск (DuckDuckGo HTML) ---
    WEB_SEARCH_ENABLED: bool = True

    # Путь к JSON-кэшу документов источников; пусто = bot/data/sources_cache.json
    SOURCES_CACHE_FILE: str = ""


@lru_cache
def get_sources_settings() -> SourcesSettings:
    return SourcesSettings()


sources_settings = get_sources_settings()
