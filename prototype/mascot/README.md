# Фокси — живой 3D-маскот на сайте

Ригнутый маскот (Meshy biped, 17 скелетных клипов) ходит по нижней кромке
экрана поверх всех страниц и реагирует на поведение посетителя. Подключён
на всех 30 страницах через `build_static_site.py` (сессия 41).

## Файлы

- `mascot.js` — движок маскота (Three.js, ES-модуль, динамический импорт
  three ПОСЛЕ `load` + `requestIdleCallback` — LCP не страдает).
- `foxi-rigged.glb` — рабочая модель: `Meshy_AI_Foxyburg_Mascot_biped_*_Merged_Animations.glb`
  (13,66 МБ) → `@gltf-transform/cli optimize --compress draco
  --texture-compress webp --texture-size 512 --simplify false` → **1,17 МБ**.
  17 клипов: Walking, Walk_Backward, Running, Stumble_Walk, Regular_Jump,
  Wave_for_Help_1/3, FunnyDancing_03, You_Groove, jazz_danc, Fast_Lightning,
  Walk_Turn_Left/Right, Walk_Turn_Right_Female, Walk_Turn_Left_with_Weapon,
  Walk_Turn_Right_Idle_Style, Run_Turn_Right. Кость головы — `Head`.
- `foxi.glb` — старая статичная модель без рига (про запас, не подключается).
- `index.html`, `test-rigged.html` — локальные демо.

## Поведение (все клипы задействованы)

| Контекст | Клип |
|---|---|
| idle (база) | You_Groove на timeScale 0.22 — еле заметное покачивание |
| медленный скролл вниз | Walking (шагает вправо) |
| медленный скролл вверх | Walk_Backward (отступает спиной) |
| быстрый скролл (>2600 px/с) | Running |
| рывки туда-сюда (3+ смены направления/1.2с) | Stumble_Walk |
| доскроллил до низа страницы | FunnyDancing_03 / jazz_danc (раз в 60 сек) |
| наведение на CTA заявки | Wave_for_Help_1 (кулдаун 10 сек) |
| клик по CTA | Fast_Lightning ×3.2 (кулдаун 10 сек) |
| клик рядом с маскотом | Regular_Jump (иногда Wave_for_Help_1) |
| скука (каждые 8–18 сек) | прогулка Walking / развороты (все 6 turn-клипов) / Wave_for_Help_3 / jazz_danc |
| курсор рядом | голова (кость `Head`) следит за мышью поверх клипа |

## Не мешает читать

- живёт в нижней полосе экрана, стартует у левой кромки;
- canvas `pointer-events: none` — клики проходят сквозь;
- правый нижний угол (чат-виджет) — запретная зона (`reserveRightPx`);
- скрытая вкладка — рендер на паузе; `prefers-reduced-motion` и слабые
  устройства (hardwareConcurrency<4, deviceMemory<4, saveData) — маскот
  не загружается вовсе.

## Подключение (уже встроено в build_static_site.py)

```html
<script type="importmap">{"imports":{"three":"…0.180.0/build/three.module.js",
"three/addons/":"…0.180.0/examples/jsm/"}}</script>
<script>window.FOXI_CONFIG={modelUrl:'/mascot/foxi-rigged.glb'};</script>
<script type="module" src="/mascot/mascot.js"></script>
```

ВАЖНО: importmap обязан идти раньше первого `<script type="module">`
на странице (поэтому в WOW_SNIPPET он первой строкой).

## API для сайта

`window.FOXI` (после загрузки модели): `wave()`, `jump()`, `dance()`,
`walk()`, `_state`/`_scroll` — отладка.

## Конфиг (`window.FOXI_CONFIG`)

| Ключ | По умолчанию | Описание |
|---|---|---|
| `modelUrl` | `./foxi-rigged.glb` | путь к GLB |
| `headBone` | `head` | подстрока имени кости головы |
| `height` / `mobileHeight` | `1.0` / `0.72` | высота маскота (автомасштаб) |
| `faceOffset` | `0` | добавка к yaw (модель смотрит в +Z) |
| `walkSpeed` / `runSpeed` | `1.7` / `3.6` | юнитов/сек |
| `reserveRightPx` | `120` | запретная зона справа (чат-виджет) |
| `minDelay`/`maxDelay` | `8`/`18` | паузы между «поступками», сек |
| `hideUnderWidth` | `0` | >0 — отключить на узких экранах |

## Замена модели

Если пришлют новый GLB: прогнать через gltf-transform (команда выше),
проверить имена клипов (парсинг GLB JSON или консоль `[foxi]`), при
другом направлении лица подобрать `faceOffset` (0 или `Math.PI`).
