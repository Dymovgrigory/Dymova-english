#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Обновляет ТОЛЬКО блоки шапки и подвала на существующих страницах
(в них добавлены ссылки на новые лендинги: ОГЭ, ЕГЭ, взрослые, немецкий,
китайский). Контент-блоки и порядок блоков НЕ трогаем.

Источники:
  - подстраницы: шапка = tilda_shapka.html (маркер id="fxb-shapka")
  - главная:     шапка = tilda_blocks_min/tilda_header_unified_min.html
                 (маркер id="fxb-hero")
  - подвал (все): подстраницы -> tilda_footer.html,
                  главная     -> tilda_blocks_min/tilda_footer_min.html
                  (маркер id="fxb-footer")

Роль блока определяем по ОПУБЛИКОВАННОМУ HTML (rec перед маркером) — редактор
не рендерит код T123 инлайн, поэтому это надёжно. Скрипт идемпотентен.

Мутации идут через /page/submit/ (comm=saverecord, onlythisfield=code) из
контекста открытого авторизованного редактора (нужны cookie + window.pageid).

Публикация — отдельно: python3 tilda_publish_pages.py <pageid...>.

Запуск:  python3 tilda_update_nav.py
Требуется: открытый авторизованный Chrome с CDP на :29229.
"""
import asyncio, os, re, time, urllib.request
from playwright.async_api import async_playwright

DIR = os.path.dirname(os.path.abspath(__file__))
PROJECTID = "2053071"
CDP = "http://localhost:29229"
SITE = "https://dymova-english.ru"

# (pageid, alias, header_marker, header_src, footer_src)
SHAPKA, FOOTER = "tilda_shapka.html", "tilda_footer.html"
HEAD_MIN = "tilda_blocks_min/tilda_header_unified_min.html"
FOOT_MIN = "tilda_blocks_min/tilda_footer_min.html"

PAGES = [
    ("151210576", "",                          'id="fxb-hero"',   HEAD_MIN, FOOT_MIN),  # главная
    ("151292376", "reading-new",               'id="fxb-shapka"', SHAPKA, FOOTER),
    ("151292406", "grammar-new",               'id="fxb-shapka"', SHAPKA, FOOTER),
    ("151292476", "preparation-new",           'id="fxb-shapka"', SHAPKA, FOOTER),
    ("151228606", "doshkolniki",               'id="fxb-shapka"', SHAPKA, FOOTER),
    ("151228676", "mladshie-shkolniki",        'id="fxb-shapka"', SHAPKA, FOOTER),
    ("151228746", "podrostki",                 'id="fxb-shapka"', SHAPKA, FOOTER),
    ("151229566", "letnyaya-akademiya",        'id="fxb-shapka"', SHAPKA, FOOTER),
    ("151229606", "online-zanyatiya",          'id="fxb-shapka"', SHAPKA, FOOTER),
    ("151229676", "podderzhivayushchie-online",'id="fxb-shapka"', SHAPKA, FOOTER),
    ("151229756", "standartnye-offline",       'id="fxb-shapka"', SHAPKA, FOOTER),
    ("151228006", "kontakty",                  'id="fxb-shapka"', SHAPKA, FOOTER),
    ("151324806", "novosti",                   'id="fxb-shapka"', SHAPKA, FOOTER),
    ("151324866", "vakansii",                  'id="fxb-shapka"', SHAPKA, FOOTER),
    ("152445956", "oge-anglijskij",            'id="fxb-shapka"', SHAPKA, FOOTER),
    ("152446216", "ege-anglijskij",            'id="fxb-shapka"', SHAPKA, FOOTER),
    ("152446236", "anglijskij-dlya-vzroslyh",  'id="fxb-shapka"', SHAPKA, FOOTER),
    ("152446286", "nemeckij-yazyk",            'id="fxb-shapka"', SHAPKA, FOOTER),
    ("152446296", "kitajskij-yazyk",           'id="fxb-shapka"', SHAPKA, FOOTER),
    ("152463826", "novosti-so-skolki-let-uchit-anglijskij", 'id="fxb-shapka"', SHAPKA, FOOTER),
    ("152464166", "novosti-kak-podgotovitsya-k-oge-anglijskij", 'id="fxb-shapka"', SHAPKA, FOOTER),
    ("152464306", "novosti-kak-prohodyat-smeny-letnej-akademii", 'id="fxb-shapka"', SHAPKA, FOOTER),
]


def read(fname):
    with open(os.path.join(DIR, fname), "r", encoding="utf-8") as f:
        return f.read()


def fetch(url):
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


def rec_before(html, marker):
    """recid блока, внутри которого встречается marker."""
    pos = html.find(marker)
    if pos < 0:
        return None
    cur = None
    for m in re.finditer(r'id="rec(\d+)"', html):
        if m.start() <= pos:
            cur = m.group(1)
        else:
            break
    return cur


async def api(page, fields):
    return await page.evaluate("""(fields) => new Promise((resolve) => {
        var fd = new FormData();
        for (var k in fields) fd.append(k, fields[k]);
        fetch('/page/submit/', {method:'POST', body:fd, credentials:'same-origin'})
          .then(r => r.text()).then(t => resolve(t)).catch(e => resolve('ERR:'+e.message));
    })""", fields)


async def save_code(page, pageid, recordid, code):
    txt = await api(page, {"comm": "saverecord", "pageid": pageid, "recordid": recordid,
                           "onlythisfield": "code", "code": code})
    return txt.strip()


async def process(page, pageid, alias, marker, header_src, footer_src):
    url = "%s/%s" % (SITE, alias) if alias else SITE + "/"
    print("\n==================== %s (pageid %s) ====================" % (alias or "/", pageid))
    try:
        html = fetch(url)
    except Exception as e:
        print("  !! не удалось получить HTML:", e)
        return None
    head_rec = rec_before(html, marker)
    foot_rec = rec_before(html, 'id="fxb-footer"')
    print("  header rec:", head_rec, "| footer rec:", foot_rec)
    if not head_rec or not foot_rec:
        print("  !! не найден header/footer блок, пропускаю")
        return None

    await page.goto("https://tilda.ru/page/?pageid=%s&projectid=%s&edit=y" % (pageid, PROJECTID),
                    wait_until="load", timeout=90000)
    await asyncio.sleep(3.5)
    wp = str(await page.evaluate("window.pageid"))
    if wp != str(pageid):
        print("  !! window.pageid (%s) != ожидаемого (%s), пропускаю" % (wp, pageid))
        return None

    for rid, src, name in [(head_rec, header_src, "header"), (foot_rec, footer_src, "footer")]:
        code = read(src)
        r = await save_code(page, pageid, rid, code)
        ok = "OK" if r == "OK" else r[:60]
        print("  save %-6s rec%s (%d chars, %s) -> %s" % (name, rid, len(code), src, ok))
        await asyncio.sleep(0.6)
    return pageid


async def main():
    done = []
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP)
        page = browser.contexts[0].pages[0]
        for pageid, alias, marker, hsrc, fsrc in PAGES:
            try:
                r = await process(page, pageid, alias, marker, hsrc, fsrc)
                if r:
                    done.append(r)
            except Exception as e:
                print("  ERROR on", alias, ":", repr(e))
    print("\n===== ИТОГ: обновлено %d стр. =====" % len(done))
    print(" ".join(done))
    print("\nДалее: python3 tilda_publish_pages.py " + " ".join(done))


if __name__ == "__main__":
    asyncio.run(main())
