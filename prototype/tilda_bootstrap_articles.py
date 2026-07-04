#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bootstrap empty Tilda article pages for the Foxinburg blog.

Creates the three expected T123 blocks on pages that were added empty in the
cabinet, then writes the shared shapka/content/footer HTML and sorts records.

Run: python3 tilda_bootstrap_articles.py [alias...]
Requires: open authorized Chrome with CDP on :29229.
"""
import asyncio
import json
import os
import re
import sys

from playwright.async_api import async_playwright

DIR = os.path.dirname(os.path.abspath(__file__))
PROJECTID = "2053071"
CDP = "http://localhost:29229"

PAGES = [
    ("152463826", "page_novosti_so_skolki_let_uchit_anglijskij.html", "novosti-so-skolki-let-uchit-anglijskij"),
    ("152464166", "page_novosti_kak_podgotovitsya_k_oge_anglijskij.html", "novosti-kak-podgotovitsya-k-oge-anglijskij"),
    ("152464306", "page_novosti_kak_prohodyat_smeny_letnej_akademii.html", "novosti-kak-prohodyat-smeny-letnej-akademii"),
]


def read(fname):
    with open(os.path.join(DIR, fname), "r", encoding="utf-8") as f:
        return f.read()


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
    await page.goto("https://tilda.ru/page/?pageid=%s&projectid=%s&edit=y" % (pageid, PROJECTID),
                    wait_until="load", timeout=90000)
    await asyncio.sleep(3.5)
    wp = await page.evaluate("window.pageid")
    if str(wp) != str(pageid):
        print("  !! window.pageid (%s) != ожидаемого (%s), пропускаю" % (wp, pageid))
        return None

    b1 = await add_t123(page, "")
    b2 = await add_t123(page, b1)
    b3 = await add_t123(page, b2)
    if not (b1 and b2 and b3):
        print("  !! не удалось создать все три блока (b1=%s b2=%s b3=%s)" % (b1, b2, b3))
        return None

    content = read(content_file)
    for rid, code, name in [(b1, shapka, "shapka"), (b2, content, "content"), (b3, footer, "footer")]:
        r = await save_code(page, rid, code)
        ok = "OK" if r == "OK" else r[:60]
        print("  save %-7s rec%s (%d chars) -> %s" % (name, rid, len(code), ok))
        await asyncio.sleep(0.6)

    order = [b1, b2, b3]
    res = await sort_records(page, order)
    print("  sort %s -> %s" % (order, res[:30]))
    print("  DONE %s" % alias)
    return {"pageid": pageid, "alias": alias, "blocks": order}


async def main():
    shapka = read("tilda_shapka.html")
    footer = read("tilda_footer.html")
    print("shapka %d chars, footer %d chars" % (len(shapka), len(footer)))
    only = set(sys.argv[1:])
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP)
        page = browser.contexts[0].pages[0]
        for pageid, cfile, alias in PAGES:
            if only and alias not in only:
                continue
            try:
                r = await process_page(page, pageid, cfile, alias, shapka, footer)
                if r:
                    results.append(r)
            except Exception as e:
                print("  ERROR on", alias, ":", repr(e))
    print("\n===== ИТОГ =====")
    for r in results:
        print(r)


if __name__ == "__main__":
    asyncio.run(main())
