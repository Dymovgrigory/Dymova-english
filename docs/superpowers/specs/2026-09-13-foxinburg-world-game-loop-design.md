# Foxinburg World — игровой цикл School Hub (v1)

Дата: 2026-09-13. Статус: утверждено владельцем.
Контекст: `docs/world/architecture.md`, `docs/world/world-art-bible.md`,
DEVLOG «Сессия 94». Продолжение vertical slice: бэкенд-ядро готово
(игроки, идемпотентный ledger, квест `first-day-at-foxinburg`, инвентарь,
unlocks, 8 тестов), фронтенд — пустой скаффолд Next 16 + R3F.

## 1. Цель

Довести до рабочего состояния полный игровой цикл первого дня:
**HUD → квест → диалог с Фокси → vocabulary-челлендж → reward cinematic →
разблокировка зоны**. Цикл проходится в браузере целиком, награды
начисляются сервером, прогресс переживает перезагрузку страницы.

## 2. Принятые решения

| Развилка | Решение | Причина |
|---|---|---|
| Навигация | Кинематографические хотспоты: камера едет между именованными точками, клик по подсвеченным объектам | Стабильно на мобиле, кадр всегда композиционно верный, нет контроллера персонажа в критическом пути |
| Челлендж | 2D glass-оверлей Game OS поверх 3D | Читаемость и WCAG AA (§114), 3D продолжает жить фоном |
| Слова | Экспорт 16 тем (~460 слов) из `prototype/pages_words*.py` и `build_subpages.py`, проверка ответов на сервере | Контент уже написан и вычитан; server-authoritative (§84) — накрутить награду из консоли нельзя |
| Здание школы | Процедурная геометрия R3F по арт-библии + готовые GLB Фокси и FoxCoin | Ноль кредитов Meshy, правки сцены — кодом; генерация здания — отдельный шаг после рабочего цикла |

## 3. Игровой цикл

Конечный автомат из пяти фаз, ведомый шагами квеста `first-day-at-foxinburg`
(шаги уже лежат в БД: `visit school-hub` → `talk foxi` → `activity
vocabulary-challenge-1`).

| Фаза | 3D | UI |
|---|---|---|
| `boot` | загрузка ассетов, облёт двора | заставка с прогрессом, ввод имени |
| `explore` (шаг 1) | школа подсвечена yellow-обводкой | HUD + трекер «Найди школу Фоксинбурга» |
| `dialogue` (шаг 2) | камера к Фокси, клип `Big_Wave_Hello` | облако реплик, кнопка «Погнали» |
| `challenge` (шаг 3) | сцена уходит в расфокус | glass-оверлей: 5 вопросов |
| `reward` | reward cam (1.8 u, 30° FOV, low-angle), `Cheer_with_Both_Hands_Up`, вихрь FoxCoin'ов | `+60 XP` / `+30` Montserrat ExtraBold, level-up, unlock Library Courtyard |

После `reward` — возврат в `explore` с обновлённым HUD и зоной
Library Courtyard, проявившейся из тумана.

Доступные клипы Фокси (проверено в GLB): `Big_Wave_Hello`,
`Cheer_with_Both_Hands_Up`, `Happy_jump_f`, `Running`,
`Shake_It_Off_Dance`, `Walking`. Level-up = `Happy_jump_f`.

## 4. Границы модулей (фронтенд)

`src/engine/*` — знает про three, не знает про игру. Единственный импортёр
three в проекте (граница замены движка, architecture.md §12):

- `Stage.tsx` — Canvas, renderer, адаптивный DPR
- `Lighting.tsx` — warm sun + cool ambient + fog, пресет Day
- `CameraRig.tsx` — именованные точки съёмки, damped-переход
- `Hotspot.tsx` — интерактивный объект: hover/press scale 0.96→1, yellow-glow
- `Foxi.tsx` — GLB + state machine клипов с crossfade
- `FoxCoin.tsx` — вращение, эмиссия, режим «вихрь наград»
- `SchoolBuilding.tsx`, `Courtyard.tsx` — процедурная chibi-геометрия
- `Fireflies.tsx` — ambient-частицы (§179)
- `Postfx.tsx` — subtle bloom + vignette
- `quality.ts` — профиль ULTRA/HIGH/MEDIUM/LOW → DPR, тени, post-FX

`src/game/*` — знает про правила, не импортирует three:

- `store.ts` — zustand: игрок, квест, фаза, оверлеи; чистые редьюсеры фаз
- `hud/Hud.tsx` — аватар Фокси, XP bar, FoxCoins, индикатор квеста
- `dialogue/FoxiDialogue.tsx` — реплики по шагам
- `activities/VocabularyChallenge.tsx` — 5 вопросов, мгновенный фидбек
- `reward/RewardCinematic.tsx` — последовательность награды

Связь слоёв — через стор и колбэки хотспотов; `src/ui/*` — glass-панель,
кнопка, прогресс (база Game OS §55).

## 5. Бэкенд

Три добавления в существующий модуль `bot/app/world/`.

**5.1 Экспорт словаря** — `scripts/export_world_vocabulary.py`: разбор
16 списков `WORDS_*` через `ast.literal_eval` (без импорта модулей сайта)
из `prototype/build_subpages.py`, `pages_words2.py`, `pages_words3.py` →
`bot/app/world/data/vocabulary.json`:

```json
{"themes": [{"id": "zhivotnye", "title_ru": "Животные",
  "words": [{"en": "cat", "ipa": "[kæt]", "ru": "кошка",
             "example_en": "...", "example_ru": "..."}]}]}
```

Сайт не изменяется. Скрипт идемпотентен, перезапуск даёт тот же JSON.

**5.2 Активности** — `bot/app/world/activities.py` + таблица
`activity_sessions` (id, player_id, activity_id, payload JSON с вопросами
и правильными ответами, answers JSON, status, score, created_at,
completed_at):

- `start(player, activity_id)` → создаёт сессию, отдаёт 5 вопросов
  **без** правильных ответов (слово EN + 4 варианта перевода)
- `answer(session, index, choice)` → сверяет с серверной копией,
  возвращает `{correct, correct_choice}`; повторный ответ на тот же
  вопрос — `Conflict`
- `finish(session, idempotency_key)` → считает результат, начисляет через
  существующий `core.award` (`XP_REWARDS["vocabulary_challenge"]`=25,
  `COIN_REWARDS`=10, бонус за 5/5), продвигает шаг квеста; повторный
  вызов — no-op с тем же ответом (§160)

**5.3 Шаг квеста** — `POST /api/world/quests/{id}/step`: продвижение
на сервере с проверкой порядка шагов, чтобы прогресс переживал
перезагрузку страницы.

Новые маршруты: `POST /api/world/activities/vocabulary/start`,
`POST /api/world/activities/{session}/answer`,
`POST /api/world/activities/{session}/finish`,
`POST /api/world/quests/{id}/step`.

## 6. Тестирование

- Бэкенд (TDD, `bot/tests/test_world_activities.py`): выдача вопросов без
  правильных ответов, валидация ответа, двойной ответ → 409, двойной
  finish → те же цифры и одна запись в ledger, продвижение шага квеста,
  чужая сессия недоступна. Плюс тест парсера словаря.
- Фронтенд (vitest): чистые редьюсеры фаз стора — переходы
  `boot→explore→dialogue→challenge→reward→explore`, запрет переходов
  через фазу.
- Сборка: `cd world && npm run build` без ошибок типов.
- Живой прогон: `uvicorn` + `next dev`, полный цикл в Chrome, скриншот
  каждой фазы; проверка, что после перезагрузки на шаге 2 игра
  восстанавливает состояние.

## 7. Вне объёма этой итерации

Контроллер персонажа и физика Rapier, звук, генерация здания в Meshy,
Postgres-слой, привязка `X-World-Player` к CRM child id, вторая зона
(Library Courtyard остаётся силуэтом за туманом), мультиплеер.

## 8. Риски

- Next 16 и React 19 + R3F 9 — breaking changes; при сомнениях читать
  `world/node_modules/next/dist/docs` (записано в `world/AGENTS.md`).
- Размер `foxi-rigged.glb` 726 КБ — в бюджет boot < 5 s укладывается,
  но требует preload и заставки, а не белого экрана (§152).
- Процедурная школа может выглядеть беднее концепт-арта — принято
  сознательно, полировка геометрии и Meshy-здание идут следующим шагом.
