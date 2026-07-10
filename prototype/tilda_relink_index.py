#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""На главной заменить устаревшие курс-ссылки с суффиксом -new на канонические.

/reading-new -> /reading, /grammar-new -> /grammar, /preparation-new -> /preparation
Меняем только в 2 видимых кастомных T123-блоках (шапка + блок направлений).
Сырой код берём из опубликованного HTML между маркерами nominify (дословно).
"""
import asyncio, re, urllib.request
from playwright.async_api import async_playwright

PROJECTID = "2053071"
PAGEID = "151210576"
CDP = "http://localhost:29229"
SITE = "https://dymova-english.ru"
RECORDS = ["2421794631", "2422572651"]

REPL = [
    ('href="/reading-new"', 'href="/reading"'),
    ('href="/grammar-new"', 'href="/grammar"'),
    ('href="/preparation-new"', 'href="/preparation"'),
]


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def raw_code(html, rid):
    i = html.find('id="rec%s"' % rid)
    j = html.find('id="rec', i + 5)
    seg = html[i:j if j > 0 else len(html)]
    a = seg.find("nominify begin")
    b = seg.find("nominify end")
    if a < 0 or b < 0:
        return None
    a = seg.find("-->", a) + 3
    code = seg[a:b].rsplit("<!--", 1)[0]
    return code


async def main():
    with open("/tmp/idx_good.html", "r", encoding="utf-8") as f:
        html = f.read()
    assert "nominify begin" in html, "нет nominify в исходном HTML"
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP)
        page = browser.contexts[0].pages[0]
        await page.goto("https://tilda.ru/page/?pageid=%s&projectid=%s&edit=y" % (PAGEID, PROJECTID),
                        wait_until="load", timeout=90000)
        await asyncio.sleep(3.5)
        wp = await page.evaluate("window.pageid")
        assert str(wp) == PAGEID, "window.pageid=%s" % wp
        for rid in RECORDS:
            code = raw_code(html, rid)
            if code is None:
                print(rid, "-> нет nominify, пропуск")
                continue
            before = sum(code.count(a) for a, _ in REPL)
            new = code
            for a, bb in REPL:
                new = new.replace(a, bb)
            changed = before
            if new == code:
                print(rid, "-> нет курс-ссылок, пропуск")
                continue
            res = await page.evaluate("""(o)=>new Promise(r=>{var fd=new FormData();
                fd.append('comm','saverecord');fd.append('pageid',o.pid);
                fd.append('recordid',o.rid);fd.append('onlythisfield','code');
                fd.append('code',o.code);
                fetch('/page/submit/',{method:'POST',body:fd,credentials:'same-origin'})
                  .then(x=>x.text()).then(t=>r(t.slice(0,60))).catch(e=>r('ERR'+e));})""",
                {"pid": PAGEID, "rid": rid, "code": new})
            print(rid, "заменено ссылок:", changed, "len", len(code), "->", len(new), "save:", res.strip())
            await asyncio.sleep(0.8)
        # publish
        pub = await page.evaluate("""(pid)=>new Promise(r=>{var fd=new FormData();
            fd.append('pageid',pid);
            fetch('/page/publish/',{method:'POST',body:fd,credentials:'same-origin'})
              .then(x=>x.text()).then(t=>r(t.slice(0,120))).catch(e=>r('ERR'+e));})""", PAGEID)
        print("publish:", pub)
    print("done")


if __name__ == "__main__":
    asyncio.run(main())
