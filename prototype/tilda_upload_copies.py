#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Залить фирменный контент в страницы /reading / /grammar / /preparation."""
import asyncio
from playwright.async_api import async_playwright
import tilda_upload_subpages as U

PAGES = [
    ("151292376", "page_reading.html", "reading"),
    ("151292406", "page_grammar.html", "grammar"),
    ("151292476", "page_preparation.html", "preparation"),
]


async def main():
    shapka = U.read("tilda_shapka.html")
    footer = U.read("tilda_footer.html")
    print("shapka %d chars, footer %d chars" % (len(shapka), len(footer)))
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(U.CDP)
        page = browser.contexts[0].pages[0]
        for pageid, cfile, alias in PAGES:
            try:
                r = await U.process_page(page, pageid, cfile, alias, shapka, footer)
                results.append(r)
            except Exception as e:
                print("  ERROR on", alias, ":", repr(e))
    print("\n===== ИТОГ =====")
    for r in results:
        print(r)


if __name__ == "__main__":
    asyncio.run(main())
