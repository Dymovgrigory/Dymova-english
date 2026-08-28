# Аудит CRM-интеграции, 2026-08-28

## Было

`app/bigben.py` — GET https://panel.bigbencrm.ru/api/leads/add с query-параметрами.
Проблемы: только создание лида, без идемпотентности, без чтения данных,
ключ в query (светится в логах прокси), без retry/timeout-политики, без
мониторинга. Идентификаторы CRM локально не хранились.

## Стало (платформенный слой app/platform/)

- Единый клиент v1: Bearer, retry/backoff, 429+Retry-After, пагинация,
  Idempotency-Key на запись, маппинг ошибок (401/403/422/429/5xx).
- Read-model: bb_filials(5), bb_groups(431; активных с уроками ~75),
  bb_lessons(986 за 60 дней), bb_students(1562), bb_payments(344/92 дня) —
  проверено живой синхронизацией 2026-08-28.
- sync_runs — журнал прогонов; /api/platform/health — Alert Center данных.
- Вебхуки: HMAC, дедуп, фон-обработка, replay-таблица.
- Bookings: локальный источник истины о записях на пробное, идемпотентные
  создания лида и демо (связка booking→lead_id→demo_lesson_id).

## Дубли и рассинхронизация

- Один ученик в bb_students идентифицируется по BigBen id; связка с локальным
  customer — по телефону (find_student_by_phone, нормализация 10 цифр).
  Полноценный identity-linking — следующая фаза (таблица identity_links).
- legacy-контур продолжает создавать лидов старым способом из бота —
  после перевода бота на v1 legacy выключаем.
