#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Вытащить список страниц проекта Tilda (pageid, alias, title, статус публикации)."""
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
        await asyncio.sleep(4)
        # Each page tile on the project page carries data attributes.
        data = await page.evaluate("""()=>{
            var out=[];
            document.querySelectorAll('[id^="allrecords_page"], .js-page-block, .pagesbox__item, [data-pageid]').forEach(function(el){
                out.push({
                    pageid: el.getAttribute('data-pageid')||el.id,
                    alias: el.getAttribute('data-alias')||'',
                    cls: el.className
                });
            });
            return out;
        }""")
        print("DOM_TILES:", json.dumps(data, ensure_ascii=False)[:3000])
        # Try the settings/pages API variants
        for endpoint in ['/project/export/', '/page/list/', '/projectpageslist/']:
            txt = await page.evaluate("""(ep)=>new Promise((res)=>{
                var fd=new FormData(); fd.append('projectid','%s');
                fetch(ep,{method:'POST',body:fd,credentials:'same-origin'})
                  .then(r=>r.text()).then(t=>res(t.slice(0,300))).catch(e=>res('ERR:'+e.message));
            })""" % PROJECTID, endpoint)
            print("EP", endpoint, "->", txt[:200])


asyncio.run(main())
