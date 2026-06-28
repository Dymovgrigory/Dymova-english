#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Опубликовать указанные страницы Tilda по pageid (через td__pagePublish)."""
import asyncio, sys
from playwright.async_api import async_playwright

PROJECTID = "2053071"
CDP = "http://localhost:29229"
PAGEIDS = sys.argv[1:] or ["151292376", "151292406", "151292476"]


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP)
        page = browser.contexts[0].pages[0]
        page.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
        await page.goto("https://tilda.ru/projects/?projectid=%s" % PROJECTID,
                        wait_until="load", timeout=90000)
        await asyncio.sleep(3)
        for pid in PAGEIDS:
            txt = await page.evaluate("""(pid)=>new Promise((res)=>{
                var fd=new FormData();
                fd.append('pageid',pid);
                fetch('/page/publish/',{method:'POST',body:fd,credentials:'same-origin'})
                  .then(r=>r.text()).then(t=>res(t.slice(0,200))).catch(e=>res('ERR:'+e.message));
            })""", pid)
            print(pid, "->", txt)
            await asyncio.sleep(4)
        print("done")


if __name__ == "__main__":
    asyncio.run(main())
