# Foxinburg World — игровой цикл School Hub: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Провести ребёнка через полный цикл первого дня в Фоксинбурге — HUD, квест, диалог с Фокси, vocabulary-челлендж и кинематографичная награда — с начислением XP/монет на сервере и восстановлением прогресса после перезагрузки.

**Architecture:** Бэкенд — расширение существующего модуля `bot/app/world/` (FastAPI + SQLite-слой): словарь из страниц сайта экспортируется в JSON, активности живут в серверных сессиях, правильные ответы клиенту не отдаются, награды идут через уже готовый идемпотентный `core.award`. Фронтенд — Next 16 + React Three Fiber, жёстко разделённый на `src/engine/*` (единственный импортёр three) и `src/game/*` (правила игры, zustand-стор, оверлеи Game OS).

**Tech Stack:** Python 3.13 + FastAPI + SQLite (`bot/`), Next.js 16.3.5 + React 19.2.8 + TypeScript strict + Tailwind 4 + @react-three/fiber 9 + drei 10 + @react-three/postprocessing 3 + zustand 5 + vitest (`world/`).

## Global Constraints

- Спека: `docs/superpowers/specs/2026-09-13-foxinburg-world-game-loop-design.md`. Арт: `docs/world/world-art-bible.md`. Архитектура: `docs/world/architecture.md`.
- Палитра строго брендовая: `world.purple #3a2953`, `world.purple-dark #241a30`, `world.yellow #f5ed75`, `world.ink #ffffff`. Teal-glow второй зоны — `#7fd8c9`. Никаких других hue.
- Шрифты: Montserrat (заголовки, числа наград), DM Sans (UI-текст). UI — на русском.
- 1 engine unit = 1 метр: Фокси ≈ 0.9 u, двери 2.2 u, школа 12–14 u. World cam: дистанция 6–8 u, FOV 35–40°, высота 2.5–3.5 u. Reward cam: 1.8 u, FOV 30°, low-angle.
- Клипы `foxi-rigged.glb` (другие имена не существуют): `Big_Wave_Hello`, `Cheer_with_Both_Hands_Up`, `Happy_jump_f`, `Running`, `Shake_It_Off_Dance`, `Walking`.
- `src/game/*` и `src/app/*` НЕ импортируют `three` ни прямо, ни через drei. Весь three — только в `src/engine/*`.
- Клиент никогда не присылает суммы наград и не получает правильные ответы до ответа на вопрос.
- Экономика — только из `bot/app/world/config.py`, никаких чисел по коду.
- Тесты бэкенда: `cd bot && .venv313/bin/python -m pytest`. Базовая линия перед началом — 1155 passed, она не должна падать.
- Страницы сайта `prototype/*` не изменяются ни одной задачей этого плана.
- TypeScript strict: `any` запрещён без комментария-обоснования.
- Коммиты — Conventional Commits, каждая задача заканчивается коммитом с trailer:
  `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>` и
  `Claude-Session: https://claude.ai/code/session_01BDXQ3YRYWaMxj6V412E2En`

## File Structure

**Создаются (бэкенд):**
- `scripts/export_world_vocabulary.py` — генератор JSON из страниц сайта (build-time, в рантайме не импортируется)
- `bot/app/world/data/vocabulary.json` — 16 тем, ~460 слов (коммитится)
- `bot/app/world/vocabulary.py` — загрузка тем и сборка вопросов
- `bot/app/world/activities.py` — сессии активностей: start / answer / finish
- `bot/tests/test_world_vocabulary.py`, `bot/tests/test_world_activities.py`

**Модифицируются (бэкенд):**
- `bot/app/world/db.py` — таблица `activity_sessions` в `SCHEMA`
- `bot/app/world/config.py` — бонус за идеальный результат
- `bot/app/world/core.py` — `advance_quest_step`
- `bot/app/world/api.py` — маршруты активностей и шага квеста

**Создаются (фронтенд):** `world/src/engine/{Stage,Lighting,Postfx,Fireflies,Ground,SchoolBuilding,CameraRig,Foxi,FoxCoin,quality}.tsx|ts`
(в v1 единственный интерактивный объект — школа, поэтому hover/click живут прямо в `SchoolBuilding`;
отдельный `Hotspot` появится, когда объектов станет больше одного), `world/src/game/{store.ts,phases.ts,hud/Hud.tsx,dialogue/FoxiDialogue.tsx,activities/VocabularyChallenge.tsx,reward/RewardCinematic.tsx}`, `world/src/ui/{Glass.tsx,Button.tsx,Bar.tsx}`, `world/src/app/world/page.tsx`, `world/src/game/phases.test.ts`, `world/vitest.config.ts`

**Модифицируются (фронтенд):** `world/src/lib/api.ts`, `world/src/app/page.tsx`, `world/src/app/globals.css`, `world/src/app/layout.tsx`, `world/package.json`

---

### Task 1: Экспорт словаря сайта в JSON

**Files:**
- Create: `scripts/export_world_vocabulary.py`
- Create: `bot/tests/test_world_vocabulary.py`
- Create (генерируется скриптом, коммитится): `bot/app/world/data/vocabulary.json`

**Interfaces:**
- Consumes: списки `WORDS_*` (кортежи `(en, ipa, ru, example_en, example_ru)`) в `prototype/build_subpages.py:3975+`, `prototype/pages_words2.py:12+`, `prototype/pages_words3.py:12+`; канонический список 16 тем `(slug, title)` в `prototype/build_subpages.py:3888-3896`.
- Produces: `bot/app/world/data/vocabulary.json` вида
  `{"themes": [{"id": "zhivotnye", "title_ru": "Животные", "words": [{"en","ipa","ru","example_en","example_ru"}]}]}`.

- [ ] **Step 1: Написать падающий тест**

Создать `bot/tests/test_world_vocabulary.py`:

```python
"""Экспорт словаря сайта в данные World и сборка вопросов челленджа."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "export_world_vocabulary.py"


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    out = tmp_path_factory.mktemp("vocab") / "vocabulary.json"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--out", str(out)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(out.read_text(encoding="utf-8"))


def test_export_has_all_sixteen_themes(exported):
    ids = [t["id"] for t in exported["themes"]]
    assert len(ids) == 16
    assert "zhivotnye" in ids and "vremya-i-chisla" in ids and "prazdniki" in ids
    assert len(set(ids)) == 16


def test_export_word_shape_and_volume(exported):
    total = sum(len(t["words"]) for t in exported["themes"])
    assert total >= 400
    animals = next(t for t in exported["themes"] if t["id"] == "zhivotnye")
    assert animals["title_ru"] == "Животные"
    cat = next(w for w in animals["words"] if w["en"] == "cat")
    assert cat == {
        "en": "cat", "ipa": "[kæt]", "ru": "кошка",
        "example_en": "The cat sleeps on the sofa.",
        "example_ru": "Кошка спит на диване.",
    }


def test_every_theme_has_enough_words_for_a_question(exported):
    for theme in exported["themes"]:
        assert len(theme["words"]) >= 10, theme["id"]
```

- [ ] **Step 2: Убедиться, что тест падает**

Run: `cd bot && .venv313/bin/python -m pytest tests/test_world_vocabulary.py -v`
Expected: FAIL — скрипт не существует (`returncode != 0`, в stderr «can't open file»).

- [ ] **Step 3: Написать генератор**

Создать `scripts/export_world_vocabulary.py`:

```python
#!/usr/bin/env python3
"""Экспорт тематического словаря сайта в данные Foxinburg World.

Читает списки WORDS_* из исходников страниц через ast (без импорта —
модули сайта при импорте строят страницы). Страницы сайта не изменяются.

Запуск: python3 scripts/export_world_vocabulary.py
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOURCES = [
    REPO / "prototype" / "build_subpages.py",
    REPO / "prototype" / "pages_words2.py",
    REPO / "prototype" / "pages_words3.py",
]
DEFAULT_OUT = REPO / "bot" / "app" / "world" / "data" / "vocabulary.json"

# Имя списка в исходнике -> slug темы на сайте.
VAR_TO_SLUG = {
    "WORDS_ZHIVOTNYE": "zhivotnye", "WORDS_EDA": "eda", "WORDS_SHKOLA": "shkola",
    "WORDS_SEMA": "semya", "WORDS_TSVETA": "tsveta", "WORDS_PROFESSII": "professii",
    "WORDS_ODEZHDA": "odezhda", "WORDS_POGODA": "pogoda", "WORDS_TRANSPORT": "transport",
    "WORDS_DOM": "dom", "WORDS_SPORT": "sport", "WORDS_PUTESHESTVIYA": "puteshestviya",
    "WORDS_VREMYA": "vremya-i-chisla", "WORDS_HOBBI": "hobbi",
    "WORDS_PRIRODA": "priroda", "WORDS_PRAZDNIKI": "prazdniki",
}
# Канонические названия тем — из build_subpages.make_words_page (other_topics).
SLUG_TO_TITLE = {
    "zhivotnye": "Животные", "eda": "Еда", "shkola": "Школа", "semya": "Семья",
    "tsveta": "Цвета", "professii": "Профессии", "odezhda": "Одежда",
    "pogoda": "Погода", "transport": "Транспорт", "dom": "Дом", "sport": "Спорт",
    "puteshestviya": "Путешествия", "vremya-i-chisla": "Время и числа",
    "hobbi": "Хобби", "priroda": "Природа", "prazdniki": "Праздники",
}
FIELDS = ("en", "ipa", "ru", "example_en", "example_ru")


def extract_lists(path: Path) -> dict[str, list[tuple]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: dict[str, list[tuple]] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or target.id not in VAR_TO_SLUG:
            continue
        found[target.id] = ast.literal_eval(node.value)
    return found


def build_themes() -> list[dict]:
    raw: dict[str, list[tuple]] = {}
    for source in SOURCES:
        raw.update(extract_lists(source))
    missing = set(VAR_TO_SLUG) - set(raw)
    if missing:
        raise SystemExit(f"не найдены списки слов: {sorted(missing)}")
    themes = []
    for var, slug in VAR_TO_SLUG.items():
        words = [dict(zip(FIELDS, row)) for row in raw[var]]
        themes.append({"id": slug, "title_ru": SLUG_TO_TITLE[slug], "words": words})
    themes.sort(key=lambda t: t["id"])
    return themes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    themes = build_themes()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps({"themes": themes}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    total = sum(len(t["words"]) for t in themes)
    print(f"{args.out}: {len(themes)} тем, {total} слов")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Убедиться, что тест проходит**

Run: `cd bot && .venv313/bin/python -m pytest tests/test_world_vocabulary.py -v`
Expected: PASS — 3 теста.

- [ ] **Step 5: Сгенерировать рабочий файл данных**

Run: `python3 scripts/export_world_vocabulary.py`
Expected: вывод вида `.../bot/app/world/data/vocabulary.json: 16 тем, 4NN слов`.

- [ ] **Step 6: Коммит**

```bash
git add scripts/export_world_vocabulary.py bot/tests/test_world_vocabulary.py bot/app/world/data/vocabulary.json
git commit -m "feat(world): экспорт словаря сайта (16 тем) в данные мира"
```

---

### Task 2: Сборка вопросов челленджа

**Files:**
- Create: `bot/app/world/vocabulary.py`
- Modify: `bot/tests/test_world_vocabulary.py` (дописать тесты в конец)

**Interfaces:**
- Consumes: `bot/app/world/data/vocabulary.json` из Task 1.
- Produces: `vocabulary.load_themes() -> dict[str, dict]`; `vocabulary.build_questions(theme_id: str, count: int = 5, seed: int | None = None) -> list[dict]`, где вопрос = `{"en","ipa","example_en","example_ru","options": list[str], "correct_index": int}`; исключение `vocabulary.ThemeNotFound`.

- [ ] **Step 1: Написать падающий тест**

Дописать в конец `bot/tests/test_world_vocabulary.py`:

```python
from app.world import vocabulary


def test_build_questions_shape():
    questions = vocabulary.build_questions("zhivotnye", count=5, seed=42)
    assert len(questions) == 5
    for q in questions:
        assert len(q["options"]) == 4
        assert len(set(q["options"])) == 4
        assert 0 <= q["correct_index"] < 4
        assert q["en"] and q["ipa"]


def test_build_questions_correct_option_is_the_translation():
    themes = vocabulary.load_themes()
    by_en = {w["en"]: w["ru"] for w in themes["zhivotnye"]["words"]}
    for q in vocabulary.build_questions("zhivotnye", count=5, seed=7):
        assert q["options"][q["correct_index"]] == by_en[q["en"]]


def test_build_questions_deterministic_with_seed():
    a = vocabulary.build_questions("eda", count=5, seed=1)
    b = vocabulary.build_questions("eda", count=5, seed=1)
    c = vocabulary.build_questions("eda", count=5, seed=2)
    assert a == b
    assert a != c


def test_build_questions_unknown_theme():
    with pytest.raises(vocabulary.ThemeNotFound):
        vocabulary.build_questions("dragons")
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `cd bot && .venv313/bin/python -m pytest tests/test_world_vocabulary.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.world.vocabulary'` (ошибка импорта на сборе тестов).

- [ ] **Step 3: Реализовать модуль**

Создать `bot/app/world/vocabulary.py`:

```python
"""Словарь мира: темы из данных сайта и сборка вопросов челленджа.

Данные — data/vocabulary.json (генерируется scripts/export_world_vocabulary.py).
Правильный ответ (correct_index) остаётся на сервере: в HTTP-ответ он
не попадает (§84).
"""
from __future__ import annotations

import json
import random
from functools import lru_cache
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent / "data" / "vocabulary.json"
OPTIONS_PER_QUESTION = 4


class ThemeNotFound(Exception):
    pass


@lru_cache(maxsize=1)
def load_themes() -> dict[str, dict]:
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return {theme["id"]: theme for theme in raw["themes"]}


def build_questions(theme_id: str, count: int = 5, seed: int | None = None) -> list[dict]:
    """Вопросы «английское слово → 4 варианта перевода», варианты из той же темы."""
    themes = load_themes()
    theme = themes.get(theme_id)
    if theme is None:
        raise ThemeNotFound(f"тема {theme_id!r} не найдена")
    words = theme["words"]
    if len(words) < OPTIONS_PER_QUESTION:
        raise ThemeNotFound(f"в теме {theme_id!r} слишком мало слов")

    rng = random.Random(seed)
    questions = []
    for word in rng.sample(words, min(count, len(words))):
        distractors = [w["ru"] for w in words if w["ru"] != word["ru"]]
        options = rng.sample(distractors, OPTIONS_PER_QUESTION - 1) + [word["ru"]]
        rng.shuffle(options)
        questions.append({
            "en": word["en"],
            "ipa": word["ipa"],
            "example_en": word["example_en"],
            "example_ru": word["example_ru"],
            "options": options,
            "correct_index": options.index(word["ru"]),
        })
    return questions
```

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `cd bot && .venv313/bin/python -m pytest tests/test_world_vocabulary.py -v`
Expected: PASS — 7 тестов.

- [ ] **Step 5: Коммит**

```bash
git add bot/app/world/vocabulary.py bot/tests/test_world_vocabulary.py
git commit -m "feat(world): сборка вопросов vocabulary-челленджа из словаря"
```

---

### Task 3: Продвижение шага квеста на сервере

**Files:**
- Modify: `bot/app/world/core.py` (дописать в конец секции квестов, после `start_quest`)
- Modify: `bot/tests/test_world.py` (дописать тесты в конец)

**Interfaces:**
- Consumes: `core.get_player`, `core.get_quest`, таблица `quest_progress`.
- Produces: `core.advance_quest_step(external_key: str, quest_id: str, action: str, target: str) -> dict` → `{"quest_id", "step", "steps_total", "all_steps_done"}`; при несовпадении шага — `core.Conflict`.

- [ ] **Step 1: Написать падающий тест**

Дописать в конец `bot/tests/test_world.py`:

```python
def test_advance_quest_step_in_order():
    core.get_or_create_player("child-step")
    core.start_quest("child-step", "first-day-at-foxinburg")
    r1 = core.advance_quest_step("child-step", "first-day-at-foxinburg", "visit", "school-hub")
    assert r1["step"] == 1 and r1["steps_total"] == 3 and r1["all_steps_done"] is False
    r2 = core.advance_quest_step("child-step", "first-day-at-foxinburg", "talk", "foxi")
    assert r2["step"] == 2
    r3 = core.advance_quest_step("child-step", "first-day-at-foxinburg",
                                 "activity", "vocabulary-challenge-1")
    assert r3["step"] == 3 and r3["all_steps_done"] is True


def test_advance_quest_step_rejects_wrong_step():
    core.get_or_create_player("child-step2")
    core.start_quest("child-step2", "first-day-at-foxinburg")
    with pytest.raises(core.Conflict):
        core.advance_quest_step("child-step2", "first-day-at-foxinburg", "talk", "foxi")


def test_advance_quest_step_requires_started_quest():
    core.get_or_create_player("child-step3")
    with pytest.raises(core.Conflict):
        core.advance_quest_step("child-step3", "first-day-at-foxinburg", "visit", "school-hub")


def test_quest_progress_survives_reload():
    core.get_or_create_player("child-step4")
    core.start_quest("child-step4", "first-day-at-foxinburg")
    core.advance_quest_step("child-step4", "first-day-at-foxinburg", "visit", "school-hub")
    quest = next(q for q in core.list_quests("child-step4")
                 if q["id"] == "first-day-at-foxinburg")
    assert quest["step"] == 1 and quest["status"] == "active"
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `cd bot && .venv313/bin/python -m pytest tests/test_world.py -v -k advance`
Expected: FAIL — `AttributeError: module 'app.world.core' has no attribute 'advance_quest_step'`.

- [ ] **Step 3: Реализовать**

Дописать в `bot/app/world/core.py` сразу после функции `start_quest`:

```python
def advance_quest_step(external_key: str, quest_id: str, action: str,
                       target: str) -> dict:
    """Двигает квест на шаг вперёд, если действие совпало с текущим шагом.

    Порядок шагов проверяет сервер: клиент не может перепрыгнуть шаг (§84).
    """
    player = get_player(external_key)
    quest = get_quest(quest_id)
    steps = quest["config"].get("steps", [])
    conn = get_conn()
    row = conn.execute(
        "SELECT status, step FROM quest_progress WHERE player_id=? AND quest_id=?",
        (player["id"], quest_id),
    ).fetchone()
    if row is None:
        raise Conflict("quest not started")
    if row["status"] == "completed":
        raise Conflict("quest already completed")
    step = row["step"]
    if step >= len(steps):
        raise Conflict("all steps already done")
    current = steps[step]
    if current["action"] != action or current["target"] != target:
        raise Conflict(
            f"step mismatch: expected {current['action']}:{current['target']}"
        )
    new_step = step + 1
    conn.execute(
        "UPDATE quest_progress SET step=? WHERE player_id=? AND quest_id=?",
        (new_step, player["id"], quest_id),
    )
    return {
        "quest_id": quest_id,
        "step": new_step,
        "steps_total": len(steps),
        "all_steps_done": new_step >= len(steps),
    }
```

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `cd bot && .venv313/bin/python -m pytest tests/test_world.py -v`
Expected: PASS — 12 тестов (8 прежних + 4 новых).

- [ ] **Step 5: Коммит**

```bash
git add bot/app/world/core.py bot/tests/test_world.py
git commit -m "feat(world): серверное продвижение шагов квеста"
```

---

### Task 4: Сессия активности — start

**Files:**
- Modify: `bot/app/world/db.py` (добавить таблицу в конец строки `SCHEMA`)
- Modify: `bot/app/world/config.py` (добавить реестр активностей и бонус)
- Create: `bot/app/world/activities.py`
- Create: `bot/tests/test_world_activities.py`

**Interfaces:**
- Consumes: `core.get_player`, `core.NotFound`, `core.Conflict`, `vocabulary.build_questions`.
- Produces: `activities.start(external_key: str, activity_id: str, seed: int | None = None) -> dict` → `{"session_id","activity_id","title_ru","total","questions":[{"index","en","ipa","example_en","options"}]}` — **без** `correct_index` и без `example_ru`; таблица `activity_sessions`; `config.ACTIVITIES`.

- [ ] **Step 1: Написать падающий тест**

Создать `bot/tests/test_world_activities.py`:

```python
"""Активности World: серверные сессии челленджа, проверка ответов, награда."""
import json

import pytest

from app.world import activities, core
from app.world.db import get_conn, reset_for_tests


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    reset_for_tests(str(tmp_path / "world.sqlite"))
    core.seed_quests()
    core.get_or_create_player("child-1", "Мария")
    yield
    reset_for_tests(str(tmp_path / "world2.sqlite"))


def test_start_returns_questions_without_answers():
    session = activities.start("child-1", "vocabulary-challenge-1", seed=1)
    assert session["total"] == 5
    assert len(session["questions"]) == 5
    for i, q in enumerate(session["questions"]):
        assert q["index"] == i
        assert len(q["options"]) == 4
        assert "correct_index" not in q
        assert "example_ru" not in q


def test_start_keeps_answers_on_server():
    session = activities.start("child-1", "vocabulary-challenge-1", seed=1)
    row = get_conn().execute(
        "SELECT payload FROM activity_sessions WHERE id=?", (session["session_id"],)
    ).fetchone()
    payload = json.loads(row["payload"])
    assert all("correct_index" in q for q in payload["questions"])


def test_start_unknown_activity():
    with pytest.raises(core.NotFound):
        activities.start("child-1", "no-such-activity")
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `cd bot && .venv313/bin/python -m pytest tests/test_world_activities.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.world.activities'`.

- [ ] **Step 3: Добавить таблицу сессий**

В `bot/app/world/db.py` дописать в конец строки `SCHEMA` (перед закрывающими кавычками, после блока `world_state`):

```sql
-- Сессия активности: вопросы и правильные ответы живут на сервере (§84).
CREATE TABLE IF NOT EXISTS activity_sessions (
    id           TEXT PRIMARY KEY,
    player_id    INTEGER NOT NULL REFERENCES players(id),
    activity_id  TEXT NOT NULL,
    payload      TEXT NOT NULL,               -- {questions:[...с correct_index]}
    answers      TEXT NOT NULL DEFAULT '{}',  -- {"0": {"choice":2,"correct":true}}
    status       TEXT NOT NULL DEFAULT 'active',  -- active|completed
    score        INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT
);
```

- [ ] **Step 4: Добавить реестр активностей в конфиг**

Дописать в конец `bot/app/world/config.py`:

```python
# Активности (§68): data-driven описание, связь с шагом квеста.
ACTIVITIES = {
    "vocabulary-challenge-1": {
        "kind": "vocabulary",
        "title_ru": "Первый английский челлендж",
        "theme": "zhivotnye",
        "questions": 5,
        "quest_id": "first-day-at-foxinburg",
    },
}
# Бонус за безошибочное прохождение активности.
PERFECT_BONUS = {"xp": 10, "coins": 5}
```

- [ ] **Step 5: Реализовать start**

Создать `bot/app/world/activities.py`:

```python
"""Активности мира: серверные сессии обучающих мини-игр (§68).

Вопросы и правильные ответы хранятся на сервере; клиент получает только
формулировки и варианты, ответ проверяется здесь, награда идёт через
core.award — идемпотентно (§84, §160).
"""
from __future__ import annotations

import json
import uuid

from . import config, core, vocabulary
from .db import get_conn


def _activity(activity_id: str) -> dict:
    spec = config.ACTIVITIES.get(activity_id)
    if spec is None:
        raise core.NotFound(f"activity {activity_id!r} not found")
    return spec


def start(external_key: str, activity_id: str, seed: int | None = None) -> dict:
    """Создаёт сессию и отдаёт вопросы без правильных ответов."""
    player = core.get_player(external_key)
    spec = _activity(activity_id)
    questions = vocabulary.build_questions(spec["theme"], spec["questions"], seed)
    session_id = str(uuid.uuid4())
    get_conn().execute(
        "INSERT INTO activity_sessions (id, player_id, activity_id, payload)"
        " VALUES (?,?,?,?)",
        (session_id, player["id"], activity_id,
         json.dumps({"questions": questions}, ensure_ascii=False)),
    )
    return {
        "session_id": session_id,
        "activity_id": activity_id,
        "title_ru": spec["title_ru"],
        "total": len(questions),
        "questions": [
            {
                "index": i,
                "en": q["en"],
                "ipa": q["ipa"],
                "example_en": q["example_en"],
                "options": q["options"],
            }
            for i, q in enumerate(questions)
        ],
    }
```

- [ ] **Step 6: Убедиться, что тесты проходят**

Run: `cd bot && .venv313/bin/python -m pytest tests/test_world_activities.py -v`
Expected: PASS — 3 теста.

- [ ] **Step 7: Коммит**

```bash
git add bot/app/world/activities.py bot/app/world/db.py bot/app/world/config.py bot/tests/test_world_activities.py
git commit -m "feat(world): серверные сессии активностей, выдача вопросов без ответов"
```

---

### Task 5: Проверка ответа

**Files:**
- Modify: `bot/app/world/activities.py`
- Modify: `bot/tests/test_world_activities.py`

**Interfaces:**
- Consumes: `activities.start` из Task 4.
- Produces: `activities.answer(external_key: str, session_id: str, index: int, choice: int) -> dict` → `{"index","correct","correct_index","example_en","example_ru","answered","total"}`; повторный ответ на тот же вопрос и ответ в завершённой сессии — `core.Conflict`; чужая сессия — `core.NotFound`.

- [ ] **Step 1: Написать падающий тест**

Дописать в `bot/tests/test_world_activities.py`:

```python
def _correct_index(session_id: str, index: int) -> int:
    row = get_conn().execute(
        "SELECT payload FROM activity_sessions WHERE id=?", (session_id,)
    ).fetchone()
    return json.loads(row["payload"])["questions"][index]["correct_index"]


def test_answer_correct_and_wrong():
    s = activities.start("child-1", "vocabulary-challenge-1", seed=3)
    sid = s["session_id"]
    right = _correct_index(sid, 0)
    r = activities.answer("child-1", sid, 0, right)
    assert r["correct"] is True
    assert r["correct_index"] == right
    assert r["answered"] == 1 and r["total"] == 5
    assert r["example_ru"]

    wrong = (_correct_index(sid, 1) + 1) % 4
    r2 = activities.answer("child-1", sid, 1, wrong)
    assert r2["correct"] is False
    assert r2["correct_index"] == _correct_index(sid, 1)


def test_answer_twice_on_same_question_conflicts():
    s = activities.start("child-1", "vocabulary-challenge-1", seed=3)
    activities.answer("child-1", s["session_id"], 0, 0)
    with pytest.raises(core.Conflict):
        activities.answer("child-1", s["session_id"], 0, 1)


def test_answer_out_of_range_question():
    s = activities.start("child-1", "vocabulary-challenge-1", seed=3)
    with pytest.raises(core.NotFound):
        activities.answer("child-1", s["session_id"], 99, 0)


def test_answer_in_foreign_session_is_not_found():
    core.get_or_create_player("child-2", "Пётр")
    s = activities.start("child-1", "vocabulary-challenge-1", seed=3)
    with pytest.raises(core.NotFound):
        activities.answer("child-2", s["session_id"], 0, 0)
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `cd bot && .venv313/bin/python -m pytest tests/test_world_activities.py -v -k answer`
Expected: FAIL — `AttributeError: module 'app.world.activities' has no attribute 'answer'`.

- [ ] **Step 3: Реализовать**

Дописать в `bot/app/world/activities.py`:

```python
def _load_session(external_key: str, session_id: str) -> tuple[dict, dict, dict]:
    """Возвращает (игрок, строка сессии как dict, payload). Чужая сессия — NotFound."""
    player = core.get_player(external_key)
    row = get_conn().execute(
        "SELECT * FROM activity_sessions WHERE id=? AND player_id=?",
        (session_id, player["id"]),
    ).fetchone()
    if row is None:
        raise core.NotFound(f"activity session {session_id!r} not found")
    return player, dict(row), json.loads(row["payload"])


def answer(external_key: str, session_id: str, index: int, choice: int) -> dict:
    """Сверяет ответ с серверной копией и запоминает его в сессии."""
    _player, session, payload = _load_session(external_key, session_id)
    if session["status"] == "completed":
        raise core.Conflict("activity already completed")
    questions = payload["questions"]
    if not 0 <= index < len(questions):
        raise core.NotFound(f"question {index} not found")

    answers = json.loads(session["answers"])
    if str(index) in answers:
        raise core.Conflict(f"question {index} already answered")

    question = questions[index]
    correct = int(choice) == question["correct_index"]
    answers[str(index)] = {"choice": int(choice), "correct": correct}
    get_conn().execute(
        "UPDATE activity_sessions SET answers=? WHERE id=?",
        (json.dumps(answers, ensure_ascii=False), session_id),
    )
    return {
        "index": index,
        "correct": correct,
        "correct_index": question["correct_index"],
        "example_en": question["example_en"],
        "example_ru": question["example_ru"],
        "answered": len(answers),
        "total": len(questions),
    }
```

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `cd bot && .venv313/bin/python -m pytest tests/test_world_activities.py -v`
Expected: PASS — 7 тестов.

- [ ] **Step 5: Коммит**

```bash
git add bot/app/world/activities.py bot/tests/test_world_activities.py
git commit -m "feat(world): серверная проверка ответов челленджа"
```

---

### Task 6: Завершение активности — награда, идемпотентность, шаг квеста

**Files:**
- Modify: `bot/app/world/activities.py`
- Modify: `bot/tests/test_world_activities.py`

**Interfaces:**
- Consumes: `activities.answer` (Task 5), `core.award`, `core.advance_quest_step` (Task 3), `config.XP_REWARDS["vocabulary_challenge"]`, `config.COIN_REWARDS["vocabulary_challenge"]`, `config.PERFECT_BONUS`.
- Produces: `activities.finish(external_key: str, session_id: str, idempotency_key: str | None = None) -> dict` → `{"session_id","activity_id","score","total","perfect","xp_delta","coins_delta","level_up","new_level","new_title","player","quest": {...} | None}`; незавершённая сессия — `core.Conflict`; повторный вызов — те же цифры, без второго начисления.

- [ ] **Step 1: Написать падающий тест**

Дописать в `bot/tests/test_world_activities.py`:

```python
def _answer_all(sid: str, *, correct: bool) -> None:
    for i in range(5):
        right = _correct_index(sid, i)
        activities.answer("child-1", sid, i, right if correct else (right + 1) % 4)


def test_finish_awards_xp_and_coins_from_config():
    from app.world import config
    core.start_quest("child-1", "first-day-at-foxinburg")
    s = activities.start("child-1", "vocabulary-challenge-1", seed=5)
    _answer_all(s["session_id"], correct=False)
    r = activities.finish("child-1", s["session_id"])
    assert r["score"] == 0 and r["total"] == 5 and r["perfect"] is False
    assert r["xp_delta"] == config.XP_REWARDS["vocabulary_challenge"]
    assert r["coins_delta"] == config.COIN_REWARDS["vocabulary_challenge"]


def test_finish_perfect_run_adds_bonus():
    from app.world import config
    core.start_quest("child-1", "first-day-at-foxinburg")
    s = activities.start("child-1", "vocabulary-challenge-1", seed=6)
    _answer_all(s["session_id"], correct=True)
    r = activities.finish("child-1", s["session_id"])
    assert r["score"] == 5 and r["perfect"] is True
    assert r["xp_delta"] == (config.XP_REWARDS["vocabulary_challenge"]
                             + config.PERFECT_BONUS["xp"])
    assert r["coins_delta"] == (config.COIN_REWARDS["vocabulary_challenge"]
                                + config.PERFECT_BONUS["coins"])


def test_finish_is_idempotent():
    core.start_quest("child-1", "first-day-at-foxinburg")
    s = activities.start("child-1", "vocabulary-challenge-1", seed=7)
    _answer_all(s["session_id"], correct=True)
    first = activities.finish("child-1", s["session_id"])
    second = activities.finish("child-1", s["session_id"])
    assert second["xp_delta"] == first["xp_delta"]
    assert second["player"]["xp"] == first["player"]["xp"]
    rows = get_conn().execute(
        "SELECT COUNT(*) c FROM xp_transactions WHERE type='ACTIVITY_REWARD'"
    ).fetchone()
    assert rows["c"] == 1


def test_finish_requires_all_answers():
    s = activities.start("child-1", "vocabulary-challenge-1", seed=8)
    activities.answer("child-1", s["session_id"], 0, 0)
    with pytest.raises(core.Conflict):
        activities.finish("child-1", s["session_id"])


def test_finish_advances_quest_step():
    core.start_quest("child-1", "first-day-at-foxinburg")
    core.advance_quest_step("child-1", "first-day-at-foxinburg", "visit", "school-hub")
    core.advance_quest_step("child-1", "first-day-at-foxinburg", "talk", "foxi")
    s = activities.start("child-1", "vocabulary-challenge-1", seed=9)
    _answer_all(s["session_id"], correct=True)
    r = activities.finish("child-1", s["session_id"])
    assert r["quest"]["step"] == 3 and r["quest"]["all_steps_done"] is True


def test_finish_without_matching_quest_step_still_awards():
    core.start_quest("child-1", "first-day-at-foxinburg")
    s = activities.start("child-1", "vocabulary-challenge-1", seed=10)
    _answer_all(s["session_id"], correct=True)
    r = activities.finish("child-1", s["session_id"])
    assert r["quest"] is None
    assert r["xp_delta"] > 0
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `cd bot && .venv313/bin/python -m pytest tests/test_world_activities.py -v -k finish`
Expected: FAIL — `AttributeError: module 'app.world.activities' has no attribute 'finish'`.

- [ ] **Step 3: Реализовать**

Дописать в `bot/app/world/activities.py`:

```python
def finish(external_key: str, session_id: str,
           idempotency_key: str | None = None) -> dict:
    """Закрывает сессию, начисляет награду и двигает шаг квеста.

    Награда считается сервером по config; повторный вызов ничего не
    начисляет второй раз и возвращает те же цифры (§160).
    """
    _player, session, payload = _load_session(external_key, session_id)
    questions = payload["questions"]
    answers = json.loads(session["answers"])
    if len(answers) < len(questions):
        raise core.Conflict("activity not finished: not all questions answered")

    score = sum(1 for a in answers.values() if a["correct"])
    perfect = score == len(questions)
    spec = _activity(session["activity_id"])
    xp = config.XP_REWARDS["vocabulary_challenge"]
    coins = config.COIN_REWARDS["vocabulary_challenge"]
    if perfect:
        xp += config.PERFECT_BONUS["xp"]
        coins += config.PERFECT_BONUS["coins"]

    result = core.award(
        external_key,
        xp=xp, coins=coins,
        source=session["activity_id"],
        type_="ACTIVITY_REWARD",
        idempotency_key=idempotency_key or f"activity-finish:{session_id}",
    )
    # Суммы фиксируются в сессии при первом завершении: повтор возвращает
    # их же, хотя core.award второй раз ничего не начисляет (§160).
    if session["status"] != "completed":
        payload["reward"] = {"xp": xp, "coins": coins}
        get_conn().execute(
            "UPDATE activity_sessions SET status='completed', score=?, payload=?,"
            " completed_at=datetime('now') WHERE id=?",
            (score, json.dumps(payload, ensure_ascii=False), session_id),
        )
    reward = payload.get("reward", {"xp": xp, "coins": coins})

    quest_result = None
    quest_id = spec.get("quest_id")
    if quest_id:
        try:
            quest_result = core.advance_quest_step(
                external_key, quest_id, "activity", session["activity_id"]
            )
        except core.Conflict:
            quest_result = None  # шаг уже пройден или квест на другом шаге

    return {
        "session_id": session_id,
        "activity_id": session["activity_id"],
        "score": score,
        "total": len(questions),
        "perfect": perfect,
        "xp_delta": reward["xp"],
        "coins_delta": reward["coins"],
        "level_up": result["level_up"],
        "new_level": result["new_level"],
        "new_title": result["new_title"],
        "player": result["player"],
        "quest": quest_result,
    }
```

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `cd bot && .venv313/bin/python -m pytest tests/test_world_activities.py -v`
Expected: PASS — 13 тестов.

- [ ] **Step 5: Полный прогон сьюта бота**

Run: `cd bot && .venv313/bin/python -m pytest -q`
Expected: PASS — не меньше 1168 passed (1155 базовых + 13 новых), 0 failed.

- [ ] **Step 6: Коммит**

```bash
git add bot/app/world/activities.py bot/tests/test_world_activities.py
git commit -m "feat(world): награда за челлендж, идемпотентность, продвижение квеста"
```

---

### Task 7: HTTP-маршруты активностей и шага квеста

**Files:**
- Modify: `bot/app/world/api.py`
- Create: `bot/tests/test_world_api.py`

**Interfaces:**
- Consumes: `activities.start/answer/finish`, `core.advance_quest_step`.
- Produces: `POST /api/world/quests/{quest_id}/step` (тело `{"action","target"}`), `POST /api/world/activities/start` (тело `{"activity_id"}`), `POST /api/world/activities/{session_id}/answer` (тело `{"index","choice"}`), `POST /api/world/activities/{session_id}/finish` (тело `{"idempotency_key"}` или пустое). Все — с заголовком `X-World-Player`.

- [ ] **Step 1: Написать падающий тест**

Создать `bot/tests/test_world_api.py`:

```python
"""HTTP-контракт /api/world/* — маршруты цикла School Hub."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.world import api as world_api
from app.world import core
from app.world.db import reset_for_tests

HEADERS = {"X-World-Player": "child-api"}


@pytest.fixture()
def client(tmp_path):
    reset_for_tests(str(tmp_path / "world.sqlite"))
    core.seed_quests()
    app = FastAPI()
    app.include_router(world_api.router)
    with TestClient(app) as c:
        c.post("/api/world/players", json={"display_name": "Мария"}, headers=HEADERS)
        yield c
    reset_for_tests(str(tmp_path / "world2.sqlite"))


def test_requires_player_header(client):
    assert client.get("/api/world/player").status_code == 401


def test_quest_step_route(client):
    client.post("/api/world/quests/first-day-at-foxinburg/start", headers=HEADERS)
    r = client.post("/api/world/quests/first-day-at-foxinburg/step",
                    json={"action": "visit", "target": "school-hub"}, headers=HEADERS)
    assert r.status_code == 200 and r.json()["step"] == 1
    bad = client.post("/api/world/quests/first-day-at-foxinburg/step",
                      json={"action": "visit", "target": "school-hub"}, headers=HEADERS)
    assert bad.status_code == 409


def test_activity_flow_over_http(client):
    client.post("/api/world/quests/first-day-at-foxinburg/start", headers=HEADERS)
    started = client.post("/api/world/activities/start",
                          json={"activity_id": "vocabulary-challenge-1"},
                          headers=HEADERS).json()
    sid = started["session_id"]
    assert len(started["questions"]) == 5
    assert all("correct_index" not in q for q in started["questions"])

    for i in range(5):
        r = client.post(f"/api/world/activities/{sid}/answer",
                        json={"index": i, "choice": 0}, headers=HEADERS)
        assert r.status_code == 200
        assert isinstance(r.json()["correct"], bool)

    fin = client.post(f"/api/world/activities/{sid}/finish",
                      json={"idempotency_key": "http-1"}, headers=HEADERS)
    assert fin.status_code == 200
    body = fin.json()
    assert body["total"] == 5 and body["player"]["xp"] > 0


def test_activity_unknown_session_is_404(client):
    r = client.post("/api/world/activities/nope/answer",
                    json={"index": 0, "choice": 0}, headers=HEADERS)
    assert r.status_code == 404
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `cd bot && .venv313/bin/python -m pytest tests/test_world_api.py -v`
Expected: FAIL — 404 на `/api/world/activities/start` (маршрутов нет).

- [ ] **Step 3: Реализовать маршруты**

Дописать в конец `bot/app/world/api.py`:

```python
class StepBody(BaseModel):
    action: str
    target: str


@router.post("/quests/{quest_id}/step")
def quest_step(quest_id: str, body: StepBody, x_world_player: str | None = Header(None)):
    return _guard(core.advance_quest_step, _player_key(x_world_player), quest_id,
                  body.action, body.target)


class ActivityStartBody(BaseModel):
    activity_id: str


@router.post("/activities/start")
def activity_start(body: ActivityStartBody, x_world_player: str | None = Header(None)):
    return _guard(activities.start, _player_key(x_world_player), body.activity_id)


class ActivityAnswerBody(BaseModel):
    index: int
    choice: int


@router.post("/activities/{session_id}/answer")
def activity_answer(session_id: str, body: ActivityAnswerBody,
                    x_world_player: str | None = Header(None)):
    return _guard(activities.answer, _player_key(x_world_player), session_id,
                  body.index, body.choice)


class ActivityFinishBody(BaseModel):
    idempotency_key: str | None = None


@router.post("/activities/{session_id}/finish")
def activity_finish(session_id: str, body: ActivityFinishBody | None = None,
                    x_world_player: str | None = Header(None)):
    return _guard(activities.finish, _player_key(x_world_player), session_id,
                  body.idempotency_key if body else None)
```

И заменить строку импорта `from . import core` на:

```python
from . import activities, core
```

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `cd bot && .venv313/bin/python -m pytest tests/test_world_api.py -v`
Expected: PASS — 4 теста.

- [ ] **Step 5: Полный прогон сьюта**

Run: `cd bot && .venv313/bin/python -m pytest -q`
Expected: PASS, 0 failed.

- [ ] **Step 6: Коммит**

```bash
git add bot/app/world/api.py bot/tests/test_world_api.py
git commit -m "feat(world): HTTP-маршруты активностей и шага квеста"
```

---

### Task 8: Клиент API и конечный автомат фаз

**Files:**
- Modify: `world/src/lib/api.ts`
- Create: `world/src/game/phases.ts`
- Create: `world/src/game/phases.test.ts`
- Create: `world/vitest.config.ts`
- Modify: `world/package.json`

**Interfaces:**
- Consumes: HTTP-контракт из Task 7.
- Produces: типы `ChallengeSession`, `ChallengeQuestion`, `AnswerResult`, `FinishResult`, `QuestStepResult`; методы `worldApi.advanceStep`, `worldApi.startActivity`, `worldApi.answer`, `worldApi.finishActivity`; чистые функции `transition(phase, event)`, `phaseForStep(step, status)`, тип `Phase`, `GameEvent`.

- [ ] **Step 1: Написать падающий тест**

Создать `world/src/game/phases.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { phaseForStep, transition } from "./phases";

describe("transition", () => {
  it("проводит игрока по полному циклу первого дня", () => {
    expect(transition("boot", "loaded")).toBe("explore");
    expect(transition("explore", "school-clicked")).toBe("dialogue");
    expect(transition("dialogue", "dialogue-done")).toBe("challenge");
    expect(transition("challenge", "challenge-done")).toBe("reward");
    expect(transition("reward", "reward-done")).toBe("explore");
  });

  it("игнорирует события не из текущей фазы", () => {
    expect(transition("boot", "challenge-done")).toBe("boot");
    expect(transition("explore", "reward-done")).toBe("explore");
    expect(transition("challenge", "school-clicked")).toBe("challenge");
  });
});

describe("phaseForStep", () => {
  it("восстанавливает фазу по прогрессу с сервера", () => {
    expect(phaseForStep(0, "active")).toBe("explore");
    expect(phaseForStep(1, "active")).toBe("dialogue");
    expect(phaseForStep(2, "active")).toBe("challenge");
    expect(phaseForStep(3, "completed")).toBe("explore");
  });
});
```

- [ ] **Step 2: Подключить vitest и убедиться, что тест падает**

Run: `cd world && npm install -D vitest@^3`
Создать `world/vitest.config.ts`:

```ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: { environment: "node", include: ["src/**/*.test.ts"] },
});
```

В `world/package.json` в `scripts` добавить: `"test": "vitest run"`.
Run: `cd world && npm test`
Expected: FAIL — `Failed to resolve import "./phases"`.

- [ ] **Step 3: Реализовать автомат фаз**

Создать `world/src/game/phases.ts`:

```ts
/** Фазы игрового цикла первого дня в Фоксинбурге. */
export type Phase = "boot" | "explore" | "dialogue" | "challenge" | "reward";

export type GameEvent =
  | "loaded"
  | "school-clicked"
  | "dialogue-done"
  | "challenge-done"
  | "reward-done";

const TRANSITIONS: Record<Phase, Partial<Record<GameEvent, Phase>>> = {
  boot: { loaded: "explore" },
  explore: { "school-clicked": "dialogue" },
  dialogue: { "dialogue-done": "challenge" },
  challenge: { "challenge-done": "reward" },
  reward: { "reward-done": "explore" },
};

/** Событие не из текущей фазы игнорируется — фаза не меняется. */
export function transition(phase: Phase, event: GameEvent): Phase {
  return TRANSITIONS[phase][event] ?? phase;
}

/** Восстановление фазы по прогрессу квеста с сервера (перезагрузка страницы). */
export function phaseForStep(step: number, status: string): Phase {
  if (status === "completed") return "explore";
  if (step <= 0) return "explore";
  if (step === 1) return "dialogue";
  return "challenge";
}
```

- [ ] **Step 4: Убедиться, что тест проходит**

Run: `cd world && npm test`
Expected: PASS — 3 теста.

- [ ] **Step 5: Дописать клиент API**

В `world/src/lib/api.ts` добавить типы перед `const API`:

```ts
export type ChallengeQuestion = {
  index: number;
  en: string;
  ipa: string;
  example_en: string;
  options: string[];
};

export type ChallengeSession = {
  session_id: string;
  activity_id: string;
  title_ru: string;
  total: number;
  questions: ChallengeQuestion[];
};

export type AnswerResult = {
  index: number;
  correct: boolean;
  correct_index: number;
  example_en: string;
  example_ru: string;
  answered: number;
  total: number;
};

export type QuestStepResult = {
  quest_id: string;
  step: number;
  steps_total: number;
  all_steps_done: boolean;
};

export type FinishResult = {
  session_id: string;
  activity_id: string;
  score: number;
  total: number;
  perfect: boolean;
  xp_delta: number;
  coins_delta: number;
  level_up: boolean;
  new_level: number;
  new_title: string;
  player: Player;
  quest: QuestStepResult | null;
};
```

И методы в объект `worldApi`:

```ts
  advanceStep: (questId: string, action: string, target: string) =>
    call<QuestStepResult>(`/api/world/quests/${questId}/step`, {
      method: "POST",
      body: JSON.stringify({ action, target }),
    }),
  startActivity: (activityId: string) =>
    call<ChallengeSession>("/api/world/activities/start", {
      method: "POST",
      body: JSON.stringify({ activity_id: activityId }),
    }),
  answer: (sessionId: string, index: number, choice: number) =>
    call<AnswerResult>(`/api/world/activities/${sessionId}/answer`, {
      method: "POST",
      body: JSON.stringify({ index, choice }),
    }),
  finishActivity: (sessionId: string) =>
    call<FinishResult>(`/api/world/activities/${sessionId}/finish`, {
      method: "POST",
      body: JSON.stringify({ idempotency_key: crypto.randomUUID() }),
    }),
```

- [ ] **Step 6: Проверить типы**

Run: `cd world && npx tsc --noEmit`
Expected: без ошибок.

- [ ] **Step 7: Коммит**

```bash
git add world/src/lib/api.ts world/src/game/phases.ts world/src/game/phases.test.ts world/vitest.config.ts world/package.json world/package-lock.json
git commit -m "feat(world): клиент активностей и конечный автомат фаз"
```

---

### Task 9: Игровой стор

**Files:**
- Create: `world/src/game/store.ts`

**Interfaces:**
- Consumes: `phases.transition`, `phases.phaseForStep`, `worldApi` (Task 8).
- Produces: `useGame()` — zustand-стор со свойствами `phase, player, quest, session, answers, finish, loadingLabel, error` и действиями `boot(name)`, `clickSchool()`, `finishDialogue()`, `answerQuestion(index, choice)`, `finishChallenge()`, `closeReward()`. Константа `QUEST_ID = "first-day-at-foxinburg"`, `ACTIVITY_ID = "vocabulary-challenge-1"`.

- [ ] **Step 1: Создать стор**

Создать `world/src/game/store.ts`:

```ts
"use client";

import { create } from "zustand";
import {
  worldApi,
  type AnswerResult,
  type ChallengeSession,
  type FinishResult,
  type Player,
  type Quest,
} from "@/lib/api";
import { phaseForStep, transition, type GameEvent, type Phase } from "./phases";

export const QUEST_ID = "first-day-at-foxinburg";
export const ACTIVITY_ID = "vocabulary-challenge-1";

type GameState = {
  phase: Phase;
  player: Player | null;
  quest: Quest | null;
  session: ChallengeSession | null;
  answers: Record<number, AnswerResult>;
  finish: FinishResult | null;
  error: string | null;
  boot: (displayName: string) => Promise<void>;
  clickSchool: () => Promise<void>;
  finishDialogue: () => Promise<void>;
  answerQuestion: (index: number, choice: number) => Promise<void>;
  finishChallenge: () => Promise<void>;
  closeReward: () => void;
};

/** Шаг квеста считает сервер; 409 значит «шаг уже пройден» — не ошибка. */
async function advance(action: string, target: string): Promise<void> {
  try {
    await worldApi.advanceStep(QUEST_ID, action, target);
  } catch (err) {
    if (!String(err).includes("409")) throw err;
  }
}

export const useGame = create<GameState>((set, get) => ({
  phase: "boot",
  player: null,
  quest: null,
  session: null,
  answers: {},
  finish: null,
  error: null,

  boot: async (displayName) => {
    try {
      const player = await worldApi.ensurePlayer(displayName);
      const quests = await worldApi.getQuests();
      const quest = quests.find((q) => q.id === QUEST_ID) ?? null;
      if (quest && quest.status === "available") await worldApi.startQuest(QUEST_ID);
      const step = quest?.step ?? 0;
      const status = quest?.status ?? "active";
      set({
        player,
        quest,
        phase: step === 0 ? transition("boot", "loaded") : phaseForStep(step, status),
        error: null,
      });
    } catch (err) {
      set({ error: String(err) });
    }
  },

  clickSchool: async () => {
    if (get().phase !== "explore") return;
    await advance("visit", "school-hub");
    set((s) => ({ phase: transition(s.phase, "school-clicked") }));
  },

  finishDialogue: async () => {
    if (get().phase !== "dialogue") return;
    await advance("talk", "foxi");
    const session = await worldApi.startActivity(ACTIVITY_ID);
    set((s) => ({ session, answers: {}, phase: transition(s.phase, "dialogue-done") }));
  },

  answerQuestion: async (index, choice) => {
    const session = get().session;
    if (!session || get().answers[index]) return;
    const result = await worldApi.answer(session.session_id, index, choice);
    set((s) => ({ answers: { ...s.answers, [index]: result } }));
  },

  finishChallenge: async () => {
    const session = get().session;
    if (!session) return;
    const finish = await worldApi.finishActivity(session.session_id);
    set((s) => ({
      finish,
      player: finish.player,
      phase: transition(s.phase, "challenge-done"),
    }));
  },

  closeReward: () => {
    set((s) => ({ phase: transition(s.phase, "reward-done"), session: null }));
  },
}));

/** Событие для отладки сцены из консоли браузера. */
export function debugEvent(event: GameEvent): void {
  useGame.setState((s) => ({ phase: transition(s.phase, event) }));
}
```

- [ ] **Step 2: Проверить типы**

Run: `cd world && npx tsc --noEmit`
Expected: без ошибок.

- [ ] **Step 3: Проверить, что тесты фаз не сломались**

Run: `cd world && npm test`
Expected: PASS — 3 теста.

- [ ] **Step 4: Коммит**

```bash
git add world/src/game/store.ts
git commit -m "feat(world): игровой стор цикла первого дня"
```

---

### Task 10: Сцена — свет, земля, школа, атмосфера

**Files:**
- Create: `world/src/engine/quality.ts`
- Create: `world/src/engine/Lighting.tsx`
- Create: `world/src/engine/Ground.tsx`
- Create: `world/src/engine/SchoolBuilding.tsx`
- Create: `world/src/engine/Fireflies.tsx`
- Create: `world/src/engine/Postfx.tsx`
- Create: `world/src/engine/Stage.tsx`
- Modify: `world/src/app/globals.css` (токены палитры)

**Interfaces:**
- Consumes: палитру из Global Constraints.
- Produces: `qualityProfile(): "ultra" | "high" | "medium" | "low"`; `<Lighting />`, `<Ground />`, `<SchoolBuilding onClick highlighted />`, `<Fireflies count />`, `<Postfx />`, `<Stage>{children}</Stage>`; CSS-переменные `--world-purple`, `--world-purple-dark`, `--world-yellow`, `--world-teal`.

- [ ] **Step 1: Токены палитры**

Дописать в конец `world/src/app/globals.css`:

```css
:root {
  --world-purple: #3a2953;
  --world-purple-dark: #241a30;
  --world-yellow: #f5ed75;
  --world-teal: #7fd8c9;
  --world-ink: #ffffff;
}

body {
  background: var(--world-purple-dark);
  color: var(--world-ink);
}
```

- [ ] **Step 2: Детектор качества**

Создать `world/src/engine/quality.ts`:

```ts
export type QualityProfile = "ultra" | "high" | "medium" | "low";

/** Профиль рендера по возможностям устройства (architecture.md §7). */
export function qualityProfile(): QualityProfile {
  if (typeof window === "undefined") return "medium";
  const memory = (navigator as Navigator & { deviceMemory?: number }).deviceMemory ?? 4;
  const cores = navigator.hardwareConcurrency ?? 4;
  const coarse = window.matchMedia("(pointer: coarse)").matches;
  if (coarse && memory <= 4) return "low";
  if (memory >= 8 && cores >= 8) return "ultra";
  if (memory >= 8) return "high";
  return "medium";
}

export const DPR: Record<QualityProfile, [number, number]> = {
  ultra: [1, 2],
  high: [1, 1.75],
  medium: [1, 1.5],
  low: [0.75, 1],
};

export const SHADOWS: Record<QualityProfile, boolean> = {
  ultra: true, high: true, medium: true, low: false,
};

export const POSTFX: Record<QualityProfile, boolean> = {
  ultra: true, high: true, medium: true, low: false,
};

export const FIREFLIES: Record<QualityProfile, number> = {
  ultra: 160, high: 120, medium: 80, low: 0,
};
```

- [ ] **Step 3: Свет и атмосфера**

Создать `world/src/engine/Lighting.tsx`:

```tsx
"use client";

/** Тёплое солнце + холодный ambient + туман глубины (world-art-bible §6). */
export function Lighting() {
  return (
    <>
      <color attach="background" args={["#241a30"]} />
      <fog attach="fog" args={["#241a30", 18, 46]} />
      <hemisphereLight args={["#f5ed75", "#3a2953", 0.55]} />
      <directionalLight
        position={[6, 9, 4]}
        intensity={2.1}
        color="#ffe9b8"
        castShadow
        shadow-mapSize={[1024, 1024]}
        shadow-camera-left={-18}
        shadow-camera-right={18}
        shadow-camera-top={18}
        shadow-camera-bottom={-18}
      />
      <ambientLight intensity={0.35} color="#6b4f9a" />
    </>
  );
}
```

- [ ] **Step 4: Земля двора**

Создать `world/src/engine/Ground.tsx`:

```tsx
"use client";

/** Двор школы: мягкий круг мощения на тёмной траве. */
export function Ground() {
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <circleGeometry args={[26, 64]} />
        <meshStandardMaterial color="#2c2140" roughness={0.9} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, 0]} receiveShadow>
        <circleGeometry args={[9, 64]} />
        <meshStandardMaterial color="#3a2953" roughness={0.7} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]}>
        <ringGeometry args={[8.6, 9, 64]} />
        <meshStandardMaterial color="#f5ed75" emissive="#f5ed75" emissiveIntensity={0.35} />
      </mesh>
    </group>
  );
}
```

- [ ] **Step 5: Здание школы**

Создать `world/src/engine/SchoolBuilding.tsx`:

```tsx
"use client";

import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import type { Group } from "three";

type Props = { highlighted: boolean; onClick: () => void };

const WINDOW_ROWS = [3.2, 5.4];
const WINDOW_COLS = [-2.4, -0.8, 0.8, 2.4];

/** Школа-замок Фоксинбурга: chibi-пропорции, башня с часами, тёплые окна. */
export function SchoolBuilding({ highlighted, onClick }: Props) {
  const group = useRef<Group>(null);

  useFrame((state) => {
    if (!group.current || !highlighted) return;
    const pulse = 1 + Math.sin(state.clock.elapsedTime * 2) * 0.012;
    group.current.scale.setScalar(pulse);
  });

  return (
    <group
      ref={group}
      position={[0, 0, -9]}
      onClick={(event) => {
        event.stopPropagation();
        onClick();
      }}
      onPointerOver={() => (document.body.style.cursor = "pointer")}
      onPointerOut={() => (document.body.style.cursor = "auto")}
    >
      {/* корпус */}
      <mesh position={[0, 3.5, 0]} castShadow receiveShadow>
        <boxGeometry args={[11, 7, 7]} />
        <meshStandardMaterial color="#3a2953" roughness={0.65} />
      </mesh>
      {/* крыша */}
      <mesh position={[0, 8, 0]} castShadow>
        <coneGeometry args={[8.4, 3.4, 4]} />
        <meshStandardMaterial color="#241a30" roughness={0.8} />
      </mesh>
      {/* башня с часами */}
      <mesh position={[4.6, 7, 0]} castShadow>
        <cylinderGeometry args={[1.5, 1.7, 12, 16]} />
        <meshStandardMaterial color="#45305f" roughness={0.6} />
      </mesh>
      <mesh position={[4.6, 13.6, 0]} castShadow>
        <coneGeometry args={[2.1, 2.8, 16]} />
        <meshStandardMaterial color="#241a30" roughness={0.8} />
      </mesh>
      <mesh position={[4.6, 10.4, 1.55]}>
        <circleGeometry args={[1, 32]} />
        <meshStandardMaterial
          color="#f5ed75"
          emissive="#f5ed75"
          emissiveIntensity={highlighted ? 1.4 : 0.7}
        />
      </mesh>
      {/* дверь 2.2 u */}
      <mesh position={[0, 1.1, 3.55]}>
        <boxGeometry args={[2.4, 2.2, 0.2]} />
        <meshStandardMaterial
          color="#c96f4a"
          emissive="#f5ed75"
          emissiveIntensity={highlighted ? 0.5 : 0.15}
        />
      </mesh>
      {/* тёплые окна */}
      {WINDOW_ROWS.map((y) =>
        WINDOW_COLS.map((x) => (
          <mesh key={`${x}-${y}`} position={[x, y, 3.55]}>
            <boxGeometry args={[1.1, 1.4, 0.15]} />
            <meshStandardMaterial
              color="#f5ed75"
              emissive="#f5ed75"
              emissiveIntensity={0.9}
            />
          </mesh>
        )),
      )}
    </group>
  );
}
```

- [ ] **Step 6: Ambient-частицы**

Создать `world/src/engine/Fireflies.tsx`:

```tsx
"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import type { Points } from "three";
import { BufferAttribute, BufferGeometry } from "three";

/** Светлячки: мир не должен выглядеть мёртвым (world-art-bible §6). */
export function Fireflies({ count }: { count: number }) {
  const points = useRef<Points>(null);

  const geometry = useMemo(() => {
    const positions = new Float32Array(count * 3);
    for (let i = 0; i < count; i += 1) {
      positions[i * 3] = (Math.random() - 0.5) * 34;
      positions[i * 3 + 1] = Math.random() * 9 + 0.5;
      positions[i * 3 + 2] = (Math.random() - 0.5) * 34;
    }
    const geom = new BufferGeometry();
    geom.setAttribute("position", new BufferAttribute(positions, 3));
    return geom;
  }, [count]);

  useFrame((state) => {
    if (points.current) {
      points.current.rotation.y = state.clock.elapsedTime * 0.02;
    }
  });

  if (count === 0) return null;

  return (
    <points ref={points} geometry={geometry}>
      <pointsMaterial
        size={0.09}
        color="#f5ed75"
        transparent
        opacity={0.8}
        sizeAttenuation
      />
    </points>
  );
}
```

- [ ] **Step 7: Пост-обработка**

Создать `world/src/engine/Postfx.tsx`:

```tsx
"use client";

import { Bloom, EffectComposer, Vignette } from "@react-three/postprocessing";

/** Subtle bloom + vignette — «не максимум постоянно» (world-art-bible §6). */
export function Postfx() {
  return (
    <EffectComposer>
      <Bloom intensity={0.45} luminanceThreshold={0.65} luminanceSmoothing={0.25} mipmapBlur />
      <Vignette eskil={false} offset={0.25} darkness={0.55} />
    </EffectComposer>
  );
}
```

- [ ] **Step 8: Canvas**

Создать `world/src/engine/Stage.tsx`:

```tsx
"use client";

import { Canvas } from "@react-three/fiber";
import { Suspense, type ReactNode } from "react";
import { DPR, POSTFX, SHADOWS, qualityProfile } from "./quality";
import { Postfx } from "./Postfx";

/** Единственная точка входа в three: всё остальное приложение — про игру. */
export function Stage({ children }: { children: ReactNode }) {
  const profile = qualityProfile();
  return (
    <Canvas
      shadows={SHADOWS[profile]}
      dpr={DPR[profile]}
      camera={{ fov: 38, position: [0, 3.2, 12], near: 0.1, far: 120 }}
      gl={{ antialias: profile !== "low" }}
    >
      <Suspense fallback={null}>
        {children}
        {POSTFX[profile] ? <Postfx /> : null}
      </Suspense>
    </Canvas>
  );
}
```

- [ ] **Step 9: Проверить типы**

Run: `cd world && npx tsc --noEmit`
Expected: без ошибок.

- [ ] **Step 10: Коммит**

```bash
git add world/src/engine world/src/app/globals.css
git commit -m "feat(world): сцена School Hub — свет, двор, школа, атмосфера"
```

---

### Task 11: Камера, хотспоты, Фокси, монета

**Files:**
- Create: `world/src/engine/CameraRig.tsx`
- Create: `world/src/engine/Foxi.tsx`
- Create: `world/src/engine/FoxCoin.tsx`

**Interfaces:**
- Consumes: `world/public/assets/foxi-rigged.glb`, `world/public/assets/school-foxcoin-v1.glb`.
- Produces: `type CameraShot = "courtyard" | "school" | "foxi" | "reward"`; `<CameraRig shot={CameraShot} />`; `<Foxi clip="idle" | "wave" | "cheer" | "jump" position />`; `<FoxCoin position swirl />`.

- [ ] **Step 1: Камера по именованным точкам**

Создать `world/src/engine/CameraRig.tsx`:

```tsx
"use client";

import { useFrame, useThree } from "@react-three/fiber";
import { Vector3 } from "three";

export type CameraShot = "courtyard" | "school" | "foxi" | "reward";

/** Точки съёмки: дистанция 6–8 u, высота 2.5–3.5 u; reward — 1.8 u, low-angle. */
const SHOTS: Record<CameraShot, { position: Vector3; target: Vector3 }> = {
  courtyard: { position: new Vector3(0, 3.4, 12), target: new Vector3(0, 2.2, -4) },
  school: { position: new Vector3(-2.4, 3.2, 4.5), target: new Vector3(0, 4.2, -8) },
  foxi: { position: new Vector3(1.6, 2.6, 3.2), target: new Vector3(2.4, 1.1, -0.4) },
  reward: { position: new Vector3(2.2, 1.4, 2.6), target: new Vector3(2.4, 1.5, -0.4) },
};

const target = new Vector3();

export function CameraRig({ shot }: { shot: CameraShot }) {
  const camera = useThree((state) => state.camera);

  useFrame((_, delta) => {
    const next = SHOTS[shot];
    const damping = 1 - Math.pow(0.001, delta);
    camera.position.lerp(next.position, damping);
    target.lerp(next.target, damping);
    camera.lookAt(target);
  });

  return null;
}
```

- [ ] **Step 2: Фокси с переключением клипов**

Создать `world/src/engine/Foxi.tsx`:

```tsx
"use client";

import { useEffect, useRef } from "react";
import { useAnimations, useGLTF } from "@react-three/drei";
import type { Group } from "three";

export type FoxiClip = "idle" | "wave" | "cheer" | "jump";

/** Имена клипов внутри foxi-rigged.glb — других в файле нет. */
const CLIP_NAMES: Record<FoxiClip, string> = {
  idle: "Walking",
  wave: "Big_Wave_Hello",
  cheer: "Cheer_with_Both_Hands_Up",
  jump: "Happy_jump_f",
};

type Props = { clip: FoxiClip; position?: [number, number, number] };

export function Foxi({ clip, position = [2.4, 0, -0.4] }: Props) {
  const group = useRef<Group>(null);
  const { scene, animations } = useGLTF("/assets/foxi-rigged.glb");
  const { actions } = useAnimations(animations, group);

  useEffect(() => {
    const name = CLIP_NAMES[clip];
    const action = actions[name];
    if (!action) return;
    action.reset().fadeIn(0.35).play();
    return () => {
      action.fadeOut(0.35);
    };
  }, [actions, clip]);

  return (
    <group ref={group} position={position} rotation={[0, -0.4, 0]}>
      <primitive object={scene} scale={0.9} castShadow />
    </group>
  );
}

useGLTF.preload("/assets/foxi-rigged.glb");
```

- [ ] **Step 3: FoxCoin**

Создать `world/src/engine/FoxCoin.tsx`:

```tsx
"use client";

import { useRef } from "react";
import { useGLTF } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import type { Group } from "three";

type Props = {
  position?: [number, number, number];
  /** Вихрь монет в кинематографике награды. */
  swirl?: boolean;
  seed?: number;
};

export function FoxCoin({ position = [0, 1.2, 0], swirl = false, seed = 0 }: Props) {
  const group = useRef<Group>(null);
  const { scene } = useGLTF("/assets/school-foxcoin-v1.glb");

  useFrame((state) => {
    if (!group.current) return;
    const t = state.clock.elapsedTime + seed;
    group.current.rotation.y = t * 1.6;
    if (swirl) {
      group.current.position.set(
        position[0] + Math.cos(t * 1.2) * 0.8,
        position[1] + Math.sin(t * 2) * 0.35 + 0.3,
        position[2] + Math.sin(t * 1.2) * 0.8,
      );
    } else {
      group.current.position.set(position[0], position[1] + Math.sin(t) * 0.08, position[2]);
    }
  });

  return (
    <group ref={group}>
      <primitive object={scene.clone()} scale={0.5} />
      <pointLight color="#f5ed75" intensity={2.4} distance={3} />
    </group>
  );
}

useGLTF.preload("/assets/school-foxcoin-v1.glb");
```

- [ ] **Step 4: Проверить типы**

Run: `cd world && npx tsc --noEmit`
Expected: без ошибок.

- [ ] **Step 5: Коммит**

```bash
git add world/src/engine/CameraRig.tsx world/src/engine/Foxi.tsx world/src/engine/FoxCoin.tsx
git commit -m "feat(world): кинематографическая камера, Фокси и FoxCoin в сцене"
```

---

### Task 12: Game OS — примитивы, HUD, диалог

**Files:**
- Create: `world/src/ui/Glass.tsx`
- Create: `world/src/ui/Button.tsx`
- Create: `world/src/game/hud/Hud.tsx`
- Create: `world/src/game/dialogue/FoxiDialogue.tsx`
- Modify: `world/src/app/layout.tsx` (шрифты Montserrat + DM Sans)

**Interfaces:**
- Consumes: `useGame` (Task 9).
- Produces: `<Glass className>`, `<GameButton onClick variant="primary" | "ghost">`, `<Hud />`, `<FoxiDialogue />`.

- [ ] **Step 1: Шрифты**

В `world/src/app/layout.tsx` заменить импорты шрифтов на:

```tsx
import { DM_Sans, Montserrat } from "next/font/google";

const montserrat = Montserrat({
  variable: "--font-display",
  subsets: ["cyrillic", "latin"],
  weight: ["700", "800"],
});

const dmSans = DM_Sans({
  variable: "--font-ui",
  subsets: ["cyrillic", "latin"],
  weight: ["400", "500"],
});
```

и в `<body>` подставить `className={`${montserrat.variable} ${dmSans.variable} antialiased`}`.

- [ ] **Step 2: Glass-панель и кнопка**

Создать `world/src/ui/Glass.tsx`:

```tsx
import type { ReactNode } from "react";

/** Glass-панель Game OS: purple-dark 70% + blur, скругление 20px. */
export function Glass({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-[20px] border border-white/10 bg-[#241a30]/70 backdrop-blur-md shadow-[0_18px_50px_rgba(0,0,0,0.45)] ${className}`}
    >
      {children}
    </div>
  );
}
```

Создать `world/src/ui/Button.tsx`:

```tsx
"use client";

import type { ReactNode } from "react";

type Props = {
  children: ReactNode;
  onClick: () => void;
  variant?: "primary" | "ghost";
  disabled?: boolean;
};

export function GameButton({ children, onClick, variant = "primary", disabled }: Props) {
  const base =
    "rounded-full px-6 py-3 font-[family-name:var(--font-display)] text-sm font-extrabold uppercase tracking-wide transition-transform duration-150 active:scale-[0.96] disabled:opacity-40";
  const skin =
    variant === "primary"
      ? "bg-[#f5ed75] text-[#241a30] hover:brightness-110"
      : "border border-white/20 text-white hover:bg-white/10";
  return (
    <button className={`${base} ${skin}`} onClick={onClick} disabled={disabled}>
      {children}
    </button>
  );
}
```

- [ ] **Step 3: HUD**

Создать `world/src/game/hud/Hud.tsx`:

```tsx
"use client";

import { Glass } from "@/ui/Glass";
import { useGame } from "@/game/store";

const STEP_LABELS = [
  "Найди школу Фоксинбурга",
  "Поговори с Фокси",
  "Пройди первый английский челлендж",
];

export function Hud() {
  const { player, quest, phase } = useGame();
  if (!player) return null;

  const total = player.xp_into_level + (player.xp_to_next ?? 0);
  const progress = total > 0 ? (player.xp_into_level / total) * 100 : 100;
  const step = quest?.step ?? 0;
  const label = quest?.status === "completed" ? "Квест пройден" : STEP_LABELS[step] ?? "";

  return (
    <div className="pointer-events-none absolute inset-x-0 top-0 flex flex-col gap-3 p-4 sm:flex-row sm:items-start sm:justify-between">
      <Glass className="pointer-events-auto w-full max-w-sm p-4">
        <div className="flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-full bg-[#f5ed75] font-[family-name:var(--font-display)] text-lg font-extrabold text-[#241a30]">
            {player.level}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate font-[family-name:var(--font-display)] text-sm font-bold">
              {player.display_name} · {player.level_title}
            </p>
            <div className="mt-1 h-2 overflow-hidden rounded-full bg-white/10">
              <div
                className="h-full rounded-full bg-[#f5ed75] transition-[width] duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="mt-1 text-xs text-white/60">
              {player.xp} XP{player.xp_to_next ? ` · до уровня ${player.xp_to_next}` : ""}
            </p>
          </div>
          <div className="text-right">
            <p className="font-[family-name:var(--font-display)] text-lg font-extrabold text-[#f5ed75]">
              {player.coins}
            </p>
            <p className="text-[10px] uppercase tracking-wide text-white/50">FoxCoins</p>
          </div>
        </div>
      </Glass>

      {phase === "explore" && label ? (
        <Glass className="pointer-events-auto max-w-xs p-4">
          <p className="text-[10px] uppercase tracking-widest text-[#f5ed75]">Квест</p>
          <p className="mt-1 text-sm">{label}</p>
        </Glass>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 4: Диалог с Фокси**

Создать `world/src/game/dialogue/FoxiDialogue.tsx`:

```tsx
"use client";

import { useState } from "react";
import { Glass } from "@/ui/Glass";
import { GameButton } from "@/ui/Button";
import { useGame } from "@/game/store";

const LINES = [
  "Привет! Я Фокси. Добро пожаловать в Фоксинбург!",
  "Здесь всё держится на английских словах — они открывают двери.",
  "Проверим, сколько ты уже знаешь? Пять слов, это быстро.",
];

export function FoxiDialogue() {
  const { phase, finishDialogue } = useGame();
  const [line, setLine] = useState(0);
  if (phase !== "dialogue") return null;

  const last = line === LINES.length - 1;

  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-0 flex justify-center p-4">
      <Glass className="pointer-events-auto w-full max-w-md p-5">
        <p className="text-[10px] uppercase tracking-widest text-[#f5ed75]">Фокси</p>
        <p className="mt-2 min-h-[3.5rem] text-base leading-relaxed">{LINES[line]}</p>
        <div className="mt-4 flex justify-end">
          <GameButton onClick={() => (last ? finishDialogue() : setLine(line + 1))}>
            {last ? "Погнали" : "Дальше"}
          </GameButton>
        </div>
      </Glass>
    </div>
  );
}
```

- [ ] **Step 5: Проверить типы**

Run: `cd world && npx tsc --noEmit`
Expected: без ошибок.

- [ ] **Step 6: Коммит**

```bash
git add world/src/ui world/src/game/hud world/src/game/dialogue world/src/app/layout.tsx
git commit -m "feat(world): Game OS — glass-примитивы, HUD и диалог Фокси"
```

---

### Task 13: Оверлей vocabulary-челленджа

**Files:**
- Create: `world/src/game/activities/VocabularyChallenge.tsx`

**Interfaces:**
- Consumes: `useGame().session/answers/answerQuestion/finishChallenge`.
- Produces: `<VocabularyChallenge />` — рендерится только в фазе `challenge`.

- [ ] **Step 1: Создать оверлей**

Создать `world/src/game/activities/VocabularyChallenge.tsx`:

```tsx
"use client";

import { useState } from "react";
import { Glass } from "@/ui/Glass";
import { GameButton } from "@/ui/Button";
import { useGame } from "@/game/store";

export function VocabularyChallenge() {
  const { phase, session, answers, answerQuestion, finishChallenge } = useGame();
  const [index, setIndex] = useState(0);
  const [chosen, setChosen] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  if (phase !== "challenge" || !session) return null;

  const question = session.questions[index];
  const answer = answers[index];
  const last = index === session.questions.length - 1;

  const choose = async (choice: number) => {
    if (answer || busy) return;
    setBusy(true);
    setChosen(choice);
    try {
      await answerQuestion(index, choice);
    } finally {
      setBusy(false);
    }
  };

  const next = async () => {
    if (!last) {
      setIndex(index + 1);
      setChosen(null);
      return;
    }
    setBusy(true);
    try {
      await finishChallenge();
    } finally {
      setBusy(false);
    }
  };

  const optionSkin = (option: number): string => {
    if (!answer) return "border-white/15 hover:border-[#f5ed75] hover:bg-white/5";
    if (option === answer.correct_index) return "border-[#7fd8c9] bg-[#7fd8c9]/15";
    if (option === chosen && !answer.correct) return "border-[#c96f4a] bg-[#c96f4a]/10";
    return "border-white/10 opacity-50";
  };

  return (
    <div className="absolute inset-0 flex items-center justify-center bg-[#241a30]/45 p-4 backdrop-blur-[2px]">
      <Glass className="w-full max-w-lg p-6">
        <div className="flex items-center justify-between text-[10px] uppercase tracking-widest text-[#f5ed75]">
          <span>{session.title_ru}</span>
          <span>
            {index + 1} / {session.total}
          </span>
        </div>

        <p className="mt-5 font-[family-name:var(--font-display)] text-4xl font-extrabold">
          {question.en}
        </p>
        <p className="mt-1 text-sm text-white/50">{question.ipa}</p>

        <div className="mt-5 grid gap-2">
          {question.options.map((option, i) => (
            <button
              key={option}
              onClick={() => choose(i)}
              disabled={Boolean(answer) || busy}
              className={`rounded-2xl border px-4 py-3 text-left text-base transition-colors ${optionSkin(i)}`}
            >
              {option}
            </button>
          ))}
        </div>

        {answer ? (
          <div className="mt-4 rounded-2xl bg-white/5 p-4">
            <p className="font-[family-name:var(--font-display)] text-sm font-bold text-[#f5ed75]">
              {answer.correct ? "Верно!" : "Правильный ответ подсвечен"}
            </p>
            <p className="mt-2 text-sm text-white/80">{answer.example_en}</p>
            <p className="text-sm text-white/50">{answer.example_ru}</p>
          </div>
        ) : null}

        <div className="mt-5 flex justify-end">
          <GameButton onClick={next} disabled={!answer || busy}>
            {last ? "Забрать награду" : "Дальше"}
          </GameButton>
        </div>
      </Glass>
    </div>
  );
}
```

- [ ] **Step 2: Проверить типы**

Run: `cd world && npx tsc --noEmit`
Expected: без ошибок.

- [ ] **Step 3: Коммит**

```bash
git add world/src/game/activities
git commit -m "feat(world): оверлей vocabulary-челленджа"
```

---

### Task 14: Reward cinematic и сборка страницы мира

**Files:**
- Create: `world/src/game/reward/RewardCinematic.tsx`
- Create: `world/src/app/world/page.tsx`
- Modify: `world/src/app/page.tsx`

**Interfaces:**
- Consumes: всё из Task 9–13.
- Produces: страница `/world` — единственное место, где склеиваются `Stage` (3D) и оверлеи (2D); `/` — вход с именем игрока.

- [ ] **Step 1: Кинематографика награды**

Создать `world/src/game/reward/RewardCinematic.tsx`:

```tsx
"use client";

import { Glass } from "@/ui/Glass";
import { GameButton } from "@/ui/Button";
import { useGame } from "@/game/store";

export function RewardCinematic() {
  const { phase, finish, closeReward } = useGame();
  if (phase !== "reward" || !finish) return null;

  return (
    <div className="absolute inset-0 flex items-end justify-center p-6 sm:items-center">
      <Glass className="w-full max-w-md p-7 text-center">
        <p className="text-[10px] uppercase tracking-widest text-[#f5ed75]">
          {finish.perfect ? "Безошибочно!" : "Челлендж пройден"}
        </p>
        <p className="mt-2 font-[family-name:var(--font-display)] text-2xl font-extrabold">
          {finish.score} из {finish.total}
        </p>

        <div className="mt-6 flex items-center justify-center gap-8">
          <div>
            <p className="font-[family-name:var(--font-display)] text-4xl font-extrabold text-[#f5ed75]">
              +{finish.xp_delta}
            </p>
            <p className="text-[10px] uppercase tracking-widest text-white/50">XP</p>
          </div>
          <div>
            <p className="font-[family-name:var(--font-display)] text-4xl font-extrabold text-[#f5ed75]">
              +{finish.coins_delta}
            </p>
            <p className="text-[10px] uppercase tracking-widest text-white/50">FoxCoins</p>
          </div>
        </div>

        {finish.level_up ? (
          <p className="mt-6 rounded-2xl bg-[#f5ed75]/15 px-4 py-3 font-[family-name:var(--font-display)] text-sm font-bold text-[#f5ed75]">
            Новый уровень {finish.new_level} — {finish.new_title}
          </p>
        ) : null}

        {finish.quest?.all_steps_done ? (
          <p className="mt-3 text-sm text-[#7fd8c9]">
            Открыт Библиотечный двор — загляни туда в следующий раз.
          </p>
        ) : null}

        <div className="mt-7">
          <GameButton onClick={closeReward}>Вернуться в Фоксинбург</GameButton>
        </div>
      </Glass>
    </div>
  );
}
```

- [ ] **Step 2: Страница мира**

Создать `world/src/app/world/page.tsx`:

```tsx
"use client";

import { useEffect } from "react";
import { Stage } from "@/engine/Stage";
import { Lighting } from "@/engine/Lighting";
import { Ground } from "@/engine/Ground";
import { SchoolBuilding } from "@/engine/SchoolBuilding";
import { Fireflies } from "@/engine/Fireflies";
import { CameraRig, type CameraShot } from "@/engine/CameraRig";
import { Foxi, type FoxiClip } from "@/engine/Foxi";
import { FoxCoin } from "@/engine/FoxCoin";
import { FIREFLIES, qualityProfile } from "@/engine/quality";
import { Hud } from "@/game/hud/Hud";
import { FoxiDialogue } from "@/game/dialogue/FoxiDialogue";
import { VocabularyChallenge } from "@/game/activities/VocabularyChallenge";
import { RewardCinematic } from "@/game/reward/RewardCinematic";
import { useGame } from "@/game/store";
import type { Phase } from "@/game/phases";

const SHOT_BY_PHASE: Record<Phase, CameraShot> = {
  boot: "courtyard",
  explore: "courtyard",
  dialogue: "foxi",
  challenge: "school",
  reward: "reward",
};

const CLIP_BY_PHASE: Record<Phase, FoxiClip> = {
  boot: "idle",
  explore: "idle",
  dialogue: "wave",
  challenge: "idle",
  reward: "cheer",
};

export default function WorldPage() {
  const { phase, player, error, boot, clickSchool, finish } = useGame();
  const fireflies = FIREFLIES[qualityProfile()];

  useEffect(() => {
    if (!player) {
      const name =
        (typeof window !== "undefined" && window.localStorage.getItem("world.name")) ||
        "Исследователь";
      void boot(name);
    }
  }, [boot, player]);

  const rewardCoins = phase === "reward" && finish ? Math.min(finish.coins_delta, 12) : 0;

  return (
    <main className="relative h-dvh w-full overflow-hidden bg-[#241a30]">
      <Stage>
        <Lighting />
        <CameraRig shot={SHOT_BY_PHASE[phase]} />
        <Ground />
        <SchoolBuilding highlighted={phase === "explore"} onClick={() => void clickSchool()} />
        <Foxi clip={CLIP_BY_PHASE[phase]} />
        {Array.from({ length: rewardCoins }).map((_, i) => (
          <FoxCoin key={i} position={[2.4, 1.2, -0.4]} swirl seed={i * 0.7} />
        ))}
        <Fireflies count={fireflies} />
      </Stage>

      <Hud />
      <FoxiDialogue />
      <VocabularyChallenge />
      <RewardCinematic />

      {phase === "boot" ? (
        <div className="absolute inset-0 grid place-items-center bg-[#241a30]">
          <p className="font-[family-name:var(--font-display)] text-lg font-extrabold tracking-wide text-[#f5ed75]">
            Фоксинбург просыпается…
          </p>
        </div>
      ) : null}

      {error ? (
        <div className="absolute inset-x-0 bottom-0 bg-[#c96f4a] p-3 text-center text-sm">
          Мир недоступен: {error}
        </div>
      ) : null}
    </main>
  );
}
```

- [ ] **Step 3: Вход в мир**

Заменить содержимое `world/src/app/page.tsx`:

```tsx
"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Glass } from "@/ui/Glass";
import { GameButton } from "@/ui/Button";

export default function Home() {
  const router = useRouter();
  const [name, setName] = useState("");

  const enter = () => {
    const chosen = name.trim() || "Исследователь";
    window.localStorage.setItem("world.name", chosen);
    router.push("/world");
  };

  return (
    <main className="grid min-h-dvh place-items-center bg-[#241a30] p-6">
      <Glass className="w-full max-w-md p-8 text-center">
        <p className="text-[10px] uppercase tracking-widest text-[#f5ed75]">Фоксинбург</p>
        <h1 className="mt-3 font-[family-name:var(--font-display)] text-3xl font-extrabold leading-tight">
          Первый день в мире английского
        </h1>
        <p className="mt-3 text-sm text-white/60">
          Фокси уже ждёт тебя во дворе школы.
        </p>
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Как тебя зовут?"
          className="mt-6 w-full rounded-2xl border border-white/15 bg-white/5 px-4 py-3 text-center outline-none focus:border-[#f5ed75]"
        />
        <div className="mt-6">
          <GameButton onClick={enter}>В Фоксинбург</GameButton>
        </div>
      </Glass>
    </main>
  );
}
```

- [ ] **Step 4: Сборка**

Run: `cd world && npm run build`
Expected: сборка успешна, ошибок типов и ESLint нет. Если Next ругается на неиспользуемые импорты из шаблона — удалить их.

- [ ] **Step 5: Коммит**

```bash
git add world/src/game/reward world/src/app/world/page.tsx world/src/app/page.tsx
git commit -m "feat(world): reward cinematic и сборка страницы мира"
```

---

### Task 15: Живая верификация цикла и журнал

**Files:**
- Modify: `DEVLOG.md`
- Modify: `docs/superpowers/plans/2026-09-13-foxinburg-world-game-loop.md` (отметить выполнение)

**Interfaces:**
- Consumes: всё предыдущее.
- Produces: запись сессии в DEVLOG, скриншоты фаз в `/private/tmp/claude-501/-Users-grigory-Dymova-english/e3897c78-7e69-4819-aa52-670f09ed0bf5/scratchpad/`.

- [x] **Step 1: Запустить бэкенд**

Run (в фоне): `cd bot && .venv313/bin/python -m uvicorn app.main:app --port 8000`
Проверка: `curl -s localhost:8000/api/world/quests -H "X-World-Player: smoke-1"` → 404 (игрока нет) — сервер отвечает.

- [x] **Step 2: Прогнать цикл по HTTP до браузера**

```bash
curl -s -X POST localhost:8000/api/world/players -H "X-World-Player: smoke-1" \
  -H "Content-Type: application/json" -d '{"display_name":"Смоук"}'
curl -s -X POST localhost:8000/api/world/quests/first-day-at-foxinburg/start -H "X-World-Player: smoke-1"
curl -s -X POST localhost:8000/api/world/quests/first-day-at-foxinburg/step -H "X-World-Player: smoke-1" \
  -H "Content-Type: application/json" -d '{"action":"visit","target":"school-hub"}'
```
Expected: последний ответ — `{"quest_id":"first-day-at-foxinburg","step":1,...}`.

- [x] **Step 3: Запустить фронтенд**

Run (в фоне): `cd world && npm run dev`
Expected: `http://localhost:3000` отвечает.
Фактически: порт 3000 был занят посторонним процессом другого проекта пользователя (`/Users/grigory/dashenka`), dev-сервер `world` поднялся на 3002 — цикл пройден там.

- [x] **Step 4: Пройти цикл в браузере**

Через claude-in-chrome: открыть `http://localhost:3000`, ввести имя, войти в мир, кликнуть школу, пройти диалог, ответить на 5 вопросов, посмотреть награду, вернуться в мир. На каждой фазе — скриншот в scratchpad (`01-boot.png` … `06-explore-after.png`). Проверить в консоли отсутствие ошибок (`read_console_messages`).
Фактически: расширение Claude in Chrome не подключилось к сессии — цикл пройден через Playwright MCP (реальный Chromium). По пути найден и исправлен блокирующий баг CORS (`bot/app/main.py` не разрешал `GET` и заголовок `X-World-Player`) — без фикса ни один запрос из браузера не проходил. После фикса — 0 ошибок в консоли по всему циклу. Подробности и скриншоты — DEVLOG, Сессия 95.

- [x] **Step 5: Проверить восстановление прогресса**

Перезагрузить страницу на фазе `dialogue` (после клика по школе) и убедиться, что игра вернулась в диалог, а не в начало.
Подтверждено: после `reload` игра вернулась в диалог с Фокси (реплика 1 из 3), а не на экран входа.

- [x] **Step 6: Финальные прогоны тестов**

```bash
cd bot && .venv313/bin/python -m pytest -q
cd ../world && npm test && npm run build
```
Expected: бот — 0 failed; world — тесты зелёные, сборка успешна.
Фактически: бот — 1185 passed; world — vitest 3 passed, `npm run build` успешно.

- [x] **Step 7: Запись в DEVLOG**

Добавить в `DEVLOG.md` запись «Сессия 95» по формату соседних записей: запрос владельца, что сделано (пункты по задачам плана), как проверено (числа тестов, скриншоты), решения и нюансы, осталось/следующий шаг (Postgres, auth через miniapp, Meshy-школа, вторая зона).

- [x] **Step 8: Коммит**

```bash
git add DEVLOG.md docs/superpowers/plans/2026-09-13-foxinburg-world-game-loop.md
git commit -m "docs(world): журнал сессии — игровой цикл School Hub работает"
```
