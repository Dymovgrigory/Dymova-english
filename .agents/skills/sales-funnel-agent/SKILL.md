---
name: sales-funnel-agent
description: Pull Yandex.Metrika + GA4 (+ BigBen CRM when accessible) and assemble a source → visits → leads → deals funnel for dymova-english.ru, showing where leads drop and which channel actually converts. Use when the owner asks for a KPI dashboard, funnel report, or "where are we losing leads" analysis. Adapted from EdgeLab's usecase-sales-funnel-agent for this project's actual tools (Metrika/GA4/BigBen — no Sink or Supabase).
---

# Sales Funnel Agent — dymova-english.ru

Сводит воронку по источникам за период, вместо ручной выгрузки из трёх
систем. Смотри `wiki/04-analitika.md` для актуальных счётчиков/целей и
`wiki/07-bot-i-crm.md` для состояния CRM-интеграции — сверяйся с ними,
цифры там могли обновиться.

## Отличие от оригинального EdgeLab-юзкейса

Оригинал использует Sink (короткие ссылки) и Supabase (хранилище сведённых
цифр) — у нас нет ни того, ни другого, и заводить их сейчас не входило в
задачу. Вместо этого:
- Источник трафика — не Sink-клики, а `utm_source`/`ym:s:lastTrafficSource`
  из самой Метрики/GA4.
- Результат — не строка в Supabase, а markdown-отчёт: приложи к ответу
  владельцу и, если это разовый срез для решения, добавь короткую запись в
  `DEVLOG.md` (не заводи новый файл на каждый запуск).
- Оплаты (лиды → деньги) — не отдельный сервис, а BigBen CRM. Бот уже в
  проде (VM Yandex Cloud, см. `.agents/skills/server-doctor` и `DEVLOG.md` →
  "Текущий статус" — актуальнее, чем `wiki/07-bot-i-crm.md`) и по
  задумке передаёт лиды в BigBen, но сквозной путь лида отдельно не
  проверен (открытый TODO). Проверь на живых данных перед тем как доверять
  цифрам; если доступа к BigBen API нет или лиды не доходят — ограничься
  переходами → целями по Метрике/GA4 и явно отметь оплаты как «нет данных»,
  не выдумывай.

## Существующие ID (проверь актуальность в wiki/04-analitika.md)

- Яндекс.Метрика: счётчик **109945462**
  - цель «отправка формы»: 578168283
  - цель «клик по телефону»: 578168629
  - цель «переход в мессенджер»: 578168992
  - цель «переход в соцсеть»: 578169121
- GA4 Measurement ID: **G-9XMYR6MJGL**

## Шаги

1. **UTM-проверка** — прежде чем читать отчёт, убедись, что ссылки в
   рекламе/соцсетях/рассылках размечены `utm_source`. Без разметки соцсети
   сольются в «переходы из соцсетей» и воронку не развести по каналам.

2. **Яндекс.Метрика** — нужен OAuth-токен владельца (Yandex OAuth app,
   Authorization: OAuth [token]). Это доступ к уже существующему аккаунту
   Яндекса, не новая платная подписка — можно запросить у владельца напрямую.
   ```
   curl -G 'https://api-metrika.yandex.net/stat/v1/data' \
     -H 'Authorization: OAuth [YANDEX_TOKEN]' \
     --data-urlencode 'id=109945462' \
     --data-urlencode 'dimensions=ym:s:lastTrafficSource' \
     --data-urlencode 'metrics=ym:s:visits,ym:s:users,ym:s:goal578168283conversionRate'
   ```

3. **GA4** — нужен service account с ролью Viewer на уровне Property
   (создаётся один раз в Google Cloud, email сервисного аккаунта добавляется
   в GA4 → Admin → Property access). `runReport`: dimensions
   `sessionSource`/`sessionMedium`, metrics `sessions`/`keyEvents`.

4. **BigBen CRM (опционально)** — если есть рабочий доступ, вытяни оплаты за
   тот же период и период сессии, чтобы сопоставить с лидами из Метрики/GA4
   по времени. Если доступа нет — не выдумывай цифры, помечай «нет данных».

5. **Сведи и покажи владельцу**
   Источник → визиты → цели/лиды → (если есть) оплаты — по каждому каналу.
   Явно укажи, где данных не хватает, а не заполняй пробелы догадками.
   Вывод должен отвечать на один вопрос: какой канал даёт клики, а какой —
   деньги, и куда перекладывать бюджет/время.

## Красная зона (не делай без явного «да» владельца)
- Заводить новую инфраструктуру (Sink, Supabase или что-то ещё) для хранения
  истории воронки — этого не было в задаче, спроси, если понадобится.
- Любые новые платные подписки/API.
