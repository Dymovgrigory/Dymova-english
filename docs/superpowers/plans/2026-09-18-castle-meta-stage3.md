# Замок, этап 3: сезоны, украшения, знамя, примерка — план реализации

**Дата:** 2026-09-18
**Спека:** `docs/superpowers/specs/2026-09-17-castle-meta-design.md`, этап 3.
**Этап 1 (звания + экономика + Мастерская) завершён и на проде** — см. `2026-09-18-castle-meta-handoff.md`.

## Цель

Сцена замка становится стопкой слоёв: сезонная картинка → свет времени суток → погода →
украшения на точках → знамя с эмблемой звания. Покупка — через режим примерки из Мастерской.

## Что уже есть (не переписывать)

- Каталог: сезоны/время/погода/цвета знамени — `world-backend/app/castle/catalog.py`.
- Слои света и погоды на сцене — `world/src/castle/appearance.ts`, `Weather.tsx`.
- Зоны кликов: `castle-hotspots.json` + `masks/{id}.png`, генерятся `world-pipeline/castle_compose.py`.
- Сцена: `world/src/features/castle/CastleScreen.tsx` (`CastleStage`), вписывание — `scene.ts`.
- Meshy: ключ `secrets/meshy.env`, img2img `gpt-image-2-5-flare` (`castle_compose.py`),
  text-to-image (`diorama_art.py`, модель та же).

## Решения

1. **Сезоны — img2img от текущей диорамы** (`castle-diorama.webp`), раскладка хранится
   силой промпта + автовыбором варианта по совпадению кадра (корреляция контуров,
   тот же приём, что в `castle_compose.global_fit`). Каждый сезон получает свои зоны
   кликов и маски — здания могут сместиться на пару пикселей.
2. **Украшения — 14 предметов на авторских точках** (ворота, мост, двор, крыши, ручей,
   луг, стены). Точка фиксирована за предметом (колонка `castle_owned.anchor` уже есть,
   UI выбора точки не делаем — это «примерка на месте»). Купленное стоит сразу,
   снять/поставить — из Мастерской.
3. **Знамя — вектор**: цвет из `appearance.banner_color`, эмблема носимого звания —
   inline-SVG (5 веток + лиса по умолчанию), без расхода кредитов.
4. **Примерка** — overlay поверх замка из Мастерской: та же сцена с превью-обликом,
   лента вариантов внизу, покупка на месте. Превью не трогает сервер.

## Арт-бюджет

Сезоны: 4 × 2 варианта × ~9 кредитов ≈ 72. Украшения: 14 × ~9 ≈ 126. Запас на
перерисовки ≈ 100. Итого ≤ 300 — в рамках спеки.

---

### Task 1: Арт сезонов — `world-pipeline/season_art.py`

**Files:** Create `world-pipeline/season_art.py`; output `world/public/content/castle/seasons/{spring,summer,autumn,winter}.webp`.

- img2img (`/openapi/v1/image-to-image`, flare) от `castle-diorama.webp`, 2 варианта
  на сезон параллельно (`ThreadPoolExecutor`), опрос задачи как в `fuse_once`.
- Промпт на сезон = `SEASON_PROMPTS[season]`: «keep the exact camera, framing, castle,
  buildings and layout; only the season changes» + сезонные детали (снег/цветение/
  листопад/зелень). Стиль CORE из `diorama_art.py`.
- Автовыбор варианта: корреляция контуров с референсом (`edges`+`correlation` из
  `castle_compose.py`), winner → `seasons/{season}.webp` (WEBP q90), проигравший — в
  `world-pipeline/word-art/castle/seasons/` для истории. Печать score обоих.
- Прогон: `python3 world-pipeline/season_art.py` (4 сезона). Визуальная проверка каждого
  (ReadMediaFile): раскладка не съехала, здания на местах. Слабый сезон — перегенерация
  с `--only winter --variants 3`.
- Commit: `feat(world-art): сезонные диорамы замка`.

### Task 2: Зоны кликов сезонов — `castle_compose.py season-masks`

**Files:** Modify `world-pipeline/castle_compose.py`; output `world/src/castle/castle-hotspots-{season}.json`,
`world/public/content/castle/castle-hotspots-{season}.png`, `world/public/content/castle/masks/{season}/{id}.png`.

- Новая команда `season-masks --season winter --pick <fused.png>`: как `masks`, но
  референс для `global_fit` — `castle-diorama.webp` (не `collage.png`), а `placed-*`
  спрайты позиционируются через существующие области базового `castle-hotspots.json`
  (не layout.json): для каждого спота берём его area базы как стартовое окно поиска
  `best_placement`. MANUAL_SILHOUETTES применяются только если score < 0.35 — иначе
  доверяем автоматике; ручные полигоны в этом случае копируем из базы (силуэт тот же).
- Прогон на 4 сезона; проверка `hotspots-preview-{season}.png` глазами; зона каждого
  здания должна сидеть на здании.
- Commit: `feat(world-art): зоны кликов для сезонов замка`.

### Task 3: Клиент — сезонная сцена

**Files:** Create `world/src/castle/seasons.ts` + `seasons.test.ts`; Modify `buildings.ts`,
`CastleScreen.tsx` (`CastleStage`, `SpotHighlight`).

- `seasons.ts`: `SEASONS = ["spring","summer","autumn","winter"]`, `seasonSceneUrl(season)`
  → `/content/castle/seasons/{season}.webp`, `seasonHotspotsUrl`, импорт 4 JSON
  (`castle-hotspots-{season}.json`) статически — `SEASON_SPOTS[season]` строится тем же
  кодом, что `SPOTS` в `buildings.ts` (вынести билдер `buildSpots(hotspots)` и экспортировать).
- `useHotspotMap(season)` — грузит `castle-hotspots-{season}.png`; fallback на базовую
  карту при ошибке загрузки ( сезон без файла не должен ломать сцену).
- `CastleStage` принимает `season: string` (из `effectiveAppearance`): img/bg/masks берутся
  из сезонного набора; размытая подложка тоже сезонная.
- Тесты: `buildSpots` даёт те же SPOTS на базовом JSON; `seasonSceneUrl`; fallback-карта.
- `npx tsc --noEmit`, `npm test`, e2e: на зимнем сезоне клик по Лавке открывает Лавку.

### Task 4: Бэкенд — декор в каталоге и API

**Files:** Modify `world-backend/app/castle/catalog.py`, `service.py`, `state.py`;
Test `world-backend/tests/test_castle_decor.py`.

- 14 предметов `kind="decor"`, `value` = id предмета, новое поле `anchor: str`
  (gate|bridge|courtyard|roofs|stream|meadow|walls). Список:

  | id | Название | anchor | Цена | Условие |
  |---|---|---|---|---|
  | decor-gate-lantern | Фонарь у ворот | gate | 40 | — |
  | decor-gate-pots | Цветочные кашпо | gate | 60 | — |
  | decor-gate-pumpkins | Тыквы у ворот | gate | 60 | — |
  | decor-bridge-garland | Гирлянда на мосту | bridge | 80 | — |
  | decor-stream-boat | Лодочка на ручье | stream | 120 | — |
  | decor-yard-swing | Качели во дворе | courtyard | 100 | — |
  | decor-yard-firepit | Костровая чаша | courtyard | 120 | yard 2 |
  | decor-roof-weathervane | Флюгер-петух | roofs | 60 | — |
  | decor-meadow-sundial | Солнечные часы | meadow | 80 | — |
  | decor-meadow-beehive | Пчелиный улей | meadow | 100 | — |
  | decor-meadow-apple-tree | Яблоня | meadow | 140 | lexicon 2 |
  | decor-wall-gargoyle | Горгулья на стене | walls | 160 | glory 2 |
  | decor-wall-bell | Колокол на стене | walls | 120 | — |
  | decor-gate-fox-statue | Статуя лисы | gate | 200 | nest 3 |

- `view()` отдаёт `decor: [{item_id, anchor, active}]`; купленный декор активен сразу.
- `POST /appearance` принимает `decor_off: [item_id]` / `decor_on: [item_id]` (снять/поставить
  своё). Нельзя поставить чужое/некупленное — 409.
- Тесты: покупка декора с anchor в owned; view показывает активный декор; off/on;
  отказ без звания (fox-statue без nest 3); идемпотентность покупки.
- `pytest -q` зелёный. Commit: `feat(castle): декор в каталоге и API облика`.

### Task 5: Арт украшений — `world-pipeline/decor_art.py`

**Files:** Create `world-pipeline/decor_art.py`; output `world/public/content/castle/decor/{id}.webp`.

- text-to-image flare, 768×768, стиль CORE diorama + «single small handcrafted miniature
  prop on a plain pure white background, contact shadow, no text». Промпт каждого предмета
  в скрипте (RU-ид → EN-описание).
- Альфа: флуд-филл белого от краёв (numpy/PIL, порог 240), feather 1px, обрезка по bbox,
  даунскейл до 512, WEBP q90 с альфой.
- `--only id` для перерисовок. Визуальная проверка контакт-листа (монтаж 4×4).
- Commit: `feat(world-art): украшения замка`.

### Task 6: Клиент — слой украшений

**Files:** Create `world/src/castle/decor.ts` + тест; Modify `CastleScreen.tsx` (`CastleStage`),
`Workshop.tsx` (витрина декора с миниатюрами).

- `decor.ts`: `DECOR_POINTS: Record<anchor, {x,y (доли), width (доля)}>` — точки измерены по
  диораме (ворота ~0.47/0.55, мост, двор, крыши задней стены, берег ручья справа, луг перед
  замком, стены). Каждый предмет: `<img>` в точке, размер по `width`, z-index по y
  (ниже на картинке = ближе = выше z), `drop-shadow` + эллипс контактной тени под предметом
  (div с radial-gradient), фильтр под время суток (`brightness(0.7) sepia` для ночи и т.п. —
  та же логика, что lightLayer, экспортировать `decorFilter(time)`).
- CastleStage рендерит активный декор из `castle.decor` между погодой и SpotHighlight.
- Витрина: в Мастерской декор с миниатюрой `decor/{id}.webp`, ценой, условием.
- Тесты: `decorFilter` по времени; порядок z по y. e2e: купленный фонарь виден на сцене
  (по `data-decor`).

### Task 7: Знамя с эмблемой звания

**Files:** Create `world/src/castle/Banner.tsx`, `emblems.tsx` (5 веток + лиса, inline-SVG);
Modify `CastleStage`; тест `emblems.test.tsx` (эмблема по track id).

- Флаг у главных ворот (точка измеряется по диораме): древко + полотнище цвета
  `banner_color` (палитра BANNER_COLORS из каталога → hex в `decor.ts`/`Banner.tsx`),
  эмблема носимого звания белым штампом; лёгкая CSS-анимация ветра
  (`@keyframes`, выключается `prefers-reduced-motion`).
- Цвета: plum #7c4d8f, emerald #2e8b6e, gold #c9962e, azure #3b7dd8, rose #d35f7f
  (проверить по бренд-гайду перед коммитом).
- e2e: смена цвета знамени в Мастерской меняет `data-banner-color` на сцене.

### Task 8: Примерка (try-on)

**Files:** Create `world/src/features/castle/FittingRoom.tsx`; Modify `Workshop.tsx` (кнопка
«Примерить»), `CastleScreen.tsx`; e2e `world/e2e/castle-fitting.spec.ts`.

- Из Мастерской кнопка «Примерить на замке» открывает overlay: CastleStage в режиме
  `previewAppearance` (локальный state, сервер не трогаем) + лента вариантов выбранной
  категории внизу (карточки: миниатюра/название/цена или условие).
- Выбор варианта обновляет превью мгновенно; «Купить» — POST /buy + /appearance,
  overlay остаётся; «Готово» закрывает. Закрытая вещь — бейдж «Словесник 2 уровня».
- Декор в примерке: превью ставит предмет на его точку локально.
- e2e: примерка Ночи меняет сцену без покупки (монеты не списались — проверка через API);
  покупка в примерке применяется; зоны кликов работают на каждом сезоне (4 клика по Лавке
  при переключённом сезоне — сезон подсовываем через API appearance).

### Task 9: Финал

- `cd world-backend && .venv/bin/python -m pytest -q` — зелёный.
- `cd world && npm test && npx tsc --noEmit -p . && npx eslint` — зелёный.
- E2E (API :8010 + dev :3002 со свежим кодом): все сценарии замка.
- Запись в журнал спринта (skill session-journal), коммит, пуш `world-v2`.
- Деплой — только после явного подтверждения владельца (пересборка world-api и world-web).

## Грабли из этапа 1 (не повторять)

- Тесты бэкенда только через `world-backend/.venv/bin/python` (системный python3.9 не тянет).
- Перед e2e убить старые процессы на :8010/:3002 (`lsof -ti | xargs kill`).
- E2E ходит по ленте локаций и `role="tab"`, не по `data-spot`.
- В `SessionResult.kind` нет `"lesson"`.
- Стиль `docs/world/STYLE_LOCK.md` не менять; правки этого плана — отдельным коммитом до кода.
