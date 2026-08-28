# Деплой платформенного слоя

## Переменные окружения (production)

Обязательные для платформы:
- `BIGBEN_PUBLIC_API_KEY` — ключ API v1 (read+write)
- `BIGBEN_PUBLIC_API_BASE` — https://platformapi.bigbencrm.ru/api/public/v1
- `BIGBEN_WEBHOOK_SECRET` — секрет подписки вебхуков
- `BIGBEN_SYNC_ENABLED=true`, `BIGBEN_SYNC_INTERVAL_MIN=15`, `BIGBEN_FULL_SYNC_HOURS=6`

Оплаты (когда включим):
- `CLOUDPAYMENTS_ENABLED=true`, `CLOUDPAYMENTS_PUBLIC_ID`, `CLOUDPAYMENTS_API_SECRET`

## Шаги выкладки

1. Бот: `git pull && cd bot && docker compose build && docker compose up -d`
   (прод: foxinburg-vm, контейнер bot-bot-1). Сайт: сборка
   `python3 prototype/build_static_site.py --out dist_prod` + rsync в
   `/home/yc-user/foxinburg-site/` (первый прод-деплой платформы: 2026-08-28).
2. Проверить `GET /api/platform/health` — bigben_api_reachable: true.
3. В CRM настроить вебхуки → URL `https://bot.dymova-english.ru/api/webhooks/bigben`,
   события: все 5. Тестовое событие из панели должно дать 200.
4. В CloudPayments (когда включим): вебхуки check/pay/fail →
   `https://bot.dymova-english.ru/api/webhooks/cloudpayments/{check,pay,fail}`.
5. В CRM: Воронки → первый статус → Автоматизация (автозадача менеджеру) —
   лиды из API не запускают автозадачи сами.
6. Виджет на сайте: УЖЕ в проде — страница https://dymova-english.ru/raspisanie
   (2026-08-28). Для других страниц: `<div id="fxb-schedule"></div>` + script
   (SCHEDULE_WIDGET.md).

## Откат

Платформенный слой аддитивен: откат = `git revert` коммитов + рестарт.
Таблицы bb_*/bookings/billing_payments/automation_jobs/notification_log
новые, legacy-данных не трогают; удалять их при откате не обязательно.

## Мониторинг

- `/api/platform/health` — публичный health интеграции;
- `/admin/api/platform/alerts` — Alert Center (критичные уровни);
- sync_runs / bb_webhook_events / automation_jobs — журналы в SQLite;
- failed jobs: retry через таблицу (вебхуки — /admin/api/platform/webhooks/{id}/retry).
