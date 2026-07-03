#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Изучить вкладку Actions и исходники функций unpublish / make-home."""
import asyncio, json
from playwright.async_api import async_playwright

PROJECTID = "2053071"
CDP = "http://localhost:29229"
PAGEID = "151210576"  # index-new


async def main():
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp(CDP)
        page = b.contexts[0].pages[0]
        page.on("dialog", lambda d: asyncio.ensure_future(d.dismiss()))
        await page.goto("https://tilda.ru/projects/?projectid=%s" % PROJECTID,
                        wait_until="load", timeout=90000)
        await asyncio.sleep(3)
        srcs = await page.evaluate(r"""()=>{
            var names=['td__pagesettings__pageUnpublish','td__project__unpublishSelectedPages',
                       'td__pagesettings__drawTabActions','td__pagesettings__updatePage','tc__clearPageAlias'];
            var out={};
            names.forEach(function(n){ try{ out[n]=String(window[n]).slice(0,900);}catch(e){out[n]='ERR';} });
            return out;
        }""")
        for k,v in srcs.items():
            print("\n===== %s =====\n%s" % (k, v))
        # search all function sources for 'index' / 'setindex' / 'главн'
        hits = await page.evaluate(r"""()=>{
            var out=[];
            for (var k in window){
              try{ var s=String(window[k]); if(typeof window[k]==='function' && /setindex|makeindex|set_index|is_index|isindex|setmain|mainpage/i.test(s+k)) out.push(k);}catch(e){}
            }
            return out;
        }""")
        print("\nINDEX_FN_HITS:", hits)
        # Look at the actions tab html for index-new page
        await page.evaluate("(id)=>td__showform__EditPageSettings(id)", PAGEID)
        await asyncio.sleep(2)
        # click Actions tab if present
        acts = await page.evaluate(r"""()=>{
            // find tab labeled Действия
            var tabs=[].slice.call(document.querySelectorAll('.td-pagesettings__tab, .td-tabs__item, [onclick*=drawTab]'));
            var found=null;
            tabs.forEach(function(t){ if(/действ|actions/i.test(t.textContent)) found=t.outerHTML.slice(0,120);});
            return {tabsCount:tabs.length, actionsTab:found};
        }""")
        print("\nTABS:", acts)
        # try to call drawTabActions directly and read its html
        html = await page.evaluate(r"""()=>{
            try{
              var f=document.forms['formpageedit'];
              // find the actions tab content container
              var body=document.querySelector('.td-pagesettings, .td-popup__content, .popup') || document.body;
              return body.innerText.slice(0,1500);
            }catch(e){return 'ERR '+e.message;}
        }""")
        print("\nSETTINGS_TEXT:\n", html)


asyncio.run(main())
