#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Опубликовать страницы Tilda через Kimi WebBridge.

Запуск: python3 tilda_publish_pages_webbridge.py [pageid...]
Требуется: запущенный Kimi WebBridge, авторизованная Tilda.
"""
import json
import sys
import time
import urllib.request

WEBBRIDGE = "http://127.0.0.1:10086/command"
PROJECTID = "2053071"
PAGEIDS = sys.argv[1:] or ["151292376", "151292406", "151292476"]


def wb(action, args):
    req = urllib.request.Request(
        WEBBRIDGE,
        data=json.dumps({"action": action, "args": args}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def evaluate(code, wait=0.5):
    res = wb("evaluate", {"code": code})
    if wait:
        time.sleep(wait)
    return res


def publish_page(pageid):
    print(f"\n=== Публикация pageid {pageid} ===")
    code = f"""
    new Promise((resolve) => {{
        var fd = new FormData();
        fd.append('pageid', '{pageid}');
        fetch('/page/publish/', {{method: 'POST', body: fd, credentials: 'same-origin'}})
          .then(r => r.text())
          .then(t => resolve(t.slice(0, 200)))
          .catch(e => resolve('ERR:' + e.message));
    }})
    """
    res = evaluate(code, wait=4)
    print(f"  результат: {res.get('data', {}).get('value') if res.get('ok') else res}")
    return res.get("ok", False)


def main():
    print("Открываю проект Tilda...")
    wb("navigate", {"url": f"https://tilda.ru/projects/?projectid={PROJECTID}"})
    time.sleep(3)

    ok = 0
    for pid in PAGEIDS:
        try:
            if publish_page(pid):
                ok += 1
        except Exception as e:
            print(f"  ОШИБКА: {e}")

    print(f"\n=== Готово: {ok}/{len(PAGEIDS)} страниц опубликовано ===")


if __name__ == "__main__":
    main()
