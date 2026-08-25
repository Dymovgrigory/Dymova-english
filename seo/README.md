# SEO-интеграции: семантическое ядро × Вебмастер × Wordstat

Питон-скрипты без фреймворков (requests + sqlite3 + csv). Данные и venv не коммитятся
(см. `.gitignore`: `seo/.venv/`, `seo/*.sqlite`, `seo/*.csv`, `seo/report.md`),
коммитим только скрипты и этот README.

## Структура

```
seo/
├── common.py             # чтение .env.seo, sqlite-подключение, схема БД
├── parse_semantic_map.py # SEO_SEMANTIC_MAP.md → keywords.csv + keywords.sqlite
├── yandex_webmaster.py   # API Вебмастера v4 → webmaster_queries (sqlite+csv)
├── yandex_wordstat.py    # Директ API v5 WordstatReports → wordstat (sqlite+csv)
├── merge_report.py       # join всего → report.md + report.csv с флагами
├── keywords.csv          # [данные, gitignored]
├── keywords.sqlite       # [данные, gitignored] таблицы: keywords, webmaster_queries, wordstat
├── webmaster_queries.csv # [данные, gitignored]
├── wordstat.csv          # [данные, gitignored]
└── report.md / report.csv# [данные, gitignored]
```

## Установка

```bash
python3 -m venv seo/.venv
seo/.venv/bin/pip install requests
```

## Конфигурация (.env.seo в корне репо, gitignored)

```
YANDEX_WEBMASTER_TOKEN=...   # есть, работает (user_id 1629110380, хост подтверждён)
DIRECT_TOKEN=                # TODO: получить (см. раздел «Wordstat» ниже)
GOOGLE_SA_KEY=               # TODO: JSON-ключ service account для GSC (точка расширения)
```

TODO Метрика: счётчик 109945462, OAuth-токен Метрики не получен — раздел аналитики
поисковых фраз Метрики не подключён. Когда будет токен: API Метрики v1,
`https://api-metrika.yandex.net/stat/v1/data` с `dimensions=ym:s:searchPhrase`.

## Команды

```bash
# 1. Ядро: перечитать SEO_SEMANTIC_MAP.md (после любой правки карты)
seo/.venv/bin/python seo/parse_semantic_map.py

# 2. Вебмастер: показы/клики/CTR/позиция за последние ~3 мес
seo/.venv/bin/python seo/yandex_webmaster.py            # --days 92, --limit 500

# 3. Wordstat: частотность (нужен DIRECT_TOKEN; без токена мягко выходит)
seo/.venv/bin/python seo/yandex_wordstat.py             # --all | --limit N

# 4. Сводный отчёт
seo/.venv/bin/python seo/merge_report.py
```

## Что в отчёте (report.md / report.csv)

По каждому запросу: частотность (если есть), показы/клики/CTR/позиция из Вебмастера,
target_url и флаги:

- `NO_PAGE_WITH_SHOWS` — есть показы, страница NEW → **создать страницу**;
- `LOW_CTR` — позиция 5–20, CTR < 2%, показы ≥ 10 → **доработать title/description**;
- `WM_NOT_IN_CORE` — запрос из Вебмастера с показами ≥ 5, которого нет в ядре →
  **добавить в SEO_SEMANTIC_MAP.md**;
- `NO_FREQ` — нет частотности (ждём Wordstat).

## Wordstat: как владельцу получить DIRECT_TOKEN (пошагово)

1. Зайти под Яндекс-логином, у которого есть доступ к Директу (или зарегистрировать
   Директ — достаточно бесплатного кабинета без запуска рекламы).
2. Зарегистрировать приложение на https://oauth.yandex.ru/ :
   - название любое (например, «Foxinburg SEO»);
   - платформа: **веб-сервисы**, Redirect URI: `https://oauth.yandex.ru/verification_code`;
   - в правах (scope) отметить **«Яндекс Директ API»** (`direct:read` достаточно,
     обычно ставят «Использование API Яндекс.Директа»).
3. Скопировать ClientID приложения и открыть в браузере:
   `https://oauth.yandex.ru/authorize?response_type=token&client_id=<ClientID>`
   → подтвердить → из URL после редиректа взять `access_token=...`.
4. Вписать токен в `.env.seo`: `DIRECT_TOKEN=<токен>`.
5. В кабинете Директа включить доступ к API: https://direct.yandex.ru/ →
   внизу «API» / https://yandex.ru/dev/direct/doc/ru/concepts/access — принять
   условия и подать заявку на полный доступ (для WordstatReports хватает тестового,
   но заявка снимает ограничения).
6. Проверить: `seo/.venv/bin/python seo/yandex_wordstat.py --limit 5` — закажет
   1–2 отчёта и запишет частотность в БД.

Лимиты API: до 10 фраз в одном отчёте, до 5 отчётов в очереди, баллы списываются
за заказ отчётов — скрипт сам держит очередь и делает retry с backoff.
Регионы по умолчанию: GeoIds 213 (Москва) и 1 (Московская область) — правятся
константой `GEO_IDS` в `yandex_wordstat.py` (id уточнять через справочник
Dictionaries/get → GeoRegions).

## Регламент (ежемесячно, начало месяца)

1. Обновить `SEO_SEMANTIC_MAP.md` (добавить запросы из прошлого `WM_NOT_IN_CORE`,
   отметить созданные страницы: NEW → URL).
2. `parse_semantic_map.py` → `yandex_webmaster.py` → (`yandex_wordstat.py`) →
   `merge_report.py`.
3. Разобрать `report.md`: страницы для создания, мета-описания на доработку,
   новые запросы в карту.
4. Wordstat обновлять раз в месяц (частотность меняется медленно; скрипт сам
   пропускает запросы со свежими данными < 35 дней).

## Расширения (заложены, не реализованы)

- **Google Search Console**: завести service account, JSON в `GOOGLE_SA_KEY`,
  скрипт `google_search_console.py` → таблица `gsc_queries` (аналог
  `webmaster_queries`), join в `merge_report.py`.
- **Яндекс Метрика** (счётчик 109945462): OAuth-токен, поисковые фразы и
  конверсии по страницам.
