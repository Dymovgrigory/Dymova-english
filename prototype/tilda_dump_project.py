#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Выгрузить HTML страницы проекта Tilda для анализа селекторов страниц."""
import asyncio
from playwright.async_api import async_playwright

PROJECTID = "2053071"
CDP = "http://localhost:29229"


async def main():
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp(CDP)
        page = b.contexts[0].pages[0]
        await page.goto("https://tilda.ru/projects/?projectid=%s" % PROJECTID,
                        wait_until="networkidle", timeout=90000)
        await asyncio.sleep(4)
        html = await page.content()
        with open("/tmp/tilda_project.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("URL:", page.url, "len:", len(html))
        # Look for candidate attributes that hold pageid/alias
        info = await page.evaluate(r"""()=>{
            var res={};
            res.dataPageid = document.querySelectorAll('[data-pageid]').length;
            res.dataAlias  = document.querySelectorAll('[data-alias]').length;
            res.pagesLink  = document.querySelectorAll('a[href*="pageid="]').length;
            // sample of elements referencing pageid in onclick / href
            var samp=[];
            document.querySelectorAll('*').forEach(function(el){
              var oc=el.getAttribute('onclick')||'';
              if(oc.indexOf('pageid')>-1 || oc.indexOf('PageSettings')>-1){ if(samp.length<8) samp.push(oc.slice(0,120)); }
            });
            res.onclickSamples=samp;
            return res;
        }""")
        print("INFO:", info)


asyncio.run(main())
