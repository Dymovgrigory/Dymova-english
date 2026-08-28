# Интеграция BigBen CRM

## Два контура API

1. **Legacy** (`app/bigben.py`): старый endpoint «интеграция с сайтом»
   (GET leads/add). Оставлен для обратной совместимости бота; новый код его
   не использует.
2. **Public API v1** (`app/platform/bigben_v2.py`): официальный REST API.
   Документация: https://developers.bigbencrm.ru

## Аутентификация

- `Authorization: Bearer bb_<prefix>_<secret>`, скоупы read/write.
- Ключ: CRM → Настройки → Интеграции → API-ключи. Хранится в `.env`
  (BIGBEN_PUBLIC_API_KEY), в git не попадает. При компрометации: выпустить
  новый, переключить, отозвать старый (перевыпуска нет).

## Эндпоинты (v1)

| Метод | Что | Использование |
|---|---|---|
| GET /filials | филиалы | sync, справочник |
| GET /groups | группы + free_slots | расписание, booking |
| GET /lessons?from&to | уроки (окно ≤92 дн.) | расписание |
| GET /students(+/{id}) | ученики, баланс | sync, кабинет |
| GET /payments | оплаты (копейки!) | sync, финансы |
| POST /leads | лид | booking, формы сайта |
| POST /demo-lessons | запись на пробное | booking |
| POST /students/{id}/groups | зачисление | будущее |

Пагинация: page/per_page (max 100), meta.total. `updated_since` — для
инкремента (legacy-записи без даты изменения туда НЕ попадают — поэтому
есть периодическая полная сверка).

Write-методы требуют `Idempotency-Key` (24ч окно). 429 → Retry-After.

## Вебхуки

POST /api/webhooks/bigben. Подписка: CRM → Информация о школе → Интеграции →
Вебхуки (секрет показывается один раз → BIGBEN_WEBHOOK_SECRET).

События: student.created, lead.created, group.enrolled, lesson.completed,
payment.received (суммы в РУБЛЯХ). Подпись: X-BigBen-Signature = HMAC-SHA256
(raw body, secret), сравнение timing-safe. Ретраи BigBen: 4 попытки
(1м/5м/30м). Отвечаем 200 сразу, обработка в фоне; дедуп по
(event, account, внутренний id, timestamp), replay через bb_webhook_events.

## Известные ограничения API v1 (запрошены у вендора)

- нет переноса/отмены занятий, отмены демо, отчисления из группы;
- нет вебхуков на пропуск/отмену урока/изменение расписания;
- capacity=null у групп без max_students (fallback: вместимость аудитории);
- создание лида через API не запускает автозадачи воронки → в CRM настроить
  автоматизацию первого статуса (ручная настройка владельцем).
