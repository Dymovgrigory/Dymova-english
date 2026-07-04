#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Targeted deploy of the two fixed main-page blocks (onboarding + footer/modal)
to Tilda. Matches records by content marker, saves new min content. No sorting."""
import asyncio, os
from playwright.async_api import async_playwright
from tilda_upload_subpages import save_code

PROJECTID = "2053071"
PAGEID = "151210576"
CDP = "http://localhost:29229"
DIR = os.path.dirname(os.path.abspath(__file__))

TARGETS = [
    ("fxb-onboarding", "tilda_blocks_min/tilda_onboarding_min.html", "onboarding"),
    ("fxb-zayavka-modal", "tilda_blocks_min/tilda_footer_min.html", "footer"),
]


def read(fname):
    with open(os.path.join(DIR, fname), encoding="utf-8") as f:
        return f.read()


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP)
        page = browser.contexts[0].pages[0]
        await page.goto(
            "https://tilda.ru/page/?pageid=%s&projectid=%s&edit=y" % (PAGEID, PROJECTID),
            wait_until="load", timeout=90000)
        await asyncio.sleep(4)
        wp = await page.evaluate("window.pageid")
        print("window.pageid =", wp)
        recs = await page.evaluate("""()=>{
            var out=[];
            document.querySelectorAll('.record[recordid]').forEach(function(r){
                out.push({rid:r.getAttribute('recordid'),cod:r.getAttribute('data-record-cod'),html:(r.innerHTML||'')});
            });
            return out;
        }""")
        print("total records:", len(recs))
        for marker, fname, label in TARGETS:
            match = None
            for r in recs:
                if marker in r["html"]:
                    match = r
                    break
            if not match:
                print("NOT FOUND: %s (marker %s)" % (label, marker))
                continue
            code = read(fname)
            res = await save_code(page, match["rid"], code)
            print("SAVE %s rec%s cod=%s (%d chars) -> %s" % (label, match["rid"], match["cod"], len(code), res[:100]))


if __name__ == "__main__":
    asyncio.run(main())
