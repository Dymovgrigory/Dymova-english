#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генератор контент-блоков доп. страниц Фоксинбург в едином фирменном стиле.

Каждая доп. страница на Tilda состоит из 3 блоков «HTML-код» (T123):
  1) tilda_shapka.html  — общая шапка/меню (одинаковая на всех страницах)
  2) <этот блок>         — контент, релевантный конкретной странице
  3) tilda_footer.html  — общий подвал

Здесь генерируется только блок (2) для каждой страницы: фирменный стиль,
бренд-иконки (SVG) вместо emoji, аккуратные брендовые акценты, scroll-reveal.

Запуск:  python3 build_subpages.py
"""
import os
from build_course_pages import zayavka_unit

OUT = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- SVG иконки
# Линейные иконки в фирменном стиле (stroke, без заливки), как в блоке преимуществ.
ICONS = {
    "puzzle": '<path d="M9 3h6v3a2 2 0 0 0 4 0V3"/><path d="M21 9h-3a2 2 0 0 0 0 4h3v8H3V3"/>',
    "game":  '<rect x="3" y="7" width="18" height="11" rx="4"/><path d="M8 11v3M6.5 12.5h3"/><circle cx="16" cy="11.5" r=".6"/><circle cx="18" cy="13.5" r=".6"/>',
    "group": '<circle cx="9" cy="7" r="3"/><circle cx="17" cy="9" r="2.4"/><path d="M3 20v-1a5 5 0 0 1 10 0v1"/><path d="M15.5 20v-.5a4 4 0 0 1 5.5-3.7"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "chart": '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    "book":  '<path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z"/><path d="M19 19H6a2 2 0 0 0-2 2"/>',
    "pencil":'<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
    "chat":  '<path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8z"/>',
    "trophy":'<path d="M8 4h8v5a4 4 0 0 1-8 0z"/><path d="M8 5H5v2a3 3 0 0 0 3 3M16 5h3v2a3 3 0 0 1-3 3M9 20h6M12 13v4"/>',
    "rocket":'<path d="M5 15c-1 1-1.5 4-1.5 4s3-.5 4-1.5"/><path d="M9 11a9 9 0 0 1 9-9 9 9 0 0 1-9 9z"/><path d="M9 11l4 4c3-1 5-4 5-9"/><circle cx="14.5" cy="6.5" r="1.2"/>',
    "monitor":'<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
    "headset":'<path d="M4 13v-1a8 8 0 0 1 16 0v1"/><rect x="2.5" y="13" width="4" height="6" rx="1.5"/><rect x="17.5" y="13" width="4" height="6" rx="1.5"/><path d="M20 19a4 4 0 0 1-4 3h-2"/>',
    "sun":   '<circle cx="12" cy="12" r="4"/><path d="M12 2v3M12 19v3M4.9 4.9l2.1 2.1M16.9 16.9l2.1 2.1M2 12h3M19 12h3M4.9 19.1l2.1-2.1M16.9 7.1l2.1-2.1"/>',
    "calendar":'<rect x="3" y="4" width="18" height="17" rx="2"/><path d="M3 9h18M8 2v4M16 2v4"/>',
    "target":'<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.3"/>',
    "star":  '<path d="M12 3l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 17l-5.2 2.8 1-5.8L3.5 9.2l5.9-.9z"/>',
    "check": '<circle cx="12" cy="12" r="9"/><path d="M8.5 12.5l2.4 2.4 4.6-5"/>',
    "cap":   '<path d="M3 9l9-4 9 4-9 4z"/><path d="M7 11v4c0 1.5 2.5 3 5 3s5-1.5 5-3v-4"/>',
    "music": '<path d="M9 18V6l10-2v12"/><circle cx="6" cy="18" r="3"/><circle cx="16" cy="16" r="3"/>',
    "palette":'<path d="M12 3a9 9 0 1 0 0 18c1 0 1.5-.8 1.5-1.5 0-.4-.2-.8-.5-1.1-.3-.3-.5-.7-.5-1.1 0-.8.7-1.3 1.5-1.3H16a5 5 0 0 0 5-5c0-4.4-4-8-9-8z"/><circle cx="7.5" cy="11.5" r="1"/><circle cx="12" cy="8" r="1"/><circle cx="16.5" cy="11.5" r="1"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18A14 14 0 0 1 12 3z"/>',
    "shield":'<path d="M12 2l7 4v6c0 5-3.5 8-7 10-3.5-2-7-5-7-10V6z"/><path d="M9 12l2 2 4-4"/>',
    "mic":   '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
    "compass":'<circle cx="12" cy="12" r="9"/><path d="M16 8l-2 6-6 2 2-6z"/>',
}

def svg(name):
    return ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">'
            + ICONS[name] + '</svg>')

# ---------------------------------------------------------------- общий CSS
CSS = """
<style>
#fxb-page{--purple:#392852;--purple-2:#662d92;--purple-3:#6237a2;--orange:#ee7349;--yellow:#fcf951;--ink:#241a36;--muted:#6f6883;--bg:#f4f1fa;
  font-family:'Montserrat',Arial,sans-serif;color:var(--ink);-webkit-font-smoothing:antialiased;background:#fff}
#fxb-page *{box-sizing:border-box;margin:0;padding:0}
#fxb-page a{text-decoration:none}

/* HERO */
#fxb-page .fxb-hero{position:relative;overflow:hidden;padding:84px 24px 76px;text-align:center;color:#fff}
#fxb-page .fxb-hero-bg{position:absolute;inset:0;pointer-events:none;z-index:0;overflow:hidden}
#fxb-page .fxb-hero-bg img{position:absolute;opacity:.05}
#fxb-page .fxb-hd1{right:-110px;top:-50px;width:460px;transform:rotate(14deg)}
#fxb-page .fxb-hd2{left:-70px;bottom:-30px;width:300px;transform:rotate(-12deg);opacity:.04}
#fxb-page .fxb-hero-inner{position:relative;z-index:1;max-width:760px;margin:0 auto}
#fxb-page .fxb-eyebrow{display:inline-flex;align-items:center;gap:9px;font-weight:800;font-size:12.5px;letter-spacing:.15em;text-transform:uppercase;background:rgba(255,255,255,.14);padding:9px 18px;border-radius:100px;margin-bottom:22px;backdrop-filter:blur(4px)}
#fxb-page .fxb-dot{width:7px;height:7px;border-radius:50%;background:var(--yellow);box-shadow:0 0 0 4px rgba(252,249,81,.28)}
#fxb-page .fxb-h1{font-weight:900;font-size:clamp(32px,5vw,54px);line-height:1.08;margin-bottom:18px;letter-spacing:-.02em}
#fxb-page .fxb-accent{position:relative;white-space:nowrap}
#fxb-page .fxb-accent::after{content:"";position:absolute;left:-2px;right:-2px;bottom:.05em;height:.34em;background:var(--yellow);opacity:.45;border-radius:6px;z-index:-1;transform:rotate(-1.2deg)}
#fxb-page .fxb-sub{font-size:17px;font-weight:500;opacity:.9;max-width:600px;margin:0 auto 30px;line-height:1.55}
#fxb-page .fxb-hero-btns{display:flex;gap:14px;justify-content:center;flex-wrap:wrap}
#fxb-page .fxb-btn-main{display:inline-flex;align-items:center;gap:8px;padding:17px 32px;border-radius:100px;background:linear-gradient(135deg,var(--yellow),#f5ee76);color:var(--purple);font-weight:800;font-size:15.5px;box-shadow:0 14px 30px -10px rgba(252,249,81,.5);transition:transform .3s}
#fxb-page .fxb-btn-main:hover{transform:translateY(-3px)}
#fxb-page .fxb-btn-sec{display:inline-flex;align-items:center;padding:17px 30px;border-radius:100px;background:rgba(255,255,255,.14);color:#fff;font-weight:700;font-size:15px;border:1px solid rgba(255,255,255,.25);transition:background .2s}
#fxb-page .fxb-btn-sec:hover{background:rgba(255,255,255,.24)}

/* SECTIONS */
#fxb-page .fxb-section{padding:78px 24px}
#fxb-page .fxb-bg-light{background:var(--bg)}
#fxb-page .fxb-wrap{max-width:1100px;margin:0 auto}
#fxb-page .fxb-head{text-align:center;margin-bottom:46px}
#fxb-page .fxb-kicker{display:inline-flex;align-items:center;gap:8px;font-weight:800;font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--purple-2);background:rgba(102,45,146,.08);padding:8px 16px;border-radius:100px;margin-bottom:16px}
#fxb-page .fxb-kicker .fxb-dot{background:var(--orange);box-shadow:0 0 0 4px rgba(238,115,73,.18)}
#fxb-page .fxb-h2{font-weight:800;font-size:clamp(26px,3.6vw,40px);line-height:1.1;letter-spacing:-.02em}
#fxb-page .fxb-h2 .fxb-accent::after{background:var(--yellow);opacity:1}
#fxb-page .fxb-lead{color:var(--muted);font-weight:500;max-width:600px;margin:14px auto 0;font-size:16px;line-height:1.55}

/* FEATURE GRID */
#fxb-page .fxb-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:22px}
#fxb-page .fxb-card{position:relative;overflow:hidden;background:#fff;border:1px solid rgba(57,40,82,.08);border-radius:22px;padding:30px 28px;box-shadow:0 16px 36px -22px rgba(57,40,82,.4);transition:transform .45s cubic-bezier(.2,.8,.2,1),box-shadow .45s,border-color .45s;opacity:0;transform:translateY(30px)}
#fxb-page .fxb-card.fxb-in{opacity:1;transform:none}
#fxb-page .fxb-card:hover{transform:translateY(-8px);box-shadow:0 30px 54px -24px rgba(102,45,146,.5);border-color:rgba(102,45,146,.2)}
#fxb-page .fxb-ic{width:56px;height:56px;border-radius:16px;display:grid;place-items:center;margin-bottom:18px;background:linear-gradient(135deg,rgba(102,45,146,.12),rgba(102,45,146,.04))}
#fxb-page .fxb-ic svg{width:28px;height:28px;stroke:var(--purple-2)}
#fxb-page .fxb-card:nth-child(2) .fxb-ic{background:linear-gradient(135deg,rgba(238,115,73,.16),rgba(238,115,73,.04))}
#fxb-page .fxb-card:nth-child(2) .fxb-ic svg{stroke:var(--orange)}
#fxb-page .fxb-card:nth-child(3) .fxb-ic{background:linear-gradient(135deg,rgba(231,194,0,.2),rgba(252,249,81,.07))}
#fxb-page .fxb-card:nth-child(3) .fxb-ic svg{stroke:#cda400}
#fxb-page .fxb-card:nth-child(4) .fxb-ic{background:linear-gradient(135deg,rgba(43,182,115,.16),rgba(126,217,87,.06))}
#fxb-page .fxb-card:nth-child(4) .fxb-ic svg{stroke:#2bb673}
#fxb-page .fxb-card h3{font-size:17.5px;font-weight:800;margin-bottom:9px;line-height:1.25}
#fxb-page .fxb-card p{color:var(--muted);font-size:14.5px;font-weight:500;line-height:1.55}

/* FACT CHIPS */
#fxb-page .fxb-facts{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}
#fxb-page .fxb-fact{background:#fff;border:1px solid rgba(57,40,82,.08);border-radius:18px;padding:24px 20px;text-align:center;box-shadow:0 12px 28px -20px rgba(57,40,82,.35)}
#fxb-page .fxb-fact .fxb-fic{width:46px;height:46px;border-radius:14px;margin:0 auto 12px;display:grid;place-items:center;background:rgba(102,45,146,.08)}
#fxb-page .fxb-fact .fxb-fic svg{width:23px;height:23px;stroke:var(--purple-2)}
#fxb-page .fxb-fact b{display:block;font-size:16px;font-weight:800;margin-bottom:4px}
#fxb-page .fxb-fact span{color:var(--muted);font-size:13px;font-weight:500;line-height:1.45}

/* BOOKS */
#fxb-page .fxb-books{display:grid;grid-template-columns:repeat(2,1fr);gap:18px}
#fxb-page .fxb-book{display:flex;gap:18px;align-items:flex-start;background:#fff;border:1px solid rgba(57,40,82,.08);border-radius:18px;padding:22px;box-shadow:0 10px 24px -16px rgba(57,40,82,.3)}
#fxb-page .fxb-book-cover{width:62px;height:82px;border-radius:10px;background:linear-gradient(135deg,var(--purple-2),var(--purple-3));display:grid;place-items:center;flex:0 0 auto;box-shadow:0 8px 18px -8px rgba(102,45,146,.6)}
#fxb-page .fxb-book-cover svg{width:28px;height:28px;stroke:#fff}
#fxb-page .fxb-book-cover--img{width:74px;height:98px;background:#fff;border:1px solid rgba(57,40,82,.1);padding:5px;box-shadow:0 9px 20px -8px rgba(57,40,82,.45)}
#fxb-page .fxb-book-cover--img img{width:100%;height:100%;object-fit:contain;border-radius:6px}
#fxb-page .fxb-book h4{font-size:15.5px;font-weight:800;margin-bottom:6px}
#fxb-page .fxb-book p{color:var(--muted);font-size:13.5px;font-weight:500;line-height:1.5}
#fxb-page .fxb-note{margin-top:22px;font-size:13px;color:#a89fbd;font-weight:600;text-align:center;font-style:italic}

/* CTA */
#fxb-page .fxb-cta{position:relative;overflow:hidden;background:linear-gradient(135deg,#392852,#662d92);padding:74px 24px;text-align:center;color:#fff}
#fxb-page .fxb-cta-bg{position:absolute;inset:0;pointer-events:none}
#fxb-page .fxb-cta-bg img{position:absolute;right:-50px;bottom:-40px;width:240px;opacity:.05}
#fxb-page .fxb-cta-box{position:relative;z-index:1;max-width:640px;margin:0 auto}
#fxb-page .fxb-cta-box h2{font-weight:800;font-size:clamp(24px,3.2vw,36px);margin-bottom:14px;line-height:1.15}
#fxb-page .fxb-cta-box h2 .fxb-accent::after{opacity:.4}
#fxb-page .fxb-cta-box p{color:rgba(255,255,255,.78);font-size:16px;font-weight:500;margin-bottom:30px;line-height:1.55}
#fxb-page .fxb-cta-btns{display:flex;gap:14px;justify-content:center;flex-wrap:wrap}
#fxb-page .fxb-btn-max{display:inline-flex;align-items:center;gap:8px;padding:17px 32px;border-radius:100px;background:linear-gradient(135deg,var(--orange),#f5a06f);color:#fff;font-weight:800;font-size:15px;box-shadow:0 14px 28px -10px rgba(238,115,73,.5);transition:transform .3s}
#fxb-page .fxb-btn-max:hover{transform:translateY(-3px)}

@media(max-width:860px){#fxb-page .fxb-facts{grid-template-columns:repeat(2,1fr)}}
@media(max-width:680px){#fxb-page .fxb-grid,#fxb-page .fxb-books{grid-template-columns:1fr}#fxb-page .fxb-hero{padding:62px 18px 56px}#fxb-page .fxb-section{padding:58px 18px}}
@media(max-width:440px){#fxb-page .fxb-facts{grid-template-columns:1fr}}
</style>
"""

JS = """
<script>
(function(){
  var root=document.getElementById('fxb-page');if(!root)return;
  var items=root.querySelectorAll('.fxb-card,.fxb-fact,.fxb-book');
  if('IntersectionObserver' in window){
    var io=new IntersectionObserver(function(es){es.forEach(function(e){
      if(e.isIntersecting){e.target.classList.add('fxb-in');io.unobserve(e.target);}
    })},{threshold:.15});
    items.forEach(function(el,i){el.style.transitionDelay=(i%4*70)+'ms';io.observe(el);});
  } else { items.forEach(function(el){el.classList.add('fxb-in');}); }
})();
</script>
"""

DECOR_SWIRL = "https://raw.githubusercontent.com/Dymovgrigory/Dymova-english/devin/1782590824-session6-redesign/brand-assets/decor-swirl-yellow-1.png"
DECOR_FOX = "https://raw.githubusercontent.com/Dymovgrigory/Dymova-english/devin/1782590824-session6-redesign/brand-assets/fox-head-yellow.png"
MYLEVEL = "https://raw.githubusercontent.com/Dymovgrigory/Dymova-english/devin/1782590824-session6-redesign/brand-assets/"
MAX_BOT = "https://max.ru/id611904726658_bot"


def feature_card(icon, title, text):
    return ('<article class="fxb-card"><div class="fxb-ic">' + svg(icon) +
            '</div><h3>' + title + '</h3><p>' + text + '</p></article>')


def fact(icon, value, label):
    return ('<div class="fxb-fact"><div class="fxb-fic">' + svg(icon) +
            '</div><b>' + value + '</b><span>' + label + '</span></div>')


def book(title, text, cover=None):
    if cover:
        inner = ('<div class="fxb-book-cover fxb-book-cover--img"><img src="' + cover +
                 '" alt="' + title + '" loading="lazy"></div>')
    else:
        inner = '<div class="fxb-book-cover">' + svg("book") + '</div>'
    return ('<div class="fxb-book">' + inner +
            '<div><h4>' + title + '</h4><p>' + text + '</p></div></div>')


def render_page(p):
    """p: dict with page content."""
    grad = p["hero_grad"]
    h = []
    h.append('<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800;900&display=swap&subset=latin,cyrillic" rel="stylesheet">')
    h.append('<div id="fxb-page">')
    # HERO
    h.append('<section class="fxb-hero" style="background:' + grad + '">')
    h.append('<div class="fxb-hero-bg"><img class="fxb-hd1" src="' + DECOR_SWIRL + '" alt="" loading="lazy"><img class="fxb-hd2" src="' + DECOR_FOX + '" alt="" loading="lazy"></div>')
    h.append('<div class="fxb-hero-inner">')
    h.append('<span class="fxb-eyebrow"><span class="fxb-dot"></span>' + p["eyebrow"] + '</span>')
    h.append('<h1 class="fxb-h1">' + p["h1"] + '</h1>')
    h.append('<p class="fxb-sub">' + p["sub"] + '</p>')
    h.append('<div class="fxb-hero-btns">')
    h.append('<a data-fxb-zayavka data-fxb-subject="' + p["lead_subject"] + '" data-fxb-window="' + p["lead_hero_window"] + '" role="button" tabindex="0" class="fxb-btn-main">' + p["cta_label"] + '</a>')
    h.append('<a href="#fxb-program" class="fxb-btn-sec">Подробнее о программе</a>')
    h.append('</div></div></section>')
    # FEATURES
    h.append('<section class="fxb-section" id="fxb-program"><div class="fxb-wrap">')
    h.append('<div class="fxb-head"><span class="fxb-kicker"><span class="fxb-dot"></span>' + p["feat_kicker"] + '</span>')
    h.append('<h2 class="fxb-h2">' + p["feat_title"] + '</h2>')
    if p.get("feat_lead"):
        h.append('<p class="fxb-lead">' + p["feat_lead"] + '</p>')
    h.append('</div><div class="fxb-grid">')
    for c in p["features"]:
        h.append(feature_card(*c))
    h.append('</div></div></section>')
    # FACTS
    h.append('<section class="fxb-section fxb-bg-light"><div class="fxb-wrap">')
    h.append('<div class="fxb-head"><span class="fxb-kicker"><span class="fxb-dot"></span>Формат</span>')
    h.append('<h2 class="fxb-h2">' + p["facts_title"] + '</h2></div>')
    h.append('<div class="fxb-facts">')
    for f in p["facts"]:
        h.append(fact(*f))
    h.append('</div></div></section>')
    # BOOKS (optional)
    if p.get("books"):
        bg = "" if p.get("books_on_light") else " fxb-bg-light"
        h.append('<section class="fxb-section' + bg + '"><div class="fxb-wrap">')
        h.append('<div class="fxb-head"><span class="fxb-kicker"><span class="fxb-dot"></span>Материалы</span>')
        h.append('<h2 class="fxb-h2">' + p["books_title"] + '</h2>')
        h.append('<p class="fxb-lead">' + p["books_lead"] + '</p></div>')
        h.append('<div class="fxb-books">')
        for b in p["books"]:
            h.append(book(*b))
        note = p.get("books_note", "Фотографии пособий будут добавлены позже. Все материалы включены в стоимость курса.")
        h.append('</div><p class="fxb-note">' + note + '</p>')
        h.append('</div></section>')
    # CTA
    h.append('<section class="fxb-cta" id="fxb-cta">')
    h.append('<div class="fxb-cta-bg"><img src="' + DECOR_FOX + '" alt="" loading="lazy"></div>')
    h.append('<div class="fxb-cta-box"><h2>' + p["cta_title"] + '</h2><p>' + p["cta_text"] + '</p>')
    h.append('<div class="fxb-cta-btns">')
    h.append('<a data-fxb-zayavka data-fxb-subject="' + p["lead_subject"] + '" data-fxb-window="' + p["lead_final_window"] + '" role="button" tabindex="0" class="fxb-btn-main">Оставить заявку на сайте</a>')
    h.append('<a href="' + MAX_BOT + '" target="_blank" rel="noopener" class="fxb-btn-max">' + svg("chat") + 'Написать в Max</a>')
    h.append('</div></div></section>')
    h.append(zayavka_unit())
    h.append('</div>')
    h.append(CSS)
    h.append(JS)
    return "\n".join(h)


# ---------------------------------------------------------------- контент
PAGES = {}

PAGES["page_doshkolniki.html"] = {
    "hero_grad": "linear-gradient(135deg,#392852 0%,#7b4fc0 55%,#662d92 100%)",
    "eyebrow": "Для детей 3–6 лет",
    "h1": 'Английский для <span class="fxb-accent">дошкольников</span>',
    "sub": "Игровой формат, который влюбляет ребёнка в язык с самого раннего возраста. Маленькие группы — большой результат.",
    "cta_label": "Записаться на диагностику",
    "feat_kicker": "Как мы учим",
    "feat_title": "Как устроены занятия",
    "feat_lead": "Через игру, движение и творчество — так, как дети этого возраста усваивают новое легче всего.",
    "features": [
        ("game", "Игровой формат", "Песни, мультфильмы, подвижные игры и творческие задания. Без скучных учебников и зубрёжки."),
        ("group", "Мини-группы до 6 детей", "Педагог уделяет внимание каждому ребёнку и видит прогресс каждого."),
        ("music", "Полное погружение", "Занятие полностью на английском — ребёнок привыкает к звучанию языка естественно."),
        ("chart", "Видимый прогресс", "Регулярная обратная связь родителям. Первые фразы — уже через месяц занятий."),
    ],
    "facts_title": "Коротко о занятиях",
    "facts": [
        ("calendar", "2 раза / нед", "Регулярность для устойчивого результата"),
        ("clock", "45 минут", "Оптимально для концентрации малышей"),
        ("sun", "Утренние группы", "Для тех, кто ходит в сад во вторую смену"),
        ("group", "До 6 человек", "Камерные группы по возрасту и уровню"),
    ],
    "lead_subject": "Английский для дошкольников",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "books": [
        ("Cookie and Friends", "Яркие картинки, песни и истории с персонажами. Идеально для первого знакомства с языком."),
        ("Happy House", "Развитие слухового восприятия и произношения через диалоги и ролевые игры."),
    ],
    "books_title": "Пособия и материалы",
    "books_lead": "Используем проверенные международные пособия, адаптированные для дошкольного возраста.",
    "cta_title": 'Запишите ребёнка на <span class="fxb-accent">бесплатную диагностику</span>',
    "cta_text": "Методист определит уровень и подберёт подходящую группу — без обязательств.",
}

PAGES["page_mladshie_shkolniki.html"] = {
    "hero_grad": "linear-gradient(135deg,#2e1a47 0%,#662d92 55%,#8a4fb8 100%)",
    "eyebrow": "Для детей 7–10 лет",
    "h1": 'Английский для <span class="fxb-accent">младших школьников</span>',
    "sub": "Уверенная база языка параллельно со школьной программой: чтение, письмо, грамматика и живое общение.",
    "cta_label": "Записаться на диагностику",
    "feat_kicker": "Что освоит ребёнок",
    "feat_title": "Чему научится ваш ребёнок",
    "feat_lead": "Закладываем прочный фундамент, на котором легко строится дальнейшее обучение.",
    "features": [
        ("book", "Чтение и фоника", "Учим читать по правилам phonics — ребёнок понимает, как из букв складываются слова."),
        ("pencil", "Письмо и грамматика", "Базовая грамматика и письмо в игровой подаче, без перегруза правилами."),
        ("chat", "Разговорная практика", "Диалоги, ролевые игры и проекты — язык как инструмент общения, а не набор слов."),
        ("shield", "Поддержка школьной программы", "Закрываем пробелы и идём на шаг впереди школьной программы английского."),
    ],
    "facts_title": "Коротко о занятиях",
    "facts": [
        ("calendar", "2 раза / нед", "Стабильный ритм обучения"),
        ("clock", "60 минут", "Полноценное занятие с практикой"),
        ("sun", "Утро, день, вечер", "Дневные, вечерние и утренние группы — подойдут и тем, кто учится во вторую смену"),
        ("group", "До 7 человек", "Мини-группы по уровню"),
    ],
    "lead_subject": "Английский для младших школьников",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "books": [
        ("My Level 1", "6–8 лет, 1-й год обучения. Уровень Pre-A1. Старт с азов: алфавит, фоника и первые фразы, чтение по Read with Richie.", MYLEVEL + "mylevel-1.png"),
        ("My Level 2", "8–9 лет, 2-й год обучения. Уровень Pre-A1 → A1. Расширяем лексику и грамматику, больше чтения с Richie's Adventures.", MYLEVEL + "mylevel-2.png"),
        ("My Level 3", "9–10 лет, 3-й год обучения. Уровень A1. Уверенное чтение и грамматика, отработка лексики по Move It 1.", MYLEVEL + "mylevel-3.png"),
        ("My Level 4", "10–11 лет, 4-й год обучения. Уровень A1 → A2. Сложнее тексты и грамматика по Move It 2, мягкая подготовка к Кембриджским экзаменам YLE.", MYLEVEL + "mylevel-4.png"),
    ],
    "books_title": "Учебники My Level",
    "books_lead": "Занимаемся по современным оригинальным УМК My Level — с 1 по 4 уровень, по возрасту и подготовке ребёнка.",
    "books_note": "Комплекты учебников My Level приобретаются в нашей школе отдельно.",
    "cta_title": 'Начните с <span class="fxb-accent">бесплатной диагностики</span>',
    "cta_text": "Методист оценит уровень ребёнка и предложит индивидуальный план обучения.",
}

PAGES["page_podrostki.html"] = {
    "hero_grad": "linear-gradient(135deg,#1e1433 0%,#4a2a7a 55%,#662d92 100%)",
    "eyebrow": "Для подростков 11–16 лет",
    "h1": 'Английский для <span class="fxb-accent">подростков</span>',
    "sub": "Свободное общение, академический английский и уверенная подготовка к ОГЭ, ЕГЭ и международным экзаменам.",
    "cta_label": "Записаться на диагностику",
    "feat_kicker": "Цели обучения",
    "feat_title": "На чём фокусируемся",
    "feat_lead": "Язык для реальной жизни и для оценок — развиваем оба направления одновременно.",
    "features": [
        ("mic", "Свободная речь", "Дискуссии, презентации и дебаты — подросток говорит уверенно и без страха ошибиться."),
        ("cap", "Подготовка к ОГЭ / ЕГЭ", "Системная отработка всех частей экзамена, пробные тестирования и стратегии."),
        ("globe", "Академический английский", "Эссе, аргументация и работа с текстами — навыки, нужные для учёбы и поступления."),
        ("trophy", "Международные экзамены", "Подготовка к Cambridge (PET / FCE) и участие в олимпиаде Hippo."),
    ],
    "facts_title": "Коротко о занятиях",
    "facts": [
        ("calendar", "2 раза / нед", "Регулярная отработка навыков"),
        ("clock", "60 минут", "Интенсивная практика на каждом занятии"),
        ("sun", "Утренние группы", "Удобно для учащихся во вторую смену"),
        ("group", "До 7 человек", "Группы по уровню и целям"),
    ],
    "lead_subject": "Английский для подростков",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "books": [
        ("Solutions (Oxford)", "Курс для подростков с упором на коммуникацию и подготовку к экзаменам."),
        ("Prepare! (Cambridge)", "Подготовка к экзаменам Cambridge и развитие всех языковых навыков."),
    ],
    "books_title": "Пособия и материалы",
    "books_lead": "Современные курсы Oxford и Cambridge для подросткового возраста.",
    "cta_title": 'Узнайте уровень на <span class="fxb-accent">бесплатной диагностике</span>',
    "cta_text": "Определим текущий уровень и составим маршрут до нужного результата — экзамен, олимпиада или свободное общение.",
}

# ----- летние программы -----
PAGES["page_letnyaya_akademiya.html"] = {
    "hero_grad": "linear-gradient(135deg,#ee7349 0%,#f7971e 50%,#fcc419 100%)",
    "eyebrow": "Летние программы",
    "h1": 'Летняя <span class="fxb-accent">Академия</span>',
    "sub": "Интенсив на лето: развиваем английский, не теряя форму. Игры, проекты и общение — без скучных уроков.",
    "cta_label": "Записаться в Академию",
    "feat_kicker": "Программа",
    "feat_title": "Что входит в программу",
    "feat_lead": "Каждая смена — насыщенная языковая среда с проектами и практикой.",
    "features": [
        ("palette", "Тематические недели", "Путешествия, профессии, природа, технологии — каждая неделя новая тема, всё на английском."),
        ("rocket", "Творческие проекты", "Презентации, мини-спектакли и видеоблоги — язык применяется в реальных задачах."),
        ("group", "Мини-группы до 8", "Формирование по уровню и возрасту, максимум практики для каждого."),
        ("sun", "Первая половина дня", "Свободный день у ребёнка остаётся — занятия проходят утром."),
    ],
    "facts_title": "Коротко о смене",
    "facts": [
        ("calendar", "2–4 недели", "Гибкий выбор удобного периода"),
        ("clock", "Утро", "Занятия в первой половине дня"),
        ("group", "До 8 человек", "Группы по возрасту и уровню"),
        ("target", "Без потери формы", "Поддерживаем уровень за лето"),
    ],
    "lead_subject": "Летняя Академия",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "cta_title": 'Запишитесь в <span class="fxb-accent">Летнюю Академию</span>',
    "cta_text": "Количество мест ограничено — бронируйте заранее, чтобы попасть в удобную смену.",
}

PAGES["page_online_zanyatiya.html"] = {
    "hero_grad": "linear-gradient(135deg,#392852 0%,#6237a2 55%,#8a4fb8 100%)",
    "eyebrow": "Летние программы · Онлайн",
    "h1": 'Онлайн <span class="fxb-accent">занятия</span>',
    "sub": "Тот же сильный английский Фоксинбург — из любой точки. Живые уроки с педагогом в небольших группах.",
    "cta_label": "Записаться онлайн",
    "feat_kicker": "Формат",
    "feat_title": "Как проходят онлайн-уроки",
    "feat_lead": "Полноценные интерактивные занятия — не запись, а живое общение с преподавателем.",
    "features": [
        ("monitor", "Живые видеоуроки", "Занятия в реальном времени с педагогом — вопросы и практика прямо на уроке."),
        ("palette", "Интерактивная доска", "Игры, задания и материалы на онлайн-доске удерживают внимание ребёнка."),
        ("group", "Мини-группы", "Небольшие группы по уровню — каждый успевает говорить и получать обратную связь."),
        ("globe", "Из любой точки", "Удобно на даче, в поездке или в другом городе — нужен только интернет."),
    ],
    "facts_title": "Коротко о занятиях",
    "facts": [
        ("calendar", "2 раза / нед", "Стабильный ритм обучения"),
        ("clock", "45–60 минут", "Длительность по возрасту"),
        ("monitor", "Zoom / онлайн", "Подключение по ссылке"),
        ("group", "Мини-группы", "По уровню и возрасту"),
    ],
    "lead_subject": "Онлайн-занятия",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "cta_title": 'Запишитесь на <span class="fxb-accent">онлайн-занятия</span>',
    "cta_text": "Подберём удобное время и группу под уровень вашего ребёнка.",
}

PAGES["page_podderzhivayushchie_online.html"] = {
    "hero_grad": "linear-gradient(135deg,#2e1a47 0%,#662d92 55%,#7b4fc0 100%)",
    "eyebrow": "Летние программы · Онлайн",
    "h1": 'Поддерживающие <span class="fxb-accent">онлайн-занятия</span>',
    "sub": "Лёгкий формат, чтобы не забыть выученное за лето. Повторяем, закрепляем и поддерживаем уровень.",
    "cta_label": "Записаться на поддержку",
    "feat_kicker": "Зачем это нужно",
    "feat_title": "Что даёт формат поддержки",
    "feat_lead": "Без перегруза — но регулярно, чтобы знания не «осыпались» за длинные каникулы.",
    "features": [
        ("shield", "Сохраняем уровень", "Регулярное повторение не даёт забыть лексику и грамматику за лето."),
        ("chat", "Разговорная практика", "Главный акцент — на говорении: ребёнок продолжает использовать язык."),
        ("clock", "Лёгкая нагрузка", "Короткие уроки без домашнего перегруза — комфортно в каникулы."),
        ("rocket", "Лёгкий старт осенью", "К новому учебному году ребёнок возвращается в форме, без отката."),
    ],
    "facts_title": "Коротко о занятиях",
    "facts": [
        ("calendar", "1–2 раза / нед", "Гибкая нагрузка на лето"),
        ("clock", "45 минут", "Короткий поддерживающий формат"),
        ("monitor", "Онлайн", "Из любой точки"),
        ("group", "Мини-группы", "По уровню"),
    ],
    "lead_subject": "Поддерживающие онлайн-занятия",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "cta_title": 'Поддержите уровень <span class="fxb-accent">за лето</span>',
    "cta_text": "Запишитесь на лёгкий онлайн-формат — и сентябрь начнётся без стресса.",
}

PAGES["page_standartnye_offline.html"] = {
    "hero_grad": "linear-gradient(135deg,#1e1433 0%,#392852 55%,#662d92 100%)",
    "eyebrow": "Летние программы · Оффлайн",
    "h1": 'Стандартные <span class="fxb-accent">оффлайн-занятия</span>',
    "sub": "Классические занятия в наших филиалах в Долгопрудном — живое общение, среда и внимание педагога.",
    "cta_label": "Записаться в филиал",
    "feat_kicker": "Формат",
    "feat_title": "Почему оффлайн работает",
    "feat_lead": "Очный формат даёт максимум вовлечённости и живой языковой среды.",
    "features": [
        ("group", "Живая среда", "Общение, игры и работа в парах — язык усваивается естественно через взаимодействие."),
        ("compass", "Два филиала рядом", "Лихачевский, 76к1 и Ракетостроителей, 9к3 — выбирайте удобный."),
        ("shield", "Внимание педагога", "Преподаватель видит каждого ученика и сразу корректирует ошибки."),
        ("sun", "Утренние группы", "Есть утренние группы для тех, кто учится во вторую смену."),
    ],
    "facts_title": "Коротко о занятиях",
    "facts": [
        ("calendar", "2 раза / нед", "Регулярные занятия"),
        ("clock", "60 минут", "Полноценный урок"),
        ("compass", "2 филиала", "Долгопрудный"),
        ("group", "До 7 человек", "Мини-группы по уровню"),
    ],
    "lead_subject": "Стандартные оффлайн-занятия",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "cta_title": 'Запишитесь на <span class="fxb-accent">занятия в филиале</span>',
    "cta_text": "Подберём удобный филиал, время и группу под уровень ученика.",
}

# ----- летние копии легаси-страниц (оригиналы не трогаем) -----
PAGES["page_reading.html"] = {
    "hero_grad": "linear-gradient(135deg,#2e1a47 0%,#5a2d8f 55%,#7b4fc0 100%)",
    "eyebrow": "Летний курс • Learn to Read",
    "h1": 'Курс по <span class="fxb-accent">чтению</span> на английском',
    "sub": "Интенсив на лето для младших школьников: от букв и звуков — до уверенного чтения текстов. Программа разработана методистами на основе школьной.",
    "cta_label": "Узнать расписание курса",
    "feat_kicker": "Как мы учим",
    "feat_title": "Чему научится ребёнок",
    "feat_lead": "Ведём шаг за шагом — от первых звуков до чтения целых текстов, без зубрёжки и стресса.",
    "features": [
        ("book", "Фоника и звуки", "Учим читать по правилам phonics — ребёнок понимает, как из букв и звуков складываются слова."),
        ("chat", "От букв до текстов", "Пошагово: буквы → слоги → слова → предложения → короткие тексты. Уверенное чтение к концу курса."),
        ("group", "Мини-группы до 7", "Языковая среда без перехода на русский и внимание каждому ученику."),
        ("chart", "Обратная связь", "Еженедельные видео-отчёты, открытые уроки и тестирования — прогресс виден родителям."),
    ],
    "facts_title": "Коротко о курсе",
    "facts": [
        ("calendar", "Старт 1 июня", "Интенсив на летние месяцы"),
        ("sun", "Летний формат", "Подготовка к школьному английскому за лето"),
        ("cap", "Младшие школьники", "Для учеников начальной школы"),
        ("group", "До 7 человек", "Мини-группы по уровню"),
    ],
    "lead_subject": "Курс по чтению",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "cta_title": 'Подготовьте ребёнка к школьному английскому <span class="fxb-accent">за лето</span>',
    "cta_text": "Оставьте заявку — расскажем расписание курса и подберём группу под уровень ребёнка.",
}

PAGES["page_grammar.html"] = {
    "hero_grad": "linear-gradient(135deg,#241a36 0%,#662d92 55%,#8a4fb8 100%)",
    "eyebrow": "Летний курс грамматики",
    "h1": 'Курс по <span class="fxb-accent">грамматике</span>',
    "sub": "Для учеников 3–8 классов, кто путается во временах, не понимает правил и не может их применить. Закрываем пробелы за лето.",
    "cta_label": "Записаться на диагностику",
    "feat_kicker": "Что даёт курс",
    "feat_title": "Как мы учим грамматике",
    "feat_lead": "Объясняем так, чтобы ребёнок понимал систему языка — и уверенно применял правила в речи.",
    "features": [
        ("puzzle", "Понятная система", "Объясняем грамматику просто и логично — ребёнок понимает, а не заучивает наизусть."),
        ("clock", "Времена без путаницы", "Разбираем английские времена по полочкам, с практикой до автоматизма."),
        ("pencil", "Правила в речи", "Учимся применять правила в речи и письме, а не только в упражнениях."),
        ("shield", "Закрываем пробелы", "Подтягиваем темы, которые «провисли» в школе, к новому учебному году."),
    ],
    "facts_title": "Коротко о курсе",
    "facts": [
        ("cap", "3–8 классы", "Для школьников среднего звена"),
        ("sun", "Летний курс", "Интенсив перед учебным годом"),
        ("target", "Без пробелов", "Закрываем слабые темы"),
        ("group", "До 7 человек", "Мини-группы по уровню"),
    ],
    "lead_subject": "Курс по грамматике",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "cta_title": 'Закройте пробелы и <span class="fxb-accent">подготовьтесь к году</span>',
    "cta_text": "Запишитесь на бесплатную диагностику — определим пробелы и составим план занятий.",
}

PAGES["page_preparation.html"] = {
    "hero_grad": "linear-gradient(135deg,#2e1a47 0%,#662d92 60%,#9a5fc0 100%)",
    "eyebrow": "Подготовка к школе и не только",
    "h1": 'Подготовка <span class="fxb-accent">к школе</span>',
    "sub": "Готовим дошкольников 4–7 лет к первому классу, занимаемся со школьниками 1–4 классов и помогаем с подготовкой к ОГЭ, ЕГЭ и ВПР.",
    "cta_label": "Оставить заявку",
    "feat_kicker": "Чем занимаемся",
    "feat_title": "Что входит в подготовку",
    "feat_lead": "Помогаем ребёнку войти в школьную жизнь уверенно — и поддерживаем на каждом этапе обучения.",
    "features": [
        ("star", "Подготовка к школе", "Для детей 4–5 и 6–7 лет: чтение, счёт, логика, речь и усидчивость."),
        ("book", "Школьники 1–4 классов", "Помогаем осваивать школьную программу и учиться с удовольствием."),
        ("cap", "ОГЭ, ЕГЭ, ВПР", "Системная подготовка к экзаменам и проверочным работам."),
        ("pencil", "Русский и математика", "Не только английский — подтягиваем ключевые школьные предметы."),
    ],
    "facts_title": "Коротко о занятиях",
    "facts": [
        ("sun", "Лето с пользой", "Готовимся к учебному году заранее"),
        ("target", "Диагностика", "Купон на комплексную диагностику"),
        ("group", "Мини-группы", "Внимание каждому ребёнку"),
        ("chart", "Видимый прогресс", "Регулярные отчёты родителям"),
    ],
    "lead_subject": "Подготовка к школе",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "cta_title": 'Проведите <span class="fxb-accent">лето с пользой</span>',
    "cta_text": "Оставьте заявку и получите купон на комплексную диагностику ребёнка.",
}


def main():
    for fname, data in PAGES.items():
        html = render_page(data)
        path = os.path.join(OUT, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        print("wrote", fname, len(html), "bytes")


if __name__ == "__main__":
    main()
