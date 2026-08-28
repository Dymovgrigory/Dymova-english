# Архитектура цифровой платформы Фоксинбург

## Принцип

BigBen CRM — единственный source of truth по ученикам, группам, урокам,
оплатам. Собственная БД (SQLite, `DB_PATH`) — read-model, операционные данные
(диалоги, клиенты, бронирования, события) и аудит. Мы не строим вторую CRM.

## Слои

```
Сайт (static) / Telegram / MAX / Mini App / Виджет
        │  одинаковые данные везде (§211 мандата)
        ▼
app/platform/public_api.py   — /api/platform/{groups,schedule,booking,health}
        ▼
app/platform/booking.py      — BookingService (anti-race, idempotent)
app/platform/sync.py         — Sync engine (full + incremental + reconciliation)
app/platform/webhooks.py     — приёмник вебхуков (HMAC, dedup, fast-200)
        ▼
app/platform/bigben_v2.py    — ЕДИНСТВЕННЫЙ клиент BigBen API v1
        ▼
app/platform/bb_store.py     — read-model SQLite + sync_runs + webhook events + bookings
```

## Правила

- Ни один модуль не ходит в BigBen напрямую — только через `bigben_v2`.
- Кэш никогда не является основанием для записи: booking перед созданием
  демо-урока делает свежий запрос группы в API (anti-race).
- Все write-операции идемпотентны (Idempotency-Key, UNIQUE-ключи).
- Деньги: API = копейки (int), вебхук payment.received = рубли. Не путать.
- Каждая read-model запись имеет synced_at; API отдаёт freshness в ответах.

## Статус фаз

- [x] Phase 0: аудит (см. ARCHITECTURE_AUDIT.md)
- [x] Phase 1: BigBen v2 client + конфиг + .env.example
- [x] Phase 2: sync engine + webhook receiver + read-model
- [x] Phase 3: schedule/groups API (публичные)
- [x] Phase 4: Booking engine (API-уровень)
- [x] Phase 5: бот отвечает о расписании/местах из read-model (детерминированно, без LLM)
- [x] Phase 6: виджет fxb-schedule.js (карточки, места, booking, anti-race UI)
- [x] Phase 7: Mini App «Мои занятия» (баланс, группы, расписание; initData-auth)
- [x] Phase 8: Billing CloudPayments (инвойсы, подписанные вебхуки, идемпотентность)
- [x] Phase 9: Notification Orchestrator (dedup, тихие часы, приоритеты)
- [x] Phase 10: Automation Engine (напоминания о пробном, thankyou за оплату)
- [x] Phase 12 (частично): Alert Center /admin/api/platform/alerts + replay вебхуков
- [x] Phase 11: кампании — тихие часы (возврат в draft) + frequency cap 20ч
- [x] Phase 12: Customer 360 (/admin/api/customers/{id}/crm360 + секция в карточке админки)
- [x] Phase 13: продуктовая аналитика (product_events, /api/platform/events, админ-воронка)
- [x] Автоматизация low-balance (ежедневный скан, ISO-недельный дедуп);
      inactive-student по урокам НЕВОЗМОЖЕН — API v1 не отдаёт посещаемость ученика
- [x] TG-версия экрана «Мои занятия» (tgapp, sheet mylessons)
- [x] Сайт: страница /raspisanie с живым виджетом (в проде)
- [ ] CloudPayments: код готов, ждёт public_id/api_secret владельца (CLOUDPAYMENTS_ENABLED=false)
- [ ] Вебхук BigBen: приёмник готов, нужна регистрация URL в кабинете BigBen (секрет в .env прода)
