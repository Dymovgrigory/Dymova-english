#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Обновить шапку и подвал на всех страницах через Kimi WebBridge.

Запуск: python3 tilda_update_nav_webbridge.py
Требуется: Kimi WebBridge на :10086, авторизованная Tilda.
"""
import json
import os
import re
import sys
import time
import urllib.request

WEBBRIDGE = "http://127.0.0.1:10086/command"
DIR = os.path.dirname(os.path.abspath(__file__))
PROJECTID = "2053071"
SITE = "https://dymova-english.ru"

SHAPKA, FOOTER = "tilda_shapka.html", "tilda_footer.html"
HEAD_MIN = "tilda_blocks_min/tilda_header_unified_min.html"
FOOT_MIN = "tilda_blocks_min/tilda_footer_min.html"

PAGES = [
    ("151210576", "",                          'id="fxb-hero"',   HEAD_MIN, FOOT_MIN),
    ("151292376", "reading",                   'id="fxb-shapka"', SHAPKA, FOOTER),
    ("151292406", "grammar",                   'id="fxb-shapka"', SHAPKA, FOOTER),
    ("151292476", "preparation",               'id="fxb-shapka"', SHAPKA, FOOTER),
    ("151228606", "doshkolniki",               'id="fxb-shapka"', SHAPKA, FOOTER),
    ("151228676", "mladshie-shkolniki",        'id="fxb-shapka"', SHAPKA, FOOTER),
    ("151228746", "podrostki",                 'id="fxb-shapka"', SHAPKA, FOOTER),
    ("151229566", "letnyaya-akademiya",        'id="fxb-shapka"', SHAPKA, FOOTER),
    ("151229606", "online-zanyatiya",          'id="fxb-shapka"', SHAPKA, FOOTER),
    ("151229676", "podderzhivayushchie-online",'id="fxb-shapka"', SHAPKA, FOOTER),
    ("151229756", "standartnye-offline",       'id="fxb-shapka"', SHAPKA, FOOTER),
    ("151228006", "kontakty",                  'id="fxb-shapka"', SHAPKA, FOOTER),
    ("151324806", "novosti",                   'id="fxb-shapka"', SHAPKA, FOOTER),
    ("151324866", "vakansii",                  'id="fxb-shapka"', SHAPKA, FOOTER),
    ("152445956", "oge-anglijskij",            'id="fxb-shapka"', SHAPKA, FOOTER),
    ("152446216", "ege-anglijskij",            'id="fxb-shapka"', SHAPKA, FOOTER),
    ("152446236", "anglijskij-dlya-vzroslyh",  'id="fxb-shapka"', SHAPKA, FOOTER),
    ("152446286", "nemeckij-yazyk",            'id="fxb-shapka"', SHAPKA, FOOTER),
    ("152446296", "kitajskij-yazyk",           'id="fxb-shapka"', SHAPKA, FOOTER),
    ("152463826", "novosti-so-skolki-let-uchit-anglijskij", 'id="fxb-shapka"', SHAPKA, FOOTER),
    ("152464166", "novosti-kak-podgotovitsya-k-oge-anglijskij", 'id="fxb-shapka"', SHAPKA, FOOTER),
    ("152464306", "novosti-kak-prohodyat-smeny-letnej-akademii", 'id="fxb-shapka"', SHAPKA, FOOTER),
]


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


def read(fname):
    with open(os.path.join(DIR, fname), "r", encoding="utf-8") as f:
        return f.read()


def fetch(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru,en;q=0.9",
    }
    last = None
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers=headers)
            # macOS может не видеть Let's Encrypt / Tilda-сертификат
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            last = e
            time.sleep(2 + attempt * 2)
    raise last


def rec_before(html, marker):
    pos = html.find(marker)
    if pos < 0:
        return None
    cur = None
    for m in re.finditer(r'id="rec(\d+)"', html):
        if m.start() <= pos:
            cur = m.group(1)
        else:
            break
    return cur


def save_code(pageid, recordid, code):
    js = f"""
    new Promise((resolve) => {{
        var fd = new FormData();
        fd.append('comm', 'saverecord');
        fd.append('pageid', '{pageid}');
        fd.append('recordid', '{recordid}');
        fd.append('onlythisfield', 'code');
        fd.append('code', {json.dumps(code)});
        fetch('/page/submit/', {{method: 'POST', body: fd, credentials: 'same-origin'}})
          .then(r => r.text())
          .then(t => resolve(t.slice(0, 80)))
          .catch(e => resolve('ERR:' + e.message));
    }})
    """
    res = evaluate(js, wait=1.2)
    return res.get("data", {}).get("value") if res.get("ok") else str(res)


def publish_page(pageid):
    js = f"""
    new Promise((resolve) => {{
        var fd = new FormData();
        fd.append('pageid', '{pageid}');
        fetch('/page/publish/', {{method: 'POST', body: fd, credentials: 'same-origin'}})
          .then(r => r.text())
          .then(t => resolve(t.slice(0, 80)))
          .catch(e => resolve('ERR:' + e.message));
    }})
    """
    res = evaluate(js, wait=4)
    return res.get("data", {}).get("value") if res.get("ok") else str(res)


def process_page(pageid, alias, marker, header_src, footer_src):
    url = f"{SITE}/{alias}" if alias else f"{SITE}/"
    print(f"\n=== {'/' + alias if alias else '/'} (pageid {pageid}) ===")

    try:
        html = fetch(url)
    except Exception as e:
        print(f"  не удалось получить HTML: {e}")
        return None

    head_rec = rec_before(html, marker)
    foot_rec = rec_before(html, 'id="fxb-footer"')
    print(f"  header rec: {head_rec} | footer rec: {foot_rec}")
    if not head_rec or not foot_rec:
        print("  пропускаю: не найден header/footer")
        return None

    # Переходим в редактор страницы
    wb("navigate", {"url": f"https://tilda.ru/page/?pageid={pageid}&projectid={PROJECTID}&edit=y"})
    time.sleep(4)

    # Проверяем window.pageid
    wp_res = evaluate("window.pageid", wait=0.5)
    wp = str(wp_res.get("data", {}).get("value")) if wp_res.get("ok") else ""
    if wp != str(pageid):
        print(f"  пропускаю: window.pageid={wp} != {pageid}")
        return None

    for rid, src, name in [(head_rec, header_src, "header"), (foot_rec, footer_src, "footer")]:
        code = read(src)
        r = save_code(pageid, rid, code)
        ok = "OK" if r == "OK" else r[:80]
        print(f"  save {name} rec{rid} ({len(code)} chars, {src}) -> {ok}")
        time.sleep(0.6)

    pub = publish_page(pageid)
    print(f"  publish: {pub}")
    return pageid


def main():
    import sys
    only = sys.argv[1:]
    pages = PAGES
    if only:
        only_set = set(only)
        pages = [p for p in PAGES if p[0] in only_set]
        if not pages:
            print("Не найдено страниц с указанными pageid:", only)
            return

    print("Начинаю обновление навигации через WebBridge...")
    done = []
    for pageid, alias, marker, hsrc, fsrc in pages:
        try:
            r = process_page(pageid, alias, marker, hsrc, fsrc)
            if r:
                done.append(r)
        except Exception as e:
            print(f"  ОШИБКА на {alias}: {e}")
    print(f"\n=== Готово: обновлено {len(done)} страниц ===")
    print(" ".join(done))


if __name__ == "__main__":
    main()
