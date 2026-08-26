# 02. Архитектура сайта

## Общая схема

Сайт — самописная статическая сборка: генераторы в `prototype/` собирают полноценные HTML-страницы из блоков и контентных фрагментов, результат раскладывается в `prototype/dist*/` и отдаётся Caddy (см. `bot/deploy/Caddyfile`).

### Главная

Главная собирается в `prototype/main_combined_v7.html` из канонических блоков.

Канонический порядок блоков:

1. `block_header_unified_min.html`
2. `block_cta_enrollment_min.html`
3. `block_advantages_min.html`
4. `block_directions_min.html`
5. `block_onboarding_min.html`
6. `block_team_min.html`
7. `block_languages_min.html`
8. `block_photobank_gallery_min.html`
9. `block_pricing_enrollment_min.html`
10. `block_yandex_reviews_min.html`
11. `block_faq_min.html`
12. `block_svedeniya_min.html`
13. `block_contacts_map_min.html`
14. `block_footer_min.html`

### Подстраницы

Канонические URL подстраниц генерируются `build_subpages.py` и `build_course_pages.py`; алиасы страниц заданы в `PAGE_ALIASES` в `build_static_site.py`. Старые адреса (`/reading-old`, `pageXXXXX.html` и т.п.) закрыты 301-редиректами в `bot/deploy/Caddyfile`.

### Логика модалки заявки

- открытие заявки завязано на `data-fxb-zayavka`;
- обработчик в футере открывает модалку на уровне `document`;
- кнопка/ссылка в onboarding не должна глушить клики по `<a>`.

### Сборка

- `make build` / `python3 prototype/devflow.py build` — пересобрать страницы из генераторов;
- `make minify` — обновить минифицированные блоки в `prototype/blocks_min/`;
- `prototype/build_static_site.py` — финальная статическая сборка в `dist/` (прод), `dist_staging/` (`--noindex`), `dist_prod/`;
- `prototype/minify_block.py` — минифицирует отдельный блок (вызывается из devflow).

## Где лежат исходники

- `prototype/block_*.html` — канонические HTML-фрагменты блоков;
- `prototype/page_*.html` — подстраницы (генерируются, руками не править);
- `prototype/blocks_min/` — минифицированные версии блоков;
- `prototype/seo_schema/` — JSON-LD сниппеты.

## Примечание

Если меняется один блок, нужно синхронизировать:

1. исходник `prototype/block_*.html`,
2. минифицированную версию,
3. `prototype/main_combined_v7.html`, если он используется как preview-сборка.
