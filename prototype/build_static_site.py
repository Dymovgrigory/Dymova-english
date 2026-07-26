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

DIR = os.path.dirname(os.path.abspath(__file__))
SITE = "https://dymova-english.ru"

# page_<slug>.html -> alias на сайте. Совпадает с алиасами в
# tilda_upload_subpages.py / tilda_bootstrap_articles.py.
PAGE_ALIASES = {
    "page_doshkolniki.html": "doshkolniki",
    "page_mladshie_shkolniki.html": "mladshie-shkolniki",
    "page_podrostki.html": "podrostki",
    "page_reading.html": "reading",
    "page_grammar.html": "grammar",
    "page_preparation.html": "preparation",
    "page_online_zanyatiya.html": "online-zanyatiya",
    "page_podderzhivayushchie_online.html": "podderzhivayushchie-online",
    "page_standartnye_offline.html": "standartnye-offline",
    "page_letnyaya_akademiya.html": "letnyaya-akademiya",
    "page_kontakty.html": "kontakty",
    "page_policy.html": "policy",
    "page_test_na_uroven.html": "test-na-uroven",
    "page_novosti.html": "novosti",
    "page_vakansii.html": "vakansii",
    "page_oge_anglijskij.html": "oge-anglijskij",
    "page_ege_anglijskij.html": "ege-anglijskij",
    "page_anglijskij_dlya_vzroslyh.html": "anglijskij-dlya-vzroslyh",
    "page_nemeckij_yazyk.html": "nemeckij-yazyk",
    "page_kitajskij_yazyk.html": "kitajskij-yazyk",
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
}

# Статьи уже несут собственную Article+BreadcrumbList JSON-LD внутри себя
# (article_jsonld() в build_subpages.py) — им из seo_schema/ ничего не
# добавляем, чтобы не задвоить разметку.
ARTICLE_ALIASES = {a for a in PAGE_ALIASES.values() if a.startswith("novosti-")}

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
    "oge-anglijskij": ["breadcrumb_oge-anglijskij.html"],
    "ege-anglijskij": ["breadcrumb_ege-anglijskij.html"],
    "anglijskij-dlya-vzroslyh": ["breadcrumb_anglijskij-dlya-vzroslyh.html"],
    "nemeckij-yazyk": ["breadcrumb_nemeckij-yazyk.html"],
    "kitajskij-yazyk": ["breadcrumb_kitajskij-yazyk.html"],
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


def build_head(alias: str, title: str, description: str, canonical: str, noindex: bool, extra_schema: list[str]) -> str:
    robots = "noindex,nofollow" if noindex else "index,follow"
    parts = [
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{title}</title>",
        f'<meta name="description" content="{description}">',
        f'<link rel="canonical" href="{canonical}">',
        f'<meta name="robots" content="{robots}">',
        f'<meta property="og:title" content="{title}">',
        f'<meta property="og:description" content="{description}">',
        f'<meta property="og:url" content="{canonical}">',
        '<meta property="og:type" content="website">',
        '<meta property="og:locale" content="ru_RU">',
        read_schema("org_localbusiness.html"),
    ]
    for fname in extra_schema:
        parts.append(read_schema(fname))
    return "\n".join(parts)


def wrap_page(alias: str, content: str, shapka: str, footer: str, meta: dict, noindex: bool) -> str:
    title = meta.get("title") or f"{alias} — Фоксинбург"
    description = meta.get("description") or ""
    canonical = meta.get("canonical") or f"{SITE}/{alias}"
    extra_schema = INDEX_SCHEMA if alias == "index" else SCHEMA_MAP.get(alias, [])
    if alias in ARTICLE_ALIASES:
        extra_schema = []  # уже есть собственная Article+BreadcrumbList
    head = build_head(alias, title, description, canonical, noindex, extra_schema)
    body = content if alias == "index" else (shapka + "\n" + content + "\n" + footer)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="ru">\n<head>\n' + head + "\n</head>\n<body>\n" + body + "\n</body>\n</html>\n"
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
    written.append(("index", "/"))

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
        written.append((alias, f"/{alias}"))

    # sitemap.xml + robots.txt
    urlset = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for alias, path in written:
        loc = SITE + (path if path != "/" else "/")
        urlset.append(f"  <url><loc>{loc}</loc></url>")
    urlset.append("</urlset>")
    with open(os.path.join(out_dir, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write("\n".join(urlset) + "\n")

    if args.noindex:
        robots = "User-agent: *\nDisallow: /\n"
    else:
        robots = f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n"
    with open(os.path.join(out_dir, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(robots)

    print(f"\nСобрано страниц: {len(written)} -> {out_dir}")
    print(f"robots: {'NOINDEX (стейджинг)' if args.noindex else 'индексируемый (прод)'}")
    if missing_meta:
        print(f"!! нет title/description (ни в seo_meta_live.json, ни в <h1>/<p>): {missing_meta}")


if __name__ == "__main__":
    main()
