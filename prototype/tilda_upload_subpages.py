#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Загрузка/обновление доп. страниц Фоксинбург в едином фирменном стиле.

Для каждой страницы обеспечиваем 3 блока «HTML-код» (T123) в порядке:
    1) fxb-shapka  — общая шапка/меню (tilda_shapka.html)
    2) fxb-page / fxb-contacts — контент страницы (page_*.html)
    3) fxb-footer  — общий подвал (tilda_footer.html)

Роли существующих блоков определяем по ОПУБЛИКОВАННОМУ HTML страницы
(надёжно, т.к. редактор не рендерит код T123 инлайн). Скрипт идемпотентен:
после первой публикации шапка/подвал распознаются и не дублируются.

Мутации (создание блоков, запись кода, сортировка) идут через /page/submit/
из контекста открытого редактора (нужны cookie + window.pageid).

Публикация — отдельно, кнопкой «Опубликовать все» в кабинете проекта
(API публикации в Tilda не работает).

Запуск:  python3 tilda_upload_subpages.py
Требуется: открытый авторизованный Chrome с CDP на :29229.
"""
import asyncio, json, os, re, urllib.request
from playwright.async_api import async_playwright

DIR = os.path.dirname(os.path.abspath(__file__))
PROJECTID = "2053071"
CDP = "http://localhost:29229"
SITE = "https://dymova-english.ru"

# (pageid, файл контента, alias на сайте)
PAGES = [
    ("151228606", "page_doshkolniki.html", "doshkolniki"),
    ("151228676", "page_mladshie_shkolniki.html", "mladshie-shkolniki"),
    ("151228746", "page_podrostki.html", "podrostki"),
    ("151229566", "page_letnyaya_akademiya.html", "letnyaya-akademiya"),
    ("151229606", "page_online_zanyatiya.html", "online-zanyatiya"),
    ("151229676", "page_podderzhivayushchie_online.html", "podderzhivayushchie-online"),
    ("151229756", "page_standartnye_offline.html", "standartnye-offline"),
    ("151228006", "page_kontakty.html", "kontakty"),
    ("152445956", "page_oge_anglijskij.html", "oge-anglijskij"),
    ("152446216", "page_ege_anglijskij.html", "ege-anglijskij"),
    ("152446236", "page_anglijskij_dlya_vzroslyh.html", "anglijskij-dlya-vzroslyh"),
    ("152446286", "page_nemeckij_yazyk.html", "nemeckij-yazyk"),
    ("152446296", "page_kitajskij_yazyk.html", "kitajskij-yazyk"),
]

CONTENT_MARKERS = ['id="fxb-page"', 'id="fxb-age-page"', 'id="fxb-summer-page"', 'id="fxb-contacts"']


def read(fname):
    with open(os.path.join(DIR, fname), "r", encoding="utf-8") as f:
        return f.read()


def fetch(url):
    import time
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru,en;q=0.9",
    }
    last = None
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            last = e
            time.sleep(2 + attempt * 2)
    raise last


def detect_roles(html):
    """По опубликованному HTML вернуть {shapka, content, footer, order:[recids...]}."""
    rec_iter = [(m.start(), m.group(1)) for m in re.finditer(r'id="rec(\d+)"', html)]
    order = []
    for _, rid in rec_iter:
        if rid not in order:
            order.append(rid)

    def rec_before(pos):
        cur = None
        for p, rid in rec_iter:
            if p <= pos:
                cur = rid
            else:
                break
        return cur

    def find_rec(marker):
        i = html.find(marker)
        return rec_before(i) if i > -1 else None

    shapka = find_rec('id="fxb-shapka"')
    footer = find_rec('id="fxb-footer"')
    content = None
    for mk in CONTENT_MARKERS:
        content = find_rec(mk)
        if content:
            break
    return {"shapka": shapka, "content": content, "footer": footer, "order": order}


async def api(page, fields):
    return await page.evaluate("""(fields) => new Promise((resolve) => {
        var fd = new FormData();
        for (var k in fields) fd.append(k, fields[k]);
        fetch('/page/submit/', {method:'POST', body:fd, credentials:'same-origin'})
          .then(r => r.text()).then(t => resolve(t)).catch(e => resolve('ERR:'+e.message));
    })""", fields)


async def add_t123(page, afterid):
    pageid = await page.evaluate("window.pageid")
    txt = await api(page, {"comm": "addnewrecord", "pageid": pageid,
                           "afterid": afterid or "", "tplid": "131"})
    try:
        data = json.loads(txt)
        html = data.get("html", txt)
    except Exception:
        html = txt
    m = re.search(r'recordid="?(\d+)"?', html) or re.search(r'rec(\d+)', html)
    return m.group(1) if m else None


async def save_code(page, recordid, code):
    pageid = await page.evaluate("window.pageid")
    txt = await api(page, {"comm": "saverecord", "pageid": pageid, "recordid": recordid,
                           "onlythisfield": "code", "code": code})
    return txt.strip()


async def sort_records(page, order):
    pageid = await page.evaluate("window.pageid")
    fields = {"comm": "saverecordssort", "pageid": pageid}
    for i, rid in enumerate(order):
        fields["sorts[%d]" % i] = rid
    return await api(page, fields)


async def process_page(page, pageid, content_file, alias, shapka, footer):
    print("\n==================== %s (pageid %s) ====================" % (alias, pageid))
    try:
        html = fetch("%s/%s" % (SITE, alias))
    except Exception as e:
        print("  !! не удалось получить опубликованный HTML:", e)
        html = ""
    roles = detect_roles(html)
    print("  published roles:", {k: roles[k] for k in ("shapka", "content", "footer")},
          "| records:", len(roles["order"]))

    await page.goto("https://tilda.ru/page/?pageid=%s&projectid=%s&edit=y" % (pageid, PROJECTID),
                    wait_until="load", timeout=90000)
    await asyncio.sleep(3.5)
    wp = await page.evaluate("window.pageid")
    if str(wp) != str(pageid):
        print("  !! window.pageid (%s) != ожидаемого (%s), пропускаю" % (wp, pageid))
        return None

    sh, content, ft = roles["shapka"], roles["content"], roles["footer"]
    if not content:
        print("  !! контент-блок не найден в опубликованном HTML, пропускаю")
        return None

    if not sh:
        sh = await add_t123(page, content)
        print("  создан блок шапки rec", sh)
        await asyncio.sleep(1)
    if not ft:
        ft = await add_t123(page, content)
        print("  создан блок подвала rec", ft)
        await asyncio.sleep(1)
    if not sh or not ft:
        print("  !! не удалось создать блоки (sh=%s ft=%s), пропускаю" % (sh, ft))
        return None

    content_code = read(content_file)
    for rid, code, name in [(sh, shapka, "shapka"), (content, content_code, "content"), (ft, footer, "footer")]:
        r = await save_code(page, rid, code)
        ok = "OK" if r == "OK" else r[:50]
        print("  save %-7s rec%s (%d chars) -> %s" % (name, rid, len(code), ok))
        await asyncio.sleep(0.6)

    allrecs = list(roles["order"])
    for x in (sh, content, ft):
        if x not in allrecs:
            allrecs.append(x)
    rest = [r for r in allrecs if r not in (sh, content, ft)]
    order = [sh, content, ft] + rest
    res = await sort_records(page, order)
    print("  sort %s -> %s" % (order, res[:30]))
    return {"pageid": pageid, "alias": alias, "shapka": sh, "content": content, "footer": ft}


async def main():
    shapka = read("tilda_shapka.html")
    footer = read("tilda_footer.html")
    print("shapka %d chars, footer %d chars" % (len(shapka), len(footer)))
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP)
        page = browser.contexts[0].pages[0]
        for pageid, cfile, alias in PAGES:
            try:
                r = await process_page(page, pageid, cfile, alias, shapka, footer)
                results.append(r)
            except Exception as e:
                print("  ERROR on", alias, ":", repr(e))
    print("\n===== ИТОГ =====")
    for r in results:
        print(r)
    print("\nДалее: кабинет проекта -> «Опубликовать все».")


if __name__ == "__main__":
    asyncio.run(main())
