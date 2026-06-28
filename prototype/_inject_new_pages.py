#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Создать 3 T123-блока (шапка/контент/подвал) на ПУСТЫХ новых страницах."""
import asyncio, json, os, re
from playwright.async_api import async_playwright

DIR = os.path.dirname(os.path.abspath(__file__))
PROJECTID = "2053071"
CDP = "http://localhost:29229"

# (pageid, content_file, alias)
PAGES = [
    ("151324806", "page_novosti.html", "novosti"),
    ("151324866", "page_vakansii.html", "vakansii"),
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
    return (await api(page, {"comm": "saverecord", "pageid": pageid, "recordid": recordid,
                             "onlythisfield": "code", "code": code})).strip()


async def sort_records(page, order):
    pageid = await page.evaluate("window.pageid")
    fields = {"comm": "saverecordssort", "pageid": pageid}
    for i, rid in enumerate(order):
        fields["sorts[%d]" % i] = rid
    return await api(page, fields)


async def main():
    shapka = read("tilda_shapka.html")
    footer = read("tilda_footer.html")
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp(CDP)
        page = b.contexts[0].pages[0]
        for pageid, cfile, alias in PAGES:
            print("\n==== %s (pageid %s) ====" % (alias, pageid))
            await page.goto("https://tilda.ru/page/?pageid=%s&projectid=%s&edit=y" % (pageid, PROJECTID),
                            wait_until="load", timeout=90000)
            await asyncio.sleep(3.5)
            wp = await page.evaluate("window.pageid")
            if str(wp) != str(pageid):
                print("  !! window.pageid", wp, "!=", pageid, "- skip")
                continue
            sh = await add_t123(page, "")
            await asyncio.sleep(1)
            ct = await add_t123(page, sh)
            await asyncio.sleep(1)
            ft = await add_t123(page, ct)
            await asyncio.sleep(1)
            print("  blocks:", sh, ct, ft)
            content_code = read(cfile)
            for rid, code, name in [(sh, shapka, "shapka"), (ct, content_code, "content"), (ft, footer, "footer")]:
                r = await save_code(page, rid, code)
                print("  save %-7s rec%s (%d chars) -> %s" % (name, rid, len(code), "OK" if r == "OK" else r[:60]))
                await asyncio.sleep(0.6)
            res = await sort_records(page, [sh, ct, ft])
            print("  sort", [sh, ct, ft], "->", res[:30])


if __name__ == "__main__":
    asyncio.run(main())
