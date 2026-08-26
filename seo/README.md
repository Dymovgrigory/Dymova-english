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
├── yandex_wordstat.py    # Yandex Cloud Search API v2 Wordstat → wordstat (sqlite+csv)
├── google_search_console.py # GSC API → gsc_queries (нужен GOOGLE_SA_KEY)
├── yandex_metrika.py     # Метрика v1 поисковые фразы → metrika_phrases (нужен METRIKA_TOKEN)
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
WORDSTAT_API_KEY=            # TODO: API-ключ Yandex Cloud (Search API) — см. «Wordstat» ниже
WORDSTAT_FOLDER_ID=          # TODO: id каталога Yandex Cloud
DIRECT_TOKEN=                # устарело: OAuth Директа больше не принимается Wordstat API (404)
GOOGLE_SA_KEY=               # путь к JSON service account для GSC (или JSON одной строкой)
METRIKA_TOKEN=               # OAuth-токен Метрики (metrika:read), счётчик 109945462
```

Скрипты GSC и Метрики готовы и ждут ключей — см. раздел «GSC и Метрика» ниже.

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

## Wordstat: как владельцу получить доступ (пошагово, АКТУАЛЬНО с 2026)

⚠️ Старые способы закрыты Яндексом: сервис WordstatReports в Директ API v5 и бета
`api.wordstat.yandex.net` отдают 404, OAuth-токен Яндекс ID (`DIRECT_TOKEN`, y0__...)
не принимается. Wordstat API теперь — часть **Yandex Cloud Search API v2**
(`https://searchapi.api.cloud.yandex.net/v2/wordstat/*`), нужны API-ключ и id каталога.

1. Зарегистрироваться/войти в **Yandex Cloud** (https://console.cloud.yandex.ru/)
   под рабочим Яндекс-логином. При первом входе создастся облако и каталог
   (folder) — бесплатно, карта для активации может быть запрошена, но Wordstat-методы
   работают в рамках квоты без платного тарифа (лимиты ~10 rps, ~1000 запросов/сутки).
2. Создать **сервисный аккаунт**: каталог → «Сервисные аккаунты» → «Создать»,
   роль не критична для Search API (достаточно `search-api.executor` /
   по доке https://yandex.cloud/ru/docs/search-api/).
3. В сервисном аккаунте: «Создать новый ключ» → **«Создать API-ключ»** →
   сохранить секрет (показывается один раз).
4. **folderId** — в консоли: каталог → «Обзор» → «Идентификатор каталога».
5. Вписать в `.env.seo`:
   ```
   WORDSTAT_API_KEY=<секрет API-ключа>
   WORDSTAT_FOLDER_ID=<id каталога>
   ```
6. Проверить: `seo/.venv/bin/python seo/yandex_wordstat.py --limit 5` —
   запишет частотность 5 запросов в БД.

Механика скрипта: `v2/wordstat/topRequests` (до 2000 фраз за вызов), частотность
запроса = count точного совпадения в `results`; не попал в топ-2000 → freq_base=0.
`--exact` — второй проход точной формой `"!слова"` (только для freq_base > 0).
Скрипт держит rate-limit (10 rps), считает вызовы и останавливается у дневного
порога 950 — повторный запуск на следующий день продолжит (пропускает свежие).
Регионы: 213 (Москва) + 1 (Московская область), константа `REGIONS`; id уточнять
через `v2/wordstat/getRegionsTree`.

## Регламент (ежемесячно, начало месяца)

1. Обновить `SEO_SEMANTIC_MAP.md` (добавить запросы из прошлого `WM_NOT_IN_CORE`,
   отметить созданные страницы: NEW → URL).
2. `parse_semantic_map.py` → `yandex_webmaster.py` → (`yandex_wordstat.py`) →
   `merge_report.py`.
3. Разобрать `report.md`: страницы для создания, мета-описания на доработку,
   новые запросы в карту.
4. Wordstat обновлять раз в месяц (частотность меняется медленно; скрипт сам
   пропускает запросы со свежими данными < 35 дней).

## GSC и Метрика: как владельцу получить ключи (пошагово)

Скрипты `google_search_console.py` и `yandex_metrika.py` реализованы; без ключей
выходят мягко с подсказкой. После заполнения ключей в `.env.seo` прогон:
`seo/.venv/bin/python seo/google_search_console.py` и
`seo/.venv/bin/python seo/yandex_metrika.py` — данные попадут в таблицы
`gsc_queries` и `metrika_phrases`. Join в `merge_report.py` — следующий шаг
после первой успешной выгрузки.

**Google Search Console (GOOGLE_SA_KEY):**
1. console.cloud.google.com → проект → включить «Google Search Console API»;
2. IAM → Service Accounts → создать, скачать JSON-ключ;
3. Search Console → Настройки → Пользователи → добавить email сервисного
   аккаунта с доступом «чтение»;
4. В `.env.seo`: `GOOGLE_SA_KEY=/полный/путь/key.json` (или JSON одной строкой).

**Яндекс Метрика (METRIKA_TOKEN), счётчик 109945462:**
1. https://oauth.yandex.ru → «Зарегистрировать новое приложение»,
   платформа «веб-сервисы», права `metrika:read`;
2. Открыть `https://oauth.yandex.ru/authorize?response_type=token&client_id=<ID>`
   под логином владельца счётчика → скопировать токен;
3. В `.env.seo`: `METRIKA_TOKEN=y0__...`
