#!/usr/bin/env python3
"""Сборка продающих презентаций по курсам Spotlight 2-5 для родителей.

Генерирует по одному HTML-файлу на класс и печатает их в PDF через headless Chrome.

    python3 build.py            # HTML + PDF
    python3 build.py --html     # только HTML
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

from content import DECKS, PRICE, SCHOOL, TEACHER

ROOT = Path(__file__).parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
MODS_PER_SLIDE = 9

LINKS = {
    "site": "https://dymova-english.ru",
    "vk": "https://vk.com/foxyfoxclub",
    "telegram": "https://t.me/foxinburg",
    "whatsapp": "https://wa.me/79939232309",
    "max": "https://max.ru/id611904726658_biz",
    "map_main": "https://yandex.ru/maps/?text=" + quote("Долгопрудный, проспект Лихачевский, 76к1"),
    "map_alt": "https://yandex.ru/maps/?text=" + quote("Долгопрудный, проспект Ракетостроителей, 9к3"),
}


# --------------------------------------------------------------- вспомогательные
def logo() -> str:
    return (
        '<div class="logo"><img src="assets/fox-head-purple.png" alt="">'
        '<div class="wordmark">ФОКСИНБУРГ<small>ЯЗЫКОВАЯ ШКОЛА</small></div></div>'
    )


def slide(deck: dict, eyebrow: str, heading: str, body: str, lead: str = "") -> str:
    lead_html = f'<p class="lead">{lead}</p>' if lead else ""
    return f"""<section class="slide">
  {logo()}
  <div class="eyebrow">{eyebrow}</div>
  <h2>{heading}</h2>
  {lead_html}
  <div class="body">{body}</div>
  <div class="foot">Языковая школа «Фоксинбург» · Spotlight {deck['grade']} · {deck['klass']}</div>
</section>"""


def cards(items, cls="card") -> str:
    out = []
    for title, text in items:
        out.append(f'<div class="{cls}"><h3>{title}</h3><p>{text}</p></div>')
    return "".join(out)


def ticks(items) -> str:
    return '<ul class="ticks">' + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


# --------------------------------------------------------------------- слайды
def s_cover(d: dict) -> str:
    return f"""<section class="slide cover">
  <div class="inner">
    <div class="left">
      <div class="brandline">
        <img src="assets/fox-head-purple.png" alt="">
        <div class="wordmark">ФОКСИНБУРГ<small>ЯЗЫКОВАЯ ШКОЛА</small></div>
      </div>
      <h1>Английский<br>по учебнику<br><em>Spotlight {d['grade']}</em></h1>
      <div class="klass">Курс для {d['klass']}а · {d['age']}</div>
      <p class="tagline">{d['lead']}</p>
      <div class="pills">
        <div class="pill">9 месяцев · <b>сентябрь — май</b></div>
        <div class="pill">2 раза в неделю · <b>по 60 минут</b></div>
        <div class="pill">мини-группы · <b>до 7 человек</b></div>
      </div>
      <div class="year">{SCHOOL['year']} · г. Долгопрудный</div>
    </div>
    <div class="right">
      <img class="book" src="assets/cover-sp{d['grade']}.jpg" alt="Учебник Spotlight {d['grade']}">
      <img class="foxi" src="assets/mascot-foxinburg.png" alt="">
    </div>
  </div>
</section>"""


def s_why(d: dict) -> str:
    head, cls, tail = d["why_title"]
    body = f"""<div style="display:grid;grid-template-columns:1.55fr 1fr;gap:4.4mm;flex:1">
  <div class="grid g2 stretch">{cards(d['why'])}</div>
  <div class="card purple">
    <div class="kicker">Что делаем мы</div>
    <h3>Не «ещё один кружок», а поддержка по школьной программе английского языка и развития ребёнка</h3>
    <p style="margin-bottom:3mm">Наш курс разработан по школьному учебнику <b>Spotlight {d['grade']}</b> — мы идём на шаг впереди.</p>
    <ul class="ticks">
      <li>Разбираем каждую тему модуля <b>до конца</b> — так, чтобы ребёнок усвоил и запомнил</li>
      <li>Доводим правила до автоматизма в речи, а не только в упражнениях</li>
      <li>Ребёнок приходит в школу подготовленным: чувствует себя уверенно, не боится отвечать
          и <b>успешно справляется с контрольными</b></li>
    </ul>
  </div>
</div>"""
    return slide(d, "Зачем нужен курс", f'{head}<span class="{cls}">{tail}</span>', body)


def s_book(d: dict) -> str:
    stats = "".join(
        f'<div class="stat"><div class="v">{v}</div><div class="k">{k}</div></div>'
        for v, k in d["focus_stat"]
    )
    body = f"""<div style="display:grid;grid-template-columns:52mm 1fr;gap:8mm;flex:1;align-items:center">
  <img class="book-inline" src="assets/cover-sp{d['grade']}.jpg" style="width:52mm" alt="">
  <div>
    <div class="grid g2" style="gap:3.4mm">
      <div class="card cream">
        <div class="kicker">Учебник</div>
        <h3>«Английский в фокусе» · Spotlight {d['grade']}</h3>
        <p>{d['authors']}<br>Издательство «Просвещение» и Express Publishing, редакция ФГОС 2021.</p>
      </div>
      <div class="card">
        <div class="kicker">Уровень по итогам года</div>
        <h3>{d['level']}</h3>
        <p>Соответствует требованиям ФГОС к {d['klass']}у и международной шкале CEFR.</p>
      </div>
    </div>
    <div class="card purple" style="margin-top:3.4mm">
      <div class="kicker">Главное</div>
      <p>Spotlight — самый распространённый УМК по английскому в российских школах. Мы берём <b>тот же учебник</b>
      и подкрепляем его сильной методикой: с отработкой каждого правила, чтением вслух, говорением и домашними заданиями,
      на которые в школе не хватает времени.</p>
    </div>
    <div class="stat-row" style="margin-top:3.4mm">{stats}</div>
  </div>
</div>"""
    return slide(d, "Учебник, по которому учится ваш ребёнок",
                 f'Работаем по <span class="hl">Spotlight {d["grade"]}</span>', body)


def s_results(d: dict) -> str:
    body = f"""<div class="grid g3 stretch">{cards(d['results'])}</div>
<div class="spec" style="grid-template-columns:1fr">
  <div class="it"><div class="k">Главная цель курса — самостоятельность</div>
  <div class="v">Чтобы вечером ребёнок сам открыл учебник и рабочую тетрадь, понял задание и выполнил его без взрослого.
  Всё остальное — оценки, уверенность у доски и интерес к языку — приходит следом.</div></div>
</div>"""
    return slide(d, "Результат курса",
                 f'{d["result_title"][0]}<span class="{d["result_title"][1]}">{d["result_title"][2]}</span>', body)


def s_modules(d: dict) -> list[str]:
    cells = []
    for num, title, ru, desc, starter in d["modules"]:
        cls = "mod starter" if starter else "mod"
        label = "★" if starter else num
        cells.append(
            f'<div class="{cls}"><div class="n">{label}</div><div class="b">'
            f'<div class="t">{title}</div><div class="ru">{ru}</div><div class="d">{desc}</div>'
            "</div></div>"
        )
    n = len(d["modules"])
    cols = "g2" if n <= 6 else ("g3" if n <= 9 else "g4")
    band = """<div class="spec">
  <div class="it"><div class="k">После каждого модуля</div><div class="v">Проверочная работа по формату учебника — та же, что в школе.</div></div>
  <div class="it"><div class="k">Каждый месяц</div><div class="v">Тестирование по пройденным темам и отдельным навыкам.</div></div>
  <div class="it"><div class="k">Лексика модуля</div><div class="v">Тренируется в приложении «Твоя школа» в игровой форме.</div></div>
  <div class="it"><div class="k">Проекты</div><div class="v">Spotlight on Russia — готовим и защищаем проект на английском.</div></div>
</div>"""
    mods_n = len(d["modules"]) - 1
    if cols == "g4":  # 10+ модулей — короткий лид в одну строку, иначе сетка не помещается
        lead = f"Курс повторяет структуру учебника: {mods_n} модулей и стартовый раздел."
    else:
        lead = (f"Курс повторяет структуру учебника: {mods_n} модулей и стартовый раздел. "
                "Каждый модуль — это лексика, грамматика, чтение, аудирование, говорение и письмо по одной теме.")
    body = f'<div class="mods {cols} stretch">{"".join(cells)}</div>{band}'
    return [slide(d, "Программа года",
                  'Все модули учебника — <span class="hl">по порядку</span>', body, lead)]


def s_grammar(d: dict) -> str:
    extra = "".join(
        f'<div class="card"><h3>{t}</h3><p>{p}</p></div>' for t, p in d["extra"]
    )
    body = f"""<div class="grid g2">
  <div class="card purple"><div class="kicker">Грамматика</div><h3>Что разберём и доведём до автоматизма</h3>{ticks(d['grammar'])}</div>
  <div class="card cream"><div class="kicker">Чтение и произношение</div><h3>Фонетика и техника чтения</h3>{ticks(d['phonics'])}
    <p style="margin-top:auto;padding-top:3mm">Читаем вслух на каждом занятии. К концу года ребёнок открывает незнакомый текст
    учебника и читает его сам — без «угадывания» слов по первой букве.</p>
  </div>
</div>
<div class="grid g3">{extra}</div>"""
    return slide(d, "Грамматика, чтение и дополнительные разделы",
                 'Отрабатываем <span class="hly">до автоматизма</span>', body)


def s_lesson(d: dict) -> str:
    blocks = [
        ("5 мин", "Разогрев", "Приветствие, повторение слов прошлого урока, короткая игра на английском."),
        ("10 мин", "Домашнее задание", "Разбираем, что не получилось. Ни одно непонятое место не уходит домой."),
        ("20 мин", "Новая тема", "Лексика и грамматика модуля: объяснение, примеры, управляемая практика."),
        ("15 мин", "Практика речи", "Диалоги, чтение вслух, аудирование, игра или задание в парах."),
        ("10 мин", "Итог и домашка", "Закрепление, выдача задания в приложение, монетки за активность."),
    ]
    flow = "".join(
        f'<div class="blk"><div class="min">{m}</div><h4>{t}</h4><p>{p}</p></div>'
        for m, t, p in blocks
    )
    body = f"""<div class="flow">{flow}</div>
<div class="grid g3 stretch">
  <div class="card cream"><h3>Всё занятие — на английском</h3><p>Русский используем только там, где без него не объяснить грамматику. Инструкции, игры и обсуждение — на английском.</p></div>
  <div class="card cream"><h3>Каждый говорит на каждом уроке</h3><p>В группе до 7 человек у ребёнка в 4–5 раз больше речевого времени, чем в обычном классе.</p></div>
  <div class="card cream"><h3>Смена деятельности каждые 10 минут</h3><p>Объяснение, игра, чтение, движение. Дети этого возраста не могут держать внимание 60 минут подряд — и мы это учитываем.</p></div>
</div>"""
    return slide(d, "Как проходит занятие", 'Урок на <span class="hl">60 минут</span>', body)


def s_format(d: dict) -> str:
    body = """<div class="grid g4">
  <div class="card"><div class="big">9</div><h3>месяцев обучения</h3><p>С сентября по май — полный учебный год, параллельно школьной программе.</p></div>
  <div class="card"><div class="big">2 × 60</div><h3>занятия в неделю</h3><p>Два урока по 60 минут. Оптимальный ритм: материал не забывается между занятиями.</p></div>
  <div class="card"><div class="big">до 7</div><h3>человек в группе</h3><p>Мини-группы по возрасту и уровню. Педагог видит каждого ребёнка.</p></div>
  <div class="card"><div class="big">≈ 72</div><h3>занятия за год</h3><p>Абонемент на календарный месяц: стоимость не меняется, сколько бы уроков ни выпало.</p></div>
</div>
<div class="grid g3 stretch">
  <div class="card cream"><h3>Пропустили занятие?</h3><p>Предупредите администратора за 3 часа — и урок можно отработать в другой группе подходящего уровня до конца следующего месяца.</p></div>
  <div class="card cream"><h3>Ребёнок заболел?</h3><p>Можно подключиться к своей группе онлайн. Предупредите за 3 часа, чтобы педагог успел подготовиться.</p></div>
  <div class="card cream"><h3>Каникулы и праздники</h3><p>В школьные каникулы занятия идут в обычном режиме. Работаем по производственному календарю.</p></div>
</div>
<div class="spec" style="grid-template-columns:1fr">
  <div class="it"><div class="k">Утренние, дневные и вечерние группы</div>
  <div class="v">Есть группы для тех, кто учится во вторую смену. Подберём время под ваше расписание — на двух адресах в Долгопрудном.</div></div>
</div>"""
    return slide(d, "Формат обучения", 'Учебный год <span class="hl">с сентября по май</span>', body)


def s_app(d: dict) -> str:
    body = """<div style="display:grid;grid-template-columns:1fr 1fr;gap:4.4mm;flex:1">
  <div class="card purple">
    <div class="kicker">Приложение «Твоя школа»</div>
    <h3>Домашняя работа больше не проблема родителя</h3>
    <ul class="ticks">
      <li><b>Домашнее задание</b> прикреплено к каждому пройденному уроку — не нужно ничего искать и переспрашивать.</li>
      <li><b>Тренировка слов</b> в игровой форме — в нашем мобильном приложении.</li>
      <li><b>Чат с педагогом</b> — можно задать вопрос по заданию в любой момент.</li>
      <li><b>Жизни и монетки</b> за активность на каждом уроке.</li>
      <li><b>Магазин подарков</b>: монетки обмениваются на призы.</li>
      <li><b>Расписание группы</b> и все уведомления в одном месте.</li>
    </ul>
  </div>
  <div class="appcol" style="display:flex;flex-direction:column;gap:3.4mm">
    <div class="card cream"><h3>Чат-бот школы в Max и Telegram</h3><p>Можно загрузить фото страницы школьного учебника и получить объяснение, как выполнить задание — <b>без готовых ответов</b>. Ребёнок разбирается сам, а не списывает.</p></div>
    <div class="card"><h3>Конкурс «Самый активный ученик»</h3><p>Каждый месяц награждаем ученика с наибольшим количеством баллов за тренировку слов. Рейтинг виден в приложении.</p></div>
    <div class="card"><h3>Конкурс «Лучший ученик Фоксинбург»</h3><p>С октября по май: полностью выполненная домашка, пунктуальность, тренировка слов, уважение к группе. Главный приз — до 10 000 ₽ и награждение на сцене.</p></div>
  </div>
</div>"""
    return slide(d, "Цифровая поддержка", 'Чтобы ребёнок занимался <span class="hly">самостоятельно</span>', body)


def s_control(d: dict) -> str:
    body = """<div class="steps">
  <div class="step"><div class="n">1</div><h3>Группа по классу</h3><p>Ребёнок попадает в группу по своему классу и проходит именно те темы, которые идут в школе.</p></div>
  <div class="step"><div class="n">2</div><h3>Ежемесячные тесты</h3><p>Каждый месяц — тестирование по пройденным темам. Дважды в год — отдельно по каждому навыку: чтение, аудирование, письмо, говорение.</p></div>
  <div class="step"><div class="n">3</div><h3>Отчёт родителю</h3><p>Ежемесячный отчёт педагога: письменно, аудиосообщением или по звонку. Вы видите динамику, а не только оценку.</p></div>
  <div class="step"><div class="n">4</div><h3>Финальное тестирование</h3><p>В конце года — итоговый тест и наглядный результат.</p></div>
</div>
<div class="grid g2 stretch">
  <div class="card cream"><h3>Вы всегда знаете, что происходит</h3><p>Расписание и домашние задания — в приложении «Твоя школа». Оперативные вопросы — в чате группы в Max или Telegram. Личные вопросы — администратору напрямую.</p></div>
  <div class="card cream"><h3>Аккредитованный центр Hippo</h3><p>Школа — официальная площадка международной олимпиады по английскому языку Hippo. Ученики могут участвовать и получать международные дипломы.</p></div>
</div>"""
    return slide(d, "Контроль результата", 'Прогресс, который <span class="hl">видно</span>', body)


def s_teachers(d: dict) -> str:
    if TEACHER["photo"]:
        photo = f'<img src="assets/{TEACHER["photo"]}" alt="">'
    else:
        photo = ('<div class="photo-stub"><img src="assets/fox-head-purple.png" alt="">'
                 "<span>Фото педагога</span></div>")
    facts = ticks(TEACHER["facts"])
    body = f"""<div style="display:grid;grid-template-columns:72mm 1fr;gap:6mm;flex:1">
  <div class="teacher solo">{photo}</div>
  <div class="card" style="justify-content:center">
    <div class="kicker">Педагог курса</div>
    <h3 style="font-size:16pt">{TEACHER['name']}</h3>
    <p style="font-size:10.4pt;margin:1.5mm 0 3.5mm;color:var(--purple-soft);font-weight:800">{TEACHER['role']}</p>
    <p style="margin-bottom:4mm">{TEACHER['bio']}</p>
    {facts}
  </div>
</div>
<div class="grid g3 stretch">
  <div class="card cream"><h3>Методист следит за программой</h3><p>Елизавета Коваленко — контроль качества занятий и соответствия программы школьному учебнику.</p></div>
  <div class="card cream"><h3>Видеовизитки педагогов</h3><p>На сайте dymova-english.ru можно посмотреть видеовизитку педагога и фрагмент настоящего урока — до того, как записаться.</p></div>
  <div class="card cream"><h3>Постоянный педагог у группы</h3><p>Группу весь год ведёт один преподаватель: он знает сильные и слабые места каждого ребёнка.</p></div>
</div>"""
    return slide(d, "Педагог", 'Человек, которому вы <span class="hl">доверяете ребёнка</span>', body)


def s_school(d: dict) -> str:
    body = f"""<div class="grid g4">
  <div class="card"><div class="kicker">Официально</div><h3>Образовательная лицензия</h3><p>{SCHOOL['license']}. Статус — действующая.</p></div>
  <div class="card"><div class="kicker">Признание</div><h3>Аккредитованный центр Hippo</h3><p>Официальная площадка престижной международной олимпиады по английскому языку.</p></div>
  <div class="card"><div class="kicker">Два адреса</div><h3>Долгопрудный</h3><p>{SCHOOL['addr_main']}<br>{SCHOOL['addr_alt']}<br>Помещения более 200 м², интерактивные доски.</p></div>
  <div class="card"><div class="kicker">Оплата</div><h3>Принимаем материнский капитал</h3><p>Абонемент на календарный месяц. Оплата в приложении, по QR-коду, на расчётный счёт или наличными.</p></div>
</div>
<div class="grid g3 stretch">
  <div class="card cream"><h3>Праздники и мастер-классы</h3><p>Хеллоуин, новогодние вечеринки, Easter Party, Китайский Новый год, кулинарные и творческие мастер-классы — и на русском, и на английском.</p></div>
  <div class="card cream"><h3>Новогодний Адвент</h3><p>Весь декабрь детей ждут задания от гнома-проказника на английском прямо в начале урока. Входит в стоимость абонемента.</p></div>
  <div class="card cream"><h3>Академия на каникулах</h3><p>В школьные каникулы с 10:00 до 14:00 — квесты, творческие и кулинарные мастер-классы, тематические занятия по английскому.</p></div>
</div>
<div class="spec" style="grid-template-columns:1fr">
  <div class="it"><div class="k">Английский не для школы, а для жизни</div>
  <div class="v">В мае — торжественное завершение учебного года с награждениями, открытыми уроками и финальным тестированием. Ребёнок уходит на каникулы с сертификатом и понятным планом на следующий год.</div></div>
</div>"""
    return slide(d, "О школе", 'Языковая школа <span class="hl">«Фоксинбург»</span>', body)


def s_price(d: dict) -> str:
    body = f"""<div class="price-wrap">
  <div class="price-main">
    <div class="kicker">Стоимость курса Spotlight {d['grade']}</div>
    <div class="old">{PRICE['old']} ₽ / мес</div>
    <div class="now">{PRICE['now']} ₽</div>
    <div class="per">в месяц · 2 занятия в неделю по 60 минут</div>
    <div class="save">Выгода {PRICE['save_month']} ₽ в месяц — {PRICE['save_year']} ₽ за учебный год</div>
    <p class="note">В среднем за учебный год — около {PRICE['per_lesson']} ₽ за занятие. Абонемент действует один календарный месяц, стоимость
    не зависит от количества занятий в нём. Оплата до 1 числа — в приложении, по QR-коду, на расчётный счёт
    или наличными. Принимаем материнский капитал.</p>
  </div>
  <div class="price-side">
    <div class="card yellow"><div class="big">1 125 ₽</div><h3>Пробное занятие</h3><p>Знакомство с методикой и педагогом, подбор группы и расписания, рекомендации по обучению. Длительность — 60 минут.</p></div>
    <div class="card"><h3>Что входит в абонемент</h3>
      <ul class="ticks">
        <li>От 6 до 10 занятий по 60 минут — в зависимости от месяца и государственных праздников</li>
        <li>Приложение «Твоя школа» с домашкой и тренировкой слов</li>
        <li>Ежемесячные тесты и отчёт родителю</li>
        <li>Новогодний Адвент и школьные конкурсы</li>
        <li>Финальное тестирование и сертификат</li>
      </ul>
    </div>
  </div>
</div>"""
    return slide(d, "Стоимость", f'<span class="hly">{PRICE["now"]} ₽ в месяц</span> вместо {PRICE["old"]} ₽', body)


def s_cta(d: dict) -> str:
    body = f"""<div class="cta">
  <div class="cta-col">
    <div class="kicker">Адреса и запись</div>
    <a class="big-link" href="tel:+79939232309">{SCHOOL['phone_main']}</a>
    <p class="addr">{SCHOOL['addr_main']}</p>
    <a class="map-link" href="{LINKS['map_main']}">Открыть на Яндекс.Картах</a>
    <a class="big-link" href="tel:+79167323169">{SCHOOL['phone_alt']}</a>
    <p class="addr">{SCHOOL['addr_alt']}</p>
    <a class="map-link" href="{LINKS['map_alt']}">Открыть на Яндекс.Картах</a>
  </div>
  <div class="cta-col">
    <div class="kicker">Написать нам</div>
    <a class="soc" href="{LINKS['max']}">Max</a>
    <a class="soc" href="{LINKS['telegram']}">Telegram</a>
    <a class="soc" href="{LINKS['whatsapp']}">WhatsApp</a>
    <a class="soc" href="{LINKS['vk']}">ВКонтакте</a>
    <a class="mail" href="mailto:{SCHOOL['email']}">{SCHOOL['email']}</a>
    <p class="hours">{SCHOOL['hours']}</p>
  </div>
  <div class="cta-col">
    <div class="kicker">Сайт школы</div>
    <a class="site-link" href="{LINKS['site']}">{SCHOOL['site']}</a>
    <p class="hours">Расписание групп, видеовизитки педагогов, фрагменты уроков и отзывы родителей.</p>
  </div>
  <div class="cta-foot">
    <span><b>Языковая школа «Фоксинбург»</b> · г. Долгопрудный · {SCHOOL['year']}</span>
    <span>Образовательная лицензия {SCHOOL['license']}</span>
  </div>
</div>"""
    return slide(d, "Ждём вас",
                 f'Запишите ребёнка на <span class="hl">Spotlight {d["grade"]}</span>', body)


# ----------------------------------------------------------------------- сборка
def build_deck(d: dict) -> str:
    slides = [s_cover(d), s_why(d), s_book(d), s_results(d)]
    slides += s_modules(d)
    slides += [s_grammar(d), s_lesson(d), s_format(d), s_app(d), s_control(d),
               s_teachers(d), s_school(d), s_price(d), s_cta(d)]
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Spotlight {d['grade']} · Курс английского для {d['klass']}а — Фоксинбург</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
{chr(10).join(slides)}
</body>
</html>"""


def main() -> None:
    html_only = "--html" in sys.argv
    for d in DECKS:
        name = f"Spotlight-{d['grade']}-kurs-dlya-{d['grade']}-klassa-Foxinburg"
        html_path = ROOT / f"{name}.html"
        html_path.write_text(build_deck(d), encoding="utf-8")
        print(f"HTML  {html_path.name}")
        if html_only:
            continue
        pdf_path = ROOT / f"{name}.pdf"
        subprocess.run(
            [CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
             "--allow-file-access-from-files", "--virtual-time-budget=20000",
             f"--print-to-pdf={pdf_path}", html_path.as_uri()],
            check=True, capture_output=True,
        )
        print(f"PDF   {pdf_path.name}")


if __name__ == "__main__":
    main()
