#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Задать title/descr/alias страницам Tilda через Kimi WebBridge.

Запуск: python3 tilda_set_settings_webbridge.py
Требуется: запущенный Kimi WebBridge на http://127.0.0.1:10086,
           Chrome с авторизованной Tilda, открытый проект 2053071.

Порядок важен: сначала старые страницы получают -old (освобождают URL),
затем новые занимают канонические /reading / /grammar / /preparation.
"""
import json
import time
import urllib.request

WEBBRIDGE = "http://127.0.0.1:10086/command"
PROJECTID = "2053071"

PAGES = [
    # Новые страницы — занимаем канонические URL.
    # Старые оригиналы (137726126, 137739566, 130390566) находятся в корзине,
    # поэтому канонические URL свободны.
    ("151292376", "Курс по чтению — Фоксинбург",
     "Летний курс по чтению на английском для младших школьников — школа Фоксинбург", "reading"),
    ("151292406", "Курс по грамматике — Фоксинбург",
     "Летний курс грамматики английского для 3–8 классов — школа Фоксинбург", "grammar"),
    ("151292476", "Подготовка к школе — Фоксинбург",
     "Подготовка к школе, занятия со школьниками и подготовка к ОГЭ/ЕГЭ/ВПР — Фоксинбург", "preparation"),
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


def navigate_project():
    print("Открываю проект Tilda...")
    wb("navigate", {"url": f"https://tilda.ru/projects/?projectid={PROJECTID}"})
    time.sleep(3)


def set_page_alias(pageid, title, descr, alias):
    print(f"\n=== pageid {pageid} -> /{alias} ===")

    # Открыть форму настроек
    res = evaluate(f"td__showform__EditPageSettings('{pageid}')", wait=2)
    print(f"  вызов формы: {res.get('data', {}).get('value', 'ok') if res.get('ok') else res}")

    # Проверить, что форма появилась
    form_check = evaluate(
        "document.forms['formpageedit'] ? 'form found' : 'form NOT found'", wait=0.5
    )
    if not form_check.get("ok") or form_check.get("data", {}).get("value") != "form found":
        print("  ОШИБКА: форма не появилась, пропускаю")
        return False

    # Заполнить поля
    evaluate(
        f"""
        var f = document.forms['formpageedit'];
        f.title.value = {json.dumps(title, ensure_ascii=False)};
        f.descr.value = {json.dumps(descr, ensure_ascii=False)};
        f.alias.value = {json.dumps(alias, ensure_ascii=False)};
        'filled';
        """,
        wait=0.5,
    )

    # Проверить значения
    vals = evaluate(
        """
        var f = document.forms['formpageedit'];
        [f.title.value, f.descr.value, f.alias.value];
        """,
        wait=0.3,
    )
    print(f"  значения: {vals.get('data', {}).get('value')}")

    # Отправить форму
    submit = evaluate(
        """
        var f = document.forms['formpageedit'];
        var btn = f.querySelector('input[type=submit]');
        if (btn) { btn.click(); 'clicked'; }
        else { f.dispatchEvent(new Event('submit')); 'submitted'; }
        """,
        wait=2.5,
    )
    print(f"  сохранение: {submit.get('data', {}).get('value') if submit.get('ok') else submit}")
    return True


def main():
    navigate_project()
    ok = 0
    for pageid, title, descr, alias in PAGES:
        try:
            if set_page_alias(pageid, title, descr, alias):
                ok += 1
        except Exception as e:
            print(f"  ОШИБКА: {e}")
    print(f"\n=== Готово: {ok}/{len(PAGES)} страниц обновлено ===")
    print("Далее запусти: python3 tilda_publish_pages.py 137726126 137739566 130390566 151292376 151292406 151292476")


if __name__ == "__main__":
    main()
