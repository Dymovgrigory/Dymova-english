# World v2 — План 1: движок обучения (backend) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Duolingo-подобный движок урока на `/api/v2`: контент Spotlight атомами → сборка сессии → проверка ответов → mastery/SRS → XP, серия, дневная цель, статусы пути.

**Architecture:** Новый пакет `world-backend/app/learning/` рядом с `app/world/` (v1 не трогаем). Контент — JSON на модуль, валидируется pydantic + инвариантами при старте. Эталоны ответов только на сервере; сессия хранит `pending` — индексы заданий, которые ещё не решены верно. Награды — через существующий `core.award` (идемпотентно).

**Tech Stack:** Python 3.13, FastAPI, pydantic v2, SQLite/Postgres через `app/world/db.py`, pytest.

**Spec:** `docs/superpowers/specs/2026-09-17-foxinburg-world-v2-spotlight-engine-design.md`

**Серия планов:** План 1 — этот (backend). План 2 — фронтенд (дизайн-система, урок, путь, онбординг). План 3 — контент Spotlight 1–4. План 4 — арт Meshy.

## Global Constraints

- Запуск тестов: `cd world-backend && .venv/bin/python -m pytest -q`.
- SQL только с `?`-плейсхолдерами и конструкциями, которые переводит `db.adapt_sql` (Postgres-совместимость); без `;` внутри комментариев схемы.
- День ученика — московский (UTC+3), `clock.local_day`.
- Никаких импортов CRM/бота (`tests/test_isolation.py`).
- XP: 10 за узел + 5 без ошибок; `module_test` — 10 × звёзды (≥95/≥80/≥60 %). Монеты: 5 за сессию, 30 за сундук, 50 за первое прохождение контрольной.
- Лимиты сессии: `speak` ≤ 2; один тип не больше 3 подряд; одно и то же задание (атом) не два раза подряд; `teach_*` идёт раньше оцениваемых заданий на тот же атом.
- Дневная цель ∈ {10, 20, 30}. TTL сессии — 2 часа (`410`).
- Контент-каталог: env `LEARN_CONTENT_DIR`, по умолчанию `world-backend/content/spotlight`.

## File Structure

```
world-backend/
  app/learning/
    __init__.py
    errors.py       # LearningError → HTTP-статусы
    clock.py        # now(), local_day() по Москве, add_days()
    content.py      # pydantic-схемы, Course (индексы), validate(), get_course()
    phonics.py      # segment()/readable(): можно ли прочитать слово изученными графемами
    checker.py      # normalize(), Verdict, check_text/choice/pairs/speech
    mastery.py      # atom_mastery: record(), due_atoms(), weakest(), strengths()
    challenges.py   # Challenge + фабрики 16 типов + grade()
    builder.py      # build_session(), build_practice()
    progress.py     # профиль, статусы узлов, награды, серия, сундук
    sessions.py     # start/answer/finish
    views.py        # courses/home/path/words
    api.py          # /api/v2
  content/spotlight/books.json      # SP1–4 метаданные (модули — План 3)
  tests/conftest.py                 # фикстуры learn_course / learn_db
  tests/fixtures/spotlight/{books.json, sp1/m1.json, sp1/m2.json, sp3/m1.json}
  tests/test_learning_{content,phonics,checker,mastery,challenges,builder,progress,sessions,api}.py
  app/world/db.py                   # + 6 таблиц
  main.py                           # + router v2, PUT в CORS, fail-fast загрузка контента
```

---

### Task 1: Контент — схемы, индекс курса, инварианты, фикстуры

**Files:** Create `app/learning/{__init__,errors,clock,content,phonics}.py`, `content/spotlight/books.json`, `tests/fixtures/spotlight/**`, `tests/conftest.py`, `tests/test_learning_content.py`, `tests/test_learning_phonics.py`

**Interfaces — Produces:**
- `errors.LearningError(status)`, `NotFound(404)`, `Conflict(409)`, `Gone(410)`, `BadAnswer(422)`, `ProfileRequired(Conflict, "profile_required")`
- `clock.now() -> datetime`, `clock.local_day(dt) -> "YYYY-MM-DD"`, `clock.add_days(day, n) -> str`
- `content.Book/Word/Phrase/Grammar/GrammarItem/Grapheme/Node/Module`, `content.Course` с методами `book(id)`, `module(id)`, `modules_of(book_id)`, `nodes_of(book_id) -> list[(Module, Node)]`, `node(id) -> (Module, Node)`, `atom(id) -> (Module, Word|Phrase|GrammarItem)`, `grammar(id)`, `grapheme(id)`, `modules_up_to(module_id)`, `word_pool(module_id)`, `phrase_pool(module_id)`, `known_graphemes(node_id) -> list[str]`, `grapheme_inventory() -> list[str]`, `trick_words(module_id) -> set[str]`
- `content.validate(course) -> list[str]`, `content.load_course(dir) -> Course` (raises `ContentError`), `content.get_course()`, `content.reset_cache()`
- `phonics.segment(word, inventory) -> list[str] | None`, `phonics.readable(word, known, inventory) -> list[str] | None`

- [ ] Step 1: тесты — фикстура грузится и `validate == []`; порядок узлов; `known_graphemes("sp1.m1.n1") == []`, `("sp1.m1.n3") == ["a","t","c","d","m"]`; `word_pool("sp1.m2")` начинается со слов m2 и содержит `cat`; validate ловит дубль id, неизвестное слово в узле, фразу с неизученным словом, `module_test` не последним, starter-модуль без phonics; реальный `content/spotlight` грузится. Phonics: `segment("ship", ["s","h","i","p","sh"]) == ["sh","i","p"]`, `readable("cat", {"c","a","t"}, inv)`, `readable("mum", {"m"}, inv) is None`, пробелы/цифры → `None`.
- [ ] Step 2: `pytest tests/test_learning_content.py tests/test_learning_phonics.py` → FAIL (нет модуля).
- [ ] Step 3: реализация по интерфейсам выше; инварианты раздела 5 спецификации + «grammar-узел требует ≥2 фраз с этим grammar_id», «band модуля = band книги».
- [ ] Step 4: тесты → PASS; полный сьют зелёный.
- [ ] Step 5: commit `feat(world-v2): контент Spotlight — схемы, индекс и инварианты`.

### Task 2: Checker

**Files:** Create `app/learning/checker.py`, `tests/test_learning_checker.py`

**Produces:** `Verdict(correct: bool, typo: bool=False)`, `normalize(text) -> str`, `tokens(text) -> list[str]`, `levenshtein(a,b) -> int`, `check_text(answer, accepted, *, allow_typo) -> Verdict`, `check_choice(answer:int, correct:int)`, `check_pairs(answer, pairs)`, `check_speech(transcript, target)` (≥75 % слов цели).

- [ ] Step 1: тесты — `normalize("It’s a CAT!") == "it is a cat"`; `"I'm"`→`"i am"`; accept-варианты; `check_text("pencl", ["pencil"], allow_typo=True) == Verdict(True, True)`; опечатка в слове <5 букв → False; без `allow_typo` опечатка → False; пустой ответ → False; pairs в другом порядке → True, неполные → False; speech `"this is my"` против `"This is my bag."` → True (3/4), `"bag"` → False.
- [ ] Step 2: FAIL → Step 3: реализация → Step 4: PASS → Step 5: commit `feat(world-v2): проверка ответов с сокращениями и опечатками`.

### Task 3: Mastery + таблицы БД

**Files:** Modify `app/world/db.py` (SCHEMA + 6 таблиц: `learner_profile`, `node_progress`, `learn_sessions`, `attempts`, `atom_mastery`, `daily_activity`); Create `app/learning/mastery.py`, `tests/test_learning_mastery.py`

**Produces:** `record(player_id, atom_id, *, correct, now=None) -> int` (верно: сила+1, срок = сегодня + `srs.INTERVALS_DAYS[сила]`; ошибка: сила−1, срок = сегодня), `strengths(player_id, atom_ids) -> dict`, `due_atoms(player_id, *, limit, exclude=frozenset(), now=None) -> list[str]` (слабые и старые первыми), `weakest(player_id, atom_ids, limit) -> list[str]` (стабильно, неизвестные = 0), `weakest_seen(player_id, limit)`.

- [ ] Step 1: тесты — рост силы до 5 и потолок; ошибка не уходит ниже 0 и делает атом due сегодня; `due_atoms` не возвращает атом со сроком в будущем; `exclude`; `weakest` порядок.
- [ ] Step 2–4: FAIL → реализация → PASS (полный сьют — v1 не сломан новой схемой).
- [ ] Step 5: commit `feat(world-v2): сила атомов и сроки повторения`.

### Task 4: Challenges — типы заданий

**Files:** Create `app/learning/challenges.py`, `tests/test_learning_challenges.py`

**Consumes:** content-модели, `checker`, `phonics`.
**Produces:** `@dataclass Challenge(type, atom_id, prompt: dict, solution: dict, graded=True)` с `.public(index)`, `.to_dict()`, `Challenge.from_dict()`; `solution.kind ∈ {none, choice, text, tiles, pairs, speech}` + `display`; фабрики `teach_word, teach_rule, teach_grapheme, listen_pick_image, image_pick_word, read_word_pick_image, read_phrase_pick_image, blend_sounds, translate_pick, match_pairs, letter_sound, sound_letter, spell_tiles, build_phrase, listen_build, grammar_pick, type_word, speak` (неприменимо → `None`); `phrase_tiles(en) -> list[str]`; `grade(ch, answer: dict) -> Verdict` (битый ответ → `BadAnswer`).
Форматы ответа: choice `{"index"}`, text `{"text"}`, tiles `{"tiles": [..]}`, pairs `{"pairs": [[l, r], ..]}`, speech `{"transcript"}` или `{"skip": true}`.

- [ ] Step 1: тесты — `public()` не содержит `solution`; `listen_pick_image` без картинки → None, с картинкой: `options[index].image == word.image`; `match_pairs`: id справа не совпадают по номеру с левыми для seed 1 и `grade` принимает эталон; `build_phrase`: плитки содержат все слова фразы + ≤2 лишних, `grade({"tiles": ["This","is","my","bag"]})` → True; `spell_tiles` без typo-допуска; `grammar_pick` display подставляет ответ; `read_word_pick_image` для нечитаемого → None; `grade(..., {})` → `BadAnswer`.
- [ ] Step 2–4 → Step 5: commit `feat(world-v2): 18 типов заданий и проверка ответа`.

### Task 5: Builder — сборка сессии

**Files:** Create `app/learning/builder.py`, `tests/test_learning_builder.py`

**Produces:** `SessionPlan(node_id, kind, challenges)`, `build_session(course, node_id, *, player_id: int|None, seed: int, allow_speak: bool)`, `build_practice(course, player_id, *, seed, allow_speak)` (<5 заданий → `Conflict("nothing_to_practice")`); константы `MAX_SPEAK=2, MAX_SAME_TYPE_RUN=3, DUE_MIX=3, REVIEW_SIZE=15, TEST_SIZE=15`.

Правила: см. спецификацию 6.2 и 4.1. `words`: teach + 3 оцениваемых на слово (2, если слов >5) + `match_pairs`; `phonics`: teach_grapheme + letter_sound + sound_letter на графему, затем blend/read/spell на читаемых словах пула, SP2+ — `read_phrase_pick_image`; `grammar`: teach_rule + до 6 grammar_pick + build_phrase/translate_pick на фразах правила; `review`: 15 по слабым атомам модуля; `module_test`: 15 без teach и без due. Во все, кроме `module_test`, подмешивается до 3 due-атомов других модулей (без `speak`). Финальная раскладка `_spread` соблюдает лимиты из Global Constraints.

- [ ] Step 1: тесты — для всех узлов фикстуры × seed 0..40: ограничения раскладки; `allow_speak=False` → нет `speak`; `sp1.m1.n1` (3 слова с картинками): 10 оцениваемых; `sp1.m1.n1` — нет `read_word_pick_image` (графем ещё нет); `sp1.m1.n3`: 5 `teach_grapheme`, `blend_sounds` только по `cat`/`dad`; `sp3.m1.n3`: первый `teach_rule`, 4 `grammar_pick`, есть `build_phrase`; `module_test`: 15 оцениваемых, без teach; детерминизм по seed; `chest` → `Conflict`; due-атом `sp1.m1.cat` попадает в `sp1.m2.n1`; practice без истории → `Conflict`.
- [ ] Step 2–4 → Step 5: commit `feat(world-v2): сборка урока по типу узла, полосе и повторению`.

### Task 6: Progress — профиль, статусы пути, награды, серия, сундук

**Files:** Create `app/learning/progress.py`, `tests/test_learning_progress.py`

**Produces:** `DAILY_GOALS`, `Reward(xp, coins, stars, passed)`, `stars_for(accuracy)`, `session_reward(kind, accuracy, wrong)`, `get_profile(player_id)` (нет → `ProfileRequired`), `set_profile(player_id, course, *, book_id, module_id, daily_goal_xp)`, `completed_nodes(player_id) -> dict`, `complete_node(player_id, node_id, *, stars, accuracy, now)` (звёзды/точность — максимум), `node_statuses(course, player_id, book_id, profile) -> {node_id: completed|current|open|locked}`, `next_node_id(course, node_id)`, `record_activity(player_id, xp, *, now) -> {today_xp, streak_days}`, `streak_days(player_id, *, now)`, `today_xp(player_id, *, now)`, `open_chest(external_key, course, node_id, *, now=None)`.

Статусы: книга ниже профиля — всё `open`; книга профиля — узлы до модуля профиля `open`, первый непройденный с модуля профиля `current`, дальше `locked`; книга выше — `locked`, пока не пройдены все контрольные книг от профиля до неё, затем обычная логика с начала.

- [ ] Step 1: тесты — пороги звёзд; награды; профиль sp1.m2 → узлы m1 `open`, `sp1.m2.n1` `current`, остальные `locked`, sp3 `locked`; профиль sp3.m1 → sp1 весь `open`; после `complete_node` текущим становится следующий; серия через полночь по Москве (20:30Z и 21:30Z одного UTC-дня = 2 дня), пропуск дня обнуляет; `set_profile` с чужим модулем/целью 15 → `NotFound`/`Conflict`; сундук: монеты +30, повторно → `Conflict`, locked → `Conflict`.
- [ ] Step 2–4 → Step 5: commit `feat(world-v2): прогресс пути, награды, серия и дневная цель`.

### Task 7: Sessions — старт, ответ, финиш

**Files:** Create `app/learning/sessions.py`, `tests/test_learning_sessions.py`

**Produces:** `start(external_key, node_id, *, allow_speak, seed=None, now=None) -> {session_id, node_id, kind, challenges[public], graded_total}` (`node_id="practice"` → тренировка; locked → `Conflict("node_locked")`); `answer(external_key, session_id, index, payload, *, response_ms=None, now=None) -> {correct, typo, skipped, solution, requeued, remaining}`; `finish(external_key, session_id, *, now=None) -> {xp, coins, stars, passed, accuracy, duration_sec, mistakes, streak_days, today_xp, daily_goal_xp, goal_reached, node_completed, next_node_id, player}`.

Правила: ответ на уже решённое → `Conflict("challenge_done")`; после TTL → `Gone("session_expired")`; ошибка → индекс остаётся в `pending` (`requeued=True`), кроме `module_test`; `speak` + `skip` закрывает задание без учёта в точности; mastery и точность считаются по первой попытке; каждая попытка пишется в `attempts`; `finish` при непустом `pending` → `Conflict("session_not_complete")`, повторный `finish` возвращает сохранённый результат; награда через `core.award(idempotency_key=f"v2:{session_id}")`.

- [ ] Step 1: тесты — полный проход `sp1.m1.n1` с одной ошибкой (requeue → повтор → finish: xp 10, accuracy < 1, узел пройден, next = `sp1.m1.n2`); без ошибок → xp 15; повторный finish не начисляет повторно; ранний finish → Conflict; TTL → Gone; `module_test` с 50 % → `passed=False`, узел не пройден; skip speak; attempts пишутся.
- [ ] Step 2–4 → Step 5: commit `feat(world-v2): жизненный цикл сессии урока`.

### Task 8: Views + API `/api/v2` + подключение

**Files:** Create `app/learning/views.py`, `app/learning/api.py`, `tests/test_learning_api.py`; Modify `main.py`

**Produces (HTTP):** `GET /api/v2/courses`; `GET|PUT /api/v2/profile`; `GET /api/v2/home`; `GET /api/v2/path?book_id=`; `POST /api/v2/sessions`; `POST /api/v2/sessions/{id}/answer`; `POST /api/v2/sessions/{id}/finish`; `POST /api/v2/nodes/{node_id}/chest`; `POST /api/v2/practice`; `GET /api/v2/words?book_id=`. Авторизация — `X-World-Player` через `app.world.api._player_key`. Ошибки `LearningError` → `HTTPException(status, detail)`.

- [ ] Step 1: тест сценария по HTTP: игрок → `home` 409 `profile_required` → `PUT profile` → `path` (current `sp1.m1.n1`) → locked узел 409 → сессия → ответы (одна ошибка) → finish → `home` показывает xp/серию/следующий узел → `words` содержит `cat` с силой ≥1 → chest 409 пока locked → practice 409.
- [ ] Step 2–4 → `main.py`: `include_router`, `PUT` в CORS, `content.get_course()` в startup.
- [ ] Step 5: полный сьют + `tests/test_isolation.py` зелёные; commit `feat(world-v2): API /api/v2 для урока, пути и профиля`.
