"""Конфигурация бота MAX для языковой школы «Фоксинбург».

Все значения берутся из переменных окружения (см. .env.example).
Секреты никогда не хранятся в коде.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- MAX Bot API ---
    MAX_BOT_TOKEN: str = ""
    # Рабочий домен MAX Bot API. botapi.max.ru работает без доп. сертификатов.
    # Новый домен platform-api2.max.ru (миграция до 19.07.2026) требует установки
    # корневого сертификата Минцифры в доверенные — переключайтесь на него только
    # после установки сертификата на хосте.
    MAX_BOT_API_URL: str = "https://botapi.max.ru"
    MAX_WEBHOOK_SECRET: str = ""

    # --- LLM (провайдер-агностик, OpenAI-совместимый) ---
    # По умолчанию OpenRouter (бесплатные модели). Можно заменить на Groq,
    # локальный Ollama и т.д., поменяв LLM_BASE_URL / LLM_MODEL / LLM_API_KEY.
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://openrouter.ai/api/v1"
    LLM_MODEL: str = "meta-llama/llama-3.3-70b-instruct:free"
    # Запасные провайдеры в порядке попыток. JSON-массив объектов
    # {"base_url": "...", "api_key": "...", "model": "..."}.
    LLM_FALLBACKS: str = "[]"
    LLM_TEMPERATURE: float = 0.4
    LLM_MAX_TOKENS: int = 700
    LLM_TIMEOUT: int = 40
    LLM_HISTORY_TURNS: int = 8

    # --- BigBen CRM ---
    # Эндпоинт интеграции «с сайтом через API» (GET-запрос с лид-полями).
    BIGBEN_API_URL: str = ""
    BIGBEN_API_KEY: str = ""
    BIGBEN_PIPELINE_ID: str = ""
    BIGBEN_PIPELINE_STATUS_ID: str = ""

    # --- Передача администратору ---
    # ID администраторов в MAX (через запятую), куда дублируется контекст диалога.
    ADMIN_MAX_IDS: str = ""
    ADMIN_TOKEN: str = ""

    # --- Мини-приложение ---
    MINIAPP_BASE_URL: str = ""
    CONV_LOG_FILE: str = ""
    GROUP_MODE_ENABLED: bool = True
    GROUP_CHAT_WHITELIST: str = ""
    NUDGE_DELAY_HOURS: int = 36
    NUDGE_MAX_AGE_HOURS: int = 100

    # --- Telegram ---
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_PROXY_URL: str = ""
    TELEGRAM_WEBHOOK_URL: str = ""
    TELEGRAM_WEBHOOK_SECRET: str = ""

    # --- Прочее ---
    REGISTRATION_REQUIRED: bool = False
    BOT_NAME: str = "Фоксинбург"
    DATA_DIR: str = ""  # переопределение пути к knowledge/data.yaml (опц.)
    DB_PATH: str = "./data/bot.db"
    STATE_FILE: str = ""  # legacy alias для DB_PATH

    @property
    def admin_ids(self) -> list[str]:
        return [x.strip() for x in self.ADMIN_MAX_IDS.split(",") if x.strip()]

    @property
    def group_chat_whitelist(self) -> set[int]:
        items: set[int] = set()
        for raw in self.GROUP_CHAT_WHITELIST.split(","):
            raw = raw.strip()
            if not raw:
                continue
            try:
                items.add(int(raw))
            except ValueError:
                continue
        return items


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
