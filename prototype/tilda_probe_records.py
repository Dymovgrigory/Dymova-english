#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Пробинг: перечислить T123-записи страницы и найти те, что содержат
маркеры fxb-team / fxb-lang (по innerHTML и по тексту)."""
import asyncio, os
from playwright.async_api import async_playwright

PROJECTID = "2053071"
PAGEID = "151210576"
CDP = "http://localhost:29229"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP)
        page = browser.contexts[0].pages[0]
        await page.goto(
            "https://tilda.ru/page/?pageid=%s&projectid=%s&edit=y" % (PAGEID, PROJECTID),
            wait_until="load", timeout=90000)
        await asyncio.sleep(4)
        info = await page.evaluate("""()=>{
            var out=[];
            var recs=document.querySelectorAll('.record[recordid]');
            recs.forEach(function(r){
                var html=r.innerHTML||'';
                out.push({
                    rid:r.getAttribute('recordid'),
                    cod:r.getAttribute('data-record-cod'),
                    team:html.indexOf('fxb-vbtn')>=0,
                    lang:html.indexOf('fxb-teacher-photo')>=0,
                    len:html.length
                });
            });
            return {count:recs.length, recs:out};
        }""")
        print("total records:", info["count"])
        for r in info["recs"]:
            mark = ""
            if r["team"]:
                mark += " <== TEAM"
            if r["lang"]:
                mark += " <== LANG"
            print("rec%s cod=%s len=%s%s" % (r["rid"], r["cod"], r["len"], mark))


if __name__ == "__main__":
    asyncio.run(main())
