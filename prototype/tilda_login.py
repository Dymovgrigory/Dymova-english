#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Логин в Tilda (email + TILDA_PASSWORD из env)."""
import asyncio, os
from playwright.async_api import async_playwright
EMAIL = os.environ.get("TILDA_EMAIL", "vkrivobokova4@gmail.com")
PWD = os.environ["TILDA_PASSWORD"]
async def main():
    async with async_playwright() as p:
        b=await p.chromium.connect_over_cdp("http://localhost:29229")
        page=b.contexts[0].pages[0]
        await page.goto("https://tilda.ru/login/",wait_until="load",timeout=90000)
        await asyncio.sleep(2)
        fields=await page.evaluate("()=>[].map.call(document.querySelectorAll('input'),i=>({name:i.name,type:i.type}))")
        print("inputs:",fields)
        await page.fill("input[name=email]", EMAIL)
        await page.fill("input[name=password]", PWD)
        await asyncio.sleep(0.3)
        # submit
        btn=await page.query_selector("button[type=submit],input[type=submit],.t-form__submit button")
        if btn: await btn.click()
        else: await page.keyboard.press("Enter")
        await asyncio.sleep(5)
        print("after login url:",page.url)
        await page.goto("https://tilda.ru/projects/?projectid=2053071",wait_until="load",timeout=90000)
        await asyncio.sleep(3)
        print("projects url:",page.url, "title:", await page.title())
asyncio.run(main())
