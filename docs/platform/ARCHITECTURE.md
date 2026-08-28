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
- [ ] Phase 5: подключение бота к живым группам/расписанию (matching)
- [ ] Phase 6: виджет расписания/записи на сайте
- [ ] Phase 7: Mini App «мои занятия» (по телефону → bb_students)
- [ ] Phase 8: Billing (CloudPayments онлайн + T-bank терминал)
- [ ] Phase 9+: уведомления, автоматизации, кампании, Customer 360, аналитика
