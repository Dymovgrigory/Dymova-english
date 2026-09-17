# Замок: звания, экономика и Мастерская облика — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** замкнуть петлю «позанимался → заработал монеты → купил облик замка → это видно», выдавая звания по пяти веткам от зданий.

**Architecture:** новый модуль `world-backend/app/castle/` поверх существующих `core.award` / `core.spend`; таблицы добавляются в общую `SCHEMA` в `app/world/db.py`. Каталог товаров и пороги званий живут в коде (их часто крутят по балансу), состояние игрока — в базе. Фронтенд рисует облик слоями поверх нынешней диорамы: свет времени суток, частицы погоды, знамя. Сезоны и украшения требуют нового арта и вынесены в отдельный план (этап 3).

**Tech Stack:** FastAPI + SQLite (`world-backend`), Next.js 16 + TypeScript strict + Tailwind (`world`), pytest, vitest, Playwright.

## Global Constraints

- Спека: `docs/superpowers/specs/2026-09-17-castle-meta-design.md`. Цифры экономики и пороги званий берутся из неё дословно.
- Стиль и арт: `docs/world/STYLE_LOCK.md`. Дизайн замка не менять; новые элементы — латунь/эмаль/пергамент из `world/src/app/globals.css`.
- Клиент ничего не решает: цена, доступность по званию и начисление — только на сервере.
- Любое списание и начисление монет идёт через `core.spend` / `core.award` с ключом идемпотентности — повтор запроса не должен списать дважды.
- TypeScript strict, `any` запрещён. Комментарии и тексты интерфейса — по-русски.
- Тесты: `cd world-backend && .venv/bin/python -m pytest -q`, `cd world && npm test`, `npx tsc --noEmit -p .`, `npx eslint`.
- Коммиты — Conventional Commits, каждый шаг «Commit» делает отдельный коммит.

---

### Task 1: Таблицы мета-игры

**Files:**
- Modify: `world-backend/app/world/db.py` (константа `SCHEMA`, в конец)
- Test: `world-backend/tests/test_castle_schema.py`

**Interfaces:**
- Consumes: `app.world.db.get_conn`, фикстура `learn_db` из `tests/conftest.py`
- Produces: таблицы `castle_appearance`, `castle_owned`, `titles`, `league_weeks`

- [ ] **Step 1: Write the failing test**

```python
# world-backend/tests/test_castle_schema.py
"""Таблицы мета-игры замка создаются вместе с остальной схемой."""
from __future__ import annotations

import pytest

from app.world.db import get_conn


@pytest.mark.parametrize("table", ["castle_appearance", "castle_owned", "titles", "league_weeks"])
def test_castle_tables_exist(learn_db, table):
    rows = get_conn().execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchall()
    assert len(rows) == 1


def test_owned_item_is_unique_per_player(learn_db):
    conn = get_conn()
    conn.execute("INSERT INTO players (external_key, display_name) VALUES ('kid-1','Маша')")
    pid = conn.execute("SELECT id FROM players WHERE external_key='kid-1'").fetchone()["id"]
    conn.execute("INSERT INTO castle_owned (player_id, item_id, source) VALUES (?,?,?)", (pid, "weather-snow", "shop"))
    conn.execute(
        "INSERT OR IGNORE INTO castle_owned (player_id, item_id, source) VALUES (?,?,?)", (pid, "weather-snow", "shop")
    )
    count = conn.execute("SELECT COUNT(*) AS c FROM castle_owned WHERE player_id=?", (pid,)).fetchone()["c"]
    assert count == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd world-backend && .venv/bin/python -m pytest tests/test_castle_schema.py -q`
Expected: FAIL — таблиц нет, `len(rows) == 0`.

- [ ] **Step 3: Add tables to SCHEMA**

В `world-backend/app/world/db.py`, в конец строки `SCHEMA` (перед закрывающими кавычками):

```sql
CREATE TABLE IF NOT EXISTS castle_appearance (
    player_id     INTEGER PRIMARY KEY REFERENCES players(id),
    season        TEXT,                       -- spring|summer|autumn|winter, NULL = по календарю
    time_of_day   TEXT,                       -- dawn|day|dusk|night, NULL = как за окном
    weather       TEXT,                       -- snow|rain|fireflies|fog|aurora|petals, NULL = без эффекта
    banner_color  TEXT NOT NULL DEFAULT 'plum',
    banner_emblem TEXT NOT NULL DEFAULT 'fox',
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS castle_owned (
    player_id   INTEGER NOT NULL REFERENCES players(id),
    item_id     TEXT NOT NULL,
    anchor      TEXT,                          -- точка на замке для украшений
    source      TEXT NOT NULL,                 -- shop|title|gift
    acquired_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (player_id, item_id)
);

CREATE TABLE IF NOT EXISTS titles (
    player_id  INTEGER NOT NULL REFERENCES players(id),
    track      TEXT NOT NULL,                  -- lexicon|yard|nest|glory|stickers
    level      INTEGER NOT NULL DEFAULT 0,
    awarded_at TEXT NOT NULL DEFAULT (datetime('now')),
    worn       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (player_id, track)
);

CREATE TABLE IF NOT EXISTS league_weeks (
    player_id     INTEGER NOT NULL REFERENCES players(id),
    week_start    TEXT NOT NULL,               -- понедельник недели, YYYY-MM-DD
    rank          INTEGER NOT NULL,
    weekly_xp     INTEGER NOT NULL,
    coins_awarded INTEGER NOT NULL DEFAULT 0,
    closed_at     TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (player_id, week_start)
);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd world-backend && .venv/bin/python -m pytest tests/test_castle_schema.py -q`
Expected: PASS (3 теста).

- [ ] **Step 5: Commit**

```bash
git add world-backend/app/world/db.py world-backend/tests/test_castle_schema.py
git commit -m "feat(castle): таблицы званий, облика и итогов недели"
```

---

### Task 2: Ветки званий и математика уровней

**Files:**
- Create: `world-backend/app/castle/__init__.py` (пустой)
- Create: `world-backend/app/castle/tracks.py`
- Test: `world-backend/tests/test_castle_tracks.py`

**Interfaces:**
- Produces: `TRACKS: dict[str, Track]`, `Track(id, title_ru, building, unit_ru, thresholds, level_titles)`, `level_for(track_id: str, value: int) -> int`, `level_reward(level: int) -> int`, `track_view(track_id: str, value: int) -> dict`

- [ ] **Step 1: Write the failing test**

```python
# world-backend/tests/test_castle_tracks.py
"""Пороги и уровни веток званий — чистая математика, без базы."""
from __future__ import annotations

import pytest

from app.castle import tracks


def test_five_tracks_with_five_levels_each():
    assert set(tracks.TRACKS) == {"lexicon", "yard", "nest", "glory", "stickers"}
    for track in tracks.TRACKS.values():
        assert len(track.thresholds) == 5
        assert len(track.level_titles) == 5
        assert list(track.thresholds) == sorted(track.thresholds)


@pytest.mark.parametrize(
    "value,expected",
    [(0, 0), (9, 0), (10, 1), (49, 1), (50, 2), (150, 3), (300, 4), (600, 5), (10_000, 5)],
)
def test_level_for_words(value, expected):
    assert tracks.level_for("lexicon", value) == expected


def test_level_reward_grows():
    assert [tracks.level_reward(level) for level in (1, 2, 3, 4, 5)] == [25, 50, 100, 200, 400]


def test_track_view_shows_next_goal():
    view = tracks.track_view("nest", 8)
    assert view["level"] == 2
    assert view["title_ru"] == tracks.TRACKS["nest"].level_titles[1]
    assert view["value"] == 8
    assert view["next_threshold"] == 21


def test_track_view_at_max_has_no_next_goal():
    view = tracks.track_view("stickers", 22)
    assert view["level"] == 5
    assert view["next_threshold"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd world-backend && .venv/bin/python -m pytest tests/test_castle_tracks.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.castle'`.

- [ ] **Step 3: Write the implementation**

```python
# world-backend/app/castle/__init__.py
```

```python
# world-backend/app/castle/tracks.py
"""Ветки званий: каждое здание замка растит свою.

Пороги и названия держим кодом, а не в базе: баланс правится часто, и миграция
на каждое изменение порога не нужна. Уровень 0 — звания ещё нет.
"""
from __future__ import annotations

from dataclasses import dataclass

LEVEL_REWARDS = (25, 50, 100, 200, 400)


@dataclass(frozen=True)
class Track:
    id: str
    title_ru: str
    building: str          # id здания на карте замка
    unit_ru: str           # что считаем, для подписи прогресса
    thresholds: tuple[int, int, int, int, int]
    level_titles: tuple[str, str, str, str, str]


TRACKS: dict[str, Track] = {
    "lexicon": Track(
        id="lexicon", title_ru="Словесник", building="lexicon", unit_ru="слов выучено",
        thresholds=(10, 50, 150, 300, 600),
        level_titles=("Собиратель слов", "Знаток слов", "Хранитель словаря", "Мастер слова", "Магистр словаря"),
    ),
    "yard": Track(
        id="yard", title_ru="Тренер", building="yard", unit_ru="тренировок",
        thresholds=(5, 20, 60, 150, 300),
        level_titles=("Новичок двора", "Боец двора", "Ветеран двора", "Мастер двора", "Легенда двора"),
    ),
    "nest": Track(
        id="nest", title_ru="Хранитель огня", building="nest", unit_ru="дней подряд",
        thresholds=(3, 7, 21, 60, 150),
        level_titles=("Искра", "Огонёк", "Костёр", "Маяк", "Вечное пламя"),
    ),
    "glory": Track(
        id="glory", title_ru="Чемпион", building="glory", unit_ru="недель в тройке",
        thresholds=(1, 3, 8, 20, 40),
        level_titles=("Призёр", "Финалист", "Чемпион недели", "Чемпион замка", "Легенда лиги"),
    ),
    "stickers": Track(
        id="stickers", title_ru="Собиратель", building="stickers", unit_ru="наклеек",
        thresholds=(3, 8, 14, 20, 22),
        level_titles=("Любитель наклеек", "Коллекционер", "Знаток альбома", "Хранитель альбома", "Полный альбом"),
    ),
}


def level_for(track_id: str, value: int) -> int:
    """Уровень 0..5 по достигнутому значению."""
    thresholds = TRACKS[track_id].thresholds
    return sum(1 for threshold in thresholds if value >= threshold)


def level_reward(level: int) -> int:
    """Монеты за взятый уровень."""
    return LEVEL_REWARDS[level - 1] if 1 <= level <= len(LEVEL_REWARDS) else 0


def track_view(track_id: str, value: int) -> dict:
    """Строка прогресса ветки для интерфейса."""
    track = TRACKS[track_id]
    level = level_for(track_id, value)
    return {
        "track": track.id,
        "track_title_ru": track.title_ru,
        "building": track.building,
        "unit_ru": track.unit_ru,
        "level": level,
        "title_ru": track.level_titles[level - 1] if level else None,
        "value": value,
        "next_threshold": track.thresholds[level] if level < len(track.thresholds) else None,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd world-backend && .venv/bin/python -m pytest tests/test_castle_tracks.py -q`
Expected: PASS (все параметры).

- [ ] **Step 5: Commit**

```bash
git add world-backend/app/castle world-backend/tests/test_castle_tracks.py
git commit -m "feat(castle): ветки званий и уровни"
```

---

### Task 3: Значения веток из базы

**Files:**
- Create: `world-backend/app/castle/counters.py`
- Test: `world-backend/tests/test_castle_counters.py`

**Interfaces:**
- Consumes: `app.world.db.get_conn`, `app.learning.progress.streak_days`, `app.learning.clock`
- Produces: `counters(player_id: int) -> dict[str, int]` — ключи `lexicon|yard|nest|glory|stickers`

- [ ] **Step 1: Write the failing test**

```python
# world-backend/tests/test_castle_counters.py
"""Значения веток берутся из уже существующих таблиц прогресса."""
from __future__ import annotations

from app.castle import counters
from app.world.db import get_conn


def _word(player_id: int, word: str, strength: int) -> None:
    get_conn().execute(
        "INSERT INTO word_stats (player_id, unit_id, word_en, strength) VALUES (?,?,?,?)",
        (player_id, "sp1.m1", word, strength),
    )


def test_counts_only_learned_words(learner):
    _, player_id = learner
    _word(player_id, "cat", 2)
    _word(player_id, "dog", 5)
    _word(player_id, "fish", 1)  # ещё не выучено
    assert counters.counters(player_id)["lexicon"] == 2


def test_counts_practice_sessions(learner):
    _, player_id = learner
    for n in range(3):
        get_conn().execute(
            "INSERT INTO coin_transactions (player_id, type, amount, source, idempotency_key)"
            " VALUES (?,?,?,?,?)",
            (player_id, "PRACTICE_REWARD", 3, "practice", f"practice:{n}"),
        )
    assert counters.counters(player_id)["yard"] == 3


def test_counts_top3_weeks_and_stickers(learner):
    _, player_id = learner
    get_conn().execute(
        "INSERT INTO league_weeks (player_id, week_start, rank, weekly_xp) VALUES (?,?,?,?)",
        (player_id, "2026-09-07", 2, 120),
    )
    get_conn().execute(
        "INSERT INTO league_weeks (player_id, week_start, rank, weekly_xp) VALUES (?,?,?,?)",
        (player_id, "2026-09-14", 7, 90),
    )
    get_conn().execute(
        "INSERT OR IGNORE INTO items (id, category, title_ru) VALUES ('sticker-family','collectibles','Семья')"
    )
    get_conn().execute(
        "INSERT INTO inventory (player_id, item_id, source) VALUES (?,?,?)", (player_id, "sticker-family", "lesson")
    )
    values = counters.counters(player_id)
    assert values["glory"] == 1
    assert values["stickers"] == 1


def test_streak_comes_from_learning_progress(learner):
    _, player_id = learner
    assert counters.counters(player_id)["nest"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd world-backend && .venv/bin/python -m pytest tests/test_castle_counters.py -q`
Expected: FAIL — нет модуля `app.castle.counters`.

- [ ] **Step 3: Write the implementation**

```python
# world-backend/app/castle/counters.py
"""Текущие значения веток званий.

Считаем из таблиц, которые уже ведёт движок учёбы, а не заводим свои счётчики:
один источник правды, и пересчёт остаётся верным даже после ручных правок базы.
"""
from __future__ import annotations

from app.learning import clock, progress
from app.world.db import get_conn

WORD_LEARNED_STRENGTH = 2  # шкала силы слова 0..5; 2 — слово пережило пару верных ответов


def _scalar(sql: str, params: tuple) -> int:
    row = get_conn().execute(sql, params).fetchone()
    return int(row["value"]) if row else 0


def counters(player_id: int) -> dict[str, int]:
    return {
        "lexicon": _scalar(
            "SELECT COUNT(*) AS value FROM word_stats WHERE player_id=? AND strength>=?",
            (player_id, WORD_LEARNED_STRENGTH),
        ),
        "yard": _scalar(
            # Считаем сами тренировки, а не выплаты: после дневного потолка монет нет,
            # но тренировка всё равно должна расти в ветку Тренера.
            "SELECT COUNT(*) AS value FROM learn_sessions"
            " WHERE player_id=? AND kind='practice' AND status='completed'",
            (player_id,),
        ),
        "nest": progress.streak_days(player_id, now=clock.now()),
        "glory": _scalar(
            "SELECT COUNT(*) AS value FROM league_weeks WHERE player_id=? AND rank<=3",
            (player_id,),
        ),
        "stickers": _scalar(
            "SELECT COUNT(*) AS value FROM inventory WHERE player_id=? AND item_id LIKE 'sticker-%'",
            (player_id,),
        ),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd world-backend && .venv/bin/python -m pytest tests/test_castle_counters.py -q`
Expected: PASS. Если `clock.now()` называется иначе — открыть `app/learning/clock.py` и взять имеющуюся функцию текущего момента, тест не менять.

- [ ] **Step 5: Commit**

```bash
git add world-backend/app/castle/counters.py world-backend/tests/test_castle_counters.py
git commit -m "feat(castle): значения веток званий из прогресса"
```

---

### Task 4: Выдача званий с монетами

**Files:**
- Create: `world-backend/app/castle/titles.py`
- Test: `world-backend/tests/test_castle_titles.py`

**Interfaces:**
- Consumes: `app.castle.counters.counters`, `app.castle.tracks`, `app.world.core.award`, `app.world.core.get_player`
- Produces: `sync(external_key: str) -> list[dict]` (список новых уровней: `{"track","level","title_ru","coins"}`), `state(player_id: int) -> list[dict]` (прогресс всех веток + `worn`), `wear(player_id: int, track_id: str) -> list[dict]`

- [ ] **Step 1: Write the failing test**

```python
# world-backend/tests/test_castle_titles.py
"""Звания выдаются один раз, вместе с монетами, и одно можно носить."""
from __future__ import annotations

import pytest

from app.castle import titles
from app.world import core
from app.world.db import get_conn
from app.world.core import Conflict


def _learn_words(player_id: int, count: int) -> None:
    for n in range(count):
        get_conn().execute(
            "INSERT INTO word_stats (player_id, unit_id, word_en, strength) VALUES (?,?,?,?)",
            (player_id, "sp1.m1", f"word{n}", 3),
        )


def test_sync_awards_level_and_coins_once(learner):
    key, player_id = learner
    coins_before = core.get_player(key)["coins"]
    _learn_words(player_id, 10)

    first = titles.sync(key)
    assert [item["track"] for item in first] == ["lexicon"]
    assert first[0]["level"] == 1
    assert first[0]["coins"] == 25
    assert core.get_player(key)["coins"] == coins_before + 25

    assert titles.sync(key) == []
    assert core.get_player(key)["coins"] == coins_before + 25


def test_sync_jumps_two_levels_and_pays_for_both(learner):
    key, player_id = learner
    coins_before = core.get_player(key)["coins"]
    _learn_words(player_id, 50)
    new = titles.sync(key)
    assert new[0]["level"] == 2
    assert new[0]["coins"] == 25 + 50
    assert core.get_player(key)["coins"] == coins_before + 75


def test_state_lists_all_tracks(learner):
    key, player_id = learner
    state = titles.state(player_id)
    assert [row["track"] for row in state] == ["lexicon", "yard", "nest", "glory", "stickers"]
    assert all(row["level"] == 0 for row in state)
    assert all(row["worn"] is False for row in state)


def test_wear_switches_single_title(learner):
    key, player_id = learner
    _learn_words(player_id, 10)
    titles.sync(key)
    state = titles.wear(player_id, "lexicon")
    assert [row["worn"] for row in state if row["track"] == "lexicon"] == [True]
    assert sum(1 for row in state if row["worn"]) == 1


def test_cannot_wear_title_without_level(learner):
    _, player_id = learner
    with pytest.raises(Conflict):
        titles.wear(player_id, "glory")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd world-backend && .venv/bin/python -m pytest tests/test_castle_titles.py -q`
Expected: FAIL — нет модуля `app.castle.titles`.

- [ ] **Step 3: Write the implementation**

```python
# world-backend/app/castle/titles.py
"""Звания игрока: пересчёт уровней веток, выдача монет и носимое звание."""
from __future__ import annotations

from app.world import core
from app.world.db import get_conn

from . import counters, tracks


def _levels(player_id: int) -> dict[str, int]:
    rows = get_conn().execute("SELECT track, level FROM titles WHERE player_id=?", (player_id,)).fetchall()
    return {row["track"]: int(row["level"]) for row in rows}


def sync(external_key: str) -> list[dict]:
    """Догоняет уровни веток до текущих значений. Возвращает только новые уровни.

    Монеты за каждый уровень выдаются через core.award с ключом уровня — повторный
    вызов после сбоя сети не начислит дважды.
    """
    player = core.get_player(external_key)
    player_id = int(player["id"])
    values = counters.counters(player_id)
    known = _levels(player_id)
    conn = get_conn()
    gained: list[dict] = []

    for track_id, track in tracks.TRACKS.items():
        old = known.get(track_id, 0)
        new = tracks.level_for(track_id, values[track_id])
        if new <= old:
            continue
        coins = sum(tracks.level_reward(level) for level in range(old + 1, new + 1))
        core.award(
            external_key, coins=coins, source=f"title:{track_id}:{new}", type_="TITLE_REWARD",
            idempotency_key=f"title:{player_id}:{track_id}:{new}",
        )
        conn.execute(
            "INSERT INTO titles (player_id, track, level) VALUES (?,?,?)"
            " ON CONFLICT(player_id, track) DO UPDATE SET level=excluded.level,"
            " awarded_at=datetime('now')",
            (player_id, track_id, new),
        )
        gained.append({
            "track": track_id,
            "level": new,
            "title_ru": track.level_titles[new - 1],
            "coins": coins,
        })
    return gained


def state(player_id: int) -> list[dict]:
    """Прогресс всех веток: уровень, значение, следующая цель, носимое звание."""
    values = counters.counters(player_id)
    levels = _levels(player_id)
    worn = get_conn().execute(
        "SELECT track FROM titles WHERE player_id=? AND worn=1", (player_id,)
    ).fetchone()
    worn_track = worn["track"] if worn else None
    rows = []
    for track_id in tracks.TRACKS:
        view = tracks.track_view(track_id, values[track_id])
        # Уровень не отбирается, даже если значение упало (оборвалась серия дней), поэтому
        # берём сохранённый уровень и от него же считаем следующую цель — иначе рядом со
        # званием 3 уровня будет прогресс «0 из 3».
        level = max(levels.get(track_id, 0), view["level"])
        thresholds = tracks.TRACKS[track_id].thresholds
        view["level"] = level
        view["title_ru"] = tracks.TRACKS[track_id].level_titles[level - 1] if level else None
        view["next_threshold"] = thresholds[level] if level < len(thresholds) else None
        view["worn"] = track_id == worn_track
        rows.append(view)
    return rows


def wear(player_id: int, track_id: str) -> list[dict]:
    """Надеть звание ветки. Носится ровно одно."""
    if track_id not in tracks.TRACKS:
        raise core.NotFound(f"track {track_id!r} not found")
    if _levels(player_id).get(track_id, 0) < 1:
        raise core.Conflict("title_not_earned")
    conn = get_conn()
    conn.execute("UPDATE titles SET worn=0 WHERE player_id=?", (player_id,))
    conn.execute("UPDATE titles SET worn=1 WHERE player_id=? AND track=?", (player_id, track_id))
    return state(player_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd world-backend && .venv/bin/python -m pytest tests/test_castle_titles.py -q`
Expected: PASS (5 тестов).

- [ ] **Step 5: Commit**

```bash
git add world-backend/app/castle/titles.py world-backend/tests/test_castle_titles.py
git commit -m "feat(castle): выдача званий и носимое звание"
```

---

### Task 5: Новая экономика уроков и тренировок

**Files:**
- Create: `world-backend/tests/lesson_helpers.py` (переезд хелперов из `test_learning_sessions.py`)
- Modify: `world-backend/tests/test_learning_sessions.py` (импорт хелперов вместо их определения)
- Modify: `world-backend/app/learning/progress.py` (константы вверху файла)
- Modify: `world-backend/app/learning/sessions.py:186-215` (блок наград в `finish`)
- Test: `world-backend/tests/test_castle_economy.py`

**Interfaces:**
- Consumes: `progress.session_reward`, `core.award`, `progress.record_activity`
- Produces: в ответе `finish` появляются поля `coins_breakdown: dict[str, int]` и `titles_gained: list[dict]`; новый тип транзакции `PRACTICE_REWARD`

- [ ] **Step 0: Вынести хелперы прохождения урока**

`start` намеренно не отдаёт решения (см. `test_start_hides_solutions`), поэтому тесты берут их
из сохранённого payload. Функции `stored`, `right_answer`, `wrong_answer` уже написаны в
`tests/test_learning_sessions.py` — перенести их без изменений (вместе с импортами `json`, `re`,
`get_conn`) в новый файл `world-backend/tests/lesson_helpers.py`, а в `test_learning_sessions.py`
заменить определения на `from tests.lesson_helpers import right_answer, stored, wrong_answer`.

Проверка переезда: `cd world-backend && .venv/bin/python -m pytest tests/test_learning_sessions.py -q` — PASS.

- [ ] **Step 1: Write the failing test**

```python
# world-backend/tests/test_castle_economy.py
"""Монеты за урок, за отсутствие ошибок, за цель дня и за тренировку — с дневным потолком."""
from __future__ import annotations

from app.learning import sessions
from app.world import core
from app.world.db import get_conn
from tests.lesson_helpers import right_answer, stored, wrong_answer


def _finish_lesson(key: str, node_id: str, *, wrong: int = 0) -> dict:
    """Проходит урок целиком. Первые `wrong` вопросов сначала отвечает неверно.

    Неверный ответ возвращает вопрос в очередь ошибок, поэтому сразу после него даётся
    верный — так урок дойдёт до конца, а счётчик ошибок останется ненулевым.
    """
    started = sessions.start(key, node_id, allow_speak=False)
    session_id = started["session_id"]
    payload = stored(session_id)
    mistakes_left = wrong
    for index, challenge in enumerate(payload):
        if mistakes_left:
            sessions.answer(key, session_id, index, wrong_answer(challenge))
            mistakes_left -= 1
        sessions.answer(key, session_id, index, right_answer(challenge))
    return sessions.finish(key, session_id)


def test_perfect_lesson_pays_bonus(learner, learn_course):
    key, _ = learner
    result = _finish_lesson(key, "sp1.m1.n1")
    assert result["coins_breakdown"]["lesson"] == 5
    assert result["coins_breakdown"]["perfect"] == 3
    assert result["coins"] == sum(result["coins_breakdown"].values())


def test_lesson_with_mistake_has_no_perfect_bonus(learner, learn_course):
    key, _ = learner
    result = _finish_lesson(key, "sp1.m1.n1", wrong=1)
    assert result["coins_breakdown"].get("perfect", 0) == 0


def test_daily_goal_pays_once_per_day(learner, learn_course):
    key, player_id = learner
    first = _finish_lesson(key, "sp1.m1.n1")
    second = _finish_lesson(key, "sp1.m1.n2")
    goal_payments = [r["coins_breakdown"].get("daily_goal", 0) for r in (first, second)]
    assert sum(1 for payment in goal_payments if payment == 10) <= 1
    rows = get_conn().execute(
        "SELECT COUNT(*) AS c FROM coin_transactions WHERE player_id=? AND type='DAILY_GOAL_REWARD'",
        (player_id,),
    ).fetchone()["c"]
    assert rows <= 1


def test_practice_pays_three_coins_twice_a_day(learner, learn_course):
    key, player_id = learner
    payouts = []
    for _ in range(3):
        payouts.append(_finish_lesson(key, sessions.PRACTICE_NODE)["coins"])
    assert payouts[0] == 3 and payouts[1] == 3
    assert payouts[2] == 0  # третья тренировка за день монет не приносит
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd world-backend && .venv/bin/python -m pytest tests/test_castle_economy.py -q`
Expected: FAIL — в ответе нет `coins_breakdown`.

- [ ] **Step 3: Write the implementation**

В `world-backend/app/learning/progress.py` рядом с существующими константами:

```python
COINS_SESSION = 5
COINS_CHEST = 30
COINS_MODULE_TEST_FIRST = 50
COINS_PERFECT = 3          # урок без ошибок
COINS_DAILY_GOAL = 10      # цель дня, один раз в день
COINS_PRACTICE = 3         # тренировка во Дворе
PRACTICE_PAID_PER_DAY = 2  # дальше тренировка бесплатна: иначе это ферма монет
```

В `world-backend/app/learning/sessions.py` заменить блок начисления в `finish` (строки с `coins = reward.coins` до `award = core.award(...)`) на:

```python
    from app.castle import titles as castle_titles

    day_key = clock.local_day(moment)
    breakdown: dict[str, int] = {}
    if kind == PRACTICE_NODE:
        paid_today = get_conn().execute(
            "SELECT COUNT(*) AS c FROM coin_transactions"
            " WHERE player_id=? AND type='PRACTICE_REWARD' AND date(created_at)=?",
            (player_id, day_key),
        ).fetchone()["c"]
        if paid_today < progress.PRACTICE_PAID_PER_DAY:
            breakdown["practice"] = progress.COINS_PRACTICE
    else:
        breakdown["lesson"] = reward.coins
        if state["wrong"] == 0:
            breakdown["perfect"] = progress.COINS_PERFECT
        if kind == "module_test" and reward.passed and node_id not in progress.completed_nodes(player_id):
            breakdown["module_test"] = progress.COINS_MODULE_TEST_FIRST

    coins = sum(breakdown.values())
    award_type = "PRACTICE_REWARD" if kind == PRACTICE_NODE else "LESSON_REWARD"
    award = core.award(
        external_key, xp=reward.xp, coins=coins, source=node_id, type_=award_type,
        idempotency_key=f"v2:{session_id}",
    )
```

Ниже, сразу после `day = progress.record_activity(...)` и вычисления `goal`, добавить выплату за цель дня и пересчёт званий:

```python
    if day["today_xp"] >= goal:
        goal_award = core.award(
            external_key, coins=progress.COINS_DAILY_GOAL, source=day_key, type_="DAILY_GOAL_REWARD",
            idempotency_key=f"goal:{player_id}:{day_key}",
        )
        if goal_award["coins_delta"]:
            breakdown["daily_goal"] = progress.COINS_DAILY_GOAL
            coins += progress.COINS_DAILY_GOAL
            award = goal_award

    titles_gained = castle_titles.sync(external_key)
```

И в словарь `result` добавить два поля:

```python
        "coins_breakdown": breakdown,
        "titles_gained": titles_gained,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd world-backend && .venv/bin/python -m pytest tests/test_castle_economy.py tests/test_learning_sessions.py -q`
Expected: PASS. Если старые тесты ждут прежние суммы монет — обновить в них ожидания по спеке (урок 5, без ошибок +3), это осознанное изменение баланса.

- [ ] **Step 5: Commit**

```bash
git add world-backend/app/learning world-backend/tests/test_castle_economy.py
git commit -m "feat(castle): новая экономика урока, цели дня и тренировки"
```

---

### Task 6: Закрытие недели лиги

**Files:**
- Create: `world-backend/app/castle/league_weeks.py`
- Modify: `world-backend/app/world/learn.py:110-140` (функция `league`)
- Test: `world-backend/tests/test_castle_league_weeks.py`

**Interfaces:**
- Consumes: `app.world.core.award`, `app.world.db.get_conn`
- Produces: `week_start(moment: datetime) -> str`, `close_previous_week(now: datetime | None = None) -> int` (сколько игроков закрыто), `COINS_BY_RANK: dict[int, int]`

- [ ] **Step 1: Write the failing test**

```python
# world-backend/tests/test_castle_league_weeks.py
"""Неделя лиги закрывается лениво, один раз, и платит за место."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.castle import league_weeks
from app.world import core
from app.world.db import get_conn


def _player_with_xp(key: str, name: str, xp: int, *, days_ago: int) -> int:
    player = core.get_or_create_player(key, name)
    moment = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
    get_conn().execute(
        "INSERT INTO xp_transactions (player_id, type, amount, source, idempotency_key, created_at)"
        " VALUES (?,?,?,?,?,?)",
        (player["id"], "LESSON_REWARD", xp, "test", f"xp:{key}:{days_ago}:{xp}", moment),
    )
    return int(player["id"])


def test_week_start_is_monday():
    assert league_weeks.week_start(datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)) == "2026-09-14"
    assert league_weeks.week_start(datetime(2026, 9, 14, 0, 30, tzinfo=timezone.utc)) == "2026-09-14"


def test_closing_pays_by_rank_and_only_once(learn_db):
    _player_with_xp("kid-a", "Аня", 300, days_ago=9)
    _player_with_xp("kid-b", "Боря", 200, days_ago=9)

    closed = league_weeks.close_previous_week()
    assert closed == 2
    assert core.get_player("kid-a")["coins"] == league_weeks.COINS_BY_RANK[1]
    assert core.get_player("kid-b")["coins"] == league_weeks.COINS_BY_RANK[2]

    assert league_weeks.close_previous_week() == 0
    assert core.get_player("kid-a")["coins"] == league_weeks.COINS_BY_RANK[1]


def test_player_without_lessons_is_not_recorded(learn_db):
    core.get_or_create_player("kid-quiet", "Тихоня")
    league_weeks.close_previous_week()
    rows = get_conn().execute("SELECT COUNT(*) AS c FROM league_weeks").fetchone()["c"]
    assert rows == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd world-backend && .venv/bin/python -m pytest tests/test_castle_league_weeks.py -q`
Expected: FAIL — нет модуля `app.castle.league_weeks`.

- [ ] **Step 3: Write the implementation**

```python
# world-backend/app/castle/league_weeks.py
"""Итог недели в лиге.

Лига считается скользящим окном и сама ничего не сохраняет. Здесь неделя
закрывается лениво: первый заход после понедельника подводит итог прошлой недели
один раз. Внешний планировщик не нужен — на сервере его всё равно нет.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.world import core
from app.world.db import get_conn

COINS_BY_RANK = {1: 100, 2: 60, 3: 60, 4: 30, 5: 30, 6: 30, 7: 30, 8: 30, 9: 30, 10: 30}


def week_start(moment: datetime) -> str:
    """Понедельник недели, к которой относится момент."""
    day = moment.date() - timedelta(days=moment.weekday())
    return day.strftime("%Y-%m-%d")


def close_previous_week(now: datetime | None = None) -> int:
    """Подводит итог прошлой недели. Возвращает число закрытых игроков."""
    moment = now or datetime.now(timezone.utc)
    start = week_start(moment - timedelta(days=7))
    end = week_start(moment)
    conn = get_conn()
    rows = conn.execute(
        "SELECT p.id, p.external_key,"
        " COALESCE(SUM(CASE WHEN x.amount>0 AND date(x.created_at)>=? AND date(x.created_at)<? THEN x.amount END),0)"
        " AS weekly_xp"
        " FROM players p LEFT JOIN xp_transactions x ON x.player_id=p.id"
        " WHERE p.role='child'"
        " GROUP BY p.id HAVING weekly_xp > 0 ORDER BY weekly_xp DESC, p.id ASC",
        (start, end),
    ).fetchall()

    closed = 0
    for rank, row in enumerate(rows, start=1):
        already = conn.execute(
            "SELECT 1 FROM league_weeks WHERE player_id=? AND week_start=?", (row["id"], start)
        ).fetchone()
        if already:
            continue
        coins = COINS_BY_RANK.get(rank, 0)
        conn.execute(
            "INSERT INTO league_weeks (player_id, week_start, rank, weekly_xp, coins_awarded)"
            " VALUES (?,?,?,?,?)",
            (row["id"], start, rank, int(row["weekly_xp"]), coins),
        )
        if coins:
            core.award(
                row["external_key"], coins=coins, source=f"league:{start}", type_="LEAGUE_REWARD",
                idempotency_key=f"league:{row['id']}:{start}",
            )
        closed += 1
    return closed
```

В `world-backend/app/world/learn.py`, в начале функции `league`, закрывать прошлую неделю перед расчётом:

```python
def league(external_key: str) -> dict:
    """Недельный рейтинг по всем игрокам: тир, место, размер лиги и таблица лидеров."""
    from app.castle import league_weeks

    league_weeks.close_previous_week()
    player = core.get_player(external_key)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd world-backend && .venv/bin/python -m pytest tests/test_castle_league_weeks.py tests/test_world_learn.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add world-backend/app/castle/league_weeks.py world-backend/app/world/learn.py world-backend/tests/test_castle_league_weeks.py
git commit -m "feat(castle): закрытие недели лиги и монеты за место"
```

---

### Task 7: Каталог облика и состояние замка

**Files:**
- Create: `world-backend/app/castle/catalog.py`
- Create: `world-backend/app/castle/state.py`
- Test: `world-backend/tests/test_castle_state.py`

**Interfaces:**
- Produces:
  - `catalog.ITEMS: dict[str, Item]`, `Item(id, kind, title_ru, price, requires_track, requires_level, purchasable)`; `kind` ∈ `season|time|weather|banner|decor`
  - `catalog.season_by_date(moment: datetime) -> str`
  - `state.appearance(player_id: int) -> dict`, `state.set_appearance(player_id: int, **fields) -> dict`, `state.owned(player_id: int) -> list[str]`

- [ ] **Step 1: Write the failing test**

```python
# world-backend/tests/test_castle_state.py
"""Каталог облика и сохранение выбранного вида замка."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.castle import catalog, state
from app.world.core import Conflict


def test_season_follows_calendar():
    assert catalog.season_by_date(datetime(2026, 1, 15, tzinfo=timezone.utc)) == "winter"
    assert catalog.season_by_date(datetime(2026, 4, 15, tzinfo=timezone.utc)) == "spring"
    assert catalog.season_by_date(datetime(2026, 7, 15, tzinfo=timezone.utc)) == "summer"
    assert catalog.season_by_date(datetime(2026, 10, 15, tzinfo=timezone.utc)) == "autumn"


def test_catalog_prices_match_spec():
    assert catalog.ITEMS["season-winter"].price == 150
    assert catalog.ITEMS["time-night"].price == 80
    assert 60 <= catalog.ITEMS["weather-snow"].price <= 120
    assert catalog.ITEMS["banner-emerald"].price == 50


def test_rarest_item_cannot_be_bought():
    item = catalog.ITEMS["weather-aurora"]
    assert item.purchasable is False
    assert item.requires_track == "nest"
    assert item.requires_level == 5


def test_default_appearance_is_free_and_seasonal(learner):
    _, player_id = learner
    view = state.appearance(player_id)
    assert view["season"] is None       # означает «по календарю»
    assert view["time_of_day"] is None  # означает «как за окном»
    assert view["weather"] is None
    assert view["banner_color"] == "plum"


def test_set_appearance_saves_and_validates(learner):
    _, player_id = learner
    view = state.set_appearance(player_id, time_of_day="night", banner_color="emerald")
    assert view["time_of_day"] == "night"
    assert view["banner_color"] == "emerald"
    with pytest.raises(Conflict):
        state.set_appearance(player_id, time_of_day="полночь")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd world-backend && .venv/bin/python -m pytest tests/test_castle_state.py -q`
Expected: FAIL — нет модулей `catalog` и `state`.

- [ ] **Step 3: Write the implementation**

```python
# world-backend/app/castle/catalog.py
"""Витрина облика замка. Цены и условия — из спеки, держим кодом ради быстрых правок баланса."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

SEASONS = ("spring", "summer", "autumn", "winter")
TIMES = ("dawn", "day", "dusk", "night")
WEATHERS = ("snow", "rain", "fireflies", "fog", "aurora", "petals")
BANNER_COLORS = ("plum", "emerald", "gold", "azure", "rose")


@dataclass(frozen=True)
class Item:
    id: str
    kind: str              # season|time|weather|banner|decor
    title_ru: str
    price: int
    value: str             # что применяется: имя сезона, времени, погоды, цвета
    requires_track: str | None = None
    requires_level: int = 0
    purchasable: bool = True


def _items() -> dict[str, Item]:
    items: dict[str, Item] = {}
    seasons_ru = {"spring": "Весна", "summer": "Лето", "autumn": "Осень", "winter": "Зима"}
    for season, title in seasons_ru.items():
        items[f"season-{season}"] = Item(
            id=f"season-{season}", kind="season", title_ru=title, price=150, value=season,
            requires_track="lexicon", requires_level=2,
        )
    times_ru = {"dawn": "Рассвет", "day": "День", "dusk": "Закат", "night": "Ночь"}
    for time_of_day, title in times_ru.items():
        items[f"time-{time_of_day}"] = Item(
            id=f"time-{time_of_day}", kind="time", title_ru=title, price=80, value=time_of_day,
        )
    weather_specs = {
        "snow": ("Снегопад", 90, None, 0, True),
        "rain": ("Дождь", 60, None, 0, True),
        "fireflies": ("Светлячки", 120, "yard", 2, True),
        "fog": ("Туман", 60, None, 0, True),
        "petals": ("Лепестки", 90, "stickers", 2, True),
        "aurora": ("Северное сияние", 0, "nest", 5, False),  # только за звание
    }
    for weather, (title, price, track, level, purchasable) in weather_specs.items():
        items[f"weather-{weather}"] = Item(
            id=f"weather-{weather}", kind="weather", title_ru=title, price=price, value=weather,
            requires_track=track, requires_level=level, purchasable=purchasable,
        )
    colors_ru = {"emerald": "Изумрудное", "gold": "Золотое", "azure": "Лазурное", "rose": "Розовое"}
    for color, title in colors_ru.items():
        items[f"banner-{color}"] = Item(
            id=f"banner-{color}", kind="banner", title_ru=f"{title} знамя", price=50, value=color,
        )
    return items


ITEMS: dict[str, Item] = _items()

# Бесплатно и всегда доступно: сезон по календарю, время «как за окном», сливовое знамя.
FREE_VALUES = {"season": None, "time": None, "weather": None, "banner": "plum"}


def season_by_date(moment: datetime) -> str:
    month = moment.month
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "autumn"
```

```python
# world-backend/app/castle/state.py
"""Что выбрано и что куплено у конкретного игрока."""
from __future__ import annotations

from app.world.core import Conflict
from app.world.db import get_conn

from .catalog import BANNER_COLORS, SEASONS, TIMES, WEATHERS

_ALLOWED = {
    "season": SEASONS,
    "time_of_day": TIMES,
    "weather": WEATHERS,
    "banner_color": BANNER_COLORS,
}


def appearance(player_id: int) -> dict:
    row = get_conn().execute(
        "SELECT season, time_of_day, weather, banner_color, banner_emblem"
        " FROM castle_appearance WHERE player_id=?",
        (player_id,),
    ).fetchone()
    if row is None:
        return {"season": None, "time_of_day": None, "weather": None,
                "banner_color": "plum", "banner_emblem": "fox"}
    return {
        "season": row["season"],
        "time_of_day": row["time_of_day"],
        "weather": row["weather"],
        "banner_color": row["banner_color"],
        "banner_emblem": row["banner_emblem"],
    }


def set_appearance(player_id: int, **fields) -> dict:
    """Сохраняет выбор. None у сезона, времени и погоды означает «бесплатный вариант»."""
    current = appearance(player_id)
    for name, value in fields.items():
        if name not in current:
            raise Conflict(f"unknown field {name!r}")
        if value is not None and name in _ALLOWED and value not in _ALLOWED[name]:
            raise Conflict(f"bad value for {name}")
        current[name] = value
    get_conn().execute(
        "INSERT INTO castle_appearance (player_id, season, time_of_day, weather, banner_color, banner_emblem)"
        " VALUES (?,?,?,?,?,?)"
        " ON CONFLICT(player_id) DO UPDATE SET season=excluded.season, time_of_day=excluded.time_of_day,"
        " weather=excluded.weather, banner_color=excluded.banner_color, banner_emblem=excluded.banner_emblem,"
        " updated_at=datetime('now')",
        (player_id, current["season"], current["time_of_day"], current["weather"],
         current["banner_color"], current["banner_emblem"]),
    )
    return current


def owned(player_id: int) -> list[str]:
    rows = get_conn().execute(
        "SELECT item_id FROM castle_owned WHERE player_id=? ORDER BY acquired_at", (player_id,)
    ).fetchall()
    return [row["item_id"] for row in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd world-backend && .venv/bin/python -m pytest tests/test_castle_state.py -q`
Expected: PASS (5 тестов).

- [ ] **Step 5: Commit**

```bash
git add world-backend/app/castle/catalog.py world-backend/app/castle/state.py world-backend/tests/test_castle_state.py
git commit -m "feat(castle): каталог облика и состояние замка"
```

---

### Task 8: Покупка и применение облика

**Files:**
- Create: `world-backend/app/castle/service.py`
- Test: `world-backend/tests/test_castle_service.py`

**Interfaces:**
- Consumes: `catalog.ITEMS`, `state`, `titles.state`, `core.spend`, `core.get_player`
- Produces: `view(external_key: str) -> dict`, `buy(external_key: str, item_id: str) -> dict`, `apply(external_key: str, **fields) -> dict`

- [ ] **Step 1: Write the failing test**

```python
# world-backend/tests/test_castle_service.py
"""Покупка облика: проверка звания, монет и повторного нажатия."""
from __future__ import annotations

import pytest

from app.castle import service
from app.world import core
from app.world.core import Conflict
from app.world.db import get_conn


def _give_coins(key: str, coins: int) -> None:
    core.award(key, coins=coins, source="test", type_="TEST_GRANT", idempotency_key=f"grant:{key}:{coins}")


def _learn_words(player_id: int, count: int) -> None:
    for n in range(count):
        get_conn().execute(
            "INSERT INTO word_stats (player_id, unit_id, word_en, strength) VALUES (?,?,?,?)",
            (player_id, "sp1.m1", f"word{n}", 3),
        )


def test_view_lists_catalog_titles_and_appearance(learner):
    key, _ = learner
    view = service.view(key)
    assert view["appearance"]["banner_color"] == "plum"
    assert any(item["id"] == "time-night" for item in view["catalog"])
    assert len(view["titles"]) == 5
    assert view["owned"] == []


def test_buy_spends_coins_and_unlocks_item(learner):
    key, _ = learner
    _give_coins(key, 100)
    result = service.buy(key, "time-night")
    assert result["owned"] == ["time-night"]
    assert core.get_player(key)["coins"] == 20


def test_buy_twice_does_not_charge_twice(learner):
    key, _ = learner
    _give_coins(key, 100)
    service.buy(key, "time-night")
    service.buy(key, "time-night")
    assert core.get_player(key)["coins"] == 20


def test_buy_without_coins_is_rejected(learner):
    key, _ = learner
    with pytest.raises(Conflict):
        service.buy(key, "time-night")


def test_buy_locked_by_title_is_rejected(learner):
    key, player_id = learner
    _give_coins(key, 500)
    with pytest.raises(Conflict):
        service.buy(key, "season-winter")     # нужен Словесник 2 уровня
    _learn_words(player_id, 50)
    from app.castle import titles
    titles.sync(key)
    assert service.buy(key, "season-winter")["owned"] == ["season-winter"]


def test_item_that_is_not_purchasable_is_rejected(learner):
    key, _ = learner
    _give_coins(key, 500)
    with pytest.raises(Conflict):
        service.buy(key, "weather-aurora")


def test_apply_requires_owning_the_item(learner):
    key, _ = learner
    _give_coins(key, 100)
    with pytest.raises(Conflict):
        service.apply(key, time_of_day="night")
    service.buy(key, "time-night")
    assert service.apply(key, time_of_day="night")["appearance"]["time_of_day"] == "night"


def test_free_variants_apply_without_purchase(learner):
    key, _ = learner
    assert service.apply(key, time_of_day=None, season=None)["appearance"]["season"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd world-backend && .venv/bin/python -m pytest tests/test_castle_service.py -q`
Expected: FAIL — нет модуля `app.castle.service`.

- [ ] **Step 3: Write the implementation**

```python
# world-backend/app/castle/service.py
"""Витрина, покупка и применение облика замка.

Все проверки — на сервере: цена, условие по званию и владение вещью. Клиент только
показывает то, что вернул этот модуль.
"""
from __future__ import annotations

from app.world import core
from app.world.core import Conflict, NotFound
from app.world.db import get_conn

from . import catalog, state, titles

_FIELD_KIND = {"season": "season", "time_of_day": "time", "weather": "weather", "banner_color": "banner"}


def _levels(player_id: int) -> dict[str, int]:
    """Уровни веток игрока: {track: level}."""
    return {row["track"]: int(row["level"]) for row in titles.state(player_id)}


def _unlocked(item: catalog.Item, levels: dict[str, int]) -> bool:
    if item.requires_track is None:
        return True
    return levels.get(item.requires_track, 0) >= item.requires_level


def view(external_key: str) -> dict:
    player = core.get_player(external_key)
    player_id = int(player["id"])
    track_rows = titles.state(player_id)
    levels = {row["track"]: int(row["level"]) for row in track_rows}
    owned = state.owned(player_id)
    items = []
    for item in catalog.ITEMS.values():
        items.append({
            "id": item.id,
            "kind": item.kind,
            "title_ru": item.title_ru,
            "value": item.value,
            "price": item.price,
            "purchasable": item.purchasable,
            "owned": item.id in owned,
            "unlocked": _unlocked(item, levels),
            "requires_track": item.requires_track,
            "requires_level": item.requires_level,
        })
    return {
        "appearance": state.appearance(player_id),
        "catalog": items,
        "owned": owned,
        "titles": track_rows,
        "coins": int(player["coins"]),
    }


def buy(external_key: str, item_id: str) -> dict:
    item = catalog.ITEMS.get(item_id)
    if item is None:
        raise NotFound(f"item {item_id!r} not found")
    player = core.get_player(external_key)
    player_id = int(player["id"])
    if item_id in state.owned(player_id):
        return view(external_key)          # повторное нажатие не списывает второй раз
    if not item.purchasable:
        raise Conflict("item_not_for_sale")
    levels = _levels(player_id)
    if not _unlocked(item, levels):
        raise Conflict("title_required")

    core.spend(
        external_key, coins=item.price, source=item_id, type_="CASTLE_BUY",
        idempotency_key=f"castle:{player_id}:{item_id}",
    )
    get_conn().execute(
        "INSERT OR IGNORE INTO castle_owned (player_id, item_id, source) VALUES (?,?,?)",
        (player_id, item_id, "shop"),
    )
    return view(external_key)


def apply(external_key: str, **fields) -> dict:
    """Применяет выбранное. Платный вариант должен быть куплен, бесплатный доступен всегда."""
    player = core.get_player(external_key)
    player_id = int(player["id"])
    owned = set(state.owned(player_id))
    levels = _levels(player_id)

    for field, value in fields.items():
        kind = _FIELD_KIND.get(field)
        if kind is None or value is None or value == catalog.FREE_VALUES.get(kind):
            continue
        item = next((i for i in catalog.ITEMS.values() if i.kind == kind and i.value == value), None)
        if item is None:
            raise Conflict(f"unknown value for {field}")
        earned = not item.purchasable and _unlocked(item, levels)
        if item.id not in owned and not earned:
            raise Conflict("item_not_owned")

    state.set_appearance(player_id, **fields)
    return view(external_key)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd world-backend && .venv/bin/python -m pytest tests/test_castle_service.py -q`
Expected: PASS (8 тестов).

- [ ] **Step 5: Commit**

```bash
git add world-backend/app/castle/service.py world-backend/tests/test_castle_service.py
git commit -m "feat(castle): покупка и применение облика"
```

---

### Task 9: HTTP API замка

**Files:**
- Create: `world-backend/app/castle/api.py`
- Modify: `world-backend/main.py:9-33` (импорт и `include_router`)
- Test: `world-backend/tests/test_castle_api.py`

**Interfaces:**
- Consumes: `service.view/buy/apply`, `titles.wear`, `app.world.api._player_key`
- Produces: `GET /api/v2/castle`, `POST /api/v2/castle/buy`, `POST /api/v2/castle/appearance`, `POST /api/v2/castle/title`

- [ ] **Step 1: Write the failing test**

```python
# world-backend/tests/test_castle_api.py
"""HTTP-контракт замка."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.world import core


@pytest.fixture()
def client(learn_db, learn_course):
    from main import app

    core.get_or_create_player("kid-v2", "Маша")
    with TestClient(app) as test_client:
        yield test_client


HEAD = {"X-World-Player": "kid-v2"}


def test_get_castle_returns_appearance_and_catalog(client):
    body = client.get("/api/v2/castle", headers=HEAD).json()
    assert body["appearance"]["banner_color"] == "plum"
    assert len(body["titles"]) == 5
    assert any(item["id"] == "time-night" for item in body["catalog"])


def test_buy_without_coins_returns_409(client):
    res = client.post("/api/v2/castle/buy", json={"item_id": "time-night"}, headers=HEAD)
    assert res.status_code == 409


def test_buy_then_apply(client):
    core.award("kid-v2", coins=200, source="test", type_="TEST_GRANT", idempotency_key="grant:api")
    assert client.post("/api/v2/castle/buy", json={"item_id": "time-night"}, headers=HEAD).status_code == 200
    body = client.post("/api/v2/castle/appearance", json={"time_of_day": "night"}, headers=HEAD).json()
    assert body["appearance"]["time_of_day"] == "night"


def test_wear_title_without_level_returns_409(client):
    res = client.post("/api/v2/castle/title", json={"track": "glory"}, headers=HEAD)
    assert res.status_code == 409


def test_unknown_item_returns_404(client):
    res = client.post("/api/v2/castle/buy", json={"item_id": "time-полночь"}, headers=HEAD)
    assert res.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd world-backend && .venv/bin/python -m pytest tests/test_castle_api.py -q`
Expected: FAIL — 404 на `/api/v2/castle`.

- [ ] **Step 3: Write the implementation**

```python
# world-backend/app/castle/api.py
"""HTTP API замка: облик, покупки, звания."""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.world import core
from app.world.api import _player_key as resolve_player_key

from . import service, titles

router = APIRouter(prefix="/api/v2/castle", tags=["castle"])


class BuyBody(BaseModel):
    item_id: str


class AppearanceBody(BaseModel):
    season: str | None = None
    time_of_day: str | None = None
    weather: str | None = None
    banner_color: str | None = None
    banner_emblem: str | None = None


class TitleBody(BaseModel):
    track: str


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except core.NotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except core.Conflict as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("")
def get_castle(x_world_player: str | None = Header(None)):
    return _run(service.view, resolve_player_key(x_world_player))


@router.post("/buy")
def buy(body: BuyBody, x_world_player: str | None = Header(None)):
    return _run(service.buy, resolve_player_key(x_world_player), body.item_id)


@router.post("/appearance")
def appearance(body: AppearanceBody, x_world_player: str | None = Header(None)):
    fields = body.model_dump(exclude_unset=True)
    return _run(service.apply, resolve_player_key(x_world_player), **fields)


@router.post("/title")
def wear_title(body: TitleBody, x_world_player: str | None = Header(None)):
    key = resolve_player_key(x_world_player)
    player = _run(core.get_player, key)
    _run(titles.wear, int(player["id"]), body.track)
    return _run(service.view, key)
```

В `world-backend/main.py`:

```python
from app.castle import api as castle_api
...
app.include_router(castle_api.router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd world-backend && .venv/bin/python -m pytest tests/test_castle_api.py -q && .venv/bin/python -m pytest -q`
Expected: PASS, весь набор тестов зелёный.

- [ ] **Step 5: Commit**

```bash
git add world-backend/app/castle/api.py world-backend/main.py world-backend/tests/test_castle_api.py
git commit -m "feat(castle): HTTP API облика и званий"
```

---

### Task 10: Клиент замка на фронтенде

**Files:**
- Create: `world/src/lib/v2/castle.ts`
- Test: `world/src/lib/v2/castle.test.ts`

**Interfaces:**
- Consumes: `call`/`post` из `world/src/lib/v2/client.ts` (экспортировать `post` не нужно — методы добавляем в этот же файл через `v2`)
- Produces: типы `CastleView`, `CastleItem`, `TitleRow`, `Appearance`; объект `castleApi` с `get`, `buy`, `apply`, `wear`

- [ ] **Step 1: Write the failing test**

```ts
// world/src/lib/v2/castle.test.ts
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { castleApi } from "./castle";

const view = {
  appearance: { season: null, time_of_day: null, weather: null, banner_color: "plum", banner_emblem: "fox" },
  catalog: [],
  owned: [],
  titles: [],
  coins: 0,
};

describe("castleApi", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(view), { status: 200 })));
  });
  afterEach(() => vi.unstubAllGlobals());

  it("запрашивает состояние замка", async () => {
    await castleApi.get();
    const [url] = (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(String(url)).toContain("/api/v2/castle");
  });

  it("покупает вещь по id", async () => {
    await castleApi.buy("time-night");
    const [url, init] = (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(String(url)).toContain("/api/v2/castle/buy");
    expect(JSON.parse(String((init as RequestInit).body))).toEqual({ item_id: "time-night" });
  });

  it("применяет только переданные поля", async () => {
    await castleApi.apply({ time_of_day: "night" });
    const [, init] = (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(JSON.parse(String((init as RequestInit).body))).toEqual({ time_of_day: "night" });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd world && npx vitest run src/lib/v2/castle.test.ts`
Expected: FAIL — модуля `./castle` нет.

- [ ] **Step 3: Write the implementation**

```ts
// world/src/lib/v2/castle.ts
/** Клиент замка: облик, витрина и звания (/api/v2/castle). */
import { playerKey } from "@/lib/api";

const API = (process.env.NEXT_PUBLIC_WORLD_API || "").replace(/\/$/, "");

export type Appearance = {
  season: string | null;
  time_of_day: string | null;
  weather: string | null;
  banner_color: string;
  banner_emblem: string;
};

export type CastleItem = {
  id: string;
  kind: "season" | "time" | "weather" | "banner" | "decor";
  title_ru: string;
  value: string;
  price: number;
  purchasable: boolean;
  owned: boolean;
  unlocked: boolean;
  requires_track: string | null;
  requires_level: number;
};

export type TitleRow = {
  track: string;
  track_title_ru: string;
  building: string;
  unit_ru: string;
  level: number;
  title_ru: string | null;
  value: number;
  next_threshold: number | null;
  worn: boolean;
};

export type CastleView = {
  appearance: Appearance;
  catalog: CastleItem[];
  owned: string[];
  titles: TitleRow[];
  coins: number;
};

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    cache: "no-store",
    headers: { "Content-Type": "application/json", "X-World-Player": playerKey(), ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* пустое тело ответа */
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export const castleApi = {
  get: () => call<CastleView>("/api/v2/castle"),
  buy: (itemId: string) =>
    call<CastleView>("/api/v2/castle/buy", { method: "POST", body: JSON.stringify({ item_id: itemId }) }),
  apply: (fields: Partial<Appearance>) =>
    call<CastleView>("/api/v2/castle/appearance", { method: "POST", body: JSON.stringify(fields) }),
  wear: (track: string) =>
    call<CastleView>("/api/v2/castle/title", { method: "POST", body: JSON.stringify({ track }) }),
};
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd world && npx vitest run src/lib/v2/castle.test.ts && npx tsc --noEmit -p .`
Expected: PASS, типы чистые.

- [ ] **Step 5: Commit**

```bash
git add world/src/lib/v2/castle.ts world/src/lib/v2/castle.test.ts
git commit -m "feat(castle): клиент API замка"
```

---

### Task 11: Слои облика на сцене

**Files:**
- Create: `world/src/castle/appearance.ts` (чистые функции слоёв)
- Create: `world/src/castle/Weather.tsx` (частицы)
- Modify: `world/src/features/castle/CastleScreen.tsx` (сцена получает слои)
- Test: `world/src/castle/appearance.test.ts`

**Interfaces:**
- Consumes: `Appearance` из `@/lib/v2/castle`
- Produces: `seasonByDate(date: Date): string`, `timeByClock(date: Date): string`, `lightLayer(time: string): { background: string; mixBlendMode: string }`, `effectiveAppearance(view: Appearance, now: Date): { season: string; time: string; weather: string | null }`

- [ ] **Step 1: Write the failing test**

```ts
// world/src/castle/appearance.test.ts
import { describe, expect, it } from "vitest";
import { effectiveAppearance, lightLayer, seasonByDate, timeByClock } from "./appearance";

describe("облик замка", () => {
  it("сезон по календарю, если ничего не куплено", () => {
    expect(seasonByDate(new Date("2026-01-15T12:00:00"))).toBe("winter");
    expect(seasonByDate(new Date("2026-07-15T12:00:00"))).toBe("summer");
  });

  it("время суток по часам ребёнка", () => {
    expect(timeByClock(new Date("2026-09-17T06:30:00"))).toBe("dawn");
    expect(timeByClock(new Date("2026-09-17T13:00:00"))).toBe("day");
    expect(timeByClock(new Date("2026-09-17T19:30:00"))).toBe("dusk");
    expect(timeByClock(new Date("2026-09-17T23:30:00"))).toBe("night");
  });

  it("выбранное побеждает автоматическое", () => {
    const result = effectiveAppearance(
      { season: "winter", time_of_day: "night", weather: "snow", banner_color: "gold", banner_emblem: "fox" },
      new Date("2026-07-15T13:00:00"),
    );
    expect(result).toEqual({ season: "winter", time: "night", weather: "snow" });
  });

  it("пустой выбор подставляет календарь и часы", () => {
    const result = effectiveAppearance(
      { season: null, time_of_day: null, weather: null, banner_color: "plum", banner_emblem: "fox" },
      new Date("2026-07-15T13:00:00"),
    );
    expect(result).toEqual({ season: "summer", time: "day", weather: null });
  });

  it("день не затемняет сцену, ночь затемняет", () => {
    expect(lightLayer("day").background).toContain("transparent");
    expect(lightLayer("night").background).not.toContain("transparent");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd world && npx vitest run src/castle/appearance.test.ts`
Expected: FAIL — модуля нет.

- [ ] **Step 3: Write the implementation**

```ts
// world/src/castle/appearance.ts
/** Облик замка: что показать, если ребёнок ничего не выбрал, и как красить слой света. */
import type { Appearance } from "@/lib/v2/castle";

export function seasonByDate(date: Date): string {
  const month = date.getMonth() + 1;
  if (month === 12 || month <= 2) return "winter";
  if (month <= 5) return "spring";
  if (month <= 8) return "summer";
  return "autumn";
}

export function timeByClock(date: Date): string {
  const hour = date.getHours();
  if (hour < 5 || hour >= 22) return "night";
  if (hour < 9) return "dawn";
  if (hour < 18) return "day";
  return "dusk";
}

export function effectiveAppearance(
  appearance: Appearance,
  now: Date,
): { season: string; time: string; weather: string | null } {
  return {
    season: appearance.season ?? seasonByDate(now),
    time: appearance.time_of_day ?? timeByClock(now),
    weather: appearance.weather,
  };
}

/** Слой света поверх диорамы: плёнка цвета, а не перерисовка картинки. */
export function lightLayer(time: string): { background: string; mixBlendMode: string } {
  const layers: Record<string, string> = {
    dawn: "linear-gradient(180deg, rgb(255 190 140 / 0.28), rgb(120 90 160 / 0.18))",
    day: "linear-gradient(180deg, transparent, transparent)",
    dusk: "linear-gradient(180deg, rgb(255 140 90 / 0.22), rgb(70 40 110 / 0.30))",
    night: "linear-gradient(180deg, rgb(20 24 70 / 0.55), rgb(10 12 40 / 0.62))",
  };
  return { background: layers[time] ?? layers.day, mixBlendMode: time === "night" ? "multiply" : "soft-light" };
}
```

```tsx
// world/src/castle/Weather.tsx
"use client";

import { useEffect, useRef } from "react";

/** Погода над замком: частицы на canvas. Ограничены по числу и выключаются при «уменьшить движение». */
const COUNTS: Record<string, number> = { snow: 90, rain: 120, fireflies: 45, petals: 60, fog: 0, aurora: 0 };

export function Weather({ kind }: { kind: string | null }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas || !kind) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const context = canvas.getContext("2d");
    const count = COUNTS[kind] ?? 0;
    if (!context || count === 0) return;

    let frame = 0;
    const resize = () => {
      canvas.width = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    };
    resize();
    window.addEventListener("resize", resize);

    const drops = Array.from({ length: count }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      speed: 0.3 + Math.random() * (kind === "rain" ? 4 : 1.2),
      drift: (Math.random() - 0.5) * 0.6,
      size: kind === "rain" ? 1 : 1 + Math.random() * 2.5,
    }));

    const colors: Record<string, string> = {
      snow: "rgba(255,255,255,0.9)",
      rain: "rgba(180,210,255,0.6)",
      fireflies: "rgba(255,214,120,0.9)",
      petals: "rgba(255,190,214,0.85)",
    };

    const tick = () => {
      context.clearRect(0, 0, canvas.width, canvas.height);
      context.fillStyle = colors[kind] ?? colors.snow;
      for (const drop of drops) {
        drop.y += drop.speed;
        drop.x += drop.drift;
        if (drop.y > canvas.height) {
          drop.y = -4;
          drop.x = Math.random() * canvas.width;
        }
        context.beginPath();
        context.arc(drop.x, drop.y, drop.size, 0, Math.PI * 2);
        context.fill();
      }
      frame = window.requestAnimationFrame(tick);
    };
    tick();

    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("resize", resize);
    };
  }, [kind]);

  if (!kind) return null;
  return <canvas ref={ref} aria-hidden className="pointer-events-none absolute inset-0 h-full w-full" />;
}
```

В `world/src/features/castle/CastleScreen.tsx` добавить импорты `import { effectiveAppearance, lightLayer } from "@/castle/appearance";`, `import { Weather } from "@/castle/Weather";`, `import type { Appearance, CastleView } from "@/lib/v2/castle";` и `type { CSSProperties }` из `react`. В `CastleStage` принять проп `appearance: Appearance | null`, и внутри блока сцены, сразу после `<img src={CASTLE_SCENE} …/>`, добавить слои:

```tsx
          {appearance ? (
            <>
              <div
                aria-hidden
                className="pointer-events-none absolute inset-0"
                style={lightLayer(effectiveAppearance(appearance, new Date()).time) as CSSProperties}
              />
              <Weather kind={effectiveAppearance(appearance, new Date()).weather} />
            </>
          ) : null}
```

`CastleScreen` грузит облик вместе с остальными данными (`castleApi.get()`) и передаёт `data.castle.appearance` в `CastleStage`.

- [ ] **Step 4: Run tests and check the page**

Run: `cd world && npx vitest run src/castle && npx tsc --noEmit -p . && npx eslint src/castle src/features/castle`
Expected: PASS, 0 ошибок.

- [ ] **Step 5: Commit**

```bash
git add world/src/castle/appearance.ts world/src/castle/appearance.test.ts world/src/castle/Weather.tsx world/src/features/castle/CastleScreen.tsx
git commit -m "feat(castle): слои времени суток и погоды на сцене"
```

---

### Task 12: Мастерская облика в Лавке

**Files:**
- Create: `world/src/features/castle/Workshop.tsx`
- Modify: `world/src/features/castle/CastleScreen.tsx` (комната `shop`: две вкладки)
- Test: `world/e2e/castle-workshop.spec.ts`

**Interfaces:**
- Consumes: `castleApi`, `CastleView`, `CastleItem`
- Produces: `<Workshop view={CastleView} onChange={(view: CastleView) => void} />`

- [ ] **Step 1: Write the failing test**

```ts
// world/e2e/castle-workshop.spec.ts
import { expect, test } from "@playwright/test";

test("мастерская облика: покупка и применение", async ({ page }) => {
  await page.goto("/world");
  await page.waitForTimeout(1200);
  // data-spot-кнопки клавиатурные (pointer-events: none), поэтому идём через ленту локаций
  await page.getByRole("button", { name: "Лавка" }).click();

  await page.getByRole("button", { name: "Мастерская облика" }).click();
  const night = page.getByRole("button", { name: /Ночь/ });
  await expect(night).toBeVisible();

  // Без монет покупка недоступна, и сервер говорит почему
  await night.click();
  await expect(page.getByText("Не хватает монет")).toBeVisible();
});

test("закрытая вещь показывает условие", async ({ page }) => {
  await page.goto("/world");
  await page.waitForTimeout(1200);
  await page.getByRole("button", { name: "Лавка" }).click();
  await page.getByRole("button", { name: "Мастерская облика" }).click();
  await expect(page.getByText(/Словесник/)).toBeVisible();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd world && npx playwright test e2e/castle-workshop.spec.ts`
Expected: FAIL — вкладки «Мастерская облика» нет.

- [ ] **Step 3: Write the implementation**

```tsx
// world/src/features/castle/Workshop.tsx
"use client";

import { useState } from "react";

import { Button } from "@/design/Button";
import { Icon } from "@/design/Icon";
import { castleApi, type Appearance, type CastleItem, type CastleView } from "@/lib/v2/castle";

const KIND_TITLES: Record<string, string> = {
  season: "Сезон",
  time: "Время суток",
  weather: "Погода",
  banner: "Знамя",
};

type Field = "season" | "time_of_day" | "weather" | "banner_color";

const FIELD_BY_KIND: Record<string, Field> = {
  season: "season",
  time: "time_of_day",
  weather: "weather",
  banner: "banner_color",
};

/** Один слой облика для POST /appearance: strict TS не даёт собрать объект вычисляемым ключом. */
function fieldPatch(field: Field, value: string): Partial<Appearance> {
  if (field === "season") return { season: value };
  if (field === "time_of_day") return { time_of_day: value };
  if (field === "weather") return { weather: value };
  return { banner_color: value };
}

/** Витрина облика: покупка и применение. Все проверки делает сервер, здесь только показ. */
export function Workshop({ view, onChange }: { view: CastleView; onChange: (view: CastleView) => void }) {
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const act = async (run: () => Promise<CastleView>, failure: string) => {
    setBusy(true);
    try {
      onChange(await run());
      setMessage(null);
    } catch (err) {
      const detail = err instanceof Error ? err.message : "";
      setMessage(detail === "not enough coins" ? "Не хватает монет" : failure);
    } finally {
      setBusy(false);
    }
  };

  const isApplied = (item: CastleItem) => view.appearance[FIELD_BY_KIND[item.kind]] === item.value;

  return (
    <div className="space-y-4">
      {Object.entries(KIND_TITLES).map(([kind, title]) => {
        const items = view.catalog.filter((item) => item.kind === kind);
        if (items.length === 0) return null;
        return (
          <section key={kind} className="space-y-2">
            <h3 className="text-[15px] font-extrabold text-ink">{title}</h3>
            <ul className="grid grid-cols-2 gap-2">
              {items.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    disabled={busy || !item.unlocked}
                    onClick={() =>
                      item.owned
                        ? act(
                            () => castleApi.apply(fieldPatch(FIELD_BY_KIND[item.kind], item.value)),
                            "Не удалось применить",
                          )
                        : act(() => castleApi.buy(item.id), "Не удалось купить")
                    }
                    className={[
                      "flex w-full items-center justify-between gap-2 rounded-2xl px-3 py-2 text-left",
                      isApplied(item) ? "mat-brass" : "mat-enamel",
                      item.unlocked ? "" : "opacity-60",
                    ].join(" ")}
                  >
                    <span className="text-[15px] font-extrabold text-ink">{item.title_ru}</span>
                    {item.owned ? (
                      <span className="text-[13px] font-bold text-ink-soft">
                        {isApplied(item) ? "выбрано" : "есть"}
                      </span>
                    ) : item.unlocked ? (
                      <span className="inline-flex items-center gap-1 text-[15px] font-extrabold text-[#d69e00]">
                        <Icon name="coin" size={16} />
                        {item.price}
                      </span>
                    ) : (
                      <span className="text-[12px] font-bold text-ink-soft">
                        {item.requires_track === "lexicon" ? "Словесник" : "звание"} {item.requires_level} ур.
                      </span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
      {message ? <p className="text-center text-[15px] font-bold text-[#a82f25]">{message}</p> : null}
      <Button block variant="paper" onClick={() => void act(() => castleApi.get(), "Не удалось обновить")}>
        Обновить витрину
      </Button>
    </div>
  );
}
```

В `CastleScreen.tsx` комната `shop` получает две вкладки: «Припасы» (нынешний список `shop`) и «Мастерская облика» (`<Workshop …/>`). Состояние вкладки — локальный `useState<"supplies" | "workshop">("supplies")`, кнопки вкладок — `mat-enamel` / `mat-brass`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd world && npx playwright test e2e/castle-workshop.spec.ts && npx tsc --noEmit -p . && npx eslint src`
Expected: PASS, 0 ошибок.

- [ ] **Step 5: Commit**

```bash
git add world/src/features/castle/Workshop.tsx world/src/features/castle/CastleScreen.tsx world/e2e/castle-workshop.spec.ts
git commit -m "feat(castle): мастерская облика в Лавке"
```

---

### Task 13: Звания в Гнезде и в лиге

**Files:**
- Modify: `world/src/features/castle/CastleScreen.tsx` (комнаты `nest` и `glory`)
- Test: `world/e2e/castle-titles.spec.ts`

**Interfaces:**
- Consumes: `CastleView.titles`, `castleApi.wear`
- Produces: список веток с прогрессом в Гнезде; выбор носимого звания; подпись звания рядом с именем в лиге

- [ ] **Step 1: Write the failing test**

```ts
// world/e2e/castle-titles.spec.ts
import { expect, test } from "@playwright/test";

test("в Гнезде видно пять веток званий и прогресс", async ({ page }) => {
  await page.goto("/world");
  await page.waitForTimeout(1200);
  await page.getByRole("button", { name: "Гнездо" }).click();

  for (const track of ["Словесник", "Тренер", "Хранитель огня", "Чемпион", "Собиратель"]) {
    await expect(page.getByText(track, { exact: false })).toBeVisible();
  }
});

test("звание без уровня надеть нельзя", async ({ page }) => {
  await page.goto("/world");
  await page.waitForTimeout(1200);
  await page.getByRole("button", { name: "Гнездо" }).click();
  const wear = page.getByRole("button", { name: /Носить/ }).first();
  await expect(wear).toBeDisabled();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd world && npx playwright test e2e/castle-titles.spec.ts`
Expected: FAIL — названий веток на экране нет.

- [ ] **Step 3: Write the implementation**

В комнате `nest` добавить блок под карточками XP/монет/сердец:

```tsx
              <div className="space-y-2">
                <h3 className="text-[15px] font-extrabold text-ink">Звания</h3>
                <ul className="space-y-1.5">
                  {castle?.titles.map((row) => (
                    <li key={row.track} className="mat-enamel flex items-center justify-between gap-2 rounded-2xl px-3 py-2">
                      <span className="min-w-0">
                        <span className="block truncate text-[15px] font-extrabold text-ink">
                          {row.title_ru ?? row.track_title_ru}
                        </span>
                        <span className="block text-[12px] font-bold text-ink-soft">
                          {row.value} {row.unit_ru}
                          {row.next_threshold ? ` · до следующего ${row.next_threshold - row.value}` : " · максимум"}
                        </span>
                      </span>
                      <button
                        type="button"
                        disabled={row.level === 0 || row.worn}
                        onClick={() => void castleApi.wear(row.track).then(setCastle)}
                        className="shrink-0 rounded-xl px-3 py-1.5 text-[13px] font-extrabold text-ink ring-1 ring-[#3b2a1e]/25 disabled:opacity-45"
                      >
                        {row.worn ? "Надето" : "Носить"}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
```

В комнате `glory` рядом с именем игрока в таблице показывать надетое звание: строка `row.is_me` дополняется подписью из `castle?.titles.find((t) => t.worn)?.title_ru`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd world && npx playwright test e2e/castle-titles.spec.ts && npx tsc --noEmit -p .`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add world/src/features/castle/CastleScreen.tsx world/e2e/castle-titles.spec.ts
git commit -m "feat(castle): звания в Гнезде и в лиге"
```

---

### Task 14: Поздравление с новым званием после урока

**Files:**
- Modify: `world/src/lib/v2/types.ts` (тип `SessionResult`: `coins_breakdown`, `titles_gained`)
- Modify: `world/src/features/lesson/FinishScreen.tsx`
- Test: `world/src/features/lesson/FinishScreen.test.tsx`

**Interfaces:**
- Consumes: поля `coins_breakdown: Record<string, number>` и `titles_gained: { track: string; level: number; title_ru: string; coins: number }[]` из Task 5
- Produces: плашка «Новое звание» на листе результата

- [ ] **Step 1: Write the failing test**

```tsx
// world/src/features/lesson/FinishScreen.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FinishScreen } from "./FinishScreen";

const base = {
  node_id: "sp1.m1.n1",
  kind: "lesson",
  xp: 10,
  coins: 8,
  stars: 0,
  passed: true,
  accuracy: 1,
  mistakes: 0,
  duration_sec: 60,
  streak_days: 1,
  today_xp: 10,
  daily_goal_xp: 20,
  goal_reached: false,
  node_completed: true,
  next_node_id: null,
  player: { xp: 10, coins: 8, level: 1 },
  coins_breakdown: { lesson: 5, perfect: 3 },
  titles_gained: [{ track: "lexicon", level: 1, title_ru: "Собиратель слов", coins: 25 }],
};

describe("FinishScreen", () => {
  it("показывает новое звание", () => {
    render(<FinishScreen result={base} onContinue={() => {}} onRetry={() => {}} />);
    expect(screen.getByText("Собиратель слов")).toBeInTheDocument();
    expect(screen.getByText(/\+25/)).toBeInTheDocument();
  });

  it("без нового звания плашки нет", () => {
    render(
      <FinishScreen result={{ ...base, titles_gained: [] }} onContinue={() => {}} onRetry={() => {}} />,
    );
    expect(screen.queryByText("Новое звание")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd world && npx vitest run src/features/lesson/FinishScreen.test.tsx`
Expected: FAIL — поля нет в типе, плашки нет.

Если в проекте ещё нет `@testing-library/react`, установить: `cd world && npm i -D @testing-library/react @testing-library/jest-dom jsdom`, и в `vitest.config.ts` включить `environment: "jsdom"`.

- [ ] **Step 3: Write the implementation**

В `world/src/lib/v2/types.ts` в тип `SessionResult` добавить:

```ts
  coins_breakdown: Record<string, number>;
  titles_gained: { track: string; level: number; title_ru: string; coins: number }[];
```

В `FinishScreen.tsx` над кнопками:

```tsx
        {result.titles_gained.length > 0 ? (
          <div className="mat-brass mx-auto mb-3 w-full max-w-sm rounded-2xl px-4 py-3 text-center">
            <p className="text-[12px] font-bold uppercase tracking-[0.24em] text-[#5a3d12]">Новое звание</p>
            {result.titles_gained.map((title) => (
              <p key={title.track} className="text-[18px] font-extrabold text-ink">
                {title.title_ru} · +{title.coins}
              </p>
            ))}
          </div>
        ) : null}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd world && npx vitest run && npx tsc --noEmit -p .`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add world/src/features/lesson/FinishScreen.tsx world/src/features/lesson/FinishScreen.test.tsx world/src/lib/v2/types.ts
git commit -m "feat(castle): поздравление с новым званием после урока"
```

---

### Task 15: Сквозная проверка и выкладка

**Files:**
- Modify: `DEVLOG.md`

- [ ] **Step 1: Прогнать всё**

```bash
cd world-backend && .venv/bin/python -m pytest -q
cd ../world && npm test && npx tsc --noEmit -p . && npx eslint && npm run build
```

Expected: все зелёные, 0 ошибок линтера, сборка проходит.

- [ ] **Step 2: Пройти путь руками на локальном сервере**

Запустить `world-backend` и `npm run dev`, затем:
1. Пройти урок без ошибок — на листе результата видно разбивку монет и, при достижении порога, новое звание.
2. Открыть Гнездо — пять веток, у взятой можно нажать «Носить».
3. Открыть Лавку → «Мастерская облика» — купить «Ночь», применить, увидеть тёмный замок и подпись «выбрано».
4. Купить «Снегопад», применить — над замком идёт снег.
5. Нажать покупку дважды подряд — монеты списываются один раз.

- [ ] **Step 3: Записать в журнал**

Добавить в `DEVLOG.md` раздел сессии: что сделано, цифры экономики, какие таблицы появились, как проверено.

- [ ] **Step 4: Commit и выкладка**

```bash
git add DEVLOG.md && git commit -m "docs(world-v2): журнал — звания, экономика, мастерская облика"
git push origin world-v2
ssh yc-user@89.169.132.104 'cd ~/Dymova-english && git fetch origin world-v2 && git reset --hard origin/world-v2 && \
  WORLD_PLAYER_SECRET=placeholder-not-used-by-web NEXT_PUBLIC_WORLD_API=https://new.dymova-english.ru \
  docker compose -f docker-compose.world.yml up -d --build world-web world-api'
```

Внимание: здесь пересобирается и `world-api` (появился новый модуль), поэтому `WORLD_PLAYER_SECRET` нужен **настоящий** — взять у владельца, заглушка не годится.

- [ ] **Step 5: Проверить прод**

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://new.dymova-english.ru/api/v2/castle
```

Ожидание: 401 или 200 (не 404 — значит роутер поднялся). Затем открыть https://new.dymova-english.ru/world и проверить Мастерскую и Гнездо.

---

## Что не входит в этот план

- **Этап 3 — сезоны и украшения:** 4 сезонные картинки flare, спрайты украшений, точки на замке, режим примерки с лентой. Требует арта и пересчёта зон кликов, поэтому отдельный план.
- **Этап 4 — связность:** сундуки слов в Сокровищнице, испытание дня во Дворе, задания Беседки, трофеи лиги.
- Отложенные владельцем идеи: визиты к друзьям, сезонные события, питомец (см. память проекта).
