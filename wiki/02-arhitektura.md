# 02. Архитектура сайта

## Общая схема

Сайт собран из Tilda-блоков и служебных страниц-копий.

### Главная

Канонический набор блоков для `index-new` собирается через `prototype/tilda_upload_blocks.py`.

Канонический порядок блоков:

1. `tilda_header_unified_min.html`
2. `tilda_cta_enrollment_min.html`
3. `tilda_advantages_min.html`
4. `tilda_directions_min.html`
5. `tilda_onboarding_min.html`
6. `tilda_team_min.html`
7. `tilda_languages_min.html`
8. `tilda_photobank_gallery_min.html`
9. `tilda_pricing_enrollment_min.html`
10. `tilda_reviews_min.html`
11. `tilda_faq_min.html`
12. `tilda_svedeniya_min.html`
13. `tilda_contacts_map_min.html`
14. `tilda_footer_min.html`

### Подстраницы

Служебные копии и их `pageid`:

- `/reading` — `151292376` — `reading-new`
- `/grammar` — `151292406` — `grammar-new`
- `/preparation` — `151292476` — `preparation-new`

Скрипт: [`prototype/tilda_upload_copies.py`](../prototype/tilda_upload_copies.py).

### Логика модалки заявки

- открытие заявки завязано на `data-fxb-zayavka`;
- обработчик в футере открывает модалку на уровне `document`;
- кнопка/ссылка в onboarding не должна глушить клики по `<a>`.

### Сборка

- `prototype/minify_block.py` — минифицирует отдельный блок в `prototype/tilda_blocks_min/`;
- `prototype/tilda_upload_blocks.py` — заливает блоки главной в правильном порядке;
- `prototype/tilda_upload_copies.py` — заливает копии подстраниц;
- `prototype/tilda_publish_pages.py` — публикует указанные `pageid`;
- `prototype/tilda_reorder.py` — переставляет блоки главной;
- `prototype/tilda_relink_index.py` — перепривязывает старые ссылки главной к новым копиям;
- `prototype/tilda_deploy_forms.py` — выкатывает обновления формы/модалки на главную;
- `prototype/tilda_update_*.py` — точечные обновления отдельных блоков.

## Где лежат исходники

- `prototype/tilda_*.html` — канонические HTML-фрагменты блоков;
- `prototype/page_*.html` — подстраницы;
- `prototype/tilda_blocks_min/` — минифицированные версии для загрузки в Tilda;
- `prototype/seo_schema/` — JSON-LD сниппеты.

## Примечание

Если меняется один блок, нужно синхронизировать:

1. исходник `prototype/tilda_*.html`,
2. минифицированную версию,
3. `prototype/main_combined_v7.html`, если он используется как preview-сборка.
