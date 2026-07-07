#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Обновить блок «Наши преимущества» (fxb-adv, rec2422572521) на /index-new."""
import asyncio, os
from playwright.async_api import async_playwright

PROJECTID = "2053071"
PAGEID = "151210576"
RECORDID = "2422572521"
CDP = "http://localhost:29229"
DIR = os.path.dirname(os.path.abspath(__file__))


async def main():
    with open(os.path.join(DIR, "fxb_adv_v2.html"), "r", encoding="utf-8") as f:
        code = f.read()
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP)
        page = browser.contexts[0].pages[0]
        await page.goto("https://tilda.ru/page/?pageid=%s&projectid=%s&edit=y" % (PAGEID, PROJECTID),
                        wait_until="load", timeout=90000)
        await asyncio.sleep(3.5)
        wp = await page.evaluate("window.pageid")
        assert str(wp) == PAGEID, "window.pageid=%s" % wp
        res = await page.evaluate("""(o)=>new Promise(r=>{var fd=new FormData();
            fd.append('comm','saverecord');fd.append('pageid',o.pid);
            fd.append('recordid',o.rid);fd.append('onlythisfield','code');
            fd.append('code',o.code);
            fetch('/page/submit/',{method:'POST',body:fd,credentials:'same-origin'})
              .then(x=>x.text()).then(t=>r(t.slice(0,80))).catch(e=>r('ERR'+e));})""",
            {"pid": PAGEID, "rid": RECORDID, "code": code})
        print("save (%d chars):" % len(code), res.strip())
        await asyncio.sleep(1)
        pub = await page.evaluate("""(pid)=>new Promise(r=>{var fd=new FormData();
            fd.append('pageid',pid);
            fetch('/page/publish/',{method:'POST',body:fd,credentials:'same-origin'})
              .then(x=>x.text()).then(t=>r(t.slice(0,120))).catch(e=>r('ERR'+e));})""", PAGEID)
        print("publish:", pub)
    print("done")


if __name__ == "__main__":
    asyncio.run(main())
