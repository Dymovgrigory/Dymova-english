# Foxinburg World — World Art Bible (STEP 4, бриф §222)

Статус: v1 (2026-09-13). Обязателен для любого ассета/сцены/экрана мира.
Никаких случайных отклонений — бренд узнаваем всегда (§107, §224, §245).

## 1. Визуальная формула (§36)

**PREMIUM CINEMATIC FANTASY × FOXINBURG BRAND** — ориентир качества:
кадры в `world/public/world/cinematic/` (`establishing.jpg`, `gates-foxi.jpg`,
`library-courtyard.jpg`) и hub-карта `world/public/world/castle/map.png`
(cinematic v2, layout-preserving). Это «дорогой фильм / AAA fantasy»: объёмный
камень, golden-hour + lantern light, teal/purple dual tone, туман, единая сцена
без «картинка поверх картинки». Не flat cartoon, не generic AI purple dashboard.

Формула: cinematic lighting + stylized PBR + educational clarity.

## 2. Цвет (§106)

Ядро — официальная палитра брендбука (`brand-assets/brand-guide.pdf`):

| Токен | Hex | Роль |
|---|---|---|
| `world.purple` | `#3a2953` | основа мира: архитектура, ткани, вторичные поверхности |
| `world.purple-dark` | `#241a30` | ночной режим, тени, глубина, HUD-фон (glass) |
| `world.yellow` | `#f5ed75` | фирменный акцент: награды, XP, интерактивные подсветки, эмиссия |
| `world.ink` | `#ffffff` | текст, иконки |
| `world.near-black` | `#2a2a2a` | графика/печать |

Расширение для мира (semantic, не rainbow-хаос):
- `zone.school` — тёплый purple + yellow (дом, безопасность);
- `zone.library` — deep purple + teal-ish glow `#7fd8c9` (знания, магия книг);
- `zone.english-street` — purple + кирпично-тёплый `#c96f4a` + yellow свет окон;
- `reward.gold` — `#f5ed75` → `#e8b93e` градиент (FoxCoins, трофеи);
- `rarity` — common `#b8b8c4`, uncommon `#7fd8c9`, rare `#5aa9ff`,
  epic `#b07fff`, legendary `#f5ed75`, mythic `#ff8ad8` (§17; редкость —
  через материал/свет/звук, не только цвет §198).

Правило: один доминирующий hue на зону + yellow как универсальный
«интерактивный» сигнал. Контраст текста ≥ AA (WCAG, §114).

## 3. Типографика (§110)

- Display/игровая: **Montserrat** (ExtraBold/Bold, italic для акцентов — как на сайте).
- UI/тексты: **DM Sans** (Regular/Medium).
- Числа наград (XP +100): Montserrat ExtraBold + анимация «полёт к цели» (§110).
- Кириллица first (UI — русский, §171), шрифты уже используются на сайте —
  никаких новых семейств без решения бренд-директора.

## 4. Мир: пропорции и масштаб (§225)

- 1 engine unit = 1 метр. Высота «ребёнка-аватара» ≈ 1.2 u; Фокси ≈ 0.9 u;
  двери 2.2 u; школа (hub) ≈ 12–14 u высотой — слегка «игрушечные» пропорции
  (chibi-архитектура: окна/двери крупнее реальных на ~15%).
- Камера стандартная (§226): world cam — 6–8 u дистанция, 35–40° FOV,
  высота 2.5–3.5 u; reward cam — 1.5–2 u, 30° FOV, лёгкий low-angle.

## 5. Материалы (§37)

Stylized PBR: rounded edges, мягкие нормали, приглушённый roughness-range
0.35–0.8. Дерево/ткань/кирпич — тёплые; металл/стекло — только в акцентах
(portals, coins, trophies, hologram UI). FoxCoin — золотой металлик с
эмбоссом лапки/мордочки Фокси (§12, собственный 3D-объект, не иконка).
Запрещено: фотореалистичные текстуры, generic flat low-poly без градиентов.

## 6. Свет и атмосфера (§38, §29)

- База: warm directional (sun) + cool ambient (purple-dark bounce) +
  emissive accents (yellow окна/порталы/FX).
- Day states: Morning (розово-золотой), Day (чистый), Sunset (кинематографик,
  длинные тени), Night (purple-dark + emissive мир оживает).
- Post: bloom (subtle), vignette (subtle), color grading к тёплому mid,
  SSAO/аналог, fog для глубины. Не максимум постоянно (§39).
- Particles: fireflies/пылица в воздухе всегда чуть-чуть — мир не мёртв (§179).

## 7. Фокси (§224)

Канон: `prototype/mascot/foxi-rigged.glb` (Meshy biped, 6 клипов) —
пропорции, текстура, рюкзак не меняем. Расширение анимаций (§43) — только
через Meshy rig на ту же модель (state machine: IDLE/WALK/RUN/WAVE/POINT/
CELEBRATE/SAD/SURPRISED/THINKING/SLEEP/DANCE/LEVEL_UP, плавные crossfade).
Outfits — отдельные меши поверх, силуэт и мордочка неизменны.

## 8. Зоны v1 (§4)

- **Foxinburg School (hub):** уютное «замок-школа» здание, башенка с часами,
  флаги, двор с фонтаном; тёплый свет окон; доска объявлений.
- **Library Courtyard (первый unlock):** портал-арка из парящих книг,
  teal-glow светильники, лавочки, лепестки/страницы в воздухе.
- Locked-зоны: silhouette + туман + цепь с замком в фирменном стиле —
  продуманный locked state, не gray box (§220).

## 9. UI = Game OS (§55)

Glass-панели (purple-dark 70% + blur), скругления 16–24px, yellow-акценты,
3D-превью предметов в карточках, Montserrat для чисел/заголовков.
HUD минимален (§56): Фокси-аватар, XP bar, FoxCoins, quest indicator, меню.
Никаких LMS-таблиц в детском режиме; utility-UI — только admin (§119).

## 10. Звук (§53) — краткая установка

Мягкие pluck/mallet для UI, coin — «золотой звон + искры», level-up —
короткий фанфар-мотив; ambient: птицы/листья днём, сверчки ночью. Всё
mutable, lazy-load по зонам (§178).

## 11. Motion-иерархия (§109)

PRIMARY: награды, level-up, unlock (камера+типографика+свет+звук §111).
SECONDARY: hover/press (scale 0.96→1, glow). AMBIENT: облака, частицы,
NPC-движение. MICRO: иконки, счётчики. Запрещено: постоянное bouncing,
хаотичное движение всего сразу.

## 12. Ассет-правила (§51–52)

Каждый ассет: ≤ 15k tris (props), ≤ 60k (здания hub), текстуры 512–1024
webp, 1–2 материала, LOD0/LOD1, collider box/mesh, draco+meshopt, запись в
asset registry (id, type, lod, variants, deps). Имя: `zone-object-vN.glb`
(snake-case). Ничего не импортируется без записи в manifest.
