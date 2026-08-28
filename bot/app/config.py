"""Конфигурация бота MAX для языковой школы «Фоксинбург».

Все значения берутся из переменных окружения (см. .env.example).
Секреты никогда не хранятся в коде.
"""
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- MAX Bot API ---
    MAX_BOT_TOKEN: str = ""
    # Рабочий домен MAX Bot API. Срок миграции с botapi.max.ru истёк 19.07.2026,
    # поэтому по умолчанию — актуальный platform-api2.max.ru.
    MAX_BOT_API_URL: str = "https://platform-api2.max.ru"
    MAX_WEBHOOK_SECRET: str = ""
    # Домен обслуживается сертификатом Минцифры, которого нет в стандартном
    # списке доверенных. Если он не установлен в систему, укажите путь к
    # PEM-файлу здесь — иначе каждый запрос упадёт на проверке TLS.
    MAX_CA_BUNDLE: str = ""

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
    # Общий бюджет каскада провайдеров: 3 попытки × N провайдеров × LLM_TIMEOUT
    # в худшем случае складываются в минуты молчания. Каскад обязан уложиться
    # в это окно, чтобы вызывающий успел отправить живой фолбэк.
    LLM_TOTAL_BUDGET_SEC: float = 45.0

    # --- Роли моделей (LLM Gateway) ---
    # Разные задачи требуют разных моделей: диалогу нужна лучшая, служебной
    # классификации хватит быстрой и дешёвой. Пусто = использовать LLM_MODEL.
    # Подменяется только модель основного провайдера; запасные из
    # LLM_FALLBACKS остаются со своими собственными моделями.
    LLM_ROLE_REASONING: str = ""   # диалог с клиентом, SMART, рекомендации
    LLM_ROLE_FAST: str = ""        # намерение, эмоция, классификация
    LLM_ROLE_VISION: str = ""      # разбор фото домашнего задания
    LLM_ROLE_CRITIC: str = ""      # оценка ответа перед отправкой
    # Прятать ФИО/телефон/даты за плейсхолдерами перед отправкой в модель.
    # Выключать стоит только для локальной отладки промптов.
    LLM_PII_REDACTION: bool = True

    # --- Дедлайны диалога ---
    # Максимум, сколько пользователь ждёт ответ (включая очередь своих же
    # предыдущих сообщений). По истечении — честный фолбэк, а не молчание.
    REPLY_TIMEOUT_SEC: float = 60.0
    # Через сколько секунд ожидания отправить промежуточное «секунду, уточняю».
    SLOW_NOTICE_SEC: float = 12.0

    # --- BigBen CRM ---
    # Эндпоинт интеграции «с сайтом через API» (GET-запрос с лид-полями).
    BIGBEN_API_URL: str = "https://panel.bigbencrm.ru/api/leads/add"
    BIGBEN_API_KEY: str = ""
    BIGBEN_PIPELINE_ID: str = "1924"
    BIGBEN_PIPELINE_STATUS_ID: str = "1"

    # --- BigBen CRM Public API v1 ---
    # Ключ выпускается в CRM: Настройки → Интеграции → API-ключи (скоупы read+write).
    BIGBEN_PUBLIC_API_KEY: str = ""
    BIGBEN_PUBLIC_API_BASE: str = "https://platformapi.bigbencrm.ru/api/public/v1"
    # Секрет подписки вебхуков (CRM → Информация о школе → Интеграции → Вебхуки).
    BIGBEN_WEBHOOK_SECRET: str = ""
    # Периодичность инкрементальной синхронизации read-model (минуты).
    BIGBEN_SYNC_INTERVAL_MIN: int = 15
    # Полная сверка (reconciliation) раз в N часов.
    BIGBEN_FULL_SYNC_HOURS: int = 6
    # Окно расписания уроков для синхронизации (дней вперёд).
    BIGBEN_LESSONS_WINDOW_DAYS: int = 60
    BIGBEN_SYNC_ENABLED: bool = True
    # Порог «мало мест» в группе для UI/бота (конфигурация, не магическое число).
    LOW_AVAILABILITY_THRESHOLD: int = 2
    # Вместимость по умолчанию, если у группы не задан max_students в CRM:
    # используем вместимость аудитории как наиболее близкий физический лимит.
    BIGBEN_CAPACITY_FALLBACK_AUDITORY: bool = True

    # Физические лимиты групп по филиалам (правила школы, 2026-08):
    # Лихачевский — до 8, Ракетостроителей — до 7, школьные филиалы — до 10.
    # Детский сад из онлайн-расписания исключаем (запись через менеджера).
    CAPACITY_LIKHACHEVSKY: int = 8
    CAPACITY_RAKETOSTROITELEY: int = 7
    CAPACITY_SCHOOL: int = 10
    # Фильтр детского сада: по подстроке в названии филиала или группы.
    KINDERGARTEN_EXCLUDE_PATTERN: str = "детск"

    # Напоминания об оплате абонемента (service-уведомления родителю).
    # Модель школы: абонемент на месяц, счёт выставляется в CRM 24-го числа,
    # оплата — до 1-го числа оплачиваемого месяца. Баланс в деньгах клиентам
    # НЕ показываем (стоимость абонемента фиксирована, число занятий разное).
    SUBSCRIPTION_REMINDER_ENABLED: bool = True
    # День месяца, когда напоминаем о выставленном счёте (на следующий день
    # после автовыставления счетов в CRM).
    SUBSCRIPTION_REMINDER_DAY: int = 25
    # День месяца финального напоминания тем, кто ещё не оплатил.
    SUBSCRIPTION_DUE_DAY: int = 1
    SUBSCRIPTION_SCAN_INTERVAL_HOURS: int = 24

    # Маркетинговые рассылки: тихие часы и frequency cap (§103).
    MARKETING_RESPECT_QUIET_HOURS: bool = True
    # Минимальный интервал между маркетинговыми сообщениями одному клиенту.
    MARKETING_FREQ_CAP_HOURS: int = 20

    # --- Платежи: CloudPayments (онлайн-касса) ---
    # Терминал в филиалах — T-bank, он к CloudPayments не относится и через
    # API не управляется. PublicId/secret: личный кабинет CloudPayments.
    CLOUDPAYMENTS_PUBLIC_ID: str = ""
    CLOUDPAYMENTS_API_SECRET: str = ""
    CLOUDPAYMENTS_ENABLED: bool = False
    CLOUDPAYMENTS_API_BASE: str = "https://api.cloudpayments.ru"
    # Назначение платежа в чеке/виджете.
    CLOUDPAYMENTS_DESCRIPTION: str = "Оплата занятий Фоксинбург"
    # Цена месячного абонемента в рублях. Если > 0 — сумма платежа берётся
    # только отсюда, клиент сумму не присылает (защита от занижения).
    SUBSCRIPTION_PRICE_RUB: int = 0

    # Провайдер оплат: cloudpayments | tbank (один активный).
    BILLING_PROVIDER: str = "cloudpayments"
    # Т-Банк (интернет-эквайринг, securepay API v2). TerminalKey + пароль
    # из личного кабинета Т-Бизнеса. Оплата — редиректом на PaymentURL.
    TBANK_ENABLED: bool = False
    TBANK_TERMINAL_KEY: str = ""
    TBANK_PASSWORD: str = ""
    TBANK_API_BASE: str = "https://securepay.tinkoff.ru"
    # Объединённый CA-бандл (certifi + Russian Trusted Root CA) — генерируется
    # лениво; нужен, т.к. Т-Банк использует национальный сертификат Минцифры.
    TBANK_CA_BUNDLE: str = ""

    # --- Интеграции разработки и наблюдаемости ---
    SENTRY_DSN: str = ""
    SENTRY_ENVIRONMENT: str = ""
    SENTRY_TRACES_SAMPLE_RATE: float = 0.0
    SLACK_WEBHOOK_URL: str = ""

    # --- Передача администратору ---
    # ID администраторов в MAX (через запятую), куда дублируется контекст диалога.
    ADMIN_MAX_IDS: str = ""
    # ID методиста(ов) в Telegram — уведомления о записях на диагностику
    # и оплаченных пробных (через запятую).
    METHODIST_TG_IDS: str = ""
    ADMIN_TOKEN: str = ""

    # --- Платное пробное занятие на сайте ---
    # Если true — запись на пробное через сайт идёт с онлайн-оплатой
    # (CloudPayments-виджет): CRM-лид и демо-урок создаются только после
    # подтверждённого webhook pay. Сумму клиент не присылает — цена
    # определяется сервером по длительности урока группы.
    TRIAL_PAID: bool = False
    TRIAL_PRICE_60_RUB: int = 1125  # занятия от 55 минут
    TRIAL_PRICE_45_RUB: int = 875   # занятия 40-54 минуты

    # Педагоги школы (через запятую) — для разметки расписания: имя ищется
    # в названии группы. В публичном API BigBen педагогов нет.
    KNOWN_TEACHERS: str = ("Вероника Дымова,Анна Виноградова,Мария Прокудина,"
                           "Салтанат Джанузакова,Анастасия Спорыхина,"
                           "Светлана Сушко,Григорий Дымов")

    # Слоты диагностики для страницы /diagnostika (JSON-массив):
    # [{"filial_id": 13296, "weekday": 2, "time": "17:00"}]
    # weekday: 0=пн..6=вс. Пусто — форма без выбора времени («свяжемся»).
    DIAGNOSTIC_SLOTS_JSON: str = ""

    # --- Мини-приложение ---
    MINIAPP_BASE_URL: str = ""
    MINIAPP_REQUIRE_REGISTRATION: bool = True
    # Если true, API мини-приложения принимает личность ТОЛЬКО из подписанного
    # initData (Telegram/MAX). Открытый ?user_id= перестаёт что-либо значить —
    # иначе любой может прочитать и изменить чужой профиль (IDOR).
    MINIAPP_AUTH_REQUIRED: bool = True
    CONV_LOG_FILE: str = ""
    GROUP_MODE_ENABLED: bool = True
    # Сколько минут тишины держится режим менеджера: после последнего
    # сообщения (клиента или менеджера) диалог автоматически возвращается
    # боту. Окно скользящее — каждое новое сообщение его продлевает.
    MANAGER_AUTO_RESUME_MIN: int = 15
    GROUP_CHAT_WHITELIST: str = ""
    NUDGE_DELAY_HOURS: int = 36
    NUDGE_MAX_AGE_HOURS: int = 100
    NUDGE_ENABLED: bool = True
    NUDGE_HOUR: int = 11
    NUDGE_MINUTE: int = 0

    # --- Цикл улучшения: журнал вопросов без ответа и ежедневный отчёт ---
    # JSONL-журнал вопросов, на которые бот не смог уверенно ответить.
    INSIGHTS_FILE: str = "./data/insights.jsonl"
    DIGEST_ENABLED: bool = True
    DIGEST_HOUR: int = 21
    DIGEST_MINUTE: int = 0
    DIGEST_TZ_OFFSET: int = 3  # МСК
    DIGEST_DAYS: int = 1

    # --- Живая синхронизация KB с сайтом ---
    SITE_SYNC_ENABLED: bool = True
    SITE_SYNC_URLS: str = ""  # список URL через запятую; пусто = главная сайта
    SITE_SYNC_INTERVAL_MIN: int = 60

    # --- Telegram ---
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_PROXY_URL: str = ""
    # long-polling getUpdates вместо вебхука (вебхуки Telegram→РФ блокируются)
    TELEGRAM_POLLING: bool = True
    TELEGRAM_WEBHOOK_URL: str = ""
    TELEGRAM_WEBHOOK_SECRET: str = ""
    # Публичный HTTPS-URL Telegram Mini App (кнопка web_app в чате).
    # Пусто = взять {MINIAPP_BASE_URL origin}/tg/ , если он задан.
    TELEGRAM_MINIAPP_URL: str = ""
    # Известные адреса api.telegram.org. Сторож проверяет их, чтобы при
    # обрыве связи сразу подсказать администратору рабочий адрес для
    # extra_hosts, а не просто сообщить «всё сломалось».
    TELEGRAM_API_IPS: str = (
        "149.154.167.220,149.154.166.110,149.154.167.197,149.154.171.5,91.108.56.130"
    )

    # --- Сторож доступности ---
    WATCHDOG_ENABLED: bool = True
    WATCHDOG_INTERVAL_MIN: int = 5
    # Сколько проверок подряд должны провалиться до тревоги (защита от
    # одиночной сетевой осечки).
    WATCHDOG_FAILURES_BEFORE_ALERT: int = 2
    WATCHDOG_ALERT_COOLDOWN_MIN: int = 60
    # Опрос Telegram считается вставшим, если успешных циклов не было
    # дольше этого времени (обычный цикл — 25 секунд).
    WATCHDOG_POLL_SILENCE_MIN: int = 5

    # --- Email-уведомления о заявках (Gmail SMTP, App Password) ---
    GMAIL_SMTP_USER: str = ""
    GMAIL_SMTP_APP_PASSWORD: str = ""
    LEAD_NOTIFY_EMAILS: str = ""

    # --- Статический сайт: разрешённые origin для CORS формы заявки ---
    SITE_CORS_ORIGINS: str = "https://dymova-english.ru,https://new.dymova-english.ru,https://www.dymova-english.ru"

    # --- Прочее ---
    REGISTRATION_REQUIRED: bool = False
    # Пароль первого пользователя админки (логин admin) при начальной
    # инициализации RBAC. Пусто = сгенерировать и напечатать в лог один раз.
    ADMIN_BOOTSTRAP_PASSWORD: str = ""
    BOT_NAME: str = "Фоксинбург"
    DATA_DIR: str = ""  # переопределение пути к knowledge/data.yaml (опц.)
    DB_PATH: str = "./data/bot.db"
    STATE_FILE: str = ""  # legacy alias для DB_PATH

    @field_validator(
        "LLM_API_KEY",
        "MAX_BOT_TOKEN",
        "BIGBEN_API_KEY",
        "ADMIN_TOKEN",
        "TELEGRAM_BOT_TOKEN",
        "MAX_WEBHOOK_SECRET",
        "TELEGRAM_WEBHOOK_SECRET",
        mode="before",
    )
    @classmethod
    def _strip_secret(cls, v: object) -> object:
        # Пробелы/переводы строк в ключах ломают HTTP-заголовки провайдеров.
        return v.strip() if isinstance(v, str) else v

    @property
    def telegram_miniapp_url(self) -> str:
        """URL Telegram Mini App: явный или производный от MINIAPP_BASE_URL.

        MAX-приложение живёт на /app/, Telegram-версия — на /tg/ того же
        хоста, поэтому отдельную переменную окружения задавать не обязательно.
        """
        explicit = self.TELEGRAM_MINIAPP_URL.strip()
        if explicit:
            return explicit
        base = self.MINIAPP_BASE_URL.strip()
        if not base:
            return ""
        origin = base.split("#", 1)[0].split("?", 1)[0].rstrip("/")
        if origin.endswith("/app"):
            origin = origin[: -len("/app")]
        return f"{origin}/tg/"

    @property
    def admin_ids(self) -> list[str]:
        return [x.strip() for x in self.ADMIN_MAX_IDS.split(",") if x.strip()]

    @property
    def site_cors_origins(self) -> list[str]:
        return [x.strip() for x in self.SITE_CORS_ORIGINS.split(",") if x.strip()]

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
