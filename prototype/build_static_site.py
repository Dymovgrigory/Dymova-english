#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сборка полноценного статического сайта из фрагментов, которые раньше
вставлялись вручную в T123-блоки Tilda.

Берёт:
  - tilda_shapka.html / tilda_footer.html — общая шапка/подвал;
  - page_*.html — контент каждой страницы (вывод build_subpages.py /
    build_course_pages.py, уже актуален после `make build`);
  - main_combined_v7.html — отдельно собранная главная (уже содержит
    шапку и подвал сама, не оборачивается);
  - seo_meta_live.json — title/description/canonical, снятые с реально
    опубликованных страниц Tilda (не выдуманы, см. DEVLOG);
  - seo_schema/ — sitewide LocalBusiness + по-страничные Course/FAQ/
    BreadcrumbList JSON-LD (карта — seo_schema/DEPLOY_MAP.md).

Каждая страница оборачивается в полный HTML5-документ и раскладывается
как dist/<alias>/index.html (чистые URL без .html, под nginx с
`try_files $uri $uri/ index.html`). Плюс sitemap.xml и robots.txt.

Запуск:
  python3 build_static_site.py            # прод-сборка (индексируемая)
  python3 build_static_site.py --noindex  # стейджинг: noindex,nofollow везде
  python3 build_static_site.py --out dist_staging --noindex
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from datetime import datetime

DIR = os.path.dirname(os.path.abspath(__file__))
SITE = "https://dymova-english.ru"

# page_<slug>.html -> alias на сайте. Совпадает с алиасами в
# tilda_upload_subpages.py / tilda_bootstrap_articles.py.
PAGE_ALIASES = {
    "page_doshkolniki.html": "doshkolniki",
    "page_tseny.html": "tseny",
    "page_mladshie_shkolniki.html": "mladshie-shkolniki",
    "page_podrostki.html": "podrostki",
    "page_reading.html": "reading",
    "page_grammar.html": "grammar",
    "page_preparation.html": "preparation",
    "page_geo_mytishchi.html": "geo/mytishchi",
    "page_online_zanyatiya.html": "online-zanyatiya",
    "page_podderzhivayushchie_online.html": "podderzhivayushchie-online",
    "page_standartnye_offline.html": "standartnye-offline",
    "page_letnyaya_akademiya.html": "letnyaya-akademiya",
    "page_kontakty.html": "kontakty",
    "page_policy.html": "policy",
    "page_novosti.html": "novosti",
    "page_vakansii.html": "vakansii",
    "page_oge_anglijskij.html": "oge-anglijskij",
    "page_ege_anglijskij.html": "ege-anglijskij",
    "page_anglijskij_dlya_vzroslyh.html": "anglijskij-dlya-vzroslyh",
    "page_nemeckij_yazyk.html": "nemeckij-yazyk",
    "page_kitajskij_yazyk.html": "kitajskij-yazyk",
    "page_ispanskij_yazyk.html": "ispanskij-yazyk",
    "page_repetitor.html": "repetitor",
    "page_repetitor_nachalnaya_shkola.html": "repetitor-nachalnaya-shkola",
    "page_novosti_so_skolki_let_uchit_anglijskij.html": "novosti-so-skolki-let-uchit-anglijskij",
    "page_novosti_kak_podgotovitsya_k_oge_anglijskij.html": "novosti-kak-podgotovitsya-k-oge-anglijskij",
    "page_novosti_kak_prohodyat_smeny_letnej_akademii.html": "novosti-kak-prohodyat-smeny-letnej-akademii",
    "page_novosti_vtoroj_inostrannyj_yazyk_nemeckij_ili_kitajskij.html": "novosti-vtoroj-inostrannyj-yazyk-nemeckij-ili-kitajskij",
    "page_novosti_anglijskij_letom_kak_ne_poteryat_navyk.html": "novosti-anglijskij-letom-kak-ne-poteryat-navyk",
    "page_novosti_kak_ponyat_uroven_rebenka_pered_uchebnym_godom.html": "novosti-kak-ponyat-uroven-rebenka-pered-uchebnym-godom",
    "page_novosti_zapis_na_novyj_uchebnyj_god_anglijskij_nemeckij_kitajskij.html": "novosti-zapis-na-novyj-uchebnyj-god-anglijskij-nemeckij-kitajskij",
    "page_novosti_yazykovaya_shkola_ili_repetitor_kak_vybrat.html": "novosti-yazykovaya-shkola-ili-repetitor-kak-vybrat",
    "page_novosti_anglijskij_dlya_vzroslyh_s_nulya_s_chego_nachat.html": "novosti-anglijskij-dlya-vzroslyh-s-nulya-s-chego-nachat",
    "page_novosti_lozhnye_druzya_perevodchika_slova_kotorye_obmanyvayut.html": "novosti-lozhnye-druzya-perevodchika-slova-kotorye-obmanyvayut",
    "page_novosti_komu_nuzhen_repetitor_po_anglijskomu_5_priznakov.html": "novosti-komu-nuzhen-repetitor-po-anglijskomu-5-priznakov",
    "page_novosti_otkryt_nabor_na_novyj_uchebnyj_god_2026.html": "novosti-otkryt-nabor-na-novyj-uchebnyj-god-2026",
    "page_novosti_kak_vybrat_programmu_anglijskogo_dlya_rebenka.html": "novosti-kak-vybrat-programmu-anglijskogo-dlya-rebenka",
    "page_novosti_podgotovka_k_novomu_uchebnomu_godu_anglijskij.html": "novosti-podgotovka-k-novomu-uchebnomu-godu-anglijskij",
    "page_novosti_start_novogo_uchebnogo_goda_2026.html": "novosti-start-novogo-uchebnogo-goda-2026",
    "page_vpr_anglijskij.html": "vpr-anglijskij",
    "page_razgovornyj_anglijskij.html": "razgovornyj-anglijskij",
    "page_meropriyatiya.html": "meropriyatiya",
    "page_zhizn_shkoly.html": "zhizn-shkoly",
    "page_vypusknoj_2026.html": "vypusknoj-2026",
    "page_ekskursii.html": "ekskursii",
    "page_prazdniki.html": "prazdniki",
    "page_vesennyaya_akademiya_2026.html": "vesennyaya-akademiya-2026",
    "page_nositel_yazyka.html": "nositel-yazyka",
    "page_otzyvy.html": "otzyvy",
    "page_about.html": "about",
    "page_test_uroven.html": "test-uroven",
    "page_test_gotov_k_shkole.html": "test-gotov-k-shkole",
    "page_test_format.html": "test-format",
    "page_english_words.html": "english-words",
    "page_english_words_zhivotnye.html": "english-words/zhivotnye",
    "page_english_words_eda.html": "english-words/eda",
    "page_english_words_shkola.html": "english-words/shkola",
    "page_english_words_semya.html": "english-words/semya",
    "page_english_words_tsveta.html": "english-words/tsveta",
    "page_blog.html": "blog",
    "page_blog_anglijskij_dlya_detej_3_4_goda.html": "blog-anglijskij-dlya-detej-3-4-goda",
    "page_blog_kak_nauchit_rebenka_chitat_po_anglijski.html": "blog-kak-nauchit-rebenka-chitat-po-anglijski",
    "page_blog_rebenok_ne_ponimaet_anglijskij_v_shkole.html": "blog-rebenok-ne-ponimaet-anglijskij-v-shkole",
    "page_blog_vpr_po_anglijskomu_4_klass.html": "blog-vpr-po-anglijskomu-4-klass",
    "page_blog_razgovornyj_barjer_u_podrostka.html": "blog-razgovornyj-barjer-u-podrostka",
    "page_blog_struktura_oge_po_anglijskomu.html": "blog-struktura-oge-po-anglijskomu",
    "page_blog_gotov_li_rebenok_k_shkole.html": "blog-gotov-li-rebenok-k-shkole",
    "page_blog_onlajn_ili_oflajn_anglijskij.html": "blog-onlajn-ili-oflajn-anglijskij",
    "page_blog_kitajskij_dlya_detej.html": "blog-kitajskij-dlya-detej",
    "page_blog_repetitor_ili_gruppa.html": "blog-repetitor-ili-gruppa",
    "page_blog_kak_vyuchit_anglijskie_slova_bystro.html": "blog-kak-vyuchit-anglijskie-slova-bystro",
    "page_blog_present_simple_dlya_roditelej.html": "blog-present-simple-dlya-roditelej",
    "page_blog_anglijskij_v_5_klasse_chto_zhdat.html": "blog-anglijskij-v-5-klasse-chto-zhdat",
    "page_blog_skolko_stoit_anglijskij_dlya_rebenka.html": "blog-skolko-stoit-anglijskij-dlya-rebenka",
    "page_blog_chtenie_na_anglijskom_s_chego_nachat.html": "blog-chtenie-na-anglijskom-s-chego-nachat",
    "page_blog_kak_vybrat_posobie_po_anglijskomu.html": "blog-kak-vybrat-posobie-po-anglijskomu",
    "page_blog_letnij_intensiv_itogi_i_plany.html": "blog-letnij-intensiv-itogi-i-plany",
    "page_blog_vesennyaya_akademiya_2026_kak_eto_bylo.html": "blog-vesennyaya-akademiya-2026-kak-eto-bylo",
    "page_blog_ekskursii_yu_klinika_pozharnaya_stanciya.html": "blog-ekskursii-yu-klinika-pozharnaya-stanciya",
    "page_blog_halloween_v_foxinburge_kak_eto_bylo.html": "blog-halloween-v-foxinburge-kak-eto-bylo",
    "page_blog_novyj_god_2026_v_foxinburge.html": "blog-novyj-god-2026-v-foxinburge",
    "page_blog_probely_po_anglijskomu.html": "blog-probely-po-anglijskomu",
    "page_blog_oshibki_v_anglijskom_top_15.html": "blog-oshibki-v-anglijskom-top-15",
    "page_blog_audirovanie_kak_nauchitsya_ponimat.html": "blog-audirovanie-kak-nauchitsya-ponimat",
    "page_blog_anglijskij_pered_1_sentyabrya.html": "blog-anglijskij-pered-1-sentyabrya",
    "page_blog_kruzhok_anglijskogo_dlya_doshkolnika.html": "blog-kruzhok-anglijskogo-dlya-doshkolnika",
    "page_blog_anglijskij_letom_progress.html": "blog-anglijskij-letom-progress",
    "page_blog_present_perfect_prostymi_slovami.html": "blog-present-perfect-prostymi-slovami",
    "page_blog_multfilmy_na_anglijskom_po_vozrastam.html": "blog-multfilmy-na-anglijskom-po-vozrastam",
    "page_blog_pesni_na_anglijskom_dlya_detej.html": "blog-pesni-na-anglijskom-dlya-detej",
    "page_blog_domashka_po_anglijskomu_roditel_bez_yazyka.html": "blog-domashka-po-anglijskomu-roditel-bez-yazyka",
    "page_blog_shkola_ili_repetitor_otlichiya.html": "blog-shkola-ili-repetitor-otlichiya",
    "page_blog_anglijskij_dlya_postupleniya_v_gimnaziyu.html": "blog-anglijskij-dlya-postupleniya-v-gimnaziyu",
    "page_blog_kogda_nachinat_gotovitsya_k_oge.html": "blog-kogda-nachinat-gotovitsya-k-oge",
    "page_blog_halloween_rozhdestvo_foxinburg.html": "blog-halloween-rozhdestvo-foxinburg",
}

# Статьи уже несут собственную Article+BreadcrumbList JSON-LD внутри себя
# (article_jsonld() в build_subpages.py) — им из seo_schema/ ничего не
# добавляем, чтобы не задвоить разметку.
ARTICLE_ALIASES = {a for a in PAGE_ALIASES.values() if a.startswith(("novosti-", "blog-"))}

# alias -> список файлов seo_schema/ (кроме sitewide org_localbusiness.html,
# который идёт на каждую страницу). Взято из seo_schema/DEPLOY_MAP.md.
SCHEMA_MAP = {
    "reading": ["course_reading.html", "breadcrumb_reading.html"],
    "grammar": ["course_grammar.html", "breadcrumb_grammar.html"],
    "preparation": ["course_preparation.html", "breadcrumb_preparation.html"],
    "letnyaya-akademiya": ["course_letnyaya-akademiya.html", "breadcrumb_letnyaya-akademiya.html"],
    "kontakty": ["breadcrumb_kontakty.html"],
    "doshkolniki": ["breadcrumb_doshkolniki.html"],
    "mladshie-shkolniki": ["breadcrumb_mladshie-shkolniki.html"],
    "podrostki": ["breadcrumb_podrostki.html"],
    "online-zanyatiya": ["breadcrumb_online-zanyatiya.html"],
    "podderzhivayushchie-online": ["breadcrumb_podderzhivayushchie-online.html"],
    "standartnye-offline": ["breadcrumb_standartnye-offline.html"],
    "novosti": ["breadcrumb_novosti.html"],
    "vakansii": ["breadcrumb_vakansii.html"],
    "oge-anglijskij": ["course_oge-anglijskij.html", "breadcrumb_oge-anglijskij.html"],
    "ege-anglijskij": ["course_ege-anglijskij.html", "breadcrumb_ege-anglijskij.html"],
    "anglijskij-dlya-vzroslyh": ["course_anglijskij-dlya-vzroslyh.html", "breadcrumb_anglijskij-dlya-vzroslyh.html"],
    "nemeckij-yazyk": ["course_nemeckij-yazyk.html", "breadcrumb_nemeckij-yazyk.html"],
    "kitajskij-yazyk": ["course_kitajskij-yazyk.html", "breadcrumb_kitajskij-yazyk.html"],
    "ispanskij-yazyk": ["course_ispanskij-yazyk.html", "breadcrumb_ispanskij-yazyk.html"],
    "repetitor": ["course_repetitor.html", "breadcrumb_repetitor.html"],
    "repetitor-nachalnaya-shkola": ["course_repetitor-nachalnaya-shkola.html", "breadcrumb_repetitor-nachalnaya-shkola.html"],
    "tseny": ["breadcrumb_tseny.html"],
    # vpr-anglijskij / razgovornyj-anglijskij / otzyvy / about несут
    # Course/WebPage + BreadcrumbList инлайн в контенте (extra_jsonld в
    # build_subpages.py) — файлы seo_schema/ в той сессии не создавались,
    # поэтому здесь записей нет.
}
INDEX_SCHEMA = ["faq.html"]

# Новые статьи этой сессии не были на живой Tilda -> нет записи в
# seo_meta_live.json. Title/description для них уже заданы в самом
# генераторе (NEWS_POST_*["title"/"description"]) — здесь не дублируем
# вручную, а достаём прямо из HTML (<h1>/шапка статьи), см. extract_article_meta().
NEWS_ALIAS_TITLES_FALLBACK = True


def read(fname: str) -> str:
    with open(os.path.join(DIR, fname), "r", encoding="utf-8") as f:
        return f.read()


def read_schema(fname: str) -> str:
    with open(os.path.join(DIR, "seo_schema", fname), "r", encoding="utf-8") as f:
        return f.read()


def crumbs_nav_html(items: list) -> str:
    """Видимые хлебные крошки с микроразметкой Schema.org (сессия 62).
    items: [(name, url|None), ...] — последний пункт без ссылки."""
    lis = []
    for i, (name, url) in enumerate(items):
        pos = f'<meta itemprop="position" content="{i + 1}">'
        if url:
            inner = (f'<a itemprop="item" href="{url}">'
                     f'<span itemprop="name">{name}</span></a>' + pos)
        else:
            inner = f'<span itemprop="name">{name}</span>' + pos
        lis.append('<li itemprop="itemListElement" itemscope '
                   'itemtype="https://schema.org/ListItem">' + inner + '</li>')
    return ('<nav class="fxb-breadcrumbs" aria-label="Хлебные крошки">'
            '<ol itemscope itemtype="https://schema.org/BreadcrumbList">'
            + "".join(lis) + '</ol></nav>')


def crumbs_from_schema_files(fnames: list) -> list | None:
    """Достаёт пункты BreadcrumbList из seo_schema/breadcrumb_*.html."""
    for fname in fnames:
        if "breadcrumb" not in fname:
            continue
        m = re.search(r"<script[^>]*>(.*?)</script>", read_schema(fname), re.S)
        if not m:
            continue
        try:
            d = json.loads(m.group(1))
        except ValueError:
            continue
        if d.get("@type") == "BreadcrumbList":
            items = [(el.get("name", ""), el.get("item"))
                     for el in d.get("itemListElement", [])]
            if items:
                items[-1] = (items[-1][0], None)
            return items
    return None


# Self-hosted Montserrat (сессия 47): вместо блокирующих <link> на
# fonts.googleapis.com во всех шаблонах — @font-face инлайном в <head>
# каждой страницы. Файлы — variable font (кириллица 21 КБ, латиница 35 КБ)
# в assets/fonts/, копируются в dist вместе с assets/.
FONT_FACE_STYLE = "<style>" + read("assets/fonts/montserrat.css") + "</style>"


def extract_article_meta(html: str) -> tuple[str | None, str | None]:
    """Для новых статей без записи в seo_meta_live.json: title из <h1>,
    description — из уже встроенного в страницу Article JSON-LD (та же
    строка, что задана в NEWS_POST_*["description"] в build_subpages.py),
    а не угадывается по первому абзацу тела."""
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    title = re.sub(r"<[^>]+>", "", h1.group(1)).strip() if h1 else None
    desc_m = re.search(r'"description":\s*"((?:[^"\\]|\\.)*)"', html)
    desc = json.loads(f'"{desc_m.group(1)}"') if desc_m else None
    return title, desc


def build_head(alias: str, title: str, description: str, canonical: str, noindex: bool, extra_schema: list[str], og_type: str = "website") -> str:
    robots = "noindex,nofollow" if noindex else "index,follow"
    og_image = f"{SITE}/assets/og-cover.png"
    parts = [
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        PRELOADER_HEAD,
        FONT_FACE_STYLE,
        '<link rel="preload" href="/assets/fonts/montserrat-cyrillic.woff2" as="font" type="font/woff2" crossorigin>',
        '<link rel="preload" href="/assets/fonts/montserrat-latin.woff2" as="font" type="font/woff2" crossorigin>',
        # ранние соединения к нашим поддоменам: LMS CMS API и чат-бот (сессия 61)
        '<link rel="preconnect" href="https://lms.dymova-english.ru" crossorigin>',
        '<link rel="dns-prefetch" href="https://lms.dymova-english.ru">',
        '<link rel="preconnect" href="https://bot.dymova-english.ru" crossorigin>',
        '<link rel="dns-prefetch" href="https://bot.dymova-english.ru">',
        '<link rel="icon" type="image/png" href="/favicon.png">',
        f"<title>{title}</title>",
        f'<meta name="description" content="{description}">',
        f'<link rel="canonical" href="{canonical}">',
        f'<meta name="robots" content="{robots}">',
        # подтверждение владения сайтом для Яндекс.Вебмастера (сессия 47)
        '<meta name="yandex-verification" content="c08742055e803bc5">',
        # подтверждение владения для Google Search Console (сессия 59)
        '<meta name="google-site-verification" content="ZvzgMgWANwISH6Ke2ApOXh6a-KjCxK-RQPrmjerGoOs">',
        f'<meta property="og:title" content="{title}">',
        f'<meta property="og:description" content="{description}">',
        f'<meta property="og:url" content="{canonical}">',
        f'<meta property="og:type" content="{og_type}">',
        '<meta property="og:locale" content="ru_RU">',
        '<meta property="og:site_name" content="Языковая школа Фоксинбург">',
        f'<meta property="og:image" content="{og_image}">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:image" content="{og_image}">',
        read_schema("org_localbusiness.html"),
    ]
    for fname in extra_schema:
        parts.append(read_schema(fname))
    return "\n".join(parts)


# WOW-эффекты (prototype/wow/) — scroll-reveal, магнитные кнопки, tilt,
# параллакс — подключаются на всех страницах перед </body>.
# 3D-маскот Фокси (prototype/mascot/): ригнутая модель с 17 клипами
# (сессия 41) — ходит по нижней кромке, реагирует на скорость скролла,
# курсор и CTA. three.js и GLB грузятся ПОСЛЕ load + requestIdleCallback.
# (сессия 52: снимали по недоразумению — владелец вернул: «он не мешает».)
# ВАЖНО: importmap обязан идти раньше первого <script type="module"> —
# поэтому он вынесен в PRELOADER_BODY (самое начало <body>).
# Чат-виджет Фокси (бот, POST /api/chat) — на всех страницах, правый нижний угол.
# Cookie-согласие (wow/foxi-consent.js) — баннер с localStorage + событие
# 'fxb-consent' для будущего гейтинга аналитики (сессия 46).
WOW_SNIPPET = (
    '<link rel="stylesheet" href="/wow/foxi-wow.css">\n'
    '<link rel="stylesheet" href="/wow/foxi-consent.css">\n'
    '<script type="module" src="/wow/foxi-wow.js"></script>\n'
    "<script>window.FOXI_CONFIG={modelUrl:'/mascot/foxi-rigged.glb'};</script>\n"
    '<script type="module" src="/mascot/mascot.js"></script>\n'
    '<script src="https://bot.dymova-english.ru/widget/foxi.js" defer></script>\n'
    # Аналитика (Метрика 109945462 + GA4) — гейтится согласием fxb-consent;
    # должна идти РАНЬШЕ foxi-consent.js, чтобы успеть подписаться на событие
    # до announce() сохранённого выбора на DOMContentLoaded.
    '<script src="/wow/foxi-analytics.js" defer></script>\n'
    '<script src="/wow/foxi-consent.js" defer></script>'
)

# ATMOS (сессия 58): единая «кинематографичная» атмосфера внутренних страниц —
# те же WebGL-чернила в hero, след за указателем, cursor-glow, glass-карточки.
# Подключается ТОЛЬКО на внутренних страницах: у главной своя встроенная
# fluid-система, и она не меняется. Цвет glow — data-fxb-glow на #fxb-page.
ATMOS_SNIPPET = (
    '<link rel="stylesheet" href="/wow/foxi-atmos.css">\n'
    '<script src="/wow/foxi-atmos.js" defer></script>'
)


# Заставка-прелоадер (сессия 46, v2.1): РИГНУТЫЙ 3D-Фокси (/mascot/foxi-rigged.glb,
# клип Big_Wave_Hello) машет над полосой загрузки. Статичного webp-фолбэка НЕТ
# (запрос владельца: «только живой») — пока модель грузится, на градиенте
# просто текст и полоса; canvas плавно проявляется при готовности модели.
# Раскладка: крупная надпись «Языковая школа Фоксинбург» сверху, под ней
# маскот, ниже — полоса загрузки; фон — многослойный брендовый градиент
# с жёлтым/оранжевым свечением. Критический CSS инлайном в <head> первым,
# оверлей и скрипты — первыми в <body>: никакой белой вспышки. Прогресс —
# rAF до 90%, скрытие: window.load И (3D готов ИЛИ прошло 5 с), мин. показ
# 1.2 с, принудительно через 8 с; reduced-motion — без анимаций и ожидания 3D.
# Если GLB пришёл после скрытия заставки — 3D-сцену не стартуем (экономим CPU).
PRELOADER_HEAD = (
    "<style>"
    "#fxb-splash{position:fixed;inset:0;z-index:99999;display:grid;place-items:center;"
    "background:"
    "radial-gradient(120% 90% at 50% 26%,rgba(252,249,81,.13) 0%,rgba(252,249,81,0) 55%),"
    "radial-gradient(100% 80% at 82% 92%,rgba(238,115,73,.2) 0%,rgba(238,115,73,0) 60%),"
    "linear-gradient(135deg,#241a36 0%,#392852 42%,#662d92 78%,#7b4fc0 100%);"
    "transition:opacity .5s ease,visibility .5s}"
    "#fxb-splash::after{content:'';position:absolute;inset:0;pointer-events:none;"
    "background:radial-gradient(60% 45% at 50% 34%,rgba(252,249,81,.1) 0%,rgba(252,249,81,0) 70%);"
    "animation:fxbSplashGlow 3.2s ease-in-out infinite}"
    "@keyframes fxbSplashGlow{0%,100%{opacity:.5}50%{opacity:1}}"
    "#fxb-splash.fxb-splash-done{opacity:0;visibility:hidden;pointer-events:none}"
    ".fxb-splash-inner{position:relative;display:flex;flex-direction:column;align-items:center;gap:16px;padding:24px;text-align:center}"
    ".fxb-splash-brand{font-family:'Montserrat',system-ui,-apple-system,sans-serif;font-weight:700;"
    "font-size:clamp(24px,4.6vw,34px);letter-spacing:.03em;color:rgba(255,255,255,.95);"
    "text-shadow:0 2px 18px rgba(0,0,0,.35)}"
    ".fxb-splash-brand b{font-weight:800;color:#fcf951}"
    ".fxb-splash-stage{position:relative;width:220px;height:210px}"
    ".fxb-splash-3d{position:absolute;inset:0;width:220px;height:210px;opacity:0;transition:opacity .5s ease;"
    "filter:drop-shadow(0 14px 30px rgba(0,0,0,.35))}"
    ".fxb-splash-3d-on .fxb-splash-3d{opacity:1}"
    ".fxb-splash-bar{width:220px;height:7px;border-radius:99px;background:rgba(255,255,255,.16);overflow:hidden;"
    "box-shadow:0 2px 12px rgba(0,0,0,.25)}"
    ".fxb-splash-bar span{display:block;height:100%;width:0;border-radius:99px;"
    "background:linear-gradient(90deg,#fcf951,#c24712);transition:width .25s ease;"
    "animation:fxbSplashBar 1.9s ease-out forwards}"
    "@keyframes fxbSplashBar{0%{width:0}60%{width:55%}100%{width:88%}}"
    "@media (prefers-reduced-motion:reduce){"
    "#fxb-splash::after{animation:none}.fxb-splash-bar span{animation:none;width:60%}}"
    "</style>"
    # three.js вендорен локально (prototype/mascot/vendor, min-сборки) — без задержек на CDN;
    # modulepreload начинает качать модули сразу, fetch в <head> — GLB,
    # поэтому живой Фокси появляется практически сразу с началом загрузки
    # (дублирующий prefetch draco-wasm убран в сессии 52 — wasm грузит сам DRACOLoader)
    '<link rel="modulepreload" href="/mascot/vendor/three/build/three.module.min.js">'
    '<link rel="modulepreload" href="/mascot/vendor/three/build/three.core.min.js">'
    '<link rel="modulepreload" href="/mascot/vendor/three/examples/jsm/loaders/GLTFLoader.js">'
    '<link rel="modulepreload" href="/mascot/vendor/three/examples/jsm/loaders/DRACOLoader.js">'
    "<script>window.__fxbPre={"
    "glb:fetch('/mascot/foxi-splash.glb').then(function(r){return r.arrayBuffer();}).catch(function(){return null;})"
    "};</script>"
)

PRELOADER_BODY = (
    '<script type="importmap">{"imports":{'
    '"three":"/mascot/vendor/three/build/three.module.min.js",'
    '"three/addons/":"/mascot/vendor/three/examples/jsm/"'
    "}}</script>\n"
    '<div id="fxb-splash" aria-hidden="true">'
    '<div class="fxb-splash-inner">'
    '<div class="fxb-splash-brand">Языковая школа <b>Фоксинбург</b></div>'
    '<div class="fxb-splash-stage">'
    '<canvas class="fxb-splash-3d" width="220" height="210"></canvas>'
    "</div>"
    '<div class="fxb-splash-bar"><span></span></div>'
    "</div></div>\n"
    "<noscript><style>#fxb-splash{display:none}</style></noscript>\n"
    # прогресс и скрытие — обычный скрипт, работает даже при недоступном CDN
    "<script>(function(){var s=document.getElementById('fxb-splash');if(!s)return;"
    "var bar=s.querySelector('.fxb-splash-bar span'),t0=performance.now(),done=false,loaded=false;"
    "var rm=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;"
    "var MIN=rm?0:900,WAIT3D=rm?0:1500,MAX=3500;"
    "function pct(v){if(bar)bar.style.width=v+'%';}"
    "function tick(){if(done)return;var t=(performance.now()-t0)/1800;"
    "pct(Math.min(90,Math.round(t*90)));if(t<1)requestAnimationFrame(tick);}"
    "requestAnimationFrame(tick);"
    "function tryHide(){if(done||!loaded)return;"
    "if(!window.__fxb3dReady&&performance.now()-t0<WAIT3D)return;done=true;pct(100);"
    "var wait=Math.max(0,MIN-(performance.now()-t0));"
    "setTimeout(function(){s.classList.add('fxb-splash-done');"
    "setTimeout(function(){if(window.__fxbSplashStop)window.__fxbSplashStop();"
    "s.parentNode&&s.parentNode.removeChild(s);},600);},wait);}"
    "window.addEventListener('load',function(){loaded=true;tryHide();});"
    "document.addEventListener('fxb-splash-3d-ready',tryHide);"
    "setTimeout(function(){loaded=true;tryHide();},MAX);})();</script>\n"
    # ригнутый Фокси — модуль; GLB уже летит с <head> (__fxbPre.glb) — берём буфер
    # через loader.parse, а не ждём повторную загрузку; three.js локальный (vendor)
    "<script type=\"module\">"
    "try{"
    "const THREE=await import('three');"
    "const{GLTFLoader}=await import('three/addons/loaders/GLTFLoader.js');"
    "const{DRACOLoader}=await import('three/addons/loaders/DRACOLoader.js');"
    "const stage=document.querySelector('.fxb-splash-stage');"
    # сеть слишком медленная: заставка уже скрыта, пока качались модули — тихо выходим
    "if(!stage)throw new Error('splash-already-hidden');"
    "const canvas=stage.querySelector('.fxb-splash-3d');"
    "const renderer=new THREE.WebGLRenderer({canvas,alpha:true,antialias:true});"
    "renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));"
    "renderer.setSize(220,210,false);"
    "const scene=new THREE.Scene();"
    "const camera=new THREE.PerspectiveCamera(40,220/210,0.1,50);"
    "camera.position.set(0,1.0,3.2);camera.lookAt(0,0.85,0);"
    "scene.add(new THREE.HemisphereLight(0xffffff,0xd9c8ff,1.05));"
    "const dl=new THREE.DirectionalLight(0xffffff,1.4);dl.position.set(2,4,3);scene.add(dl);"
    "const draco=new DRACOLoader().setDecoderPath('/mascot/vendor/draco/');"
    "const loader=new GLTFLoader().setDRACOLoader(draco);"
    "const onReady=(gltf)=>{"
    "window.__fxb3dReady=true;"
    # заставка уже скрылась (медленная сеть) — сцену не стартуем, цикл не крутим
    "if(!document.getElementById('fxb-splash'))return;"
    "const model=gltf.scene;"
    "const box=new THREE.Box3().setFromObject(model);"
    "const c=box.getCenter(new THREE.Vector3());"
    "model.position.x-=c.x;model.position.z-=c.z;model.position.y-=box.min.y;"
    "const size=box.getSize(new THREE.Vector3());"
    "const body=new THREE.Group();body.add(model);"
    "body.scale.setScalar(1.7/Math.max(size.y,0.001));"
    "scene.add(body);"
    "const mixer=new THREE.AnimationMixer(model);"
    "const clips={};for(const cl of gltf.animations)clips[cl.name]=mixer.clipAction(cl);"
    "(clips['Big_Wave_Hello']||Object.values(clips)[0]).play();"
    "const clock=new THREE.Clock();"
    "renderer.setAnimationLoop(()=>{mixer.update(clock.getDelta());renderer.render(scene,camera);});"
    "window.__fxbSplashStop=()=>renderer.setAnimationLoop(null);"
    "stage.classList.add('fxb-splash-3d-on');"
    "document.dispatchEvent(new Event('fxb-splash-3d-ready'));"
    "};"
    "const pre=(window.__fxbPre&&window.__fxbPre.glb)||Promise.resolve(null);"
    "const onErr=(e)=>{try{window.__fxb3dError=[String((e&&e.message)||e),Object.prototype.toString.call(e),e&&e.type,e&&e.error].join('|');}catch(_){window.__fxb3dError='unserializable';}};"
    "pre.then((buf)=>{"
    "if(buf)loader.parse(buf,'/mascot/',onReady,onErr);"
    "else loader.load('/mascot/foxi-splash.glb',onReady,undefined,onErr);"
    "}).catch(onErr);"
    "}catch(e){window.__fxb3dError=String((e&&e.message)||e);}</script>"
)


def wrap_page(alias: str, content: str, shapka: str, footer: str, meta: dict, noindex: bool) -> str:
    title = meta.get("title") or f"{alias} — Фоксинбург"
    description = meta.get("description") or ""
    canonical = meta.get("canonical") or f"{SITE}/{alias}"
    extra_schema = INDEX_SCHEMA if alias == "index" else SCHEMA_MAP.get(alias, [])
    og_type = "website"
    if alias in ARTICLE_ALIASES:
        extra_schema = []  # уже есть собственная Article+BreadcrumbList
        og_type = "article"
    head = build_head(alias, title, description, canonical, noindex, extra_schema, og_type)
    # Видимые хлебные крошки для страниц, чей BreadcrumbList живёт в seo_schema/
    # (курсы из SCHEMA_MAP). У лендингов из build_subpages крошки уже в контенте.
    if alias != "index" and '<nav class="fxb-breadcrumbs"' not in content:
        crumbs = crumbs_from_schema_files(extra_schema)
        if crumbs and '<div class="fxb-hero-inner">' in content:
            content = content.replace(
                '<div class="fxb-hero-inner">',
                '<div class="fxb-hero-inner">' + crumbs_nav_html(crumbs), 1)
        elif crumbs and '<span class="fxb-eyebrow">' in content:
            # кастомные страницы без fxb-hero-inner (например, kontakty)
            content = content.replace(
                '<span class="fxb-eyebrow">',
                crumbs_nav_html(crumbs) + '<span class="fxb-eyebrow">', 1)
    body = content if alias == "index" else (shapka + "\n" + content + "\n" + footer)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="ru">\n<head>\n' + head + "\n</head>\n<body>\n"
        + PRELOADER_BODY + "\n" + body + "\n"
        + WOW_SNIPPET + "\n"
        + ("" if alias == "index" else ATMOS_SNIPPET + "\n")
        + "</body>\n</html>\n"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist")
    ap.add_argument("--noindex", action="store_true", help="Стейджинг: noindex,nofollow на всех страницах")
    args = ap.parse_args()

    out_dir = os.path.join(DIR, args.out)
    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(DIR, "seo_meta_live.json"), "r", encoding="utf-8") as f:
        seo_meta = json.load(f)

    shapka = read("tilda_shapka.html")
    footer = read("tilda_footer.html")

    written = []

    # Главная — отдельный случай, уже полностью собрана (шапка+блоки+подвал).
    index_content = read("main_combined_v7.html")
    index_meta = seo_meta.get("index", {})
    index_html = wrap_page("index", index_content, "", "", index_meta, args.noindex)
    index_path = os.path.join(out_dir, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_html)
    written.append(("index", "/", os.path.join(DIR, "main_combined_v7.html")))

    missing_meta = []
    for fname, alias in PAGE_ALIASES.items():
        src_path = os.path.join(DIR, fname)
        if not os.path.exists(src_path):
            print(f"!! пропускаю {fname}: файла нет (запусти `make build`)")
            continue
        content = read(fname)
        meta = dict(seo_meta.get(alias, {}))
        if not meta.get("title") or not meta.get("description"):
            t, d = extract_article_meta(content)
            meta.setdefault("title", t)
            meta.setdefault("description", d)
            if not meta.get("title") or not meta.get("description"):
                missing_meta.append(alias)
        meta.setdefault("canonical", f"{SITE}/{alias}")
        html = wrap_page(alias, content, shapka, footer, meta, args.noindex)
        page_dir = os.path.join(out_dir, alias)
        os.makedirs(page_dir, exist_ok=True)
        with open(os.path.join(page_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)
        written.append((alias, f"/{alias}", src_path))

    # sitemap.xml + robots.txt
    # <lastmod> — mtime исходного файла страницы (page_*.html / главная),
    # если он недоступен — дата сборки.
    build_date = datetime.now().date().isoformat()
    urlset = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for alias, path, src in written:
        loc = SITE + (path if path != "/" else "/")
        try:
            lastmod = datetime.fromtimestamp(os.path.getmtime(src)).date().isoformat()
        except OSError:
            lastmod = build_date
        urlset.append(f"  <url><loc>{loc}</loc><lastmod>{lastmod}</lastmod></url>")
    urlset.append("</urlset>")
    with open(os.path.join(out_dir, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write("\n".join(urlset) + "\n")

    if args.noindex:
        robots = "User-agent: *\nDisallow: /\n"
    else:
        robots = f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n"
    with open(os.path.join(out_dir, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(robots)

    # 404-страница (сессия 59, SEO P0): Caddy отдаёт её через handle_errors
    # при промахе try_files. Всегда noindex — статуса 404 достаточно, но
    # мета страхует от индексации при ошибках конфигурации. Не входит в
    # sitemap и в список written.
    not_found_content = (
        '<section class="fxb-section" style="text-align:center;padding:120px 20px 80px">'
        '<p class="fxb-eyebrow">Ошибка 404</p>'
        "<h1>Страница не найдена</h1>"
        '<p class="fxb-sub">Похоже, такой страницы нет или она переехала. '
        "Вот что может помочь:</p>"
        '<div class="fxb-card-grid" style="max-width:900px;margin:40px auto 0">'
        '<a class="fxb-card" href="/"><h3>Главная</h3>'
        "<p>Программы, цены и запись на бесплатную диагностику.</p></a>"
        '<a class="fxb-card" href="/doshkolniki"><h3>Английский для детей</h3>'
        "<p>Дошкольники, младшие школьники и подростки.</p></a>"
        '<a class="fxb-card" href="/tseny"><h3>Цены</h3>'
        "<p>Стоимость всех программ и форматов.</p></a>"
        '<a class="fxb-card" href="/kontakty"><h3>Контакты</h3>'
        "<p>Адреса филиалов, телефон и мессенджеры.</p></a>"
        "</div></section>"
    )
    not_found_html = wrap_page(
        "404", not_found_content, shapka, footer,
        {"title": "Страница не найдена — Фоксинбург",
         "description": "Такой страницы нет. Перейдите на главную, к программам или контактам школы Фоксинбург в Долгопрудном.",
         "canonical": f"{SITE}/404"},
        True,
    )
    with open(os.path.join(out_dir, "404.html"), "w", encoding="utf-8") as f:
        f.write(not_found_html)

    # WOW-ассеты (scroll-эффекты; foxi-3d.js лежит про запас, не подключается;
    # wow/foxi.glb — 1.2 МБ модель только для него — в прод НЕ уходит, сессия 59)
    wow_src = os.path.join(DIR, "wow")
    if os.path.isdir(wow_src):
        shutil.copytree(wow_src, os.path.join(out_dir, "wow"), dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("foxi.glb"))

    # 3D-маскот (mascot.js + ригнутый foxi-rigged.glb). Демо-страницы
    # (index.html, test-rigged.html), README и неиспользуемые модели
    # (foxi.glb ~1.2 МБ, foxi-rigged-v1-17clips.glb ~1.2 МБ — бэкапы,
    # сессия 59) в прод не уходят; файлы остаются в репозитории.
    mascot_src = os.path.join(DIR, "mascot")
    if os.path.isdir(mascot_src):
        shutil.copytree(mascot_src, os.path.join(out_dir, "mascot"), dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("*.html", "README.md",
                                                      "foxi.glb", "foxi-rigged-v1-17clips.glb"))

    # Общие ассеты сайта (og-cover.png, fonts/, brand/ и т.п.)
    assets_src = os.path.join(DIR, "assets")
    if os.path.isdir(assets_src):
        shutil.copytree(assets_src, os.path.join(out_dir, "assets"), dirs_exist_ok=True)

    # Локальные медиа (сессия 47): галерея, фото/видео команды, видео страниц.
    # В прод уходят только webp/mp4 — jpg/png-исходники остаются в репозитории.
    for media_dir in ("gallery", "team-media", "media"):
        src = os.path.join(DIR, media_dir)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(out_dir, media_dir), dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("*.jpg", "*.jpeg", "*.png", "*.opt.mp4", "*-src.mp4", "wow-src"))

    # favicon → корень сайта
    favicon_src = os.path.join(DIR, "favicon.png")
    if os.path.exists(favicon_src):
        shutil.copy(favicon_src, os.path.join(out_dir, "favicon.png"))

    # YML-фиды Яндекс.Вебмастера (сессия 59): feed_education.xml зарегистрирован
    # в Вебмастере по адресу /feed_education.xml — должен переживать деплой
    # (rsync --delete). Источник правды — seo_schema/ в репозитории.
    for feed in ("feed_education.xml", "feed_vacancies.xml"):
        feed_src = os.path.join(DIR, "seo_schema", feed)
        if os.path.exists(feed_src):
            shutil.copy(feed_src, os.path.join(out_dir, feed))

    print(f"\nСобрано страниц: {len(written)} -> {out_dir}")
    print(f"robots: {'NOINDEX (стейджинг)' if args.noindex else 'индексируемый (прод)'}")
    if missing_meta:
        print(f"!! нет title/description (ни в seo_meta_live.json, ни в <h1>/<p>): {missing_meta}")


if __name__ == "__main__":
    main()
