# Живые данные мини-приложения: педагоги с сайта + свежесть расписания

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Список педагогов в мини-приложении бота обновляется сам с сайта школы (вместо ручного `data.yaml`, где 10 человек вместо реальных 17), и школа узнаёт, если синхронизация расписания с BigBen надолго замолчала.

**Architecture:** Новый модуль `app/knowledge/team_sync.py` скачивает и парсит блок команды `#fxb-team` с `https://dymova-english.ru/`, кэширует результат в памяти со снимком на диск (переживает рестарт), с фолбэком на `data.yaml`. Фоновый цикл в `scheduler.py` обновляет его раз в час. `/api/miniapp/info` отдаёт этот список вместо статического yaml. Педагогам достраивается список групп, которые они ведут (переиспользует существующие `bot_bridge.active_groups()` и `booking.group_teacher()`). Расписание уже синхронизируется каждые 15 минут и уже показывает «обновлено N назад» в виджете (`app/widget/fxb-schedule.js`) — этого не трогаем; добавляем только предупреждение администратору, если данные не обновлялись дольше часа.

**Tech Stack:** Python 3.11, FastAPI, `httpx` (уже используется в `site_sync.py`), `re` (без новых зависимостей — паттерн уже принят в `site_sync.py`), pytest.

**Spec:** `docs/superpowers/specs/2026-09-24-bot-miniapp-upgrade-design.md`, раздел «Подпроект 1».

## Разведка, зафиксированная для этого плана

Ниже — факты, проверенные вживую на 2026-09-25 (не додумывать, использовать как есть):

- **Источник команды** — `https://dymova-english.ru/` (не `prototype/block_team.html`, это черновик в репозитории; на сайте реальная разметка отличается). Блок начинается `<div id="fxb-team">` и заканчивается перед следующим `<div id="fxb-`, на проде это `<div id="fxb-lang">` (блок «Другие языки», у него **другая** разметка карточек — `fxb-teacher-photo`, не `fxb-photo` — если не ограничить парсинг разделом команды, туда попадёт мусор).
- На проде сейчас в `#fxb-team` **17** карточек `<article class="fxb-card">` (в мини-приложении сейчас 10 — устарело).
- Разметка одной карточки:
  ```html
  <article class="fxb-card">
    <div class="fxb-photo" style="background-image:url(/team-media/salyahova.webp)"></div>
    <div class="fxb-body">
      <span class="fxb-role fxb-r-teacher">Педагог</span>
      <h3>Саляхова Алина</h3>
      <p>Педагог английского и немецкого языков</p>
      <div class="fxb-btns">
        <button class="fxb-vbtn" type="button" data-video="/team-media/salyahova.mp4">...Видеовизитка</button>
        <button class="fxb-vbtn fxb-vbtn-2" type="button" data-video="/team-media/salyahova_lesson.mp4">...Фрагмент урока</button>
      </div>
    </div>
  </article>
  ```
  - Роль не всегда несёт модификатор класса: три карточки — `<span class="fxb-role">Педагог немецкого языка</span>` без `fxb-r-teacher`. Классифицировать «это педагог» нужно по тексту роли (подстрока «педагог», регистронезависимо), а не по CSS-классу.
  - Фото и видео — **относительные** пути (`/team-media/...`), нужно склеивать с origin.
  - Блок `<div class="fxb-btns">` с кнопками видео есть не у всех (у руководителей/администраторов его нет). Второй кнопки (фрагмент урока) тоже может не быть, либо `data-video=""` (пусто).
- **Расписание уже готово, не трогать:**
  - `app/platform/sync.py` синхронизирует BigBen каждые `BIGBEN_SYNC_INTERVAL_MIN` (15 мин по умолчанию) в `_incremental_loop()`; проверено на проде — последний успешный прогон свежий, `status='ok'`.
  - `app/platform/public_api.py:142` (`GET /api/platform/schedule`) уже отдаёт `freshness: {groups_synced_at, lessons_synced_at}` (комментарий в шапке файла: «Ответы всегда содержат свежесть данных»).
  - `app/widget/fxb-schedule.js:296-297` уже рендерит `Данные о местах обновлены {fmtAgo(...)}` из `state.freshness.groups_synced_at` — этот же скрипт подключён и в `bot/app/tgapp/index.html` (`<div id="fxb-schedule">` + `<script src="/widget/fxb-schedule.js?...">`), значит индикатор свежести уже виден и в мини-приложении бота.
  - Единственное, чего не хватает: если BigBen надолго недоступен (несколько часов подряд ошибок), никто не узнает, пока клиент не пожалуется. Это и есть весь остающийся объём работы по расписанию.
- **Сопоставление педагог↔группы уже есть, переиспользуем:**
  - `app/platform/bot_bridge.active_groups(filial_id=None) -> list[dict]` — группы с уроками в ближайшие 60 дней (поле `caption`, `id`, `filial_id`, `filial_caption`, ...).
  - `app/platform/booking.group_teacher(group_id: int, caption: str) -> str` — педагог группы («источник истины» → `bb_group_meta` → соответствие по конфигу → фамилия в названии). Возвращает **«Имя Фамилия»** (короткое имя, фамилия последним словом — см. `short_teacher_name`), либо `""`.
  - Имена на сайте — **«Фамилия Имя»** (фамилия первым словом). Сопоставлять по фамилии: `site_name.split()[0]` против `teacher_name.split()[-1]`, регистронезависимо.
- **Постоянный путь для данных** — конвенция репозитория: `DB_PATH: str = "./data/bot.db"` (относительно рабочей директории `/app` в контейнере, примонтирован том `${BOT_DATA_DIR:-./data}:/app/data`). Снимок команды кладём туда же: `./data/team_snapshot.json`.
- **Поля мини-приложения (не менять имена, их читает фронт):** `app/tgapp/app.js` `renderTeam()` (строка ~1410) использует `person.name`, `person.photo`, `person.role`, `person.about`, `person.video_intro`, `person.video_lesson`.
- **`/api/miniapp/info`** — `app/main.py:1669`: `"team": kb.raw.get("team", [])`. Меняем на синхронизированный список. `main.py` уже импортирует `scheduler`, `watchdog`; нужно добавить `from app.knowledge import team_sync`.

## Global Constraints

- Стиль комментариев — по-русски, объясняют «почему», как в остальном коде (`site_sync.py`, `booking.py`).
- Никаких новых зависимостей (без `beautifulsoup4`/`lxml`) — парсинг регулярными выражениями, как в `app/knowledge/site_sync.py`.
- Сбой сети/парсинга или пустой результат синхронизации → остаётся последний удачный снимок; при отсутствии снимка (первый холодный старт без сети) → фолбэк на `get_kb().raw.get("team", [])` из `data.yaml`.
- Тесты — из `bot/`: `cd /Users/grigory/Dymova-english/bot && .venv/bin/python -m pytest ...`.
- Коммиты — Conventional Commits, `feat(bot): …`, трейлер `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.
- Владелец разрешил мержить и деплоить без запроса подтверждения.
- Перед деплоем на прод-сервере обязательно проверить `git status --short` в рабочей копии: если там снова появятся незакоммиченные правки (как было на сессии деплоя подпроекта 0) — не откатывать и не удалять их самостоятельно, остановиться и сообщить владельцу.

---

### Task 1: Парсер блока команды с сайта

**Files:**
- Create: `bot/app/knowledge/team_sync.py`
- Test: `bot/tests/test_team_sync.py`

**Interfaces:**
- Produces:
  - `team_sync.parse_team_html(html: str, origin: str) -> list[dict]` — чистая функция, без сети. Каждый элемент: `{"name": str, "role": str, "about": str, "photo": str, "video_intro": str, "video_lesson": str}`. Пустые/битые карточки без имени пропускаются. `photo`/`video_*` — абсолютные URL (склейка с `origin`) либо `""`.
  - `team_sync._is_teacher(role: str) -> bool` — подстрока «педагог» в role, регистронезависимо.

- [ ] **Step 1: Write the failing test** — `bot/tests/test_team_sync.py`

```python
"""Парсер блока команды с сайта dymova-english.ru."""
from app.knowledge import team_sync

# Вырезка реальной разметки #fxb-team (сайт, 2026-09-25), с намеренно
# добавленным соседним блоком #fxb-lang — парсер должен остановиться
# до него и не превратить его карточки в мусорных «педагогов».
FIXTURE_HTML = """
<div id="fxb-team">
  <div class="fxb-section">
    <div class="fxb-grid">
      <article class="fxb-card">
        <div class="fxb-photo" style="background-image:url(/team-media/salyahova.webp)"></div>
        <div class="fxb-body">
          <span class="fxb-role fxb-r-teacher">Педагог</span>
          <h3>Саляхова Алина</h3>
          <p>Педагог английского и немецкого языков</p>
          <div class="fxb-btns">
            <button class="fxb-vbtn" type="button" data-video="/team-media/salyahova.mp4">Видеовизитка</button>
            <button class="fxb-vbtn fxb-vbtn-2" type="button" data-video="/team-media/salyahova_lesson.mp4">Фрагмент урока</button>
          </div>
        </div>
      </article>

      <article class="fxb-card">
        <div class="fxb-photo" style="background-image:url(/team-media/anokhin.webp)"></div>
        <div class="fxb-body">
          <span class="fxb-role fxb-r-teacher">Педагог</span>
          <h3>Анохин Роман</h3>
          <p>Педагог английского языка</p>
          <div class="fxb-btns">
            <button class="fxb-vbtn" type="button" data-video="/team-media/anokhin.mp4">Видеовизитка</button>
            <button class="fxb-vbtn fxb-vbtn-2" type="button" data-video="">Фрагмент урока</button>
          </div>
        </div>
      </article>

      <article class="fxb-card">
        <div class="fxb-photo" style="background-image:url(/team-media/sporyhina.webp)"></div>
        <div class="fxb-body">
          <span class="fxb-role">Педагог испанского языка</span>
          <h3>Спорыхина Анастасия</h3>
          <p>Педагог испанского языка</p>
        </div>
      </article>

      <article class="fxb-card">
        <div class="fxb-body">
          <span class="fxb-role fxb-r-admin">Администратор</span>
          <h3>Джанузакова Салтанат</h3>
          <p>Поможет с расписанием и записью</p>
        </div>
      </article>
    </div>
  </div>
</div>

<div id="fxb-lang">
  <div class="fxb-grid">
    <article class="fxb-card fxb-de">
      <div class="fxb-body">
        <div class="fxb-teacher">
          <div class="fxb-teacher-photo" style="background:linear-gradient(135deg,#7b4fc0,#662d92)"></div>
          <div>
            <h3>Саляхова Алина</h3>
            <span class="fxb-role">Педагог немецкого языка</span>
          </div>
        </div>
      </div>
    </article>
  </div>
</div>
"""

ORIGIN = "https://dymova-english.ru"


def test_parses_all_team_cards_only():
    people = team_sync.parse_team_html(FIXTURE_HTML, ORIGIN)
    assert [p["name"] for p in people] == [
        "Саляхова Алина", "Анохин Роман", "Спорыхина Анастасия", "Джанузакова Салтанат",
    ]


def test_photo_and_video_urls_are_absolute():
    people = team_sync.parse_team_html(FIXTURE_HTML, ORIGIN)
    salyahova = people[0]
    assert salyahova["photo"] == "https://dymova-english.ru/team-media/salyahova.webp"
    assert salyahova["video_intro"] == "https://dymova-english.ru/team-media/salyahova.mp4"
    assert salyahova["video_lesson"] == "https://dymova-english.ru/team-media/salyahova_lesson.mp4"


def test_missing_second_video_is_empty_not_crash():
    anokhin = team_sync.parse_team_html(FIXTURE_HTML, ORIGIN)[1]
    assert anokhin["video_intro"] == "https://dymova-english.ru/team-media/anokhin.mp4"
    assert anokhin["video_lesson"] == ""


def test_card_without_photo_or_video_block_survives():
    admin = team_sync.parse_team_html(FIXTURE_HTML, ORIGIN)[3]
    assert admin["name"] == "Джанузакова Салтанат"
    assert admin["role"] == "Администратор"
    assert admin["photo"] == ""
    assert admin["video_intro"] == "" and admin["video_lesson"] == ""


def test_role_without_modifier_class_still_read():
    sporyhina = team_sync.parse_team_html(FIXTURE_HTML, ORIGIN)[2]
    assert sporyhina["role"] == "Педагог испанского языка"
    assert sporyhina["about"] == "Педагог испанского языка"


def test_lang_block_cards_never_leak_into_team():
    people = team_sync.parse_team_html(FIXTURE_HTML, ORIGIN)
    # #fxb-lang не должен дать пятого человека с role="Педагог немецкого языка"
    # без about/фото — это была бы карточка-мусор поверх настоящей Саляховой.
    assert len(people) == 4


def test_is_teacher_matches_role_variants():
    assert team_sync._is_teacher("Педагог") is True
    assert team_sync._is_teacher("Педагог немецкого языка") is True
    assert team_sync._is_teacher("Администратор") is False
    assert team_sync._is_teacher("Руководитель школы") is False


def test_empty_html_returns_empty_list():
    assert team_sync.parse_team_html("<html></html>", ORIGIN) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/grigory/Dymova-english/bot && .venv/bin/python -m pytest tests/test_team_sync.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.knowledge.team_sync'`

- [ ] **Step 3: Write `bot/app/knowledge/team_sync.py`**

```python
"""Живые данные о команде школы: скачиваем и парсим блок «Команда» с сайта.

Раньше список педагогов в мини-приложении жил только в data.yaml и правился
руками — на сайте уже 17 человек с актуальными фото, а в приложении
оставалось 10 устаревших. Источник истины теперь один: сайт. Ошибка сети
или парсинга не должна оставить мини-приложение без команды — остаётся
последний удачный снимок, а если снимка ещё не было (холодный старт без
сети) — data.yaml как фолбэк.
"""
from __future__ import annotations

import html as html_mod
import json
import logging
import re
from pathlib import Path

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Раздел команды на сайте — от своего id до следующего соседнего блока
# `<div id="fxb-...">`. Ограничиваться нужно строго: сразу после команды
# идёт блок «Другие языки» с ДРУГОЙ разметкой карточек (fxb-teacher-photo,
# не fxb-photo) — без границы туда попадёт мусор поверх настоящих карточек.
_TEAM_BLOCK_RE = re.compile(r'<div id="fxb-team">(.*?)<div id="fxb-', re.DOTALL)
_CARD_RE = re.compile(r'<article class="fxb-card">(.*?)</article>', re.DOTALL)
_PHOTO_RE = re.compile(r'class="fxb-photo"\s+style="background-image:url\(([^)]*)\)"')
_ROLE_RE = re.compile(r'<span class="fxb-role[^"]*">([^<]*)</span>')
_NAME_RE = re.compile(r'<h3>([^<]*)</h3>')
_ABOUT_RE = re.compile(r'</h3>\s*<p>([^<]*)</p>')
# Кнопка видео: класс fxb-vbtn-2 отличает «фрагмент урока» от «видеовизитки».
_VIDEO_RE = re.compile(r'class="fxb-vbtn( fxb-vbtn-2)?"[^>]*data-video="([^"]*)"')


def _clean(text: str) -> str:
    return html_mod.unescape(text or "").strip()


def _abs_url(path: str, origin: str) -> str:
    path = (path or "").strip()
    if not path:
        return ""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return origin.rstrip("/") + "/" + path.lstrip("/")


def _is_teacher(role: str) -> bool:
    """Педагог — по тексту роли, не по CSS-классу: три карточки на сайте
    несут роль «Педагог немецкого языка» без модификатора fxb-r-teacher."""
    return "педагог" in (role or "").lower()


def _parse_card(card_html: str, origin: str) -> dict | None:
    name_m = _NAME_RE.search(card_html)
    if not name_m:
        return None
    name = _clean(name_m.group(1))
    if not name:
        return None
    role_m = _ROLE_RE.search(card_html)
    role = _clean(role_m.group(1)) if role_m else ""
    about_m = _ABOUT_RE.search(card_html)
    about = _clean(about_m.group(1)) if about_m else ""
    photo_m = _PHOTO_RE.search(card_html)
    photo = _abs_url(photo_m.group(1) if photo_m else "", origin)
    video_intro = ""
    video_lesson = ""
    for is_second, url in _VIDEO_RE.findall(card_html):
        resolved = _abs_url(url, origin)
        if is_second:
            video_lesson = resolved
        else:
            video_intro = resolved
    return {
        "name": name,
        "role": role,
        "about": about,
        "photo": photo,
        "video_intro": video_intro,
        "video_lesson": video_lesson,
    }


def parse_team_html(html: str, origin: str) -> list[dict]:
    """Список педагогов/сотрудников из HTML страницы. Пустой список — блок
    команды не найден или в нём нет карточек с именем (не считается ошибкой
    парсинга снаружи — вызывающий код сам решает, что делать с пустым)."""
    block_m = _TEAM_BLOCK_RE.search(html)
    if not block_m:
        return []
    block = block_m.group(1)
    people: list[dict] = []
    for card_m in _CARD_RE.finditer(block):
        person = _parse_card(card_m.group(1), origin)
        if person:
            people.append(person)
    return people
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/grigory/Dymova-english/bot && .venv/bin/python -m pytest tests/test_team_sync.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/grigory/Dymova-english
git add bot/app/knowledge/team_sync.py bot/tests/test_team_sync.py
git commit -m "feat(bot): парсер блока команды с сайта dymova-english.ru

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: Снимок на диск, фолбэк на data.yaml, фоновая синхронизация раз в час

**Files:**
- Modify: `bot/app/knowledge/team_sync.py`
- Modify: `bot/app/config.py`
- Modify: `bot/app/scheduler.py`
- Modify: `bot/app/main.py:1669` (поле `"team"` в `/api/miniapp/info`)
- Test: `bot/tests/test_team_sync.py` (дополнить)

**Interfaces:**
- Consumes: `team_sync.parse_team_html` (Task 1), `app.knowledge.kb.get_kb()`
- Produces:
  - `team_sync.get_team() -> list[dict]` — текущий список: снимок в памяти → снимок на диске → `data.yaml` в этом порядке приоритета.
  - `team_sync.sync_once() -> int` — async, скачивает и обновляет снимок; возвращает число людей (0 при неудаче, снимок не трогается).
  - Настройки `settings.TEAM_SYNC_ENABLED: bool = True`, `settings.TEAM_SYNC_URL: str = "https://dymova-english.ru"`, `settings.TEAM_SYNC_INTERVAL_MIN: int = 60`, `settings.TEAM_SNAPSHOT_PATH: str = "./data/team_snapshot.json"`.

- [ ] **Step 1: Write the failing test** — дополнить `bot/tests/test_team_sync.py`:

```python
import json

import httpx
import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def _reset_team_cache():
    team_sync._TEAM_CACHE = None
    yield
    team_sync._TEAM_CACHE = None


def test_get_team_falls_back_to_yaml_when_nothing_synced_yet(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "TEAM_SNAPSHOT_PATH", str(tmp_path / "missing.json"))
    people = team_sync.get_team()
    # data.yaml реально существует в репозитории и содержит команду —
    # значит фолбэк не пустой.
    assert len(people) > 0
    assert all("name" in p for p in people)


def test_get_team_reads_snapshot_from_disk_after_restart(tmp_path, monkeypatch):
    snapshot = tmp_path / "team_snapshot.json"
    snapshot.write_text(json.dumps([{"name": "Тест Тестов", "role": "Педагог",
                                     "about": "", "photo": "", "video_intro": "",
                                     "video_lesson": ""}]), encoding="utf-8")
    monkeypatch.setattr(settings, "TEAM_SNAPSHOT_PATH", str(snapshot))
    people = team_sync.get_team()
    assert people == [{"name": "Тест Тестов", "role": "Педагог", "about": "",
                       "photo": "", "video_intro": "", "video_lesson": ""}]


@pytest.mark.asyncio
async def test_sync_once_writes_snapshot_and_updates_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "TEAM_SYNC_URL", "https://dymova-english.ru")
    monkeypatch.setattr(settings, "TEAM_SNAPSHOT_PATH", str(tmp_path / "team_snapshot.json"))

    async def fake_get(self, url, **kwargs):
        return httpx.Response(200, text=FIXTURE_HTML, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    count = await team_sync.sync_once()
    assert count == 4
    assert json.loads((tmp_path / "team_snapshot.json").read_text(encoding="utf-8"))
    assert team_sync.get_team()[0]["name"] == "Саляхова Алина"


@pytest.mark.asyncio
async def test_sync_once_network_failure_keeps_previous_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "TEAM_SNAPSHOT_PATH", str(tmp_path / "team_snapshot.json"))
    team_sync._TEAM_CACHE = [{"name": "Старые Данные", "role": "", "about": "",
                              "photo": "", "video_intro": "", "video_lesson": ""}]

    async def fake_get(self, url, **kwargs):
        raise httpx.ConnectError("сеть недоступна", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    count = await team_sync.sync_once()
    assert count == 0
    assert team_sync.get_team()[0]["name"] == "Старые Данные"


@pytest.mark.asyncio
async def test_sync_once_empty_parse_keeps_previous_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "TEAM_SNAPSHOT_PATH", str(tmp_path / "team_snapshot.json"))
    team_sync._TEAM_CACHE = [{"name": "Старые Данные", "role": "", "about": "",
                              "photo": "", "video_intro": "", "video_lesson": ""}]

    async def fake_get(self, url, **kwargs):
        return httpx.Response(200, text="<html>совсем не та страница</html>",
                              request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    count = await team_sync.sync_once()
    assert count == 0
    assert team_sync.get_team()[0]["name"] == "Старые Данные"
```

Импортировать `FIXTURE_HTML` из уже написанного в Task 1 блока теста в этом же файле (он уже в модуле `bot/tests/test_team_sync.py`) — переносить не нужно, всё в одном файле.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/grigory/Dymova-english/bot && .venv/bin/python -m pytest tests/test_team_sync.py -v`
Expected: FAIL — `AttributeError: module 'app.knowledge.team_sync' has no attribute 'get_team'` (и `pytest.mark.asyncio` должен уже работать в проекте — проверить по `tests/test_registration_invite.py`, где уже есть `@pytest.mark.asyncio`).

- [ ] **Step 3: Add settings to `bot/app/config.py`** (рядом с `SITE_SYNC_*`, тем же стилем):

```python
    # --- Живая синхронизация команды с сайта ---
    TEAM_SYNC_ENABLED: bool = True
    TEAM_SYNC_URL: str = "https://dymova-english.ru"
    TEAM_SYNC_INTERVAL_MIN: int = 60
    TEAM_SNAPSHOT_PATH: str = "./data/team_snapshot.json"
```

- [ ] **Step 4: Extend `bot/app/knowledge/team_sync.py`** — добавить после парсера:

```python
_TEAM_CACHE: list[dict] | None = None


def _snapshot_path() -> Path:
    return Path(settings.TEAM_SNAPSHOT_PATH)


def _load_snapshot() -> list[dict]:
    path = _snapshot_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        logger.warning("team_sync: снимок на диске повреждён — игнорирую")
        return []


def _save_snapshot(people: list[dict]) -> None:
    path = _snapshot_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(people, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        logger.warning("team_sync: не удалось сохранить снимок на диск", exc_info=True)


def _yaml_fallback() -> list[dict]:
    """Последняя линия обороны: список из data.yaml, если ни разу не
    удалось синхронизироваться и снимка на диске нет (холодный старт без
    сети)."""
    from app.knowledge.kb import get_kb

    return list(get_kb().raw.get("team", []))


def get_team() -> list[dict]:
    """Текущий список команды: память → снимок на диске → data.yaml."""
    global _TEAM_CACHE
    if _TEAM_CACHE is not None:
        return _TEAM_CACHE
    from_disk = _load_snapshot()
    if from_disk:
        _TEAM_CACHE = from_disk
        return _TEAM_CACHE
    return _yaml_fallback()


async def sync_once() -> int:
    """Скачивает и обновляет команду. Возвращает число людей (0 — сбой,
    прежний снимок не трогаем, мини-приложение не остаётся пустым)."""
    global _TEAM_CACHE
    url = settings.TEAM_SYNC_URL.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
    except Exception as exc:
        logger.warning("team_sync: не удалось скачать %s: %s", url, exc)
        return 0
    people = parse_team_html(resp.text, url)
    if not people:
        logger.warning("team_sync: на странице %s не нашлось карточек команды — оставляю прежние", url)
        return 0
    _TEAM_CACHE = people
    _save_snapshot(people)
    logger.info("team_sync: обновлено %s карточек команды", len(people))
    return len(people)
```

- [ ] **Step 5: Register the periodic loop in `bot/app/scheduler.py`** — рядом с `_site_sync_loop`:

```python
async def _team_sync_loop() -> None:
    from app.knowledge import team_sync
    while True:
        try:
            await team_sync.sync_once()
        except Exception:
            logger.exception("team_sync: ошибка синхронизации команды")
        await asyncio.sleep(max(5, settings.TEAM_SYNC_INTERVAL_MIN) * 60)
```

И в `start()`, рядом с блоком `SITE_SYNC_ENABLED`:

```python
    if settings.TEAM_SYNC_ENABLED:
        tasks.append(asyncio.create_task(_team_sync_loop()))
    else:
        logger.info("team_sync: синхронизация команды выключена (TEAM_SYNC_ENABLED=false)")
```

- [ ] **Step 6: Switch `/api/miniapp/info` in `bot/app/main.py`**

Добавить импорт рядом с другими `from app import ...` (~строка 30-52):
```python
from app.knowledge import team_sync
```

Заменить строку 1669:
```python
        "team": kb.raw.get("team", []),
```
на:
```python
        "team": team_sync.get_team(),
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd /Users/grigory/Dymova-english/bot && .venv/bin/python -m pytest tests/test_team_sync.py tests/test_cabinet.py tests/test_max_miniapp.py -v`
Expected: все PASS.

- [ ] **Step 8: Commit**

```bash
cd /Users/grigory/Dymova-english
git add bot/app/knowledge/team_sync.py bot/app/config.py bot/app/scheduler.py bot/app/main.py bot/tests/test_team_sync.py
git commit -m "feat(bot): фоновая синхронизация команды раз в час, снимок на диск, фолбэк на data.yaml

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Педагог → какие группы ведёт

**Files:**
- Modify: `bot/app/knowledge/team_sync.py`
- Modify: `bot/app/tgapp/app.js` (`renderTeam()`, ~строка 1410)
- Test: `bot/tests/test_team_sync.py` (дополнить)

**Interfaces:**
- Consumes: `app.platform.bot_bridge.active_groups() -> list[dict]` (поле `caption`), `app.platform.booking.group_teacher(group_id: int, caption: str) -> str` (возвращает «Имя Фамилия» или `""`)
- Produces: `team_sync.teaching_groups(site_name: str) -> list[str]` — подписи активных групп, которые ведёт человек. Поле `"teaching": list[str]` добавляется к каждому педагогу в `get_team()`/снимке.

- [ ] **Step 1: Write the failing test** — дополнить `bot/tests/test_team_sync.py`:

```python
from unittest.mock import patch


def test_teaching_groups_matches_by_surname():
    groups = [
        {"id": 1, "caption": "Английский 2 класс, вт/чт 17:00"},
        {"id": 2, "caption": "Английский 4 класс, пн/ср 18:00"},
    ]
    with patch("app.platform.bot_bridge.active_groups", return_value=groups), \
         patch("app.platform.booking.group_teacher", side_effect=["Алина Саляхова", "Юлия Дмитроченко"]):
        assert team_sync.teaching_groups("Саляхова Алина") == ["Английский 2 класс, вт/чт 17:00"]


def test_teaching_groups_empty_for_non_teacher_name():
    with patch("app.platform.bot_bridge.active_groups", return_value=[]):
        assert team_sync.teaching_groups("") == []


@pytest.mark.asyncio
async def test_sync_once_attaches_teaching_to_teachers_only(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "TEAM_SYNC_URL", "https://dymova-english.ru")
    monkeypatch.setattr(settings, "TEAM_SNAPSHOT_PATH", str(tmp_path / "team_snapshot.json"))

    async def fake_get(self, url, **kwargs):
        return httpx.Response(200, text=FIXTURE_HTML, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    with patch.object(team_sync, "teaching_groups", return_value=["Английский 2 класс"]) as mocked:
        await team_sync.sync_once()
        people = team_sync.get_team()
        salyahova = next(p for p in people if p["name"] == "Саляхова Алина")
        admin = next(p for p in people if p["name"] == "Джанузакова Салтанат")
        assert salyahova["teaching"] == ["Английский 2 класс"]
        assert admin["teaching"] == []
        # Для администратора teaching_groups вообще не должен вызываться —
        # незачем ходить в BigBen ради человека, который не ведёт группы.
        mocked.assert_called_once_with("Саляхова Алина")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/grigory/Dymova-english/bot && .venv/bin/python -m pytest tests/test_team_sync.py -v`
Expected: FAIL — `AttributeError: module 'app.knowledge.team_sync' has no attribute 'teaching_groups'`

- [ ] **Step 3: Add `teaching_groups` and wire it into `sync_once`** — в `bot/app/knowledge/team_sync.py`:

```python
def teaching_groups(site_name: str) -> list[str]:
    """Активные группы этого педагога. Сопоставление по фамилии: на сайте
    имя «Фамилия Имя», group_teacher() отдаёт «Имя Фамилия» — фамилия у
    неё последним словом."""
    from app.platform import bot_bridge, booking

    words = (site_name or "").split()
    if not words:
        return []
    surname = words[0].lower()
    out: list[str] = []
    for group in bot_bridge.active_groups():
        teacher = booking.group_teacher(group["id"], group.get("caption", ""))
        teacher_words = teacher.split()
        if teacher_words and teacher_words[-1].lower() == surname:
            out.append(group.get("caption", ""))
    return out
```

В `sync_once`, после строки `people = parse_team_html(resp.text, url)` и перед проверкой `if not people:`, добавить обогащение:

```python
    for person in people:
        person["teaching"] = teaching_groups(person["name"]) if _is_teacher(person["role"]) else []
```

- [ ] **Step 4: Show it in the mini-app** — `bot/app/tgapp/app.js`, в `renderTeam()` (~строка 1434, сразу после блока `person.about`):

```javascript
            (person.about ? '<p class="person__about">' + esc(person.about) + "</p>" : "") +
            (person.teaching && person.teaching.length
              ? '<p class="person__teaching">Ведёт: ' + esc(person.teaching.join(", ")) + "</p>"
              : "") +
```

(проверить точный существующий текст этой строки в файле перед правкой — вставлять после него, не заменять).

- [ ] **Step 5: Run tests**

Run: `cd /Users/grigory/Dymova-english/bot && .venv/bin/python -m pytest tests/test_team_sync.py -v && node --check app/tgapp/app.js`
Expected: все PASS, `node --check` без вывода.

- [ ] **Step 6: Commit**

```bash
cd /Users/grigory/Dymova-english
git add bot/app/knowledge/team_sync.py bot/app/tgapp/app.js bot/tests/test_team_sync.py
git commit -m "feat(bot): у педагогов в мини-приложении видно, какие группы они ведут

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: Предупреждение, если расписание давно не обновлялось

**Files:**
- Modify: `bot/app/platform/sync.py`
- Test: `bot/tests/test_platform_alerts.py` (дополнить; файл уже существует — прочитать перед правкой, чтобы совпасть по стилю и фикстурам)

**Interfaces:**
- Consumes: `app.platform.bb_store.freshness() -> dict` (уже есть: `{"lessons": {"count": int, "last_synced_at": str | None}, ...}`), `app.watchdog._alert(text: str) -> None` (уже есть, шлёт админам в MAX + Slack, логирует), `sync.run_all(mode: str) -> list[dict]` (уже есть)
- Produces: `sync.check_schedule_freshness(max_age_min: int | None = None) -> bool` — True, если расписание свежее. `sync.check_schedule_freshness_and_alert(max_age_min: int | None = None) -> bool` — при устаревании сперва пробует одну внеплановую `run_all("incremental")`, и только если данные остались несвежими и после неё — шлёт предупреждение (с cooldown, не при каждом вызове).

- [ ] **Step 1: Read existing test file and sync.py freshness/loop code first**

Run: `cd /Users/grigory/Dymova-english/bot && sed -n '1,40p' tests/test_platform_alerts.py && grep -n "_incremental_loop\|_last_success\|^async def\|^def " app/platform/sync.py`

Понять реальные сигнатуры `_last_success(kind)` и цикла `_incremental_loop`, прежде чем писать тест и код — они уже существуют (см. §«Разведка» выше), но нумерация строк могла сместиться.

- [ ] **Step 2: Write the failing test** — дополнить `bot/tests/test_platform_alerts.py`:

```python
from unittest.mock import AsyncMock, patch

from app.platform import sync as sync_module


def test_check_schedule_freshness_true_when_recent(monkeypatch):
    from datetime import datetime, timezone
    recent = datetime.now(timezone.utc).isoformat()
    with patch("app.platform.bb_store.freshness",
              return_value={"lessons": {"count": 10, "last_synced_at": recent},
                            "groups": {"count": 5, "last_synced_at": recent}}):
        assert sync_module.check_schedule_freshness(max_age_min=60) is True


def test_check_schedule_freshness_false_and_alerts_when_stale(monkeypatch):
    from datetime import datetime, timedelta, timezone
    stale = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    sync_module._last_stale_alert_at = 0.0
    with patch("app.platform.bb_store.freshness",
              return_value={"lessons": {"count": 10, "last_synced_at": stale},
                            "groups": {"count": 5, "last_synced_at": stale}}), \
         patch("app.platform.sync.run_all", new=AsyncMock()) as run_all, \
         patch("app.watchdog._alert", new=AsyncMock()) as alert:
        import asyncio
        result = asyncio.run(sync_module.check_schedule_freshness_and_alert(max_age_min=60))
        assert result is False
        # Внеплановая синхронизация пробуется ДО оповещения — раз данные
        # всё равно остались несвежими (bb_store.freshness замокан статично),
        # проверяем только сам факт попытки и что после неё пришло письмо.
        run_all.assert_called_once_with("incremental")
        alert.assert_called_once()
        assert "расписан" in alert.call_args.args[0].lower()


def test_check_schedule_freshness_no_data_at_all_counts_as_stale():
    with patch("app.platform.bb_store.freshness",
              return_value={"lessons": {"count": 0, "last_synced_at": None},
                            "groups": {"count": 0, "last_synced_at": None}}):
        assert sync_module.check_schedule_freshness(max_age_min=60) is False


def test_stale_alert_has_cooldown_no_double_alert(monkeypatch):
    from datetime import datetime, timedelta, timezone
    stale = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    sync_module._last_stale_alert_at = 0.0
    with patch("app.platform.bb_store.freshness",
              return_value={"lessons": {"count": 10, "last_synced_at": stale},
                            "groups": {"count": 5, "last_synced_at": stale}}), \
         patch("app.platform.sync.run_all", new=AsyncMock()), \
         patch("app.watchdog._alert", new=AsyncMock()) as alert:
        import asyncio
        asyncio.run(sync_module.check_schedule_freshness_and_alert(max_age_min=60))
        asyncio.run(sync_module.check_schedule_freshness_and_alert(max_age_min=60))
        assert alert.call_count == 1


def test_freshness_restored_after_unplanned_sync_skips_alert(monkeypatch):
    """Внеплановая run_all() иногда чинит дело сама — тогда предупреждение
    не нужно вовсе."""
    from datetime import datetime, timedelta, timezone
    stale = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    fresh = datetime.now(timezone.utc).isoformat()
    sync_module._last_stale_alert_at = 0.0
    responses = iter([
        {"lessons": {"count": 10, "last_synced_at": stale}, "groups": {"count": 5, "last_synced_at": stale}},
        {"lessons": {"count": 10, "last_synced_at": fresh}, "groups": {"count": 5, "last_synced_at": fresh}},
    ])
    with patch("app.platform.bb_store.freshness", side_effect=lambda: next(responses)), \
         patch("app.platform.sync.run_all", new=AsyncMock()) as run_all, \
         patch("app.watchdog._alert", new=AsyncMock()) as alert:
        import asyncio
        result = asyncio.run(sync_module.check_schedule_freshness_and_alert(max_age_min=60))
        assert result is True
        run_all.assert_called_once_with("incremental")
        alert.assert_not_called()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Users/grigory/Dymova-english/bot && .venv/bin/python -m pytest tests/test_platform_alerts.py -v`
Expected: FAIL — `AttributeError: module 'app.platform.sync' has no attribute 'check_schedule_freshness'`

- [ ] **Step 4: Implement in `bot/app/platform/sync.py`** — добавить рядом с `_last_success`/`run_all`. Файл уже импортирует `time` и `from datetime import datetime, timedelta, timezone` в шапке — новый код ниже использует их, повторно не импортировать:

```python
_STALE_ALERT_COOLDOWN_SEC = 3600  # не чаще раза в час, иначе спам при долгом сбое
_last_stale_alert_at: float = 0.0


def _minutes_since(iso_ts: str | None) -> float | None:
    if not iso_ts:
        return None
    try:
        ts = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - ts).total_seconds() / 60


def check_schedule_freshness(max_age_min: int | None = None) -> bool:
    """True — данные о группах и уроках свежие. Отсутствие данных вовсе
    (last_synced_at=None) тоже считается несвежим: значит синхронизация
    ещё ни разу не прошла успешно."""
    from app.platform import bb_store

    limit = max_age_min if max_age_min is not None else max(15, settings.BIGBEN_SYNC_INTERVAL_MIN) * 4
    fresh = bb_store.freshness()
    for kind in ("groups", "lessons"):
        age = _minutes_since(fresh.get(kind, {}).get("last_synced_at"))
        if age is None or age > limit:
            return False
    return True


async def check_schedule_freshness_and_alert(max_age_min: int | None = None) -> bool:
    """Как check_schedule_freshness, но при устаревании сначала пробует
    внеплановую синхронизацию прямо сейчас (а не ждёт следующего тика
    обычного цикла), и только если это не помогло — раз в
    _STALE_ALERT_COOLDOWN_SEC шлёт администраторам предупреждение. Иначе о
    сломанной синхронизации узнают только от жалобы клиента."""
    global _last_stale_alert_at
    if check_schedule_freshness(max_age_min):
        return True
    await run_all("incremental")
    if check_schedule_freshness(max_age_min):
        return True
    now = time.monotonic()
    if now - _last_stale_alert_at < _STALE_ALERT_COOLDOWN_SEC:
        return False
    _last_stale_alert_at = now
    from app import watchdog

    limit = max_age_min if max_age_min is not None else max(15, settings.BIGBEN_SYNC_INTERVAL_MIN) * 4
    await watchdog._alert(
        f"🚨 Расписание не обновлялось дольше {limit} мин, внеплановая "
        "синхронизация не помогла — BigBen мог стать недоступен. "
        "Проверьте /admin/insights и логи бота."
    )
    return False
```

- [ ] **Step 5: Wire into the existing incremental sync loop** — в `_incremental_loop()` (тот же файл) текущее тело цикла:

```python
    while True:
        await asyncio.sleep(max(1, settings.BIGBEN_SYNC_INTERVAL_MIN) * 60)
        try:
            full_every = max(30, settings.BIGBEN_FULL_SYNC_INTERVAL_MIN) * 60
            if time.monotonic() - last_full >= full_every:
                await run_all("full")
                last_full = time.monotonic()
            else:
                await run_all("incremental")
        except Exception:
            logger.exception("sync: ошибка цикла синхронизации")
```

Добавить проверку свежести сразу после блока `if/else` с `run_all`, всё ещё внутри того же `try` (чтобы сбой самой проверки не уронил цикл синхронизации):

```python
    while True:
        await asyncio.sleep(max(1, settings.BIGBEN_SYNC_INTERVAL_MIN) * 60)
        try:
            full_every = max(30, settings.BIGBEN_FULL_SYNC_INTERVAL_MIN) * 60
            if time.monotonic() - last_full >= full_every:
                await run_all("full")
                last_full = time.monotonic()
            else:
                await run_all("incremental")
            await check_schedule_freshness_and_alert()
        except Exception:
            logger.exception("sync: ошибка цикла синхронизации")
```

- [ ] **Step 6: Run tests**

Run: `cd /Users/grigory/Dymova-english/bot && .venv/bin/python -m pytest tests/test_platform_alerts.py tests/test_platform.py tests/test_platform_api.py -v`
Expected: все PASS.

- [ ] **Step 7: Commit**

```bash
cd /Users/grigory/Dymova-english
git add bot/app/platform/sync.py bot/tests/test_platform_alerts.py
git commit -m "feat(bot): предупреждение администраторам, если расписание BigBen не обновлялось больше часа

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 5: Полная проверка, ревью, деплой, живая проверка

**Files:**
- Modify: `DEVLOG.md`

- [ ] **Step 1: Full test suite**

Run: `cd /Users/grigory/Dymova-english/bot && .venv/bin/python -m pytest -q --ignore=tests/benchmark`
Expected: 0 failed. Чинить реальные регрессии по существу, не ослаблять проверки.

- [ ] **Step 2: Review** — `superpowers:requesting-code-review` по всему диффу задач 1-4 (base — коммит перед Task 1, head — текущий).

- [ ] **Step 3: Deploy**

```bash
cd /Users/grigory/Dymova-english && git push origin world-v2
```

На сервере — **сначала** проверить чистоту рабочей копии (см. Global Constraints), затем:
```bash
ssh yc-user@89.169.132.104 'cd /home/yc-user/Dymova-english && git status --short'
# если чисто:
ssh yc-user@89.169.132.104 'cd /home/yc-user/Dymova-english && git pull --ff-only origin world-v2'
ssh yc-user@89.169.132.104 'cd /home/yc-user/Dymova-english/bot && sudo docker compose up -d --build'
```

- [ ] **Step 4: Live check on prod**

```bash
curl -s https://bot.dymova-english.ru/health
ssh yc-user@89.169.132.104 'docker logs --since 3m bot-bot-1 2>&1 | grep -iE "error|traceback|exception"'
ssh yc-user@89.169.132.104 'docker exec bot-bot-1 python -c "
from app.knowledge import team_sync
import asyncio
n = asyncio.run(team_sync.sync_once())
print(\"synced:\", n)
people = team_sync.get_team()
print(\"total:\", len(people))
print(\"first:\", people[0][\"name\"], people[0][\"photo\"][:60])
"'
curl -s https://bot.dymova-english.ru/api/platform/schedule | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[\"freshness\"])"
```

Expected: `/health` ok; ноль ошибок в логах; `team_sync.sync_once()` вернёт число, близкое к реальному составу команды (17+); первая запись — реальный человек с абсолютным URL фото на `dymova-english.ru`; `freshness` в ответе расписания непустая.

- [ ] **Step 5: DEVLOG + commit**

Дописать в `DEVLOG.md` запись сессии по образцу предыдущих (дата, ветка, что сделано, как проверено, деплой, что проверить владельцу — открыть вкладку «Педагоги» в мини-приложении и увидеть актуальный список с фото и группами).

```bash
cd /Users/grigory/Dymova-english
git add DEVLOG.md
git commit -m "docs(bot): журнал — живые данные мини-приложения (педагоги с сайта, предупреждение о несвежем расписании)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
git push origin world-v2
```
