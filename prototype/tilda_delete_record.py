#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Удалить блоки (recordid) на страницах Tilda."""
import asyncio
from playwright.async_api import async_playwright

PROJECTID = "2053071"
CDP = "http://localhost:29229"

# pageid -> [recordid, ...] лишних блоков
TARGETS = {
    "151292376": ["2422858271"],
    "151292406": ["2422858961"],
    "151292476": ["2422860481"],
}


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP)
        page = browser.contexts[0].pages[0]
        page.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
        for pageid, recs in TARGETS.items():
            await page.goto("https://tilda.ru/page/?pageid=%s&projectid=%s&edit=y" % (pageid, PROJECTID),
                            wait_until="load", timeout=90000)
            await asyncio.sleep(3.5)
            for rid in recs:
                txt = await page.evaluate("""(o)=>new Promise((res)=>{
                    var fd=new FormData();
                    fd.append('comm','deleterecord');
                    fd.append('pageid',o.pageid);
                    fd.append('recordid',o.rid);
                    fetch('/page/submit/',{method:'POST',body:fd,credentials:'same-origin'})
                      .then(r=>r.text()).then(t=>res(t.slice(0,80))).catch(e=>res('ERR:'+e.message));
                })""", {"pageid": pageid, "rid": rid})
                print(pageid, rid, "->", txt)
                await asyncio.sleep(1)
        print("done")


if __name__ == "__main__":
    asyncio.run(main())
