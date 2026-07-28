# Личный кабинет Tilda через прозрачный прокси Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Завершить перенос `dymova-english.ru` с Tilda на собственный сервер, сохранив рабочий личный кабинет Tilda (`/members/*`) через прозрачное проксирование на том же домене.

**Architecture:** Caddy на собственном сервере (`89.169.132.104`, контейнер `bot-caddy-1`) продолжает отдавать статический сайт для всех путей, кроме `/members/*` — этот путь перехватывается `handle_path` и проксируется на Tilda через промежуточную DNS-запись `tilda-origin.dymova-english.ru`, с явным `tls_server_name` и проброшенным `Host: dymova-english.ru`, чтобы Tilda узнала нужный проект.

**Tech Stack:** Caddy 2 (Docker), reg.ru DNS, bash/curl/dig для проверки.

## Global Constraints

- Домен, который трогаем — реально работающий бизнес-сайт: каждое DNS/Caddy-изменение проверяется curl-ом до и после, без слепых коммитов «должно сработать».
- DNS-правки на reg.ru делает только владелец (нет API/учётных данных доступа к регистратору в этом окружении) — эти шаги в плане помечены явно.
- Финальное переключение основной A-записи (Task 4) — только после того, как Task 3 подтвердит, что прокси на `/members/*` реально работает (тест через `curl --resolve`, без реального DNS-переключения).
- Ссылка «Личный кабинет» в шапке/подвале сайта (`https://dymova-english.ru/members/login`) не меняется — правим только серверную маршрутизацию.
- Спека: `docs/superpowers/specs/2026-07-28-tilda-members-proxy-design.md` — при расхождении плана и спеки приоритет у спеки, план должен быть скорректирован.

---

### Task 1: Добавить прокси-блок `/members/*` на Tilda в Caddyfile

**Files:**
- Modify: `bot/deploy/Caddyfile:29-33` (существующий блок `dymova-english.ru, www.dymova-english.ru`)

**Interfaces:**
- Consumes: DNS-имя `tilda-origin.dymova-english.ru` (создаётся владельцем в Task 2; на этом шаге просто ссылаемся на имя, не на IP — резолвится в рантайме).
- Produces: рабочий Caddy-конфиг с блоком `handle_path /members/*`, который Task 3 деплоит на сервер.

- [ ] **Step 1: Прочитать текущий блок перед правкой**

Файл `bot/deploy/Caddyfile`, строки 24-33 сейчас:

```caddy
# Основной сайт (миграция с Tilda завершена, см. DEVLOG.md "Сессия 28"/29
# и wiki/02-arhitektura.md). Собранные файлы (prototype/build_static_site.py,
# прод-режим — без --noindex) лежат в /srv/foxinburg-site на хосте — том
# пробрасывается в контейнер тем же способом, что и Caddyfile. Активируется
# автоматически, как только A-запись apex/www-домена укажет на этот сервер.
dymova-english.ru, www.dymova-english.ru {
    root * /srv/foxinburg-site
    try_files {path} {path}/index.html
    file_server
}
```

- [ ] **Step 2: Заменить блок на версию с прокси `/members/*`**

Новое содержимое (заменяет процитированный выше фрагмент целиком):

```caddy
# Основной сайт (миграция с Tilda завершена, см. DEVLOG.md "Сессия 28"/29
# и wiki/02-arhitektura.md). Собранные файлы (prototype/build_static_site.py,
# прод-режим — без --noindex) лежат в /srv/foxinburg-site на хосте — том
# пробрасывается в контейнер тем же способом, что и Caddyfile. Активируется
# автоматически, как только A-запись apex/www-домена укажет на этот сервер.
#
# /members/* — исключение: это фича личного кабинета Tilda (Tilda Members),
# которой нет в статической сборке. Пока не появится свой личный кабинет,
# этот путь прозрачно проксируется на Tilda — см. дизайн-документ
# docs/superpowers/specs/2026-07-28-tilda-members-proxy-design.md.
# tilda-origin.dymova-english.ru — отдельная A-запись (DNS-индикатор) с
# текущим IP Tilda для проекта 2053071. IP Tilda для этого домена уже менялся
# один раз без наших действий (было 185.215.4.12, стало 176.57.67.189) — при
# повторной смене правим ТОЛЬКО эту DNS-запись в кабинете reg.ru, Caddyfile
# трогать не нужно.
dymova-english.ru, www.dymova-english.ru {
    handle_path /members/* {
        reverse_proxy https://tilda-origin.dymova-english.ru:443 {
            transport http {
                tls_server_name dymova-english.ru
            }
        }
    }

    root * /srv/foxinburg-site
    try_files {path} {path}/index.html
    file_server
}
```

- [ ] **Step 3: Проверить синтаксис локально, если `caddy` установлен**

Run: `command -v caddy && caddy validate --config bot/deploy/Caddyfile --adapter caddyfile || echo "caddy CLI недоступен локально — синтаксис проверится на сервере в Task 3 через 'docker exec bot-caddy-1 caddy validate'"`

Expected: либо `Valid configuration`, либо явное сообщение, что проверка откладывается на Task 3 (это ожидаемо в большинстве окружений — caddy обычно не установлен локально, финальная валидация всё равно происходит на сервере тем же способом, что и в Сессии 29/30).

- [ ] **Step 4: Commit**

```bash
git add bot/deploy/Caddyfile
git commit -m "$(cat <<'EOF'
infra(bot): proxy /members/* to Tilda so the members area survives the site migration

The static site build has no Tilda Members feature. Reverse-proxy that one
path to Tilda (via a DNS indicator record so the upstream IP can change
without touching this file) instead of losing the login page again.
EOF
)"
```

---

### Task 2: Владелец создаёт DNS-индикатор `tilda-origin.dymova-english.ru`

**Files:** нет (действие вне репозитория, в кабинете reg.ru)

**Interfaces:**
- Consumes: текущий IP Tilda для проекта — `176.57.67.189` (проверено в этой сессии через `dig` у `ns1.reg.ru`/`ns2.reg.ru` и публичные резолверы).
- Produces: A-запись, на которую Task 1's `reverse_proxy` будет резолвиться в Task 3.

- [ ] **Step 1: Попросить владельца добавить запись**

Сообщение владельцу (отправляется как обычный текст в чате, не автоматизировано):

> В кабинете reg.ru добавьте A-запись: `tilda-origin.dymova-english.ru → 176.57.67.189`. Она не заменяет и не трогает существующие записи `dymova-english.ru`/`www.` — это отдельное служебное имя только для проксирования личного кабинета.

- [ ] **Step 2: Дождаться подтверждения и проверить распространение**

Run (повторять с паузой, например через `ScheduleWakeup` на 5 минут между попытками, как в Сессии 30 — не гадать, а реально перепроверять):

```bash
dig +short tilda-origin.dymova-english.ru A @ns1.reg.ru
dig +short tilda-origin.dymova-english.ru A @1.1.1.1
```

Expected: оба возвращают `176.57.67.189`.

---

### Task 3: Задеплоить Caddyfile на сервер и проверить прокси ДО переключения основного DNS

**Files:** нет новых; деплой уже закоммиченного в Task 1 `bot/deploy/Caddyfile` на `foxinburg-vm`.

**Interfaces:**
- Consumes: DNS-запись из Task 2 (`tilda-origin.dymova-english.ru`), коммит из Task 1.
- Produces: рабочий прокси на сервере, проверенный без риска для реального трафика (основной домен пока ещё смотрит на Tilda) — Task 4 полагается на этот результат перед переключением.

- [ ] **Step 1: Задеплоить и перечитать конфиг**

```bash
ssh foxinburg-vm 'cd ~/Dymova-english && git pull && docker exec bot-caddy-1 caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile'
```

Expected: `Valid configuration`.

- [ ] **Step 2: Применить конфиг**

```bash
ssh foxinburg-vm 'docker exec bot-caddy-1 caddy reload --config /etc/caddy/Caddyfile'
```

Expected: команда завершается без ошибок (без вывода — успех).

- [ ] **Step 3: Проверить, что существующие сайты не пострадали**

```bash
curl -sS -o /dev/null -w "%{http_code}\n" https://bot.dymova-english.ru/health
curl -sS -o /dev/null -w "%{http_code}\n" https://new.dymova-english.ru/
```

Expected: `200` и `200`.

- [ ] **Step 4: Проверить прокси `/members/*`, подставив IP сервера напрямую (DNS основного домена ещё не переключён)**

```bash
curl -sS --resolve dymova-english.ru:443:89.169.132.104 https://dymova-english.ru/members/login | head -c 300
```

Expected: HTML с признаками Tilda Members — `members.tildaapi.com`, `data-tilda-project-id="2053071"` (та же разметка, что мы видели напрямую с `176.57.67.189` в начале сессии).

- [ ] **Step 5: Проверить, что обычная статика на apex-домене (тот же хост) тоже не пострадала**

```bash
curl -sS --resolve dymova-english.ru:443:89.169.132.104 -o /dev/null -w "%{http_code}\n" https://dymova-english.ru/
```

Expected: `200`.

Если Step 4 не дал ожидаемого результата — **не переходить к Task 4**. Разобрать через systematic-debugging (проверить `docker logs bot-caddy-1`, вручную резолвить `tilda-origin.dymova-english.ru` изнутри контейнера, перепроверить SNI/Host отдельным `openssl s_client`).

---

### Task 4: Владелец переключает основной DNS, финальная проверка на живом трафике

**Files:** нет (DNS-действие вне репозитория).

**Interfaces:**
- Consumes: подтверждённый рабочий прокси из Task 3.
- Produces: `dymova-english.ru` полностью отдаётся с собственного сервера, включая рабочий `/members/*`.

- [ ] **Step 1: Попросить владельца переключить A-записи**

Сообщение владельцу:

> Всё готово и проверено (личный кабинет через прокси работает). В кабинете reg.ru верните A-записи `dymova-english.ru` и `www.dymova-english.ru` на `89.169.132.104` (то же значение, что было в Сессии 30). TTL 3600 — распространение до часа, обычно быстрее.

- [ ] **Step 2: Дождаться распространения**

```bash
dig +short dymova-english.ru A @ns1.reg.ru
```

Expected: `89.169.132.104`. Если после 5-10 минут (`ScheduleWakeup`) всё ещё старое значение — просто продолжать перепроверять, не считать готовым раньше времени (тот же принцип, что в Сессии 30).

- [ ] **Step 3: Финальная проверка на реальном DNS (без `--resolve`)**

```bash
curl -sS -o /dev/null -w "%{http_code}\n" https://dymova-english.ru/
curl -sS -o /dev/null -w "%{http_code}\n" https://www.dymova-english.ru/
curl -sS https://dymova-english.ru/members/login | grep -o 'data-tilda-project-id="[0-9]*"'
curl -sS -o /dev/null -w "%{http_code}\n" https://dymova-english.ru/members/register
```

Expected: `200`, `200`, `data-tilda-project-id="2053071"`, `200`.

- [ ] **Step 4: Живой тест в браузере (ручной, не автоматизируемый)**

Открыть `https://dymova-english.ru/members/login` в обычном браузере, залогиниться существующим тестовым/реальным аккаунтом кабинета, убедиться что вход и последующая навигация внутри кабинета работают на домене `dymova-english.ru` (не редиректит на голый IP/ошибку, куки принимаются).

Report the result to the user directly — this step cannot be verified by an autonomous agent.

---

### Task 5: Зафиксировать сессию в DEVLOG.md

**Files:**
- Modify: `DEVLOG.md` (добавить новую секцию `### Сессия 33 (Claude Code) — ...` в конец файла, по образцу секций 29-32).

**Interfaces:**
- Consumes: результаты Task 1-4 (что реально было сделано и проверено).
- Produces: запись в истории проекта, включая напоминание про риск TLS-сертификата Tilda (дедлайн проверки — начало октября 2026, сертификат истекает 24.10.2026).

- [ ] **Step 1: Добавить секцию в конец DEVLOG.md**

Добавить в конец файла (после последней секции `### Сессия 32 ...`):

```markdown

### Сессия 33 (Claude Code) — личный кабинет Tilda сохранён через прокси, миграция с Tilda завершена по-настоящему

**Дата:** 2026-07-28
**Спека:** `docs/superpowers/specs/2026-07-28-tilda-members-proxy-design.md`
**План:** `docs/superpowers/plans/2026-07-28-tilda-members-proxy.md`

**Запрос владельца:** личный кабинет (`/members/login`) сломался после переноса домена на свой сервер в Сессии 30 — Tilda Members не существует в статической сборке. Владелец временно откатил DNS на Tilda, попросил переехать с Tilda полностью, но оставить личный кабинет рабочим через Tilda.

**Сделано:**
- `bot/deploy/Caddyfile` — добавлен `handle_path /members/*` в блоке `dymova-english.ru, www.dymova-english.ru`, проксирует на `tilda-origin.dymova-english.ru` (новая DNS-запись-индикатор → IP Tilda) с явным `tls_server_name dymova-english.ru`.
- DNS: добавлена `tilda-origin.dymova-english.ru → 176.57.67.189`; основные A-записи `dymova-english.ru`/`www.` возвращены на `89.169.132.104`.
- Проверено: прокси протестирован через `curl --resolve` до переключения основного DNS, затем — на реальном трафике после переключения (200 на `/`, `/members/login`, `/members/register`, разметка Tilda Members с `project-id=2053071` подтверждена).

**Известный риск (проверить до 24.10.2026):** сертификат Let's Encrypt у Tilda для `dymova-english.ru` выпущен 26.07.2026, истекает 24.10.2026. Продление зависит от способности Tilda пройти ACME-валидацию домена — а домен больше не указывает на Tilda. Если к началу октября `/members/login` не проверен — сделать это в первую очередь; при поломке из-за TLS это будет новый режим отказа (не 404, а TLS-ошибка при подключении Caddy к `tilda-origin.dymova-english.ru`).

**Деплой:** прод. `dymova-english.ru`/`www.` — снова отдаются с собственного сервера (`89.169.132.104`), `/members/*` прозрачно проксируется на Tilda.
```

- [ ] **Step 2: Commit**

```bash
git add DEVLOG.md
git commit -m "docs(DEVLOG): сессия 33 — личный кабинет Tilda сохранён через прокси"
```

## Self-Review Notes

- **Spec coverage:** архитектура (Task 1), DNS-индикатор (Task 2), риски/TLS-сертификат (задокументирован в Task 5, наблюдение — не код, т.к. митигация вне нашего контроля), проверка после деплоя (Task 3 Step 4-5, Task 4 Step 3-4) — всё покрыто.
- **Placeholder scan:** нет TBD/TODO; каждый шаг содержит конкретные команды/текст.
- **Type consistency:** имя `tilda-origin.dymova-english.ru` и IP `176.57.67.189` используются одинаково во всех задачах, где встречаются.
