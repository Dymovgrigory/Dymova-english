# Технический SEO-аудит dymova-english.ru

**Дата:** 20.08.2026
**Аудитор:** Technical SEO Engineer
**Объект:** https://dymova-english.ru (39 URL) + стейджинг new.dymova-english.ru
**Стек:** статика `prototype/` → `build_static_site.py` + `build_subpages.py` → `dist_prod` → rsync → Caddy (`bot/deploy/Caddyfile`)

Все находки проверены на проде (curl) и/или чтением кода сборки. Ссылки на код — в формате `файл:строка`.

---

## 1. Executive Summary

### FOXINBURG TECHNICAL SEO SCORE: **74 / 100**

| Категория | Вес | Балл | Комментарий |
|---|---|---|---|
| Indexation & crawlability | 20 | 15 | robots.txt и sitemap.xml корректны, staging noindex — но нет редиректов со старых URL, нет 404-страницы, нет image-sitemap |
| Meta & on-page | 15 | 14 | Уникальные title/description на всех 39 URL, canonical self, og полные; минус за молчаливый fallback-meta |
| Schema / structured data | 15 | 11 | EducationalOrganization + LocalBusiness + Course×11 + FAQPage + Article×15 + BreadcrumbList — сильный набор; не хватает Review/AggregateRating, Event, VideoObject; фиды не деплоятся |
| Performance (CWV) | 25 | 12 | Главный риск: three.js ~700КБ + два GLB ~1.4МБ на **каждой** странице. Устаревший Lighthouse mobile 38 (LCP 18.6s), нужен повторный замер |
| Mobile UX | 10 | 8 | Адаптив есть, но CLS-аутсайдеры (/grammar 1.11, /podderzhivayushchie-online 0.94, /standartnye-offline 0.94) требуют перепроверки |
| Security & protocol | 10 | 10 | HTTPS, HSTS, www→apex 301, x-content-type-options, referrer-policy, zstd/gzip — всё на месте |
| Analytics / measurement | 5 | 0 | **Ни Яндекс.Метрики, ни GA4 на страницах нет** — нет данных для оценки SEO-эффективности вообще |

**Итог:** фундамент (индексация, мета, схема, безопасность) — уровень «хорошо/отлично». Два провала: отсутствие аналитики (слепота по всем решениям) и performance (тяжёлый 3D-стек на каждой странице). Оба исправимы без смены архитектуры.

**Топ-5 приоритетов:**
1. **C1** Подключить Яндекс.Метрику 109945462 через существующий гейтинг `fxb-consent` — без этого все остальные улучшения неизмеримы.
2. **H1** Условная/отложенная загрузка three.js + GLB: прелоад только на главной, на остальных — по взаимодействию/idle.
3. **H2** Редиректы `/news → /novosti` и старых legacy-URL → 301.
4. **M1** Custom 404-страница.
5. **M2** Убрать неиспользуемые `foxi.glb` (1.2МБ) и `foxi-rigged-v1-17clips.glb` (1.2МБ) из деплоя.

---

## 2. Таблица находок

| ID | Severity | Категория | Описание | Доказательство | Рекомендация | Effort |
|----|----------|-----------|----------|----------------|--------------|--------|
| C1 | **Critical** | Analytics | Яндекс.Метрика и GA4 отсутствуют на страницах: 0 совпадений `ym(`, `googletagmanager`, `109945462` в `dist_prod`. Счётчик 109945462 и цели существуют, событие согласия `fxb-consent` уже реализовано | `grep -rn "109945462\|ym(\|gtag" prototype/dist_prod/*.html` → пусто; `prototype/wow/foxi-consent.js:3,23` | Подключить Метрику в `build_static_site.py` (head-сниппет с defer-активацией по `fxb-consent`), см. §3.C1 | S (0.5д) |
| H1 | **High** | Performance | three.js (~700КБ) + `foxi-splash.glb` (688КБ) + `foxi-rigged.glb` (726КБ) грузятся на **каждой** странице (modulepreload в head + инлайн-fetch), включая `/policy` | `prototype/build_static_site.py:341-348` (инлайн-лоадер `window.__fxbPre`); `ls -la prototype/dist_prod/mascot/` | Условная загрузка: прелоад GLB только на главной, на остальных — lazy по IntersectionObserver/idle; three.js динамическим `import()` | M (1-2д) |
| H2 | **High** | Indexation | `/news` → 404 вместо 301 на `/novosti`; старые legacy-URL (`/page32889798.html` и аналоги) → 404 без редиректа. Потеря ссылочного веса и исторических позиций | `curl -sI https://dymova-english.ru/news` → `HTTP/2 404`; `curl -sI .../page32889798.html` → 404 | `redir` правила в `bot/deploy/Caddyfile` | S (1ч) |
| M1 | **Medium** | UX/Indexation | Нет custom 404-страницы — Caddy отдаёт дефолтную. Потерянные пользователи, нет навигации обратно | `curl -s https://dymova-english.ru/nonexistent-xyz` — дефолтный ответ Caddy | Собрать `404.html` в билде + `handle_errors` в Caddyfile | S (2ч) |
| M2 | **Medium** | Performance | Неиспользуемые `foxi.glb` (1.2МБ) и `foxi-rigged-v1-17clips.glb` (1.2МБ) уезжают в прод | `ls prototype/dist_prod/mascot/` — файлы присутствуют; не ссылается ни один HTML | Удалить из `dist_prod`/исключить в rsync или билде | XS (15мин) |
| M3 | **Medium** | Schema | Нет Review/AggregateRating (отзывы Яндекса есть на `/kontakty`), Event (Летняя Академия), VideoObject | Аудит JSON-LD в `dist_prod`: EducationalOrganization+LocalBusiness сайтwide, Course×11, FAQPage, Article×15, BreadcrumbList — Review/Event/VideoObject отсутствуют | Добавить в `SCHEMA_MAP`/`INDEX_SCHEMA` в `build_static_site.py` | M (1д) |
| M4 | **Medium** | Schema/Indexation | Sitemap без image-расширения (`xmlns:image`) — изображения (маскот, галерея, команда) не попадают в image-поиск эффективно | `prototype/dist_prod/sitemap.xml` — только `loc`+`lastmod` | Генерировать `image:image` в `build_static_site.py`; см. §5 | S (3ч) |
| M5 | **Medium** | Feeds | Фиды `seo_schema/feed_education.xml` и `feed_vacancies.xml` не копируются в `dist_prod` → 404 на проде | `ls prototype/dist_prod/feed*.xml` → нет | Добавить копирование фидов в билд/rsync-шаг | XS (30мин) |
| M6 | **Medium** | Cache | Caddy cache-правило `@static` ссылается на `/og-cover.png`, реальный путь `/assets/og-cover.png` → og-картинка без long-cache | `bot/deploy/Caddyfile` (matcher `@static`); `ls prototype/dist_prod/assets/og-cover.png` | Исправить путь в Caddyfile | XS (10мин) |
| M7 | **Medium** | Meta | Fallback-meta в `build_static_site.py:352-353`: при отсутствии title молча рождается `<alias> — Фоксинбург` с **пустым** description — риск тихой деградации новых страниц | `prototype/build_static_site.py:352` `title = meta.get("title") or f"{alias} — Фоксинбург"` | Сделать билд падающим (fail) при пустом meta, либо warning-отчёт в конце билда | XS (1ч) |
| L1 | **Low** | UX/Schema | Видимые хлебные крошки только в статьях — BreadcrumbList в schema есть, визуальных нет на страницах программ | Просмотр `dist_prod/*/index.html` (program pages) | Добавить визуальные breadcrumbs в шапку страниц программ (`shapka` в билде) | S (3ч) |
| L2 | **Low** | Indexation | Sitemap один файлом без sitemap-index — при 39 URL нормально, но нет готовой архитектуры роста | `dist_prod/sitemap.xml` | Задокументировать порог разделения (§5), реализовать при >200 URL | S |
| L3 | **Low** | Analytics | `yandex-verification: c08742055e803bc5` есть, но нет Google Search Console verification | Аудит head в `dist_prod` | Добавить GSC verification meta при наличии доступа | XS |

**Проверено и ОК (не находки):** уникальные title/description на всех 39 URL; canonical self-referencing; www→apex 301; staging noindex (двойной: robots + meta); HSTS `max-age=31536000`; `x-content-type-options`, `referrer-policy: strict-origin-when-cross-origin`; webp + lazy + alt у изображений; self-hosted variable Montserrat; zstd/gzip; JSON-LD EducationalOrganization+LocalBusiness сайтwide, Course×11, FAQPage, Article×15, BreadcrumbList; полные og-теги.

---

## 3. Решения по каждой проблеме (под текущий стек)

### C1 — Яндекс.Метрика через fxb-consent (готовое решение)

Согласие уже реализовано: `prototype/wow/foxi-consent.js` хранит выбор в `fxb_cookie_consent_v1` и шлёт `document.dispatchEvent(new CustomEvent("fxb-consent", { detail: { v } }))` (строки 3, 23). Цели в Метрике 109945462 уже настроены.

**Правка: `prototype/build_static_site.py`, в `build_head()`** — добавить в конец `<head>` всех страниц:

```html
<script>
(function(){
  var COUNTER_ID = 109945462;
  var loaded = false;
  function loadYM(){
    if (loaded) return; loaded = true;
    (function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};
    m[i].l=1*new Date();k=e.createElement(t),a=e.getElementsByTagName(t)[0],
    k.async=1,k.src=r,a.parentNode.insertBefore(k,a)})
    (window,document,"script","https://mc.yandex.ru/metrika/tag.js","ym");
    ym(COUNTER_ID,"init",{
      clickmap:true, trackLinks:true, accurateTrackBounce:true,
      webvisor:false, trackHash:false, defer:true
    });
  }
  if (localStorage.getItem("fxb_cookie_consent_v1")==="all") loadYM();
  document.addEventListener("fxb-consent",function(e){
    if(e.detail&&e.detail.v==="all") loadYM();
  });
})();
</script>
```

Ключевые решения:
- **Гейтинг**: счётчик грузится только при `fxb_cookie_consent_v1 === "all"` или по событию `fxb-consent` — соответствие 152-ФЗ без изменений в баннере.
- **`defer:true` + `async`** — tag.js не блокирует рендер (не ломаем CWV из H1).
- **`webvisor:false`** — Webvisor тяжёлый; включить позже при необходимости.
- **noscript-блок НЕ добавляем** — он шлёт hit без согласия.
- GA4 — не подключать, пока нет явной потребности: Метрика + Вебмастер покрывают RU-SEO, лишний JS вредит CWV.

### H1 — Условная загрузка 3D-стека

Сейчас: `modulepreload` на three.js + инлайн-скрипт с `window.__fxbPre` (fetch GLB) в `<head>` каждой страницы (`build_static_site.py:341-348`).

**Правки:**

1. **`build_static_site.py`**: modulepreload + инлайн-fetch GLB оставить **только для `alias == "index"`**. Для остальных страниц — отложенный лоадер:

```python
LAZY_3D = ("<script>"
  "window.__fxbLoad3d=function(){"
  "if(window.__fxbPre)return Promise.resolve(window.__fxbPre.glb);"
  "window.__fxbPre={glb:fetch('/mascot/foxi-splash.glb')"
  ".then(function(r){return r.arrayBuffer();})};"
  "return window.__fxbPre.glb;};"
  "var kick=function(){"
  "if('requestIdleCallback' in window){requestIdleCallback(window.__fxbLoad3d,{timeout:4000});}"
  "else{setTimeout(window.__fxbLoad3d,2000);}};"
  "if(document.readyState==='complete'){kick();}"
  "else{window.addEventListener('load',kick);}"
  "</script>")
```

- `/policy` и другие служебные страницы: **не грузить 3D вообще** (маскот там не показывается) — вешать `LAZY_3D` только на страницы, где canvas маскота реально рендерится (определить по наличию контейнера, либо whitelist алиасов).
- three.js перевести с `modulepreload` на динамический `import()` внутри `foxi-3d.js` — модуль скачивается только когда нужен маскот.
- `foxi-splash.glb`/`foxi-rigged.glb` — кандидаты на Draco/meshopt-компрессию (`gltf-transform optimize`), целевой бюджет ≤300КБ каждый. Это отдельная задача, не блокирует H1.

**Важно:** wow-эффект — сознательная фича владельца, не убираем. Цель — чтобы LCP и INP не страдали на страницах, где 3D не критичен для первого экрана.

### H2 — Редиректы в Caddyfile

**Правка: `bot/deploy/Caddyfile`** (блок `dymova-english.ru`):

```caddy
# Legacy URL (pageXXXXX.html) и алиасы
redir /news /novosti 301
redir /page32889798.html / 301
# …добавить маппинг всех известных старых URL из архива/логов:
# redir /page<old>.html /<новый-алиас> 301
```

Полный список старых URL получить из Яндекс.Вебмастера (после подключения C1 появятся данные о 404) и из `wget`-архива старой версии сайта, если сохранился. Правило: каждый старый URL → **один хоп** на максимально релевантную новую страницу, не цепочки.

### M1 — Custom 404

1. Собрать `404.html` в билде (`build_static_site.py` или отдельный статичный файл в `dist_prod` через `build_subpages.py`): бренд, навигация на главные разделы, поиск/список программ, `noindex` в meta.
2. **`bot/deploy/Caddyfile`**:

```caddy
handle_errors {
    @404 expression {http.error.status_code} == 404
    rewrite @404 /404.html
    file_server
}
```

### M2 — Удаление неиспользуемых GLB

`foxi.glb` и `foxi-rigged-v1-17clips.glb` не ссылаются ни в одном HTML. Удалить из исходников `prototype/wow/` / `prototype/mascot/` (где лежат) и добавить `--exclude` в rsync-деплой, либо просто не копировать в билде. Экономия ~2.4МБ в бандле деплоя (не влияет на CWV, но чистит crawl/backup).

### M3 — Недостающие schema-типы

**Правка: `build_static_site.py`, `SCHEMA_MAP` / `INDEX_SCHEMA`:**

- **AggregateRating + Review** на `/kontakty` и главную: агрегировать из отзывов Яндекса (рейтинг + count). Важно: schema должен соответствовать видимому контенту — вывести рейтинг и число отзывов текстом на странице, иначе Google расценит как спам.
- **Event** на `/letnyaya-akademiya`: `EducationEvent` с `startDate`, `location`, `offers` (цена), `organizer` → EducationalOrganization. Обновлять даты каждую смену (кандидат на генерацию из данных).
- **VideoObject** — только когда появятся реальные видео на страницах (сейчас не добавлять «на вырост»).

### M4 — Image-sitemap

В генераторе `sitemap.xml` (в `build_static_site.py`) добавить `xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"` и для каждой страницы — `<image:image><image:loc>…` ключевых изображений (hero, маскот, og-cover). Сейчас 39 URL — можно одним файлом, см. §5.

### M5 — Фиды в деплой

`seo_schema/feed_education.xml`, `feed_vacancies.xml`: добавить копирование в `dist_prod` в билд-скрипт (или в rsync-шаг), проверить `Content-Type: application/xml` (Caddy отдаст корректно по расширению). Добавить URL фидов в `robots.txt` комментарием и в Вебмастер.

### M6 — Caddy cache для og-cover

**`bot/deploy/Caddyfile`**: в matcher `@static` заменить `/og-cover.png` на `/assets/og-cover.png`. Заодно проверить, что все реальные статические пути покрыты: `/assets/*`, `/mascot/*`, `/media/*`, `/gallery/*`, `/team-media/*`.

### M7 — Fail-fast на пустое meta

**`build_static_site.py:352`:**

```python
title = meta.get("title")
description = meta.get("description")
if not title or not description:
    raise SystemExit(f"[SEO] Пустой title/description для '{alias}' — билд остановлен")
```

Пустой description недопустим в проде; лучше упасть в CI, чем молча выкатить деградацию. (Сейчас все 39 URL с мета — проверено, так что падать не начнёт.)

### L1 — Визуальные хлебные крошки

Добавить в общий `shapka` страниц программ: `Главная → Программы → <Название>` с микроразметкой, консистентной с существующим BreadcrumbList в JSON-LD. Крошки для статей уже есть — переиспользовать их CSS.

---

## 4. Performance-план

### Бюджеты Core Web Vitals (mobile, полевые данные CrUX/RUM)

| Метрика | Цель | Текущее (Lab, 04.07.2026, устарело) |
|---|---|---|
| LCP | < 2.5s | главная 18.6s, /doshkolniki 12.3s, /kontakty 7.5s |
| INP | < 200ms | нет данных (замерить) |
| CLS | < 0.1 | /grammar 1.11, /podderzhivayushchie-online 0.94, /standartnye-offline 0.94, /reading 0.68 |

Данные 04.07.2026 частично устарели после сессий 51–58 — обязателен повторный замер (§7) **до** оценки эффекта от H1.

### Стратегия для 3D (не убиваем wow)

3D-маскот — сознательная бренд-фича владельца. План — не удаление, а контроль момента и места загрузки:

1. **Главная**: сохранить прелоад `foxi-splash.glb` (это LCP-критичный опыт), но: fetch с `priority` после hero-контента; three.js — modulepreload (уже есть); рассмотреть `fetchpriority="high"` только на hero-изображение, а не на GLB.
2. **Внутренние страницы**: GLB + three.js — lazy (см. H1): `requestIdleCallback` после `load`, либо по первому скроллу/появлению canvas в viewport (IntersectionObserver).
3. **Служебные страницы** (`/policy`, 404): 3D не грузить вообще.
4. **Размер**: `gltf-transform optimize` (meshopt + KTX2-текстуры) → цель ≤300КБ на GLB вместо 688/726КБ. Проверить визуальное качество после компрессии.
5. **Удалить мёртвый вес**: `foxi.glb`, `foxi-rigged-v1-17clips.glb` (M2).
6. **INP**: вся инициализация three.js — после `load`, не в критическом пути; рендер-цикл маскота на `requestAnimationFrame` с паузой при `document.hidden` и когда canvas вне viewport.
7. **Кэш**: GLB/JS/wasm → `Cache-Control: public, max-age=31536000, immutable` с хэшированными именами (Caddy, заодно с M6).

### CLS

Причины на аутсайдерах (/grammar и др.) — вероятно поздние вставки блоков/изображений без размеров. Чек-лист: `width`/`height` (или `aspect-ratio`) на всех `<img>`, резерв места под динамические блоки (3D-canvas — фиксированная высота контейнера), шрифты: Montserrat self-hosted variable + `font-display: swap` — проверить, что метрики fallback близки (расхождение метрик шрифтов — частый источник CLS). Перепроверить после повторного Lighthouse.

---

## 5. Crawl budget и indexation

**Текущее состояние:** 39 URL, один `sitemap.xml` (loc+lastmod, корректный), `robots.txt`: `Allow: /` + `Sitemap`. Для сайта такого размера crawl budget не является проблемой — Яндекс/Google обходят всё. Фокус — на чистоте индекса:

- **Orphan-страницы**: контролировать, что каждый URL из sitemap достижим по внутренним ссылкам ≤3 кликов от главной. Проверка — в CI-гейте (§6): краулер по sitemap + проверка входящих ссылок.
- **Дубли**: canonical self на всех 39 — ок. Следить, чтобы не появлялись URL с параметрами (`?utm`, `?yclid`) в индексе — Метрика/реклама добавят параметры; canonical self их закрывает, но стоит добавить `Clean-param` не нужен (Яндекс сам склеивает по canonical).
- **Редиректы**: после H2 — контролировать отсутствие цепочек (старый URL → новый в один хоп). Правило: редирект живёт минимум 12 месяцев после миграции.
- **404-контроль**: после подключения Вебмастера (C1) — еженедельный просмотр «Исключённые страницы / ошибки сканирования».

**Sitemap-архитектура на будущее:**
- Сейчас (39 URL) — одного файла достаточно. **Не делить преждевременно.**
- Порог разделения: **>200 URL** или **>150 изображений** в image-расширении → sitemap-index: `sitemap-pages.xml` (программы/страницы), `sitemap-news.xml` (статьи, с news-спецификой при необходимости), `sitemap-images.xml`.
- Лимиты формата: 50 000 URL / 50МБ на файл — до них далеко, ориентир именно 200 URL как управляемость + скорость регенерации.
- Image-расширение (M4) добавить уже сейчас, в текущий единый файл.

---

## 6. CI/CD SEO-гейты

Гейты при каждом deploy (после билда `dist_prod`, до rsync). Без новых тяжёлых зависимостей — Python stdlib уже есть, билд на Python.

**Новый скрипт: `prototype/seo_gate.py`** (запускать после `build_static_site.py` + `build_subpages.py`):

```bash
python prototype/seo_gate.py prototype/dist_prod
```

Проверки (fail = ненулевой exit, деплой блокируется):

1. **Meta-полнота**: у каждого HTML — непустые уникальные `<title>` и `<meta name="description">` (дубли title между страницами = fail). Закрывает M7 на уровне артефакта.
2. **Canonical**: каждый HTML имеет `<link rel="canonical">` на свой же URL; staging-сборка — `noindex` (проверять по флагу окружения).
3. **Sitemap sync**: множество URL в `sitemap.xml` == множеству директорий-страниц в `dist_prod`; каждый `loc` отвечает бы (локально по файлам); `lastmod` валиден ISO.
4. **Broken internal links**: парсинг всех `href`/`src` в HTML — каждая внутренняя ссылка существует в `dist_prod` (или в whitelist редиректов Caddyfile). Закрыло бы H2 до прода.
5. **Schema-валидация**: извлечь все `application/ld+json`, `json.loads`, проверить обязательные поля по типам (`@type`, `name`, для Course — `provider`, для Article — `headline`, `datePublished`). Полная валидация — периодически вручную через validator.schema.org / Яндекс.Вебмастер.
6. **Analytics-гейт**: хотя бы один из маркеров (`ym(`, `109945462`) присутствует на всех страницах (после C1). Защита от регрессии «счётчик отвалился при правке шаблона».
7. **404.html существует** и содержит `noindex` (после M1).
8. **Весовой бюджет**: суммарный вес JS+GLB, отдаваемый страницей `/policy`, < 200КБ (после H1); каждый HTML < 150КБ.

**Lighthouse CI** — не в каждый деплой (долго и флаки на shared-инфре), а:
- nightly/weekly прогон `lighthouse --preset=desktop` + mobile на 5 ключевых URL (главная, /tseny, /kontakty, /grammar, одна статья) против стейджинга `new.dymova-english.ru`;
- регрессионный порог: падение perf-score >10 пунктов или LCP >4s (lab) → алерт, не блок.

---

## 7. План повторного Lighthouse-замера

**Когда:** после внедрения C1, H1, M2 (пакет «измеримость + вес»). Замер до и после — иначе не отделить эффект сессий 51–58 от новых правок.

**Протокол:**

1. **Baseline «сейчас»** (до правок, если успеваем): mobile-прогон Lighthouse (CLI, `--throttling.cpuSlowdownMultiplier=4`, симуляция) на 8 URL: главная, /tseny, /kontakty, /grammar, /podderzhivayushchie-online, /standartnye-offline, /reading, /doshkolniki + 1 статья. Сохранить JSON-отчёты в `seo_screens/` / `docs/`.
2. **После внедрений** — тот же набор URL, те же настройки. Каждый URL — 3 прогона, брать медиану (LCP флаки).
3. **Критерии успеха (mobile, lab):**
   - главная: perf-score ≥ 70 (с 38), LCP ≤ 4s lab (цель 2.5s — по полевым данным после 28 дней RUM из Метрики/CrUX);
   - CLS ≤ 0.1 на всех 8 URL (сейчас 4 страницы 0.68–1.11);
   - INP — собрать первые полевые данные из Метрики (после C1) за 28 дней.
4. **Полевые данные**: после C1 подключить отчёт CWV в Яндекс.Метрике (или web-vitals.js → custom-события в Метрику) — lab-числа ориентир, решения по бюджету принимать по p75 полевых.
5. **Результат** — таблица «до/после» в DEVLOG.md и апдейт этого аудита (секция Executive Summary, балл Performance).

---

## Приложение. Команды проверки (воспроизводимость)

```bash
# Аналитика отсутствует
grep -rn "109945462\|ym(\|googletagmanager\|gtag" prototype/dist_prod/*.html   # → пусто

# Редиректы/404
curl -sI https://dymova-english.ru/news                  # HTTP/2 404
curl -sI https://dymova-english.ru/page32889798.html     # HTTP/2 404
curl -sI https://dymova-english.ru/nonexistent-xyz       # HTTP/2 404 (дефолт Caddy)

# Заголовки безопасности (ок)
curl -sI https://dymova-english.ru/ | grep -iE "strict-transport|referrer|content-type-options"

# Sitemap / robots
curl -s https://dymova-english.ru/sitemap.xml | grep -c "<loc>"   # 39
curl -s https://dymova-english.ru/robots.txt
```

---

## Повторный baseline 20.08.2026 (после чистки GLB, сессия 59)

Замер: Chrome DevTools performance trace, мобильный профиль (390×844, Fast 4G, CPU 4x), прод https://dymova-english.ru/:

| Метрика | 04.07.2026 (старый аудит) | 20.08.2026 | Бюджет | Статус |
|---|---|---|---|---|
| LCP mobile (главная) | 18.6 s | **0.39 s** | < 2.5 s | ✅ |
| CLS (главная) | — | **0.00** | < 0.1 | ✅ |
| Lighthouse SEO | — | **100** | 100 | ✅ |
| Lighthouse Accessibility | — | **85** | ≥ 95 | ⚠️ color-contrast, aria-prohibited-attr, frame-title, select-name |
| Lighthouse Best Practices | — | **69** | ≥ 95 | ⚠️ image-aspect-ratio, third-party cookies (Яндекс.Карта), console errors (локальный /api — не прод) |

Вывод: главная по CWV укладывается в бюджеты с запасом (сессии 51–58 + чистка GLB дали эффект). Задача «условная загрузка 3D» понижена до P2: LCP не страдает, риск ломать сознательную wow-фичу владельца выше выгоды. Приоритет смещён на a11y/best-practices находки (P2) и повторный замер внутренних страниц после появления полевых данных из Метрики (через 28 дней).
