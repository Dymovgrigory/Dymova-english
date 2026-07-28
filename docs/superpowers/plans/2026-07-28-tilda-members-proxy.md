# Личный кабинет Tilda через прозрачный прокси Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Завершить перенос `dymova-english.ru` с Tilda на собственный сервер, сохранив рабочий личный кабинет Tilda (`/members/*`).

**Architecture:** Caddy на собственном сервере (`89.169.132.104`, контейнер `bot-caddy-1`) продолжает отдавать статический сайт для всех путей, кроме `/members/*` — этот путь редиректит (302) на `tilda-members.dymova-english.ru`, отдельный поддомен, у которого DNS указывает прямо на Tilda и который добавлен как алиас в настройках проекта 2053071 в кабинете Tilda.

**Ревизия (Task 1-3 ниже переписаны после первой попытки деплоя):** изначальный вариант — Caddy сам проксировал запросы на Tilda (`reverse_proxy`). При реальной проверке (curl через `--resolve` на IP сервера) выяснилось: DDoS-Guard перед Tilda возвращает `425 D'oh!` на любой запрос с IP этого сервера (датацентр Yandex Cloud) — контрольный запрос с обычного IP в то же время проходил чисто. Reverse-proxy сломал бы кабинет для всех посетителей одинаково (все выглядели бы для Tilda как один и тот же датацентр-IP). Заменено на HTTP-редирект — браузер посетителя подключается к Tilda напрямую, своим IP. Подробности — в спеке, раздел «Почему не прямое проксирование».

**Tech Stack:** Caddy 2 (Docker), reg.ru DNS, bash/curl/dig для проверки.

## Global Constraints

- Домен, который трогаем — реально работающий бизнес-сайт: каждое DNS/Caddy-изменение проверяется curl-ом до и после, без слепых коммитов «должно сработать».
- DNS-правки на reg.ru делает только владелец (нет API/учётных данных доступа к регистратору в этом окружении) — эти шаги в плане помечены явно.
- Финальное переключение основной A-записи (Task 4) — только после того, как Task 3 подтвердит, что прокси на `/members/*` реально работает (тест через `curl --resolve`, без реального DNS-переключения).
- Ссылка «Личный кабинет» в шапке/подвале сайта (`https://dymova-english.ru/members/login`) не меняется — правим только серверную маршрутизацию.
- Спека: `docs/superpowers/specs/2026-07-28-tilda-members-proxy-design.md` — при расхождении плана и спеки приоритет у спеки, план должен быть скорректирован.

---

### Task 1: Заменить блок `/members/*` в Caddyfile на редирект (было — reverse_proxy, отклонено)

**Files:**
- Modify: `bot/deploy/Caddyfile` (блок `dymova-english.ru, www.dymova-english.ru`)

**Interfaces:**
- Consumes: DNS-имя `tilda-members.dymova-english.ru` (создаётся владельцем в Task 2; на этом шаге просто ссылаемся на имя).
- Produces: рабочий Caddy-конфиг с `handle /members/* { redir ... }`, который Task 3 деплоит на сервер.

- [x] **Step 1-4 выполнены** (редактирование, коммит `bot/deploy/Caddyfile`, PR, деплой и валидация на сервере) — итоговый блок:

```caddy
dymova-english.ru, www.dymova-english.ru {
    handle /members/* {
        redir https://tilda-members.dymova-english.ru{uri} 302
    }

    root * /srv/foxinburg-site
    try_files {path} {path}/index.html
    file_server
}
```

Полный код с комментариями — см. текущее содержимое `bot/deploy/Caddyfile` в репозитории (обновлено этим же изменением).

---

### Task 2: Владелец создаёт DNS-запись и алиас домена в Tilda

**Files:** нет (действия вне репозитория)

**Interfaces:**
- Consumes: текущий IP Tilda для проекта — `176.57.67.189`.
- Produces: рабочий целевой домен для редиректа, на который Task 3 будет проверять реальный ответ Tilda.

- [ ] **Step 1: DNS-запись** — попросить владельца добавить A-запись `tilda-members.dymova-english.ru → 176.57.67.189` в кабинете reg.ru (аналогично уже сделанной ранее `tilda-origin.dymova-english.ru` — та запись теперь не используется Caddy и может быть позже удалена владельцем, не блокирует эту задачу).

- [ ] **Step 2: Алиас в Tilda** — попросить владельца в личном кабинете Tilda (настройки домена проекта 2053071) добавить `tilda-members.dymova-english.ru` как дополнительный домен/алиас — без этого Tilda не будет знать, каким сайтом отвечать на этот hostname, даже если DNS уже верный.

- [ ] **Step 3: Проверить оба условия одним запросом**

```bash
dig +short tilda-members.dymova-english.ru A @ns1.reg.ru
curl -sS -o /dev/null -w "%{http_code}\n" https://tilda-members.dymova-english.ru/members/login
```

Expected: `176.57.67.189`, затем `200`. Если DNS уже верный, но curl не `200` (например `404`/`421`/редирект на другой домен) — это значит DNS готов, а алиас в Tilda ещё не добавлен (Step 2 не выполнен); не переходить к Task 3, пока оба не подтверждены.

---

### Task 3: Проверить редирект ДО переключения основного DNS

**Files:** нет новых.

**Interfaces:**
- Consumes: подтверждённый рабочий `tilda-members.dymova-english.ru` из Task 2, задеплоенный Caddyfile из Task 1.
- Produces: подтверждение, что редирект работает и ведёт на реальную страницу Tilda Members — Task 4 полагается на этот результат перед переключением боевого DNS.

- [ ] **Step 1: Проверить, что существующие сайты не пострадали**

```bash
curl -sS -o /dev/null -w "%{http_code}\n" https://bot.dymova-english.ru/health
curl -sS -o /dev/null -w "%{http_code}\n" https://new.dymova-english.ru/
```

Expected: `200` и `200`.

- [ ] **Step 2: Проверить редирект `/members/*`, подставив IP сервера напрямую (DNS основного домена ещё не переключён)**

```bash
curl -sS -i --resolve dymova-english.ru:443:89.169.132.104 https://dymova-english.ru/members/login | grep -iE "^HTTP|^location"
```

Expected: `HTTP/2 302` и `location: https://tilda-members.dymova-english.ru/members/login`.

- [ ] **Step 3: Пройти по редиректу и убедиться, что за ним реальная страница Tilda Members**

```bash
curl -sS --resolve dymova-english.ru:443:89.169.132.104 -L https://dymova-english.ru/members/login | grep -o 'data-tilda-project-id="[0-9]*"'
```

Expected: `data-tilda-project-id="2053071"`.

- [ ] **Step 4: Проверить, что обычная статика на apex-домене (тот же хост) тоже не пострадала**

```bash
curl -sS --resolve dymova-english.ru:443:89.169.132.104 -o /dev/null -w "%{http_code}\n" https://dymova-english.ru/
```

Expected: `200`.

Если Step 2 или 3 не дали ожидаемого результата — **не переходить к Task 4**. Разобрать через systematic-debugging (проверить `docker logs bot-caddy-1`, перепроверить Task 2 через прямой curl на `tilda-members.dymova-english.ru`).

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
curl -sS -i https://dymova-english.ru/members/login | grep -iE "^HTTP|^location"
curl -sS -L https://dymova-english.ru/members/login | grep -o 'data-tilda-project-id="[0-9]*"'
curl -sS -o /dev/null -w "%{http_code}\n" -L https://dymova-english.ru/members/register
```

Expected: `200`, `200`, `HTTP/2 302` + `location: https://tilda-members.dymova-english.ru/members/login`, `data-tilda-project-id="2053071"`, `200`.

- [ ] **Step 4: Живой тест в браузере (ручной, не автоматизируемый)**

Открыть `https://dymova-english.ru/members/login` в обычном браузере, убедиться что адрес меняется на `tilda-members.dymova-english.ru` с реальной формой входа Tilda (не ошибкой), залогиниться существующим тестовым/реальным аккаунтом кабинета, убедиться что вход и последующая навигация внутри кабинета работают, куки принимаются.

Report the result to the user directly — this step cannot be verified by an autonomous agent.

---

### Task 5: Зафиксировать сессию в DEVLOG.md

**Files:**
- Modify: `DEVLOG.md` (добавить новую секцию `### Сессия 33 (Claude Code) — ...` в конец файла, по образцу секций 29-32).

**Interfaces:**
- Consumes: результаты Task 1-4 (что реально было сделано и проверено, включая отклонённый первый вариант).
- Produces: запись в истории проекта.

- [ ] **Step 1: Добавить секцию в конец DEVLOG.md**

Добавить в конец файла (после последней секции `### Сессия 32 ...`):

```markdown

### Сессия 33 (Claude Code) — личный кабинет Tilda сохранён через редирект, миграция с Tilda завершена по-настоящему

**Дата:** 2026-07-28
**Спека:** `docs/superpowers/specs/2026-07-28-tilda-members-proxy-design.md`
**План:** `docs/superpowers/plans/2026-07-28-tilda-members-proxy.md`

**Запрос владельца:** личный кабинет (`/members/login`) сломался после переноса домена на свой сервер в Сессии 30 — Tilda Members не существует в статической сборке. Владелец временно откатил DNS на Tilda, попросил переехать с Tilda полностью, но оставить личный кабинет рабочим через Tilda.

**Первая попытка (отклонена):** `handle_path /members/* { reverse_proxy tilda-origin.dymova-english.ru }` — Caddy сам ходил на Tilda. При проверке `curl --resolve` на IP сервера — `HTTP 425 D'oh!` от DDoS-Guard, стабильно воспроизводится, тогда как контрольный запрос с обычного IP в то же время проходил чисто (`200`). Вывод: DDoS-Guard блокирует запросы с IP датацентра (Yandex Cloud) независимо от реального посетителя за прокси — сломало бы кабинет для всех одинаково. Поймано на этапе верификации до переключения боевого DNS, реальные посетители не пострадали.

**Сделано (финальная версия):**
- `bot/deploy/Caddyfile` — блок `dymova-english.ru, www.dymova-english.ru`: `/members/*` теперь `handle { redir https://tilda-members.dymova-english.ru{uri} 302 }` — браузер посетителя редиректится и подключается к Tilda напрямую, своим IP.
- DNS: добавлена `tilda-members.dymova-english.ru → 176.57.67.189`; этот поддомен добавлен владельцем как алиас домена в настройках проекта 2053071 в кабинете Tilda. Основные A-записи `dymova-english.ru`/`www.` возвращены на `89.169.132.104`. (Старая запись `tilda-origin.dymova-english.ru` от первой попытки — больше не используется, можно удалить.)
- Проверено: редирект протестирован через `curl --resolve` до переключения основного DNS (302 → реальная страница Tilda Members, `project-id=2053071`), затем — на реальном трафике после переключения.

**Деплой:** прод. `dymova-english.ru`/`www.` — снова отдаются с собственного сервера (`89.169.132.104`), `/members/*` редиректит на `tilda-members.dymova-english.ru` (Tilda напрямую).
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
