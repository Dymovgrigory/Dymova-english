#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Открыть форму настроек страницы и выгрузить её поля + найти функции unpublish/index."""
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
        # probe global functions
        fns = await page.evaluate(r"""()=>{
            var out=[];
            for (var k in window){
              try{ if(typeof window[k]==='function' && /publish|unpublish|index|home|main|alias|PageSettings/i.test(k)) out.push(k); }catch(e){}
            }
            return out;
        }""")
        print("FUNCS:", fns)
        # open settings form
        await page.evaluate("(id)=>td__showform__EditPageSettings(id)", PAGEID)
        await asyncio.sleep(2.5)
        form = await page.evaluate(r"""()=>{
            var f=document.forms['formpageedit'];
            if(!f) return 'NO FORM';
            var fields=[];
            [].forEach.call(f.elements, function(el){
              fields.push({name:el.name, type:el.type, value:(el.type==='checkbox'||el.type==='radio')?(el.checked+'|'+el.value):String(el.value).slice(0,60)});
            });
            return fields;
        }""")
        print("FORM_FIELDS:", json.dumps(form, ensure_ascii=False, indent=1))
        # dump any labels mentioning главн/index/публик
        labels = await page.evaluate(r"""()=>{
            var f=document.forms['formpageedit']; if(!f) return [];
            var box=f.closest('.td-popup, .popup, body')||document;
            var txt=[];
            box.querySelectorAll('label, .t-checkbox__label, .td-control-title, div').forEach(function(el){
              var t=(el.textContent||'').trim();
              if(t && /главн|index|индекс|публик|адрес|url|alias/i.test(t) && t.length<80) txt.push(t);
            });
            return Array.from(new Set(txt)).slice(0,25);
        }""")
        print("LABELS:", json.dumps(labels, ensure_ascii=False, indent=1))


asyncio.run(main())
