#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Найти recordid блока «Преимущества» (#fxb-adv, содержит fxb-adv-modal)
и выгрузить его исходный код (T123) в файл для правки."""
import asyncio, os
from playwright.async_api import async_playwright

PROJECTID = "2053071"
PAGEID = "151210576"
CDP = "http://localhost:29229"
DIR = os.path.dirname(os.path.abspath(__file__))


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP)
        page = browser.contexts[0].pages[0]
        await page.goto(
            "https://tilda.ru/page/?pageid=%s&projectid=%s&edit=y" % (PAGEID, PROJECTID),
            wait_until="load", timeout=90000)
        await asyncio.sleep(4)
        info = await page.evaluate("""()=>{
            var out=null;
            document.querySelectorAll('.record[recordid]').forEach(function(r){
                var html=r.innerHTML||'';
                if(html.indexOf('fxb-adv-modal')>=0 || html.indexOf('id="fxb-adv"')>=0){
                    out={rid:r.getAttribute('recordid'), len:html.length};
                }
            });
            return out;
        }""")
        print("fxb-adv record:", info)
        if not info:
            return
        rid = info["rid"]
        # выгрузить исходный код записи через редактор Tilda
        code = await page.evaluate("""(rid)=>new Promise(r=>{var fd=new FormData();
            fd.append('comm','getrecord');fd.append('pageid','%s');fd.append('recordid',rid);
            fetch('/page/submit/',{method:'POST',body:fd,credentials:'same-origin'})
              .then(x=>x.text()).then(t=>r(t)).catch(e=>r('ERR'+e));})""" % PAGEID, rid)
        open(os.path.join(DIR, "_adv_getrecord.json"), "w", encoding="utf-8").write(code)
        print("getrecord bytes:", len(code), "-> _adv_getrecord.json")


if __name__ == "__main__":
    asyncio.run(main())
