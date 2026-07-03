#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверить, авторизованы ли мы в Tilda и вытащить список страниц проекта."""
import asyncio, json
from playwright.async_api import async_playwright

PROJECTID = "2053071"
CDP = "http://localhost:29229"


async def main():
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp(CDP)
        page = b.contexts[0].pages[0]
        await page.goto("https://tilda.ru/projects/?projectid=%s" % PROJECTID,
                        wait_until="load", timeout=90000)
        await asyncio.sleep(3)
        print("URL:", page.url)
        print("TITLE:", await page.title())
        # collect pages via API
        txt = await page.evaluate("""()=>new Promise((res)=>{
            var fd=new FormData(); fd.append('projectid','%s');
            fetch('/project/pageslist/',{method:'POST',body:fd,credentials:'same-origin'})
              .then(r=>r.text()).then(t=>res(t)).catch(e=>res('ERR:'+e.message));
        })""" % PROJECTID)
        print("PAGESLIST_RAW:", txt[:4000])


asyncio.run(main())
