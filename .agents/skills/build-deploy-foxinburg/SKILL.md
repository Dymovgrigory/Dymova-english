---
name: build-deploy-foxinburg
description: Build and deploy Foxinburg (dymova-english.ru) landing pages. Use when editing prototype/build_subpages.py, adding sections/media to landing pages, or deploying/publishing pages to Tilda.
---

# Build & deploy Foxinburg landing pages

## Build
- Source of truth: `prototype/build_subpages.py`. A `PAGES` dict feeds `landing_page(p)`, which renders sections from optional keys: `advantages`, `team`/`teachers`, `formats`, `prices`, `ladder`, `video`, `books`, `faq`.
- Renderers/helpers: `card_grid_section`, `teacher_team_section` (photo+video teacher cards with a click-to-play `<video>` modal), `price_section`, `ladder_section`, `video_section`. CSS/JS constants (`TEAM_CSS`/`TEAM_JS`/`PRICE_CSS`/`VIDEO_CSS`/`LADDER_CSS`) are appended conditionally.
- Rebuild all pages: `python3 prototype/build_subpages.py` (regenerates `prototype/page_*.html`). Sanity: `python3 -m py_compile prototype/build_subpages.py`.

## Deploy to Tilda (scripts drive a CDP-connected Chrome — cheap, no manual GUI)
1. Upload changed pages: `python3 prototype/tilda_upload_subpages.py <alias> [<alias> ...]` — filters by page *alias*; overwrites shapka/content/footer blocks. The `PAGES` list inside maps `(pageid, htmlfile, alias)`.
2. Publish: `python3 prototype/tilda_publish_pages.py <pageid> [<pageid> ...]`.
3. Nav (header/footer/dropdown): `prototype/tilda_update_nav.py`. Team page: `tilda_team.html` + `tilda_update_team_*.py`.
4. Verify with `curl` (HTTP 200 + grep for expected content). Per project rule, do NOT screenshot/record/test on-site unless the user explicitly asks — the user verifies himself.

## Live pageids / aliases
doshkolniki 151228606 · mladshie-shkolniki 151228676 · podrostki 151228746 · letnyaya-akademiya 151229566 · online-zanyatiya 151229606 · podderzhivayushchie-online 151229676 · standartnye-offline 151229756 · kontakty 151228006 · oge-anglijskij 152445956 · ege-anglijskij 152446216 · anglijskij-dlya-vzroslyh 152446236 · nemeckij-yazyk 152446286 · kitajskij-yazyk 152446296 · novosti 151324806 (+3 article pages).
Note: `page_reading/grammar/preparation` build but are NOT published (no live URL, absent from deploy list).

## Media / CDN rule (critical)
Do NOT serve `.mp4` from `raw.githubusercontent.com` — it returns `application/octet-stream` + `nosniff`, so browsers won't play it (empty video modal). Use **jsDelivr**: `https://cdn.jsdelivr.net/gh/Dymovgrigory/Dymova-english@<ref>/<path>` (correct `video/mp4` + CORS). Large one-off videos are pushed to branch `gh-pages` under `media/` and served via `@gh-pages/media/FILENAME`. Teacher photos/videos live in `prototype/team-media/` and are referenced through the `TEAM_MEDIA` jsDelivr constant.

## Data
- Teachers: English — Дмитроченко Юлия, Птицын Владислав, Анохин Роман (no media yet → fox placeholder), Саляхова Алина; German — only Саляхова; Chinese — only Шевченко Дарья.
- Prices (everywhere except Летняя Академия): группа 9 000 ₽/мес (2×60 мин/нед), индивидуально 2 500 ₽/час, пробный 1 125 ₽; маткапитал + вычет 13%. Branches: Лихачевского 76к1 и Ракетостроителей 9к3 (Долгопрудный).
