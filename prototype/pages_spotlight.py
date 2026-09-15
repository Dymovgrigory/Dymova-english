# -*- coding: utf-8 -*-
"""Страницы курсов Spotlight 2–5 — английский по школьному учебнику.

Тексты курсов НЕ дублируются: читаем те же словари SP2–SP5, PRICE и SCHOOL,
по которым собираются презентации для родителей
(presentations/spotlight/content.py). Правка текста курса — только там,
сайт и презентация меняются вместе.
"""
from __future__ import annotations

import os
import sys

_SPOTLIGHT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "presentations", "spotlight")
if _SPOTLIGHT_DIR not in sys.path:
    sys.path.insert(0, _SPOTLIGHT_DIR)

import content as _c  # noqa: E402  (путь добавляется выше)

# Хелперы генератора (strip_tags, course_jsonld, breadcrumb_jsonld). Идиома та же,
# что в pages_wave*.py: build_subpages запускается и как скрипт, и как модуль —
# в первом случае он лежит в sys.modules под именем __main__, и обычный
# `import build_subpages` создал бы второй экземпляр модуля с циклической ссылкой.
if hasattr(sys.modules.get("__main__"), "PAGES"):
    B = sys.modules["__main__"]  # build_subpages запущен как скрипт
else:
    import build_subpages as B  # noqa: E402

PRICE = _c.PRICE
ASSETS = "/assets/spotlight"

# Градиенты hero — по одному на класс, чтобы четыре страницы не выглядели
# копиями друг друга.
_GRADIENTS = {
    2: "linear-gradient(135deg,#2e1a47 0%,#5a2d8f 55%,#7b4fc0 100%)",
    3: "linear-gradient(135deg,#241a36 0%,#662d92 55%,#8a4fb8 100%)",
    4: "linear-gradient(135deg,#241540 0%,#5f2a8c 55%,#c24712 100%)",
    5: "linear-gradient(135deg,#392852 0%,#7b4fc0 55%,#662d92 100%)",
}

_WHY_ICONS = ("clock", "group", "book", "pencil")
_RESULT_ICONS = ("book", "pencil", "chat", "headset", "target", "star")


def _modules_section(deck):
    """Программа года: все модули учебника по порядку — таблицей-списком."""
    rows = []
    for num, name, topic, detail, is_starter in deck["modules"]:
        badge = "★" if is_starter else num
        mod = " fxb-sp-mod--starter" if is_starter else ""
        rows.append(
            '<div class="fxb-sp-mod' + mod + '">'
            '<span class="fxb-sp-mod-n">' + badge + '</span>'
            '<div class="fxb-sp-mod-txt"><b>' + name + '</b>'
            '<span class="fxb-sp-mod-topic">' + topic + '</span>'
            '<p>' + detail + '</p></div></div>')
    return (
        '<section class="fxb-section" id="fxb-modules"><div class="fxb-wrap">'
        '<div class="fxb-head"><span class="fxb-kicker"><span class="fxb-dot"></span>Программа года</span>'
        '<h2 class="fxb-h2">Все модули учебника — <span class="fxb-accent">по порядку</span></h2>'
        '<p class="fxb-lead">Курс повторяет структуру учебника. Каждый модуль — лексика, '
        'грамматика, чтение, аудирование, говорение и письмо по одной теме.</p></div>'
        '<div class="fxb-sp-mods">' + "".join(rows) + '</div>'
        '</div></section>')


def _textbook_section(deck):
    """Учебник, уровень и цифры года + кнопка скачивания презентации."""
    grade = deck["grade"]
    stats = "".join(
        '<div class="fxb-sp-stat"><b>' + value + '</b><span>' + label + '</span></div>'
        for value, label in deck["focus_stat"])
    return (
        '<section class="fxb-section fxb-bg-light"><div class="fxb-wrap">'
        '<div class="fxb-head"><span class="fxb-kicker"><span class="fxb-dot"></span>Учебник</span>'
        '<h2 class="fxb-h2">Работаем по <span class="fxb-accent">Spotlight ' + str(grade) + '</span></h2></div>'
        '<div class="fxb-sp-book">'
        '<img class="fxb-sp-cover" src="' + ASSETS + '/cover-sp' + str(grade) + '.jpg" '
        'alt="Учебник «Английский в фокусе» Spotlight ' + str(grade) + '" width="420" height="595" loading="lazy">'
        '<div class="fxb-sp-book-txt">'
        '<p><b>«Английский в фокусе» · Spotlight ' + str(grade) + '</b><br>' + deck["authors"] + '</p>'
        '<p>Издательство «Просвещение» и Express Publishing, редакция ФГОС 2021.</p>'
        '<p><b>Уровень по итогам года:</b> ' + deck["level"] + '</p>'
        '<p>Spotlight — самый распространённый УМК по английскому в российских школах. '
        'Мы берём <b>тот же учебник</b> и подкрепляем его отработкой каждого правила, '
        'чтением вслух, говорением и домашними заданиями, на которые в школе не хватает времени.</p>'
        '<div class="fxb-sp-stats">' + stats + '</div>'
        '<a class="fxb-btn-sec fxb-sp-pdf" href="' + ASSETS + '/spotlight-' + str(grade) +
        '-klass-foxinburg.pdf" target="_blank" rel="noopener">Скачать презентацию курса (PDF)</a>'
        '</div></div></div></section>')


def _grammar_section(deck):
    """Грамматика и фоника года — два списка рядом."""
    grammar = "".join("<li>" + x + "</li>" for x in deck["grammar"])
    phonics = "".join("<li>" + x + "</li>" for x in deck["phonics"])
    extra = "".join(
        '<div class="fxb-sp-extra"><b>' + title + '</b><p>' + text + '</p></div>'
        for title, text in deck["extra"])
    return (
        '<section class="fxb-section"><div class="fxb-wrap">'
        '<div class="fxb-head"><span class="fxb-kicker"><span class="fxb-dot"></span>Отрабатываем</span>'
        '<h2 class="fxb-h2">Грамматика и чтение — <span class="fxb-accent">до автоматизма</span></h2></div>'
        '<div class="fxb-sp-cols">'
        '<div class="fxb-sp-col"><h3>Грамматика года</h3><ul class="fxb-sp-list">' + grammar + '</ul></div>'
        '<div class="fxb-sp-col"><h3>Чтение и произношение</h3><ul class="fxb-sp-list">' + phonics + '</ul></div>'
        '</div><div class="fxb-sp-extras">' + extra + '</div>'
        '</div></section>')


SPOTLIGHT_CSS = """
<style>
#fxb-page .fxb-sp-mods{display:grid;grid-template-columns:repeat(2,1fr);gap:18px}
#fxb-page .fxb-sp-mod{display:flex;gap:16px;align-items:flex-start;background:#fff;border:1.5px solid rgba(102,45,146,.08);border-radius:18px;padding:22px 24px}
#fxb-page .fxb-sp-mod--starter{border-color:var(--yellow);background:linear-gradient(135deg,#fffdf0,#fff)}
#fxb-page .fxb-sp-mod-n{flex:0 0 auto;width:38px;height:38px;border-radius:12px;display:grid;place-items:center;font-weight:900;font-size:16px;color:#fff;background:var(--purple-2)}
#fxb-page .fxb-sp-mod--starter .fxb-sp-mod-n{background:var(--orange)}
#fxb-page .fxb-sp-mod-txt b{display:block;font-size:17px;color:var(--ink);margin-bottom:2px}
#fxb-page .fxb-sp-mod-topic{display:block;font-size:13px;font-weight:700;color:var(--purple-2);margin-bottom:8px}
#fxb-page .fxb-sp-mod-txt p{font-size:14px;color:var(--muted);line-height:1.55}
#fxb-page .fxb-sp-book{display:grid;grid-template-columns:280px 1fr;gap:42px;align-items:start}
#fxb-page .fxb-sp-cover{width:100%;height:auto;border-radius:14px;box-shadow:0 18px 44px -18px rgba(57,40,82,.45)}
#fxb-page .fxb-sp-book-txt p{font-size:15px;color:var(--muted);line-height:1.65;margin-bottom:14px}
#fxb-page .fxb-sp-book-txt b{color:var(--ink)}
#fxb-page .fxb-sp-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:24px 0}
#fxb-page .fxb-sp-stat b{display:block;font-size:26px;font-weight:900;color:var(--purple-2);line-height:1.1}
#fxb-page .fxb-sp-stat span{font-size:12.5px;color:var(--muted);font-weight:600}
#fxb-page .fxb-sp-pdf{display:inline-block;margin-top:6px}
#fxb-page .fxb-sp-cols{display:grid;grid-template-columns:repeat(2,1fr);gap:32px}
#fxb-page .fxb-sp-col h3{font-size:18px;color:var(--ink);margin-bottom:14px}
#fxb-page .fxb-sp-list{list-style:none;padding:0;margin:0}
#fxb-page .fxb-sp-list li{position:relative;padding:9px 0 9px 26px;font-size:14.5px;color:var(--muted);border-bottom:1px solid rgba(102,45,146,.06)}
#fxb-page .fxb-sp-list li::before{content:"";position:absolute;left:0;top:15px;width:12px;height:12px;border-radius:50%;border:2px solid var(--purple-2);background:rgba(102,45,146,.08)}
#fxb-page .fxb-sp-extras{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin-top:32px}
#fxb-page .fxb-sp-extra{background:rgba(102,45,146,.05);border-radius:16px;padding:20px 22px}
#fxb-page .fxb-sp-extra b{display:block;font-size:15px;color:var(--ink);margin-bottom:6px}
#fxb-page .fxb-sp-extra p{font-size:13.5px;color:var(--muted);line-height:1.55}
@media(max-width:900px){
  #fxb-page .fxb-sp-mods,#fxb-page .fxb-sp-cols,#fxb-page .fxb-sp-extras{grid-template-columns:1fr}
  #fxb-page .fxb-sp-book{grid-template-columns:1fr;gap:26px}
  #fxb-page .fxb-sp-cover{max-width:260px}
  #fxb-page .fxb-sp-stats{grid-template-columns:repeat(2,1fr)}
}
</style>
"""


def _course_jsonld(name, deck, url):
    description = B.strip_tags(deck["lead"])
    return B.course_jsonld(name, description, url,
                           offer_name="Курс Spotlight %d" % deck["grade"],
                           price=PRICE["now"].replace(" ", ""))


def _breadcrumb_jsonld(grade, alias):
    return B.breadcrumb_jsonld([
        ("Главная", "https://dymova-english.ru/"),
        ("Курсы английского", "https://dymova-english.ru/kursy-v-dolgoprudnom"),
        ("Spotlight %d — %d класс" % (grade, grade), "https://dymova-english.ru/" + alias),
    ])


def _page(deck):
    grade = deck["grade"]
    alias = "spotlight-%d-klass" % grade
    url = "https://dymova-english.ru/" + alias
    title_plain = "Английский по Spotlight %d — курс для %d класса" % (grade, grade)
    subject = "Spotlight %d — английский для %d класса" % (grade, grade)
    return {
        "hero_grad": _GRADIENTS[grade],
        "eyebrow": "Spotlight %d · %s · %s" % (grade, deck["klass"], deck["age"]),
        "h1": 'Английский по учебнику <span class="fxb-accent">Spotlight %d</span>' % grade,
        "sub": deck["lead"],
        "cta_label": "Записаться на курс",
        "feat_kicker": "Зачем нужен курс",
        "feat_title": 'Почему в школе <span class="fxb-accent">не хватает времени</span>',
        "feat_lead": "Не «ещё один кружок», а поддержка по школьной программе: "
                     "идём по тому же учебнику на шаг впереди класса.",
        "features": [
            (_WHY_ICONS[i % len(_WHY_ICONS)], head, text)
            for i, (head, text) in enumerate(deck["why"])
        ],
        "facts_title": "Коротко о курсе",
        "facts": [
            ("calendar", "9 месяцев", "Сентябрь — май, параллельно школе"),
            ("clock", "2 раза в неделю", "Занятие 60 минут"),
            ("group", "До 7 человек", "Мини-группы по уровню"),
            ("cap", deck["level"].split("(")[0].strip(), "Уровень по итогам года"),
        ],
        "adv_kicker": "Результат курса",
        "adv_title": 'К концу года ребёнок <span class="fxb-accent">сможет сам</span>',
        "adv_lead": "Главная цель курса — самостоятельность: чтобы вечером ребёнок сам открыл "
                    "учебник, понял задание и выполнил его без взрослого.",
        "advantages": [
            (_RESULT_ICONS[i % len(_RESULT_ICONS)], head, text)
            for i, (head, text) in enumerate(deck["results"])
        ],
        "extra_sections": [
            _textbook_section(deck),
            _modules_section(deck),
            _grammar_section(deck),
        ],
        "prices": True,
        "price_title": "Стоимость курса Spotlight %d" % grade,
        "price_lead": "Цена за месяц занятий в мини-группе. Учебные материалы включены.",
        "price_cards": [
            ("Курс Spotlight %d" % grade, "",
             PRICE["now"] + ' ₽<span>/мес</span>',
             "Вместо " + PRICE["old"] + " ₽ · 2 занятия в неделю по 60 минут"),
            ("За одно занятие", " fxb-price-tag--orange",
             PRICE["per_lesson"] + " ₽",
             "8 занятий в месяц в мини-группе до 7 человек"),
            ("Экономия за год", "",
             PRICE["save_year"] + " ₽",
             PRICE["save_month"] + " ₽ каждый месяц учебного года"),
        ],
        "faq_title": "Частые вопросы про курс Spotlight %d" % grade,
        "faq": [
            ("Мы и так учим английский в школе — зачем ещё курс?",
             "В школе английский идёт 2 раза в неделю на подгруппу около 15 человек: "
             "за 45 минут ребёнок отвечает один-два раза. Мы идём по тому же учебнику "
             "в мини-группе до 7 человек и доводим каждое правило до речи, а не только до упражнения."),
            ("Вы идёте по тому же учебнику, что и школа?",
             "Да. Курс построен на «Английском в фокусе» Spotlight %d (%s), "
             "редакция ФГОС 2021 — тот же учебник, что и в школе, только на шаг впереди." % (grade, deck["authors"])),
            ("Какой уровень будет у ребёнка к концу года?",
             "%s — это соответствует требованиям ФГОС к %s и международной шкале CEFR."
             % (deck["level"], deck["klass"])),
            ("Сколько стоит и сколько занятий в месяц?",
             "%s ₽ в месяц вместо %s ₽ — 2 занятия в неделю по 60 минут, %s ₽ за занятие. "
             "За учебный год экономия %s ₽." % (PRICE["now"], PRICE["old"], PRICE["per_lesson"], PRICE["save_year"])),
            ("Ребёнок отстал от класса — успеет догнать?",
             "Перед стартом проводим бесплатную диагностику: смотрим, какие темы модуля "
             "просели, и подбираем группу по реальному уровню, а не по номеру класса."),
        ],
        "lead_subject": subject,
        "lead_hero_window": "Блок героя",
        "lead_final_window": "Финальный блок",
        "cta_title": 'Запишитесь на курс <span class="fxb-accent">Spotlight %d</span>' % grade,
        "cta_text": "Оставьте заявку — расскажем расписание групп, проведём бесплатную "
                    "диагностику и подберём подходящий уровень.",
        "extra_jsonld": [
            _course_jsonld(title_plain, deck, url),
            _breadcrumb_jsonld(grade, alias),
        ],
        "extra_css": SPOTLIGHT_CSS,
    }


SPOTLIGHT_PAGES = {
    "page_spotlight_%d_klass.html" % deck["grade"]: _page(deck)
    for deck in _c.DECKS
}
