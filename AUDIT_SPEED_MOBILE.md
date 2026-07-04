# Аудит скорости и мобильной вёрстки — Спринт 1

**Дата:** 4 июля 2026  
**Что это:** аудит скорости и мобильной вёрстки 14 боевых страниц сайта Foxinburg (dymova-english.ru) в рамках Спринта 1.

## Скорость / Core Web Vitals (Lighthouse 12.8.2, mobile-профиль)

INP в этой версии Lighthouse не отображается, поэтому в таблице он указан как `n/a`.  
HTML/JSON-отчёты лежат в `/home/ubuntu/lh/` и в репозиторий не коммитились.

| Страница | Score | LCP | CLS | TBT | FCP | Speed Index | INP | Вес, KB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `/` | 38 | 18.6s | 0.00 | 862ms | 6.2s | 7.8s | n/a | 3736 |
| `/doshkolniki` | 56 | 12.3s | 0.05 | 0ms | 9.3s | 9.3s | n/a | 1828 |
| `/mladshie-shkolniki` | 76 | 4.4s | 0.00 | 23ms | 3.3s | 4.9s | n/a | 485 |
| `/podrostki` | 77 | 4.7s | 0.03 | 0ms | 3.1s | 3.4s | n/a | 486 |
| `/reading` | 54 | 4.6s | 0.68 | 48ms | 3.2s | 3.6s | n/a | 485 |
| `/grammar` | 55 | 4.7s | 1.11 | 0ms | 2.5s | 2.5s | n/a | 485 |
| `/preparation` | 79 | 4.3s | 0.03 | 25ms | 3.1s | 3.4s | n/a | 485 |
| `/online-zanyatiya` | 78 | 4.4s | 0.06 | 2ms | 3.2s | 3.5s | n/a | 485 |
| `/podderzhivayushchie-online` | 54 | 4.8s | 0.94 | 2ms | 2.6s | 2.6s | n/a | 485 |
| `/standartnye-offline` | 54 | 4.8s | 0.94 | 4ms | 2.6s | 2.6s | n/a | 485 |
| `/letnyaya-akademiya` | 55 | 4.5s | 0.61 | 45ms | 3.1s | 3.5s | n/a | 485 |
| `/kontakty` | 65 | 7.5s | 0.00 | 12ms | 3.9s | 5.2s | n/a | 942 |
| `/novosti` | 80 | 4.1s | 0.06 | 31ms | 3.0s | 3.4s | n/a | 449 |
| `/vakansii` | 74 | 4.8s | 0.06 | 5ms | 3.6s | 3.8s | n/a | 518 |

## Приоритетные проблемы и рекомендации

### 1) Главная страница `/`
- Score: 38, LCP: 18.6s, CLS: 0.00, TBT: 862ms, вес: 3736 KB.
- Основной LCP-элемент — декоративный hero/фото-блок; он рендерится слишком поздно на мобильном.
- Самые тяжёлые и неэффективные ресурсы:
  - `https://yastatic.net/s3/front-maps-static/maps-front-jsapi-v2-1/2.1.79-19906405/out/release/full.js` — 697.9 KB total, 471.7 KB wasted.
  - `https://static.tildacdn.com/js/tilda-catalog-1.1.min.js` — 76.9 KB total, 74.9 KB wasted.
  - `https://static.tildacdn.com/js/tilda-forms-1.0.min.js` — 31.9 KB total, 28.4 KB wasted.
  - Изображения: `prototype/team-media/kovalenko.jpg` — 186.7 KB, `prototype/team-media/salyahova.jpg` — 171.0 KB, `brand-assets/fox-head-yellow.png` — 141.8 KB.
- Что делать:
  - убрать или отложить карты, каталог и forms.js с первого экрана;
  - перевести фото и декоративные PNG в WebP/AVIF;
  - отдавать изображения в размерах, близких к фактическому отображению;
  - lazy-load для всего, что ниже первого экрана;
  - для T123-блоков держать кастомный JS минимальным и не дублировать один и тот же код на всех страницах.

### 2) `/doshkolniki`
- Score: 56, LCP: 12.3s, CLS: 0.05, TBT: 0ms, вес: 1828 KB.
- Проблемы:
  - render-blocking: `https://static.tildacdn.com/js/jquery-1.10.2.min.js`, `tilda-blocks-page151228606.min.css`, `tilda-grid-3.0.min.css`;
  - SoundCloud тянет внешние origin’ы (`wave.sndcdn.com`, `api-widget.soundcloud.com`, `widget.sndcdn.com`);
  - тяжёлые декоративные изображения: `brand-assets/fox-head-yellow.png` — 141.8 KB, `brand-assets/decor-swirl-yellow-1.png` — 65.5 KB, `brand-assets/decor-zigzag-yellow.png` — 61.1 KB.
- Что делать:
  - ускорить hero-блок и LCP-картинку;
  - не тянуть SoundCloud до взаимодействия пользователя;
  - перевести hero/декор в WebP/AVIF и ужать их;
  - по возможности убрать jQuery с этой страницы.

### 3) `/reading`
- Score: 54, LCP: 4.6s, CLS: 0.68, TBT: 48ms, вес: 485 KB.
- Основная CLS-проблема — блок `#rec2422858251` (сдвиг содержимого в середине страницы).
- Проблемы:
  - render-blocking: `jquery-1.10.2.min.js`, `tilda-blocks-page151292376.min.css`, `tilda-grid-3.0.min.css`;
  - изображения: `brand-assets/fox-head-yellow.png` — 141.8 KB, `brand-assets/decor-zigzag-yellow.png` — 61.1 KB, `brand-assets/decor-swirl-yellow-1.png` — 65.5 KB.
- Что делать:
  - зарезервировать высоты/ширины для hero и ключевых секций;
  - проверить lazy-load, чтобы он не создавал сдвиги выше фолда;
  - уменьшить изображения и перевести их в WebP/AVIF;
  - проверить, не отрисовываются ли поздно видео/фото-блоки.

### 4) `/grammar`
- Score: 55, LCP: 4.7s, CLS: 1.11, TBT: 0ms, вес: 485 KB.
- Самая тяжёлая CLS-проблема в наборе: `#fxb-program` и связанные с ним секции.
- Дополнительно в отчёте видны веб-шрифты Montserrat из `fonts.gstatic.com`, которые могут участвовать в сдвиге.
- Проблемы:
  - render-blocking: `jquery-1.10.2.min.js`, `tilda-blocks-page151292406.min.css`, `tilda-grid-3.0.min.css`;
  - изображения: `brand-assets/fox-head-yellow.png` — 141.8 KB, `brand-assets/decor-swirl-yellow-1.png` — 65.5 KB, `brand-assets/decor-zigzag-yellow.png` — 61.1 KB.
- Что делать:
  - зафиксировать размеры секций и блоков;
  - preload/self-host ключевые шрифты;
  - включить `font-display: swap`;
  - не допускать поздней подгрузки элементов над фолдом;
  - оптимизировать изображения и декоративные PNG.

### 5) `/kontakty`
- Score: 65, LCP: 7.5s, CLS: 0.00, TBT: 12ms, вес: 942 KB.
- Проблемы:
  - render-blocking: `jquery-1.10.2.min.js`, `tilda-blocks-page151228006.min.css`, `tilda-grid-3.0.min.css`;
  - карта требует `preconnect` к `maps.yastatic.net`;
  - тяжёлые декоративные изображения: `brand-assets/fox-head-yellow.png`, `brand-assets/decor-swirl-yellow-1.png`, `brand-assets/decor-zigzag-yellow.png`.
- Что делать:
  - грузить карту только после клика или реального скролла к блоку;
  - сократить JS/CSS на первом экране;
  - перевести изображения в WebP/AVIF;
  - проверить, не блокирует ли карта основной контент.

### 6) `/standartnye-offline` и `/podderzhivayushchie-online`
- Обе страницы: Score 54, CLS 0.94.
- Основные источники сдвигов:
  - hero `img.fxb-hd2`;
  - секция `#fxb-program`;
  - поздняя отрисовка текста и графики в середине страницы.
- Что делать:
  - зафиксировать размеры hero-контейнеров;
  - не позволять изображению и тексту менять высоту блока после первого рендера;
  - проверить шрифты и lazy-load внутри секции;
  - перевести декоративные изображения в WebP/AVIF.

## Итог по приоритетам

1. **Главная:** убрать неиспользуемый JS и перевести крупные изображения в WebP/AVIF.
2. **CLS на `grammar` / `reading` / офлайн-форматах:** фиксированные размеры блоков + шрифты без сдвигов.
3. **`doshkolniki`:** ускорить hero/LCP и отложить SoundCloud.
4. **`kontakty`:** отложить карту и не тянуть её в первичную отрисовку.

## Аудит мобильной вёрстки (390px, iPhone-эмуляция)

Проверка выполнена по скриншотам и наблюдениям в `/home/ubuntu/mobile_audit/`.

- Горизонтального скролла нет ни на одной из 14 страниц: `scrollWidth == clientWidth == 390` везде.
- Элементы, которые визуально выходят за вьюпорт, — это только декоративные картинки (`img.fxb-hero-decor`, `img.fxb-ft-decor` и похожие). Они обрезаются контейнерами с `overflow`, это не баг.
- Шапка, бургер-меню, hero, карточки, формы и футер рендерятся корректно на мобильном. Проверены главная, курсы, направления, контакты и вакансии.

### Минорные замечания для владельца

- `/kontakty`: блок «Наши филиалы на карте» в мобильном скриншоте отрисовался пустым белым прямоугольником. Вероятно, карта грузится лениво или по взаимодействию; стоит проверить, что она реально появляется на мобиле.
- На страницах курсов и направлений, например `/reading` и `/podrostki`, в середине страницы видны большие пустые фиолетовые вертикальные промежутки. Похоже на секции с фото/видео, которые подгружаются лениво и не успевают появиться при автоскролле; это совпадает с выводами по тяжёлым медиа и lazy-load.
- Декоративные PNG грузятся в полном размере; это пересекается с выводами по скорости — их стоит перевести в WebP и ужать.

### Вывод

Критичных поломок мобильной вёрстки нет. Основной резерв улучшений — производительность (изображения/JS) и CLS, а не сломанная раскладка.
