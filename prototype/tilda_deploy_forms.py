#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deploy only the updated Foxinburg form blocks to Tilda."""

import asyncio
import os

from playwright.async_api import async_playwright

from tilda_upload_subpages import detect_roles, fetch, save_code

DIR = os.path.dirname(os.path.abspath(__file__))
PROJECTID = "2053071"
CDP = "http://localhost:29229"
SITE = "https://dymova-english.ru"

HERO_PAGEID = "151210576"
HERO_RECORDID = "2422572641"
HERO_FILE = "tilda_blocks_min/tilda_cta_enrollment_min.html"

COURSE_PAGES = [
    ("151292376", "page_reading.html", "reading"),
    ("151292406", "page_grammar.html", "grammar"),
    ("151292476", "page_preparation.html", "preparation"),
    ("151229566", "page_letnyaya_akademiya.html", "letnyaya-akademiya"),
]


def read(fname):
    with open(os.path.join(DIR, fname), encoding="utf-8") as f:
        return f.read()


async def open_editor(browser, pageid):
    if not browser.contexts:
        raise RuntimeError("no browser context available from CDP connection")
    context = browser.contexts[0]
    page = context.pages[0] if context.pages else await context.new_page()
    await page.goto("https://tilda.ru/page/?pageid=%s&projectid=%s&edit=y" % (pageid, PROJECTID), wait_until="load", timeout=90000)
    await asyncio.sleep(3.5)
    return page


async def save_known_record(browser, pageid, recordid, code, label):
    page = await open_editor(browser, pageid)
    wp = await page.evaluate("window.pageid")
    if str(wp) != str(pageid):
        print("WARN %s: window.pageid=%s expected=%s, skipping" % (label, wp, pageid))
        return None
    try:
        res = await save_code(page, recordid, code)
    except Exception as e:
        print("ERROR %s rec%s: %r" % (label, recordid, e))
        return None
    ok = "OK" if res == "OK" else res[:120]
    print("OK %s pageid=%s rec%s <- %s (%d chars) -> %s" % (label, pageid, recordid, label, len(code), ok))
    return {"pageid": pageid, "recordid": recordid, "label": label}


async def save_content_record(browser, pageid, content_file, alias):
    try:
        html = fetch("%s/%s" % (SITE, alias))
    except Exception as e:
        print("ERROR %s: failed to fetch published HTML: %r" % (alias, e))
        return None

    roles = detect_roles(html)
    content = roles.get("content")
    if not content:
        print("WARN %s: content record not found in published HTML, skipping" % alias)
        return None

    code = read(content_file)
    page = await open_editor(browser, pageid)
    wp = await page.evaluate("window.pageid")
    if str(wp) != str(pageid):
        print("WARN %s: window.pageid=%s expected=%s, skipping" % (alias, wp, pageid))
        return None

    try:
        res = await save_code(page, content, code)
    except Exception as e:
        print("ERROR %s rec%s: %r" % (alias, content, e))
        return None

    ok = "OK" if res == "OK" else res[:120]
    print("OK %s pageid=%s rec%s <- %s (%d chars) -> %s" % (alias, pageid, content, content_file, len(code), ok))
    return {"pageid": pageid, "recordid": content, "alias": alias, "file": content_file}


async def main():
    hero_code = read(HERO_FILE)
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP)

        hero = await save_known_record(browser, HERO_PAGEID, HERO_RECORDID, hero_code, "hero")
        if hero:
            results.append(hero)

        for pageid, content_file, alias in COURSE_PAGES:
            r = await save_content_record(browser, pageid, content_file, alias)
            if r:
                results.append(r)

    print("\n===== FINAL SUMMARY =====")
    if results:
        for item in results:
            if item.get("label") == "hero":
                print("hero: pageid %s record %s <- %s" % (item["pageid"], item["recordid"], HERO_FILE))
            else:
                print("%s: pageid %s record %s <- %s" % (item["alias"], item["pageid"], item["recordid"], item["file"]))
    else:
        print("No blocks were saved.")
    print("Saved blocks only; no shapka/footer updates and no sorting.")


if __name__ == "__main__":
    asyncio.run(main())
