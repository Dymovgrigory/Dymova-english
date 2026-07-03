#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Снять с публикации указанные страницы Tilda по pageid.

Пробует /page/unpublish/ (с CSRF при наличии). Оригиналы НЕ удаляются —
только снимаются с публикации (остаются черновиками для отката).
"""
import asyncio, sys
from playwright.async_api import async_playwright

PROJECTID = "2053071"
CDP = "http://localhost:29229"
# оригиналы, переименованные в -old
PAGEIDS = sys.argv[1:] or ["137726126", "137739566", "130390566", "146080046", "32889798"]


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
                fd.append('projectid','%s');
                try{ if(typeof getCSRF==='function'){fd.append('tildaajax', getCSRF());} }catch(e){}
                fetch('/page/unpublish/',{method:'POST',body:fd,credentials:'same-origin'})
                  .then(r=>r.text()).then(t=>res(t.slice(0,200))).catch(e=>res('ERR:'+e.message));
            })""" % PROJECTID, pid)
            print(pid, "->", txt)
            await asyncio.sleep(3)
        print("done")


if __name__ == "__main__":
    asyncio.run(main())
