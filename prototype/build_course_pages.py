#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Обогащение страниц-копий курсов: программа-этапы, блок цены, видео-пример (модалка), FAQ.

Идемпотентно: при повторном запуске сначала вырезает ранее вставленный блок
между маркерами <!--FXB-EXTRA--> ... <!--/FXB-EXTRA--> и доп. CSS/JS/модалку.
"""
import os, re

DIR = os.path.dirname(os.path.abspath(__file__))

CHK = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" '
       'stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>')
PLAY = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/>'
        '<path d="M10 9l5 3-5 3z" fill="currentColor"/></svg>')


def price_card(old, now, per, items, btn="Записаться на курс"):
    lis = "".join("<li>%s%s</li>" % (CHK, x) for x in items)
    old_html = '<span class="fxb-old">%s</span>' % old if old else ""
    return ('<div class="fxb-price-card">%s<div class="fxb-now">%s</div>'
            '<div class="fxb-per">%s</div><ul class="fxb-price-list">%s</ul>'
            '<a class="fxb-btn-main" data-fxb-zayavka role="button" tabindex="0">%s</a></div>'
            % (old_html, now, per, lis, btn))


def faq(items):
    out = []
    for q, a in items:
        out.append('<details class="fxb-q"><summary>%s<span class="fxb-qi"></span></summary>'
                   '<div class="fxb-a"><p>%s</p></div></details>' % (q, a))
    return '<div class="fxb-faq">' + "".join(out) + '</div>'


def steps(items):
    out = []
    for i, (h, p) in enumerate(items, 1):
        out.append('<div class="fxb-step"><span class="fxb-step-n">%d</span>'
                   '<h4>%s</h4><p>%s</p></div>' % (i, h, p))
    return '<div class="fxb-steps">' + "".join(out) + '</div>'


def section(kicker, h2, lead, inner, light=False, sid=""):
    cls = "fxb-section fxb-bg-light" if light else "fxb-section"
    idattr = ' id="%s"' % sid if sid else ""
    lead_html = '<p class="fxb-lead">%s</p>' % lead if lead else ""
    return ('<section class="%s"%s><div class="fxb-wrap"><div class="fxb-head">'
            '<span class="fxb-kicker"><span class="fxb-dot"></span>%s</span>'
            '<h2 class="fxb-h2">%s</h2>%s</div>%s</div></section>'
            % (cls, idattr, kicker, h2, lead_html, inner))


def video_block(label="Посмотреть фрагмент урока", vid="456239500",
                title="Как проходит урок", note="Живая языковая среда без перехода на русский — посмотрите фрагмент занятия в мини-группе."):
    return ('<div class="fxb-video-card"><div class="fxb-video-txt"><b>%s</b><p>%s</p>'
            '<button type="button" class="fxb-video-cta" data-fxb-video="%s">%s%s</button></div>'
            '<div class="fxb-video-deco"><span class="fxb-play-big">%s</span></div></div>'
            % (title, note, vid, PLAY, label, PLAY))


# ---------- per-page content ----------
def reading_sections():
    st = steps([
        ("Звуки и буквы", "Все гласные и согласные звуки английского алфавита и буквосочетания по методике Phonics."),
        ("Слоги и слова", "Складываем звуки в слоги и слова, ставим технику чтения без зубрёжки."),
        ("Предложения", "Читаем простые предложения и набираем до 90% лексики школьного учебника."),
        ("Чтение текстов", "К концу курса ребёнок уверенно читает короткие английские тексты."),
    ])
    forwhom = ('<div class="fxb-fw"><div class="fxb-fw-i">'
               '<b>Идёт во 2 класс</b><p>Хочет научиться читать на английском и подготовиться к школе.</p></div>'
               '<div class="fxb-fw-i"><b>Дети 2–3 классов</b><p>Плохо читает и хочет восполнить пробелы в школьных знаниях.</p></div></div>')
    pc = price_card("16 000 ₽", "12 400 ₽", "за курс • 12 занятий по 60 минут", [
        "1 ступень — подготовка к школьному английскому",
        "3 раза в неделю, длительность 1 месяц",
        "Мини-группы до 7 человек",
        "Старт курса — 1 июня",
        "Бесплатная диагностика и подбор ступени",
    ])
    side = ('<div class="fxb-price-side"><div class="fxb-price-mini"><b>Бесплатная диагностика</b>'
            '<p>Если ребёнок уже учил английский, но не научился читать — проверим уровень и подберём ступень.</p></div>'
            + video_block() + '</div>')
    fq = faq([
        ("Как вы обучаете чтению?", "По методике Phonics, одобренной Британским советом: ребёнок изучает звуки и алфавит в лёгкой форме, и на знании звуков строится умение читать и писать — без зубрёжки и транскрипции."),
        ("По какой программе вы идёте?", "Учебники издательств Cambridge и Oxford (Kid's Box, Super Minds, Prepare), дополненные авторскими наработками, играми и пособиями."),
        ("Сколько раз в неделю проходят занятия?", "На курсе чтения — 3 раза в неделю по 60 минут, длительность курса 1 месяц (12 уроков). Расписание подберём под вас."),
        ("Ребёнок не знает букв — справится?", "Да. Формат English Only — это система: каждая фраза даётся плавно, с карточками, жестами и пособиями. Педагог бережно погружает в язык, как ребёнок осваивает родной."),
        ("Как я пойму, что появился результат?", "Еженедельные видео с уроков, ежемесячные отчёты о темах и успехах, открытые уроки и тестирования. Педагог всегда на связи."),
    ])
    return [
        section("Программа", "Как идёт обучение",
                "За 4 недели — путь от звуков до чтения текстов. Перед стартом проводим бесплатную диагностику и подбираем ступень.",
                st + forwhom, light=True, sid="fxb-program-steps"),
        section("Стоимость", "Цена курса", "", '<div class="fxb-price">' + pc + side + '</div>'),
        section("Вопрос-ответ", "Частые вопросы", "", fq, light=True),
    ]


def grammar_sections():
    st = steps([
        ("9–11 лет", "Программа 2–4 класса: базовые грамматические конструкции, в которых школьники путаются чаще всего, разбор заданий из учебников начальной школы."),
        ("12–15 лет", "Разбор грамматики по школьной программе соответственно возрасту — времена, правила и их применение в речи."),
        ("16–17 лет", "Интенсивный курс грамматики для дальнейшей подготовки к экзаменам (ОГЭ/ЕГЭ)."),
    ])
    forwhom = ('<div class="fxb-fw"><div class="fxb-fw-i"><b>Кому подойдёт</b>'
               '<p>Детям 3–8 классов, которые путаются во временах, не понимают правил и не могут их применить.</p></div>'
               '<div class="fxb-fw-i"><b>Пособия</b><p>Опираемся на Spotlight (школьная программа); для средней школы — основы подготовки к ЕГЭ.</p></div></div>')
    pc = price_card("18 000 ₽", "16 000 ₽", "за курс • 12 занятий по 90 минут", [
        "Программа по возрасту: 3–4, 5–6, 7–8 классы",
        "Закрываем пробелы и готовим к учебному году",
        "Мини-группы до 7 человек",
        "Персональный трекер обучения от методиста",
        "Бесплатная диагностика уровня",
    ])
    side = ('<div class="fxb-price-side"><div class="fxb-price-mini"><b>Бесплатная диагностика</b>'
            '<p>Методист задаёт вопросы 3 уровней сложности и сразу показывает, где у ребёнка пробелы и какая группа подойдёт.</p></div>'
            + video_block() + '</div>')
    fq = faq([
        ("Какая программа у курса грамматики?", "Разбиваем по возрасту: 9–11 лет — программа 2–4 класса; 12–15 лет — грамматика по школьной программе; 16–17 лет — интенсив для подготовки к экзаменам."),
        ("По каким пособиям занимаетесь?", "Для младших школьников — Spotlight (школьная программа), для средней школы — основы подготовки к ЕГЭ плюс школьная программа."),
        ("Сколько длятся занятия?", "Курс грамматики — 12 занятий по 90 минут. Точное расписание подберём после диагностики."),
        ("А программа совпадает со школьной? Ребёнок не запутается?", "Темы пересекаются со школьными, но мы идём глубже и развиваем все аспекты языка. Наши ученики часто среди лучших в классе и не боятся отвечать у доски."),
        ("Как я пойму, что появился результат?", "Видео с уроков, ежемесячные отчёты, открытые уроки и тестирования. Ребёнок получает персональный трекер с комментариями методиста."),
    ])
    return [
        section("Программа", "Что разберём на курсе",
                "Закрываем пробелы по грамматике и готовимся к учебному году. Перед стартом — бесплатная диагностика уровня.",
                st + forwhom, light=True, sid="fxb-program-steps"),
        section("Стоимость", "Цена курса", "", '<div class="fxb-price">' + pc + side + '</div>'),
        section("Вопрос-ответ", "Частые вопросы", "", fq, light=True),
    ]


def preparation_sections():
    st = steps([
        ("Диагностика", "Определяем готовность ребёнка и подбираем формат под возраст (4–5 или 6–7 лет)."),
        ("Речь и лексика", "Учимся говорить и понимать на английском в игровой форме, набираем базовую лексику."),
        ("Чтение и письмо", "Знакомимся со звуками и буквами, готовим руку и внимание к школьным занятиям."),
        ("Уверенный старт", "Ребёнок приходит в школу подготовленным и без страха перед английским."),
    ])
    forwhom = ('<div class="fxb-fw"><div class="fxb-fw-i"><b>Дети 4–5 и 6–7 лет</b>'
               '<p>Готовим к школе через игру: говорение, развитие памяти, логики и кругозора.</p></div>'
               '<div class="fxb-fw-i"><b>Мягкое погружение</b><p>Формат English Only — системно, с карточками, жестами и пособиями, без стресса.</p></div></div>')
    pc = price_card("", "5 600 ₽<span class=\"fxb-now-per\">/мес</span>", "2 раза в неделю по 60 минут", [
        "Для детей 4–5 и 6–7 лет",
        "Подготовка к школьному английскому",
        "Мини-группы до 7 человек",
        "Игровая методика, авторские пособия",
        "Бесплатная комплексная диагностика",
    ])
    side = ('<div class="fxb-price-side"><div class="fxb-price-mini"><b>Бесплатная диагностика</b>'
            '<p>Познакомимся с ребёнком, определим уровень и подберём подходящую группу.</p></div>'
            + video_block() + '</div>')
    fq = faq([
        ("Я не уверена, понравится ли ребёнку?", "Каждый ребёнок индивидуален — мы ориентируемся на личность и творчески подходим к урокам. Приходите на пробное занятие и оцените сами."),
        ("Ребёнок не знает букв — как он будет заниматься на английском?", "Формат English Only — это не хаос, а система: каждая фраза даётся плавно, с карточками, жестами и пособиями. Педагог бережно погружает в язык, как мама учит ребёнка родной речи."),
        ("Как проходят занятия?", "С учётом возраста и уровня: педагог вводит новое, дети отрабатывают с поддержкой, а в конце показывают результат в увлекательных заданиях. Мы влюбляем детей в английский."),
        ("Сколько раз в неделю проходят занятия?", "Подготовка к школе — 2 раза в неделю по 60 минут. Удобное время подберём под вашу семью."),
        ("Как я пойму, что появился результат?", "Видео с уроков, ежемесячные отчёты о темах и успехах, открытые уроки. Педагог лично ответит на любой вопрос о прогрессе ребёнка."),
    ])
    return [
        section("Программа", "Как готовим к школе",
                "Мягко и в игре — от первых слов до уверенного старта в школе. Перед началом проводим бесплатную диагностику.",
                st + forwhom, light=True, sid="fxb-program-steps"),
        section("Стоимость", "Цена курса", "", '<div class="fxb-price">' + pc + side + '</div>'),
        section("Вопрос-ответ", "Частые вопросы", "", fq, light=True),
    ]


CSS_ADD = """
/* ===== FXB-EXTRA: programme / price / video / faq / modal ===== */
#fxb-page .fxb-steps{display:grid;grid-template-columns:repeat(4,1fr);gap:18px}
#fxb-page .fxb-step{position:relative;background:#fff;border:1px solid rgba(57,40,82,.08);border-radius:20px;padding:28px 22px 24px;box-shadow:0 14px 32px -22px rgba(57,40,82,.4);opacity:0;transform:translateY(28px)}
#fxb-page .fxb-step.fxb-in{opacity:1;transform:none}
#fxb-page .fxb-step-n{display:grid;place-items:center;width:40px;height:40px;border-radius:12px;background:linear-gradient(135deg,var(--purple-2),var(--purple-3));color:#fff;font-weight:900;font-size:17px;margin-bottom:14px;box-shadow:0 10px 20px -10px rgba(102,45,146,.7)}
#fxb-page .fxb-step h4{font-size:16px;font-weight:800;margin-bottom:7px;line-height:1.25}
#fxb-page .fxb-step p{color:var(--muted);font-size:13.5px;font-weight:500;line-height:1.5}
#fxb-page .fxb-fw{display:grid;grid-template-columns:repeat(2,1fr);gap:18px;margin-top:22px}
#fxb-page .fxb-fw-i{background:rgba(102,45,146,.05);border:1px solid rgba(102,45,146,.1);border-radius:18px;padding:22px 24px}
#fxb-page .fxb-fw-i b{display:block;font-size:16px;font-weight:800;margin-bottom:6px;color:var(--purple-2)}
#fxb-page .fxb-fw-i p{color:var(--muted);font-size:14px;font-weight:500;line-height:1.5}

#fxb-page .fxb-price{display:grid;grid-template-columns:1.15fr .85fr;gap:24px;align-items:stretch}
#fxb-page .fxb-price-card{background:linear-gradient(135deg,#2e1a47,#662d92);color:#fff;border-radius:26px;padding:34px 32px;box-shadow:0 26px 54px -26px rgba(102,45,146,.7)}
#fxb-page .fxb-old{font-size:17px;opacity:.55;text-decoration:line-through;font-weight:700}
#fxb-page .fxb-now{font-size:clamp(38px,5vw,52px);font-weight:900;line-height:1;letter-spacing:-.02em;margin:2px 0 4px}
#fxb-page .fxb-now-per{font-size:20px;font-weight:700;opacity:.7;letter-spacing:0}
#fxb-page .fxb-per{font-size:14px;opacity:.82;font-weight:600;margin-bottom:24px}
#fxb-page .fxb-price-list{list-style:none;display:grid;gap:13px;margin:0 0 28px;padding:0}
#fxb-page .fxb-price-list li{display:flex;gap:11px;align-items:flex-start;font-size:14.5px;font-weight:600;line-height:1.4}
#fxb-page .fxb-price-list svg{width:20px;height:20px;stroke:var(--yellow);flex:0 0 auto;margin-top:1px}
#fxb-page .fxb-price-card .fxb-btn-main{width:100%;justify-content:center}
#fxb-page .fxb-price-side{display:flex;flex-direction:column;gap:18px}
#fxb-page .fxb-price-mini{background:#fff;border:1px solid rgba(57,40,82,.08);border-radius:20px;padding:24px;box-shadow:0 14px 30px -22px rgba(57,40,82,.4)}
#fxb-page .fxb-price-mini b{display:block;font-size:16px;font-weight:800;margin-bottom:7px;color:var(--purple-2)}
#fxb-page .fxb-price-mini p{color:var(--muted);font-size:13.5px;font-weight:500;line-height:1.5}

#fxb-page .fxb-video-card{display:flex;align-items:center;gap:18px;background:linear-gradient(135deg,var(--orange),#f5a06f);color:#fff;border-radius:20px;padding:22px 24px;box-shadow:0 16px 34px -20px rgba(238,115,73,.7);overflow:hidden}
#fxb-page .fxb-video-txt{flex:1}
#fxb-page .fxb-video-txt b{display:block;font-size:16px;font-weight:800;margin-bottom:5px}
#fxb-page .fxb-video-txt p{font-size:13px;font-weight:500;opacity:.92;line-height:1.45;margin-bottom:14px}
#fxb-page .fxb-video-cta{display:inline-flex;align-items:center;gap:8px;padding:11px 20px;border-radius:100px;border:0;cursor:pointer;background:#fff;color:var(--orange);font-family:inherit;font-weight:800;font-size:13.5px;transition:transform .25s}
#fxb-page .fxb-video-cta svg{width:18px;height:18px}
#fxb-page .fxb-video-cta:hover{transform:translateY(-2px)}
#fxb-page .fxb-video-deco{flex:0 0 auto}
#fxb-page .fxb-play-big{display:grid;place-items:center;width:56px;height:56px;border-radius:50%;background:rgba(255,255,255,.18)}
#fxb-page .fxb-play-big svg{width:28px;height:28px;stroke:#fff}
@media(max-width:520px){#fxb-page .fxb-video-deco{display:none}}

#fxb-page .fxb-faq{max-width:820px;margin:0 auto;display:grid;gap:12px}
#fxb-page .fxb-q{background:#fff;border:1px solid rgba(57,40,82,.09);border-radius:16px;padding:0 22px;box-shadow:0 10px 24px -20px rgba(57,40,82,.35)}
#fxb-page .fxb-q summary{list-style:none;cursor:pointer;display:flex;align-items:center;justify-content:space-between;gap:14px;padding:19px 0;font-weight:700;font-size:15.5px;line-height:1.35}
#fxb-page .fxb-q summary::-webkit-details-marker{display:none}
#fxb-page .fxb-qi{position:relative;flex:0 0 auto;width:20px;height:20px}
#fxb-page .fxb-qi::before,#fxb-page .fxb-qi::after{content:"";position:absolute;background:var(--purple-2);border-radius:2px;transition:transform .3s}
#fxb-page .fxb-qi::before{top:9px;left:2px;width:16px;height:2.4px}
#fxb-page .fxb-qi::after{left:9px;top:2px;width:2.4px;height:16px}
#fxb-page .fxb-q[open] .fxb-qi::after{transform:rotate(90deg);opacity:0}
#fxb-page .fxb-a{padding:0 0 20px}
#fxb-page .fxb-a p{color:var(--muted);font-size:14px;font-weight:500;line-height:1.6}

#fxb-page .fxb-modal{position:fixed;inset:0;z-index:99999;display:flex;align-items:center;justify-content:center;padding:20px}
#fxb-page .fxb-modal[hidden]{display:none}
#fxb-page .fxb-modal__ov{position:absolute;inset:0;background:rgba(20,12,36,.72);backdrop-filter:blur(4px)}
#fxb-page .fxb-modal__box{position:relative;z-index:1;width:min(900px,100%);background:#fff;border-radius:20px;padding:14px 14px 10px;box-shadow:0 40px 90px -30px rgba(0,0,0,.6);animation:fxbpop .3s ease}
@keyframes fxbpop{from{opacity:0;transform:translateY(16px) scale(.98)}to{opacity:1;transform:none}}
#fxb-page .fxb-modal__x{position:absolute;top:-16px;right:-16px;width:42px;height:42px;border-radius:50%;border:0;cursor:pointer;background:#fff;color:var(--ink);display:grid;place-items:center;box-shadow:0 10px 24px -8px rgba(0,0,0,.4)}
#fxb-page .fxb-modal__x svg{width:20px;height:20px;stroke:currentColor;stroke-width:2.2}
#fxb-page .fxb-vwrap{position:relative;width:100%;padding-top:56.25%;border-radius:12px;overflow:hidden;background:#000}
#fxb-page .fxb-vwrap iframe{position:absolute;inset:0;width:100%;height:100%;border:0}
#fxb-page .fxb-vfall{display:block;text-align:center;font-size:12.5px;font-weight:600;color:var(--purple-2);padding:9px 0 4px}
@media(max-width:860px){#fxb-page .fxb-steps{grid-template-columns:repeat(2,1fr)}#fxb-page .fxb-price{grid-template-columns:1fr}}
@media(max-width:520px){#fxb-page .fxb-steps,#fxb-page .fxb-fw{grid-template-columns:1fr}}
"""

MODAL_HTML = ('<div class="fxb-modal" id="fxb-vid-modal" hidden>'
              '<div class="fxb-modal__ov" data-fxb-close></div>'
              '<div class="fxb-modal__box" role="dialog" aria-modal="true">'
              '<button type="button" class="fxb-modal__x" data-fxb-close aria-label="Закрыть">'
              '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>'
              '</button><div class="fxb-modal__body"></div></div></div>')

JS_ADD = """
  var fxbModal=root.querySelector('#fxb-vid-modal');
  if(fxbModal){
    var fxbBody=fxbModal.querySelector('.fxb-modal__body');
    var fxbVid=function(id){var u='https://vk.com/video_ext.php?oid=-191733680&id='+id+'&hd=2&autoplay=1';
      return '<div class="fxb-vwrap"><iframe src="'+u+'" allow="autoplay; encrypted-media; fullscreen; picture-in-picture" allowfullscreen></iframe></div>'
        +'<a class="fxb-vfall" target="_blank" rel="noopener" href="https://vk.com/video-191733680_'+id+'">Видео не открылось? Смотреть во ВКонтакте</a>';};
    var fxbOpen=function(h){fxbBody.innerHTML=h;fxbModal.hidden=false;document.body.style.overflow='hidden';};
    var fxbClose=function(){fxbModal.hidden=true;fxbBody.innerHTML='';document.body.style.overflow='';};
    root.addEventListener('click',function(e){var t=e.target.closest('[data-fxb-video],[data-fxb-close]');if(!t)return;
      if(t.hasAttribute('data-fxb-video')){e.preventDefault();fxbOpen(fxbVid(t.getAttribute('data-fxb-video')));}
      else if(t.hasAttribute('data-fxb-close')){fxbClose();}});
    document.addEventListener('keydown',function(e){if(e.key==='Escape'&&!fxbModal.hidden)fxbClose();});
  }
"""

def letnyaya_sections():
    pc = price_card("", "46 000 ₽", "за смену • 10 рабочих дней", [
        "Полный день 10:00–18:00",
        "Тематические недели и творческие проекты на английском",
        "Мини-группы до 8 человек по возрасту и уровню",
        "Игры, практика и отдых в языковой среде",
        "Бесплатная диагностика и подбор смены",
    ], btn="Забронировать место")
    side = ('<div class="fxb-price-side"><div class="fxb-price-mini"><b>Места ограничены</b>'
            '<p>Бронируйте смену заранее: группы формируем по возрасту и уровню, мест немного.</p></div>'
            + video_block(title="Как проходит день", note="Полное погружение, проекты и живое общение — посмотрите, как идёт день в Академии.") + '</div>')
    fq = faq([
        ("Сколько длится смена и какой режим дня?", "Смена — 10 рабочих дней, полный день с 10:00 до 18:00. День насыщенный: занятия, тематические проекты, игры и отдых — всё в языковой среде."),
        ("Сколько стоит участие?", "46 000 ₽ за смену (10 рабочих дней, 10:00–18:00). Перед стартом проводим бесплатную диагностику и подбираем подходящую группу."),
        ("Для какого возраста и уровня?", "Группы формируем по возрасту и уровню, до 8 человек. Подойдёт и тем, кто только начинает, и тем, кто хочет не потерять форму за лето."),
        ("Что входит в программу?", "Тематические недели (путешествия, профессии, природа, технологии), творческие проекты, презентации и мини-спектакли — язык применяется в реальных задачах."),
    ])
    return [
        section("Стоимость", "Цена смены", "", '<div class="fxb-price">' + pc + side + '</div>'),
        section("Вопрос-ответ", "Частые вопросы", "", fq, light=True),
    ]


PAGES = {
    "page_reading.html": reading_sections,
    "page_grammar.html": grammar_sections,
    "page_preparation.html": preparation_sections,
    "page_letnyaya_akademiya.html": letnyaya_sections,
}

# Название курса для текста заявки (подставляется в сообщение WhatsApp).
COURSES = {
    "page_reading.html": "Курс по чтению",
    "page_grammar.html": "Курс по грамматике",
    "page_preparation.html": "Подготовка к школе",
    "page_letnyaya_akademiya.html": "Летняя Академия",
}

WA_PHONE = "79939232309"        # WhatsApp + звонок
MAX_BOT = "https://max.ru/id611904726658_bot"
FORMS_JS_TAG = '<script src="https://static.tildacdn.com/js/tilda-forms-1.0.min.js" async></script>'

SEND_ICON = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
             'stroke-linecap="round" stroke-linejoin="round"><path d="M22 2 11 13"/>'
             '<path d="M22 2 15 22l-4-9-9-4z"/></svg>')
OK_ICON = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" '
           'stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>')


def _zalts():
    return ('<div class="fxb-zalt-btns">'
            '<a class="fxb-zchip" target="_blank" rel="noopener" href="%s">Max</a>'
            '<a class="fxb-zchip" href="tel:+%s">Позвонить</a>'
            '</div>' % (MAX_BOT, WA_PHONE))


def zayavka_modal(course):
    return ('<div class="fxb-modal fxb-zmodal" id="fxb-zayavka-modal" hidden data-fxb-course="%s">'
            '<div class="fxb-modal__ov" data-fxb-close></div>'
            '<div class="fxb-modal__box fxb-zbox" role="dialog" aria-modal="true" aria-label="Заявка на курс">'
            '<button type="button" class="fxb-modal__x" data-fxb-close aria-label="Закрыть">'
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>'
            '</button>'
            '<div class="fxb-zview fxb-zview--form">'
            '<h3 class="fxb-ztitle">Оставить заявку</h3>'
            '<p class="fxb-zsub">Оставьте имя и телефон — перезвоним, расскажем расписание и подберём группу под уровень ребёнка.</p>'
            '<form class="fxb-zform js-form-proccess" id="fxbZform" name="fxbZform" role="form" method="POST" data-formactiontype="2" data-inputbox=".fxb-zfield" data-success-callback="fxbZSuccess">'
            '<input type="hidden" name="formservices[]" value="aa53a2a49933944f1fb9c3aaf4590622" class="js-formaction-services">'
            '<input type="hidden" name="formservices[]" value="30ef9df34728007db12c86a2e7cf58b6" class="js-formaction-services">'
            '<input type="hidden" name="formservices[]" value="b7967c40cba6f8680cc7a33c7d4a3bd1" class="js-formaction-services">'
            '<input type="hidden" name="formservices[]" value="406ce69659f99227298278ae7b0939c9" class="js-formaction-services">'
            '<input type="hidden" name="formservices[]" value="111d799a5db07bce252609cabd29b3e0" class="js-formaction-services">'
            '<input type="hidden" name="formservices[]" value="7c1b855d6fc4254f9b2a189ae11b7360" class="js-formaction-services">'
            '<input type="hidden" name="tildaspec-formname" value="Заявка — %s">'
            '<input type="hidden" name="Курс" value="%s">'
            '<label class="fxb-zfield"><span>Ваше имя</span><input type="text" name="Name" class="js-tilda-rule" data-tilda-req="1" data-tilda-rule="name" aria-required="true" autocomplete="name" placeholder="Как к вам обращаться"></label>'
            '<label class="fxb-zfield"><span>Телефон</span><input type="tel" name="Phone" class="js-tilda-rule" data-tilda-req="1" data-tilda-rule="phone" aria-required="true" autocomplete="tel" inputmode="tel" placeholder="+7 (___) ___-__-__"></label>'
            '<button type="submit" class="fxb-btn-main fxb-zsubmit">%sОтправить заявку</button>'
            '<p class="fxb-znote">Нажимая кнопку, вы соглашаетесь с <a href="/policy" target="_blank" rel="noopener">политикой конфиденциальности</a>.</p>'
            '<div class="js-errorbox-all" style="display:none"><div class="t-form__errorbox-text js-rule-error js-rule-error-all" style="color:#e0526a;font-size:13px;font-weight:600;margin-top:6px"></div></div>'
            '</form>'
            '<div class="fxb-zalt"><span class="fxb-zalt-l">Или свяжитесь напрямую</span>%s</div>'
            '</div>'
            '<div class="fxb-zview fxb-zview--thanks" hidden>'
            '<div class="fxb-zok">%s</div>'
            '<h3 class="fxb-ztitle">Заявка сформирована!</h3>'
            '<p class="fxb-zsub">Спасибо! Заявка отправлена — мы свяжемся с вами. Можно также написать нам:</p>'
            '%s'
            '</div></div></div>'
            % (course, course, SEND_ICON, _zalts(), OK_ICON, _zalts()))


ZAYAVKA_CSS = """
/* ===== FXB-ZAYAVKA: попап-форма заявки ===== */
#fxb-page [data-fxb-zayavka]{cursor:pointer}
#fxb-page .fxb-zbox{width:min(460px,100%);padding:34px 30px 30px;text-align:left}
#fxb-page .fxb-ztitle{font-size:22px;font-weight:900;letter-spacing:-.01em;margin-bottom:8px;color:var(--ink)}
#fxb-page .fxb-zsub{font-size:14px;font-weight:500;color:var(--muted);line-height:1.55;margin-bottom:22px}
#fxb-page .fxb-zform{display:grid;gap:14px}
#fxb-page .fxb-zfield{display:grid;gap:6px}
#fxb-page .fxb-zfield span{font-size:12.5px;font-weight:700;color:var(--purple-2);letter-spacing:.02em}
#fxb-page .fxb-zfield input{font-family:inherit;font-size:15px;font-weight:500;color:var(--ink);padding:13px 16px;border:1.6px solid rgba(57,40,82,.14);border-radius:13px;background:#faf8fe;transition:border-color .2s,box-shadow .2s;width:100%}
#fxb-page .fxb-zfield input:focus{outline:0;border-color:var(--purple-2);box-shadow:0 0 0 3px rgba(102,45,146,.12)}
#fxb-page .fxb-zfield.fxb-zerr input{border-color:#e0526a;background:#fdf2f4}
#fxb-page .fxb-zsubmit{width:100%;justify-content:center;margin-top:4px;border:0;cursor:pointer;font-family:inherit}
#fxb-page .fxb-zsubmit svg{width:18px;height:18px;stroke:var(--purple)}
#fxb-page .fxb-znote{font-size:11px;color:#a89fbd;font-weight:500;line-height:1.45;margin-top:2px;text-align:center}
#fxb-page .fxb-znote a{color:var(--purple-2);text-decoration:underline}
#fxb-page .fxb-zalt{margin-top:22px;padding-top:20px;border-top:1px solid rgba(57,40,82,.1)}
#fxb-page .fxb-zalt-l{display:block;text-align:center;font-size:11.5px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;margin-bottom:14px}
#fxb-page .fxb-zalt-btns{display:flex;gap:10px;justify-content:center;flex-wrap:wrap}
#fxb-page .fxb-zchip{display:inline-flex;align-items:center;gap:7px;padding:11px 18px;border-radius:100px;font-weight:800;font-size:13.5px;border:1.6px solid rgba(102,45,146,.2);color:var(--purple-2);background:#fff;transition:transform .2s,border-color .2s,background .2s;cursor:pointer}
#fxb-page .fxb-zchip:hover{transform:translateY(-2px);border-color:var(--purple-2);background:rgba(102,45,146,.05)}
#fxb-page .fxb-zchip--wa{border-color:rgba(43,182,115,.45);color:#1f9d63}
#fxb-page .fxb-zchip--wa:hover{border-color:#1f9d63;background:rgba(43,182,115,.07)}
#fxb-page .fxb-zview--thanks{text-align:center}
#fxb-page .fxb-zok{width:64px;height:64px;border-radius:50%;margin:0 auto 16px;display:grid;place-items:center;background:linear-gradient(135deg,#2bb673,#7ed957);box-shadow:0 14px 30px -12px rgba(43,182,115,.7)}
#fxb-page .fxb-zok svg{width:32px;height:32px;stroke:#fff;stroke-width:2.6}
#fxb-page .fxb-zview--thanks .fxb-zalt-btns{margin-top:20px}
"""

ZAYAVKA_JS = """
  var fxbZ=root.querySelector('#fxb-zayavka-modal');
  if(fxbZ){
    var fxbZvForm=fxbZ.querySelector('.fxb-zview--form');
    var fxbZvThx=fxbZ.querySelector('.fxb-zview--thanks');
    var fxbZopen=function(){fxbZvForm.hidden=false;fxbZvThx.hidden=true;fxbZ.hidden=false;document.body.style.overflow='hidden';};
    var fxbZclose=function(){fxbZ.hidden=true;document.body.style.overflow='';};
    root.addEventListener('click',function(e){
      var z=e.target.closest('[data-fxb-zayavka]');if(z){e.preventDefault();fxbZopen();return;}
      var c=e.target.closest('[data-fxb-close]');if(c&&!fxbZ.hidden){fxbZclose();}});
    root.addEventListener('keydown',function(e){var z=e.target.closest('[data-fxb-zayavka]');
      if(z&&(e.key==='Enter'||e.key===' ')){e.preventDefault();fxbZopen();}});
    document.addEventListener('keydown',function(e){if(e.key==='Escape'&&!fxbZ.hidden)fxbZclose();});
  }
  window.fxbZSuccess=function(){var m=document.getElementById('fxb-zayavka-modal');if(!m)return;var vf=m.querySelector('.fxb-zview--form');var vt=m.querySelector('.fxb-zview--thanks');if(vf)vf.hidden=true;if(vt)vt.hidden=false;};
"""


def add_zayavka(fname, course):
    path = os.path.join(DIR, fname)
    s = open(path, encoding="utf-8").read()
    if 'id="fxb-zayavka-modal"' in s:
        print("skip zayavka (уже есть):", fname)
        return
    # 1) кнопки заявки: #popup:diagnostika -> попап-форма
    s = s.replace('href="#popup:diagnostika"', 'data-fxb-zayavka role="button" tabindex="0"')
    # 2) модалка рядом с видео-модалкой
    anchor = '</div>\n\n<style>'
    assert s.count(anchor) == 1, fname + " zayavka modal anchor"
    s = s.replace(anchor, zayavka_modal(course) + "\n</div>\n\n<style>", 1)
    # 3) CSS перед </style>
    assert s.count('</style>') == 1, fname + " zayavka style anchor"
    s = s.replace('</style>', ZAYAVKA_CSS + "\n</style>", 1)
    # 4) JS перед })();
    assert s.count('})();') == 1, fname + " zayavka js anchor"
    s = s.replace('})();\n</script>', ZAYAVKA_JS + '})();\n</script>\n' + FORMS_JS_TAG, 1)
    open(path, "w", encoding="utf-8").write(s)
    print("OK zayavka", fname, "->", len(s), "chars")


def strip_old(s):
    s = re.sub(r'<!--FXB-EXTRA-->[\s\S]*?<!--/FXB-EXTRA-->', '', s)
    s = re.sub(r'\n/\* ===== FXB-EXTRA.*?(?=\n@media\(max-width:860px\)\{#fxb-page \.fxb-facts)', '', s, flags=re.S)
    return s


def build(fname, secfn):
    path = os.path.join(DIR, fname)
    s = open(path, encoding="utf-8").read()
    if "<!--FXB-EXTRA-->" in s:
        print("skip (уже собрано):", fname)
        return
    secs = "<!--FXB-EXTRA-->" + "".join(secfn()) + "<!--/FXB-EXTRA-->"
    # 1) sections before CTA
    anchor = '<section class="fxb-cta"'
    assert s.count(anchor) == 1, fname + " CTA anchor"
    s = s.replace(anchor, secs + "\n" + anchor, 1)
    # 2) modal before closing #fxb-page </div>
    anchor2 = '</div>\n\n<style>'
    assert s.count(anchor2) == 1, fname + " modal anchor"
    s = s.replace(anchor2, MODAL_HTML + "\n</div>\n\n<style>", 1)
    # 3) css before </style>
    assert s.count('</style>') == 1, fname + " style anchor"
    s = s.replace('</style>', CSS_ADD + "\n</style>", 1)
    # 4) js before })(); of IIFE
    assert s.count('})();') == 1, fname + " js anchor"
    s = s.replace('})();\n</script>', JS_ADD + '})();\n</script>\n' + FORMS_JS_TAG, 1)
    open(path, "w", encoding="utf-8").write(s)
    print("OK", fname, "->", len(s), "chars")


if __name__ == "__main__":
    for fn, secfn in PAGES.items():
        build(fn, secfn)
    for fn in PAGES:
        add_zayavka(fn, COURSES[fn])
