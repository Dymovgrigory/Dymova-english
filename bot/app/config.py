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
    # По умолчанию Groq (бесплатно, быстро). Можно заменить на OpenRouter,
    # локальный Ollama и т.д., поменяв LLM_BASE_URL / LLM_MODEL / LLM_API_KEY.
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.groq.com/openai/v1"
    LLM_MODEL: str = "llama-3.3-70b-versatile"
    LLM_FALLBACKS: str = "[]"
    VISION_MODEL: str = "openai/gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.4
    LLM_MAX_TOKENS: int = 700
    LLM_TIMEOUT: int = 40

    # --- BigBen CRM ---
    # Эндпоинт интеграции «с сайтом через API» (GET-запрос с лид-полями).
    # Хост panel.bigbencrm.ru общий для всех школ BigBen, поэтому URL задан
    # значением по умолчанию. Ключ (секрет) обязательно из окружения.
    # Воронка «Бот Макс» (id 1924), этап «Входящие» (id 1) — куда падают
    # новые заявки от бота. См. .env.example.
    BIGBEN_API_URL: str = "https://panel.bigbencrm.ru/api/leads/add"
    BIGBEN_API_KEY: str = ""
    BIGBEN_PIPELINE_ID: str = "1924"
    BIGBEN_PIPELINE_STATUS_ID: str = "1"

    # --- Передача администратору ---
    # ID администраторов в MAX (через запятую), куда дублируется контекст диалога.
    ADMIN_MAX_IDS: str = ""

    # --- Group chat mode ---
    GROUP_CHAT_WHITELIST: str = ""
    GROUP_MODE_ENABLED: bool = True

    # --- Мини-приложение ---
    MINIAPP_BASE_URL: str = ""

    # --- Прочее ---
    BOT_NAME: str = "Фоксинбург"
    DATA_DIR: str = ""  # переопределение пути к knowledge/data.yaml (опц.)
    STATE_FILE: str = ""  # путь к файлу персистентности диалогов (опц.)
    CONV_LOG_FILE: str = ""  # JSONL-лог диалогов (опц.)

    # --- Цикл улучшения ---
    # Журнал «пробелов»: вопросы, на которые бот ответил неуверенно
    # (низкое совпадение с базой знаний). JSONL-файл, по строке на запись.
    INSIGHTS_FILE: str = ""
    # Порог релевантности поиска: ниже — считаем ответ «слабым» и логируем пробел.
    INSIGHTS_MIN_SCORE: float = 0.34
    # Токен для служебных эндпоинтов /admin/* (если задан — требуется заголовок
    # X-Admin-Token). Защищает отчёт об улучшениях и регистрацию webhook.
    ADMIN_TOKEN: str = ""

    # --- Ежедневный отчёт администраторам ---
    DIGEST_ENABLED: bool = True
    DIGEST_HOUR: int = 21          # час отправки (в часовом поясе DIGEST_TZ_OFFSET)
    DIGEST_MINUTE: int = 0
    DIGEST_TZ_OFFSET: int = 3      # смещение от UTC (Москва = +3)
    DIGEST_DAYS: int = 1           # за какой период собирать дайджест

    @property
    def admin_ids(self) -> list[str]:
        return [x.strip() for x in self.ADMIN_MAX_IDS.split(",") if x.strip()]

    def is_admin(self, user_id: str | int) -> bool:
        return str(user_id) in self.admin_ids

    def group_chat_whitelist(self) -> set[int]:
        values: set[int] = set()
        for raw in self.GROUP_CHAT_WHITELIST.split(","):
            item = raw.strip()
            if not item:
                continue
            try:
                values.add(int(item))
            except ValueError:
                continue
        return values


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
