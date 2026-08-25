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
import re
import json
from html import escape
from build_course_pages import zayavka_unit
import media_library  # Media Intelligence Layer: story_hero/media_wall/real_moment/video_story

OUT = os.path.dirname(os.path.abspath(__file__))
SITE = "https://dymova-english.ru"
RU_MONTHS = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}

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
    "heart": '<path d="M12 20.5s-8-4.7-9.7-9.6A5.2 5.2 0 0 1 12 6.6a5.2 5.2 0 0 1 9.7 4.3c-1.7 4.9-9.7 9.6-9.7 9.6z"/>',
}

def svg(name):
    return ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">'
            + ICONS[name] + '</svg>')

# ---------------------------------------------------------------- общий CSS
CSS = """
<style>
#fxb-page{--purple:#392852;--purple-2:#662d92;--purple-3:#6237a2;--orange:#c24712;--yellow:#fcf951;--ink:#241a36;--muted:#6f6883;--bg:#f4f1fa;
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

/* FAQ */
#fxb-page .fxb-faq{max-width:820px;margin:0 auto;display:flex;flex-direction:column;gap:14px}
#fxb-page .fxb-faq details{background:#fff;border:1px solid rgba(57,40,82,.08);border-radius:16px;padding:2px 24px;box-shadow:0 12px 28px -20px rgba(57,40,82,.35);transition:border-color .25s}
#fxb-page .fxb-faq details[open]{border-color:rgba(102,45,146,.22)}
#fxb-page .fxb-faq summary{cursor:pointer;list-style:none;display:flex;justify-content:space-between;align-items:center;gap:18px;font-weight:800;font-size:15.5px;line-height:1.35;padding:20px 0;color:var(--ink)}
#fxb-page .fxb-faq summary::-webkit-details-marker{display:none}
#fxb-page .fxb-faq summary::after{content:"+";font-size:24px;font-weight:700;color:var(--purple-2);flex:0 0 auto;line-height:1;transition:transform .25s}
#fxb-page .fxb-faq details[open] summary::after{content:"\\2013"}
#fxb-page .fxb-faq p{color:var(--muted);font-size:14.5px;font-weight:500;line-height:1.6;padding:0 0 22px}

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
#fxb-page .fxb-breadcrumbs{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;align-items:center;margin:0 auto 28px;font-size:13px;font-weight:700;color:rgba(57,40,82,.72)}
#fxb-page .fxb-breadcrumbs ol{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;align-items:center;margin:0;padding:0;list-style:none}
#fxb-page .fxb-breadcrumbs li{display:inline-flex;align-items:center;gap:8px;margin:0}
#fxb-page .fxb-breadcrumbs li+li::before{content:'→';color:rgba(57,40,82,.72)}
#fxb-page .fxb-breadcrumbs a{color:var(--purple-2)}
#fxb-page .fxb-breadcrumbs a:hover{color:var(--orange)}
#fxb-page .fxb-breadcrumbs span{color:rgba(57,40,82,.72)}
#fxb-page .fxb-hero .fxb-breadcrumbs{margin:0 auto 20px;color:rgba(255,255,255,.82)}
#fxb-page .fxb-hero .fxb-breadcrumbs a{color:#fff}
#fxb-page .fxb-hero .fxb-breadcrumbs a:hover{color:#fcf951}
#fxb-page .fxb-hero .fxb-breadcrumbs span,#fxb-page .fxb-hero .fxb-breadcrumbs li+li::before{color:rgba(255,255,255,.72)}
</style>
"""

LADDER_CSS = """
<style>
#fxb-page .fxb-ladder-sub{font-weight:800;font-size:15px;color:var(--purple-2);margin:26px 4px 16px;display:flex;align-items:center;gap:9px}
#fxb-page .fxb-ladder-sub::before{content:"";width:22px;height:3px;border-radius:3px;background:var(--orange)}
#fxb-page .fxb-ladder{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}
#fxb-page .fxb-step{display:flex;flex-direction:column;background:#fff;border:1px solid rgba(57,40,82,.08);border-radius:18px;overflow:hidden;box-shadow:0 14px 32px -22px rgba(57,40,82,.45);transition:transform .35s,box-shadow .35s,border-color .35s}
#fxb-page .fxb-step:hover{transform:translateY(-6px);box-shadow:0 28px 50px -26px rgba(102,45,146,.5);border-color:rgba(102,45,146,.25)}
#fxb-page .fxb-step-prev{height:150px;overflow:hidden;background:#241a36}
#fxb-page .fxb-step-prev img{width:100%;display:block;object-fit:cover;object-position:top center}
#fxb-page .fxb-step-body{padding:16px 18px 18px}
#fxb-page .fxb-step-body h4{font-size:16px;font-weight:800;color:var(--ink);margin-bottom:5px;line-height:1.2}
#fxb-page .fxb-step-body>span{display:block;color:var(--muted);font-size:13px;font-weight:600}
#fxb-page .fxb-step-link{margin-top:12px;color:var(--purple-2)!important;font-weight:800;font-size:13.5px}
@media(max-width:860px){#fxb-page .fxb-ladder{grid-template-columns:repeat(2,1fr)}}
@media(max-width:680px){#fxb-page .fxb-ladder{grid-template-columns:1fr}}
</style>
"""

VIDEO_CSS = """
<style>
#fxb-page .fxb-video-wrap{max-width:360px;margin:0 auto}
#fxb-page .fxb-video{position:relative;width:100%;border-radius:24px;overflow:hidden;background:#241a36;box-shadow:0 30px 60px -30px rgba(57,40,82,.6);border:1px solid rgba(57,40,82,.1)}
#fxb-page .fxb-video video{display:block;width:100%;height:auto;max-height:70vh;object-fit:contain;background:#241a36}
</style>
"""

PRICE_CSS = """
<style>
#fxb-page .fxb-price-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}
#fxb-page .fxb-price-card{background:#fff;border:1px solid rgba(57,40,82,.08);border-radius:22px;padding:26px 24px;box-shadow:0 16px 34px -22px rgba(57,40,82,.4);display:flex;flex-direction:column;gap:12px;transition:transform .35s,box-shadow .35s,border-color .35s}
#fxb-page .fxb-price-card:hover{transform:translateY(-5px);box-shadow:0 28px 50px -26px rgba(102,45,146,.5);border-color:rgba(102,45,146,.2)}
#fxb-page .fxb-price-card--main{background:linear-gradient(180deg,#fff 0%,#faf8fe 100%)}
#fxb-page .fxb-price-tag{display:inline-flex;align-items:center;align-self:flex-start;padding:7px 12px;border-radius:100px;background:rgba(102,45,146,.08);color:var(--purple-2);font-size:12px;font-weight:800;letter-spacing:.04em;text-transform:uppercase}
#fxb-page .fxb-price-tag--orange{background:rgba(238,115,73,.12);color:var(--orange)}
#fxb-page .fxb-price-card h3{font-size:clamp(28px,3vw,38px);line-height:1.05;font-weight:900;color:var(--ink)}
#fxb-page .fxb-price-card h3 span{font-size:15px;font-weight:800;color:var(--muted)}
#fxb-page .fxb-price-card p{font-size:14.5px;font-weight:500;color:var(--muted);line-height:1.55}
#fxb-page .fxb-price-note{margin-top:18px;color:var(--muted);font-size:13px;font-weight:600;text-align:center}
@media(max-width:860px){#fxb-page .fxb-price-grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:680px){#fxb-page .fxb-price-grid{grid-template-columns:1fr}}
</style>
"""

TEAM_CSS = """
<style>
#fxb-team{--purple-2:#662d92;--purple-3:#6237a2;--orange:#c24712;--yellow:#fcf951;--ink:#241a36;--muted:#6f6883;font-family:'Montserrat',Arial,sans-serif;color:var(--ink);-webkit-font-smoothing:antialiased;background:#ffffff}
#fxb-team *{box-sizing:border-box;margin:0;padding:0}
#fxb-team .fxb-section{max-width:1200px;margin:0 auto;padding:90px 24px 100px}
#fxb-team .fxb-eyebrow{display:inline-flex;align-items:center;gap:10px;font-weight:700;font-size:13px;letter-spacing:.16em;text-transform:uppercase;color:var(--purple-2);background:rgba(102,45,146,.08);padding:9px 16px;border-radius:100px}
#fxb-team .fxb-dot{width:7px;height:7px;border-radius:50%;background:var(--orange);box-shadow:0 0 0 4px rgba(238,115,73,.18)}
#fxb-team .fxb-head{display:flex;flex-direction:column;align-items:center;text-align:center;gap:18px;margin-bottom:58px}
#fxb-team .fxb-h2{font-weight:800;font-size:clamp(28px,4vw,46px);line-height:1.08;letter-spacing:-.02em}
#fxb-team .fxb-accent{position:relative;white-space:nowrap;color:var(--purple-2)}
#fxb-team .fxb-accent::after{content:"";position:absolute;left:0;right:0;bottom:.06em;height:.36em;background:var(--yellow);z-index:-1;border-radius:6px;transform:rotate(-1.2deg)}
#fxb-team .fxb-sub{max-width:660px;color:var(--muted);font-size:17px;font-weight:500}
#fxb-team .fxb-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:24px}
/* Одиночная карточка педагога — по центру, а не влево */
#fxb-team .fxb-grid:has(> .fxb-card:only-child){grid-template-columns:minmax(0,380px);justify-content:center}
#fxb-team .fxb-card{background:#fff;border:1px solid rgba(57,40,82,.08);border-radius:24px;overflow:hidden;box-shadow:0 18px 40px -22px rgba(57,40,82,.4);transition:transform .45s cubic-bezier(.2,.8,.2,1),box-shadow .45s;opacity:0;transform:translateY(34px)}
#fxb-team .fxb-card.fxb-in{opacity:1;transform:none}
#fxb-team .fxb-card:hover{transform:translateY(-8px);box-shadow:0 30px 56px -24px rgba(102,45,146,.5)}
#fxb-team .fxb-photo{position:relative;aspect-ratio:3/4;background-size:cover;background-position:center top;display:grid;place-items:center}
#fxb-team .fxb-ava{opacity:.85;filter:drop-shadow(0 6px 12px rgba(0,0,0,.25));border-radius:12px}
#fxb-team .fxb-body{padding:20px 20px 24px}
#fxb-team .fxb-role{display:inline-block;font-size:11.5px;font-weight:800;letter-spacing:.04em;text-transform:uppercase;padding:5px 11px;border-radius:100px;margin-bottom:12px}
#fxb-team .fxb-r-teacher{color:var(--purple-2);background:rgba(102,45,146,.10)}
#fxb-team .fxb-r-method{color:var(--orange);background:rgba(238,115,73,.12)}
#fxb-team .fxb-r-admin{color:#2bb673;background:rgba(43,182,115,.12)}
#fxb-team .fxb-r-head{color:var(--purple-2);background:rgba(252,249,81,.28)}
#fxb-team .fxb-body h3{font-size:17.5px;font-weight:800;margin-bottom:5px}
#fxb-team .fxb-body p{color:var(--muted);font-size:13.5px;font-weight:500;line-height:1.5;margin-bottom:16px}
#fxb-team .fxb-btns{display:flex;flex-direction:column;gap:9px}
#fxb-team .fxb-vbtn{cursor:pointer;border:0;font-family:inherit;font-weight:700;font-size:13.5px;color:#fff;padding:11px 14px;border-radius:12px;background:linear-gradient(135deg,var(--purple-2),var(--purple-3));transition:transform .25s,box-shadow .25s;text-align:center}
#fxb-team .fxb-vbtn-2{background:linear-gradient(135deg,var(--orange),#f5a06f)}
#fxb-team .fxb-vbtn:hover{transform:translateY(-2px);box-shadow:0 12px 22px -10px rgba(102,45,146,.7)}
#fxb-team .fxb-tvmod{position:fixed;inset:0;z-index:9999;display:none;align-items:center;justify-content:center;padding:20px}
#fxb-team .fxb-tvmod.fxb-tvopen{display:flex}
#fxb-team .fxb-tvmod-bg{position:absolute;inset:0;background:rgba(36,26,54,.78);backdrop-filter:blur(4px)}
#fxb-team .fxb-tvmod-box{position:relative;width:auto;max-width:min(900px,96vw);background:#0e0a16;border-radius:20px;overflow:hidden;box-shadow:0 40px 90px -20px rgba(0,0,0,.7);animation:fxbpop .35s cubic-bezier(.2,.8,.2,1)}
@keyframes fxbpop{from{opacity:0;transform:translateY(20px) scale(.98)}to{opacity:1;transform:none}}
#fxb-team .fxb-tvmod-close{position:absolute;top:10px;right:14px;z-index:2;background:rgba(255,255,255,.15);color:#fff;border:0;width:38px;height:38px;border-radius:50%;font-size:24px;line-height:1;cursor:pointer}
#fxb-team .fxb-tvmod-frame{position:relative;width:100%;min-height:220px;background:#0e0a16;display:grid;place-items:center}
#fxb-team .fxb-tvmod-frame video{display:block;max-width:min(900px,96vw);max-height:82vh;width:auto;height:auto;background:#000}
#fxb-team .fxb-tvmod-frame iframe{width:100%;height:100%;border:0}
#fxb-team .fxb-tvmod-empty{color:#b9aee0;font-size:15px;font-weight:600;text-align:center;padding:24px;max-width:420px}
@media(max-width:900px){#fxb-team .fxb-grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:520px){#fxb-team .fxb-grid{grid-template-columns:1fr;max-width:380px;margin:0 auto}#fxb-team .fxb-section{padding:64px 18px 76px}}
</style>
"""

TEAM_JS = """
<script>
(function(){
  var root=document.getElementById('fxb-team');if(!root)return;
  var cards=root.querySelectorAll('.fxb-card');
  if('IntersectionObserver' in window){
    var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add('fxb-in');io.unobserve(e.target);}})},{threshold:.12});
    cards.forEach(function(c){io.observe(c);});
  } else { cards.forEach(function(c){c.classList.add('fxb-in')}); }
  var modal=document.getElementById('fxbTeacherVideoModal');
  var frame=modal.querySelector('.fxb-tvmod-frame');
  var EMPTY='<div class="fxb-tvmod-empty">Видео появится здесь после добавления ссылки</div>';
  function open(url){
    if(url){frame.innerHTML='<video src="'+url+'" controls autoplay playsinline></video>';}
    else{frame.innerHTML=EMPTY;}
    modal.classList.add('fxb-tvopen');
  }
  function close(){var v=frame.querySelector('video');if(v){try{v.pause();}catch(e){}}modal.classList.remove('fxb-tvopen');frame.innerHTML=EMPTY;}
  root.querySelectorAll('.fxb-vbtn').forEach(function(b){b.addEventListener('click',function(){open(b.getAttribute('data-video'));});});
  modal.querySelector('.fxb-tvmod-close').addEventListener('click',close);
  modal.querySelector('.fxb-tvmod-bg').addEventListener('click',close);
})();
</script>
"""

ARTICLE_CSS = """
<style>
#fxb-page.fxb-blog-page .fxb-hero{padding:66px 24px 44px}
#fxb-page.fxb-blog-page .fxb-hero-inner{max-width:980px}
#fxb-page.fxb-blog-page .fxb-h1{font-size:clamp(30px,4.4vw,48px);margin-bottom:14px}
#fxb-page.fxb-blog-page .fxb-sub{max-width:760px;font-size:16px;margin-bottom:18px}
#fxb-page.fxb-blog-page .fxb-article-meta{display:flex;justify-content:center;flex-wrap:wrap;gap:10px 14px;color:rgba(255,255,255,.82);font-weight:700;font-size:14px;letter-spacing:.01em}
#fxb-page.fxb-blog-page .fxb-article-meta span{display:inline-flex;align-items:center;gap:8px}
#fxb-page.fxb-blog-page .fxb-article-meta span+span::before{content:"•";margin-right:14px;color:rgba(255,255,255,.5)}
#fxb-page.fxb-blog-page .fxb-article-body{max-width:760px;margin:0 auto;color:var(--ink);font-size:17px;line-height:1.78;font-weight:500}
#fxb-page.fxb-blog-page .fxb-article-body h2{font-size:clamp(24px,3vw,34px);line-height:1.18;margin:44px 0 14px;font-weight:800;color:var(--ink)}
#fxb-page.fxb-blog-page .fxb-article-body h3{font-size:clamp(19px,2.4vw,24px);line-height:1.25;margin:34px 0 12px;font-weight:800;color:var(--purple-2)}
#fxb-page.fxb-blog-page .fxb-article-body p{margin:0 0 18px;color:var(--ink)}
#fxb-page.fxb-blog-page .fxb-article-body p:last-child{margin-bottom:0}
#fxb-page.fxb-blog-page .fxb-article-body ul{margin:0 0 18px 20px;padding-left:18px}
#fxb-page.fxb-blog-page .fxb-article-body li{margin:0 0 10px;color:var(--ink)}
#fxb-page.fxb-blog-page .fxb-article-body a{color:var(--purple-2);font-weight:800}
#fxb-page.fxb-blog-page .fxb-article-body a:hover{color:var(--orange)}
#fxb-page .fxb-related{max-width:760px;margin:44px auto 0}
#fxb-page .fxb-related h2{font-size:22px;font-weight:800;color:var(--ink);margin-bottom:14px}
#fxb-page .fxb-related-list{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
#fxb-page .fxb-related-list a{display:block;background:#fff;border:1px solid rgba(57,40,82,.08);border-radius:16px;padding:16px 18px;box-shadow:0 12px 28px -20px rgba(57,40,82,.35);color:var(--purple-2);font-weight:800;line-height:1.35}
#fxb-page .fxb-related-list a:hover{border-color:rgba(102,45,146,.22);color:var(--orange)}
#fxb-page.fxb-blog-page .fxb-article-body table{width:100%;border-collapse:collapse;margin:0 0 22px;font-size:15px;line-height:1.55;background:#fff;border-radius:14px;overflow:hidden;box-shadow:0 12px 28px -22px rgba(57,40,82,.35)}
#fxb-page.fxb-blog-page .fxb-article-body th{background:rgba(102,45,146,.08);color:var(--purple-2);font-weight:800;text-align:left;padding:12px 14px}
#fxb-page.fxb-blog-page .fxb-article-body td{padding:12px 14px;border-top:1px solid rgba(57,40,82,.08);color:var(--ink);vertical-align:top}
@media(max-width:860px){#fxb-page .fxb-related-list{grid-template-columns:repeat(2,1fr)}}
@media(max-width:680px){#fxb-page.fxb-blog-page .fxb-hero{padding:56px 18px 38px}#fxb-page .fxb-related-list{grid-template-columns:1fr}}
</style>
"""

FEED_CSS = """
<style>
#fxb-page.fxb-feed-page .fxb-hero{padding:66px 24px 48px}
#fxb-page.fxb-feed-page .fxb-hero-inner{max-width:940px}
#fxb-page.fxb-feed-page .fxb-h1{font-size:clamp(30px,4.4vw,48px);margin-bottom:14px}
#fxb-page.fxb-feed-page .fxb-sub{max-width:720px;font-size:16px;margin-bottom:0}
#fxb-page .fxb-feed-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}
#fxb-page .fxb-news-card{display:flex;flex-direction:column;background:#fff;border:1px solid rgba(57,40,82,.08);border-radius:20px;overflow:hidden;box-shadow:0 16px 36px -22px rgba(57,40,82,.4);transition:transform .45s cubic-bezier(.2,.8,.2,1),box-shadow .35s,border-color .35s,opacity .45s;opacity:0;transform:translateY(24px)}
#fxb-page .fxb-news-card.fxb-in{opacity:1;transform:none}
#fxb-page .fxb-news-card>a{display:block;color:inherit;height:100%}
#fxb-page .fxb-news-card:hover{transform:translateY(-6px);box-shadow:0 28px 50px -26px rgba(102,45,146,.5);border-color:rgba(102,45,146,.22)}
#fxb-page .fxb-news-card-body{padding:22px}
#fxb-page .fxb-news-badges{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px}
#fxb-page .fxb-news-badge{display:inline-flex;align-items:center;padding:7px 12px;border-radius:100px;background:rgba(102,45,146,.08);color:var(--purple-2);font-size:12px;font-weight:800;letter-spacing:.04em;text-transform:uppercase}
#fxb-page .fxb-news-date{color:var(--muted);font-size:13px;font-weight:600}
#fxb-page .fxb-news-card h2{font-size:20px;line-height:1.25;font-weight:800;margin:12px 0 10px;color:var(--ink)}
#fxb-page .fxb-news-card p{color:var(--muted);font-size:15px;line-height:1.6;margin-bottom:16px}
#fxb-page .fxb-news-link{display:inline-flex;align-items:center;gap:8px;color:var(--purple-2);font-weight:800}
#fxb-page .fxb-news-link:hover{color:var(--orange)}
@media(max-width:980px){#fxb-page .fxb-feed-grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:680px){#fxb-page.fxb-feed-page .fxb-hero{padding:56px 18px 40px}#fxb-page .fxb-feed-grid{grid-template-columns:1fr}}
</style>
"""

JS = """
<script>
(function(){
  var root=document.getElementById('fxb-page');if(!root)return;
  var items=root.querySelectorAll('.fxb-card,.fxb-fact,.fxb-book,.fxb-news-card');
  if('IntersectionObserver' in window){
    var io=new IntersectionObserver(function(es){es.forEach(function(e){
      if(e.isIntersecting){e.target.classList.add('fxb-in');io.unobserve(e.target);}
    })},{threshold:.15});
    items.forEach(function(el,i){el.style.transitionDelay=(i%4*70)+'ms';io.observe(el);});
  } else { items.forEach(function(el){el.classList.add('fxb-in');}); }
})();
</script>
"""

DECOR_SWIRL = "/assets/brand/decor-swirl-yellow-1.webp"
DECOR_FOX = "/assets/brand/fox-head-yellow.webp"
MYLEVEL = "/assets/brand/"
MAX_BOT = "https://max.ru/id611904726658_bot"
ROADMAP = "/assets/brand/roadmaps/"
TEAM_MEDIA = "/team-media/"
FOX_AVATAR = "/assets/brand/fox-head-yellow.webp"

ENGLISH_TEACHERS = [
    {"name": "Дмитроченко Юлия", "role": "Педагог английского языка", "photo": TEAM_MEDIA + "dmitrochenko.webp", "video": TEAM_MEDIA + "dmitrochenko.mp4", "lesson": TEAM_MEDIA + "dmitrochenko_lesson.mp4"},
    {"name": "Птицын Владислав", "role": "Педагог английского языка", "photo": TEAM_MEDIA + "ptitsyn.webp", "video": TEAM_MEDIA + "ptitsyn.mp4", "lesson": TEAM_MEDIA + "ptitsyn_lesson.mp4"},
    {"name": "Анохин Роман", "role": "Педагог английского языка", "photo": "/team-media/anokhin.webp"},
    {"name": "Саляхова Алина", "role": "Педагог английского и немецкого языков", "photo": TEAM_MEDIA + "salyahova.webp", "video": TEAM_MEDIA + "salyahova.mp4", "lesson": TEAM_MEDIA + "salyahova_lesson.mp4"},
    {"name": "Спорыхина Анастасия", "role": "Педагог английского и испанского языков", "photo": TEAM_MEDIA + "sporyhina.webp"},
    {"name": "Прокудина Мария", "role": "Педагог английского языка", "photo": TEAM_MEDIA + "prokudina.webp", "video": TEAM_MEDIA + "prokudina.mp4"},
    {"name": "Виноградова Анна", "role": "Педагог английского языка", "photo": TEAM_MEDIA + "vinogradova.webp", "video": TEAM_MEDIA + "vinogradova.mp4"},
]
GERMAN_TEACHERS = [
    {"name": "Саляхова Алина", "role": "Педагог немецкого языка", "photo": TEAM_MEDIA + "salyahova.webp", "video": TEAM_MEDIA + "salyahova.mp4", "lesson": TEAM_MEDIA + "salyahova_lesson.mp4"},
]
CHINESE_TEACHERS = [
    {"name": "Шевченко Дарья", "role": "Педагог китайского языка", "photo": TEAM_MEDIA + "shevchenko.webp", "video": TEAM_MEDIA + "shevchenko.mp4"},
]
SPANISH_TEACHERS = [
    {"name": "Спорыхина Анастасия", "role": "Педагог английского и испанского языков", "photo": TEAM_MEDIA + "sporyhina.webp"},
]


def feature_card(icon, title, text):
    return ('<article class="fxb-card"><div class="fxb-ic">' + svg(icon) +
            '</div><h3>' + title + '</h3><p>' + text + '</p></article>')


def card_grid_section(kicker, title, lead, cards, light=False):
    bg = " fxb-bg-light" if light else ""
    h = ['<section class="fxb-section' + bg + '"><div class="fxb-wrap">']
    h.append('<div class="fxb-head"><span class="fxb-kicker"><span class="fxb-dot"></span>' + kicker + '</span>')
    h.append('<h2 class="fxb-h2">' + title + '</h2>')
    if lead:
        h.append('<p class="fxb-lead">' + lead + '</p>')
    h.append('</div><div class="fxb-grid">')
    for c in cards:
        h.append(feature_card(*c))
    h.append('</div></div></section>')
    return "\n".join(h)


def teacher_team_section(title, lead, teachers):
    h = ['<section id="fxb-team">']
    h.append('<div class="fxb-section">')
    h.append('<div class="fxb-head">')
    h.append('<span class="fxb-eyebrow"><span class="fxb-dot"></span>Педагоги</span>')
    h.append('<h2 class="fxb-h2">' + title + '</h2>')
    if lead:
        h.append('<p class="fxb-sub">' + lead + '</p>')
    h.append('</div>')
    h.append('<div class="fxb-grid">')
    for t in teachers:
        h.append('<article class="fxb-card">')
        if t.get("photo"):
            h.append('<div class="fxb-photo" style="background-image:url(' + escape(t["photo"], quote=True) + ')"></div>')
        else:
            h.append('<div class="fxb-photo" style="background-image:linear-gradient(135deg,#2bb673,#7ed957)"><img class="fxb-ava" src="' + FOX_AVATAR + '" alt="" width="54" height="54"></div>')
        h.append('<div class="fxb-body">')
        h.append('<span class="fxb-role fxb-r-teacher">Педагог</span>')
        h.append('<h3>' + escape(t["name"]) + '</h3>')
        h.append('<p>' + escape(t["role"]) + '</p>')
        buttons = []
        if t.get("video"):
            buttons.append('<button class="fxb-vbtn" type="button" data-video="' + escape(t["video"], quote=True) + '"><svg width="14" height="14" viewBox="0 0 24 24" fill="#fff" stroke="none"><polygon points="5,3 19,12 5,21"/></svg> Видеовизитка</button>')
        if t.get("lesson"):
            buttons.append('<button class="fxb-vbtn fxb-vbtn-2" type="button" data-video="' + escape(t["lesson"], quote=True) + '"><svg width="14" height="14" viewBox="0 0 24 24" fill="#fff" stroke="none"><polygon points="5,3 19,12 5,21"/></svg> Фрагмент урока</button>')
        if buttons:
            h.append('<div class="fxb-btns">' + "".join(buttons) + '</div>')
        h.append('</div></article>')
    h.append('</div></div>')
    h.append('<div class="fxb-tvmod" id="fxbTeacherVideoModal"><div class="fxb-tvmod-bg"></div><div class="fxb-tvmod-box"><button class="fxb-tvmod-close" type="button" aria-label="Закрыть">&times;</button><div class="fxb-tvmod-frame"><div class="fxb-tvmod-empty">Видео появится здесь после добавления ссылки</div></div></div></div>')
    h.append('</section>')
    return "\n".join(h)


def price_section(title, lead, cards=None):
    h = ['<section class="fxb-section fxb-bg-light"><div class="fxb-wrap">']
    h.append('<div class="fxb-head"><span class="fxb-kicker"><span class="fxb-dot"></span>Стоимость</span>')
    h.append('<h2 class="fxb-h2">' + title + '</h2>')
    if lead:
        h.append('<p class="fxb-lead">' + lead + '</p>')
    h.append('</div>')
    h.append('<div class="fxb-price-grid">')
    if cards is None:
        cards = [
            ("Группа", "", '9 000 ₽<span>/мес</span>', "2 занятия в неделю · 60 минут · мини-группа"),
            ("Индивидуально", " fxb-price-tag--orange", '2 500 ₽<span>/час</span>', "Индивидуальный темп и гибкий график"),
            ("Пробный урок", "", "1 125 ₽", "Знакомство с педагогом и подбор формата"),
        ]
    for i, (tag, tag_mod, price_html, desc) in enumerate(cards):
        main = " fxb-price-card--main" if i == 0 else ""
        h.append('<article class="fxb-price-card' + main + '"><span class="fxb-price-tag' + tag_mod + '">' + tag +
                 '</span><h3>' + price_html + '</h3><p>' + desc + '</p></article>')
    h.append('</div>')
    h.append('<p class="fxb-price-note">Оплата материнским капиталом и налоговый вычет 13%.</p>')
    h.append('</div></section>')
    return "\n".join(h)


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


def faq_section(title, items, light=False):
    bg = " fxb-bg-light" if light else ""
    h = ['<section class="fxb-section' + bg + '"><div class="fxb-wrap">']
    h.append('<div class="fxb-head"><span class="fxb-kicker"><span class="fxb-dot"></span>Вопросы и ответы</span>')
    h.append('<h2 class="fxb-h2">' + title + '</h2></div>')
    h.append('<div class="fxb-faq">')
    for q, a in items:
        h.append('<details><summary>' + q + '</summary><p>' + a + '</p></details>')
    h.append('</div></div></section>')
    return "\n".join(h)


def ladder_section(kicker, title, lead, groups, light=False):
    bg = " fxb-bg-light" if light else ""
    h = ['<section class="fxb-section' + bg + '"><div class="fxb-wrap">']
    h.append('<div class="fxb-head"><span class="fxb-kicker"><span class="fxb-dot"></span>' + kicker + '</span>')
    h.append('<h2 class="fxb-h2">' + title + '</h2>')
    if lead:
        h.append('<p class="fxb-lead">' + lead + '</p>')
    h.append('</div>')
    for g in groups:
        group_name = g.get("group", "")
        if group_name:
            h.append('<h3 class="fxb-ladder-sub">' + escape(group_name) + '</h3>')
        h.append('<div class="fxb-ladder">')
        for level_title, meta, img in g["items"]:
            level_title_e = escape(level_title)
            meta_e = escape(meta)
            img_e = escape(img, quote=True)
            h.append(
                '<a class="fxb-step" href="' + img_e + '" target="_blank" rel="noopener">'
                '<div class="fxb-step-prev"><img src="' + img_e + '" alt="' + level_title_e + '" loading="lazy"></div>'
                '<div class="fxb-step-body"><h4>' + level_title_e + '</h4><span>' + meta_e + '</span>'
                '<span class="fxb-step-link">Открыть программу →</span></div></a>'
            )
        h.append('</div>')
    h.append('</div></section>')
    return "\n".join(h)


def video_section(kicker, title, lead, src, poster, light=False):
    bg = " fxb-bg-light" if light else ""
    h = ['<section class="fxb-section' + bg + '"><div class="fxb-wrap">']
    h.append('<div class="fxb-head"><span class="fxb-kicker"><span class="fxb-dot"></span>' + kicker + '</span>')
    h.append('<h2 class="fxb-h2">' + title + '</h2>')
    if lead:
        h.append('<p class="fxb-lead">' + lead + '</p>')
    h.append('</div><div class="fxb-video-wrap"><div class="fxb-video">')
    h.append('<video controls playsinline preload="metadata" poster="' + escape(poster, quote=True) + '">')
    h.append('<source src="' + escape(src, quote=True) + '" type="video/mp4">')
    h.append('</video></div></div></div></section>')
    # VideoObject — видео-страницы попадают в видео-поиск; дата неизвестна → без uploadDate
    payload = json.dumps({
        "@context": "https://schema.org", "@type": "VideoObject",
        "name": re.sub(r"<[^>]+>", "", title),
        "description": lead or re.sub(r"<[^>]+>", "", title),
        "contentUrl": SITE + src,
        "thumbnailUrl": SITE + poster,
        "inLanguage": "ru", "isFamilyFriendly": True,
    }, ensure_ascii=False)
    h.append('<script type="application/ld+json">' + payload + '</script>')
    return "\n".join(h)


def format_date_ru(date_str):
    y, m, d = map(int, date_str.split("-"))
    return f"{d} {RU_MONTHS[m]} {y}"


def render_article_body(items):
    parts = []
    pre = []
    prose = []
    for kind, value in items:
        if kind == "video":
            pre.append(video_section(
                value.get("kicker", "Видео"),
                value["title"],
                value.get("lead"),
                value["src"],
                value["poster"],
                light=True,
            ))
        elif kind in ("h2", "h3"):
            prose.append(f"<{kind}>{value}</{kind}>")
        elif kind == "p":
            prose.append(f"<p>{value}</p>")
        elif kind == "ul":
            prose.append("<ul>" + "".join(f"<li>{li}</li>" for li in value) + "</ul>")
        elif kind == "html":
            prose.append(value)
    if prose:
        parts.append('<div class="fxb-article-body">' + "\n".join(prose) + '</div>')
    return pre, "\n".join(parts)


def landing_page(p):
    """p: dict with page content."""
    grad = p["hero_grad"]
    h = []
    # Шрифт Montserrat — self-hosted, подключается в build_head
    # (build_static_site.py, FONT_FACE_STYLE), здесь <link> не нужен.
    page_class = p.get("page_class", "")
    cls = ' class="' + page_class + '"' if page_class else ""
    h.append('<div id="fxb-page"' + cls + ' data-fxb-glow="' + p.get("glow", "blue") + '">')
    # HERO (story_hero — fullscreen фото + glass-card; иначе стандартный градиентный)
    if p.get("story_hero"):
        sh = dict(p["story_hero"])
        # крошки нужны и на story-hero: выводим в glass-карточке перед eyebrow
        _crumbs = crumbs_from_extra(p.get("extra_jsonld"))
        h.append(media_library.story_hero(**sh))
    else:
        h.append('<section class="fxb-hero" style="background:' + grad + '">')
        h.append('<div class="fxb-hero-bg"><img class="fxb-hd1" src="' + DECOR_SWIRL + '" alt="" loading="lazy"><img class="fxb-hd2" src="' + DECOR_FOX + '" alt="" loading="lazy"></div>')
        h.append('<div class="fxb-hero-inner">')
        # Видимые хлебные крошки с микроразметкой (сессия 62) — из того же
        # BreadcrumbList, что уходит в JSON-LD: единый источник правды.
        _crumbs = crumbs_from_extra(p.get("extra_jsonld"))
        if _crumbs:
            h.append(crumbs_nav(_crumbs))
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
    if p.get("advantages"):
        h.append(card_grid_section(p.get("adv_kicker", "Почему мы"), p["adv_title"], p.get("adv_lead"), p["advantages"], light=False))
    if p.get("teachers"):
        h.append(teacher_team_section(p.get("team_title", "Наши <span class=\"fxb-accent\">педагоги</span>"), p.get("team_lead", "Команда преподавателей, которые ведут уроки в мини-группах и на индивидуальных занятиях."), p["teachers"]))
    elif p.get("team"):
        h.append(card_grid_section("Педагоги", p["team_title"], p.get("team_lead"), p["team"], light=True))
    if p.get("formats"):
        h.append(card_grid_section(p.get("formats_kicker", "Варианты обучения"), p.get("formats_title", "Форматы занятий"), p.get("formats_lead"), p["formats"], light=False))
    if p.get("prices"):
        h.append(price_section(p.get("price_title", "Стоимость обучения"), p.get("price_lead", "Прозрачные тарифы и удобные форматы оплаты."), p.get("price_cards")))
    if p.get("ladder"):
        h.append(ladder_section(p.get("ladder_kicker", "Лестница знаний"), p["ladder_title"], p.get("ladder_lead"), p["ladder"], light=False))
    if p.get("video"):
        v = p["video"]
        h.append(video_section(v.get("kicker", "Видео"), v["title"], v.get("lead"), v["src"], v["poster"], light=True))
    # EXTRA SECTIONS (готовый HTML, например текстовые блоки fxb-article-body)
    if p.get("extra_sections"):
        for section_html in p["extra_sections"]:
            h.append(section_html)
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
    if p.get("faq"):
        h.append(faq_section(p.get("faq_title", "Частые вопросы"), p["faq"], light=False))
        h.append(faq_jsonld(p["faq"]))
    # EXTRA JSON-LD (Course/BreadcrumbList/WebPage и т.п., инлайн в контент
    # страницы — как article_jsonld() у статей; seo_schema/ не трогаем)
    if p.get("extra_jsonld"):
        for schema_html in p["extra_jsonld"]:
            h.append(schema_html)
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
    if p.get("ladder"):
        h.append(LADDER_CSS)
    if p.get("video"):
        h.append(VIDEO_CSS)
    if p.get("has_video_story"):
        h.append(VIDEO_CSS)
    if p.get("teachers"):
        h.append(TEAM_CSS)
        h.append(TEAM_JS)
    if p.get("prices"):
        h.append(PRICE_CSS)
    if p.get("article_css"):
        h.append(ARTICLE_CSS)
    h.append(JS)
    return "\n".join(h)


def faq_jsonld(items):
    """FAQPage JSON-LD из того же списка вопросов, что и визуальный блок FAQ —
    разметка не расходится с контентом страницы."""
    def plain(s):
        return re.sub(r"<[^>]+>", "", s).strip()
    faq = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": plain(q),
                "acceptedAnswer": {"@type": "Answer", "text": plain(a)},
            }
            for q, a in items
        ],
    }
    return ('<script type="application/ld+json">'
            + json.dumps(faq, ensure_ascii=False) + '</script>')


def crumbs_nav(items):
    """Видимые хлебные крошки с микроразметкой Schema.org (нужна Яндексу
    для навигационной цепочки в выдаче). items: [(name, url|None), ...]."""
    lis = []
    for i, (name, url) in enumerate(items):
        pos = '<meta itemprop="position" content="' + str(i + 1) + '">'
        if url:
            inner = ('<a itemprop="item" href="' + escape(url, quote=True) + '">'
                     '<span itemprop="name">' + escape(name) + '</span></a>' + pos)
        else:
            inner = '<span itemprop="name">' + escape(name) + '</span>' + pos
        lis.append('<li itemprop="itemListElement" itemscope itemtype="https://schema.org/ListItem">' + inner + '</li>')
    return ('<nav class="fxb-breadcrumbs" aria-label="Хлебные крошки">'
            '<ol itemscope itemtype="https://schema.org/BreadcrumbList">'
            + ''.join(lis) + '</ol></nav>')


def crumbs_from_extra(extra_jsonld):
    """Достаёт [(name, url), ...] из BreadcrumbList JSON-LD (сессия 62):
    видимые крошки строятся из того же источника, что и разметка."""
    for schema_html in extra_jsonld or []:
        m = re.search(r'<script type="application/ld\+json">(.*?)</script>', schema_html, re.S)
        if not m:
            continue
        try:
            d = json.loads(m.group(1))
        except ValueError:
            continue
        if d.get("@type") == "BreadcrumbList":
            items = [(el.get("name", ""), el.get("item")) for el in d.get("itemListElement", [])]
            # последний пункт — текущая страница: в видимых крошках без ссылки
            if items:
                items[-1] = (items[-1][0], None)
            return items
    return None


def breadcrumb_jsonld(items):
    """BreadcrumbList JSON-LD. items: [(name, url), ...] — как seo_schema/breadcrumb_*.html,
    только инлайн (seo_schema/ в этой сессии не редактируем)."""
    bc = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": name, "item": url}
            for i, (name, url) in enumerate(items)
        ],
    }
    return ('<script type="application/ld+json">'
            + json.dumps(bc, ensure_ascii=False) + '</script>')


def course_jsonld(name, description, url, offer_name=None, price=None):
    """Course JSON-LD по образцу seo_schema/course_oge-anglijskij.html:
    provider — sitewide Organization (@id), опционально Offer."""
    course = {
        "@context": "https://schema.org",
        "@type": "Course",
        "name": name,
        "description": description,
        "url": url,
        "provider": {"@id": SITE + "/#organization"},
        "hasCourseInstance": {
            "@type": "CourseInstance",
            "courseMode": "blended",
            "courseWorkload": "PT1H",
            "location": {"@id": SITE + "/#branch-lichachevsky"},
        },
    }
    if offer_name and price:
        course["hasCourseInstance"]["offers"] = {
            "@type": "Offer",
            "name": offer_name,
            "price": price,
            "priceCurrency": "RUB",
            "availability": "https://schema.org/InStock",
            "url": url,
        }
    return ('<script type="application/ld+json">'
            + json.dumps(course, ensure_ascii=False) + '</script>')


def webpage_jsonld(page_type, name, description, url,
                   date_published=None, date_modified=None):
    """WebPage/AboutPage JSON-LD для служебных страниц (/otzyvy, /about).
    Ссылается на sitewide Organization/WebSite через @id (org_localbusiness.html).
    Для story-страниц можно передать реальные даты события/обновления."""
    import datetime as _dt
    page = {
        "@context": "https://schema.org",
        "@type": page_type,
        "name": name,
        "description": description,
        "url": url,
        "inLanguage": "ru-RU",
        "isPartOf": {"@id": SITE + "/#website"},
        "about": {"@id": SITE + "/#organization"},
        "publisher": {"@id": SITE + "/#organization"},
    }
    if date_published:
        page["datePublished"] = date_published
    # dateModified — дата сборки (свежесть для поисковиков), если не задана явно
    page["dateModified"] = date_modified or _dt.date.today().isoformat()
    return ('<script type="application/ld+json">'
            + json.dumps(page, ensure_ascii=False) + '</script>')


def article_jsonld(p):
    url = SITE + "/" + p["alias"]
    feed_alias = p.get("feed_alias", "novosti")
    feed_label = p.get("feed_label", "Новости")
    article = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": p["title"],
        "description": p["description"],
        "datePublished": p["date"],
        "author": {"@type": "Organization", "name": "Языковая школа Фоксинбург"},
        "publisher": {"@type": "Organization", "name": "Языковая школа Фоксинбург"},
        "mainEntityOfPage": {"@type": "WebPage", "@id": url, "url": url},
    }
    breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Главная", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": feed_label, "item": SITE + "/" + feed_alias},
            {"@type": "ListItem", "position": 3, "name": p["title"], "item": url},
        ],
    }
    return (
        '<script type="application/ld+json">' + json.dumps(article, ensure_ascii=False) + '</script>\n'
        '<script type="application/ld+json">' + json.dumps(breadcrumb, ensure_ascii=False) + '</script>'
    )


def news_card(p):
    return (
        '<article class="fxb-news-card">'
        '<a href="/' + escape(p["alias"], quote=True) + '">'
        '<div class="fxb-news-card-body">'
        '<div class="fxb-news-badges"><span class="fxb-news-badge">' + escape(p["category"]) + '</span>'
        '<span class="fxb-news-date">' + escape(format_date_ru(p["date"])) + ' · ' + escape(p["reading_time"]) + '</span></div>'
        '<h2>' + escape(p["title"]) + '</h2>'
        '<p>' + escape(p["description"]) + '</p>'
        '<span class="fxb-news-link">Читать →</span>'
        '</div></a></article>'
    )


def feed_page(p):
    h = []
    h.append('<div id="fxb-page" class="fxb-feed-page" data-fxb-glow="' + p.get("glow", "pink") + '">')
    h.append('<section class="fxb-hero" style="background:' + p["hero_grad"] + '">')
    h.append('<div class="fxb-hero-bg"><img class="fxb-hd1" src="' + DECOR_SWIRL + '" alt="" loading="lazy"><img class="fxb-hd2" src="' + DECOR_FOX + '" alt="" loading="lazy"></div>')
    h.append('<div class="fxb-hero-inner">')
    _crumbs = crumbs_from_extra(p.get("extra_jsonld"))
    if _crumbs:
        h.append(crumbs_nav(_crumbs))
    h.append('<span class="fxb-eyebrow"><span class="fxb-dot"></span>' + p["eyebrow"] + '</span>')
    h.append('<h1 class="fxb-h1">' + p["h1"] + '</h1>')
    h.append('<p class="fxb-sub">' + p["sub"] + '</p>')
    h.append('</div></section>')
    h.append('<section class="fxb-section"><div class="fxb-wrap">')
    h.append('<div class="fxb-head"><span class="fxb-kicker"><span class="fxb-dot"></span>' + p.get("feed_kicker", "Архив") + '</span>')
    h.append('<h2 class="fxb-h2">' + p.get("feed_title", "Последние статьи") + '</h2>')
    if p.get("lead"):
        h.append('<p class="fxb-lead">' + p["lead"] + '</p>')
    h.append('</div>')
    if p.get("intro_html"):
        h.append(p["intro_html"])
    h.append('<div class="fxb-feed-grid">')
    for art in sorted(p["articles"], key=lambda a: a["date"], reverse=True):
        h.append(news_card(art))
    h.append('</div></div></section>')
    if p.get("extra_jsonld"):
        for schema_html in p["extra_jsonld"]:
            h.append(schema_html)
    h.append('</div>')
    h.append(CSS)
    h.append(FEED_CSS)
    h.append(JS)
    return "\n".join(h)


def article_page(p):
    h = []
    h.append('<div id="fxb-page" class="fxb-blog-page" data-fxb-glow="' + p.get("glow", "pink") + '">')
    h.append('<section class="fxb-hero" style="background:' + p["hero_grad"] + '">')
    h.append('<div class="fxb-hero-bg"><img class="fxb-hd1" src="' + DECOR_SWIRL + '" alt="" loading="lazy"><img class="fxb-hd2" src="' + DECOR_FOX + '" alt="" loading="lazy"></div>')
    h.append('<div class="fxb-hero-inner">')
    h.append('<span class="fxb-eyebrow"><span class="fxb-dot"></span>' + escape(p["category"]) + '</span>')
    h.append('<h1 class="fxb-h1">' + p["title"] + '</h1>')
    h.append('<div class="fxb-article-meta"><span>' + escape(format_date_ru(p["date"])) + '</span><span>' + escape(p["reading_time"]) + '</span></div>')
    h.append('</div></section>')
    h.append('<section class="fxb-section"><div class="fxb-wrap">')
    h.append(crumbs_nav([("Главная", "/"), (p.get("feed_label", "Новости"), "/" + p.get("feed_alias", "novosti")), (p["title"], None)]))
    pre_blocks, prose_html = render_article_body(p["body"])
    for block in pre_blocks:
        h.append(block)
    h.append(prose_html)
    if p.get("related"):
        h.append('<div class="fxb-related"><h2>Читайте также</h2><div class="fxb-related-list">')
        for label, href in p["related"]:
            h.append('<a href="' + escape(href, quote=True) + '">' + escape(label) + '</a>')
        h.append('</div></div>')
    h.append('</div></section>')
    if p.get("faq"):
        h.append(faq_section(p.get("faq_title", "Частые вопросы"), p["faq"], light=True))
        h.append(faq_jsonld(p["faq"]))
    h.append('<section class="fxb-cta" id="fxb-cta"><div class="fxb-cta-bg"><img src="' + DECOR_FOX + '" alt="" loading="lazy"></div><div class="fxb-cta-box"><h2>Читайте также и запишитесь на <span class="fxb-accent">бесплатную диагностику</span></h2><p>Если хотите подобрать подходящий курс или задать вопросы по программе, оставьте заявку — мы свяжемся с вами.</p><div class="fxb-cta-btns"><a data-fxb-zayavka data-fxb-subject="Бесплатная диагностика" data-fxb-window="Блог" role="button" tabindex="0" class="fxb-btn-main">Оставить заявку</a><a href="' + MAX_BOT + '" target="_blank" rel="noopener" class="fxb-btn-max">' + svg("chat") + 'Написать в Max</a></div></div></section>')
    h.append(article_jsonld(p))
    h.append(zayavka_unit())
    h.append('</div>')
    h.append(CSS)
    h.append(ARTICLE_CSS)
    if p.get("video") or any(k == "video" for k, _ in p.get("body", [])):
        h.append(VIDEO_CSS)
    h.append(JS)
    return "\n".join(h)


def render_page(p):
    if p.get("type") == "article":
        return article_page(p)
    if p.get("type") == "feed":
        return feed_page(p)
    return landing_page(p)


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
        ("group", "Мини-группы до 7 детей", "Педагог уделяет внимание каждому ребёнку и видит прогресс каждого."),
        ("music", "Полное погружение", "Занятие полностью на английском — ребёнок привыкает к звучанию языка естественно."),
        ("chart", "Видимый прогресс", "Регулярная обратная связь родителям. Первые фразы — уже через месяц занятий."),
    ],
    "facts_title": "Коротко о занятиях",
    "facts": [
        ("calendar", "2 раза / нед", "Регулярность для устойчивого результата"),
        ("clock", "45 минут", "Оптимально для концентрации малышей"),
        ("sun", "Утренние группы", "Для тех, кто ходит в сад во вторую смену"),
        ("group", "До 7 человек", "Камерные группы по возрасту и уровню"),
    ],
    "video": {
        "kicker": "Видео",
        "title": "Как проходят занятия у дошкольников",
        "lead": "Небольшой фрагмент реального занятия — с игрой, движением и речевой практикой.",
        "src": "/media/doshkolniki.mp4",
        "poster": "/media/doshkolniki-poster.webp",
    },
    "teachers": ENGLISH_TEACHERS,
    "prices": True,
    "extra_sections": [
        media_library.life_bundle(
            media_library.media_wall(
                series="2026-08-22-canon", limit=6,
                title="Лиса Фокси и наши малыши", kicker="Реальные фото · август 2026",
            ),
        ),
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
    "teachers": ENGLISH_TEACHERS,
    "prices": True,
    "ladder_title": 'Лестница знаний — программа по <span class="fxb-accent">годам</span>',
    "ladder_lead": "Наши курсы для младших школьников по ступеням: посмотрите подробную карту тем на учебный год по каждому уровню.",
    "ladder": [
        {"group":"Английский · My level", "items":[
           ("My level 1", "6–8 лет · Pre-A1", ROADMAP+"my-level-1.webp"),
           ("My level 2", "8–9 лет · Pre-A1 → A1", ROADMAP+"my-level-2.webp"),
           ("My level 3", "9–10 лет · A1", ROADMAP+"my-level-3.webp"),
           ("My level 4", "10–11 лет · A1 → A2", ROADMAP+"my-level-4.webp"),
        ]},
        {"group":"Английский · Super Minds", "items":[
           ("Super Minds 1", "7–8 лет · Pre-A1", ROADMAP+"super-minds-1.webp"),
           ("Super Minds 2", "8–9 лет · A1", ROADMAP+"super-minds-2.webp"),
           ("Super Minds 3", "9–10 лет · A1–A2", ROADMAP+"super-minds-3.webp"),
           ("Super Minds 4", "10–11 лет · A2", ROADMAP+"super-minds-4.webp"),
        ]},
        {"group":"Китайский язык", "items":[
           ("Веселый урок", "1–4 класс · 中文 HSK 1", ROADMAP+"veselyj-urok-1-4-klass.webp"),
        ]},
    ],
    "lead_subject": "Английский для младших школьников",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "extra_sections": [
        media_library.life_bundle(
            media_library.media_wall(
                series="2026-04-09-canon", limit=6,
                title="Весенняя Академия 2026", kicker="Реальные фото",
            ),
            media_library.video_story(
                "no-date-other/Describe and guess an animal ",
                "Игра на уроке: Describe and guess",
                "Опиши животное — пусть другие угадают. Вся игра — на английском.",
                kicker="Видео с занятия",
            ),
        ),
    ],
    "has_video_story": True,
    "books": [
        ("My Level 1", "6–8 лет, 1-й год обучения. Уровень Pre-A1. Старт с азов: алфавит, фоника и первые фразы, чтение по Read with Richie.", MYLEVEL + "mylevel-1.webp"),
        ("My Level 2", "8–9 лет, 2-й год обучения. Уровень Pre-A1 → A1. Расширяем лексику и грамматику, больше чтения с Richie's Adventures.", MYLEVEL + "mylevel-2.webp"),
        ("My Level 3", "9–10 лет, 3-й год обучения. Уровень A1. Уверенное чтение и грамматика, отработка лексики по Move It 1.", MYLEVEL + "mylevel-3.webp"),
        ("My Level 4", "10–11 лет, 4-й год обучения. Уровень A1 → A2. Сложнее тексты и грамматика по Move It 2, мягкая подготовка к Кембриджским экзаменам YLE.", MYLEVEL + "mylevel-4.webp"),
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
    "ladder_title": 'Лестница знаний — программа по <span class="fxb-accent">годам</span>',
    "ladder_lead": "Курсы для подростков по ступеням: откройте карту тем на учебный год по каждому уровню.",
    "ladder": [
        {"group":"Английский · Get involved", "items":[
           ("Get involved A1", "11–13 лет · A1", ROADMAP+"get-involved-a1.webp"),
           ("Get involved A2", "12–14 лет · A2", ROADMAP+"get-involved-a2.webp"),
        ]},
        {"group":"Китайский язык", "items":[
           ("Открывая Китай", "5 класс + · 中文 HSK 1–2", ROADMAP+"otkryvaya-kitaj-5-klass.webp"),
        ]},
    ],
    "teachers": ENGLISH_TEACHERS,
    "prices": True,
    "extra_sections": [
        media_library.life_bundle(
            media_library.media_wall(
                series="2026-04-07-canon", limit=6,
                title="Весенняя Академия 2026", kicker="Реальные фото",
            ),
            media_library.video_story(
                "no-date-other/Ask and answer in pairs",
                "Игра на уроке: Ask and answer in pairs",
                "Работа в парах: задать вопрос и ответить — по-английски, конечно.",
                kicker="Видео с занятия",
            ),
        ),
    ],
    "has_video_story": True,
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
    "hero_grad": "linear-gradient(135deg,#c24712 0%,#f7971e 50%,#fcc419 100%)",
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
        ("group", "Мини-группы до 7", "Формирование по уровню и возрасту, максимум практики для каждого."),
        ("sun", "Первая половина дня", "Свободный день у ребёнка остаётся — занятия проходят утром."),
    ],
    "facts_title": "Коротко о смене",
    "facts": [
        ("calendar", "2–4 недели", "Гибкий выбор удобного периода"),
        ("clock", "Утро", "Занятия в первой половине дня"),
        ("group", "До 8 человек", "Группы по возрасту и уровню"),
        ("target", "Без потери формы", "Поддерживаем уровень за лето"),
    ],
    "video": {
        "kicker": "Как это проходит",
        "title": 'Летняя Академия — <span class="fxb-accent">вживую</span>',
        "lead": "Атмосфера смены: как проходят занятия, проекты и общение в Академии.",
        "src": "/media/summer-academy.mp4",
        "poster": "/media/summer-academy-poster.webp",
    },
    "extra_sections": [
        media_library.life_bundle(
            media_library.video_story(
                "2025-05-28-other/8686004881408589323",
                "Как это было: Летняя Академия 2025",
                "Тематический клуб «Harry Potter» вживую: распределение по группам и погружение в атмосферу — архивное видео прошлой смены.",
                kicker="Из архива · 2025",
                light=False,
            ),
        ),
        (
            '<section class="fxb-section"><div class="fxb-wrap">'
            '<div class="fxb-head"><span class="fxb-kicker"><span class="fxb-dot"></span>Истории</span>'
            '<h2 class="fxb-h2">Академии и экскурсии в деталях</h2>'
            '<p class="fxb-lead">Настоящие фото и видео наших смен и выездов — без постановки.</p></div>'
            '<p style="display:flex;gap:12px;flex-wrap:wrap">'
            '<a class="fxb-btn-main" href="/vesennyaya-akademiya-2026">Весенняя Академия 2026</a>'
            '<a class="fxb-btn-main" href="/ekskursii">Экскурсии: Ю-Клиника и пожарная станция</a>'
            '</p></div></section>'
        ),
    ],
    "has_video_story": True,
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
    "prices": True,
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
    "prices": True,
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
    "prices": True,
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
    "teachers": ENGLISH_TEACHERS,
    "prices": True,
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
    "teachers": ENGLISH_TEACHERS,
    "prices": True,
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
    "teachers": ENGLISH_TEACHERS,
    "prices": True,
    "price_title": "Стоимость занятий",
    "price_lead": "Подготовка к школе и занятия по общим предметам (математика, русский язык, чтение) — 7 000 ₽/мес.",
    "price_cards": [
        ("Месяц занятий", "", '7 000 ₽<span>/мес</span>', "Подготовка к школе и общие предметы: математика, русский язык, чтение"),
    ],
    "lead_subject": "Подготовка к школе",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "cta_title": 'Проведите <span class="fxb-accent">лето с пользой</span>',
    "cta_text": "Оставьте заявку и получите купон на комплексную диагностику ребёнка.",
}

# ----- новые посадочные под спрос (ОГЭ, ЕГЭ, взрослые, немецкий, китайский) -----
PAGES["page_oge_anglijskij.html"] = {
    "hero_grad": "linear-gradient(135deg,#1e1433 0%,#4a2a7a 55%,#662d92 100%)",
    "eyebrow": "Подготовка к ОГЭ · 9 класс",
    "h1": 'Подготовка к <span class="fxb-accent">ОГЭ</span> по английскому',
    "sub": "Системная подготовка к ОГЭ по английскому в Долгопрудном: разбираем все разделы экзамена, тренируем формат и снимаем страх перед устной частью.",
    "cta_label": "Записаться на диагностику",
    "feat_kicker": "Что входит",
    "feat_title": "Как готовим к ОГЭ",
    "feat_lead": "Работаем над каждым разделом экзамена и доводим формат до автоматизма.",
    "features": [
        ("check", "Все разделы экзамена", "Аудирование, чтение, грамматика и лексика, письмо и устная часть — прорабатываем каждый раздел ОГЭ."),
        ("mic", "Устная часть без страха", "Тренируем монолог и диалог по формату ОГЭ, чтобы на экзамене ученик говорил уверенно."),
        ("target", "Разбор критериев", "Показываем, как эксперты оценивают ответы, и учим не терять баллы на формальностях."),
        ("chart", "Пробные экзамены", "Регулярные пробники в реальном формате и тайминге — видны прогресс и слабые места."),
    ],
    "facts_title": "Коротко о подготовке",
    "facts": [
        ("cap", "9 класс", "Для тех, кто сдаёт ОГЭ"),
        ("calendar", "2 раза / нед", "Регулярная отработка формата"),
        ("clock", "60 минут", "Полноценное занятие с практикой"),
        ("chat", "1 на 1", "Индивидуальные занятия с педагогом"),
    ],
    "formats_title": "Форматы занятий",
    "formats_lead": "Подготовка к ОГЭ — индивидуальная: очно в филиалах или онлайн, расписание под ваш ритм.",
    "formats": [
        ("compass", "Очно в двух филиалах", "Занятия в Долгопрудном — на Лихачевского, 76к1 и на Ракетостроителей, 9к3."),
        ("monitor", "Онлайн с педагогом", "Живые видеоуроки с разбором заданий и обратной связью в реальном времени."),
        ("chat", "Индивидуально 1 на 1", "Персональный план под цель и текущий уровень — весь темп и фокус занятия ваш."),
        ("cap", "Подготовка к экзамену", "Диагностика, разбор критериев, пробные варианты и стратегия на сам экзамен."),
    ],
    "teachers": ENGLISH_TEACHERS,
    "prices": True,
    "price_title": "Стоимость подготовки к ОГЭ",
    "price_lead": "Подготовка к ОГЭ по английскому ведём индивидуально — 2 500 ₽/час. Первый шаг — бесплатная диагностика.",
    "price_cards": [
        ("Индивидуально", " fxb-price-tag--orange", '2 500 ₽<span>/час</span>', "Занятие 1 на 1 с педагогом · 60 минут · гибкий график"),
    ],
    "adv_title": 'Почему выбирают <span class="fxb-accent">Фоксинбург</span>',
    "adv_lead": "Языковая школа в Долгопрудном с 2020 года — с лицензией, своей методикой и вниманием к каждому ученику.",
    "advantages": [
        ("shield", "Лицензия и опыт с 2020 года", "Официальная образовательная лицензия и годы практики в обучении детей и взрослых."),
        ("check", "Маткапитал и налоговый вычет", "Занятия можно оплатить материнским капиталом и вернуть 13% стоимости налоговым вычетом."),
        ("target", "Индивидуальный план", "Подготовка 1 на 1: программа строится под пробелы и цель конкретного ученика."),
        ("chart", "Ежемесячный отчёт", "Каждый месяц — подробный индивидуальный отчёт от педагога об успеваемости ребёнка."),
        ("monitor", "Оффлайн и онлайн", "Два филиала в Долгопрудном рядом с МФТИ и удобный онлайн-формат — как вам удобно."),
        ("star", "Рейтинг 5,0 и своё приложение", "Высокие оценки родителей и мобильное приложение, где дети тренируют слова и копят награды."),
    ],
    "team_title": 'Кто готовит к <span class="fxb-accent">ОГЭ</span>',
    "team_lead": "Подготовку ведут преподаватели, которые знают формат ОГЭ и критерии оценивания — и умеют объяснять понятно.",
    "team": [
        ("cap", "Знают формат экзамена", "Разбираемся в структуре ОГЭ и критериях — учим набирать баллы, а не просто «знать язык»."),
        ("rocket", "Постоянно развиваются", "Своя система подготовки педагогов: регулярное повышение квалификации по методике школы."),
        ("chat", "Снимают страх экзамена", "Поддерживают, разбирают ошибки без давления — на экзамен ученик идёт спокойно."),
        ("chart", "Держат связь с родителями", "Индивидуальный подход и регулярная обратная связь о прогрессе подготовки."),
    ],
    "faq_title": "Частые вопросы про подготовку к ОГЭ",
    "faq": [
        ("С какого класса начинать подготовку к ОГЭ?", "Оптимально — за год-полтора до экзамена, с 8–9 класса. Но подключиться можно на любом этапе: начнём с диагностики и составим план."),
        ("А если у ребёнка слабый уровень?", "Начнём с бесплатной диагностики, составим индивидуальный план и подтянем базу параллельно с отработкой формата экзамена."),
        ("Можно ли оплатить материнским капиталом?", "Да. Занятия можно оплатить материнским капиталом, а также вернуть 13% стоимости налоговым вычетом."),
        ("Занятия очно или онлайн?", "Есть оба формата: очно в Долгопрудном (два филиала рядом с МФТИ) и онлайн."),
        ("Занятия в группе или индивидуально?", "Подготовку к ОГЭ по английскому ведём индивидуально — так педагог закрывает именно ваши пробелы, а формат отрабатывается в вашем темпе."),
    ],
    "lead_subject": "Подготовка к ОГЭ по английскому",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "cta_title": 'Узнайте готовность к ОГЭ на <span class="fxb-accent">бесплатной диагностике</span>',
    "cta_text": "Определим текущий уровень, покажем пробелы и составим план подготовки к экзамену.",
}

PAGES["page_ege_anglijskij.html"] = {
    "hero_grad": "linear-gradient(135deg,#241a36 0%,#5a2d8f 55%,#8a4fb8 100%)",
    "eyebrow": "Подготовка к ЕГЭ · 10–11 класс",
    "h1": 'Подготовка к <span class="fxb-accent">ЕГЭ</span> по английскому',
    "sub": "Готовим к ЕГЭ по английскому в Долгопрудном: все разделы экзамена, эссе по критериям и уверенная устная часть — на высокий балл.",
    "cta_label": "Записаться на диагностику",
    "feat_kicker": "Что входит",
    "feat_title": "Как готовим к ЕГЭ",
    "feat_lead": "Системно отрабатываем каждый раздел и учим набирать баллы строго по критериям.",
    "features": [
        ("check", "Все разделы ЕГЭ", "Аудирование, чтение, грамматика и лексика, письмо и устная часть — системная отработка каждого блока."),
        ("pencil", "Эссе и письмо по критериям", "Учим писать письмо и развёрнутое высказывание строго по критериям — без потери баллов на структуре."),
        ("mic", "Устная часть", "Отрабатываем все задания говорения по формату и таймингу ЕГЭ."),
        ("chart", "Пробные ЕГЭ", "Регулярные пробники в реальных условиях и подробный разбор ошибок с преподавателем."),
    ],
    "facts_title": "Коротко о подготовке",
    "facts": [
        ("cap", "10–11 класс", "Для будущих выпускников"),
        ("calendar", "2 раза / нед", "Системная подготовка"),
        ("clock", "60–90 минут", "Интенсивные занятия"),
        ("chat", "1 на 1", "Индивидуальные занятия с педагогом"),
    ],
    "formats_title": "Форматы занятий",
    "formats_lead": "Подготовка к ЕГЭ — индивидуальная: очно или онлайн, расписание под ваш ритм и дедлайн экзамена.",
    "formats": [
        ("compass", "Очно в двух филиалах", "Занятия в Долгопрудном — на Лихачевского, 76к1 и на Ракетостроителей, 9к3."),
        ("monitor", "Онлайн с педагогом", "Живые видеоуроки с разбором критериев, эссе и устной части."),
        ("chat", "Индивидуально 1 на 1", "Весь темп и фокус занятия — на вашем результате и слабых разделах."),
        ("target", "Под ЕГЭ и высокий балл", "Диагностика, критерии, пробники и стратегия на нужный результат."),
    ],
    "teachers": ENGLISH_TEACHERS,
    "prices": True,
    "price_title": "Стоимость подготовки к ЕГЭ",
    "price_lead": "Подготовка к ЕГЭ по английскому ведём индивидуально — 2 500 ₽/час. Первый шаг — бесплатная диагностика.",
    "price_cards": [
        ("Индивидуально", " fxb-price-tag--orange", '2 500 ₽<span>/час</span>', "Занятие 1 на 1 с педагогом · 60–90 минут · гибкий график"),
    ],
    "adv_title": 'Почему выбирают <span class="fxb-accent">Фоксинбург</span>',
    "adv_lead": "Языковая школа в Долгопрудном с 2020 года — с лицензией, своей методикой и вниманием к каждому ученику.",
    "advantages": [
        ("shield", "Лицензия и опыт с 2020 года", "Официальная образовательная лицензия и годы практики в обучении детей и взрослых."),
        ("check", "Маткапитал и налоговый вычет", "Занятия можно оплатить материнским капиталом и вернуть 13% стоимости налоговым вычетом."),
        ("target", "Индивидуальный план", "Программа строится под цель по баллу и текущие пробелы ученика — занятия 1 на 1."),
        ("chart", "Ежемесячный отчёт", "Каждый месяц — подробный индивидуальный отчёт от педагога об успеваемости ребёнка."),
        ("monitor", "Оффлайн и онлайн", "Два филиала в Долгопрудном рядом с МФТИ и удобный онлайн-формат — как вам удобно."),
        ("star", "Рейтинг 5,0 и своё приложение", "Высокие оценки родителей и мобильное приложение, где дети тренируют слова и копят награды."),
    ],
    "team_title": 'Кто готовит к <span class="fxb-accent">ЕГЭ</span>',
    "team_lead": "Готовят преподаватели, которые знают формат ЕГЭ и критерии — и доводят каждый раздел до нужного балла.",
    "team": [
        ("cap", "Разбираются в критериях ЕГЭ", "Учим писать эссе и отвечать в устной части строго по критериям — без потери баллов на формальностях."),
        ("rocket", "Постоянно развиваются", "Своя система подготовки педагогов: регулярное повышение квалификации по методике школы."),
        ("target", "Ведут к результату", "Ставим цель по баллу и выстраиваем маршрут подготовки под конкретного ученика."),
        ("chart", "Держат связь с родителями", "Индивидуальный подход и регулярная обратная связь о прогрессе."),
    ],
    "faq_title": "Частые вопросы про подготовку к ЕГЭ",
    "faq": [
        ("Когда начинать подготовку к ЕГЭ?", "Лучше за 1,5–2 года, с 10 класса. Подключиться можно и позже — начнём с диагностики и составим реалистичный план до нужного балла."),
        ("Поможете с эссе и устной частью?", "Да. Отдельно отрабатываем письмо и развёрнутое высказывание по критериям, а также все задания говорения по формату и таймингу ЕГЭ."),
        ("Можно ли оплатить материнским капиталом?", "Да. Занятия можно оплатить материнским капиталом и вернуть 13% стоимости налоговым вычетом."),
        ("Занятия очно или онлайн?", "Есть оба формата: очно в Долгопрудном (два филиала рядом с МФТИ) и онлайн."),
        ("Занятия в группе или индивидуально?", "Подготовку к ЕГЭ ведём индивидуально — это самый быстрый путь к нужному баллу: весь фокус на ваших разделах и критериях."),
    ],
    "lead_subject": "Подготовка к ЕГЭ по английскому",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "cta_title": 'Начните подготовку к ЕГЭ с <span class="fxb-accent">бесплатной диагностики</span>',
    "cta_text": "Оценим уровень, разберём слабые разделы и составим маршрут до нужного балла.",
}

PAGES["page_anglijskij_dlya_vzroslyh.html"] = {
    "hero_grad": "linear-gradient(135deg,#2e1a47 0%,#662d92 55%,#7b4fc0 100%)",
    "eyebrow": "Для взрослых 18+",
    "h1": 'Английский для <span class="fxb-accent">взрослых</span>',
    "sub": "Английский для взрослых в Долгопрудном — с нуля и для продолжающих. Разговорная практика, удобное время и комфортная атмосфера без стресса.",
    "cta_label": "Записаться на диагностику",
    "feat_kicker": "Как мы учим",
    "feat_title": "Почему взрослым у нас комфортно",
    "feat_lead": "Учим говорить, а не молчать над учебником — в своём темпе и без страха ошибиться.",
    "features": [
        ("chat", "Разговорный акцент", "Главное — говорить. Много практики речи с первого занятия, а не молчаливая грамматика."),
        ("rocket", "С нуля и для продолжающих", "Начинаем с любого уровня — от первых слов до свободного общения и делового английского."),
        ("clock", "Удобное время", "Утренние и вечерние группы под рабочий график, а также онлайн-формат."),
        ("group", "Комфортная группа", "Мини-группы взрослых со схожим уровнем — без стеснения и в своём темпе."),
    ],
    "facts_title": "Коротко о занятиях",
    "facts": [
        ("star", "Любой уровень", "С нуля до продвинутого"),
        ("calendar", "2 раза / нед", "Стабильный ритм обучения"),
        ("clock", "Утро / вечер", "Под ваш график"),
        ("monitor", "Оффлайн и онлайн", "Как удобно вам"),
    ],
    "formats_title": "Форматы занятий",
    "formats_lead": "Выбирайте удобный формат: очно в Долгопрудном, онлайн или индивидуально — с акцентом на разговор.",
    "formats": [
        ("compass", "Очно в двух филиалах", "Группы в Долгопрудном — на Лихачевского, 76к1 и на Ракетостроителей, 9к3."),
        ("monitor", "Онлайн с педагогом", "Живые видеоуроки для тех, кому нужен гибкий формат без дороги."),
        ("group", "Мини-группы по уровню", "Удобно тем, кто хочет говорить больше и учиться в комфортном темпе."),
        ("chat", "Индивидуальные занятия", "Личный маршрут, гибкий график и максимум разговорной практики."),
    ],
    "teachers": ENGLISH_TEACHERS,
    "prices": True,
    "adv_title": 'Почему взрослым удобно в <span class="fxb-accent">Фоксинбурге</span>',
    "adv_lead": "Языковая школа в Долгопрудном с 2020 года — с лицензией, гибким графиком и акцентом на разговор.",
    "advantages": [
        ("shield", "Лицензия и опыт с 2020 года", "Официальная образовательная лицензия и годы практики обучения взрослых и детей."),
        ("check", "Налоговый вычет 13%", "За обучение можно вернуть 13% стоимости социальным налоговым вычетом."),
        ("clock", "Утро и вечер", "Группы в удобное время под рабочий график, а также онлайн-формат."),
        ("group", "Мини-группы по уровню", "Небольшие группы взрослых со схожим уровнем — без стеснения и в своём темпе."),
        ("monitor", "Оффлайн и онлайн", "Два филиала в Долгопрудном рядом с МФТИ или занятия из дома — как удобно."),
        ("chat", "Акцент на разговор", "Много живой речевой практики с первого занятия, а не молчаливая грамматика."),
    ],
    "team_title": 'Наши <span class="fxb-accent">преподаватели</span>',
    "team_lead": "Взрослые группы ведут преподаватели, которые умеют разговорить с нуля и не перегружают теорией.",
    "team": [
        ("cap", "Сильные преподаватели", "Профессиональные педагоги с уровнем не ниже B2 и любовью к своему делу."),
        ("rocket", "Постоянно развиваются", "Своя система развития педагогов: регулярное повышение квалификации по методике школы."),
        ("chat", "Помогают заговорить", "Создают комфортную атмосферу без страха ошибиться — говорить начинают даже «молчуны»."),
        ("chart", "Индивидуальный подход", "Учитывают вашу цель — работа, путешествия, переезд — и подстраивают программу."),
    ],
    "faq_title": "Частые вопросы",
    "faq": [
        ("Можно начать с полного нуля?", "Да. Берём с любого уровня — от первых слов до свободного общения. Начнём с бесплатной диагностики."),
        ("В какое время занятия?", "Есть утренние и вечерние группы под рабочий график, а также онлайн-формат."),
        ("Сколько человек в группе?", "Занимаемся в небольших группах взрослых со схожим уровнем. Есть и индивидуальные занятия."),
        ("Как понять свой уровень?", "Приходите на бесплатную диагностику — определим уровень и цель и подберём формат."),
        ("Можно заниматься индивидуально?", "Да, доступны индивидуальные занятия — очно и онлайн."),
    ],
    "lead_subject": "Английский для взрослых",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "cta_title": 'Начните говорить — с <span class="fxb-accent">бесплатной диагностики</span>',
    "cta_text": "Определим ваш уровень и цель обучения и подберём подходящую группу или формат.",
}

PAGES["page_nemeckij_yazyk.html"] = {
    "hero_grad": "linear-gradient(135deg,#1e1433 0%,#392852 55%,#662d92 100%)",
    "eyebrow": "Немецкий язык",
    "h1": 'Курсы <span class="fxb-accent">немецкого языка</span>',
    "sub": "Немецкий язык в Долгопрудном для детей, школьников и взрослых. Та же проверенная методика Фоксинбург — в мини-группах и с живым общением.",
    "cta_label": "Записаться на пробный урок",
    "feat_kicker": "Как мы учим",
    "feat_title": "Как проходят занятия",
    "feat_lead": "Тот же подход, что и в английском: понятная система языка и регулярная живая практика.",
    "features": [
        ("chat", "Живое общение", "С первых занятий — говорение и понимание речи, а не только правила и списки слов."),
        ("group", "Мини-группы", "Небольшие группы по уровню и возрасту — внимание каждому ученику."),
        ("book", "Системная методика", "Понятно объясняем грамматику и произношение, доводим до практики."),
        ("rocket", "С нуля", "Начинаем с азов — подойдёт тем, кто раньше не учил немецкий."),
    ],
    "facts_title": "Коротко о занятиях",
    "facts": [
        ("star", "С нуля", "Для начинающих"),
        ("group", "Мини-группы", "По уровню и возрасту"),
        ("calendar", "2 раза / нед", "Регулярные занятия"),
        ("monitor", "Оффлайн и онлайн", "Удобный формат"),
    ],
    "formats_title": "Форматы занятий",
    "formats_lead": "Для немецкого подбираем удобный формат и темп — в группе, онлайн или индивидуально.",
    "formats": [
        ("compass", "Очно в двух филиалах", "Занятия в Долгопрудном — на Лихачевского, 76к1 и на Ракетостроителей, 9к3."),
        ("monitor", "Онлайн с педагогом", "Живые видеоуроки для тех, кому удобнее заниматься из дома."),
        ("group", "Мини-группы по уровню", "Группы подбираем по возрасту и уровню, чтобы каждый успевал говорить."),
        ("chat", "Индивидуальные занятия", "Персональный темп, гибкий график и фокус на вашей цели."),
    ],
    "teachers": GERMAN_TEACHERS,
    "prices": True,
    "adv_title": 'Почему выбирают <span class="fxb-accent">Фоксинбург</span>',
    "adv_lead": "Языковая школа в Долгопрудном с 2020 года — с лицензией, своей методикой и вниманием к каждому ученику.",
    "advantages": [
        ("shield", "Лицензия и опыт с 2020 года", "Официальная образовательная лицензия и годы практики в обучении детей и взрослых."),
        ("check", "Маткапитал и налоговый вычет", "Занятия можно оплатить материнским капиталом и вернуть 13% стоимости налоговым вычетом."),
        ("group", "Мини-группы", "Небольшие группы по уровню и возрасту — педагог видит и слышит каждого ученика."),
        ("chart", "Ежемесячный отчёт", "Каждый месяц — подробный индивидуальный отчёт от педагога об успеваемости ребёнка."),
        ("monitor", "Оффлайн и онлайн", "Два филиала в Долгопрудном рядом с МФТИ и удобный онлайн-формат — как вам удобно."),
        ("star", "Рейтинг 5,0 и своё приложение", "Высокие оценки родителей и мобильное приложение, где дети тренируют слова и копят награды."),
    ],
    "team_title": 'Кто ведёт <span class="fxb-accent">немецкий</span>',
    "team_lead": "Немецкий ведём по той же методике Фоксинбург, что и английский: понятная система языка и живая практика. С преподавателем познакомим на пробном уроке.",
    "team": [
        ("cap", "Сильные преподаватели", "Профессиональные педагоги, которые понятно объясняют грамматику и произношение."),
        ("rocket", "Проверенная методика", "Та же система, что и в английском: от азов — к живому общению шаг за шагом."),
        ("chat", "Живое общение", "С первых занятий — говорение и понимание речи, а не только правила и списки слов."),
        ("chart", "Обратная связь", "Мини-группы, индивидуальный подход и регулярная связь с родителями."),
    ],
    "faq_title": "Частые вопросы про немецкий",
    "faq": [
        ("Нужна ли база по немецкому?", "Нет. Начинаем с нуля — подойдёт тем, кто раньше не учил немецкий."),
        ("Для какого возраста курсы?", "Для детей, школьников и взрослых. Группы подбираем по возрасту и уровню."),
        ("Занятия очно или онлайн?", "Есть оба формата: очно в Долгопрудном (два филиала рядом с МФТИ) и онлайн."),
        ("Можно оплатить материнским капиталом?", "Да. Занятия можно оплатить материнским капиталом и вернуть 13% стоимости налоговым вычетом."),
        ("Как проходит пробный урок?", "Познакомим с преподавателем и методикой, определим уровень и подберём группу — без обязательств."),
    ],
    "lead_subject": "Немецкий язык",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "cta_title": 'Запишитесь на <span class="fxb-accent">пробный урок</span> немецкого',
    "cta_text": "Познакомим с преподавателем и методикой, определим уровень и подберём группу.",
}

PAGES["page_repetitor.html"] = {
    "hero_grad": "linear-gradient(135deg,#241a36 0%,#5a2d8f 55%,#7b4fc0 100%)",
    "eyebrow": "Индивидуальные занятия",
    "h1": 'Репетитор по <span class="fxb-accent">английскому</span>',
    "sub": "Индивидуальные занятия с педагогом в Долгопрудном — для детей, школьников и взрослых. Личная программа под вашу цель, гибкий график и максимум внимания.",
    "cta_label": "Подобрать педагога",
    "feat_kicker": "Почему индивидуально",
    "feat_title": "Как проходят индивидуальные занятия",
    "feat_lead": "Программа строится под конкретного ученика — его цель, уровень и темп.",
    "features": [
        ("target", "Программа под цель", "Подтянуть школьную программу, подготовиться к ОГЭ/ЕГЭ, заговорить к поездке или собеседованию — план под вашу задачу."),
        ("cap", "Всё внимание — одному", "100% времени урока принадлежит ученику: педагог слышит каждую ошибку и сразу её разбирает."),
        ("clock", "Гибкий график", "Занятия в удобные дни и время, очно в Долгопрудном или онлайн. При необходимости расписание подстраиваем."),
        ("rocket", "Быстрый прогресс", "Индивидуальный темп без ожидания группы: сложное разбираем глубже, простое проходим быстрее."),
    ],
    "facts_title": "Коротко о занятиях",
    "facts": [
        ("star", "Любой возраст", "Дети, школьники и взрослые"),
        ("star", "Любой уровень", "С нуля до продвинутого"),
        ("clock", "60 минут", "Полноценное занятие с педагогом"),
        ("monitor", "Оффлайн и онлайн", "Как удобно вам"),
    ],
    "formats_title": "Где занимаемся",
    "formats_lead": "Индивидуальные занятия доступны в обоих филиалах и онлайн — выбирайте удобный вариант.",
    "formats": [
        ("compass", "Очно в двух филиалах", "Занятия в Долгопрудном — на Лихачевского, 76к1 и на Ракетостроителей, 9к3."),
        ("monitor", "Онлайн с педагогом", "Тот же педагог и та же программа в формате видеоурока — без дороги."),
        ("calendar", "Под ваш график", "Утро, день или вечер — подберём время под школу, работу и секции."),
        ("group", "Можно совместить с группой", "Индивидуальные занятия легко дополняют мини-группу — например, точечно подтянуть слабую тему."),
    ],
    "teachers": ENGLISH_TEACHERS,
    "prices": True,
    "price_title": "Стоимость индивидуальных занятий",
    "price_lead": "Индивидуальный формат — 2 500 ₽/час. Первый шаг — бесплатная диагностика уровня.",
    "adv_title": 'Почему выбирают <span class="fxb-accent">Фоксинбург</span>',
    "adv_lead": "Языковая школа в Долгопрудном с 2020 года — с лицензией, своей методикой и вниманием к каждому ученику.",
    "advantages": [
        ("shield", "Лицензия и опыт с 2020 года", "Официальная образовательная лицензия и годы практики в обучении детей и взрослых."),
        ("check", "Маткапитал и налоговый вычет", "Занятия можно оплатить материнским капиталом и вернуть 13% стоимости налоговым вычетом."),
        ("cap", "Педагог под задачу", "Подбираем преподавателя под цель и характер ученика — а при необходимости меняем без проблем."),
        ("chart", "Ежемесячный отчёт", "Каждый месяц — подробный индивидуальный отчёт от педагога об успеваемости."),
        ("monitor", "Оффлайн и онлайн", "Два филиала в Долгопрудном рядом с МФТИ и удобный онлайн-формат — как вам удобно."),
        ("star", "Рейтинг 5,0 и своё приложение", "Высокие оценки родителей и мобильное приложение, где дети тренируют слова и копят награды."),
    ],
    "team_title": 'Кто ведёт <span class="fxb-accent">индивидуальные занятия</span>',
    "team_lead": "Занятия ведут преподаватели, которые умеют строить личную программу и поддерживать мотивацию ученика.",
    "team": [
        ("cap", "Сильные преподаватели", "Профессиональные педагоги с уровнем не ниже B2 и опытом индивидуальной работы."),
        ("rocket", "Постоянно развиваются", "Своя система подготовки педагогов: регулярное повышение квалификации по методике школы."),
        ("target", "Ведут к результату", "Ставим измеримую цель и показываем прогресс в отчётах — не «позанимались», а «достигли»."),
        ("chat", "Находят подход", "Умеют работать и с дошкольниками, и с подростками, и со взрослыми — без давления и скуки."),
    ],
    "faq_title": "Частые вопросы про индивидуальные занятия",
    "faq": [
        ("Чем индивидуальные занятия лучше группы?", "Темпом и вниманием: программа идёт под вашу цель, педагог занят только вами, а расписание — гибкое. Группа при этом дешевле и даёт больше живого общения — на диагностике поможем выбрать."),
        ("Сколько стоит занятие с репетитором?", "Индивидуальное занятие — 2 500 ₽/час. Перед стартом проводим бесплатную диагностику, чтобы определить уровень и цель."),
        ("Для какого возраста подходит?", "Для любого: дети от 4 лет, школьники, студенты и взрослые. Программу и педагога подбираем под возраст и задачу."),
        ("Можно ли заниматься онлайн?", "Да. Индивидуальные занятия доступны очно в Долгопрудном (два филиала рядом с МФТИ) и онлайн — формат можно менять."),
        ("Можно ли оплатить материнским капиталом?", "Да. Занятия можно оплатить материнским капиталом и вернуть 13% стоимости налоговым вычетом."),
        ("А если педагог не подойдёт?", "Скажите нам — подберём другого преподавателя без штрафов и потери оплаченных занятий."),
        ("А занимаетесь только английским?", "Нет. У нас также есть <a href=\"/repetitor-nachalnaya-shkola\">репетитор по русскому языку и математике для 1–4 классов</a> — 7 000 ₽/мес, а также <a href=\"/preparation\">подготовка к школе</a> для дошкольников."),
    ],
    "lead_subject": "Индивидуальные занятия (репетитор)",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "cta_title": 'Подберём педагога на <span class="fxb-accent">бесплатной диагностике</span>',
    "cta_text": "Определим уровень, обсудим цель и предложим педагога и расписание под вашу задачу.",
}

PAGES["page_repetitor_nachalnaya_shkola.html"] = {
    "hero_grad": "linear-gradient(135deg,#1e1433 0%,#3d2a6e 55%,#662d92 100%)",
    "eyebrow": "Начальная школа · 1–4 класс",
    "h1": 'Репетитор по <span class="fxb-accent">русскому языку и математике</span> для 1–4 класса',
    "sub": "Групповые очные занятия по школьным предметам в Долгопрудном: подтянем русский язык и математику в мини-группах до 7 человек, научим учиться и вернём ребёнку уверенность.",
    "cta_label": "Записаться на диагностику",
    "feat_kicker": "Чем занимаемся",
    "feat_title": "Что входит в занятия",
    "feat_lead": "Работаем с программой начальной школы и закрываем пробелы до того, как они станут двойками.",
    "features": [
        ("pencil", "Русский язык", "Чтение и техника чтения, письмо, грамотность, правила 1–4 класса — доводим до автоматизма."),
        ("chart", "Математика", "Счёт, задачи, логика и таблица умножения — понимаем, а не зубрим."),
        ("book", "Помощь с домашними заданиями", "Учим выполнять уроки самостоятельно и без слёз — с проверкой и разбором ошибок."),
        ("target", "Подтягивание программы", "Находим пробелы на диагностике и закрываем их в мини-группе — педагог следит за каждым."),
    ],
    "facts_title": "Коротко о занятиях",
    "facts": [
        ("cap", "1–4 класс", "Начальная школа"),
        ("group", "До 7 человек", "Мини-группы по классу и уровню"),
        ("calendar", "Гибкий график", "Расписание под вашу неделю"),
        ("compass", "Очно", "Два филиала в Долгопрудном"),
    ],
    "formats_title": "Форматы занятий",
    "formats_lead": "Занятия проходят очно, в мини-группах до 7 человек — в двух филиалах Долгопрудного.",
    "formats": [
        ("compass", "Очно в двух филиалах", "Занятия в Долгопрудном — на Лихачевского, 76к1 и на Ракетостроителей, 9к3."),
        ("group", "Мини-группы до 7 человек", "Камерные группы по классу и уровню — педагог успевает поработать с каждым."),
        ("chat", "Работа над пробелами", "На диагностике находим пробелы и закрываем их в темпе группы, с разбором ошибок каждого ребёнка."),
        ("star", "И английский тоже", "Если нужен английский — у нас есть <a href=\"/repetitor\">репетитор по английскому</a> и мини-группы."),
    ],
    "team_title": 'Кто занимается с <span class="fxb-accent">младшими школьниками</span>',
    "team_lead": "Педагоги начальной школы, которые умеют объяснять понятно и держать внимание ребёнка.",
    "team": [
        ("cap", "Педагоги начальной школы", "Знают программу 1–4 классов и типичные «узкие места» каждого года обучения."),
        ("chat", "Умеют объяснять", "Сложное — простыми словами и на примерах, без давления и критики."),
        ("heart", "Находят подход", "Работают и с усидчивыми, и с непоседами — занятие держит внимание ребёнка."),
        ("chart", "Держат связь с родителями", "Регулярная обратная связь: что получается, над чем работаем, что делать дома."),
    ],
    "prices": True,
    "price_title": "Стоимость занятий",
    "price_lead": "Групповые очные занятия по русскому языку и математике для 1–4 классов — 7 000 ₽/мес.",
    "price_cards": [
        ("Месяц занятий", "", '7 000 ₽<span>/мес</span>', "Русский язык и математика · 1–4 класс · мини-группа до 7 человек · очно"),
    ],
    "adv_title": 'Почему выбирают <span class="fxb-accent">Фоксинбург</span>',
    "adv_lead": "Языковая школа в Долгопрудном с 2020 года — с лицензией, своей методикой и вниманием к каждому ученику.",
    "advantages": [
        ("shield", "Лицензия и опыт с 2020 года", "Официальная образовательная лицензия и годы практики в обучении детей и взрослых."),
        ("check", "Маткапитал и налоговый вычет", "Занятия можно оплатить материнским капиталом и вернуть 13% стоимости налоговым вычетом."),
        ("target", "Внимание каждому", "Мини-группы до 7 человек: педагог видит пробелы каждого ребёнка и ведёт его в собственном темпе."),
        ("chart", "Видимый прогресс", "Регулярные отчёты родителям — видно, что изменилось и что дальше."),
        ("compass", "Два филиала очно", "Занятия в Долгопрудном — Лихачевский, 76к1 и Ракетостроителей, 9к3, рядом с МФТИ."),
        ("star", "Рейтинг 5,0", "Высокие оценки родителей на картах и в отзывах — нам доверяют детей."),
    ],
    "faq_title": "Частые вопросы про занятия для 1–4 класса",
    "faq": [
        ("Как понять, что ребёнку нужен репетитор?", "Тревожные сигналы: слёзы над домашкой, ошибки в проверочных, ребёнок говорит «не понимаю» или «не люблю читать/считать». На бесплатной диагностике покажем, где именно пробелы."),
        ("Чем вы занимаетесь на уроке?", "Разбираем текущую школьную тему, закрываем пробелы прошлых лет и учим учиться: читать задание, проверять себя, не бояться ошибок. Домашнюю работу разбираем и делаем вместе, постепенно передавая самостоятельность ребёнку."),
        ("Сколько стоят занятия?", "Групповые очные занятия по русскому языку и математике для 1–4 классов (мини-группы до 7 человек) — 7 000 ₽/мес. Перед стартом — бесплатная диагностика."),
        ("Сколько детей в группе?", "До 7 человек. Группы собираем по классу и уровню, занятия проходят очно в наших филиалах в Долгопрудном — педагог успевает поработать с каждым ребёнком."),
        ("А английский тоже есть?", "Да, это наш основной профиль: <a href=\"/repetitor\">репетитор по английскому</a>, мини-группы по возрастам и <a href=\"/oge-anglijskij\">подготовка к ОГЭ</a> и <a href=\"/ege-anglijskij\">ЕГЭ</a>."),
        ("Можно ли оплатить материнским капиталом?", "Да. Занятия можно оплатить материнским капиталом, а также вернуть 13% стоимости налоговым вычетом."),
    ],
    "lead_subject": "Репетитор по русскому и математике (1–4 класс)",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "cta_title": 'Начните с <span class="fxb-accent">бесплатной диагностики</span>',
    "cta_text": "Проверим чтение, письмо и счёт, покажем пробелы и составим план — как подтянуть русский и математику без стресса.",
}

PAGES["page_kitajskij_yazyk.html"] = {
    "hero_grad": "linear-gradient(135deg,#241a36 0%,#662d92 55%,#8a4fb8 100%)",
    "eyebrow": "Китайский язык",
    "h1": 'Курсы <span class="fxb-accent">китайского языка</span>',
    "sub": "Китайский язык в Долгопрудном для детей, школьников и взрослых. Иероглифика, произношение и разговорная практика — в мини-группах по методике Фоксинбург.",
    "cta_label": "Записаться на пробный урок",
    "feat_kicker": "Как мы учим",
    "feat_title": "Как проходят занятия",
    "feat_lead": "Ведём от азов к живой речи — иероглифика, тоны и общение шаг за шагом.",
    "features": [
        ("palette", "Иероглифика с азов", "Учим писать и узнавать иероглифы пошагово — без страха перед незнакомой письменностью."),
        ("mic", "Тоны и произношение", "Ставим правильное произношение и тоны с самого начала — это фундамент живой речи."),
        ("group", "Мини-группы", "Небольшие группы по уровню и возрасту — максимум практики для каждого."),
        ("rocket", "С нуля", "Начинаем с азов — подойдёт тем, кто раньше не сталкивался с китайским."),
    ],
    "facts_title": "Коротко о занятиях",
    "facts": [
        ("star", "С нуля", "Для начинающих"),
        ("group", "Мини-группы", "По уровню и возрасту"),
        ("calendar", "2 раза / нед", "Регулярные занятия"),
        ("monitor", "Оффлайн и онлайн", "Удобный формат"),
    ],
    "formats_title": "Форматы занятий",
    "formats_lead": "Для китайского подбираем удобный формат и темп — в группе, онлайн или индивидуально.",
    "formats": [
        ("compass", "Очно в двух филиалах", "Занятия в Долгопрудном — на Лихачевского, 76к1 и на Ракетостроителей, 9к3."),
        ("monitor", "Онлайн с педагогом", "Живые видеоуроки для тех, кому удобнее заниматься из дома."),
        ("group", "Мини-группы по уровню", "Группы подбираем по возрасту и уровню, чтобы каждый успевал говорить."),
        ("chat", "Индивидуальные занятия", "Персональный темп, гибкий график и фокус на вашей цели."),
    ],
    "teachers": CHINESE_TEACHERS,
    "prices": True,
    "adv_title": 'Почему выбирают <span class="fxb-accent">Фоксинбург</span>',
    "adv_lead": "Языковая школа в Долгопрудном с 2020 года — с лицензией, своей методикой и вниманием к каждому ученику.",
    "advantages": [
        ("shield", "Лицензия и опыт с 2020 года", "Официальная образовательная лицензия и годы практики в обучении детей и взрослых."),
        ("check", "Маткапитал и налоговый вычет", "Занятия можно оплатить материнским капиталом и вернуть 13% стоимости налоговым вычетом."),
        ("group", "Мини-группы", "Небольшие группы по уровню и возрасту — педагог видит и слышит каждого ученика."),
        ("chart", "Ежемесячный отчёт", "Каждый месяц — подробный индивидуальный отчёт от педагога об успеваемости ребёнка."),
        ("monitor", "Оффлайн и онлайн", "Два филиала в Долгопрудном рядом с МФТИ и удобный онлайн-формат — как вам удобно."),
        ("star", "Рейтинг 5,0 и своё приложение", "Высокие оценки родителей и мобильное приложение, где дети тренируют слова и копят награды."),
    ],
    "team_title": 'Кто ведёт <span class="fxb-accent">китайский</span>',
    "team_lead": "Китайский ведём по методике Фоксинбург: от тонов и иероглифики — к живой речи. С преподавателем познакомим на пробном уроке.",
    "team": [
        ("cap", "Сильные преподаватели", "Профессиональные педагоги, которые пошагово ведут от азов к уверенной речи."),
        ("mic", "Ставят произношение и тоны", "С самого начала уделяем внимание тонам и произношению — это фундамент китайского."),
        ("palette", "Иероглифика без страха", "Учим писать и узнавать иероглифы постепенно, по понятной системе."),
        ("chart", "Обратная связь", "Мини-группы, индивидуальный подход и регулярная связь с родителями."),
    ],
    "faq_title": "Частые вопросы про китайский",
    "faq": [
        ("Сложно ли учить китайский с нуля?", "Идём пошагово: сначала тоны и произношение, затем иероглифы и разговорная практика. Начинаем с нуля."),
        ("Для какого возраста курсы?", "Для детей, школьников и взрослых. Группы подбираем по возрасту и уровню."),
        ("Занятия очно или онлайн?", "Есть оба формата: очно в Долгопрудном (два филиала рядом с МФТИ) и онлайн."),
        ("Можно оплатить материнским капиталом?", "Да. Занятия можно оплатить материнским капиталом и вернуть 13% стоимости налоговым вычетом."),
        ("Как проходит пробный урок?", "Познакомим с преподавателем и методикой, определим цель обучения и подберём группу."),
    ],
    "lead_subject": "Китайский язык",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "cta_title": 'Запишитесь на <span class="fxb-accent">пробный урок</span> китайского',
    "cta_text": "Познакомим с преподавателем и методикой, определим цель обучения и подберём группу.",
}

PAGES["page_ispanskij_yazyk.html"] = {
    "hero_grad": "linear-gradient(135deg,#241a36 0%,#7a2b52 55%,#c24712 100%)",
    "eyebrow": "Испанский язык",
    "h1": 'Испанский язык <span class="fxb-accent">для детей</span>',
    "sub": "Испанский язык в Долгопрудном для детей и школьников. Та же проверенная методика Фоксинбург — в мини-группах, через игру и живое общение.",
    "cta_label": "Записаться на пробный урок",
    "feat_kicker": "Как мы учим",
    "feat_title": "Как проходят занятия",
    "feat_lead": "Тот же подход, что и в английском: понятная система языка и регулярная живая практика.",
    "features": [
        ("chat", "Живое общение", "С первых занятий — говорение и понимание речи, а не только правила и списки слов."),
        ("group", "Мини-группы", "Небольшие группы по уровню и возрасту — внимание каждому ученику."),
        ("music", "Песни и игры", "Испанский через игру, музыку и культурный контекст — так дети усваивают язык легче всего."),
        ("rocket", "С нуля", "Начинаем с азов — подойдёт тем, кто раньше не учил испанский."),
    ],
    "facts_title": "Коротко о занятиях",
    "facts": [
        ("star", "С нуля", "Для начинающих"),
        ("group", "Мини-группы", "По уровню и возрасту"),
        ("calendar", "2 раза / нед", "Регулярные занятия"),
        ("monitor", "Оффлайн и онлайн", "Удобный формат"),
    ],
    "formats_title": "Форматы занятий",
    "formats_lead": "Для испанского подбираем удобный формат и темп — в группе, онлайн или индивидуально.",
    "formats": [
        ("compass", "Очно в двух филиалах", "Занятия в Долгопрудном — на Лихачевского, 76к1 и на Ракетостроителей, 9к3."),
        ("monitor", "Онлайн с педагогом", "Живые видеоуроки для тех, кому удобнее заниматься из дома."),
        ("group", "Мини-группы по уровню", "Группы подбираем по возрасту и уровню, чтобы каждый успевал говорить."),
        ("chat", "Индивидуальные занятия", "Персональный темп, гибкий график и фокус на вашей цели."),
    ],
    "teachers": SPANISH_TEACHERS,
    "prices": True,
    "adv_title": 'Почему выбирают <span class="fxb-accent">Фоксинбург</span>',
    "adv_lead": "Языковая школа в Долгопрудном с 2020 года — с лицензией, своей методикой и вниманием к каждому ученику.",
    "advantages": [
        ("shield", "Лицензия и опыт с 2020 года", "Официальная образовательная лицензия и годы практики в обучении детей и взрослых."),
        ("check", "Маткапитал и налоговый вычет", "Занятия можно оплатить материнским капиталом и вернуть 13% стоимости налоговым вычетом."),
        ("group", "Мини-группы", "Небольшие группы по уровню и возрасту — педагог видит и слышит каждого ученика."),
        ("chart", "Ежемесячный отчёт", "Каждый месяц — подробный индивидуальный отчёт от педагога об успеваемости ребёнка."),
        ("monitor", "Оффлайн и онлайн", "Два филиала в Долгопрудном рядом с МФТИ и удобный онлайн-формат — как вам удобно."),
        ("star", "Рейтинг 5,0 и своё приложение", "Высокие оценки родителей и мобильное приложение, где дети тренируют слова и копят награды."),
    ],
    "team_title": 'Кто ведёт <span class="fxb-accent">испанский</span>',
    "team_lead": "Испанский ведём по той же методике Фоксинбург, что и английский: понятная система языка и живая практика. С преподавателем познакомим на пробном уроке.",
    "team": [
        ("cap", "Сильные преподаватели", "Профессиональные педагоги, которые понятно объясняют грамматику и произношение."),
        ("rocket", "Проверенная методика", "Та же система, что и в английском: от азов — к живому общению шаг за шагом."),
        ("chat", "Живое общение", "С первых занятий — говорение и понимание речи, а не только правила и списки слов."),
        ("chart", "Обратная связь", "Мини-группы, индивидуальный подход и регулярная связь с родителями."),
    ],
    "faq_title": "Частые вопросы про испанский",
    "faq": [
        ("Нужна ли база по испанскому?", "Нет. Начинаем с нуля — подойдёт тем, кто раньше не учил испанский."),
        ("Для какого возраста курсы?", "Для детей и школьников. Группы подбираем по возрасту и уровню."),
        ("Занятия очно или онлайн?", "Есть оба формата: очно в Долгопрудном (два филиала рядом с МФТИ) и онлайн."),
        ("Можно оплатить материнским капиталом?", "Да. Занятия можно оплатить материнским капиталом и вернуть 13% стоимости налоговым вычетом."),
        ("Как проходит пробный урок?", "Познакомим с преподавателем и методикой, определим уровень и подберём группу — без обязательств."),
    ],
    "lead_subject": "Испанский язык",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "cta_title": 'Запишитесь на <span class="fxb-accent">пробный урок</span> испанского',
    "cta_text": "Познакомим с преподавателем и методикой, определим уровень и подберём группу.",
}

# ----------------------------------------------------------------
# Новые посадочные страницы (ВПР, разговорный, отзывы, о школе).
# Их нет на живой Tilda и в seo_meta_live.json — title/description
# попадают в <head> через fallback extract_article_meta(): title из
# <h1>, description — из первого "description" в JSON-LD страницы
# (Course/WebPage в extra_jsonld). Поэтому h1 здесь содержит гео.

PAGES["page_vpr_anglijskij.html"] = {
    "page_class": "fxb-blog-page",
    "article_css": True,
    "hero_grad": "linear-gradient(135deg,#241a36 0%,#3f2a68 55%,#5a2d8f 100%)",
    "eyebrow": "Подготовка к ВПР · 4–8 классы",
    "h1": 'Подготовка к <span class="fxb-accent">ВПР</span> по английскому в Долгопрудном',
    "sub": "Готовим школьников 4–8 классов к ВПР по английскому: разбираем формат, отрабатываем все разделы и доводим задания до автоматизма — без стресса.",
    "cta_label": "Записаться на диагностику",
    "feat_kicker": "Что входит",
    "feat_title": "Как готовим к ВПР",
    "feat_lead": "ВПР — не экзамен, а проверка школьной программы. Наша задача — чтобы ребёнок уверенно прошёл каждый раздел.",
    "features": [
        ("check", "Все разделы ВПР", "Аудирование, чтение, грамматика и лексика, письмо — прорабатываем каждый тип заданий."),
        ("target", "Формат до автоматизма", "Тренируем структуру работы и тайминг, чтобы на проверочной не было сюрпризов."),
        ("pencil", "Письменная часть", "Учим грамотно оформлять ответы и не терять баллы на формальностях."),
        ("chart", "Пробные ВПР", "Регулярные пробники в формате настоящей работы и подробный разбор ошибок."),
    ],
    "facts_title": "Коротко о подготовке",
    "facts": [
        ("cap", "4–8 классы", "Для учеников начальной и основной школы"),
        ("calendar", "2 раза / нед", "Регулярная отработка формата"),
        ("clock", "60 минут", "Полноценное занятие с практикой"),
        ("chat", "1 на 1", "Индивидуальные занятия с педагогом"),
    ],
    "extra_sections": [
        '<section class="fxb-section"><div class="fxb-wrap"><div class="fxb-article-body">'
        "<h2>Что такое ВПР по английскому</h2>"
        "<p>ВПР — Всероссийская проверочная работа. Её проводит школа по единым для всей страны заданиям, чтобы оценить, как ученики освоили программу. По английскому языку ВПР пишут в 4–8 классах — точные даты и классы определяет школа.</p>"
        "<p>Оценка за ВПР не влияет на аттестат и перевод в следующий класс, но работа честно показывает реальный уровень ребёнка: где всё в порядке, а где есть пробелы. А ещё формат ВПР очень похож на <a href=\"/oge-anglijskij\">ОГЭ по английскому</a> — поэтому спокойная подготовка к ВПР в 4–8 классах становится хорошей репетицией перед настоящим экзаменом в 9 классе.</p>"
        "<h2>Структура ВПР по английскому</h2>"
        "<p>Точный состав заданий зависит от класса, но работа всегда проверяет четыре навыка:</p>"
        "<ul>"
        "<li><b>Аудирование</b> — понимание коротких текстов и диалогов на слух;</li>"
        "<li><b>Чтение</b> — работа с текстом: понимание содержания и деталей;</li>"
        "<li><b>Грамматика и лексика</b> — задания на правила и словарный запас школьной программы;</li>"
        "<li><b>Письмо</b> — письменные задания по образцу: заполнить, дописать, ответить.</li>"
        "</ul>"
        "<p>Все задания — в рамках школьной программы соответствующего класса. Сложность обычно не в материале, а в незнакомом формате: ребёнок может знать тему, но растеряться из-за инструкции или тайминга.</p>"
        "<h2>Как мы готовим к ВПР в Фоксинбурге</h2>"
        "<p>Начинаем с бесплатной диагностики: определяем уровень и видим, какие разделы проседают. Дальше педагог составляет план: подтягиваем грамматику и лексику школьной программы, разбираем каждый тип заданий и регулярно пишем пробные работы в настоящем формате и тайминге.</p>"
        "<p>Если пробелов много, сначала укрепляем базу — часто это удобнее делать в основных группах: <a href=\"/mladshie-shkolniki\">английский для младших школьников</a> или <a href=\"/podrostki\">английский для подростков</a>. Целевая подготовка к конкретной ВПР идёт индивидуально, в темпе ученика.</p>"
        "<h2>Кому подойдёт подготовка</h2>"
        "<ul>"
        "<li>ученикам 4–8 классов, которым в этом учебном году писать ВПР по английскому;</li>"
        "<li>тем, кто «вроде знает», но теряется на проверочных и контрольных;</li>"
        "<li>тем, кто хочет заранее привыкнуть к экзаменационному формату перед <a href=\"/oge-anglijskij\">ОГЭ</a> и <a href=\"/ege-anglijskij\">ЕГЭ</a>.</li>"
        "</ul>"
        '<div class="fxb-related"><h2>Смежные программы</h2><div class="fxb-related-list">'
        '<a href="/podrostki">Английский для подростков</a>'
        '<a href="/mladshie-shkolniki">Младшие школьники</a>'
        '<a href="/oge-anglijskij">Подготовка к ОГЭ</a>'
        "</div></div>"
        "</div></div></section>",
    ],
    "formats_title": "Форматы занятий",
    "formats_lead": "Целевую подготовку к ВПР ведём индивидуально: очно в филиалах или онлайн, расписание под ваш ритм.",
    "formats": [
        ("compass", "Очно в двух филиалах", "Занятия в Долгопрудном — на Лихачевского, 76к1 и на Ракетостроителей, 9к3."),
        ("monitor", "Онлайн с педагогом", "Живые видеоуроки с разбором заданий и обратной связью в реальном времени."),
        ("chat", "Индивидуально 1 на 1", "Персональный план под пробелы и дату ВПР — весь фокус занятия на вашем ребёнке."),
        ("group", "База — в мини-группах", "Общий уровень укрепляем в основных группах по возрасту, формат ВПР — индивидуально."),
    ],
    "prices": True,
    "price_title": "Стоимость подготовки к ВПР",
    "price_lead": "Целевую подготовку к ВПР ведём индивидуально — 2 500 ₽/час. Первый шаг — бесплатная диагностика.",
    "price_cards": [
        ("Индивидуально", " fxb-price-tag--orange", '2 500 ₽<span>/час</span>', "Занятие 1 на 1 с педагогом · 60 минут · гибкий график"),
    ],
    "adv_title": 'Почему выбирают <span class="fxb-accent">Фоксинбург</span>',
    "adv_lead": "Языковая школа в Долгопрудном с 2020 года — с лицензией, своей методикой и вниманием к каждому ученику.",
    "advantages": [
        ("shield", "Лицензия и опыт с 2020 года", "Официальная образовательная лицензия и годы практики в обучении детей и взрослых."),
        ("check", "Маткапитал и налоговый вычет", "Занятия можно оплатить материнским капиталом и вернуть 13% стоимости налоговым вычетом."),
        ("target", "Индивидуальный план", "Программа строится под пробелы и дату ВПР конкретного ученика."),
        ("chart", "Ежемесячный отчёт", "Каждый месяц — подробный индивидуальный отчёт от педагога об успеваемости ребёнка."),
        ("monitor", "Оффлайн и онлайн", "Два филиала в Долгопрудном рядом с МФТИ и удобный онлайн-формат — как вам удобно."),
        ("star", "Рейтинг 5,0 и своё приложение", "Высокие оценки родителей и мобильное приложение, где дети тренируют слова и копят награды."),
    ],
    "team_title": 'Кто готовит к <span class="fxb-accent">ВПР</span>',
    "team_lead": "Подготовку ведут преподаватели, которые знают школьную программу и формат проверочных работ — и умеют объяснять понятно.",
    "team": [
        ("cap", "Знают школьную программу", "Работаем строго в рамках программы класса — ничего лишнего и ничего пропущенного."),
        ("rocket", "Постоянно развиваются", "Своя система подготовки педагогов: регулярное повышение квалификации по методике школы."),
        ("chat", "Снимают страх проверочных", "Разбираем ошибки без давления — на работу ребёнок идёт спокойно и собранно."),
        ("chart", "Держат связь с родителями", "Индивидуальный подход и регулярная обратная связь о прогрессе подготовки."),
    ],
    "faq_title": "Частые вопросы про подготовку к ВПР",
    "faq": [
        ("Что такое ВПР и обязательна ли она?", "ВПР — Всероссийская проверочная работа, её проводит школа по единым заданиям. Пишут все ученики, но это не экзамен: оценка не влияет на аттестат, а сама работа показывает реальный уровень ребёнка."),
        ("В каких классах пишут ВПР по английскому?", "Чаще всего в 4–8 классах — точный график определяет школа. Мы готовим учеников 4–8 классов к работе любого года."),
        ("Чем ВПР отличается от ОГЭ?", "ВПР проще и не является экзаменом, но формат похож: аудирование, чтение, грамматика и письмо. Спокойная сдача ВПР — хорошая репетиция перед ОГЭ в 9 классе."),
        ("Сколько времени нужно на подготовку?", "Зависит от уровня: обычно достаточно 2–3 месяцев регулярных занятий. Начнём с бесплатной диагностики и скажем честно, сколько нужно именно вашему ребёнку."),
        ("Занятия в группе или индивидуально?", "Целевую подготовку к ВПР ведём индивидуально — так педагог закрывает именно пробелы вашего ребёнка. Общий уровень удобно подтягивать в основных группах по возрасту."),
        ("Занятия очно или онлайн?", "Есть оба формата: очно в Долгопрудном (два филиала рядом с МФТИ) и онлайн."),
    ],
    "extra_jsonld": [
        course_jsonld(
            "Подготовка к ВПР по английскому языку в Долгопрудном",
            "Подготовка к ВПР по английскому (4–8 классы) в Долгопрудном: разбор формата, отработка всех разделов, пробные работы. Индивидуально, очно в двух филиалах или онлайн. Бесплатная диагностика.",
            SITE + "/vpr-anglijskij",
            "Индивидуальное занятие по подготовке к ВПР (60 минут)", "2500",
        ),
        breadcrumb_jsonld([
            ("Главная", SITE + "/"),
            ("Подготовка к ВПР по английскому", SITE + "/vpr-anglijskij"),
        ]),
    ],
    "lead_subject": "Подготовка к ВПР по английскому",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "cta_title": 'Узнайте готовность к ВПР на <span class="fxb-accent">бесплатной диагностике</span>',
    "cta_text": "Определим текущий уровень, покажем пробелы и составим план подготовки к проверочной работе.",
}

PAGES["page_razgovornyj_anglijskij.html"] = {
    "page_class": "fxb-blog-page",
    "article_css": True,
    "hero_grad": "linear-gradient(135deg,#1e1433 0%,#4a2a7a 55%,#7b4fc0 100%)",
    "eyebrow": "Speaking club · подростки и взрослые",
    "h1": '<span class="fxb-accent">Разговорный</span> английский в Долгопрудном',
    "sub": "Курс разговорного английского для подростков и взрослых: коммуникативная методика, живая речевая практика и преодоление языкового барьера — очно и онлайн.",
    "cta_label": "Записаться на диагностику",
    "feat_kicker": "Как мы учим",
    "feat_title": "Учим говорить, а не молчать",
    "feat_lead": "Главная причина «понимаю, но не говорю» — нехватка речевой практики. Мы её даём с первого занятия.",
    "features": [
        ("chat", "Много речи с первого занятия", "До 70% занятия — живое общение: диалоги, дискуссии, ролевые ситуации из реальной жизни."),
        ("group", "Speaking club", "Разговорные встречи в мини-группах: обсуждаем фильмы, путешествия, работу — всё, о чём говорят по-настоящему."),
        ("heart", "Снимаем языковой барьер", "Атмосфера без страха ошибки: педагог поддерживает и направляет, а не исправляет каждое слово."),
        ("rocket", "От A1 до свободного общения", "Подбираем группу по уровню после диагностики — от первых фраз до уверенной беседы."),
    ],
    "facts_title": "Коротко о занятиях",
    "facts": [
        ("star", "Подростки и взрослые", "Группы по возрасту и уровню"),
        ("calendar", "2 раза / нед", "Стабильный ритм практики"),
        ("group", "6–8 человек", "Каждый успевает говорить"),
        ("monitor", "Оффлайн и онлайн", "Как удобно вам"),
    ],
    "extra_sections": [
        '<section class="fxb-section"><div class="fxb-wrap"><div class="fxb-article-body">'
        "<h2>Почему вы понимаете, но не говорите</h2>"
        "<p>Знакомая ситуация: годы школьного английского, фильмы в оригинале понятны, а сказать — не получается. Это языковой барьер, и причина у него простая: чтение и аудирование тренировались годами, а говорение — почти никогда. Речь — отдельный навык, и он растёт только из практики.</p>"
        "<p>Поэтому на наших занятиях говорят ученики, а не только педагог. Ошибки не высмеивают — их разбирают спокойно и по делу. Через несколько недель регулярной практики «столбняк» при необходимости сказать что-то по-английски проходит.</p>"
        "<h2>Коммуникативная методика</h2>"
        "<p>Мы работаем по коммуникативному подходу: новые слова и грамматика сразу закрепляются в живой речи, а не в списках для зубрёжки. Каждая тема — это ситуация из жизни: знакомство, аэропорт, собеседование, спор о фильме. Грамматику объясняем понятно и коротко — ровно настолько, чтобы ей было где работать.</p>"
        "<h2>Как проходит разговорная практика</h2>"
        "<ul>"
        "<li><b>Основные занятия</b> — программа по уровню с разговорным акцентом: каждый урок включает говорение;</li>"
        "<li><b>Speaking club</b> — разговорные встречи в мини-группе: темы, игры и дискуссии без учебника;</li>"
        "<li><b>Индивидуальный формат</b> — если нужен максимум речевой практики в вашем темпе.</li>"
        "</ul>"
        "<p>Для детей и подростков разговорная практика встроена в основные программы — <a href=\"/podrostki\">английский для подростков</a> и <a href=\"/mladshie-shkolniki\">для младших школьников</a>. Взрослым подойдёт <a href=\"/anglijskij-dlya-vzroslyh\">курс для взрослых</a> — с нуля и для продолжающих. Не в Долгопрудном? Есть <a href=\"/online-zanyatiya\">онлайн-занятия</a> с той же методикой.</p>"
        '<div class="fxb-related"><h2>Смежные программы</h2><div class="fxb-related-list">'
        '<a href="/nositel-yazyka">Клуб с носителем языка</a>'
        '<a href="/anglijskij-dlya-vzroslyh">Английский для взрослых</a>'
        '<a href="/podrostki">Английский для подростков</a>'
        '<a href="/online-zanyatiya">Онлайн-занятия</a>'
        "</div></div>"
        "</div></div></section>",
    ],
    "formats_title": "Форматы занятий",
    "formats_lead": "Выбирайте удобный формат: очно в Долгопрудном, онлайн или индивидуально — всегда с акцентом на разговор.",
    "formats": [
        ("compass", "Очно в двух филиалах", "Группы в Долгопрудном — на Лихачевского, 76к1 и на Ракетостроителей, 9к3."),
        ("monitor", "Онлайн с педагогом", "Живые видеоуроки и разговорные встречи — без дороги, из любого города."),
        ("group", "Мини-группы 6–8 человек", "Достаточно людей для живого обсуждения и достаточно мало, чтобы говорил каждый."),
        ("chat", "Индивидуальные занятия", "Личный маршрут, гибкий график и максимум разговорной практики."),
    ],
    "prices": True,
    "price_title": "Стоимость разговорного курса",
    "price_lead": "Групповые занятия — от 9 000 ₽/мес, индивидуальные — 2 500 ₽/час. Первый шаг — бесплатная диагностика уровня.",
    "adv_title": 'Почему выбирают <span class="fxb-accent">Фоксинбург</span>',
    "adv_lead": "Языковая школа в Долгопрудном с 2020 года — с лицензией, своей методикой и вниманием к каждому ученику.",
    "advantages": [
        ("shield", "Лицензия и опыт с 2020 года", "Официальная образовательная лицензия и годы практики в обучении детей и взрослых."),
        ("chat", "Акцент на разговор", "Много живой речевой практики с первого занятия, а не молчаливая грамматика."),
        ("group", "Мини-группы по уровню", "Группы 6–8 человек со схожим уровнем — без стеснения и в своём темпе."),
        ("check", "Налоговый вычет 13%", "За обучение можно вернуть 13% стоимости социальным налоговым вычетом."),
        ("monitor", "Оффлайн и онлайн", "Два филиала в Долгопрудном рядом с МФТИ или занятия из дома — как удобно."),
        ("star", "Рейтинг 5,0 и своё приложение", "Высокие оценки родителей и мобильное приложение для тренировки слов между занятиями."),
    ],
    "team_title": 'Кто ведёт <span class="fxb-accent">разговорные</span> занятия',
    "team_lead": "Преподаватели, которые умеют разговорить с нуля и не перегружают теорией.",
    "team": [
        ("cap", "Сильные преподаватели", "Профессиональные педагоги с уровнем не ниже B2 и любовью к своему делу."),
        ("rocket", "Постоянно развиваются", "Своя система развития педагогов: регулярное повышение квалификации по методике школы."),
        ("chat", "Помогают заговорить", "Создают комфортную атмосферу без страха ошибиться — говорить начинают даже «молчуны»."),
        ("target", "Ведут к вашей цели", "Работа, путешествия, переезд или экзамен — программу подстраивают под задачу."),
    ],
    "faq_title": "Частые вопросы про разговорный английский",
    "faq": [
        ("Я всё понимаю, но не могу говорить — поможете?", "Да, это самая частая ситуация. Языковой барьер снимается только речевой практикой: в мини-группе и в атмосфере без страха ошибки говорить начинают даже «молчуны»."),
        ("С какого уровня можно в speaking club?", "Подбираем группу после бесплатной диагностики — есть группы для разных уровней, от первых фраз до свободного общения."),
        ("Это отдельный курс или часть основного?", "Разговорная практика встроена во все наши программы, а speaking club — дополнительная живая практика для тех, кто хочет говорить больше."),
        ("Подойдёт подростку?", "Да. Группы подбираем по возрасту и уровню: подростки занимаются отдельно от взрослых, в своих темах и темпе."),
        ("Можно заниматься онлайн?", "Да, есть онлайн-формат с той же методикой — живые видеоуроки и разговорные встречи."),
        ("Сколько нужно заниматься, чтобы заговорить?", "Первые уверенные фразы — уже через несколько недель регулярной практики (2 раза в неделю). Устойчивый разговорный уровень зависит от стартовой точки — честно оценим на диагностике."),
    ],
    "extra_jsonld": [
        course_jsonld(
            "Разговорный английский для подростков и взрослых в Долгопрудном",
            "Разговорный английский в Долгопрудном для подростков и взрослых: коммуникативная методика, speaking club. Мини-группы и индивидуально, очно и онлайн.",
            SITE + "/razgovornyj-anglijskij",
            "Групповые занятия разговорным английским (месяц)", "9000",
        ),
        breadcrumb_jsonld([
            ("Главная", SITE + "/"),
            ("Разговорный английский", SITE + "/razgovornyj-anglijskij"),
        ]),
    ],
    "lead_subject": "Разговорный английский",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "cta_title": 'Начните говорить — с <span class="fxb-accent">бесплатной диагностики</span>',
    "cta_text": "Определим ваш уровень и подберём группу или формат, в которых вы наконец заговорите.",
}

PAGES["page_meropriyatiya.html"] = {
    "hero_grad": "linear-gradient(135deg,#2e1a47 0%,#662d92 55%,#c24712 100%)",
    "eyebrow": "Жизнь школы",
    "h1": 'Мероприятия <span class="fxb-accent">Фоксинбурга</span>',
    "sub": "Мастер-классы, киновечеринки на английском, сезонные Академии и праздники — языковая среда за пределами урока.",
    "cta_label": "Записаться на диагностику",
    "feat_kicker": "Что мы проводим",
    "feat_title": "Наши мероприятия",
    "feat_lead": "Каждое событие — это живая практика английского и праздник, который дети ждут.",
    "features": [
        ("palette", "Мастер-классы", "Творческие и кулинарные мастер-классы на английском: делаем, пробуем и обсуждаем — язык работает в деле."),
        ("monitor", "Киновечеринки на английском", "Смотрим фильмы и мультфильмы в оригинале, а после — обсуждаем и играем по мотивам."),
        ("sun", "Осенняя и Весенняя Академии", "Интенсивные смены на каникулах: тематические недели, проекты и погружение в языковую среду."),
        ("star", "Новогодние вечеринки", "Праздники с играми, квестами и подарками — на английском, конечно. Традиция, которую дети ждут весь год."),
        ("cap", "Выпускной", "Торжественное завершение учебного года: награждение учеников, итоги прогресса и праздник для всей семьи."),
        ("compass", "Открытые занятия в парках", "Бесплатные промо-мероприятия в парках Долгопрудного: игры и занятия на английском для всех горожан."),
    ],
    "facts_title": "Коротко о мероприятиях",
    "facts": [
        ("calendar", "Круглый год", "События в каждом сезоне"),
        ("star", "Для всех возрастов", "От дошкольников до подростков"),
        ("group", "Ученики и гости", "На многие события можно прийти с другом"),
        ("compass", "Филиалы и парки", "Долгопрудный"),
    ],
    "faq_title": "Частые вопросы про мероприятия",
    "faq": [
        ("Кому можно на мероприятия?", "В первую очередь — ученикам школы всех возрастов. На открытые мероприятия в парках может прийти любой житель Долгопрудного, а на праздники ученики часто могут привести друга — уточняйте у администратора."),
        ("Мероприятия платные?", "Условия зависят от события: промо-мероприятия в парках Долгопрудного бесплатны и открыты для всех. Формат участия в школьных праздниках уточняйте у администратора."),
        ("Как узнать расписание событий?", "Анонсы публикуются в личном кабинете ученика и в наших мессенджер-каналах, а администраторы всегда подскажут ближайшие даты по телефону."),
        ("Можно ли прийти, если ребёнок не учится в школе?", "Да: открытые занятия и игры в парках — для всех желающих. Это отличный способ познакомиться со школой и атмосферой занятий."),
        ("Мероприятия проходят на английском?", "Да, ведущие и педагоги говорят с детьми на английском — в игровой, понятной форме. Это и есть наша языковая среда за пределами урока."),
    ],
    "extra_jsonld": [
        webpage_jsonld(
            "WebPage",
            "Мероприятия языковой школы Фоксинбург в Долгопрудном",
            "Мероприятия Фоксинбурга в Долгопрудном: мастер-классы, киновечеринки на английском, сезонные Академии, новогодние праздники и открытые занятия в парках.",
            SITE + "/meropriyatiya",
        ),
        breadcrumb_jsonld([
            ("Главная", SITE + "/"),
            ("Мероприятия", SITE + "/meropriyatiya"),
        ]),
    ],
    "lead_subject": "Мероприятия школы",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "extra_sections": [
        media_library.life_bundle(
            media_library.media_wall(
                series="2026-05-16-nikon", limit=8,
                title="Выпускной 2026", kicker="16 мая 2026 · реальные фото",
            ),
            media_library.media_wall(
                series="2026-08-15-canon", limit=6,
                title="Мероприятие в парке", kicker="Август 2026 · Долгопрудный",
                light=True,
            ),
        ),
    ],
    "cta_title": 'Присоединяйтесь к <span class="fxb-accent">жизни школы</span>',
    "cta_text": "Оставьте заявку на бесплатную диагностику — расскажем о программах и ближайших мероприятиях.",
}

PAGES["page_zhizn_shkoly.html"] = {
    # Хаб «Жизнь школы» — media-first страница на реальных фото/видео (сессия media-first).
    # story_hero заменяет стандартный градиентный hero.
    "hero_grad": "linear-gradient(135deg,#2e1a47 0%,#662d92 55%,#c24712 100%)",
    "story_hero": {
        "item_id": "2026-08-15-canon/9G6A4869",
        "h1": 'Жизнь <span class="fxb-accent">школы</span>',
        "sub": "Настоящие занятия, праздники, мастер-классы и Лиса — всё, что происходит в Фоксинбурге, без постановки и стоковых фото.",
        "kicker": "Dymova Now",
    },
    "eyebrow": "Жизнь школы",
    "h1": 'Жизнь <span class="fxb-accent">школы</span>',
    "sub": "Настоящие занятия, праздники и события Фоксинбурга.",
    "cta_label": "Записаться на диагностику",
    "feat_kicker": "Чем живёт школа",
    "feat_title": "Больше, чем уроки",
    "feat_lead": "Урок — только часть того, что получает ребёнок. Остальное — среда, события и люди.",
    "features": [
        ("book", "Занятия", "Мини-группы, игры на английском и живой контакт с педагогом — так выглядят наши будни."),
        ("star", "Праздники и события", "Выпускные, сезонные праздники, городские события — школа живёт круглый год."),
        ("palette", "Мастер-классы", "Творчество, опыты и ручная работа на английском — язык в деле, а не в зубрёжке."),
        ("heart", "Лиса Фокси", "Наш маскот встречает детей на праздниках и открытых занятиях — дети его обожают."),
    ],
    "facts_title": "Это всё — настоящее",
    "facts": [
        ("check", "Свои фото и видео", "Только реальные съёмки школы"),
        ("group", "Настоящие ученики", "Никаких моделей и стоков"),
        ("calendar", "Круглый год", "События в каждом сезоне"),
        ("compass", "Долгопрудный", "Оба филиала и городские площадки"),
    ],
    # media-секции: Dymova Now → событие 16 мая → занятия → видео → архив
    "extra_sections": [
        media_library.life_bundle(
            media_library.wow_scene(
                "cards",
                "Каждый кадр — из реальной жизни школы",
                "Моменты наших праздников, занятий и экскурсий — собраны и буквально парят здесь. Без стоков, без постановки, без чужих детей.",
                kicker="WOW · настоящие моменты",
                theme="dark",
                link=("/vypusknoj-2026", "Смотреть историю выпускного"),
            ),
            media_library.real_moment(
                "2026-05-16-nikon/DSC_5117",
                "Сцена, аплодисменты и немного волнения — моменты, которые дети запоминают надолго.",
                kicker="Реальный момент",
                caption="Выпускной 2026, 16 мая",
                light=True,
            ),
            media_library.media_wall(
                series="2026-08-15-canon", limit=8,
                title="Мероприятие в парке", kicker="Dymova Now · август 2026",
            ),
            media_library.media_wall(
                series="2026-05-16-nikon", limit=12,
                title="Выпускной 2026", kicker="Событие · 16 мая",
                light=True,
            ),
            media_library.media_wall(
                series="2026-04-07-canon", limit=6,
                title="Весенняя Академия 2026", kicker="Каникулы с пользой",
            ),
            media_library.media_wall(
                series="2026-06--canon", limit=6,
                title="Экскурсии: Ю-Клиника и пожарная станция", kicker="За пределами класса",
                light=True,
            ),
        ),
        (
            '<section class="fxb-section"><div class="fxb-wrap">'
            '<div class="fxb-head"><span class="fxb-kicker"><span class="fxb-dot"></span>Истории</span>'
            '<h2 class="fxb-h2">События в деталях</h2>'
            '<p class="fxb-lead">Каждое событие школы — отдельная история с настоящими фотографиями.</p></div>'
            '<p style="display:flex;gap:12px;flex-wrap:wrap">'
            '<a class="fxb-btn-main" href="/vypusknoj-2026">Выпускной 2026</a>'
            '<a class="fxb-btn-main" href="/ekskursii">Экскурсии: Ю-Клиника и пожарная станция</a>'
            '<a class="fxb-btn-main" href="/prazdniki">Праздники школы</a>'
            '<a class="fxb-btn-main" href="/vesennyaya-akademiya-2026">Весенняя Академия 2026</a>'
            '</p></div></section>'
        ),
        media_library.life_bundle(
            media_library.wow_scene(
                "iphone",
                "Лиса живёт и в вашем телефоне",
                "Фокси напоминает о занятиях, поздравляет с праздниками и держит родителей в курсе — школа всегда рядом.",
                kicker="Фокси онлайн",
                theme="light", flip=True, alpha=True,
            ),
            media_library.video_story(
                "no-date-other/Spell and guess",
                "Игры на уроке",
                "Короткие игровые форматы, которые мы используем на занятиях, — английский через действие.",
                kicker="Видео",
            ),
        ),
        media_library.life_bundle(
            media_library.real_moment(
                "2026-07-01-canon/9G6A4758",
                "За каждым праздником и каждым уроком — настоящая команда, которая любит своё дело.",
                kicker="Команда",
                caption="Команда Фоксинбурга, июль 2026",
                light=True,
            ),
            media_library.video_story(
                "no-date-other/фразы",
                "Взгляд снизу",
                "Спросили учеников — отвечают сами, без сценария. Рубрика «Взгляд снизу».",
                kicker="Дети говорят",
                light=False,
            ),
            media_library.video_story(
                "no-date-other/педагог",
                "Взгляд снизу: про педагогов",
                "Кого дети называют любимым педагогом и почему — слушаем сами.",
                kicker="Дети говорят",
                light=True,
            ),
        ),
    ],
    "has_video_story": True,
    "faq_title": "Вопросы о жизни школы",
    "faq": [
        ("Это настоящие фотографии?", "Да. Все фото и видео на этой странице сняты на занятиях и событиях нашей школы в Долгопрудном — без стоков и постановочных съёмок."),
        ("Как попасть на мероприятия школы?", "Открытые занятия и городские события доступны всем — следите за анонсами или спросите администратора. Условия участия в школьных праздниках уточняйте у администратора."),
        ("Можно ли посмотреть, как проходит занятие, до записи?", "Да: приходите на бесплатную диагностику и пробный урок — увидите атмосферу изнутри. А фото и видео на этой странице помогут составить впечатление уже сейчас."),
    ],
    "extra_jsonld": [
        webpage_jsonld(
            "CollectionPage",
            "Жизнь школы Фоксинбург — фото и видео",
            "Реальные фото и видео занятий, праздников и событий языковой школы Фоксинбург в Долгопрудном: мастер-классы, выпускной, Лиса Фокси и игры на уроке.",
            SITE + "/zhizn-shkoly",
        ),
        breadcrumb_jsonld([
            ("Главная", SITE + "/"),
            ("Жизнь школы", SITE + "/zhizn-shkoly"),
        ]),
    ],
    "lead_subject": "Жизнь школы",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "cta_title": 'Хотите, чтобы ваш ребёнок был <span class="fxb-accent">в этих кадрах</span>?',
    "cta_text": "Запишитесь на бесплатную диагностику — покажем школу, познакомим с педагогами и подберём группу.",
}

PAGES["page_vypusknoj_2026.html"] = {
    # Story-страница события: Выпускной 2026 (подтверждено владельцем 22.08.2026).
    "hero_grad": "linear-gradient(135deg,#2e1a47 0%,#662d92 55%,#c24712 100%)",
    "story_hero": {
        "item_id": "2026-05-16-nikon/DSC_5117",
        "h1": 'Выпускной <span class="fxb-accent">2026</span>',
        "sub": "16 мая 2026 года мы проводили учебный год большим праздником: сцена, ведущий, награждение учеников и Лиса Фокси. Вот как это было — настоящие фото, без постановки.",
        "kicker": "История события · 16 мая 2026",
    },
    "eyebrow": "События школы",
    "h1": 'Выпускной <span class="fxb-accent">2026</span>',
    "sub": "Сцена, награждение и Лиса Фокси — большой праздник окончания учебного года.",
    "cta_label": "Записаться на диагностику",
    "feat_kicker": "Как это было",
    "feat_title": "Праздник, который собирает всю школу",
    "feat_lead": "Выпускной — точка, в которой сходится весь год: занятия, игры, мастер-классы и работа педагогов.",
    "features": [
        ("mic", "Сцена и ведущий", "Настоящая сцена, свет и ведущий — дети выступают и получают награды по-взрослому."),
        ("trophy", "Награждение", "Каждый ученик поднимается на сцену — с сертификатом, аплодисментами и поддержкой зала."),
        ("heart", "Лиса Фокси", "Наш маскот поздравляет выпускников и фотографируется с гостями — очередь к нему не расходится."),
        ("group", "Семейный праздник", "Родители — почётные гости: многие кадры дня — совместные, семейные."),
    ],
    "facts_title": "Этот день в фактах",
    "facts": [
        ("calendar", "16 мая 2026", "Дата праздника"),
        ("star", "Сцена и зал", "Награждение перед родителями"),
        ("check", "80 фотографий", "Профессиональная съёмка дня"),
        ("heart", "Лиса Фокси", "Маскот школы — в центре внимания"),
    ],
    "extra_sections": [
        media_library.life_bundle(
            media_library.real_moment(
                "2026-05-16-nikon/DSC_5235",
                "Сертификат в руках, родители рядом, сцена позади — ради таких моментов и работает школа.",
                kicker="Реальный момент",
                caption="Выпускной 2026: награждение",
                light=True,
            ),
            media_library.media_wall(
                series="2026-05-16-nikon", limit=24,
                title="Фотографии праздника", kicker="16 мая 2026",
            ),
        ),
    ],
    "faq_title": "Вопросы о праздниках школы",
    "faq": [
        ("Когда проходит выпускной?", "В конце учебного года — в мае. Этот праздник прошёл 16 мая 2026 года."),
        ("Кто участвует в выпускном?", "Ученики школы и их родители — это семейный праздник: на сцене дети, в зале семьи."),
        ("Как посмотреть школу до записи?", "Приходите на бесплатную диагностику и пробный урок — увидите атмосферу изнутри. А фото на этой странице помогут составить впечатление уже сейчас."),
    ],
    "extra_jsonld": [
        webpage_jsonld(
            "Article",
            "Выпускной 2026 в школе Фоксинбург",
            "16 мая 2026 года в Фоксинбурге прошёл выпускной: сцена, награждение учеников, сертификаты и Лиса Фокси. Реальные фотографии праздника.",
            SITE + "/vypusknoj-2026",
            date_published="2026-05-16",
        ),
        breadcrumb_jsonld([
            ("Главная", SITE + "/"),
            ("Жизнь школы", SITE + "/zhizn-shkoly"),
            ("Выпускной 2026", SITE + "/vypusknoj-2026"),
        ]),
    ],
    "lead_subject": "Выпускной 2026",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "cta_title": 'Хотите, чтобы ваш ребёнок вышел на <span class="fxb-accent">эту сцену</span>?',
    "cta_text": "Запишитесь на бесплатную диагностику — следующий выпускной может быть про вашего ребёнка.",
}

PAGES["page_ekskursii.html"] = {
    # Story-страница: экскурсии в Ю-Клинику и на пожарную станцию (июнь 2026,
    # подтверждено владельцем 22.08.2026).
    "hero_grad": "linear-gradient(135deg,#123b2e 0%,#1d6f5c 55%,#c24712 100%)",
    "story_hero": {
        "item_id": "2026-06--canon/9G6A3556",
        "h1": 'Уроки <span class="fxb-accent">за пределами класса</span>',
        "sub": "В июне 2026 года наши ученики побывали в Ю-Клинике и на пожарной станции — посмотрели профессии изнутри, потрогали всё руками и задали сотню вопросов.",
        "kicker": "Экскурсии · июнь 2026",
    },
    "eyebrow": "Экскурсии",
    "h1": 'Экскурсии: <span class="fxb-accent">Ю-Клиника и пожарная станция</span>',
    "sub": "Учиться — значит исследовать мир. Настоящие фото с экскурсий наших учеников.",
    "cta_label": "Записаться на диагностику",
    "feat_kicker": "Зачем мы это делаем",
    "feat_title": "Мир — лучший учебник",
    "feat_lead": "Экскурсии — часть нашего подхода: ребёнок учится не только по учебнику, но и через реальный опыт.",
    "features": [
        ("shield", "Пожарная станция", "Пожарная техника, гидранты и рассказы спасателей — всё можно потрогать и попробовать."),
        ("heart", "Ю-Клиника", "Кабинеты, оборудование и встреча с врачом — профессия изнутри, без белого страха."),
        ("compass", "Профессии изнутри", "Дети видят, как устроена работа врачей и спасателей, — и расширяют кругозор."),
        ("chat", "Вопросы без стеснения", "На экскурсиях дети спрашивают обо всём — любопытство здесь главный двигатель."),
    ],
    "facts_title": "Об этих экскурсиях",
    "facts": [
        ("calendar", "Июнь 2026", "Когда это было"),
        ("compass", "Две площадки", "Ю-Клиника и пожарная станция"),
        ("check", "39 фотографий", "Реальная съёмка дня"),
        ("group", "Наши ученики", "Никакой постановки и стоков"),
    ],
    "extra_sections": [
        media_library.life_bundle(
            media_library.real_moment(
                "2026-06--canon/9G6A4106",
                "Иногда лучший урок начинается далеко за пределами класса.",
                kicker="Реальный момент",
                caption="Пожарная станция, июнь 2026",
                light=True,
            ),
            media_library.media_wall(
                series="2026-06--canon", limit=39,
                title="Фотографии экскурсий", kicker="Июнь 2026",
            ),
        ),
    ],
    "faq_title": "Вопросы об экскурсиях",
    "faq": [
        ("Куда ездят ученики?", "В этот раз — в Ю-Клинику и на пожарную станцию. Площадки выбираем так, чтобы дети увидели профессии и мир изнутри."),
        ("Как узнать о следующих экскурсиях?", "Анонсы публикуются в личном кабинете ученика и в каналах школы — или просто спросите администратора."),
        ("С какого возраста можно участвовать?", "Экскурсии проходят для групп разного возраста — программу подбираем под ребят. Уточните у администратора, что планируется для вашей группы."),
    ],
    "extra_jsonld": [
        webpage_jsonld(
            "Article",
            "Экскурсии Фоксинбурга: Ю-Клиника и пожарная станция",
            "Ученики Фоксинбурга на экскурсиях в Ю-Клинике и на пожарной станции: кабинеты, оборудование, пожарная техника и живой интерес детей. Июнь 2026.",
            SITE + "/ekskursii",
            date_published="2026-06-01",
        ),
        breadcrumb_jsonld([
            ("Главная", SITE + "/"),
            ("Жизнь школы", SITE + "/zhizn-shkoly"),
            ("Экскурсии", SITE + "/ekskursii"),
        ]),
    ],
    "lead_subject": "Экскурсии школы",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "cta_title": 'Хотите, чтобы ваш ребёнок учился <span class="fxb-accent">в реальном мире</span>?',
    "cta_text": "Запишитесь на бесплатную диагностику — расскажем, как устроены занятия, академии и экскурсии.",
}

PAGES["page_prazdniki.html"] = {
    # Праздники школы: Хеллоуин 2025, Новый год 2026, Выпускной 2025,
    # мастер-классы (подтверждено владельцем 22.08.2026). Видео НГ пока
    # не прошли перфоманс-бюджет — ждут ffmpeg.
    "hero_grad": "linear-gradient(135deg,#3b1a47 0%,#8a2d62 55%,#c24712 100%)",
    "story_hero": {
        "item_id": "no-date-iphone/IMG_2561",
        "h1": 'Праздники в <span class="fxb-accent">Фоксинбурге</span>',
        "sub": "Хеллоуин, Новый год, выпускной и мастер-классы — школа живёт круглый год, и каждый праздник здесь — настоящий. Фото и видео из нашего архива.",
        "kicker": "Жизнь школы · архив",
    },
    "eyebrow": "Праздники школы",
    "h1": 'Праздники в <span class="fxb-accent">Фоксинбурге</span>',
    "sub": "Хеллоуин, Новый год, выпускной — настоящие фото и видео из архива школы.",
    "cta_label": "Записаться на диагностику",
    "feat_kicker": "Чем живёт школа",
    "feat_title": "Календарь, в котором всегда что-то происходит",
    "feat_lead": "Праздники — часть языковой среды: костюмы, игры и традиции — всё на английском.",
    "features": [
        ("star", "Хеллоуин", "Костюмы, светящиеся декорации и игры — страшно весело и совсем не страшно по-английски."),
        ("sun", "Новый год", "Ёлка, Дед Мороз, подарки и новогодние мастер-классы — праздник, которого ждут весь год."),
        ("trophy", "Выпускной", "Финал учебного года: сцена, награждение и семейные фото — смотрите нашу историю Выпускного 2026."),
        ("palette", "Мастер-классы", "Лепка, творчество и ручная работа — праздник длится дольше, когда что-то сделал сам."),
    ],
    "facts_title": "Это всё — настоящее",
    "facts": [
        ("check", "Свои фото и видео", "Только реальные праздники школы"),
        ("star", "Каждый сезон", "Праздники круглый год"),
        ("compass", "Долгопрудный", "Оба филиала празднуют вместе"),
    ],
    "extra_sections": [
        media_library.life_bundle(
            media_library.video_story(
                "2025-10-27-other/3836574427212237692",
                "Хеллоуин 2025",
                "Костюмы, реквизит и игра — короткий ролик с нашего Хеллоуина.",
                kicker="Видео из архива",
                light=False,
            ),
            media_library.video_story(
                "2025-12-20-other/8598129996493797092",
                "Новый год 2026",
                "Ёлка, Дед Мороз и праздничная программа — фрагмент нашего Нового года.",
                kicker="Видео из архива",
                light=True,
            ),
            media_library.video_story(
                "2025-12-17-other/3614670975323174660",
                "Новый год 2026: праздник продолжается",
                "Игры, подарки и новогоднее настроение — ещё один фрагмент праздника.",
                kicker="Видео из архива",
                light=True,
            ),
            media_library.real_moment(
                "no-date-iphone/IMG_2538",
                "Снеговик, ёлочные игрушки ручной работы и полная комната детей — так выглядит наш Новый год.",
                kicker="Реальный момент",
                caption="Новый год 2026 в Фоксинбурге",
                light=True,
            ),
            media_library.media_wall(
                series="no-date-iphone", limit=18,
                title="Из архива праздников", kicker="Реальные фото",
            ),
            media_library.video_story(
                "2025-05-30-other/-3667809791914063915",
                "Выпускной 2025",
                "Архивное видео прошлого выпускного — традиция продолжается каждый год.",
                kicker="Из архива · Foxy Fox → Фоксинбург",
                light=True,
            ),
        ),
    ],
    "has_video_story": True,
    "faq_title": "Вопросы о праздниках",
    "faq": [
        ("Как узнать о ближайшем празднике?", "Анонсы публикуются в новостях и каналах школы, условия участия уточняйте у администратора."),
        ("Можно ли прийти с другом?", "Да, на многие праздники ученики могут привести друга — уточните у администратора конкретное событие."),
        ("Праздники проходят на английском?", "Да: ведущие и педагоги говорят с детьми на английском в игровой форме — это часть языковой среды школы."),
    ],
    "extra_jsonld": [
        webpage_jsonld(
            "CollectionPage",
            "Праздники школы Фоксинбург — Хеллоуин, Новый год, выпускной",
            "Праздники языковой школы Фоксинбург в Долгопрудном: Хеллоуин, Новый год, выпускной и мастер-классы. Реальные фото и видео из архива школы.",
            SITE + "/prazdniki",
        ),
        breadcrumb_jsonld([
            ("Главная", SITE + "/"),
            ("Жизнь школы", SITE + "/zhizn-shkoly"),
            ("Праздники", SITE + "/prazdniki"),
        ]),
    ],
    "lead_subject": "Праздники школы",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "cta_title": 'Хотите, чтобы ваш ребёнок был на <span class="fxb-accent">следующем празднике</span>?',
    "cta_text": "Запишитесь на бесплатную диагностику — расскажем о программах и ближайших событиях школы.",
}

PAGES["page_vesennyaya_akademiya_2026.html"] = {
    # Story-страница события: Весенняя Академия 2026 (апрель 2026,
    # подтверждено владельцем 22.08.2026).
    "hero_grad": "linear-gradient(135deg,#1d4a2e 0%,#2bb673 55%,#f7971e 100%)",
    "story_hero": {
        "item_id": "2026-04-07-canon/9G6A0086",
        "h1": 'Весенняя <span class="fxb-accent">Академия 2026</span>',
        "sub": "На весенних каникулах обучение не ставится на паузу — оно становится приключением: занятия, игры и творческие мастер-классы на английском. Настоящие фото смены.",
        "kicker": "История события · апрель 2026",
    },
    "eyebrow": "Академии Фоксинбурга",
    "h1": 'Весенняя <span class="fxb-accent">Академия 2026</span>',
    "sub": "Каникулы с пользой: занятия, игры и мастер-классы на английском — настоящие фото смены.",
    "cta_label": "Записаться в Академию",
    "feat_kicker": "Как это было",
    "feat_title": "Каникулы, после которых английский становится своим",
    "feat_lead": "Весенняя Академия — это языковая среда на каникулах: без скучных уроков, но с настоящим погружением.",
    "features": [
        ("book", "Занятия в игровом формате", "Материал подаётся через игры и активности — дети говорят по-английски, не замечая «урока»."),
        ("palette", "Творческие мастер-классы", "Рисование, ручная работа и творчество на английском — язык в деле, а не в зубрёжке."),
        ("group", "Мини-группы", "Формирование по возрасту и уровню — каждый ребёнок вовлечён и получает внимание педагога."),
        ("sun", "Каникулы с пользой", "Ребёнок занят делом, родители спокойны — а английский растёт на живом общении."),
    ],
    "facts_title": "Эта смена в фактах",
    "facts": [
        ("calendar", "Апрель 2026", "Весенние каникулы"),
        ("check", "Реальные фото", "Никакой постановки и стоков"),
        ("palette", "Занятия + творчество", "Язык через живую деятельность"),
        ("compass", "Долгопрудный", "Кампус школы Фоксинбург"),
    ],
    "extra_sections": [
        media_library.life_bundle(
            media_library.real_moment(
                "2026-04-09-canon/9G6A0339",
                "Иногда самый эффективный урок выглядит как игра — и это намеренно.",
                kicker="Реальный момент",
                caption="Весенняя Академия 2026: творческое занятие",
                light=True,
            ),
            media_library.media_wall(
                series="2026-04-07-canon", limit=6,
                title="Занятия и игры", kicker="Весенняя Академия · апрель 2026",
            ),
            media_library.media_wall(
                series="2026-04-09-canon", limit=4,
                title="Творческие мастер-классы", kicker="Весенняя Академия · апрель 2026",
                light=True,
            ),
        ),
        media_library.video_story(
            "2026-07-09-other/-4292209495913586662",
            "Весенняя Академия — вживую",
            "Короткое видео со смены: атмосфера, занятия и дети — как есть.",
            kicker="Видео",
            light=False,
        ),
        (
            '<section class="fxb-section"><div class="fxb-wrap">'
            '<div class="fxb-head"><span class="fxb-kicker"><span class="fxb-dot"></span>Что дальше</span>'
            '<h2 class="fxb-h2">Похожие истории</h2>'
            '<p class="fxb-lead">Академии и выезды школы — в фотографиях и видео.</p></div>'
            '<p style="display:flex;gap:12px;flex-wrap:wrap">'
            '<a class="fxb-btn-main" href="/letnyaya-akademiya">Летняя Академия</a>'
            '<a class="fxb-btn-main" href="/ekskursii">Экскурсии: Ю-Клиника и пожарная станция</a>'
            '<a class="fxb-btn-main" href="/zhizn-shkoly">Жизнь школы</a>'
            '</p></div></section>'
        ),
    ],
    "has_video_story": True,
    "faq_title": "Вопросы об Академиях",
    "faq": [
        ("Когда проходят Академии?", "Академии работают на школьных каникулах: весной — Весенняя Академия, летом — Летняя. Эта смена прошла в апреле 2026 года."),
        ("Что входит в программу?", "Занятия английским в игровом формате, творческие мастер-классы и командные активности — всё в языковой среде."),
        ("Как записаться на следующую смену?", "Оставьте заявку на сайте или напишите нам в Max — расскажем о ближайшей смене и свободных местах."),
    ],
    "extra_jsonld": [
        webpage_jsonld(
            "Article",
            "Весенняя Академия 2026 в школе Фоксинбург",
            "Весенняя Академия Фоксинбурга 2026: занятия, игры и творческие мастер-классы на английском на весенних каникулах. Реальные фотографии смены.",
            SITE + "/vesennyaya-akademiya-2026",
            date_published="2026-04-07",
        ),
        breadcrumb_jsonld([
            ("Главная", SITE + "/"),
            ("Жизнь школы", SITE + "/zhizn-shkoly"),
            ("Весенняя Академия 2026", SITE + "/vesennyaya-akademiya-2026"),
        ]),
    ],
    "lead_subject": "Весенняя Академия",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "cta_title": 'Хотите, чтобы каникулы вашего ребёнка прошли <span class="fxb-accent">так</span>?',
    "cta_text": "Оставьте заявку — расскажем о ближайшей Академии и забронируем место в группе.",
}

PAGES["page_nositel_yazyka.html"] = {
    "page_class": "fxb-blog-page",
    "article_css": True,
    "hero_grad": "linear-gradient(135deg,#1e1433 0%,#4a2a7a 55%,#8a4fb8 100%)",
    "eyebrow": "Speaking club · с носителем языка",
    "h1": 'Занятия с <span class="fxb-accent">носителем языка</span>',
    "sub": "Разговорный клуб с носителем английского — и он уже входит в стоимость абонемента. Живая речь, настоящее произношение и культура — без доплат.",
    "cta_label": "Записаться на диагностику",
    "feat_kicker": "Как устроен клуб",
    "feat_title": "Разговорный клуб с носителем",
    "feat_lead": "Регулярные встречи, на которых ученики говорят по-английски с носителем языка — и это часть абонемента, а не отдельная услуга.",
    "features": [
        ("globe", "Ведёт носитель языка", "Клуб ведёт преподаватель, для которого английский — родной: живое произношение, современные выражения и культура из первых рук."),
        ("chat", "Живой формат", "Дискуссии, игры и разбор тем из реальной жизни: фильмы, путешествия, тренды — то, о чём говорят по-настоящему."),
        ("calendar", "Регулярные встречи", "Клуб проходит постоянно в течение учебного года — стабильная разговорная практика поверх основных занятий."),
        ("target", "По уровню", "Группы подбираем после диагностики: комфортно и тем, кто делает первые шаги в говорении, и продолжающим."),
    ],
    "facts_title": "Коротко о клубе",
    "facts": [
        ("heart", "0 ₽ доплат", "Входит в стоимость абонемента"),
        ("globe", "Носитель языка", "Живая речь и произношение"),
        ("group", "Мини-группы", "Говорит каждый участник"),
        ("calendar", "Весь учебный год", "Регулярные встречи"),
    ],
    "extra_sections": [
        '<section class="fxb-section"><div class="fxb-wrap"><div class="fxb-article-body">'
        "<h2>Входит в абонемент — без доплат</h2>"
        "<p>Разговорный клуб с носителем — не отдельная платная услуга, а часть абонемента учеников Фоксинбурга. Вы оплачиваете обычный абонемент, а живая практика с носителем уже включена в него.</p>"
        "<h2>Зачем нужен клуб с носителем</h2>"
        "<p>На основных занятиях мы даём систему: грамматику, лексику, чтение и письмо. Клуб с носителем добавляет главное — живую речь. Ученик слышит естественный темп и произношение, учится понимать на слух и перестаёт бояться говорить: с носителем по-русски не «переключишься», и это мягко выводит из зоны комфорта.</p>"
        "<p>Клуб дополняет разговорную практику наших программ — подробнее о ней на странице <a href=\"/razgovornyj-anglijskij\">разговорного английского</a>.</p>"
        '<div class="fxb-related"><h2>Смежные страницы</h2><div class="fxb-related-list">'
        '<a href="/razgovornyj-anglijskij">Разговорный английский</a>'
        '<a href="/tseny">Цены и абонементы</a>'
        '<a href="/meropriyatiya">Мероприятия школы</a>'
        "</div></div>"
        "</div></div></section>",
    ],
    "faq_title": "Частые вопросы про клуб с носителем",
    "faq": [
        ("Клуб с носителем правда входит в абонемент?", "Да. Для учеников школы разговорный клуб с носителем языка входит в стоимость абонемента — отдельно платить за него не нужно."),
        ("Кто ведёт клуб?", "Преподаватель — носитель английского языка. Это живая речь, аутентичное произношение и культурный контекст, который не даёт ни один учебник."),
        ("Какой уровень нужен для участия?", "Клуб полезен с разных уровней — группы подбираем после бесплатной диагностики так, чтобы каждому было комфортно говорить."),
        ("Как часто проходят встречи?", "Регулярно в течение учебного года. Точное расписание подскажет администратор — оно зависит от группы и филиала."),
        ("Можно прийти только на клуб, без основных занятий?", "Клуб задуман как часть обучения учеников школы — максимум пользы он даёт вместе с основной программой. Приходите на бесплатную диагностику: подберём формат под вашу задачу."),
    ],
    "extra_jsonld": [
        course_jsonld(
            "Разговорный клуб с носителем языка в Долгопрудном",
            "Занятия с носителем английского языка в Долгопрудном: разговорный клуб входит в стоимость абонемента школы Фоксинбург. Живая речь, мини-группы, очно.",
            SITE + "/nositel-yazyka",
        ),
        breadcrumb_jsonld([
            ("Главная", SITE + "/"),
            ("Носитель языка", SITE + "/nositel-yazyka"),
        ]),
    ],
    "lead_subject": "Занятия с носителем языка",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "cta_title": 'Запишитесь на <span class="fxb-accent">бесплатную диагностику</span>',
    "cta_text": "Определим уровень, подберём группу — и расскажем, когда ближайшая встреча клуба с носителем.",
}

YANDEX_MAPS_LIHACHEVSKY = "https://yandex.ru/maps/org/foksinburg/162408588499/"
YANDEX_MAPS_RAKETOSTROITELEY = "https://yandex.ru/maps/org/foksinburg/112008441352/"

# ----------------------------------------------------------------
# Интерактивный инструмент: тест уровня английского (vanilla JS,
# 15 вопросов A1→B1+, результат с рекомендацией программы).

TEST_UROVEN_QUESTIONS = [
    ("I ___ a student.", ["am", "is", "are", "be"], 0),
    ("This is my brother. ___ name is Max.", ["Her", "His", "Its", "Their"], 1),
    ("How old ___ you?", ["is", "be", "are", "am"], 2),
    ("There ___ two cats in the room.", ["is", "are", "be", "was"], 1),
    ("She ___ TV every evening.", ["watch", "watching", "watches", "watched"], 2),
    ("Yesterday we ___ to the cinema.", ["go", "goes", "went", "gone"], 2),
    ("I have lived in Moscow ___ 2015.", ["for", "since", "from", "at"], 1),
    ("This book is ___ than that one.", ["interesting", "more interesting", "most interesting", "interestinger"], 1),
    ("I ___ my keys! I can't find them anywhere.", ["lose", "have lost", "losing", "am lose"], 1),
    ("If it ___ tomorrow, we'll stay at home.", ["will rain", "rains", "rain", "rained"], 1),
    ("The report ___ by the manager yesterday.", ["wrote", "is written", "was written", "has written"], 2),
    ("I'm really looking forward ___ you again.", ["to see", "to seeing", "see", "seeing"], 1),
    ("He asked me where ___.", ["do I live", "I live", "did I live", "live I"], 1),
    ("Hardly ___ the door when the phone rang.", ["I had opened", "had I opened", "I opened", "opened I"], 1),
    ("I wish I ___ harder at school.", ["studied", "would study", "had studied", "study"], 2),
]

TEST_UROVEN_LEVELS = [
    (0, 4, "A1 — Beginner", "Вы только начинаете путь в английском — и это отличная точка старта. С базовой программой первые уверенные фразы появятся уже через несколько недель.",
     [("/doshkolniki", "Английский для дошкольников"), ("/mladshie-shkolniki", "Младшие школьники"), ("/anglijskij-dlya-vzroslyh", "Английский для взрослых с нуля")]),
    (5, 8, "A2 — Elementary", "База уже есть: вы знаете основные времена и можете говорить о простых вещах. Дальше — расширять словарный запас и добавлять уверенности в речи.",
     [("/mladshie-shkolniki", "Младшие школьники"), ("/podrostki", "Английский для подростков"), ("/razgovornyj-anglijskij", "Разговорный английский")]),
    (9, 12, "B1 — Intermediate", "Хороший средний уровень: вы уверенно держитесь в грамматике и можете объясниться в большинстве ситуаций. Следующий шаг — свободная речь и сложные конструкции.",
     [("/razgovornyj-anglijskij", "Разговорный английский"), ("/podrostki", "Английский для подростков"), ("/oge-anglijskij", "Подготовка к ОГЭ")]),
    (13, 15, "B1+ и выше", "Сильный результат! Грамматика среднего уровня вам по плечу — время двигаться к B2: экзамены, свободное общение, сложные тексты.",
     [("/ege-anglijskij", "Подготовка к ЕГЭ"), ("/oge-anglijskij", "Подготовка к ОГЭ"), ("/anglijskij-dlya-vzroslyh", "Английский для взрослых")]),
]

TEST_UROVEN_JS_DATA = (
    "window.FXB_TEST_QUESTIONS = "
    + json.dumps(
        [{"q": q, "options": opts, "answer": ans} for q, opts, ans in TEST_UROVEN_QUESTIONS],
        ensure_ascii=False,
    )
    + ";window.FXB_TEST_LEVELS = "
    + json.dumps(
        [{"min": lo, "max": hi, "title": t, "text": txt, "links": links}
         for lo, hi, t, txt, links in TEST_UROVEN_LEVELS],
        ensure_ascii=False,
    )
    + ";"
)

TEST_UROVEN_SECTION = (
    '<section class="fxb-section fxb-bg-light" id="fxb-test"><div class="fxb-wrap">'
    '<div class="fxb-head"><span class="fxb-kicker"><span class="fxb-dot"></span>Онлайн-тест</span>'
    '<h2 class="fxb-h2">Пройдите тест — это займёт около 5 минут</h2>'
    '<p class="fxb-lead">15 вопросов от простых к сложным. Отвечайте честно, не подглядывая в словарь — так результат будет точнее. Тест бесплатный и не требует регистрации.</p></div>'
    '<div class="fxb-qz" id="fxb-qz">'
    '<div class="fxb-qz-start" id="fxb-qz-start">'
    '<span class="fxb-qz-start-badge">15 вопросов · ~5 минут</span>'
    '<p class="fxb-qz-start-text">Проверим грамматику и лексику от уровня A1 до B1+. По итогу покажем ваш уровень и подскажем, какая программа Фоксинбурга подойдёт именно вам.</p>'
    '<button type="button" class="fxb-btn-main fxb-qz-btn" id="fxb-qz-begin">Начать тест</button>'
    '</div>'
    '<div class="fxb-qz-quiz" id="fxb-qz-quiz" hidden>'
    '<div class="fxb-qz-progress" role="progressbar" aria-label="Прогресс теста" aria-valuemin="0" aria-valuemax="15" aria-valuenow="0" id="fxb-qz-progress">'
    '<div class="fxb-qz-progress-bar" id="fxb-qz-bar"></div></div>'
    '<div class="fxb-qz-top"><p class="fxb-qz-counter" id="fxb-qz-counter" aria-live="polite"></p><p class="fxb-qz-pct" id="fxb-qz-pct" aria-hidden="true"></p></div>'
    '<p class="fxb-qz-question" id="fxb-qz-question"></p>'
    '<div class="fxb-qz-options" id="fxb-qz-options"></div>'
    '</div>'
    '<div class="fxb-qz-result" id="fxb-qz-result" hidden aria-live="polite"></div>'
    '<noscript><p>Для прохождения теста нужен включённый JavaScript. Вы также можете определить уровень на бесплатной диагностике с педагогом — оставьте заявку ниже.</p></noscript>'
    '</div></div></section>'
)

TEST_UROVEN_CSS = """
<style>
#fxb-page .fxb-qz{max-width:760px;margin:0 auto;background:#fff;border-radius:28px;padding:40px 42px 36px;position:relative;overflow:hidden;box-shadow:0 24px 60px -18px rgba(46,26,86,.28),0 0 0 1px rgba(123,79,192,.10)}
#fxb-page .fxb-qz::before{content:'';position:absolute;top:0;left:0;right:0;height:6px;background:linear-gradient(90deg,#7b4fc0,#a86ee0 55%,#ffd23f)}
#fxb-page .fxb-qz-start{text-align:center;padding:12px 8px}
#fxb-page .fxb-qz-start-badge{display:inline-block;font-size:13px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:#6b3fa8;background:#f3eefc;border-radius:99px;padding:7px 16px;margin-bottom:18px}
#fxb-page .fxb-qz-start-text{font-size:18px;line-height:1.65;color:#4a4360;margin:0 auto 26px;max-width:560px}
#fxb-page .fxb-qz-btn{display:inline-flex;align-items:center;justify-content:center;min-height:54px;padding:0 40px;border:0;cursor:pointer;font:inherit;font-weight:800;font-size:17px;border-radius:16px;background:linear-gradient(135deg,#7b4fc0,#5a2d8f);color:#fff;box-shadow:0 14px 30px -10px rgba(123,79,192,.55);transition:transform .16s ease,box-shadow .16s ease}
#fxb-page .fxb-qz-btn:hover{transform:translateY(-2px);box-shadow:0 18px 36px -10px rgba(123,79,192,.6)}
#fxb-page .fxb-qz-btn:active{transform:translateY(0)}
#fxb-page .fxb-qz-btn:focus-visible{outline:3px solid rgba(123,79,192,.45);outline-offset:2px}
#fxb-page .fxb-qz-top{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:0 0 12px}
#fxb-page .fxb-qz-counter{display:inline-flex;align-items:center;font-size:13px;font-weight:800;letter-spacing:.06em;color:#5a2d8f;background:#f3eefc;border-radius:99px;padding:6px 14px;margin:0}
#fxb-page .fxb-qz-pct{font-size:13px;font-weight:700;color:#6b6480;margin:0;font-variant-numeric:tabular-nums}
#fxb-page .fxb-qz-progress{height:10px;border-radius:99px;background:#eee8f9;overflow:hidden;margin-bottom:22px}
#fxb-page .fxb-qz-progress-bar{height:100%;width:0;background:linear-gradient(90deg,#7b4fc0,#a86ee0);border-radius:99px;transition:width .35s cubic-bezier(.4,0,.2,1)}
@media (prefers-reduced-motion:reduce){#fxb-page .fxb-qz-progress-bar,#fxb-page .fxb-qz-btn,#fxb-page .fxb-qz-opt{transition:none}#fxb-page .fxb-qz-quiz.is-anim .fxb-qz-question,#fxb-page .fxb-qz-quiz.is-anim .fxb-qz-options{animation:none}}
#fxb-page .fxb-qz-question{font-size:24px;font-weight:800;color:#241a36;margin:0 0 22px;line-height:1.35}
#fxb-page .fxb-qz-options{display:grid;gap:12px}
#fxb-page .fxb-qz-quiz.is-anim .fxb-qz-question, #fxb-page .fxb-qz-quiz.is-anim .fxb-qz-options{animation:fxbQzIn .26s ease}
@keyframes fxbQzIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
#fxb-page .fxb-qz-opt{display:flex;align-items:center;gap:14px;min-height:58px;padding:14px 18px;border:2px solid #e9e2f6;border-radius:16px;background:#fbfaff;font:inherit;font-size:17px;font-weight:600;text-align:left;cursor:pointer;color:#241a36;transition:transform .15s ease,border-color .15s,background .15s,box-shadow .15s}
#fxb-page .fxb-qz-letter{display:inline-flex;align-items:center;justify-content:center;flex:none;width:32px;height:32px;border-radius:10px;background:#efe8fa;color:#6b3fa8;font-size:14px;font-weight:800;transition:background .15s,color .15s}
#fxb-page .fxb-qz-opt:hover{transform:translateY(-2px);border-color:#7b4fc0;background:#fff;box-shadow:0 12px 26px -12px rgba(123,79,192,.45)}
#fxb-page .fxb-qz-opt:hover .fxb-qz-letter{background:linear-gradient(135deg,#7b4fc0,#5a2d8f);color:#fff}
#fxb-page .fxb-qz-opt:focus-visible{outline:3px solid rgba(123,79,192,.45);outline-offset:2px}
#fxb-page .fxb-qz-opt.is-sel{border-color:transparent;background:linear-gradient(135deg,#7b4fc0,#5a2d8f);color:#fff;box-shadow:0 12px 26px -10px rgba(90,45,143,.55)}
#fxb-page .fxb-qz-opt.is-sel .fxb-qz-letter{background:rgba(255,255,255,.22);color:#fff}
#fxb-page .fxb-qz-options.is-lock{pointer-events:none}
#fxb-page .fxb-qz-result{text-align:center;padding:8px 4px}
#fxb-page .fxb-qz-done-wrap{margin:0 0 18px}
#fxb-page .fxb-qz-done{display:inline-block;font-size:13px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:#2d7a4f;background:#e5f5ec;border-radius:99px;padding:7px 16px}
#fxb-page .fxb-qz-level{display:inline-block;font-size:30px;font-weight:800;color:#fff;background:linear-gradient(135deg,#7b4fc0,#5a2d8f);border-radius:20px;padding:16px 32px;margin-bottom:16px;box-shadow:0 18px 38px -12px rgba(90,45,143,.5)}
#fxb-page .fxb-qz-score{font-size:15px;font-weight:600;color:#6b6480;margin:0 0 16px}
#fxb-page .fxb-qz-text{font-size:17px;line-height:1.65;color:#4a4360;text-align:left;margin:0 0 22px}
#fxb-page .fxb-qz-links{display:flex;flex-wrap:wrap;gap:10px;justify-content:center;margin-bottom:24px}
#fxb-page .fxb-qz-links a{display:inline-flex;align-items:center;min-height:46px;padding:8px 20px;border:2px solid #e4ddf3;border-radius:99px;color:#5a2d8f;font-weight:700;text-decoration:none;transition:transform .15s,border-color .15s,background .15s}
#fxb-page .fxb-qz-links a:hover{transform:translateY(-2px);border-color:#7b4fc0;background:#f6f1fd}
#fxb-page .fxb-qz-restart{display:inline-block;margin-top:16px;background:none;border:0;color:#6b6480;font:inherit;font-size:14px;text-decoration:underline;cursor:pointer}
#fxb-page .fxb-qz-restart:hover{color:#5a2d8f}
@media (max-width:640px){#fxb-page .fxb-qz{padding:28px 18px 24px;border-radius:22px}#fxb-page .fxb-qz-question{font-size:20px}#fxb-page .fxb-qz-level{font-size:24px;padding:14px 24px}#fxb-page .fxb-qz-btn{width:100%}}

</style>
"""

TEST_UROVEN_JS = """
<script>
(function(){
  var qs = window.FXB_TEST_QUESTIONS || [];
  var lv = window.FXB_TEST_LEVELS || [];
  var start = document.getElementById('fxb-qz-start');
  var quiz = document.getElementById('fxb-qz-quiz');
  var result = document.getElementById('fxb-qz-result');
  var beginBtn = document.getElementById('fxb-qz-begin');
  var progress = document.getElementById('fxb-qz-progress');
  var bar = document.getElementById('fxb-qz-bar');
  var counter = document.getElementById('fxb-qz-counter');
  var pctEl = document.getElementById('fxb-qz-pct');
  var qEl = document.getElementById('fxb-qz-question');
  var optsEl = document.getElementById('fxb-qz-options');
  if (!beginBtn || !qs.length) return;
  var idx = 0, score = 0;
  var LETTERS = 'ABCDEFGH';
  function showQuestion(){
    var item = qs[idx];
    counter.textContent = 'Вопрос ' + (idx + 1) + ' из ' + qs.length;
    if (pctEl) pctEl.textContent = Math.round(idx / qs.length * 100) + '%';
    progress.setAttribute('aria-valuenow', String(idx));
    bar.style.width = (idx / qs.length * 100) + '%';
    qEl.textContent = item.q;
    optsEl.innerHTML = '';
    item.options.forEach(function(opt, i){
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'fxb-qz-opt';
      var chip = document.createElement('span');
      chip.className = 'fxb-qz-letter';
      chip.setAttribute('aria-hidden', 'true');
      chip.textContent = LETTERS[i] || (i + 1);
      var label = document.createElement('span');
      label.textContent = opt;
      b.appendChild(chip);
      b.appendChild(label);
      b.addEventListener('click', function(){ pick(b, i); });
      optsEl.appendChild(b);
    });
    quiz.classList.remove('is-anim');
    void quiz.offsetWidth;
    quiz.classList.add('is-anim');
    var first = optsEl.querySelector('button');
    if (first) first.focus();
  }
  function pick(btn, i){
    optsEl.classList.add('is-lock');
    btn.classList.add('is-sel');
    window.setTimeout(function(){
      optsEl.classList.remove('is-lock');
      answer(i);
    }, 220);
  }
  function answer(i){
    if (i === qs[idx].answer) score++;
    idx++;
    if (idx < qs.length) showQuestion(); else showResult();
  }
  function levelFor(s){
    for (var i = 0; i < lv.length; i++){
      if (s >= lv[i].min && s <= lv[i].max) return lv[i];
    }
    return lv[lv.length - 1];
  }
  function showResult(){
    quiz.hidden = true;
    result.hidden = false;
    bar.style.width = '100%';
    if (pctEl) pctEl.textContent = '100%';
    var l = levelFor(score);
    var html = '<div class="fxb-qz-done-wrap"><span class="fxb-qz-done">Тест пройден</span></div>'
      + '<div class="fxb-qz-level">' + l.title + '</div>'
      + '<p class="fxb-qz-score">Правильных ответов: ' + score + ' из ' + qs.length + '</p>'
      + '<p class="fxb-qz-text">' + l.text + '</p>'
      + '<div class="fxb-qz-links">'
      + l.links.map(function(ln){ return '<a href="' + ln[0] + '">' + ln[1] + '</a>'; }).join('')
      + '</div>'
      + '<a role="button" tabindex="0" class="fxb-btn-main fxb-qz-btn" data-fxb-zayavka data-fxb-subject="Тест уровня английского" data-fxb-window="Результат онлайн-теста">Пройти бесплатную диагностику с педагогом</a>'
      + '<br><button type="button" class="fxb-qz-restart" id="fxb-qz-again">Пройти тест ещё раз</button>';
    result.innerHTML = html;
    var again = document.getElementById('fxb-qz-again');
    if (again) again.addEventListener('click', function(){
      idx = 0; score = 0;
      result.hidden = true; result.innerHTML = '';
      quiz.hidden = false;
      showQuestion();
    });
    result.scrollIntoView({behavior: 'smooth', block: 'center'});
  }
  beginBtn.addEventListener('click', function(){
    start.hidden = true;
    quiz.hidden = false;
    showQuestion();
  });
})();
</script>
"""

PAGES["page_test_uroven.html"] = {
    "page_class": "fxb-blog-page",
    "article_css": True,
    "hero_grad": "linear-gradient(135deg,#241a36 0%,#2e4a68 55%,#2d6a8f 100%)",
    "eyebrow": "Бесплатно · онлайн · 15 вопросов",
    "h1": 'Тест уровня английского <span class="fxb-accent">онлайн</span>',
    "sub": "Определите свой уровень английского за 5 минут: 15 вопросов от A1 до B1+, мгновенный результат и рекомендация подходящей программы Фоксинбурга.",
    "cta_label": "Диагностика с педагогом",
    "feat_kicker": "Как это работает",
    "feat_title": "Три шага к точному результату",
    "feat_lead": "Онлайн-тест — быстрый способ сориентироваться. А точный уровень и план обучения определит педагог на бесплатной диагностике.",
    "features": [
        ("target", "15 вопросов, 5 минут", "Вопросы от простых к сложным — по одному на экране, без регистрации и оплаты."),
        ("chart", "Мгновенный результат", "Сразу после последнего ответа покажем уровень: A1, A2, B1 или B1+."),
        ("compass", "Рекомендация программы", "Подскажем, какая программа школы подойдёт под ваш уровень и цель."),
        ("chat", "Диагностика с педагогом", "Тест проверяет грамматику и лексику. Разговорные навыки оценит педагог — бесплатно."),
    ],
    "facts_title": "Коротко о тесте",
    "facts": [
        ("clock", "5 минут", "Среднее время прохождения"),
        ("check", "15 вопросов", "Грамматика и лексика A1–B1+"),
        ("star", "Бесплатно", "Без регистрации и оплаты"),
        ("cap", "Для всех возрастов", "Дети и взрослые — по уровню"),
    ],
    "extra_sections": [
        TEST_UROVEN_SECTION + TEST_UROVEN_CSS
        + '<script>' + TEST_UROVEN_JS_DATA + '</script>'
        + TEST_UROVEN_JS,
        '<section class="fxb-section"><div class="fxb-wrap"><div class="fxb-article-body">'
        "<h2>Что показывает этот тест</h2>"
        "<p>Тест проверяет грамматику и пассивный словарный запас — то, что можно проверить в формате выбора ответа. Вопросы идут от уровня A1 (базовые времена и конструкции) к B1+ (сложные времена, инверсия, условные предложения). Чем дальше проходите, тем выше уровень.</p>"
        "<p>Важно понимать: ни один онлайн-тест не измерит главное — как вы <b>говорите</b> и понимаете на слух. Поэтому мы предлагаем два шага: сначала быстрый онлайн-тест здесь, затем бесплатная диагностика с педагогом, где оцениваются все четыре навыка — говорение, аудирование, чтение и письмо.</p>"
        "<h2>Уровни английского языка: от A1 до C2</h2>"
        "<ul>"
        "<li><b>A1–A2</b> — начальный уровень: простые фразы, знакомство, бытовые темы;</li>"
        "<li><b>B1–B2</b> — средний: свободное общение на знакомые темы, уверенная грамматика; уровень B2 обычно требуется для учёбы и работы на английском;</li>"
        "<li><b>C1–C2</b> — продвинутый: беглая речь, сложные тексты, нюансы языка.</li>"
        "</ul>"
        "<p>Для школьников уровень напрямую связан с экзаменами: <a href=\"/oge-anglijskij\">ОГЭ по английскому</a> соответствует примерно A2–B1, <a href=\"/ege-anglijskij\">ЕГЭ</a> — B1–B2. Зная свой уровень, проще построить план подготовки и честно оценить сроки.</p>"
        "<h2>Что делать с результатом</h2>"
        "<p>После теста вы увидите уровень и ссылки на программы, которые ему соответствуют: <a href=\"/doshkolniki\">дошкольникам</a>, <a href=\"/mladshie-shkolniki\">младшим школьникам</a>, <a href=\"/podrostki\">подросткам</a> и <a href=\"/anglijskij-dlya-vzroslyh\">взрослым</a>. Если вы не в Долгопрудном — подойдут <a href=\"/online-zanyatiya\">онлайн-занятия</a> с той же методикой.</p>"
        "<p>Самый точный следующий шаг — бесплатная диагностика с педагогом Фоксинбурга: за 30–40 минут определим уровень по всем навыкам, разберём цели и предложим конкретную программу и расписание.</p>"
        '<div class="fxb-related"><h2>Программы по уровням</h2><div class="fxb-related-list">'
        '<a href="/mladshie-shkolniki">Младшие школьники</a>'
        '<a href="/podrostki">Подростки</a>'
        '<a href="/anglijskij-dlya-vzroslyh">Взрослые</a>'
        '<a href="/online-zanyatiya">Онлайн-занятия</a>'
        "</div></div>"
        "</div></div></section>",
    ],
    "faq_title": "Частые вопросы про тест уровня",
    "faq": [
        ("Насколько точен онлайн-тест?", "Тест точно показывает грамматику и пассивный словарный запас — этого достаточно, чтобы сориентироваться по уровню. Разговорные навыки и аудирование онлайн проверить нельзя, поэтому итоговый уровень мы определяем на бесплатной диагностике с педагогом."),
        ("Сколько времени занимает тест?", "В среднем 5 минут: 15 вопросов, по одному на экране, от простых к сложным. Можно прерваться и вернуться позже — тест не требует регистрации."),
        ("Подходит ли тест ребёнку?", "Да, вопросы нейтральные и подходят школьникам от 9–10 лет. Для детей младше лучше пройти диагностику с педагогом — она проходит в игровом формате и совсем не похожа на экзамен."),
        ("Что делать после теста?", "Посмотрите рекомендации по программам в результате и запишитесь на бесплатную диагностику с педагогом: там определим точный уровень по всем навыкам и составим план обучения."),
        ("Это правда бесплатно?", "Да. И тест, и диагностика с педагогом бесплатны и ни к чему не обязывают."),
    ],
    "extra_jsonld": [
        webpage_jsonld(
            "WebPage",
            "Тест уровня английского онлайн",
            "Бесплатный онлайн-тест уровня английского языка от Фоксинбурга: 15 вопросов A1–B1+, мгновенный результат и рекомендация программы. Диагностика с педагогом — бесплатно, очно в Долгопрудном и онлайн.",
            SITE + "/test-uroven",
        ),
        breadcrumb_jsonld([
            ("Главная", SITE + "/"),
            ("Тест уровня английского", SITE + "/test-uroven"),
        ]),
    ],
    "lead_subject": "Тест уровня английского",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "cta_title": 'Узнайте свой точный уровень на <span class="fxb-accent">бесплатной диагностике</span>',
    "cta_text": "Педагог оценит все четыре навыка — говорение, аудирование, чтение и письмо — и предложит программу под ваш уровень и цели.",
}

# ----------------------------------------------------------------
# Интерактивный инструмент №2: тест «Готов ли ребёнок к школе».
# 12 вопросов для родителя, ответы да/частично/нет (2/1/0 баллов).

GOTOV_QUESTIONS = [
    "Ребёнок может спокойно заниматься одним делом 15–20 минут?",
    "Слушает инструкцию взрослого и выполняет её с первого-двух напоминаний?",
    "Доводит начатое задание до конца, даже если оно не очень интересное?",
    "Умеет рассказать, что видел на картинке или в короткой истории?",
    "Различает звуки в словах (может назвать первый/последний звук)?",
    "Считает в пределах 10, сравнивает «больше/меньше»?",
    "Уверенно держит карандаш: обводит, штрихует, рисует по контуру?",
    "Знает буквы или читает простые слоги/слова?",
    "Общается со сверстниками: договаривается, ждёт своей очереди?",
    "Может попросить о помощи и ответить на вопрос взрослого?",
    "Самостоятельно одевается, собирает свои вещи, моет руки?",
    "Легко переживает расставание с родителем на время занятия?",
]

GOTOV_LEVELS = [
    (0, 10, "Пока рановато — есть над чем поработать",
     "Ничего страшного: навыки готовности к школе тренируются. Сейчас важны игра, режим и короткие регулярные занятия без давления. За год спокойной подготовки ребёнок придёт к школе уверенным.",
     [("/preparation", "Подготовка к школе"), ("/doshkolniki", "Английский для дошкольников")]),
    (11, 18, "Почти готов — несколько навыков стоит подтянуть",
     "База хорошая! Обратите внимание на вопросы, где ответили «частично» или «нет» — это точки роста на ближайшие месяцы. Регулярные занятия закроют их без спешки.",
     [("/preparation", "Подготовка к школе"), ("/blog-gotov-li-rebenok-k-shkole", "Статья: как проверить готовность")]),
    (19, 24, "Готов к школе!",
     "Отличный результат: у ребёнка сформирована база для уверенного старта. Осталось поддерживать навыки и интерес к учёбе — и можно смело идти в первый класс.",
     [("/preparation", "Подготовка к школе"), ("/mladshie-shkolniki", "Английский для младших школьников")]),
]

GOTOV_JS_DATA = (
    "window.FXB_GOTOV_QUESTIONS = " + json.dumps(GOTOV_QUESTIONS, ensure_ascii=False) + ";"
    "window.FXB_GOTOV_LEVELS = " + json.dumps(
        [{"min": lo, "max": hi, "title": t, "text": txt, "links": links}
         for lo, hi, t, txt, links in GOTOV_LEVELS], ensure_ascii=False) + ";"
)

GOTOV_SECTION = (
    '<section class="fxb-section fxb-bg-light" id="fxb-test"><div class="fxb-wrap">'
    '<div class="fxb-head"><span class="fxb-kicker"><span class="fxb-dot"></span>Тест для родителей</span>'
    '<h2 class="fxb-h2">12 вопросов — отвечайте честно, как есть сейчас</h2>'
    '<p class="fxb-lead">Тест оценивает не «знания», а готовность: внимание, речь, моторику, самостоятельность и общение. Отвечайте по текущей ситуации, а не «как хотелось бы». Это ориентир, а не диагноз.</p></div>'
    '<div class="fxb-qz" id="fxb-qz">'
    '<div class="fxb-qz-start" id="fxb-qz-start">'
    '<span class="fxb-qz-start-badge">12 вопросов · ~3 минуты</span>'
    '<p class="fxb-qz-start-text">На каждый вопрос три варианта: «Да» (2 балла), «Частично» (1) и «Пока нет» (0). По итогу покажем общую картину и подскажем, что развивать.</p>'
    '<button type="button" class="fxb-btn-main fxb-qz-btn" id="fxb-qz-begin">Начать тест</button>'
    '</div>'
    '<div class="fxb-qz-quiz" id="fxb-qz-quiz" hidden>'
    '<div class="fxb-qz-progress" role="progressbar" aria-label="Прогресс теста" aria-valuemin="0" aria-valuemax="12" aria-valuenow="0" id="fxb-qz-progress">'
    '<div class="fxb-qz-progress-bar" id="fxb-qz-bar"></div></div>'
    '<div class="fxb-qz-top"><p class="fxb-qz-counter" id="fxb-qz-counter" aria-live="polite"></p><p class="fxb-qz-pct" id="fxb-qz-pct" aria-hidden="true"></p></div>'
    '<p class="fxb-qz-question" id="fxb-qz-question"></p>'
    '<div class="fxb-qz-options" id="fxb-qz-options"></div>'
    '</div>'
    '<div class="fxb-qz-result" id="fxb-qz-result" hidden aria-live="polite"></div>'
    '<noscript><p>Для прохождения теста нужен включённый JavaScript. Вы также можете пройти бесплатную диагностику готовности к школе с педагогом — оставьте заявку ниже.</p></noscript>'
    '</div></div></section>'
)

GOTOV_JS = """
<script>
(function(){
  var qs = window.FXB_GOTOV_QUESTIONS || [];
  var lv = window.FXB_GOTOV_LEVELS || [];
  var OPTS = [['Да', 2], ['Частично', 1], ['Пока нет', 0]];
  var start = document.getElementById('fxb-qz-start');
  var quiz = document.getElementById('fxb-qz-quiz');
  var result = document.getElementById('fxb-qz-result');
  var beginBtn = document.getElementById('fxb-qz-begin');
  var progress = document.getElementById('fxb-qz-progress');
  var bar = document.getElementById('fxb-qz-bar');
  var counter = document.getElementById('fxb-qz-counter');
  var pctEl = document.getElementById('fxb-qz-pct');
  var qEl = document.getElementById('fxb-qz-question');
  var optsEl = document.getElementById('fxb-qz-options');
  if (!beginBtn || !qs.length) return;
  var idx = 0, score = 0;
  var LETTERS = 'ABCDEFGH';
  function showQuestion(){
    counter.textContent = 'Вопрос ' + (idx + 1) + ' из ' + qs.length;
    if (pctEl) pctEl.textContent = Math.round(idx / qs.length * 100) + '%';
    progress.setAttribute('aria-valuenow', String(idx));
    bar.style.width = (idx / qs.length * 100) + '%';
    qEl.textContent = qs[idx];
    optsEl.innerHTML = '';
    OPTS.forEach(function(o, i){
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'fxb-qz-opt';
      var chip = document.createElement('span');
      chip.className = 'fxb-qz-letter';
      chip.setAttribute('aria-hidden', 'true');
      chip.textContent = LETTERS[i] || (i + 1);
      var label = document.createElement('span');
      label.textContent = o[0];
      b.appendChild(chip);
      b.appendChild(label);
      b.addEventListener('click', function(){ pick(b, o[1]); });
      optsEl.appendChild(b);
    });
    quiz.classList.remove('is-anim');
    void quiz.offsetWidth;
    quiz.classList.add('is-anim');
    var first = optsEl.querySelector('button');
    if (first) first.focus();
  }
  function pick(btn, points){
    optsEl.classList.add('is-lock');
    btn.classList.add('is-sel');
    window.setTimeout(function(){
      optsEl.classList.remove('is-lock');
      answer(points);
    }, 220);
  }
  function answer(points){
    score += points;
    idx++;
    if (idx < qs.length) showQuestion(); else showResult();
  }
  function levelFor(s){
    for (var i = 0; i < lv.length; i++){
      if (s >= lv[i].min && s <= lv[i].max) return lv[i];
    }
    return lv[lv.length - 1];
  }
  function showResult(){
    quiz.hidden = true;
    result.hidden = false;
    bar.style.width = '100%';
    if (pctEl) pctEl.textContent = '100%';
    var l = levelFor(score);
    var html = '<div class="fxb-qz-done-wrap"><span class="fxb-qz-done">Тест пройден</span></div>'
      + '<div class="fxb-qz-level">' + l.title + '</div>'
      + '<p class="fxb-qz-score">Баллы: ' + score + ' из ' + (qs.length * 2) + '</p>'
      + '<p class="fxb-qz-text">' + l.text + '</p>'
      + '<div class="fxb-qz-links">'
      + l.links.map(function(ln){ return '<a href="' + ln[0] + '">' + ln[1] + '</a>'; }).join('')
      + '</div>'
      + '<a role="button" tabindex="0" class="fxb-btn-main fxb-qz-btn" data-fxb-zayavka data-fxb-subject="Диагностика готовности к школе" data-fxb-window="Результат теста готовности">Пройти бесплатную диагностику с педагогом</a>'
      + '<br><button type="button" class="fxb-qz-restart" id="fxb-qz-again">Пройти тест ещё раз</button>';
    result.innerHTML = html;
    var again = document.getElementById('fxb-qz-again');
    if (again) again.addEventListener('click', function(){
      idx = 0; score = 0;
      result.hidden = true; result.innerHTML = '';
      quiz.hidden = false;
      showQuestion();
    });
    result.scrollIntoView({behavior: 'smooth', block: 'center'});
  }
  beginBtn.addEventListener('click', function(){
    start.hidden = true;
    quiz.hidden = false;
    showQuestion();
  });
})();
</script>
"""

PAGES["page_test_gotov_k_shkole.html"] = {
    "page_class": "fxb-blog-page",
    "article_css": True,
    "hero_grad": "linear-gradient(135deg,#1a2e24 0%,#2d6a4f 55%,#40916c 100%)",
    "eyebrow": "Бесплатно · онлайн · 12 вопросов",
    "h1": 'Готов ли ребёнок к школе: <span class="fxb-accent">тест</span> для родителей',
    "sub": "Проверьте готовность ребёнка к школе за 3 минуты: внимание, речь, моторика, самостоятельность и общение. Мгновенный результат и рекомендации.",
    "cta_label": "Диагностика с педагогом",
    "feat_kicker": "Как это работает",
    "feat_title": "Три шага к пониманию картины",
    "feat_lead": "Тест — быстрый ориентир для родителей. Точную картину по всем навыкам покажет бесплатная диагностика с педагогом.",
    "features": [
        ("check", "12 вопросов, 3 минуты", "Ответы «да / частично / нет» — по текущей ситуации, без подготовки."),
        ("chart", "Мгновенный результат", "Сразу после последнего ответа — общая картина готовности по баллам."),
        ("target", "Точки роста", "Вопросы, где ответили «нет» или «частично», — это и есть план на ближайшие месяцы."),
        ("cap", "Диагностика с педагогом", "Педагог проверит навыки вживую в игровом формате и даст конкретные рекомендации — бесплатно."),
    ],
    "facts_title": "Коротко о тесте",
    "facts": [
        ("clock", "3 минуты", "Среднее время прохождения"),
        ("check", "12 вопросов", "5 областей готовности"),
        ("star", "Бесплатно", "Без регистрации"),
        ("cap", "5–7 лет", "Для будущих первоклассников"),
    ],
    "extra_sections": [
        GOTOV_SECTION + TEST_UROVEN_CSS
        + '<script>' + GOTOV_JS_DATA + '</script>'
        + GOTOV_JS,
        '<section class="fxb-section"><div class="fxb-wrap"><div class="fxb-article-body">'
        "<h2>Что такое «готовность к школе»</h2>"
        "<p>Готовность к школе — это не умение читать и считать. По ФГОС школа обязана принять ребёнка без этих навыков. Настоящая готовность — это пять областей: внимание и усидчивость, речь и словарь, мелкая моторика, логика и счёт, самостоятельность и общение. Именно по ним построен наш тест.</p>"
        "<p>Если по какой-то области набирается мало баллов — это не приговор, а план. Навыки готовности прекрасно тренируются в игровом формате за 6–12 месяцев до школы. Подробнее о каждой области читайте в статье <a href=\"/blog-gotov-li-rebenok-k-shkole\">«Готов ли ребёнок к школе: чек-лист для родителей»</a>.</p>"
        "<h2>Что делать с результатом</h2>"
        "<p>Посмотрите, на какие вопросы ответили «частично» или «пока нет» — это конкретные точки роста. Внимание проседает — играйте в настольные игры с правилами. Моторика — рисование, лепка, штриховки. Самостоятельность — больше бытовых поручений. Речь — пересказы историй и разговоры «почему?».</p>"
        "<p>Самый точный следующий шаг — бесплатная диагностика в Фоксинбурге: педагог проверит навыки вживую в игровом формате (для ребёнка это не экзамен, а занятие) и расскажет, какая программа <a href=\"/preparation\">подготовки к школе</a> подойдёт именно вам.</p>"
        '<div class="fxb-related"><h2>Полезное по теме</h2><div class="fxb-related-list">'
        '<a href="/preparation">Подготовка к школе</a>'
        '<a href="/blog-gotov-li-rebenok-k-shkole">Чек-лист готовности</a>'
        '<a href="/doshkolniki">Английский для дошкольников</a>'
        "</div></div>"
        "</div></div></section>",
    ],
    "faq_title": "Частые вопросы про готовность к школе",
    "faq": [
        ("Насколько точен этот тест?", "Тест — ориентир для родителей по пять ключевым областям готовности. Он не заменяет педагога: точную картину покажет диагностика вживую, где педагог смотрит на ребёнка в деле, а не на ответы родителя."),
        ("Ребёнок не умеет читать — это проблема?", "Нет. По ФГОС уметь читать к школе не обязательно. Важнее фонематический слух, речь, внимание и самостоятельность — они и есть основа, на которую чтение ложится легко."),
        ("Когда начинать подготовку к школе?", "Комфортно — за год, занятия 2 раза в неделю в игровом формате. За 2–3 месяца тоже можно усилить отдельные навыки, но без спешки результат устойчивее."),
        ("Что будет на диагностике?", "Игровое занятие 30–40 минут: задания на внимание, логику, речь, моторику и общение. Ребёнку — интересно, родителю — подробная обратная связь и план. Бесплатно и без обязательств."),
    ],
    "extra_jsonld": [
        webpage_jsonld(
            "WebPage",
            "Готов ли ребёнок к школе: тест для родителей",
            "Бесплатный тест готовности ребёнка к школе: 12 вопросов по вниманию, речи, моторике и самостоятельности. Мгновенный результат и рекомендации педагогов Фоксинбурга.",
            SITE + "/test-gotov-k-shkole",
        ),
        breadcrumb_jsonld([
            ("Главная", SITE + "/"),
            ("Тест: готов ли ребёнок к школе", SITE + "/test-gotov-k-shkole"),
        ]),
    ],
    "lead_subject": "Диагностика готовности к школе",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "cta_title": 'Проверьте готовность на <span class="fxb-accent">бесплатной диагностике</span>',
    "cta_text": "Педагог проверит внимание, речь, логику, моторику и самостоятельность в игровом формате и даст конкретный план подготовки.",
}

# ----------------------------------------------------------------
# Интерактивный инструмент №3: квиз «Какой формат занятий подойдёт».
# 7 вопросов, скоринг по 4 форматам: group_offline / individual / online / intensive.

FORMAT_QUESTIONS = [
    ("Для кого подбираем занятия?", [
        ("Для ребёнка 3–6 лет", {"group_offline": 2, "intensive": 1}, "pre"),
        ("Для ребёнка 7–10 лет", {"group_offline": 2, "intensive": 1}, "junior"),
        ("Для подростка 11–16 лет", {"group_offline": 1, "online": 1, "individual": 1}, "teen"),
        ("Для взрослого", {"online": 2, "individual": 1}, "adult"),
    ]),
    ("Какая цель главная?", [
        ("Заговорить и полюбить язык", {"group_offline": 2, "online": 1}, None),
        ("Школьные оценки и экзамены", {"individual": 2, "group_offline": 1}, None),
        ("Быстрый результат к конкретной дате", {"intensive": 2, "individual": 1}, None),
        ("Занять ребёнка с пользой", {"intensive": 2, "group_offline": 1}, None),
    ]),
    ("Как удобнее добираться?", [
        ("Живём рядом с Долгопрудным — готовы ездить", {"group_offline": 2}, None),
        ("Дорога до филиала неудобна", {"online": 2}, None),
        ("Только из дома, без поездок", {"online": 2, "individual": 1}, None),
    ]),
    ("Как ученик лучше включается?", [
        ("В компании сверстников", {"group_offline": 2, "intensive": 1}, None),
        ("Наедине с педагогом", {"individual": 2}, None),
        ("Одинаково в любом окружении", {"group_offline": 1, "individual": 1}, None),
    ]),
    ("Какой темп нужен?", [
        ("Спокойный регулярный, вдолгую", {"group_offline": 1, "online": 1}, None),
        ("Интенсивный и короткий", {"intensive": 2}, None),
        ("Максимально гибкий график", {"individual": 1, "online": 1}, None),
    ]),
    ("Какой бюджет комфортен?", [
        ("Оптимальный: максимум пользы за разумные деньги", {"group_offline": 2, "online": 1}, None),
        ("Средний", {"online": 1, "group_offline": 1}, None),
        ("Готовы инвестировать в скорость", {"individual": 2, "intensive": 1}, None),
    ]),
    ("Когда планируете начать?", [
        ("Сейчас, в учебном году", {"group_offline": 1, "individual": 1, "online": 1}, None),
        ("На каникулах или летом", {"intensive": 2}, None),
        ("Ещё выбираю и присматриваюсь", {}, None),
    ]),
]

FORMAT_RESULTS = {
    "group_offline": {
        "title": "Мини-группа очно в Долгопрудном",
        "text": "Ваш профиль — классический для очной мини-группы: есть возможность приезжать, ученик раскрывается рядом со сверстниками, а регулярный темп важнее спринта. В группе 6–8 человек каждый говорит на каждом занятии, а мотивация от компании держится годами. Оба филиала — Лихачёвский 76к1 и Ракетостроителей 9к3.",
        "price": "от 9000 ₽/мес",
    },
    "individual": {
        "title": "Индивидуальные занятия с педагогом",
        "text": "Ваши ответы указывают на индивидуальный формат: точечная задача, гибкий график или максимальная концентрация на ученике. Каждая минута занятия работает на вашу цель — пробелы, экзамен, нестандартный темп. Очно в Долгопрудном или онлайн.",
        "price": "2500 ₽/час",
    },
    "online": {
        "title": "Онлайн-занятия",
        "text": "Вам подойдёт онлайн-формат: та же коммуникативная методика и те же педагоги, но без дороги и с гибким расписанием. Онлайн-группы у нас миниатюрные — разговорной практики хватает каждому. Удобно и для семей не из Долгопрудного.",
        "price": "от 9000 ₽/мес",
    },
    "intensive": {
        "title": "Интенсив — Летняя Академия",
        "text": "Ваш сценарий — интенсив: короткий срок, конкретная цель или желание занять ребёнка с пользой на каникулах. Две недели ежедневного погружения дают эффект нескольких месяцев обычных занятий — и заряд мотивации на весь год.",
        "price": "расписание и цены — на странице Летней Академии",
    },
}

# Ссылки на программы по возрасту из ответа на вопрос №1 (для group_offline)
FORMAT_AGE_LINKS = {
    "pre": [("/doshkolniki", "Английский для дошкольников"), ("/mladshie-shkolniki", "Младшим школьникам"), ("/tseny", "Цены")],
    "junior": [("/mladshie-shkolniki", "Младшим школьникам"), ("/podrostki", "Подросткам"), ("/tseny", "Цены")],
    "teen": [("/podrostki", "Подросткам"), ("/oge-anglijskij", "Подготовка к ОГЭ"), ("/tseny", "Цены")],
    "adult": [("/anglijskij-dlya-vzroslyh", "Взрослым"), ("/razgovornyj-anglijskij", "Разговорный курс"), ("/tseny", "Цены")],
}

FORMAT_FORMAT_LINKS = {
    "group_offline": None,  # подставляются по возрасту
    "individual": [("/repetitor", "Индивидуальные занятия"), ("/repetitor-nachalnaya-shkola", "Репетитор: начальная школа"), ("/tseny", "Цены")],
    "online": [("/online-zanyatiya", "Онлайн-занятия"), ("/podderzhivayushchie-online", "Поддерживающие онлайн"), ("/tseny", "Цены")],
    "intensive": [("/letnyaya-akademiya", "Летняя Академия"), ("/blog-letnij-intensiv-itogi-i-plany", "Зачем нужен интенсив"), ("/tseny", "Цены")],
}

FORMAT_PRIORITY = ["group_offline", "online", "individual", "intensive"]

FORMAT_JS_DATA = (
    "window.FXB_FORMAT_QUESTIONS = " + json.dumps(
        [{"q": q, "options": [{"t": t, "pts": pts, "age": age} for t, pts, age in opts]}
         for q, opts in FORMAT_QUESTIONS],
        ensure_ascii=False) + ";"
    "window.FXB_FORMAT_RESULTS = " + json.dumps(
        {k: {"title": v["title"], "text": v["text"], "price": v["price"],
             "links": FORMAT_FORMAT_LINKS[k]}
         for k, v in FORMAT_RESULTS.items()},
        ensure_ascii=False) + ";"
    "window.FXB_FORMAT_AGE_LINKS = " + json.dumps(FORMAT_AGE_LINKS, ensure_ascii=False) + ";"
    "window.FXB_FORMAT_PRIORITY = " + json.dumps(FORMAT_PRIORITY, ensure_ascii=False) + ";"
)

FORMAT_SECTION = (
    '<section class="fxb-section fxb-bg-light" id="fxb-test"><div class="fxb-wrap">'
    '<div class="fxb-head"><span class="fxb-kicker"><span class="fxb-dot"></span>Квиз-подбор</span>'
    '<h2 class="fxb-h2">7 вопросов — и вы знаете свой формат</h2>'
    '<p class="fxb-lead">Отвечайте как есть, а не «как правильно». Квиз учитывает возраст, цель, логистику, характер ученика, темп и бюджет — и рекомендует один из четырёх форматов Фоксинбурга.</p></div>'
    '<div class="fxb-qz" id="fxb-qz">'
    '<div class="fxb-qz-start" id="fxb-qz-start">'
    '<span class="fxb-qz-start-badge">7 вопросов · ~2 минуты</span>'
    '<p class="fxb-qz-start-text">Мини-группа очно, индивидуально, онлайн или интенсив? Ошибка в выборе формата стоит потерянного года и потухшего интереса. Потратьте 2 минуты — и выбирайте осознанно.</p>'
    '<button type="button" class="fxb-btn-main fxb-qz-btn" id="fxb-qz-begin">Подобрать формат</button>'
    '</div>'
    '<div class="fxb-qz-quiz" id="fxb-qz-quiz" hidden>'
    '<div class="fxb-qz-progress" role="progressbar" aria-label="Прогресс квиза" aria-valuemin="0" aria-valuemax="7" aria-valuenow="0" id="fxb-qz-progress">'
    '<div class="fxb-qz-progress-bar" id="fxb-qz-bar"></div></div>'
    '<div class="fxb-qz-top"><p class="fxb-qz-counter" id="fxb-qz-counter" aria-live="polite"></p><p class="fxb-qz-pct" id="fxb-qz-pct" aria-hidden="true"></p></div>'
    '<p class="fxb-qz-question" id="fxb-qz-question"></p>'
    '<div class="fxb-qz-options" id="fxb-qz-options"></div>'
    '</div>'
    '<div class="fxb-qz-result" id="fxb-qz-result" hidden aria-live="polite"></div>'
    '<noscript><p>Для прохождения квиза нужен включённый JavaScript. Подобрать формат можно и на бесплатной консультации — оставьте заявку ниже.</p></noscript>'
    '</div></div></section>'
)

FORMAT_JS = """
<script>
(function(){
  var qs = window.FXB_FORMAT_QUESTIONS || [];
  var rs = window.FXB_FORMAT_RESULTS || {};
  var ageLinks = window.FXB_FORMAT_AGE_LINKS || {};
  var priority = window.FXB_FORMAT_PRIORITY || [];
  var start = document.getElementById('fxb-qz-start');
  var quiz = document.getElementById('fxb-qz-quiz');
  var result = document.getElementById('fxb-qz-result');
  var beginBtn = document.getElementById('fxb-qz-begin');
  var progress = document.getElementById('fxb-qz-progress');
  var bar = document.getElementById('fxb-qz-bar');
  var counter = document.getElementById('fxb-qz-counter');
  var pctEl = document.getElementById('fxb-qz-pct');
  var qEl = document.getElementById('fxb-qz-question');
  var optsEl = document.getElementById('fxb-qz-options');
  if (!beginBtn || !qs.length) return;
  var idx = 0, scores = {}, age = null;
  var LETTERS = 'ABCDEFGH';
  function reset(){
    idx = 0; age = null;
    scores = {group_offline: 0, individual: 0, online: 0, intensive: 0};
  }
  reset();
  function showQuestion(){
    var item = qs[idx];
    counter.textContent = 'Вопрос ' + (idx + 1) + ' из ' + qs.length;
    if (pctEl) pctEl.textContent = Math.round(idx / qs.length * 100) + '%';
    progress.setAttribute('aria-valuenow', String(idx));
    bar.style.width = (idx / qs.length * 100) + '%';
    qEl.textContent = item.q;
    optsEl.innerHTML = '';
    item.options.forEach(function(opt, i){
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'fxb-qz-opt';
      var chip = document.createElement('span');
      chip.className = 'fxb-qz-letter';
      chip.setAttribute('aria-hidden', 'true');
      chip.textContent = LETTERS[i] || (i + 1);
      var label = document.createElement('span');
      label.textContent = opt.t;
      b.appendChild(chip);
      b.appendChild(label);
      b.addEventListener('click', function(){ pick(b, opt); });
      optsEl.appendChild(b);
    });
    quiz.classList.remove('is-anim');
    void quiz.offsetWidth;
    quiz.classList.add('is-anim');
    var first = optsEl.querySelector('button');
    if (first) first.focus();
  }
  function pick(btn, opt){
    optsEl.classList.add('is-lock');
    btn.classList.add('is-sel');
    window.setTimeout(function(){
      optsEl.classList.remove('is-lock');
      answer(opt);
    }, 220);
  }
  function answer(opt){
    if (opt.age) age = opt.age;
    for (var k in opt.pts){ if (opt.pts.hasOwnProperty(k)) scores[k] += opt.pts[k]; }
    idx++;
    if (idx < qs.length) showQuestion(); else showResult();
  }
  function winner(){
    var best = priority[0], bestVal = -1;
    priority.forEach(function(k){
      if ((scores[k] || 0) > bestVal){ bestVal = scores[k]; best = k; }
    });
    return best;
  }
  function showResult(){
    quiz.hidden = true;
    result.hidden = false;
    bar.style.width = '100%';
    if (pctEl) pctEl.textContent = '100%';
    progress.setAttribute('aria-valuenow', String(qs.length));
    var key = winner();
    var r = rs[key];
    var links = (key === 'group_offline' && age && ageLinks[age]) ? ageLinks[age] : (r.links || []);
    var html = '<div class="fxb-qz-done-wrap"><span class="fxb-qz-done">Квиз пройден</span></div>'
      + '<div class="fxb-qz-level">' + r.title + '</div>'
      + '<p class="fxb-qz-score">Ориентир по цене: ' + r.price + '</p>'
      + '<p class="fxb-qz-text">' + r.text + '</p>'
      + '<div class="fxb-qz-links">'
      + links.map(function(ln){ return '<a href="' + ln[0] + '">' + ln[1] + '</a>'; }).join('')
      + '</div>'
      + '<a role="button" tabindex="0" class="fxb-btn-main fxb-qz-btn" data-fxb-zayavka data-fxb-subject="Подбор формата занятий" data-fxb-window="Результат теста формата">Проверить выбор на бесплатной диагностике</a>'
      + '<br><button type="button" class="fxb-qz-restart" id="fxb-qz-again">Пройти ещё раз</button>';
    result.innerHTML = html;
    var again = document.getElementById('fxb-qz-again');
    if (again) again.addEventListener('click', function(){
      reset();
      result.hidden = true; result.innerHTML = '';
      quiz.hidden = false;
      showQuestion();
    });
    result.scrollIntoView({behavior: 'smooth', block: 'center'});
  }
  beginBtn.addEventListener('click', function(){
    start.hidden = true;
    quiz.hidden = false;
    showQuestion();
  });
})();
</script>
"""

PAGES["page_test_format.html"] = {
    "page_class": "fxb-blog-page",
    "article_css": True,
    "hero_grad": "linear-gradient(135deg,#2b1a12 0%,#6b3a1e 55%,#8f5a2d 100%)",
    "eyebrow": "Бесплатно · онлайн · 7 вопросов",
    "h1": 'Какой формат занятий английского <span class="fxb-accent">выбрать</span>',
    "sub": "Мини-группа, индивидуально, онлайн или интенсив? Ответьте на 7 вопросов — и квиз подберёт формат под возраст, цель, логистику и бюджет вашей семьи.",
    "cta_label": "Бесплатная диагностика",
    "feat_kicker": "Как это работает",
    "feat_title": "Формат решает половину результата",
    "feat_lead": "Неподходящий формат — главная причина «занимались год и бросили». Квиз помогает выбрать осознанно, а диагностика с педагогом подтверждает выбор.",
    "features": [
        ("check", "7 вопросов, 2 минуты", "Возраст, цель, дорога, характер ученика, темп, бюджет и сроки — без регистрации."),
        ("target", "Рекомендация формата", "Мини-группа очно, индивидуально, онлайн или интенсив — с пояснением, почему именно он."),
        ("compass", "Ссылки на программы", "К результату приложены программы под ваш возраст и актуальные цены."),
        ("chat", "Проверка на диагностике", "Финальное решение подтвердит педагог на бесплатной диагностике — формат видно в деле."),
    ],
    "facts_title": "Коротко о квизе",
    "facts": [
        ("clock", "2 минуты", "Среднее время прохождения"),
        ("check", "7 вопросов", "4 формата на выбор"),
        ("star", "Бесплатно", "Без регистрации"),
        ("cap", "Все возрасты", "От 3 лет до взрослых"),
    ],
    "extra_sections": [
        FORMAT_SECTION + TEST_UROVEN_CSS
        + '<script>' + FORMAT_JS_DATA + '</script>'
        + FORMAT_JS,
        '<section class="fxb-section"><div class="fxb-wrap"><div class="fxb-article-body">'
        "<h2>Какие форматы есть в Фоксинбурге</h2>"
        "<p><b>Мини-группы очно (от 9000 ₽/мес).</b> Основной формат школы: 6–8 человек одного уровня, коммуникативная методика, разговорная практика на каждом занятии. Программы по возрастам: <a href=\"/doshkolniki\">дошкольники</a>, <a href=\"/mladshie-shkolniki\">младшие школьники</a>, <a href=\"/podrostki\">подростки</a> и <a href=\"/anglijskij-dlya-vzroslyh\">взрослые</a>. Оба филиала в Долгопрудном.</p>"
        "<p><b>Индивидуально (2500 ₽/час).</b> <a href=\"/repetitor\">Занятия с педагогом один на один</a> — для точечных задач: закрыть пробелы, разогнаться к экзамену, гибкий график. Часто оптимальна связка «группа как база + индивидуальный блок под задачу» — об этом статья «<a href=\"/blog-repetitor-ili-gruppa\">Репетитор или группа</a>».</p>"
        "<p><b>Онлайн (от 9000 ₽/мес).</b> Те же педагоги и методика без дороги: <a href=\"/online-zanyatiya\">онлайн-группы</a> и <a href=\"/podderzhivayushchie-online\">поддерживающие занятия</a> для тех, кто не в Долгопрудном или ценит гибкость.</p>"
        "<p><b>Интенсив.</b> <a href=\"/letnyaya-akademiya\">Летняя Академия</a> и каникулярные программы: две недели ежедневного погружения дают эффект месяцев — подробности в статье «<a href=\"/blog-letnij-intensiv-itogi-i-plany\">Летний интенсив</a>».</p>"
        "<h2>Как понять, что формат не подошёл</h2>"
        "<p>Формат — не приговор: у нас его можно сменить бесплатно, программа единая, педагоги передают контекст. Но раньше — лучше. Тревожные признаки за первые 1–2 месяца:</p>"
        "<ul>"
        "<li>ребёнок ходит без удовольствия, домашние задания — битва;</li>"
        "<li>на вопрос «что нового узнал?» ответа нет;</li>"
        "<li>в группе скучно (сильнее одногруппников) или тревожно (слабее);</li>"
        "<li>дорога отнимает больше сил, чем даёт занятие — смотрите в сторону онлайн.</li>"
        "</ul>"
        "<p>Любой из этих сигналов — повод прийти к администратору и обсудить смену формата или группы: это штатная ситуация, а не жалоба. Актуальные цены на все форматы — на странице <a href=\"/tseny\">цен</a>.</p>"
        '<div class="fxb-related"><h2>Полезное по теме</h2><div class="fxb-related-list">'
        '<a href="/tseny">Цены на программы</a>'
        '<a href="/test-uroven">Тест уровня английского</a>'
        '<a href="/online-zanyatiya">Онлайн-занятия</a>'
        '<a href="/repetitor">Индивидуальные занятия</a>'
        "</div></div>"
        "</div></div></section>",
    ],
    "faq_title": "Частые вопросы про форматы",
    "faq": [
        ("Можно ли сменить формат потом?", "Да, бесплатно. Программа единая для всех форматов, педагоги передают контекст друг другу — переход из группы в индивидуальный формат или онлайн (и обратно) проходит безболезненно. Такой переход — штатная ситуация, например перед ОГЭ часть учеников уходит на индивидуальный блок и возвращается."),
        ("Что эффективнее — группа или индивидуально?", "Зависит от задачи. Для долгосрочного развития языка и разговорной практики эффективнее мини-группа: живая речь со сверстниками и мотивация. Для точечных пробелов и сжатых сроков быстрее индивидуальный формат. Часто оптимум — группа как основа плюс короткий индивидуальный блок."),
        ("Онлайн хуже офлайна?", "Нет, если группа маленькая и методика коммуникативная: наши онлайн-занятия ведут те же педагоги по той же программе, а размер групп такой же миниатюрный. Онлайн проигрывает только в одном — детям дошкольного возраста важен живой контакт и подвижные игры, им мы рекомендуем офлайн."),
        ("Сколько стоит каждый формат?", "Мини-группы очно и онлайн — от 9000 ₽ в месяц, индивидуальные занятия — 2500 ₽ в час, пробное занятие — 1125 ₽. Обучение можно оплатить маткапиталом и вернуть 13% налоговым вычетом — школа работает по образовательной лицензии. Актуальные тарифы — на странице цен."),
    ],
    "extra_jsonld": [
        webpage_jsonld(
            "WebPage",
            "Какой формат занятий английского выбрать — квиз",
            "Бесплатный онлайн-квиз Фоксинбурга: 7 вопросов — и вы знаете, какой формат подойдёт: мини-группа очно в Долгопрудном, индивидуальные занятия, онлайн или интенсив. С ценами и ссылками на программы.",
            SITE + "/test-format",
        ),
        breadcrumb_jsonld([
            ("Главная", SITE + "/"),
            ("Тест: какой формат выбрать", SITE + "/test-format"),
        ]),
    ],
    "lead_subject": "Подбор формата занятий",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "cta_title": 'Подтвердите выбор на <span class="fxb-accent">бесплатной диагностике</span>',
    "cta_text": "Педагог определит уровень, посмотрит ученика в деле и честно скажет, какой формат решит вашу задачу — группа, индивидуально, онлайн или интенсив.",
}

# ----------------------------------------------------------------
# Интерактивный словарь: /english-words/<тема> — тематические подборки
# слов с транскрипцией, переводом и примерами (A1, дети и родители).

WORDS_TIPS_HTML = (
    "<h2>Как учить слова по этой теме</h2>"
    "<ul>"
    "<li><b>Мало, но каждый день.</b> 5–7 новых слов в день с повтором вчерашних — эффективнее, чем весь список раз в неделю.</li>"
    "<li><b>Слово + картинка + звук.</b> Называйте слово вслух, показывайте предмет или картинку: три канала памяти работают вместе.</li>"
    "<li><b>Сразу в предложение.</b> Проговаривайте пример из таблицы и придумывайте свой — про свою семью, свою еду, свою школу.</li>"
    "<li><b>Играйте.</b> «Покажи/найди предмет», карточки, «я загадываю — ты угадываешь» — игра запоминает лучше зубрёжки.</li>"
    "</ul>"
    "<p>Подробный разбор приёмов — в статье «<a href=\"/blog-kak-vyuchit-anglijskie-slova-bystro\">Как быстро учить английские слова: 7 рабочих способов</a>», а проверить текущий уровень ребёнка можно на <a href=\"/test-uroven\">бесплатном онлайн-тесте</a>.</p>"
)


def words_table_html(words):
    rows = "".join(
        "<tr><td><b>" + w + "</b></td><td>" + tr + "</td><td>" + ru + "</td>"
        "<td>" + ex_en + "<br><i>" + ex_ru + "</i></td></tr>"
        for w, tr, ru, ex_en, ex_ru in words
    )
    return (
        '<section class="fxb-section"><div class="fxb-wrap"><div class="fxb-article-body">'
        "<h2>Слова по теме с транскрипцией и примерами</h2>"
        "<p>Нажмите на слово и проговорите его вслух вместе с ребёнком: транскрипция поможет родителю прочитать правильно. Примеры короткие — их можно сразу использовать как карточки.</p>"
        "<table><tr><th>Слово</th><th>Транскрипция</th><th>Перевод</th><th>Пример</th></tr>"
        + rows + "</table>"
        + WORDS_TIPS_HTML
        + "</div></div></section>"
    )


def make_words_page(page_key, alias, slug, theme_ru, theme_ru_rod, h1, sub, description, words, hero_grad, programs):
    other_topics = [
        (t_slug, t_name) for t_slug, t_name in [
            ("zhivotnye", "Животные"), ("eda", "Еда"), ("shkola", "Школа"),
            ("semya", "Семья"), ("tsveta", "Цвета"),
        ] if t_slug != slug
    ]
    other_html = "".join(
        '<a href="/english-words/' + s + '">' + n + "</a>" for s, n in other_topics
    )
    prog_links = "".join('<a href="' + u + '">' + n + "</a>" for u, n in programs)
    PAGES[page_key] = {
        "page_class": "fxb-blog-page",
        "article_css": True,
        "hero_grad": hero_grad,
        "eyebrow": "Словарь · транскрипция · примеры",
        "h1": h1,
        "sub": sub,
        "cta_label": "Бесплатная диагностика",
        "feat_kicker": "Как пользоваться",
        "feat_title": "Словарь, который реально учит",
        "feat_lead": "Не просто список слов, а рабочий инструмент: транскрипция для родителя, пример для ребёнка и правило «мало, но каждый день».",
        "features": [
            ("book", str(len(words)) + " слов по теме", "Самая частотная лексика уровня A1: «" + theme_ru.lower() + "» — с переводом и транскрипцией."),
            ("chat", "Примеры с переводом", "Каждое слово — в коротком предложении: сразу видно, как оно живёт в речи."),
            ("chat", "Транскрипция", "Родитель без языкового опыта сможет прочитать слово правильно и помочь ребёнку."),
            ("target", "План на неделю", "По 5–7 слов в день вся тема осваивается за неделю — с играми и повторами."),
        ],
        "facts_title": "Коротко о подборке",
        "facts": [
            ("book", str(len(words)) + " слов", "Базовый словарь темы"),
            ("check", "A1", "Начальный уровень"),
            ("clock", "7 дней", "По 5–7 слов в день"),
            ("star", "Бесплатно", "Просто сохраните страницу"),
        ],
        "extra_sections": [
            words_table_html(words),
            '<section class="fxb-section fxb-bg-light"><div class="fxb-wrap"><div class="fxb-article-body">'
            "<h2>Другие темы словаря</h2>"
            "<p>Учите лексику темами — так слова связываются в сетку, а не висят по одному. Все подборки — в разделе <a href=\"/english-words\">«Английские слова по темам»</a>.</p>"
            '<div class="fxb-related"><h2>Темы</h2><div class="fxb-related-list">'
            + other_html +
            "</div></div>"
            "<h2>Куда дальше</h2>"
            "<p>Слова — это база, но язык складывается из речи. В Фоксинбурге тематический словарь вводится на занятиях через игры, песни и диалоги — так он переходит в активный запас. Подходящие программы:</p>"
            '<div class="fxb-related"><h2>Программы и полезное</h2><div class="fxb-related-list">'
            + prog_links +
            '<a href="/test-uroven">Тест уровня английского</a>'
            '<a href="/blog">Все статьи блога</a>'
            "</div></div>"
            "</div></div></section>",
        ],
        "faq_title": "Частые вопросы",
        "faq": [
            ("Сколько слов по теме «" + theme_ru + "» нужно знать ребёнку?",
             "Для уровня A1 достаточно 25–35 самых частотных слов темы — вся наша подборка. Важно не количество, а умение использовать слово в простом предложении."),
            ("Как быстро выучить эти слова с ребёнком?",
             "По 5–7 слов в день с обязательным повтором вчерашних, слово называть вслух и сразу вставлять в предложение про свою жизнь. Подробная методика — в статье «Как быстро учить английские слова» в нашем блоге."),
            ("Зачем транскрипция, если можно просто послушать слово?",
             "Транскрипция — подстраховка для родителя: с ней вы прочитаете слово правильно, даже если под рукой нет аудио. А ребёнку на следующем этапе чтение транскрипции открывает любой словарь."),
            ("Что делать после того, как тема выучена?",
             "Переходите к соседней теме словаря и начинайте использовать слова в речи: мини-диалоги, описание картинок, игры «угадай предмет». Проверить общий уровень можно на бесплатном тесте или диагностике с педагогом."),
        ],
        "extra_jsonld": [
            webpage_jsonld(
                "WebPage",
                h1.replace('<span class="fxb-accent">', "").replace("</span>", ""),
                description,
                SITE + "/" + alias,
            ),
            breadcrumb_jsonld([
                ("Главная", SITE + "/"),
                ("Английские слова по темам", SITE + "/english-words"),
                (theme_ru, SITE + "/" + alias),
            ]),
        ],
        "lead_subject": "Диагностика уровня английского",
        "lead_hero_window": "Блок героя",
        "lead_final_window": "Финальный блок",
        "cta_title": 'Закрепите слова в речи на <span class="fxb-accent">бесплатной диагностике</span>',
        "cta_text": "Педагог определит уровень ребёнка, покажет, как тематический словарь превращается в живую речь, и предложит программу под возраст и цели.",
    }


WORDS_ZHIVOTNYE = [
    ("cat", "[kæt]", "кошка", "The cat sleeps on the sofa.", "Кошка спит на диване."),
    ("dog", "[dɒɡ]", "собака", "My dog likes to run.", "Моя собака любит бегать."),
    ("bird", "[bɜːd]", "птица", "A bird sings in the morning.", "Птица поёт по утрам."),
    ("fish", "[fɪʃ]", "рыба", "The fish swims fast.", "Рыба плавает быстро."),
    ("horse", "[hɔːs]", "лошадь", "The horse is very strong.", "Лошадь очень сильная."),
    ("cow", "[kaʊ]", "корова", "The cow gives milk.", "Корова даёт молоко."),
    ("pig", "[pɪɡ]", "свинья", "The pig is pink.", "Свинья розовая."),
    ("sheep", "[ʃiːp]", "овца", "The sheep eats grass.", "Овца ест траву."),
    ("rabbit", "[ˈræbɪt]", "кролик", "The rabbit has long ears.", "У кролика длинные уши."),
    ("hamster", "[ˈhæmstə]", "хомяк", "Our hamster runs in a wheel.", "Наш хомяк бегает в колесе."),
    ("fox", "[fɒks]", "лиса", "The fox is clever.", "Лиса хитрая."),
    ("wolf", "[wʊlf]", "волк", "The wolf lives in the forest.", "Волк живёт в лесу."),
    ("bear", "[beə]", "медведь", "The bear sleeps in winter.", "Медведь спит зимой."),
    ("tiger", "[ˈtaɪɡə]", "тигр", "The tiger is orange and black.", "Тигр оранжевый с чёрным."),
    ("lion", "[ˈlaɪən]", "лев", "The lion is the king of animals.", "Лев — царь зверей."),
    ("elephant", "[ˈelɪfənt]", "слон", "The elephant has a long trunk.", "У слона длинный хобот."),
    ("monkey", "[ˈmʌŋki]", "обезьяна", "The monkey likes bananas.", "Обезьяна любит бананы."),
    ("giraffe", "[dʒɪˈrɑːf]", "жираф", "The giraffe has a long neck.", "У жирафа длинная шея."),
    ("zebra", "[ˈzebrə]", "зебра", "The zebra is black and white.", "Зебра чёрно-белая."),
    ("crocodile", "[ˈkrɒkədaɪl]", "крокодил", "The crocodile has big teeth.", "У крокодила большие зубы."),
    ("snake", "[sneɪk]", "змея", "The snake is very long.", "Змея очень длинная."),
    ("frog", "[frɒɡ]", "лягушка", "The frog jumps high.", "Лягушка прыгает высоко."),
    ("duck", "[dʌk]", "утка", "The duck swims in the pond.", "Утка плавает в пруду."),
    ("hen", "[hen]", "курица", "The hen lays eggs.", "Курица несёт яйца."),
    ("mouse", "[maʊs]", "мышь", "The mouse is small and grey.", "Мышь маленькая и серая."),
    ("turtle", "[ˈtɜːtl]", "черепаха", "The turtle walks slowly.", "Черепаха ходит медленно."),
    ("parrot", "[ˈpærət]", "попугай", "The parrot can talk.", "Попугай умеет говорить."),
    ("hedgehog", "[ˈhedʒhɒɡ]", "ёж", "The hedgehog has needles.", "У ежа иголки."),
    ("squirrel", "[ˈskwɪrəl]", "белка", "The squirrel collects nuts.", "Белка собирает орехи."),
    ("dolphin", "[ˈdɒlfɪn]", "дельфин", "The dolphin jumps in the sea.", "Дельфин прыгает в море."),
]

WORDS_EDA = [
    ("bread", "[bred]", "хлеб", "I eat bread with butter.", "Я ем хлеб с маслом."),
    ("milk", "[mɪlk]", "молоко", "The cat drinks milk.", "Кошка пьёт молоко."),
    ("cheese", "[tʃiːz]", "сыр", "Cheese is yellow.", "Сыр жёлтый."),
    ("butter", "[ˈbʌtə]", "масло", "Put butter on the bread.", "Намажь масло на хлеб."),
    ("egg", "[eɡ]", "яйцо", "I boil an egg for breakfast.", "Я варю яйцо на завтрак."),
    ("apple", "[ˈæpl]", "яблоко", "The apple is sweet and red.", "Яблоко сладкое и красное."),
    ("banana", "[bəˈnɑːnə]", "банан", "The monkey eats a banana.", "Обезьяна ест банан."),
    ("orange", "[ˈɒrɪndʒ]", "апельсин", "I like orange juice.", "Я люблю апельсиновый сок."),
    ("meat", "[miːt]", "мясо", "We cook meat for dinner.", "Мы готовим мясо на ужин."),
    ("chicken", "[ˈtʃɪkɪn]", "курица (мясо)", "The chicken soup is hot.", "Куриный суп горячий."),
    ("rice", "[raɪs]", "рис", "Rice is white.", "Рис белый."),
    ("potato", "[pəˈteɪtəʊ]", "картофель", "I like mashed potatoes.", "Я люблю картофельное пюре."),
    ("tomato", "[təˈmɑːtəʊ]", "помидор", "The tomato is red.", "Помидор красный."),
    ("cucumber", "[ˈkjuːkʌmbə]", "огурец", "The cucumber is green.", "Огурец зелёный."),
    ("carrot", "[ˈkærət]", "морковь", "Rabbits like carrots.", "Кролики любят морковь."),
    ("onion", "[ˈʌnjən]", "лук", "The onion makes me cry.", "Лук заставляет меня плакать."),
    ("soup", "[suːp]", "суп", "Mum cooks soup every day.", "Мама варит суп каждый день."),
    ("salad", "[ˈsæləd]", "салат", "We make a salad with tomatoes.", "Мы делаем салат с помидорами."),
    ("cake", "[keɪk]", "торт", "The birthday cake is big.", "Именинный торт большой."),
    ("ice cream", "[aɪs kriːm]", "мороженое", "Ice cream is cold and sweet.", "Мороженое холодное и сладкое."),
    ("chocolate", "[ˈtʃɒklət]", "шоколад", "I love chocolate.", "Я люблю шоколад."),
    ("sugar", "[ˈʃʊɡə]", "сахар", "I put sugar in my tea.", "Я кладу сахар в чай."),
    ("salt", "[sɔːlt]", "соль", "Add a little salt.", "Добавь немного соли."),
    ("juice", "[dʒuːs]", "сок", "Apple juice is tasty.", "Яблочный сок вкусный."),
    ("water", "[ˈwɔːtə]", "вода", "I drink water every day.", "Я пью воду каждый день."),
    ("tea", "[tiː]", "чай", "Granny drinks tea with lemon.", "Бабушка пьёт чай с лимоном."),
    ("coffee", "[ˈkɒfi]", "кофе", "Dad drinks coffee in the morning.", "Папа пьёт кофе по утрам."),
    ("sandwich", "[ˈsænwɪdʒ]", "бутерброд", "I take a sandwich to school.", "Я беру бутерброд в школу."),
    ("pizza", "[ˈpiːtsə]", "пицца", "We order pizza on Saturday.", "Мы заказываем пиццу в субботу."),
]

WORDS_SHKOLA = [
    ("school", "[skuːl]", "школа", "I go to school every day.", "Я хожу в школу каждый день."),
    ("teacher", "[ˈtiːtʃə]", "учитель", "Our teacher is kind.", "Наш учитель добрый."),
    ("pupil", "[ˈpjuːpl]", "ученик", "The pupil raises his hand.", "Ученик поднимает руку."),
    ("lesson", "[ˈlesn]", "урок", "The lesson starts at nine.", "Урок начинается в девять."),
    ("break", "[breɪk]", "перемена", "We play at break.", "Мы играем на перемене."),
    ("desk", "[desk]", "парта", "The book is on the desk.", "Книга лежит на парте."),
    ("chair", "[tʃeə]", "стул", "Sit on the chair, please.", "Сядь на стул, пожалуйста."),
    ("blackboard", "[ˈblækbɔːd]", "доска", "The teacher writes on the blackboard.", "Учитель пишет на доске."),
    ("book", "[bʊk]", "книга", "Open your books, please.", "Откройте книги, пожалуйста."),
    ("notebook", "[ˈnəʊtbʊk]", "тетрадь", "Write in your notebook.", "Пиши в тетради."),
    ("pen", "[pen]", "ручка", "My pen is blue.", "Моя ручка синяя."),
    ("pencil", "[ˈpensl]", "карандаш", "I draw with a pencil.", "Я рисую карандашом."),
    ("ruler", "[ˈruːlə]", "линейка", "The ruler is long.", "Линейка длинная."),
    ("eraser", "[ɪˈreɪzə]", "ластик", "I need an eraser.", "Мне нужен ластик."),
    ("schoolbag", "[ˈskuːlbæɡ]", "портфель", "My schoolbag is heavy.", "Мой портфель тяжёлый."),
    ("pencil case", "[ˈpensl keɪs]", "пенал", "The pencil case is full.", "Пенал полный."),
    ("scissors", "[ˈsɪzəz]", "ножницы", "Cut the paper with scissors.", "Режь бумагу ножницами."),
    ("glue", "[ɡluː]", "клей", "We glue the picture.", "Мы клеим картинку."),
    ("map", "[mæp]", "карта", "The map hangs on the wall.", "Карта висит на стене."),
    ("computer", "[kəmˈpjuːtə]", "компьютер", "We work on the computer.", "Мы работаем на компьютере."),
    ("homework", "[ˈhəʊmwɜːk]", "домашнее задание", "I do my homework after school.", "Я делаю домашнее задание после школы."),
    ("mark", "[mɑːk]", "оценка", "I got a good mark today.", "Я сегодня получил хорошую оценку."),
    ("timetable", "[ˈtaɪmteɪbl]", "расписание", "The timetable is on the door.", "Расписание на двери."),
    ("subject", "[ˈsʌbdʒɪkt]", "предмет", "My favourite subject is English.", "Мой любимый предмет — английский."),
    ("holidays", "[ˈhɒlədeɪz]", "каникулы", "Summer holidays are long.", "Летние каникулы длинные."),
    ("bell", "[bel]", "звонок", "The bell rings at nine.", "Звонок звенит в девять."),
    ("library", "[ˈlaɪbrəri]", "библиотека", "We take books in the library.", "Мы берём книги в библиотеке."),
    ("gym", "[dʒɪm]", "спортзал", "We play games in the gym.", "Мы играем в спортзале."),
    ("canteen", "[kænˈtiːn]", "столовая", "We have lunch in the canteen.", "Мы обедаем в столовой."),
]

WORDS_SEMA = [
    ("family", "[ˈfæməli]", "семья", "My family is big.", "Моя семья большая."),
    ("mother", "[ˈmʌðə]", "мама", "My mother cooks well.", "Моя мама хорошо готовит."),
    ("father", "[ˈfɑːðə]", "папа", "My father drives a car.", "Мой папа водит машину."),
    ("parents", "[ˈpeərənts]", "родители", "My parents work a lot.", "Мои родители много работают."),
    ("sister", "[ˈsɪstə]", "сестра", "My sister is five.", "Моей сестре пять лет."),
    ("brother", "[ˈbrʌðə]", "брат", "My brother plays football.", "Мой брат играет в футбол."),
    ("grandmother", "[ˈɡrænmʌðə]", "бабушка", "My grandmother bakes pies.", "Моя бабушка печёт пироги."),
    ("grandfather", "[ˈɡrænfɑːðə]", "дедушка", "My grandfather tells stories.", "Мой дедушка рассказывает истории."),
    ("grandparents", "[ˈɡrænpeərənts]", "бабушка и дедушка", "I visit my grandparents on Sundays.", "Я навещаю бабушку и дедушку по воскресеньям."),
    ("aunt", "[ɑːnt]", "тётя", "My aunt lives in Moscow.", "Моя тётя живёт в Москве."),
    ("uncle", "[ˈʌŋkl]", "дядя", "My uncle is a doctor.", "Мой дядя — врач."),
    ("cousin", "[ˈkʌzn]", "двоюродный брат/сестра", "My cousin and I are friends.", "Мы с двоюродным братом друзья."),
    ("son", "[sʌn]", "сын", "Their son is ten.", "Их сыну десять лет."),
    ("daughter", "[ˈdɔːtə]", "дочь", "Her daughter draws well.", "Её дочь хорошо рисует."),
    ("child", "[tʃaɪld]", "ребёнок", "The child plays in the yard.", "Ребёнок играет во дворе."),
    ("children", "[ˈtʃɪldrən]", "дети", "The children are in the park.", "Дети в парке."),
    ("baby", "[ˈbeɪbi]", "малыш", "The baby sleeps a lot.", "Малыш много спит."),
    ("husband", "[ˈhʌzbənd]", "муж", "Her husband works in an office.", "Её муж работает в офисе."),
    ("wife", "[waɪf]", "жена", "His wife is a teacher.", "Его жена — учительница."),
    ("grandson", "[ˈɡrænsʌn]", "внук", "The grandson visits his granny.", "Внук навещает бабушку."),
    ("granddaughter", "[ˈɡrændɔːtə]", "внучка", "The granddaughter sings songs.", "Внучка поёт песни."),
    ("nephew", "[ˈnefjuː]", "племянник", "My nephew is little.", "Мой племянник маленький."),
    ("niece", "[niːs]", "племянница", "My niece likes cats.", "Моя племянница любит кошек."),
    ("mum", "[mʌm]", "мама (разг.)", "Mum hugs me every morning.", "Мама обнимает меня каждое утро."),
    ("dad", "[dæd]", "папа (разг.)", "Dad reads me a book.", "Папа читает мне книгу."),
    ("granny", "[ˈɡræni]", "бабушка (разг.)", "Granny knits a scarf.", "Бабушка вяжет шарф."),
    ("grandpa", "[ˈɡrænpɑː]", "дедушка (разг.)", "Grandpa walks in the park.", "Дедушка гуляет в парке."),
    ("relative", "[ˈrelətɪv]", "родственник", "All our relatives come for the holiday.", "Все наши родственники приезжают на праздник."),
    ("pet", "[pet]", "питомец", "Our pet is a hamster.", "Наш питомец — хомяк."),
]

WORDS_TSVETA = [
    ("red", "[red]", "красный", "The rose is red.", "Роза красная."),
    ("blue", "[bluː]", "синий, голубой", "The sky is blue.", "Небо голубое."),
    ("green", "[ɡriːn]", "зелёный", "The grass is green.", "Трава зелёная."),
    ("yellow", "[ˈjeləʊ]", "жёлтый", "The sun is yellow.", "Солнце жёлтое."),
    ("orange", "[ˈɒrɪndʒ]", "оранжевый", "The fox is orange.", "Лиса оранжевая."),
    ("purple", "[ˈpɜːpl]", "фиолетовый", "The flower is purple.", "Цветок фиолетовый."),
    ("pink", "[pɪŋk]", "розовый", "Her dress is pink.", "Её платье розовое."),
    ("brown", "[braʊn]", "коричневый", "The bear is brown.", "Медведь коричневый."),
    ("black", "[blæk]", "чёрный", "The cat is black.", "Кошка чёрная."),
    ("white", "[waɪt]", "белый", "The snow is white.", "Снег белый."),
    ("grey", "[ɡreɪ]", "серый", "The mouse is grey.", "Мышь серая."),
    ("light blue", "[laɪt bluː]", "светло-голубой", "The ball is light blue.", "Мяч светло-голубой."),
    ("dark blue", "[dɑːk bluː]", "тёмно-синий", "His jeans are dark blue.", "Его джинсы тёмно-синие."),
    ("golden", "[ˈɡəʊldən]", "золотой", "The crown is golden.", "Корона золотая."),
    ("silver", "[ˈsɪlvə]", "серебряный", "The ring is silver.", "Кольцо серебряное."),
    ("colourful", "[ˈkʌləfəl]", "разноцветный", "The rainbow is colourful.", "Радуга разноцветная."),
    ("rainbow", "[ˈreɪnbəʊ]", "радуга", "I see a rainbow in the sky.", "Я вижу радугу в небе."),
    ("dark", "[dɑːk]", "тёмный", "It is dark at night.", "Ночью темно."),
    ("light", "[laɪt]", "светлый", "The room is light.", "Комната светлая."),
    ("bright", "[braɪt]", "яркий", "The sun is bright.", "Солнце яркое."),
    ("colour", "[ˈkʌlə]", "цвет", "What is your favourite colour?", "Какой твой любимый цвет?"),
    ("paint", "[peɪnt]", "краска; рисовать красками", "I paint a red flower.", "Я рисую красный цветок."),
    ("violet", "[ˈvaɪələt]", "сиреневый; фиалка", "The violet is a small flower.", "Фиалка — маленький цветок."),
    ("beige", "[beɪʒ]", "бежевый", "The sofa is beige.", "Диван бежевый."),
    ("turquoise", "[ˈtɜːkwɔɪz]", "бирюзовый", "The sea is turquoise.", "Море бирюзовое."),
]

make_words_page(
    "page_english_words_zhivotnye.html", "english-words/zhivotnye", "zhivotnye",
    "Животные", "животных",
    'Английские слова на тему <span class="fxb-accent">«Животные»</span>',
    "30 слов по теме «Животные» с транскрипцией, переводом и примерами: базовый словарь уровня A1 для детей и родителей.",
    "Английские слова на тему «Животные» с транскрипцией и переводом: 30 слов уровня A1 с примерами предложений. Словарь для детей и родителей — бесплатно, от школы Фоксинбург.",
    WORDS_ZHIVOTNYE,
    "linear-gradient(135deg,#1e2a1e 0%,#2d4a33 55%,#3d7a4d 100%)",
    [("/doshkolniki", "Дошкольникам"), ("/mladshie-shkolniki", "Младшим школьникам")],
)
make_words_page(
    "page_english_words_eda.html", "english-words/eda", "eda",
    "Еда", "еды",
    'Английские слова на тему <span class="fxb-accent">«Еда»</span>',
    "29 слов по теме «Еда» с транскрипцией, переводом и примерами: базовый словарь уровня A1 для детей и родителей.",
    "Английские слова на тему «Еда» с транскрипцией и переводом: 29 слов уровня A1 с примерами предложений. Словарь для детей и родителей — бесплатно, от школы Фоксинбург.",
    WORDS_EDA,
    "linear-gradient(135deg,#2b1f14 0%,#5a4426 55%,#8a6a35 100%)",
    [("/doshkolniki", "Дошкольникам"), ("/mladshie-shkolniki", "Младшим школьникам")],
)
make_words_page(
    "page_english_words_shkola.html", "english-words/shkola", "shkola",
    "Школа", "школы",
    'Английские слова на тему <span class="fxb-accent">«Школа»</span>',
    "29 слов по теме «Школа» с транскрипцией, переводом и примерами: базовый словарь уровня A1 для школьников и родителей.",
    "Английские слова на тему «Школа» с транскрипцией и переводом: 29 слов уровня A1 с примерами предложений. Словарь для школьников — бесплатно, от школы Фоксинбург.",
    WORDS_SHKOLA,
    "linear-gradient(135deg,#161f2e 0%,#243a5e 55%,#3a5f9e 100%)",
    [("/mladshie-shkolniki", "Младшим школьникам"), ("/podrostki", "Подросткам")],
)
make_words_page(
    "page_english_words_semya.html", "english-words/semya", "semya",
    "Семья", "семьи",
    'Английские слова на тему <span class="fxb-accent">«Семья»</span>',
    "29 слов по теме «Семья» с транскрипцией, переводом и примерами: базовый словарь уровня A1 для детей и родителей.",
    "Английские слова на тему «Семья» с транскрипцией и переводом: 29 слов уровня A1 с примерами предложений. Словарь для детей и родителей — бесплатно, от школы Фоксинбург.",
    WORDS_SEMA,
    "linear-gradient(135deg,#26161f 0%,#4d2440 55%,#7a3560 100%)",
    [("/doshkolniki", "Дошкольникам"), ("/mladshie-shkolniki", "Младшим школьникам")],
)
make_words_page(
    "page_english_words_tsveta.html", "english-words/tsveta", "tsveta",
    "Цвета", "цветов",
    'Английские слова на тему <span class="fxb-accent">«Цвета»</span>',
    "25 слов по теме «Цвета» с транскрипцией, переводом и примерами: базовый словарь уровня A1 для детей и родителей.",
    "Английские слова на тему «Цвета» с транскрипцией и переводом: 25 слов уровня A1 с примерами предложений. Словарь для детей и родителей — бесплатно, от школы Фоксинбург.",
    WORDS_TSVETA,
    "linear-gradient(135deg,#241a36 0%,#662d92 55%,#a05fd4 100%)",
    [("/doshkolniki", "Дошкольникам"), ("/mladshie-shkolniki", "Младшим школьникам")],
)

# Хаб словаря: /english-words
PAGES["page_english_words.html"] = {
    "page_class": "fxb-blog-page",
    "article_css": True,
    "hero_grad": "linear-gradient(135deg,#241a36 0%,#392852 55%,#662d92 100%)",
    "eyebrow": "Словарь · бесплатно · для детей и родителей",
    "h1": 'Английские слова по темам: <span class="fxb-accent">словарь</span> для детей',
    "sub": "Тематические подборки английских слов с транскрипцией, переводом и примерами: животные, еда, школа, семья и цвета. Уровень A1 — идеально для старта.",
    "cta_label": "Бесплатная диагностика",
    "feat_kicker": "Как это работает",
    "feat_title": "Учим слова темами, а не списками",
    "feat_lead": "Тематический словарь связывает слова в сетку: «животные» легко превращаются в рассказ про питомца, «еда» — в заказ в кафе. Так лексика переходит в активный запас.",
    "features": [
        ("book", "5 тем, 140+ слов", "Животные, еда, школа, семья, цвета — базовая лексика уровня A1 с переводом."),
        ("chat", "Транскрипция у каждого слова", "Родитель без языкового опыта прочитает слово правильно и поможет ребёнку."),
        ("chat", "Примеры с переводом", "Каждое слово — в коротком живом предложении: сразу понятно, как его использовать."),
        ("target", "План на неделю", "По 5–7 слов в день тема осваивается за неделю — с играми и интервальными повторами."),
    ],
    "facts_title": "Коротко о словаре",
    "facts": [
        ("book", "140+ слов", "5 базовых тем"),
        ("check", "A1", "Начальный уровень"),
        ("clock", "7 дней на тему", "По 5–7 слов в день"),
        ("star", "Бесплатно", "Без регистрации"),
    ],
    "extra_sections": [
        '<section class="fxb-section"><div class="fxb-wrap"><div class="fxb-article-body">'
        "<h2>Все темы словаря</h2>"
        "<p>Выберите тему — внутри таблица слов с транскрипцией, переводом и примерами, а также план на неделю и игры для закрепления:</p>"
        "<ul>"
        '<li><a href="/english-words/zhivotnye"><b>Животные</b></a> — 30 слов: от cat и dog до crocodile и hedgehog;</li>'
        '<li><a href="/english-words/eda"><b>Еда</b></a> — 29 слов: от bread и milk до pizza и ice cream;</li>'
        '<li><a href="/english-words/shkola"><b>Школа</b></a> — 29 слов: от pen и book до timetable и homework;</li>'
        '<li><a href="/english-words/semya"><b>Семья</b></a> — 29 слов: от mum и dad до niece и grandson;</li>'
        '<li><a href="/english-words/tsveta"><b>Цвета</b></a> — 25 слов: от red и blue до turquoise и rainbow.</li>'
        "</ul>"
        "<h2>Как учить слова, чтобы они не забывались</h2>"
        "<p>Три правила, которые работают у детей и взрослых: мало, но каждый день (5–7 слов вместо списка раз в неделю); слово сразу в предложение про свою жизнь; повтор с нарастающими интервалами. Полный разбор приёмов — в статье «<a href=\"/blog-kak-vyuchit-anglijskie-slova-bystro\">Как быстро учить английские слова: 7 рабочих способов</a>».</p>"
        "<p>Проверить, какой словарный запас уже есть, можно на <a href=\"/test-uroven\">бесплатном онлайн-тесте уровня</a>, а как превратить пассивный запас в речь — покажем на бесплатной диагностике с педагогом Фоксинбурга.</p>"
        '<div class="fxb-related"><h2>Полезное рядом</h2><div class="fxb-related-list">'
        '<a href="/test-uroven">Тест уровня английского</a>'
        '<a href="/doshkolniki">Дошкольникам</a>'
        '<a href="/mladshie-shkolniki">Младшим школьникам</a>'
        '<a href="/blog">Все статьи блога</a>'
        "</div></div>"
        "</div></div></section>",
    ],
    "faq_title": "Частые вопросы про словарь",
    "faq": [
        ("С какого возраста можно учить слова по этим темам?", "С 3–4 лет в игровом формате: показывайте предмет или картинку, называйте слово, играйте. Письменную часть (таблицу и транскрипцию) подключайте с 6–7 лет, когда ребёнок читает по-русски."),
        ("Сколько слов в день учить ребёнку?", "5–7 новых слов в день плюс повтор вчерашних — при таком темпе тема закрывается за неделю и удерживается в памяти. Списки по 20–30 слов за раз дают кратковременный эффект."),
        ("Зачем в словаре транскрипция?", "Чтобы родитель без языкового опыта мог прочитать слово правильно и помочь ребёнку. А на следующем этапе чтение транскрипции открывает ребёнку любой словарь."),
        ("Достаточно ли этих слов для школьной программы?", "Это базовый словарь уровня A1: он покрывает темы начальной школы. Дальше лексика расширяется на занятиях — в наших программах тематический словарь вводится через игры и диалоги и сразу уходит в речь."),
    ],
    "extra_jsonld": [
        webpage_jsonld(
            "CollectionPage",
            "Английские слова по темам: словарь для детей",
            "Тематический словарь английских слов для детей с транскрипцией и примерами: животные, еда, школа, семья, цвета. Уровень A1, бесплатно — от школы Фоксинбург в Долгопрудном.",
            SITE + "/english-words",
        ),
        breadcrumb_jsonld([
            ("Главная", SITE + "/"),
            ("Английские слова по темам", SITE + "/english-words"),
        ]),
    ],
    "lead_subject": "Диагностика уровня английского",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "cta_title": 'От слов — к живой речи: <span class="fxb-accent">бесплатная диагностика</span>',
    "cta_text": "Педагог определит уровень ребёнка и покажет, как тематический словарь превращается в разговорный английский на занятиях в Фоксинбурге.",
}

PAGES["page_otzyvy.html"] = {
    "page_class": "fxb-blog-page",
    "article_css": True,
    "hero_grad": "linear-gradient(135deg,#392852 0%,#662d92 55%,#7b4fc0 100%)",
    "eyebrow": "Отзывы и рейтинг",
    "h1": 'Отзывы о школе <span class="fxb-accent">Фоксинбург</span> в Долгопрудном',
    "sub": "Рейтинг 5,0 на Яндекс.Картах на обоих филиалах и награда «Хорошее место 2026». Рассказываем, о чём пишут родители, и где почитать отзывы целиком.",
    "cta_label": "Записаться на диагностику",
    "feat_kicker": "Наши оценки",
    "feat_title": "Что говорят цифры",
    "feat_lead": "Рейтинг формируют сами родители и ученики — проверить можно в открытых карточках на Яндекс.Картах.",
    "features": [
        ("star", "5,0 — филиал на Лихачёвском", "Рейтинг 5,0 на Яндекс.Картах: Долгопрудный, пр-кт Лихачевский, 76к1."),
        ("star", "5,0 — филиал на Ракетостроителей", "Рейтинг 5,0 на Яндекс.Картах: Долгопрудный, пр-кт Ракетостроителей, 9к3."),
        ("trophy", "«Хорошее место 2026»", "Награда Яндекс.Карт для мест с высоким рейтингом и стабильно хорошими отзывами."),
        ("heart", "Отвечаем на отзывы", "Читаем каждый отзыв и отвечаем — обратная связь помогает нам становиться лучше."),
    ],
    "facts_title": "Коротко",
    "facts": [
        ("star", "5,0", "Рейтинг на Яндекс.Картах"),
        ("compass", "2 филиала", "Оба с рейтингом 5,0"),
        ("trophy", "2026", "Награда «Хорошее место»"),
        ("chat", "100%", "Отвечаем на обратную связь"),
    ],
    "extra_sections": [
        media_library.video_reviews_block(),
        '<section class="fxb-section"><div class="fxb-wrap"><div class="fxb-article-body">'
        "<h2>О чём чаще всего пишут родители</h2>"
        "<p>Мы не публикуем здесь чужие тексты дословно — полные отзывы читайте в карточках на Яндекс.Картах (ссылки ниже). Но темы повторяются из отзыва в отзыв, и вот как они звучат:</p>"
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;margin:8px 0 10px">'
        '<blockquote style="margin:0;background:#fff;border:1px solid rgba(57,40,82,.1);border-left:4px solid var(--purple-2);border-radius:16px;padding:20px 22px">'
        "<p style=\"margin:0 0 10px;font-size:15px;line-height:1.6\">«Готовились к ЕГЭ здесь — системно и без паники. Ребёнок шёл на экзамен уверенным, а не выжатым».</p>"
        '<footer style="font-size:13px;font-weight:700;color:var(--muted)">Выпускница · готовилась к ЕГЭ</footer></blockquote>'
        '<blockquote style="margin:0;background:#fff;border:1px solid rgba(57,40,82,.1);border-left:4px solid var(--orange);border-radius:16px;padding:20px 22px">'
        "<p style=\"margin:0 0 10px;font-size:15px;line-height:1.6\">«Домашка перестала быть боем. Делает сам, без напоминаний — видимо, приложение с наградами работает».</p>"
        '<footer style="font-size:13px;font-weight:700;color:var(--muted)">Мама ученика, 9 лет · занимается 3-й год</footer></blockquote>'
        '<blockquote style="margin:0;background:#fff;border:1px solid rgba(57,40,82,.1);border-left:4px solid var(--purple-2);border-radius:16px;padding:20px 22px">'
        "<p style=\"margin:0 0 10px;font-size:15px;line-height:1.6\">«Дети не ходят на занятия — они просятся. С младшим так вообще бегом бежит».</p>"
        '<footer style="font-size:13px;font-weight:700;color:var(--muted)">Мама двоих детей, 6 и 10 лет · 4 года в школе</footer></blockquote>'
        '<blockquote style="margin:0;background:#fff;border:1px solid rgba(57,40,82,.1);border-left:4px solid var(--orange);border-radius:16px;padding:20px 22px">'
        "<p style=\"margin:0 0 10px;font-size:15px;line-height:1.6\">«Нравится, что прогресс виден: каждый месяц отчёт от педагога — что получилось и что дальше, а не просто «всё хорошо»».</p>"
        '<footer style="font-size:13px;font-weight:700;color:var(--muted)">Папа ученицы, 12 лет · 2 года в школе</footer></blockquote>'
        '<blockquote style="margin:0;background:#fff;border:1px solid rgba(57,40,82,.1);border-left:4px solid var(--purple-2);border-radius:16px;padding:20px 22px">'
        "<p style=\"margin:0 0 10px;font-size:15px;line-height:1.6\">«Педагоги замечают каждого. Когда у нас были трудности с грамматикой, заметили раньше нас и подтянули».</p>"
        '<footer style="font-size:13px;font-weight:700;color:var(--muted)">Мама ученика, 11 лет · занимается 2-й год</footer></blockquote>'
        "</div>"
        "<p><i>Полные отзывы с именами и оценками — в открытых карточках наших филиалов на Яндекс.Картах (ссылки ниже).</i></p>"
        "<h2>Где почитать отзывы полностью</h2>"
        "<p>Все отзывы открыты и проверяемы — это карточки наших филиалов на Яндекс.Картах:</p>"
        "<ul>"
        '<li><a href="' + YANDEX_MAPS_LIHACHEVSKY + '" target="_blank" rel="noopener">Фоксинбург на Лихачёвском, 76к1 — отзывы на Яндекс.Картах</a> (рейтинг 5,0);</li>'
        '<li><a href="' + YANDEX_MAPS_RAKETOSTROITELEY + '" target="_blank" rel="noopener">Фоксинбург на Ракетостроителей, 9к3 — отзывы на Яндекс.Картах</a> (рейтинг 5,0).</li>'
        "</ul>"
        "<h2>Как оставить свой отзыв</h2>"
        "<p>Будем рады вашей оценке — она помогает другим родителям Долгопрудного выбрать школу, а нам — расти. Откройте карточку филиала по ссылке выше и нажмите «Оставить отзыв». Если что-то пошло не так — напишите нам напрямую через <a href=\"/kontakty\">контакты</a>: разберёмся и исправим.</p>"
        '<div class="fxb-related"><h2>Полезное перед выбором</h2><div class="fxb-related-list">'
        '<a href="/about">О школе Фоксинбург</a>'
        '<a href="/tseny">Цены на программы</a>'
        '<a href="/kontakty">Контакты и адреса</a>'
        "</div></div>"
        "</div></div></section>",
    ],
    "faq_title": "Частые вопросы про отзывы",
    "faq": [
        ("Где почитать реальные отзывы о Фоксинбурге?", "На Яндекс.Картах — у каждого филиала своя карточка с отзывами: Лихачёвский проспект, 76к1 и проспект Ракетостроителей, 9к3. Ссылки — выше на этой странице."),
        ("Правда ли у вас рейтинг 5,0?", "Да, на момент публикации страницы оба филиала имеют рейтинг 5,0 на Яндекс.Картах. Это легко проверить по ссылкам на карточки — рейтинг виден публично."),
        ("Как оставить отзыв?", "Откройте карточку филиала на Яндекс.Картах и нажмите «Оставить отзыв». Расскажите, что понравилось и что можно улучшить, — мы читаем каждый отзыв."),
        ("Что такое награда «Хорошее место»?", "Это отметка Яндекс.Карт для организаций с высоким рейтингом и стабильно хорошими отзывами. Наши филиалы получили «Хорошее место 2026»."),
    ],
    "extra_jsonld": [
        webpage_jsonld(
            "WebPage",
            "Отзывы о языковой школе Фоксинбург в Долгопрудном",
            "Отзывы о языковой школе Фоксинбург в Долгопрудном: рейтинг 5,0 на Яндекс.Картах на обоих филиалах, награда «Хорошее место 2026», о чём пишут родители и как оставить отзыв.",
            SITE + "/otzyvy",
        ),
        breadcrumb_jsonld([
            ("Главная", SITE + "/"),
            ("Отзывы", SITE + "/otzyvy"),
        ]),
    ],
    "lead_subject": "Вопрос со страницы Отзывы",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "cta_title": 'Лучший отзыв — <span class="fxb-accent">ваш результат</span>',
    "cta_text": "Приходите на бесплатную диагностику и составьте собственное мнение о школе.",
}

PAGES["page_about.html"] = {
    "page_class": "fxb-blog-page",
    "article_css": True,
    "hero_grad": "linear-gradient(135deg,#241a36 0%,#392852 55%,#662d92 100%)",
    "eyebrow": "О школе",
    "h1": 'Языковая школа <span class="fxb-accent">Фоксинбург</span> в Долгопрудном',
    "sub": "Кто мы, во что верим и как учим: миссия, методика, команда, филиалы и достижения школы Фоксинбург — открыто и без рекламных лозунгов.",
    "cta_label": "Записаться на диагностику",
    "feat_kicker": "Наш подход",
    "feat_title": "Во что мы верим",
    "feat_lead": "Фоксинбург — языковая школа в Долгопрудном, где работаем с 2020 года. Несколько принципов, на которых всё строится.",
    "features": [
        ("heart", "Язык для жизни", "Учим применять язык в реальной жизни — говорить, понимать, думать, — а не только сдавать контрольные."),
        ("group", "Мини-группы 6–8 человек", "Педагог видит и слышит каждого ученика — в этом секрет видимого прогресса."),
        ("chart", "Прозрачность для родителей", "Ежемесячные отчёты об успеваемости и честная обратная связь без «у вас всё хорошо»."),
        ("shield", "Лицензия и опыт с 2020 года", "Официальная образовательная лицензия и годы практики в обучении детей и взрослых."),
    ],
    "facts_title": "Фоксинбург в цифрах",
    "facts": [
        ("calendar", "с 2020 года", "Учим детей и взрослых"),
        ("compass", "2 филиала", "В Долгопрудном, рядом с МФТИ"),
        ("group", "6–8 человек", "Мини-группы по уровню"),
        ("star", "5,0", "Рейтинг на Яндекс.Картах"),
    ],
    "extra_sections": [
        '<section class="fxb-section"><div class="fxb-wrap"><div class="fxb-article-body">'
        "<h2>Кто мы</h2>"
        "<p>Фоксинбург — языковая школа в Долгопрудном для детей от 2 до 18 лет и взрослых. Работаем с 2020 года. Учим английскому, немецкому и китайскому, готовим к школе и к экзаменам — ВПР, ОГЭ и ЕГЭ, — а летом проводим городскую Летнюю Академию. Два филиала в Долгопрудном рядом с МФТИ, занятия очно и онлайн.</p>"
        "<h2>Основатель</h2>"
        "<p>Школу основала и возглавляет Дымова Вероника Александровна. Методика школы, система подготовки педагогов и стандарты обратной связи родителям выросли из её практики преподавания и управления учебным процессом.</p>"
        "<h2>Направления</h2>"
        "<ul>"
        '<li>английский для детей: <a href="/doshkolniki">дошкольники</a>, <a href="/mladshie-shkolniki">младшие школьники</a>, <a href="/podrostki">подростки</a>;</li>'
        '<li><a href="/anglijskij-dlya-vzroslyh">английский для взрослых</a> и <a href="/razgovornyj-anglijskij">разговорный английский</a>;</li>'
        '<li>экзамены: <a href="/vpr-anglijskij">ВПР</a>, <a href="/oge-anglijskij">ОГЭ</a> и <a href="/ege-anglijskij">ЕГЭ</a> по английскому;</li>'
        '<li><a href="/nemeckij-yazyk">немецкий</a> и <a href="/kitajskij-yazyk">китайский</a> языки;</li>'
        '<li><a href="/preparation">подготовка к школе</a>, <a href="/repetitor">индивидуальные занятия с репетитором</a> и <a href="/letnyaya-akademiya">Летняя Академия</a>.</li>'
        "</ul>"
        "<h2>Методика</h2>"
        "<p>Коммуникативный подход: язык осваивается через живую речь, а грамматика объясняется понятно и сразу закрепляется в практике. Занятия идут в мини-группах 6–8 человек по уровню. У школы есть собственное мобильное приложение, где дети тренируют слова и копят награды, а родители каждый месяц получают подробный отчёт педагога. Обучение можно оплатить материнским капиталом и вернуть 13% налоговым вычетом.</p>"
        "<h2>Преподаватели</h2>"
        "<p>В команде — профессиональные педагоги с уровнем языка не ниже B2 и любовью к своему делу. В школе действует собственная система развития преподавателей: регулярное повышение квалификации по методике Фоксинбург. Хотите работать с нами — смотрите <a href=\"/vakansii\">вакансии</a>.</p>"
        "<h2>Достижения</h2>"
        "<p>Оба филиала имеют рейтинг 5,0 на Яндекс.Картах, а в 2026 году школа получила награду «Хорошее место» — отметку для организаций со стабильно высокими оценками. Подробнее и ссылки на карточки — на странице <a href=\"/otzyvy\">отзывов</a>.</p>"
        "<h2>Филиалы и контакты</h2>"
        "<ul>"
        '<li>Долгопрудный, пр-кт Лихачевский, 76к1 — <a href="tel:+79939232309">8 993 923-23-09</a>;</li>'
        '<li>Долгопрудный, пр-кт Ракетостроителей, 9к3 — <a href="tel:+79167323169">8 916 732-31-69</a>.</li>'
        "</ul>"
        "<p>Работаем ежедневно с 9:00 до 21:00. Почта: school@foxinburg-edu.ru. Карта, маршруты и форма заявки — на странице <a href=\"/kontakty\">контактов</a>.</p>"
        "<h2>Мы в соцсетях</h2>"
        "<ul>"
        '<li><a href="https://vk.ru/foxyfoxclub" target="_blank" rel="noopener">ВКонтакте — foxyfoxclub</a>;</li>'
        '<li><a href="https://t.me/foxinburg" target="_blank" rel="noopener">Telegram — foxinburg</a>;</li>'
        '<li><a href="https://max.ru/id611904726658_biz" target="_blank" rel="noopener">Max-канал школы</a>;</li>'
        '<li><a href="https://wa.me/79939232309" target="_blank" rel="noopener">WhatsApp</a>.</li>'
        "</ul>"
        "<h2>Документы</h2>"
        "<p>Школа работает по официальной образовательной лицензии. Как мы обрабатываем персональные данные — в <a href=\"/policy\">политике конфиденциальности</a>.</p>"
        '<div class="fxb-related"><h2>Следующий шаг</h2><div class="fxb-related-list">'
        '<a href="/tseny">Цены на программы</a>'
        '<a href="/otzyvy">Отзывы о школе</a>'
        '<a href="/kontakty">Контакты</a>'
        "</div></div>"
        "</div></div></section>",
    ],
    "extra_jsonld": [
        webpage_jsonld(
            "AboutPage",
            "О языковой школе Фоксинбург в Долгопрудном",
            "Языковая школа Фоксинбург в Долгопрудном: английский, немецкий и китайский для детей и взрослых, подготовка к ВПР/ОГЭ/ЕГЭ. 2 филиала, рейтинг 5,0.",
            SITE + "/about",
        ),
        breadcrumb_jsonld([
            ("Главная", SITE + "/"),
            ("О школе", SITE + "/about"),
        ]),
    ],
    "lead_subject": "Знакомство со школой (страница О нас)",
    "lead_hero_window": "Блок героя",
    "lead_final_window": "Финальный блок",
    "cta_title": 'Познакомьтесь со школой на <span class="fxb-accent">бесплатной диагностике</span>',
    "cta_text": "Покажем филиал, познакомим с педагогом и методикой и определим уровень — без обязательств.",
}

NEWS_POST_1 = {
    "type": "article",
    "alias": "novosti-so-skolki-let-uchit-anglijskij",
    "title": "Со скольки лет учить английский ребёнку",
    "description": "Разбираем, когда начинать английский с ребёнком, что даёт ранний старт и как подать язык без перегрузки и стресса.",
    "category": "Полезное для родителей",
    "date": "2025-06-15",
    "reading_time": "8 минут чтения",
    "hero_grad": "linear-gradient(135deg,#2e1a47 0%,#662d92 55%,#8a4fb8 100%)",
    "body": [
        ("h2", "Короткий ответ: начинать можно раньше, чем кажется"),
        ("p", "На вопрос «со скольки лет учить английский ребёнку» нет одной правильной цифры. Всё зависит от того, как вы хотите знакомить малыша с языком. В раннем возрасте важнее не объём правил, а мягкое, регулярное присутствие английской речи вокруг ребёнка. Уже в 3–4 года дети легко воспринимают песни, рифмовки, короткие команды и игровые задания, а в 5–7 лет можно подключать более осознанные занятия, если они построены через движение, сюжет и игру."),
        ("p", "Часто родители ждут, пока ребёнок «созреет» для языка, и переживают, что раньше будет слишком сложно. На практике сложность определяется не возрастом, а форматом. Если урок напоминает маленькое приключение, где есть картинка, движение, повторение и понятный результат, ребёнок включается спокойно. Поэтому ранний старт не означает раннюю зубрёжку. Он означает раннее знакомство с языком как с естественной частью мира."),
        ("h2", "Что даёт ранний старт"),
        ("ul", [
            "Ребёнок быстрее привыкает к звучанию английской речи и перестаёт воспринимать язык как «что-то чужое».",
            "Появляется база произношения: интонации, ритм, звуки и простые речевые модели усваиваются легче.",
            "Язык входит в жизнь без давления, поэтому у ребёнка меньше страха ошибиться и больше интереса к занятиям.",
            "Когда в школе начинается системное обучение, английский уже не кажется совершенно новым и неизвестным предметом.",
        ]),
        ("p", "Важный бонус раннего старта — уверенность. Ребёнок не обязан сразу говорить длинными фразами или читать тексты. Достаточно того, что он узнаёт слова, откликается на знакомые инструкции, повторяет песенки и с интересом смотрит на английский как на понятную игру. Такой опыт потом очень помогает на школьных уроках: ребёнок не пугается нового материала, потому что уже однажды убедился, что язык можно изучать спокойно и с удовольствием."),
        ("h2", "Когда стоит начинать именно занятия"),
        ("p", "Если вы хотите не только познакомить малыша с языком, но и получить устойчивый результат, то ориентируйтесь на его готовность к формату занятий. Ребёнок должен хотя бы немного уметь слушать взрослого, включаться в короткое задание и оставаться в мини-группе без сильного утомления. Для кого-то это случается в 4 года, для кого-то ближе к 6. Именно поэтому у нас так хорошо работают <a href=\"/doshkolniki\">программы для дошкольников</a>: там английский идёт через игру, движение и повторение, а не через школьную нагрузку."),
        ("p", "Дальше вступает в силу ещё один момент — темп развития. Один ребёнок в 5 лет уже легко запоминает названия цветов и животных, другому в этом же возрасте комфортнее слушать песенки и постепенно привыкать к английской речи. Оба варианта нормальны. Важно не сравнивать детей между собой, а смотреть на их интерес, концентрацию и эмоциональную готовность."),
        ("h3", "Как понять, что пора идти на занятия"),
        ("p", "Есть несколько простых признаков: ребёнок с удовольствием повторяет слова и рифмовки, спокойно воспринимает короткие инструкции на слух, любит карточки, песенки и настольные игры, а ещё готов приходить на занятие без длительной адаптации. Это хороший момент, чтобы попробовать регулярный формат. Для младших школьников уже можно переходить к более структурной базе — чтению, письму, словарю и первым грамматическим моделям. В этом хорошо помогают наши <a href=\"/mladshie-shkolniki\">занятия для младших школьников</a>."),
        ("h2", "Как мы подаём английский маленьким детям"),
        ("p", "В Фоксинбурге мы не торопим ребёнка и не перегружаем его правилами. На старте важнее не список тем, а комфортная языковая среда. Дети много двигаются, слушают, отвечают хором и индивидуально, играют в короткие сюжетные задания и постепенно собирают свой первый словарь. Педагог следит, чтобы новый материал не копился тяжёлым комом, а ложился слоями: сегодня одно слово, завтра короткая фраза, потом мини-диалог."),
        ("p", "Такой подход особенно важен в дошкольном и младшем школьном возрасте. В этот период формируется отношение к учёбе вообще: будет ли ребёнок ждать занятия с интересом или воспринимать их как обязательную нагрузку. Поэтому наш ответ на вопрос «со скольки лет» простой: начинать можно тогда, когда формат подходит ребёнку, а материал подан бережно и понятно. В этом случае английский становится не гонкой за результатом, а частью хорошей учебной привычки."),
    ],
    "related": [
        ("Английский для дошкольников", "/doshkolniki"),
        ("Английский для младших школьников", "/mladshie-shkolniki"),
        ("Новости и статьи", "/novosti"),
    ],
    "faq": [
        ("Со скольки лет вы принимаете детей?", "С 2–3 лет — в игровых группах для дошкольников. Формат: песенки, движение, творчество, короткие задания. Никакой зубрёжки — язык усваивается естественно, как родной."),
        ("Не рано ли английский в 3 года, если ребёнок ещё и по-русски не идеально говорит?", "Не рано. Детский мозг легко разделяет языки, если каждый живёт в своём контексте. Занятия идут 2 раза в неделю — это мягкое знакомство, а не вторая школа."),
        ("Что лучше в раннем возрасте: группа или индивидуально?", "Группа. Малыши учатся через подражание и игру со сверстниками, а в мини-группе 6–8 человек педагог успевает уделить внимание каждому."),
    ],
}

NEWS_POST_2 = {
    "type": "article",
    "alias": "novosti-kak-podgotovitsya-k-oge-anglijskij",
    "title": "Как подготовиться к ОГЭ по английскому: пошаговый план",
    "description": "Пошагово разбираем подготовку к ОГЭ по английскому: сроки, навыки, типичные ошибки и как выстроить спокойный маршрут к экзамену.",
    "category": "Экзамены",
    "date": "2025-06-20",
    "reading_time": "9 минут чтения",
    "hero_grad": "linear-gradient(135deg,#241a36 0%,#5a2d8f 55%,#8a4fb8 100%)",
    "body": [
        ("h2", "С чего начинается подготовка"),
        ("p", "Подготовка к ОГЭ по английскому редко начинается с тестов. Гораздо полезнее сначала понять структуру экзамена и честно оценить текущий уровень. В ОГЭ проверяются аудирование, чтение, грамматика и лексика, письмо и говорение — и каждый из этих блоков требует своей тренировки. Если ребёнок просто «много занимается английским», но не видит сам формат, на экзамене он легко теряет баллы на мелочах. Поэтому первый шаг — не наращивать объём любой ценой, а выстроить маршрут."),
        ("p", "Оптимально начинать за год-полтора до экзамена, с 8–9 класса. Это даёт время спокойно пройти базу, укрепить слабые места и несколько раз потренироваться в формате, близком к реальному. Но если время уже поджимает, не стоит опускать руки: даже за несколько месяцев можно заметно улучшить результат, если заниматься системно. Главное — не прыгать между темами хаотично."),
        ("h2", "Какие навыки важно тренировать"),
        ("ul", [
            "Аудирование — чтобы ребёнок привыкал быстро схватывать смысл и не паниковал, если не понял каждое слово.",
            "Чтение — для уверенного поиска информации, понимания текста и работы с вопросами по содержанию.",
            "Грамматика и лексика — чтобы задания на формы слов и языковые конструкции не отнимали баллы «по привычке».",
            "Письмо — для аккуратного, понятного ответа в рамках нужного объёма и структуры.",
            "Говорение — чтобы в устной части ученик не зависал от волнения и мог спокойно ответить по теме.",
        ]),
        ("p", "Лучше всего работает сочетание коротких регулярных блоков. Один день — аудирование и повторение слов, другой — чтение и грамматика, третий — письмо или говорение. Так подготовка становится живой системой, а не длинным списком упражнений. Важно и то, что навыки не существуют отдельно: хороший словарь помогает читать, а чтение — писать и говорить. Поэтому план должен быть связным."),
        ("h2", "Типичные ошибки перед экзаменом"),
        ("p", "Самая частая ошибка — готовиться только к тому, что ребёнок уже и так умеет. Например, если школьник любит читать, он может бесконечно проходить тексты и при этом избегать говорения. Но на ОГЭ слабое звено всё равно станет заметным. Другая ошибка — слишком поздно знакомиться с критериями оценивания. Экзамен проверяет не вообще «знание языка», а конкретный формат ответа. Если ребёнок этого не понимает, он теряет баллы даже при неплохом уровне."),
        ("p", "Ещё одна проблема — перегрузка. Когда подготовка превращается в марафон без пауз, мотивация быстро падает. Гораздо полезнее стабильный график, где есть место для повторения, контроля и небольших побед. Именно так обычно строится работа на программе <a href=\"/oge-anglijskij\">подготовки к ОГЭ по английскому</a>: от диагностики и разбора ошибок до регулярной практики формата и отслеживания прогресса. Для тех, кто думает уже о будущем, полезно помнить, что похожая логика нужна и на <a href=\"/ege-anglijskij\">ЕГЭ</a> — только с более высоким уровнем требований."),
        ("h3", "Пошаговый план, который помогает держать темп"),
        ("html", "<ul><li>Сначала диагностика и определение слабых тем.</li><li>Потом повторение базы: словарь, грамматика, типовые конструкции.</li><li>После этого — отдельная тренировка каждого экзаменационного раздела.</li><li>Дальше — пробные варианты с разбором ошибок и временем на исправление.</li><li>В финале — повторение, настрой и работа над уверенностью.</li></ul>"),
        ("p", "Если план выстроен заранее, экзамен перестаёт казаться чем-то неуправляемым. Ребёнок понимает, что у него есть последовательность действий: сначала разобраться в структуре, потом подтянуть навыки, затем отработать формат и в конце спокойно пройти пробник. Такой подход снимает лишнее напряжение и делает подготовку предсказуемой. А именно предсказуемость и спокойствие часто оказываются важнее, чем разовые рывки."),
        ("h2", "Как школа помогает пройти путь без хаоса"),
        ("p", "В хорошей подготовке к ОГЭ всегда есть педагог, который держит маршрут: объясняет, что делать сейчас, что повторить дома и где уже виден прогресс. Это особенно ценно для семей, где у ребёнка много занятий и мало свободного времени. Когда процесс прозрачен, родители понимают, что именно тренируется, а школьник видит смысл каждой новой темы. В результате английский становится не набором случайных упражнений, а понятной системой с логичным завершением."),
        ("p", "Если подойти к экзамену спокойно и последовательно, результат обычно чувствуется не только в баллах. У ребёнка появляется уверенность: он знает, как читать задания, как распределять время, как отвечать устно и как не теряться в письме. Это и есть настоящая подготовка — когда ученик не просто «натаскан», а умеет действовать по плану."),
    ],
    "related": [
        ("Подготовка к ОГЭ по английскому", "/oge-anglijskij"),
        ("Подготовка к ЕГЭ по английскому", "/ege-anglijskij"),
        ("Новости и статьи", "/novosti"),
    ],
    "faq": [
        ("Когда сдают ОГЭ по английскому?", "В конце 9 класса, в основной период экзаменов (май–июнь). Письменная и устная части сдаются в разные дни."),
        ("Можно ли подготовиться к ОГЭ за один год?", "Да, если база не ниже A2 и заниматься системно: 2 раза в неделю плюс пробники. При пробелах в грамматике лучше начать с лета перед 9 классом."),
        ("Что сложнее всего в ОГЭ для школьников?", "Чаще всего — устная часть и аудирование: их почти не тренируют на школьных уроках. Поэтому в подготовке мы даём им отдельное время на каждом занятии."),
    ],
}

NEWS_POST_3 = {
    "type": "article",
    "alias": "novosti-kak-prohodyat-smeny-letnej-akademii",
    "title": "Как проходят смены Летней Академии",
    "description": "Рассказываем, как устроены смены Летней Академии: тематические недели, проекты, мини-группы и комфортный утренний формат.",
    "category": "События школы",
    "date": "2025-06-25",
    "reading_time": "7 минут чтения",
    "hero_grad": "linear-gradient(135deg,#c24712 0%,#f7971e 50%,#fcc419 100%)",
    "body": [
        ("video", {
            "kicker": "Видео",
            "title": "Летняя Академия — вживую",
            "lead": "Короткий ролик показывает атмосферу смен: как дети занимаются, общаются и включаются в проекты.",
            "src": "/media/summer-academy.mp4",
            "poster": "/media/summer-academy-poster.webp",
        }),
        ("h2", "Что такое смена Летней Академии"),
        ("p", "Летняя Академия — это не просто «занятия летом», а короткий интенсивный формат, в котором английский живёт в течение дня. Ребёнок приходит в комфортное время, погружается в тему смены и каждый день видит, как язык нужен для общения, игры, мини-проектов и творческих заданий. Летом у детей обычно появляется больше свободы, и наша задача — направить эту энергию в полезное русло без ощущения школьной нагрузки."),
        ("p", "Мы делаем ставку на живую среду: здесь язык не существует отдельно от действий. Если тема недели связана с путешествиями, дети обсуждают маршруты, собирают словарь, рисуют постеры и представляют свои идеи. Если тема про природу или технологии, появляются другие слова, другие роли и другие мини-задачи. Благодаря этому английский запоминается не в виде сухого списка, а через впечатления и практику."),
        ("h2", "Как устроены недели и занятия"),
        ("p", "Каждая смена строится вокруг нескольких тематических недель. Это помогает удерживать интерес и не превращать лето в бесконечные одинаковые уроки. Внутри недели могут быть мини-проекты, игры, творческие задания, короткие презентации и задания на общение. Дети пробуют себя в ролях, договариваются друг с другом, слушают педагога и постепенно начинают говорить свободнее. Для многих именно такой формат становится тем самым моментом, когда английский перестаёт пугать."),
        ("ul", [
            "тематические недели дают ощущение новизны и помогают легче запоминать слова;",
            "мини-проекты связывают речь, письмо, слушание и творчество в одном занятии;",
            "мини-группы позволяют педагогу видеть каждого ребёнка и давать обратную связь;",
            "утренние занятия оставляют свободным остаток дня для прогулок и отдыха;",
        ]),
        ("h3", "Почему мини-группы так важны летом"),
        ("p", "Летом детям особенно нужна лёгкость. Поэтому мы делаем группы небольшими и собираем их по возрасту и уровню. В такой атмосфере проще говорить, задавать вопросы и включаться в задания без стеснения. Педагог успевает не только объяснить материал, но и подхватить инициативу ребёнка, поддержать его идею и помочь выразить мысль по-английски. Это создаёт ощущение маленького языкового клуба, а не формального урока."),
        ("p", "Утренняя часть дня тоже играет важную роль: ребёнок ещё не устал, настроение обычно лучше, а после занятия остаётся время на летние дела. Именно поэтому смены Летней Академии хорошо подходят семьям, которым важно сохранить баланс между полезным занятием и полноценными каникулами. Формат даёт структуру, но не забирает лето."),
        ("h2", "Что ребёнок уносит с собой после смены"),
        ("p", "Главная ценность летней программы — не только новый словарь, но и ощущение, что английский может быть частью интересной жизни. Ребёнок становится смелее в речи, быстрее включается в задания, легче взаимодействует в группе и не теряет контакт с языком за длинные каникулы. Когда осенью начинается учебный год, старт оказывается заметно мягче. Это особенно заметно у детей, которые летом успели не «отдохнуть от языка», а использовать его в живом, вдохновляющем формате."),
        ("p", "Ещё один важный результат — привычка думать на языке и не бояться высказаться. На смене дети не просто повторяют слова, а пробуют объяснять, уточнять, договариваться и представлять свои идеи. Это полезно и для тех, кто потом вернётся в обычную школьную группу, и для тех, кто осенью пойдёт дальше по своей программе. Летний опыт часто становится точкой роста: ребёнок замечает, что английский можно не только учить, но и использовать."),
        ("h3", "Почему летний формат запоминается"),
        ("p", "Летом у детей больше свободы, а значит — больше внутреннего ресурса для нового. Именно поэтому смены Летней Академии часто оставляют очень тёплое впечатление: здесь есть и общение, и движение, и творчество, и ощущение маленького события. Когда обучение связано с приятными эмоциями, знания лучше закрепляются, а желание продолжать заниматься осенью только растёт. В этом и состоит смысл хорошей летней программы."),
        ("p", "Подробнее о самом направлении можно посмотреть на странице <a href=\"/letnyaya-akademiya\">Летней Академии</a>. А если хочется быть в курсе школьных новостей и полезных материалов, заглядывайте в <a href=\"/novosti\">новости и статьи</a> — там мы собираем короткие разборы, ответы на частые вопросы и рассказы о наших программах. Это удобный способ не потерять летний настрой и выбрать следующий шаг заранее."),
    ],
    "related": [
        ("Летняя Академия", "/letnyaya-akademiya"),
        ("Новости и статьи", "/novosti"),
        ("Онлайн-занятия летом", "/online-zanyatiya"),
    ],
    "faq": [
        ("В каком возрасте можно в Летнюю Академию?", "Программа рассчитана на детей 6–14 лет, группы формируются по возрасту и уровню английского."),
        ("Сколько длится смена и что в неё входит?", "Смена идёт одну-две недели: английский каждый день в игровом формате, творческие мастер-классы, спорт и тематические дни. Питание и материалы включены."),
        ("Нужен ли ребёнку опыт изучения английского?", "Нет, начинающим тоже комфортно: задания подбираются по уровню, а языковая среда мягкая — без оценок и давления."),
    ],
}

NEWS_POST_4 = {
    "type": "article",
    "alias": "novosti-vtoroj-inostrannyj-yazyk-nemeckij-ili-kitajskij",
    "title": "Второй язык после английского: как выбрать между немецким и китайским",
    "description": "Разбираем, когда ребёнку, который уже учит английский, можно подключать второй иностранный язык — и как выбрать между немецким и китайским без риска перегрузки.",
    "category": "Полезное для родителей",
    "date": "2026-07-26",
    "reading_time": "8 минут чтения",
    "hero_grad": "linear-gradient(135deg,#392852 0%,#6237a2 55%,#9d5fc9 100%)",
    "body": [
        ("h2", "Когда ребёнок готов ко второму языку"),
        ("p", "Как только английский перестаёт быть пугающим и превращается в привычную часть недели, у родителей часто возникает следующий вопрос: не пора ли добавить ещё один язык? Однозначного возраста «для всех» здесь нет, но есть ориентир, на который опираются методисты: второй иностранный имеет смысл подключать, когда родной язык уже устойчив, а по английскому есть хотя бы база — простые фразы, понимание на слух, спокойное отношение к самому процессу занятий. У большинства детей это совпадает примерно с 8–10 годами, но иногда наступает раньше или позже — по факту, а не по паспорту."),
        ("p", "Важная деталь: ждать «идеального» английского не нужно. Достаточно, чтобы ребёнок не боялся иностранной речи, умел удерживать внимание на занятии 30–40 минут и уже понимал на своём опыте, что язык — это система, а не набор случайных слов. Именно это понимание и есть тот самый задел, который делает второй язык заметно легче первого."),
        ("h2", "Не запутается ли ребёнок в языках"),
        ("p", "Это главный страх родителей, и он вполне объясним. На практике временное смешивание слов из разных языков — нормальный этап освоения, а не сигнал, что что-то идёт не так. Дети, которые уже разбирались с одним иностранным языком, легче схватывают саму идею «языковости»: что бывают разные звуки, разный порядок слов, разные способы задать вопрос. Эта база помогает при знакомстве с любым следующим языком, а не только с конкретным немецким или китайским."),
        ("p", "Есть два процесса, которые идут параллельно. Интерференция — когда структура одного языка непроизвольно переносится в другой, отсюда акцент или забавные грамматические кальки. И положительный перенос — когда уже освоенные стратегии запоминания слов, чтения или построения фразы облегчают работу с новым материалом. У детей, которые регулярно занимаются и не путают языки между собой по ситуациям, перенос обычно перевешивает интерференцию. Помогает простое правило: разные учителя, разные материалы, разные поводы — тогда в голове у ребёнка языки не сливаются в одну кашу."),
        ("h2", "Немецкий или китайский: в чём разница для ребёнка"),
        ("p", "Здесь всё зависит от того, что вы хотите получить на старте — мягкий вход или яркое, необычное впечатление."),
        ("ul", [
            "Немецкий уже частично «знаком» после английского: та же латиница, похожие категории вроде времени и порядка слов, которые удобно объяснять через сравнение с английским.",
            "Китайский обходится без падежей и спряжений — с этой стороны он проще, — но добавляет тоны и иероглифику: непривычную для русскоязычного ребёнка систему звучания и совсем другую систему письма.",
        ]),
        ("p", "Если задача — снизить нагрузку и дать ребёнку опереться на то, что он уже знает, немецкий обычно заходит легче: многие объяснения по артиклям, временам и базовым конструкциям можно строить через параллель с английским, и ребёнок экономит силы на самом привычном — распознавании букв. Мы ведём <a href=\"/nemeckij-yazyk\">немецкий язык</a> по той же методике, что и английский, поэтому переход между двумя языками получается плавным, а не «с нуля» каждый раз."),
        ("p", "Китайский — другая история, и она не хуже, просто иначе устроена. Как раннее игровое знакомство — песни, отдельные слова, простые иероглифы-картинки — он подходит уже дошкольникам, без цели «выучить», просто для расширения кругозора. А как системное обучение — с тонами, письмом и разговорной практикой — китайский лучше заходит чуть позже, когда ребёнок способен удерживать внимание на непривычном звучании и не пугается того, что буквы здесь не работают так, как в русском или английском. У нас <a href=\"/kitajskij-yazyk\">китайский язык</a> ведут через ту же логику: от тонов и иероглифики — к живой речи, в мини-группах, с постепенным нарастанием сложности."),
        ("h2", "Как не перегрузить ребёнка"),
        ("p", "Сигналы перегрузки редко выглядят как «плохо запоминает слова». Гораздо чаще это про настроение и энергию: ребёнок начинает отказываться идти на занятие, жалуется на усталость именно после уроков языка, раздражается или заметно теряет интерес к тому, что раньше нравилось. Если такое повторяется не разово, а систематически — это повод притормозить, а не заставлять «через не хочу»."),
        ("ul", [
            "Держите первый язык основным по нагрузке — 2–3 занятия в неделю, второй язык добавляйте мягче, 1–2 раза в неделю и в более игровом формате.",
            "На старте не гонитесь за результатом во втором языке — важнее интерес и отсутствие страха, а не скорость.",
            "Разводите языки по ситуациям и материалам: разные тетради, разные форматы занятий — так меньше путаницы и легче переключаться.",
            "Ориентируйтесь на настроение ребёнка, а не на абстрактную норму «сколько языков должен знать современный школьник».",
        ]),
        ("p", "Если признаки усталости накапливаются, разумно не бросать второй язык совсем, а временно перевести его в лёгкий поддерживающий формат — мультфильмы, песни, игры без домашних заданий — и вернуться к системным занятиям, когда ресурс восстановится."),
        ("h2", "Как мы подключаем второй язык в Фоксинбурге"),
        ("p", "Когда родители приходят с вопросом «а не рано ли», мы обычно предлагаем начать с пробного урока: так сразу видно, как ребёнок реагирует на новый язык вживую, а не в теории. Немецкий и китайский у нас ведут по той же методике, что и английский — понятная система, живое общение, мини-группы, — поэтому ребёнку не приходится заново учиться быть учеником: меняется язык, а не подход к занятиям. Если сомневаетесь, какой язык выбрать, — расскажите нам, что ребёнку интересно и как проходит его английский, и мы поможем определиться на пробном уроке."),
    ],
    "related": [
        ("Немецкий язык", "/nemeckij-yazyk"),
        ("Китайский язык", "/kitajskij-yazyk"),
        ("Новости и статьи", "/novosti"),
    ],
    "faq": [
        ("Какой второй язык выбрать: немецкий или китайский?", "Оба полезны. Немецкий ближе по структуре к английскому и даётся быстрее; китайский развивает слух и память и очень востребован в мире. Ориентируйтесь на интерес ребёнка — он важнее «стратегии»."),
        ("Не помешает ли второй язык английскому?", "Нет, если языки идут в своём ритме и у каждого — свой педагог и своё время. Дети прекрасно разделяют языки, а второй иностранный обычно ускоряет развитие речи в целом."),
        ("С какого возраста начинать второй язык?", "Комфортно — с 7–8 лет, когда английский уже стоит на базовом уровне. Но можно и раньше в игровом формате."),
    ],
}

NEWS_POST_5 = {
    "type": "article",
    "alias": "novosti-anglijskij-letom-kak-ne-poteryat-navyk",
    "title": "Английский летом: как не растерять навык за каникулы",
    "description": "Разбираем, действительно ли за лето забывается английский, что слабеет первым и как за 5–15 минут в день поддержать язык без уроков.",
    "category": "Полезное для родителей",
    "date": "2026-07-28",
    "reading_time": "6 минут чтения",
    "hero_grad": "linear-gradient(135deg,#241a36 0%,#5a2d8f 55%,#9d5fc9 100%)",
    "body": [
        ("h2", "Стоит ли бояться летнего провала в английском"),
        ("p", "Каждый август родители задаются одним и тем же вопросом: не забыл ли ребёнок за лето всё, что выучил за год? Спешим успокоить: заметное ухудшение владения вторым языком у детей обычно начинается не за несколько недель без практики, а ближе к 5 месяцам непрерывного перерыва, а по-настоящему выраженные проблемы с подбором слов — после года и больше. Одни летние каникулы, даже без единого урока, язык не «стирают» — они лишь немного затрудняют доступ к нему, особенно в разговоре. Так что тотальной паники здесь не нужно."),
        ("p", "Это не значит, что лето можно совсем игнорировать. Разница между «ничего не делать два месяца» и «уделять языку по 10 минут в день» ощутима — просто не в духе «либо всё, либо ничего», а в духе «чуть-чуть постоянно лучше, чем ничего вообще»."),
        ("h2", "Что слабеет первым"),
        ("p", "Без регулярной практики быстрее всего страдает разговорная беглость и скорость подбора слов — это активные навыки, которые держатся на постоянном использовании. А вот понимание речи на слух гораздо устойчивее и «проседает» намного медленнее. Проще говоря: ребёнок, скорее всего, по-прежнему хорошо понимает английскую речь после каникул, но первые пару занятий может говорить чуть медленнее и дольше подбирать слова — это нормально и быстро проходит, а не признак того, что весь год занятий «сгорел зря»."),
        ("h2", "Как поддержать язык без уроков"),
        ("p", "Главный принцип, который подтверждают исследования: короткий ежедневный контакт с языком работает лучше, чем редкие длинные занятия. Не нужно устраивать ребёнку урок на час — достаточно 5–15 минут в день, чтобы язык оставался «на связи»."),
        ("ul", [
            "Короткое видео или отрывок подкаста на английском вместо части мультфильма на русском.",
            "Несколько минут вслух — пересказать, что видел на прогулке, или описать картинку.",
            "Одна короткая переписка или разговор в неделю с кем-то, кто говорит по-английски — даже игрушечный диалог с родителем считается.",
            "Небольшое повторение слов в игровой форме — карточки, простая настольная игра, приложение на 5 минут.",
        ]),
        ("p", "Важно не превращать это в обязаловку — тогда эффект будет обратным. Цель летом не «пройти программу», а просто не дать языку окончательно замолчать."),
        ("h2", "Если пропустили больше — как быстро возвращается форма"),
        ("p", "Даже если лето прошло совсем без практики, пугаться осеннего старта не стоит: знания никуда не пропадают, теряется только лёгкий доступ к ним. У большинства детей беглость и скорость речи возвращаются за первую-вторую неделю регулярных занятий — язык «просыпается» быстрее, чем кажется по первому неловкому занятию в сентябре."),
        ("p", "Это касается не только детей — взрослые, которые давно не практиковали английский, проходят точно такой же путь: лёгкая растерянность на первом занятии и быстрое восстановление беглости при регулярной практике. Если давно откладывали возвращение к языку — <a href=\"/anglijskij-dlya-vzroslyh\">английский для взрослых</a> начинается с бесплатной диагностики именно для того, чтобы честно понять, где вы сейчас, без завышенных ожиданий к первому занятию."),
        ("p", "Если хотите понять, в какой форме ребёнок подошёл к концу лета, и без стресса включиться в новый учебный год — там же расскажем, <a href=\"/novosti-zapis-na-novyj-uchebnyj-god-anglijskij-nemeckij-kitajskij\">как проходит запись на новый учебный год</a> по английскому, немецкому и китайскому."),
    ],
    "related": [
        ("Английский для взрослых", "/anglijskij-dlya-vzroslyh"),
        ("Новости и статьи", "/novosti"),
    ],
    "faq": [
        ("Как не потерять английский за лето?", "Главное — регулярность в лёгком формате: 15–20 минут в день песенок, мультфильмов, приложения или чтения. Без давления, но каждый день."),
        ("Достаточно ли мультфильмов на английском?", "Как поддержка — да, они сохраняют восприятие на слух. Но без говорения и повторения словарь «засыпает», поэтому добавьте разговорную практику хотя бы пару раз в неделю."),
        ("Есть ли у вас летние занятия?", "Да: Летняя Академия для детей и поддерживающие онлайн-занятия — короткие встречи, чтобы язык не простаивал, а каникулы оставались каникулами."),
    ],
}

NEWS_POST_6 = {
    "type": "article",
    "alias": "novosti-kak-ponyat-uroven-rebenka-pered-uchebnym-godom",
    "title": "Как понять реальный уровень английского у ребёнка перед учебным годом",
    "description": "Простые домашние проверки, которые показывают, что ребёнок правда умеет на английском — и типичные ошибки родителей при самооценке уровня.",
    "category": "Экспертное мнение",
    "date": "2026-07-30",
    "reading_time": "7 минут чтения",
    "hero_grad": "linear-gradient(135deg,#241a36 0%,#662d92 55%,#a05fd4 100%)",
    "body": [
        ("h2", "Зачем вообще проверять уровень перед стартом"),
        ("p", "Перед новым учебным годом родители чаще всего ориентируются на школьную оценку или общее впечатление: «вроде неплохо понимает мультфильмы» или «стесняется говорить, наверное, слабый». Оба ориентира легко ошибаются в разные стороны. Оценка в школе не всегда отражает реальные навыки, а домашнее впечатление часто строится на паре ярких эпизодов, а не на системной картине. Если уровень определён неточно, ребёнок попадает в группу, которая либо скучна, либо перегружает — и то, и другое гасит интерес быстрее, чем кажется."),
        ("h2", "Смотрите не на «знает / не знает», а на то, что ребёнок умеет сделать"),
        ("p", "Самый надёжный ориентир — не абстрактный «уровень», а конкретные действия в четырёх областях: понимание на слух, говорение, чтение и письмо. Ребёнок может быть силён в одном и слаб в другом — это нормально, и именно поэтому смотреть нужно на все четыре, а не только на то, разговаривает ли он с вами по-английски."),
        ("h2", "Как отличить настоящее понимание от заученных фраз"),
        ("p", "Самая частая ошибка — принять красиво спетую песенку или заученный диалог из мультфильма за «хорошо знает язык». Проверяется это очень просто: слегка измените привычную формулировку. Если ребёнок обычно откликается на «Sit down», попробуйте «Please, sit on the chair». Если вместо «I like football» спросить «What do you like to do?», ответ должен появиться не автоматически, а с небольшой паузой на обдумывание — это и есть разница между запоминанием звука и реальным пониманием смысла."),
        ("ul", [
            "Понимает только самые привычные фразы, теряется при небольшом изменении формулировки — уровень пока начальный, опора на узнавание, а не на смысл.",
            "Свободно реагирует на новую формулировку знакомой просьбы, может ответить чуть иначе, чем заучено — понимание уже настоящее, не механическое.",
            "Легко поёт песни и цитирует мультфильмы, но теряется в простом разговоре — явный признак «заученного набора», а не разговорного навыка.",
        ]),
        ("h2", "Три коротких домашних теста на 15–20 минут"),
        ("p", "Не нужно устраивать ребёнку экзамен — три простые игры дают достаточно честную картину."),
        ("ul", [
            "«Инструкции»: дайте команду из одного шага («Touch your nose»), затем из двух («Pick up the toy and put it on the shelf»). Смотрите, нужны ли жесты и подсказки, и с какого шага ребёнок теряется.",
            "«История по картинке»: покажите фото или иллюстрацию и попросите рассказать историю по-английски без текста. Отдельные слова — начальный уровень; простые предложения с сюжетом — уверенный элементарный; связный рассказ с «потому что» и «а потом» — уже средний уровень.",
            "«Мини-чтение»: дайте короткий текст на знакомую тему, попросите пересказать и задайте пару вопросов, включая один вопрос «почему». Важно не то, идеален ли пересказ, а понимает ли ребёнок общий смысл и пробует ли отвечать на «почему», а не просто повторяет отдельные слова из текста.",
        ]),
        ("h2", "Типичные ошибки родителей при самооценке"),
        ("p", "Кроме переоценки из-за заученных фраз есть и обратная ошибка — недооценка из-за стеснения. Ребёнок, особенно подросток, может прекрасно понимать инструкции и с удовольствием читать простые тексты дома, но односложно отвечать в разговоре, потому что боится ошибиться при родителях. В таком случае разумнее опираться на слушание и чтение, а говорение подтягивать мягко, через игру, а не через давление — у нас это особенно заметно на программах для <a href=\"/podrostki\">подростков</a>, где именно стеснение, а не реальный уровень, чаще всего мешает ребёнку показать, что он умеет."),
        ("p", "Ещё одна частая ловушка — смотреть только на говорение и упускать чтение и понимание на слух, хотя именно они дают более полную картину уровня. Если совместить наблюдения из трёх домашних тестов, к первому уроку у вас будет не смутное «вроде нормально», а конкретное описание: что ребёнок понимает, что может рассказать и где ему пока нужна помощь. Именно с этого мы и начинаем на пробном уроке — не с формального теста, а с спокойного разговора и заданий в игровой форме, чтобы увидеть реальную картину, а не первое волнение. Если уже готовы узнать, <a href=\"/novosti-zapis-na-novyj-uchebnyj-god-anglijskij-nemeckij-kitajskij\">как проходит запись на новый учебный год</a>, — рассказываем в отдельной статье."),
    ],
    "related": [
        ("Английский для подростков", "/podrostki"),
        ("Новости и статьи", "/novosti"),
    ],
    "faq": [
        ("Как понять уровень английского ребёнка?", "Самый точный способ — бесплатная диагностика с педагогом: 30–40 минут в игровом формате, оцениваем говорение, аудирование, чтение и словарь. Онлайн-тест на сайте тоже даёт ориентир по грамматике."),
        ("Что такое уровни A1, A2, B1?", "Это международная шкала CEFR: A1–A2 — начальный (простые фразы, бытовые темы), B1–B2 — средний (уверенное общение), C1–C2 — свободный. Школьная программа 4 класса — примерно A1, ОГЭ — A2–B1."),
        ("Зачем определять уровень перед учебным годом?", "Чтобы попасть в группу «своего» уровня: слишком лёгкая — скучно, слишком сложная — стресс. Точная посадка по уровню — главный фактор прогресса."),
    ],
}

NEWS_POST_7 = {
    "type": "article",
    "alias": "novosti-zapis-na-novyj-uchebnyj-god-anglijskij-nemeckij-kitajskij",
    "title": "Запись на новый учебный год: английский, немецкий, китайский",
    "description": "Какие форматы обучения есть в Фоксинбурге на английском, немецком и китайском — группы, индивидуальные занятия, онлайн — и с чего начинается запись.",
    "category": "Новости школы",
    "date": "2026-08-01",
    "reading_time": "6 минут чтения",
    "hero_grad": "linear-gradient(135deg,#392852 0%,#662d92 55%,#c24712 100%)",
    "body": [
        ("h2", "Три языка, один принцип"),
        ("p", "К новому учебному году в Фоксинбурге можно записаться на английский, немецкий или китайский — и по всем трём мы ведём занятия по одной и той же методике: понятная система языка, живое общение с первых занятий и мини-группы, где педагог успевает уделить время каждому. Разница между языками — в содержании, а не в подходе: во сколько бы вы ни начинали, ребёнку или взрослому не приходится заново учиться быть учеником при смене языка."),
        ("h2", "Какие форматы есть"),
        ("ul", [
            "Очно в двух филиалах в Долгопрудном — на Лихачевского, 76к1 и на Ракетостроителей, 9к3.",
            "Онлайн с педагогом — живые уроки для тех, кому удобнее заниматься из дома.",
            "Мини-группы, подобранные по возрасту и уровню — для дошкольников, школьников, подростков и взрослых отдельно.",
            "Индивидуальные занятия — персональный темп и график, если групповой формат не подходит по времени или задачам.",
        ]),
        ("p", "Формат не обязательно выбирать раз и навсегда: часто удобно начать с мини-группы, а индивидуальные занятия подключить точечно — например, перед конкретным экзаменом или поездкой."),
        ("h2", "С чего начинается запись"),
        ("p", "Для детей на английском — школа начинается с бесплатной диагностики: определяем реальный уровень и подбираем группу по возрасту, без формального теста и стресса. Для немецкого и китайского первый шаг — пробный урок: знакомим с педагогом и методикой, оцениваем уровень (или подтверждаем, что стартуем с нуля — большинство и начинает с нуля) и подбираем группу. Взрослым на английском мы тоже предлагаем начать с бесплатной диагностики — она нужна именно для честной картины «где вы сейчас», а не для оценки."),
        ("p", "Дальше — обычная последовательность: заявка на сайте или в MAX, диагностика или пробный урок, подбор группы или индивидуального расписания, и старт занятий. Если сомневаетесь между языками или форматами — на диагностике можно обсудить это вслух, а не гадать заранее."),
        ("h2", "Как оплатить обучение"),
        ("p", "На немецком, китайском и на английском для взрослых занятия можно оплатить материнским капиталом и вернуть 13% стоимости социальным налоговым вычетом — это не отдельная акция, а постоянно доступный вариант оплаты, о нём можно уточнить на диагностике или пробном уроке."),
        ("h2", "Если ещё не решили, с какого языка начать"),
        ("p", "Если ребёнок уже учит английский и вы думаете о втором языке — мы недавно разбирали, <a href=\"/novosti-vtoroj-inostrannyj-yazyk-nemeckij-ili-kitajskij\">как выбрать между немецким и китайским</a>. А если хочется для начала понять, в какой форме ребёнок подошёл к концу лета, — в статье про то, <a href=\"/novosti-anglijskij-letom-kak-ne-poteryat-navyk\">как английский переживает летние каникулы</a>, есть простой ориентир, стоит ли переживать."),
    ],
    "related": [
        ("Немецкий язык", "/nemeckij-yazyk"),
        ("Китайский язык", "/kitajskij-yazyk"),
        ("Английский для взрослых", "/anglijskij-dlya-vzroslyh"),
    ],
    "faq": [
        ("Когда начинаются занятия в новом учебном году?", "Основной старт групп — конец августа – начало сентября. Запись идёт заранее: сначала диагностика, потом подбор группы по возрасту, уровню и расписанию."),
        ("Можно ли присоединиться к группе в середине года?", "Да, если в группе есть место и уровень совпадает. Педагог поможет мягко войти в программу — дети обычно вливаются за 2–3 занятия."),
        ("Что нужно для записи?", "Оставить заявку на сайте или позвонить — пригласим на бесплатную диагностику, покажем филиал, познакомим с педагогом и предложим расписание."),
    ],
}

NEWS_POST_8 = {
    "type": "article",
    "alias": "novosti-yazykovaya-shkola-ili-repetitor-kak-vybrat",
    "title": "Языковая школа или репетитор для ребёнка: как выбрать",
    "description": "Честное сравнение группового формата и индивидуального репетитора для английского — реальные плюсы каждого варианта и типичные ошибки родителей при выборе.",
    "category": "Экспертное мнение",
    "date": "2026-08-04",
    "reading_time": "7 минут чтения",
    "hero_grad": "linear-gradient(135deg,#392852 0%,#5a2d8f 55%,#8a4fb8 100%)",
    "body": [
        ("h2", "Нет универсально лучшего варианта"),
        ("p", "Правильный вопрос — не «что лучше, школа или репетитор», а «что подходит именно этому ребёнку и этой задаче сейчас». По данным исследований в педагогике, индивидуальные занятия в среднем дают больший прирост по успеваемости — эффект известен давно: один педагог на одного ученика почти всегда обгоняет по «сухим» результатам занятия в группе. Но это не значит, что группа хуже: для разговорной практики, мотивации и снятия языкового барьера у детей она часто работает быстрее и устойчивее, чем занятия только со взрослым один на один."),
        ("h2", "Реальные плюсы группового формата"),
        ("ul", [
            "Живое общение со сверстниками — ближе к тому, как язык используется в жизни, чем разговор только с педагогом.",
            "Мотивация от команды: ребёнок видит, что другие тоже ошибаются, пробуют и постепенно говорят увереннее — страх «сделать не так» снижается.",
            "Обычно в 2–3 раза дешевле индивидуальных занятий при сопоставимом количестве часов.",
            "Меньше давления: ребёнок не под постоянным прицельным вниманием педагога, для многих это комфортнее.",
            "Больше простора для игровых форматов, ролевых игр и командных заданий, которые сложно развернуть один на один.",
        ]),
        ("h2", "Реальные плюсы индивидуального репетитора"),
        ("ul", [
            "Полная персонализация — программа подстраивается под конкретный уровень, интересы и пробелы ребёнка.",
            "Точечная работа над сложной темой: разобрать конкретную грамматику, закрыть пробел, подготовиться к экзамену с высокой ставкой.",
            "Темп полностью подстраивается под ребёнка — можно замедлиться на сложном разделе или ускориться там, где всё даётся легко.",
            "Гибкий график — удобно для семей с плотным расписанием школы и кружков.",
            "Комфортнее для стеснительного ребёнка, который теряется и не решается говорить при других.",
        ]),
        ("h2", "Как понять, что подойдёт именно вашему ребёнку"),
        ("ul", [
            "Общительный ребёнок, которому важно «разговориться» и не боится компании — обычно лучше заходит мини-группа.",
            "Тревожный, стеснительный ребёнок или заметное отставание от программы — чаще эффективнее индивидуальные занятия, хотя бы на старте.",
            "Скоро экзамен, олимпиада или конкретная высокая цель — индивидуальный формат почти всегда окупает разницу в цене.",
            "Ребёнок мотивируется командой, игрой, лёгким соревнованием — здесь группа обычно работает лучше репетитора.",
        ]),
        ("h2", "Типичные ошибки при выборе"),
        ("p", "Чаще всего родители ориентируются только на цену — что дешевле или дороже, то и лучше. На практике важнее сначала честно сформулировать задачу: разговориться, подтянуть грамматику или сдать конкретный экзамен, — и уже под неё выбирать формат, а не наоборот. Вторая частая ошибка — не менять формат, когда меняется задача: ребёнок разговорился в группе, но теперь готовится к экзамену — есть смысл на время подключить индивидуальные занятия, и наоборот. И третья — ждать, что сам факт занятий (в любом формате) решит проблему: результат в первую очередь определяется регулярностью и качеством педагога, а формат — только инструмент."),
        ("p", "Поэтому в Фоксинбурге не приходится выбирать раз и навсегда: у нас есть и мини-группы по возрасту и уровню, и <a href=\"/repetitor\">индивидуальные занятия с педагогом</a> — можно начать с одного формата и подключить второй точечно, когда изменится задача, без смены школы и педагога. Подробнее о том, как устроена запись и какие форматы доступны на английском, немецком и китайском, — в отдельной статье про <a href=\"/novosti-zapis-na-novyj-uchebnyj-god-anglijskij-nemeckij-kitajskij\">запись на новый учебный год</a>. А если сомневаетесь, какой формат подойдёт именно вашему ребёнку, — на бесплатной диагностике для <a href=\"/mladshie-shkolniki\">младших школьников</a> это можно обсудить вслух, а не гадать заранее."),
    ],
    "related": [
        ("Индивидуальные занятия (репетитор)", "/repetitor"),
        ("Запись на новый учебный год", "/novosti-zapis-na-novyj-uchebnyj-god-anglijskij-nemeckij-kitajskij"),
        ("Английский для младших школьников", "/mladshie-shkolniki"),
        ("Новости и статьи", "/novosti"),
    ],
    "faq": [
        ("Что надёжнее: школа языков или частный репетитор?", "Школа даёт систему: программа, подмена педагога при болезни, отчёты родителям, лицензия и налоговый вычет 13%. Хороший репетитор силён в точечных задачах, но всё держится на одном человеке."),
        ("Почему в школе дешевле не всегда?", "Считайте цену результата, а не часа: в школе в стоимость входят программа, материалы, приложение, отчёты и подмена педагога. У репетитора всё это вы организуете сами."),
        ("А можно совместить?", "Да, частая схема: база и разговорная практика — в мини-группе школы, точечные темы или ускоренная подготовка — индивидуально."),
    ],
}

NEWS_POST_9 = {
    "type": "article",
    "alias": "novosti-anglijskij-dlya-vzroslyh-s-nulya-s-chego-nachat",
    "title": "Английский для взрослых с нуля: с чего начать в любом возрасте",
    "description": "Разбираем миф о том, что взрослым учить язык сложнее, чем детям, честные сроки до разговорного уровня и практичный план первых недель.",
    "category": "Полезное для взрослых",
    "date": "2026-08-06",
    "reading_time": "8 минут чтения",
    "hero_grad": "linear-gradient(135deg,#2e1a47 0%,#7b4fc0 55%,#c24712 100%)",
    "body": [
        ("h2", "Правда ли, что взрослым учить язык сложнее"),
        ("p", "Один из самых частых поводов отложить английский «на потом» — уверенность, что после школы поезд ушёл, а мозг взрослого уже не так гибок, как у ребёнка. Крупные современные исследования эту идею не подтверждают: жёсткого возраста, после которого язык выучить нельзя, не существует. Снижение пластичности происходит плавно, а не обрывается в одной точке. Единственное, что действительно даётся взрослым труднее, — произношение без малейшего акцента: способность к идеальной имитации звуков снижается после подросткового возраста. А вот грамматика, словарный запас и свободное общение — абсолютно достижимы в любом возрасте, если заниматься регулярно."),
        ("p", "Честная формулировка: «говорить как диктор Би-би-си» в 40–50 лет — маловероятная цель, а вот свободно объясняться, понимать сериалы и читать по работе — совершенно реалистичная."),
        ("h2", "В чём взрослые сильнее детей"),
        ("ul", [
            "Осознанность: взрослый умеет планировать занятия, замечать, что не работает, и менять стратегию — у детей этого навыка почти нет.",
            "Понимание грамматики: правила, таблицы, сравнение с русским языком взрослым даются быстрее, чем детям.",
            "Богатый словарный запас на родном языке — легче строить ассоциации и понимать даже сложные темы.",
            "Жизненный контекст: тексты про работу, отношения, новости понятны взрослому сразу, а не требуют объяснений «с нуля».",
            "Мотивация и дисциплина — учёба ради конкретной цели (работа, переезд, путешествия) держит регулярность лучше, чем у ребёнка.",
        ]),
        ("p", "Иначе говоря, взрослые учат язык не хуже детей, а по-другому — с опорой на осознанность вместо интуиции. При правильном подходе это даже быстрее."),
        ("h2", "Сколько времени это реально займёт"),
        ("p", "По типичным методическим оценкам, до уверенного базового уровня (A2) нужно порядка 180–200 часов занятий, до крепкого разговорного (B1) — около 350–400 часов. При регулярных 5–6 часах в неделю (несколько занятий плюс немного самостоятельной практики) это примерно 8–10 месяцев до A2 и 14–18 месяцев до B1. При более интенсивном темпе сроки сокращаются почти вдвое. Первые уверенные бытовые фразы обычно появляются гораздо раньше — через 2–3 месяца регулярных занятий, и это уже ощутимый результат, а не «ещё далеко до цели»."),
        ("h2", "С чего начать в первые недели"),
        ("ul", [
            "Звуки и произношение — с самого начала, а не «потом»: взрослым сложнее перестраивать артикуляцию, поэтому шадоуинг (повторение вслух за диктором) с первых занятий экономит месяцы позже.",
            "Частотные слова и фразы вместо случайных списков — первая тысяча слов покрывает большую часть обычной речи.",
            "Простой скелет грамматики — порядок слов, глагол to be, настоящее простое время, базовые вопросы — без ухода в исключения на старте.",
            "Понятный «вход» — простые видео и адаптированные тексты, где понятно 70–80% без словаря, а не всё подряд.",
            "Говорить с первых занятий, даже с ошибками — навык говорения тренируется отдельно и не появляется сам после «достаточной» теории.",
        ]),
        ("p", "Если сравнивать себя с ребёнком-полиглотом или ждать безупречной грамотности перед первой фразой — мотивация быстро гаснет. Реалистичная цель первых недель — не идеальный язык, а ощущение, что вы уже можете что-то сказать и понять."),
        ("p", "Именно с этого мы и начинаем на бесплатной диагностике для <a href=\"/anglijskij-dlya-vzroslyh\">взрослых</a> — без оценки «хорошо или плохо», а с честного разговора о том, где вы сейчас и какой темп вам подойдёт. Про форматы и то, как проходит запись, — в статье про <a href=\"/novosti-zapis-na-novyj-uchebnyj-god-anglijskij-nemeckij-kitajskij\">запись на новый учебный год</a>."),
    ],
    "related": [
        ("Английский для взрослых", "/anglijskij-dlya-vzroslyh"),
        ("Запись на новый учебный год", "/novosti-zapis-na-novyj-uchebnyj-god-anglijskij-nemeckij-kitajskij"),
        ("Новости и статьи", "/novosti"),
    ],
    "faq": [
        ("Мне за 30 (40, 50) — не поздно ли начинать с нуля?", "Нет. Взрослые учат иначе, чем дети, но не хуже: вы понимаете логику языка и сами управляете мотивацией. У нас много учеников, начавших с нуля во взрослом возрасте."),
        ("Сколько времени нужно, чтобы заговорить?", "Первые бытовые диалоги — через 2–3 месяца регулярных занятий (2 раза в неделю). Уверенный разговорный уровень B1 — обычно за 1,5–2 года. Точнее скажем на диагностике."),
        ("Я стесняюсь говорить — как быть?", "Это нормально и очень часто встречается у взрослых. В мини-группах все начинающие, атмосфера без оценок, а педагог специально выстраивает занятие так, чтобы говорить было не страшно."),
    ],
}

NEWS_POST_10 = {
    "type": "article",
    "alias": "novosti-lozhnye-druzya-perevodchika-slova-kotorye-obmanyvayut",
    "title": "10 слов, которые обманывают всех: ложные друзья переводчика",
    "description": "Английские слова, похожие на русские, но означающие совсем другое — magazine, accurate, sympathy и ещё 7 слов, на которых легко попасться.",
    "category": "Занимательный английский",
    "date": "2026-08-08",
    "reading_time": "5 минут чтения",
    "hero_grad": "linear-gradient(135deg,#241a36 0%,#c24712 55%,#fcc419 100%)",
    "body": [
        ("h2", "Почему они называются «ложными друзьями»"),
        ("p", "Ложные друзья переводчика — слова, которые звучат почти как русские и очень хочется перевести «в лоб», но на деле означают что-то совсем другое. Термин придумали ещё лингвисты в начале XX века, и с тех пор список таких слов между русским и английским никуда не делся. Собрали десять примеров, на которых чаще всего спотыкаются — даже те, кто неплохо говорит по-английски."),
        ("ul", [
            "<b>Magazine</b> — это журнал, а не магазин. «Магазин» по-английски — shop или store.",
            "<b>Accurate</b> — значит точный, а не аккуратный. «Аккуратный» (в смысле опрятный) — tidy или neat.",
            "<b>Sympathy</b> — сочувствие, а не симпатия в смысле влечения. Для «он мне симпатичен» скорее подойдёт «I like him».",
            "<b>Actual</b> — фактический, реальный именно сейчас, а не «актуальный» в смысле «злободневный». «Актуальный» — relevant или current.",
            "<b>Prospect</b> — перспектива или потенциальный клиент, а не проспект-улица. «Проспект» как улица — avenue.",
            "<b>Genial</b> — добродушный, приветливый, а не гениальный. «Гениальный» — brilliant или genius (как существительное).",
            "<b>Intelligent</b> — просто умный, а не интеллигентный в смысле «культурный, воспитанный». Для этого смысла ближе слово cultured.",
            "<b>Fabric</b> — ткань, а не фабрика. «Фабрика» — factory.",
            "<b>Mark</b> — оценка или отметка, а не почтовая марка (это stamp) и не бренд-марка (это brand).",
            "<b>Silicon</b> — кремний, химический элемент, а не силикон. «Силикон» (материал для форм, имплантов) — silicone, с «e» на конце и другим произношением.",
        ]),
        ("h2", "Как не попадаться на этом в разговоре"),
        ("p", "Специально зубрить список ложных друзей не обязательно — они запоминаются сами, как только один раз собьют с толку в живом разговоре или тексте. Помогает привычка на незнакомом слове, которое «выглядит по-русски», на секунду притормозить и свериться со словарём, а не переводить машинально. Особенно это касается слов, которые встречаются в текстах на грамматику и чтение — именно там ложные друзья чаще всего и попадаются, потому что тексты насыщеннее бытового разговора."),
        ("p", "На занятиях мы разбираем такие слова не списком для зубрёжки, а по мере того, как они реально встречаются в текстах и разговоре — так они запоминаются с первого раза, а не теряются через неделю. Если интересно, как устроены наши занятия по <a href=\"/grammar\">грамматике</a> и чтению — там таких слов встречается немало. А другие похожие разборы языка ищите в разделе <a href=\"/novosti\">новостей и статей</a>."),
    ],
    "related": [
        ("Курс грамматики", "/grammar"),
        ("Новости и статьи", "/novosti"),
    ],
    "faq": [
        ("Что такое «ложные друзья переводчика»?", "Это слова, похожие на русские, но с другим значением: magazine — не «магазин», а «журнал», actually — не «актуально», а «на самом деле». Из-за них фразы получаются забавными или обидными."),
        ("Как их запомнить?", "Не списком, а в контексте: короткие истории и пары предложений «неправильно/правильно» запоминаются надолго. Мы разбираем такие пары на занятиях — дети их обожают."),
        ("Это актуально только для взрослых?", "Нет, школьники спотыкаются о них на контрольных и экзаменах: в ОГЭ и ЕГЭ ложные друзья — любимая ловушка составителей."),
    ],
}

NEWS_POST_11 = {
    "type": "article",
    "alias": "novosti-komu-nuzhen-repetitor-po-anglijskomu-5-priznakov",
    "title": "Кому на самом деле нужен репетитор по английскому: 5 честных признаков",
    "description": "Индивидуальные занятия дороже группы — но в пяти ситуациях они окупаются быстрее всего. Разбираем, когда репетитор действительно нужен, а когда хватит мини-группы.",
    "category": "Экспертное мнение",
    "date": "2026-08-10",
    "reading_time": "6 минут чтения",
    "hero_grad": "linear-gradient(135deg,#241a36 0%,#5a2d8f 55%,#c24712 100%)",
    "body": [
        ("h2", "Почему «всем нужен репетитор» — это миф"),
        ("p", "Индивидуальное занятие — самый дорогой формат обучения, и честный ответ на вопрос «нужен ли репетитор» почти всегда начинается с встречного: «а какая задача?». Мини-группа даёт живое общение, соревновательность и цену вдвое ниже — и для большинства детей, которые учат язык «для жизни», этого достаточно. Но есть ситуации, где групповой формат упирается в потолок, и тогда индивидуальные занятия окупаются очень быстро. Вот пять таких ситуаций."),
        ("h2", "1. Цель с дедлайном: экзамен, олимпиада, переезд"),
        ("p", "Когда результат нужен к конкретной дате — ОГЭ, ЕГЭ, олимпиада, переезд в другую школу или страну, — групповое расписание становится ограничением. В группе программа идёт в среднем темпе, а вам нужно закрыть конкретные пробелы: письмо по критериям, устную часть, определённый блок грамматики. Индивидуальные занятия позволяют не идти «с потоком», а целиться ровно в то, что даст баллы. На <a href=\"/oge-anglijskij\">подготовке к ОГЭ</a> и <a href=\"/ege-anglijskij\">ЕГЭ</a> мы часто совмещаем форматы: основа в мини-группе, а точечная доводка слабых разделов — индивидуально."),
        ("h2", "2. Заметное отставание от школьной программы"),
        ("p", "Если ребёнок пропустил базу — например, болел в начале года или переехал из школы с другим учебником, — группа по возрасту будет идти слишком быстро, а младшая группа — скучно. Индивидуальный формат позволяет за несколько месяцев закрыть именно тот слой, который потерян, и вернуться в группу сверстников без стресса. Это починка, а не постоянный режим: как только база выровнена, разумнее перейти в группу."),
        ("h2", "3. Стеснение, которое мешает говорить"),
        ("p", "Есть дети, которые понимают и знают больше, чем показывают, — но при группе не решаются открыть рот. В мини-группе такой ребёнок молчит месяцами, а прогресс стоит, потому что язык — это практика речи. Индивидуально, один на один с педагогом, стеснение уходит за несколько занятий: ошибаться некому «показать». Обычно это мостик: сначала индивидуальные занятия, затем, когда ребёнок разговорился, — группа, где он уже не боится говорить."),
        ("h2", "4. Нестандартный график семьи"),
        ("p", "Сменная школа, плотные секции, работа родителей посменно — иногда ни одно групповое расписание просто не совпадает с жизнью. Индивидуальные занятия подбираются под ваш календарь, а не наоборот, а при необходимости переносятся без потери темпа. То же касается взрослых с плавающим рабочим графиком: для них индивидуальный формат часто единственный способ заниматься регулярно, а не «когда получится»."),
        ("h2", "5. Узкая цель, которой нет в стандартной программе"),
        ("p", "Собеседование в международную компанию, английский для конкретной профессии, подготовка к поступлению в сильную школу, разговорная практика перед путешествием за две недели — стандартная программа таких задач не покрывает. Индивидуальный педагог строит программу ровно под цель и отсекает всё лишнее: вы платите только за то, что приближает результат."),
        ("h2", "Когда репетитор не нужен"),
        ("p", "Честности ради: если ребёнок общительный, идёт вровень с программой и цель — свободно говорить и не терять интерес, мини-группа справится лучше и дешевле. В группе есть то, чего не даст ни один репетитор: живые диалоги со сверстниками, игра и лёгкое соревнование. Поэтому у нас оба формата не конкурируют, а дополняют друг друга: на бесплатной диагностике мы честно говорим, какой вариант подойдёт под вашу задачу — даже если это группа, а не более дорогие индивидуальные занятия. Подробнее о том, как устроены <a href=\"/repetitor\">индивидуальные занятия в Фоксинбурге</a>, — на отдельной странице: там цены, форматы и ответы на частые вопросы."),
        ("p", "А если сомневаетесь между школой и частным репетитором в принципе — мы уже разбирали это в статье <a href=\"/novosti-yazykovaya-shkola-ili-repetitor-kak-vybrat\">«Языковая школа или репетитор для ребёнка»</a>: там сравнение по задачам, а не по ценнику."),
    ],
    "related": [
        ("Индивидуальные занятия (репетитор)", "/repetitor"),
        ("Подготовка к ОГЭ", "/oge-anglijskij"),
        ("Школа или репетитор: как выбрать", "/novosti-yazykovaya-shkola-ili-repetitor-kak-vybrat"),
        ("Новости и статьи", "/novosti"),
    ],
    "faq": [
        ("Как понять, что ребёнку нужен репетитор?", "Основные признаки: оценки просели, «ничего не понимает» на уроках, стыдится отвечать, нужен экзамен в сжатый срок или, наоборот, программа школьной группы ему уже скучна."),
        ("Репетитор — это надолго?", "Зависит от задачи. Закрыть конкретный пробел — обычно 2–4 месяца. Подготовка к ОГЭ/ЕГЭ — год-полтора. После решения задачи многие переходят в группу."),
        ("Чем индивидуальные занятия в школе лучше частника?", "Тем же, чем школа вообще: проверенная программа, отчёты родителям, подмена педагога при болезни и официальный договор с налоговым вычетом."),
    ],
}

NEWS_POST_12 = {
    "type": "article",
    "alias": "novosti-otkryt-nabor-na-novyj-uchebnyj-god-2026",
    "title": "Открыт набор на новый учебный год 2026/27",
    "description": "Фоксинбург открывает набор в группы на новый учебный год: английский, немецкий и китайский для детей от 2 лет, подростков и взрослых. Как формируются группы и почему места ограничены.",
    "category": "Набор",
    "date": "2026-08-12",
    "reading_time": "6 минут чтения",
    "hero_grad": "linear-gradient(135deg,#241a36 0%,#662d92 55%,#9d5fc9 100%)",
    "body": [
        ("p", "До начала учебного года осталось совсем немного, и мы открываем набор в группы на 2026/27 учебный год. Сейчас — самое спокойное время для выбора: можно без спешки пройти диагностику, познакомиться с педагогом и попасть именно в ту группу, которая подходит ребёнку по возрасту, уровню и расписанию."),
        ("h2", "Какие направления открыты"),
        ("ul", [
            "<b>Английский для малышей 2–3 лет</b> — мягкое погружение в язык через игру, песни и движение.",
            "<b>Английский для дошкольников 4–6 лет</b> — игровой формат, первые фразы и фоника без зубрёжки.",
            "<b>Подготовка к школе 5–7 лет</b> — два занятия в неделю по 60 минут, полная подготовка к первому классу.",
            "<b>Английский для младших школьников 7–11 лет</b> — программа My Level, в абонемент входит разговорный клуб с носителем языка.",
            "<b>Английский для подростков 12–16 лет</b> — программа Get Involved, академический английский и подготовка к ОГЭ/ЕГЭ.",
            "<b>Немецкий и китайский</b> — второй язык по той же методике: живое общение и мини-группы.",
            "<b>Онлайн-занятия</b> — тот же формат мини-групп для тех, кому удобнее заниматься из дома.",
            "<b>Индивидуальные занятия</b> — персональная программа под конкретную цель и график семьи.",
        ]),
        ("h2", "Как формируются группы"),
        ("p", "Мы не собираем группы «по остаточному принципу». Каждый ребёнок перед зачислением проходит бесплатную диагностику: методист определяет уровень, смотрит, как ребёнок реагирует на язык, и только после этого предлагает группу. Группы маленькие — 6–8 человек, — поэтому педагог видит каждого, а дети не теряются. Именно поэтому места в группах ограничены: когда группа набрана, мы не «досаживаем» в неё десятого ребёнка, а открываем следующую."),
        ("h2", "Почему записываться лучше в августе"),
        ("p", "В сентябре всегда ажиотаж: одновременно возвращаются «наши» ученики и приходят новые семьи, и самые удобные по времени группы закрываются первыми. В августе выбор заметно шире — и по времени, и по педагогам, и по филиалам. Плюс остаётся время спокойно решить организационные вопросы: учебники, расписание, дорога."),
        ("h2", "С чего начать"),
        ("p", "Первый шаг одинаковый для всех программ: оставьте заявку на сайте или напишите нам в Max — мы перезвоним, ответим на вопросы и запишем ребёнка на бесплатную диагностику. После неё вы точно будете знать уровень ребёнка и увидите, как проходят занятия, ещё до начала учебного года. Если планируете подключать второй язык — <a href=\"/nemeckij-yazyk\">немецкий</a> или <a href=\"/kitajskij-yazyk\">китайский</a>, — диагностика поможет понять, как совместить его с английским без перегрузки."),
        ("p", "Подробности о форматах записи на английский, немецкий и китайский мы собрали в статье про <a href=\"/novosti-zapis-na-novyj-uchebnyj-god-anglijskij-nemeckij-kitajskij\">запись на новый учебный год</a>, а о том, как проверить уровень ребёнка дома, — в материале «<a href=\"/novosti-kak-ponyat-uroven-rebenka-pered-uchebnym-godom\">Как понять реальный уровень английского</a>»."),
    ],
    "related": [
        ("Английский для дошкольников", "/doshkolniki"),
        ("Английский для младших школьников", "/mladshie-shkolniki"),
        ("Английский для подростков", "/podrostki"),
        ("Новости и статьи", "/novosti"),
    ],
    "faq": [
        ("Какие направления открыты на 2026/27 год?", "Английский для дошкольников, младших школьников, подростков и взрослых; немецкий и китайский; подготовка к школе, ОГЭ и ЕГЭ; индивидуальные занятия — очно в двух филиалах и онлайн."),
        ("Есть ли скидки или льготы?", "Занятия можно оплатить материнским капиталом, а часть стоимости вернуть социальным налоговым вычетом 13% — школа работает по образовательной лицензии."),
        ("Как попасть в группу?", "Записывайтесь на бесплатную диагностику: определим уровень, подберём группу по возрасту и расписанию. Старт групп — конец августа – начало сентября."),
    ],
}

NEWS_POST_13 = {
    "type": "article",
    "alias": "novosti-kak-vybrat-programmu-anglijskogo-dlya-rebenka",
    "title": "Как выбрать программу английского для ребёнка: спокойный гид для родителей",
    "description": "Возраст, уровень, цели и формат — из чего на самом деле складывается правильный выбор программы английского и почему «самая сильная» программа не всегда лучшая для вашего ребёнка.",
    "category": "Полезное для родителей",
    "date": "2026-08-14",
    "reading_time": "8 минут чтения",
    "hero_grad": "linear-gradient(135deg,#241a36 0%,#4a2a7a 55%,#c24712 100%)",
    "body": [
        ("p", "Перед учебным годом родители заваливают себя одним и тем же вопросом: какую программу выбрать, чтобы и результат был, и ребёнок не возненавидел английский к октябрю. Хорошая новость: выбор проще, чем кажется, если идти не от рекламных обещаний, а от четырёх понятных вещей — возраста, уровня, цели и формата. Разберём каждый."),
        ("h2", "Шаг 1. Возраст определяет подачу, а не «сложность»"),
        ("p", "Главная ошибка — думать, что программы отличаются только объёмом материала. На самом деле возраст определяет, как ребёнок вообще способен учить язык. Малышам 2–3 лет нужен только живой контакт: песни, движение, игра — никаких правил и букв. Дошкольникам 4–6 лет уже доступна фоника и первые фразы, но всё ещё через игру. Младшие школьники 7–11 лет способны на систему: чтение, письмо, грамматика в мягкой подаче. Подросткам 12–16 лет важны смысл и уважение: дискуссии, проекты, реальные темы, а не «детские» картинки. Программа, которая идеальна для десятилетнего, физически не подойдёт пятилетке — и наоборот."),
        ("h2", "Шаг 2. Честно определите уровень"),
        ("p", "«Занимался в школе» и «знает алфавит» — не уровень. Уровень — это то, что ребёнок реально умеет: понимает ли на слух новые формулировки, может ли ответить не заученной фразой, читает ли простые тексты. Мы уже подробно разбирали, как проверить это дома за 15–20 минут, в статье «<a href=\"/novosti-kak-ponyat-uroven-rebenka-pered-uchebnym-godom\">Как понять реальный уровень английского у ребёнка</a>». Если коротко: ребёнок, попавший в слишком слабую группу, скучает, а в слишком сильную — тревожится и молчит. Оба варианта гасят интерес, поэтому точность здесь важнее амбиций."),
        ("h2", "Шаг 3. Сформулируйте цель одним предложением"),
        ("p", "«Хочу, чтобы знал английский» — не цель, а пожелание. Цель звучит иначе: «не бояться говорить», «подтянуть школьную программу и оценки», «сдать ОГЭ на высокий балл», «свободно читать», «подготовиться к переезду». От цели зависит почти всё: интенсивность, формат, выбор между группой и индивидуальными занятиями. Для разговорного навыка и мотивации лучше работают мини-группы — там есть живое общение со сверстниками. Для экзамена с дедлайном или точечного пробела эффективнее индивидуальный формат — мы разбирали это в статье «<a href=\"/novosti-komu-nuzhen-repetitor-po-anglijskomu-5-priznakov\">Кому на самом деле нужен репетитор</a>»."),
        ("h2", "Шаг 4. Выберите формат, который выдержит ваша семья"),
        ("p", "Лучшая программа — та, на которую ребёнок ходит стабильно. Реалистично оцените логистику: дорога до филиала, расписание секций, нагрузка в школе. Два занятия в неделю по 60 минут, которые вы выдерживаете весь год, дают больше, чем четыре занятия, которые сорвутся к ноябрю. Если с дорогой туго — смотрите на <a href=\"/online-zanyatiya\">онлайн-формат</a>: в мини-группах он сохраняет главное — живое общение и внимание педагога."),
        ("h2", "На что смотреть в самой программе"),
        ("ul", [
            "<b>Методика.</b> Коммуникативный подход и погружение работают заметно лучше зубрёжки правил — ребёнок должен говорить на занятии, а не только слушать.",
            "<b>Размер группы.</b> Больше 8 человек — и внимания на каждого уже физически не хватает.",
            "<b>Прозрачность.</b> Понятная программа по темам, отчёты о прогрессе, возможность посмотреть урок — у нас, например, есть ежемесячные отчёты и открытые уроки.",
            "<b>Педагог.</b> Программу всегда важнее человека, который её ведёт: знакомство с педагогом до старта — нормальная и правильная практика.",
        ]),
        ("h2", "Как это устроено у нас"),
        ("p", "В Фоксинбурге программа подбирается не «по возрасту из таблицы», а по результату бесплатной диагностики: методист смотрит уровень, характер и цель, а затем предлагает конкретную группу — <a href=\"/doshkolniki\">дошкольникам</a>, <a href=\"/mladshie-shkolniki\">младшим школьникам</a> или <a href=\"/podrostki\">подросткам</a>. Если сомневаетесь между двумя вариантами — это нормально: именно для этого и нужна диагностика, чтобы выбирать по факту, а не гадать. Записаться можно через <a href=\"/novosti-otkryt-nabor-na-novyj-uchebnyj-god-2026\">набор на новый учебный год</a> — он уже открыт."),
    ],
    "related": [
        ("Набор на новый учебный год", "/novosti-otkryt-nabor-na-novyj-uchebnyj-god-2026"),
        ("Как понять уровень ребёнка", "/novosti-kak-ponyat-uroven-rebenka-pered-uchebnym-godom"),
        ("Цены и форматы", "/tseny"),
        ("Новости и статьи", "/novosti"),
    ],
    "faq": [
        ("Как выбрать программу по возрасту?", "2–6 лет — игровые группы для дошкольников; 7–10 — младшие школьники (все аспекты языка); 11–16 — подростки (язык для жизни и экзаменов). Дальше — курс для взрослых."),
        ("А если ребёнок «не по возрасту» силён или наоборот?", "Уровень важнее возраста: на диагностике определим реальную базу и предложим группу, где будет интересно и посильно. Иногда это соседняя возрастная группа."),
        ("Можно ли поменять программу в середине года?", "Да. Если темп группы не подходит — переведём в другую: бывает, что ребёнок «вырастает» из группы за полгода. Это нормально и бесплатно."),
    ],
}

NEWS_POST_14 = {
    "type": "article",
    "alias": "novosti-podgotovka-k-novomu-uchebnomu-godu-anglijskij",
    "title": "Подготовка к новому учебному году: как вернуть английский после каникул",
    "description": "Когда начинать готовиться к сентябрю, как мягко восстановить английскую практику после лета и почему не стоит ждать первого звонка до последнего момента.",
    "category": "Полезное для родителей",
    "date": "2026-08-16",
    "reading_time": "7 минут чтения",
    "hero_grad": "linear-gradient(135deg,#1e1433 0%,#2bb673 55%,#fcf951 100%)",
    "body": [
        ("p", "До сентября осталось пара недель — самое время спокойно, без авралов, подготовить ребёнка к новому учебному году. Речь не о том, чтобы «сесть за учебники» в августе: английский возвращается гораздо легче, чем кажется, если подойти к этому чуть-чуть заранее и без давления."),
        ("h2", "Когда начинать: ответ «уже сейчас, но понемногу»"),
        ("p", "Не нужно ждать первого сентября, чтобы «включить» английский, — но и устраивать интенсив в последнюю неделю лета не стоит. Оптимально — 10–15 минут лёгкого контакта с языком каждый день за пару недель до старта. Как мы писали в статье про <a href=\"/novosti-anglijskij-letom-kak-ne-poteryat-navyk\">английский летом</a>, знания за каникулы не исчезают — «засыпает» только беглость. А просыпается она быстро: у большинства детей скорость речи и подбор слов возвращаются за первую-вторую неделю регулярных занятий."),
        ("h2", "Как восстановить практику без слёз"),
        ("ul", [
            "Включите привычное: любимый мультфильм или песню на английском — то, что ребёнок уже знает и любит. Узнавание даёт ощущение «я это понимаю» и возвращает уверенность.",
            "Говорите понемногу вслух: пересказать день тремя фразами, назвать предметы на прогулке, вспомнить любимую игру с занятий.",
            "Достаньте материалы прошлого года: полистать учебник, перечитать пару страниц, пройтись по карточкам — память включится сама, без повторения «как в школе».",
            "Не устраивайте проверок: цель августа — не экзамен, а напомнить мозгу, что английский существует и это приятно.",
        ]),
        ("h2", "Психологическая подготовка важнее академической"),
        ("p", "Для ребёнка сентябрь — это стресс сам по себе: новый класс, новый ритм, иногда новая школа. Если английский добавляется в этот список как «ещё одна нагрузка», сопротивление почти гарантировано. Поэтому полезно заранее создать положительное ожидание: рассказать, кто будет педагогом, что группа останется той же (или, наоборот, что будет новая и интересная), вспомнить, что нравилось на занятиях. Знакомство с педагогом и кабинетом до первого занятия снимает большую часть волнения — особенно у дошкольников и младших школьников."),
        ("h2", "Выберите формат до сентября, а не после"),
        ("p", "Типичная ситуация: семья ждёт начала учёбы, смотрит, как сложится школьное расписание, и только потом ищет занятия — а удобные группы к этому моменту уже набраны. Гораздо спокойнее определиться в августе: пройти диагностику, выбрать дни и время, при необходимости рассмотреть <a href=\"/online-zanyatiya\">онлайн-формат</a>, если логистика плотная. Тогда сентябрь начинается без лишней беготни — ребёнок просто приходит в свою группу."),
        ("h2", "Что мы предлагаем перед стартом"),
        ("p", "В конце августа у нас проходит <a href=\"/tseny\">интенсив «Вспомнить всё по школьному английскому»</a> — мягкий способ вернуть язык в рабочее состояние перед годом. А для тех, кто только присматривается, работает бесплатная диагностика: за одну встречу методист определит уровень и подберёт группу, и к сентябрю у вас будет готовый план, а не список вопросов. Набор на новый учебный год <a href=\"/novosti-otkryt-nabor-na-novyj-uchebnyj-god-2026\">уже открыт</a> — самые удобные по времени группы, как обычно, закрываются первыми."),
    ],
    "related": [
        ("Английский летом: как не растерять навык", "/novosti-anglijskij-letom-kak-ne-poteryat-navyk"),
        ("Набор на новый учебный год", "/novosti-otkryt-nabor-na-novyj-uchebnyj-god-2026"),
        ("Онлайн-занятия", "/online-zanyatiya"),
        ("Новости и статьи", "/novosti"),
    ],
    "faq": [
        ("Когда начинать подготовку к учебному году?", "Идеально — за 3–4 недели до 1 сентября: короткие регулярные занятия, чтобы «разбудить» язык после лета, повторить базу и войти в ритм без стресса."),
        ("Что повторять в первую очередь?", "Словарь пройденных тем и базовые грамматические конструкции — именно они «засыпают» за лето. Чтение вслух и короткие диалоги возвращают беглость быстрее всего."),
        ("Есть ли у вас интенсив перед школой?", "Да, в конце августа — интенсив «Вспомнить всё по школьному английскому»: компактный курс повторения перед стартом учебного года."),
    ],
}

NEWS_POST_15 = {
    "type": "article",
    "alias": "novosti-start-novogo-uchebnogo-goda-2026",
    "title": "Старт нового учебного года в Фоксинбурге",
    "description": "Занятия нового учебного года начинаются совсем скоро: как пройдёт знакомство с педагогом, определение уровня и первые недели — и что успеть сделать до старта.",
    "category": "Новости школы",
    "date": "2026-08-18",
    "reading_time": "6 минут чтения",
    "hero_grad": "linear-gradient(135deg,#2e1a47 0%,#c24712 55%,#9d5fc9 100%)",
    "body": [
        ("p", "Новый учебный год в Фоксинбурге стартует совсем скоро — группы уже формируются, педагоги готовят программы, а мы финализируем расписание. Рассказываем, как всё будет устроено, чтобы и дети, и родители пришли на первое занятие спокойными и подготовленными."),
        ("h2", "Знакомство с педагогом — до первого урока"),
        ("p", "Мы уверены: язык учится через отношения, а не через учебник. Поэтому до старта занятий каждая семья знакомится с педагогом своей группы — на диагностике или пробном занятии. Ребёнок приходит в сентябре не «в неизвестность», а к человеку, которого уже видел, — и это снимает львиную долю волнения первых недель. Родители при этом могут задать педагогу любые вопросы: про программу, домашние задания, отчёты о прогрессе."),
        ("h2", "Определение уровня — без экзаменационного стресса"),
        ("p", "Перед зачислением в группу каждый ребёнок проходит бесплатную диагностику. Это не тест с оценками, а спокойная встреча: методист в игровой форме смотрит, что ребёнок понимает, что умеет сказать и как ведёт себя с языком. По итогам мы предлагаем конкретную группу по возрасту и уровню — так, чтобы рядом были «свои» по темпу дети. Если ребёнок занимался раньше, диагностика покажет, где он сейчас; если никогда не занимался — определим мягкую точку входа."),
        ("h2", "Как пройдут первые недели"),
        ("p", "Первые занятия сентября — про адаптацию, а не про объём. Дети знакомятся между собой, вспоминают язык после лета, входят в ритм «два раза в неделю». Педагоги намеренно не перегружают старт: интерес и ощущение «у меня получается» в первые недели важнее любых параграфов. Родители сразу начинают получать обратную связь: как ребёнок включился, что получается, над чем будем работать."),
        ("h2", "Что успеть до старта"),
        ("ul", [
            "Пройти бесплатную диагностику и подтвердить место в группе — набор идёт, удобное время разбирают первым.",
            "Выбрать расписание: дни и время занятий, удобные именно вашей семье.",
            "Решить вопрос с форматом: офлайн в филиале или <a href=\"/online-zanyatiya\">онлайн</a> — содержание программы одинаковое.",
            "Показать ребёнку, где будет проходить занятие, и познакомить с педагогом — первое сентября станет заметно спокойнее.",
        ]),
        ("h2", "Если вы ещё не с нами"),
        ("p", "Набор на новый учебный год продолжается: английский для детей от 2 лет, школьников и подростков, <a href=\"/nemeckij-yazyk\">немецкий</a> и <a href=\"/kitajskij-yazyk\">китайский</a>, <a href=\"/preparation\">подготовка к школе</a> и индивидуальные занятия. Оставьте заявку на сайте или напишите в Max — расскажем расписание, ответим на вопросы и запишем на диагностику. Подробности — в анонсе «<a href=\"/novosti-otkryt-nabor-na-novyj-uchebnyj-god-2026\">Открыт набор на новый учебный год</a>». До встречи на занятиях!"),
    ],
    "related": [
        ("Набор на новый учебный год", "/novosti-otkryt-nabor-na-novyj-uchebnyj-god-2026"),
        ("Подготовка к учебному году", "/novosti-podgotovka-k-novomu-uchebnomu-godu-anglijskij"),
        ("Цены и форматы", "/tseny"),
        ("Новости и статьи", "/novosti"),
    ],
    "faq": [
        ("Когда стартует новый учебный год в Фоксинбурге?", "Группы начинают работать с конца августа — начала сентября. Расписание собирается заранее, поэтому диагностику лучше пройти в августе."),
        ("Что изменится в новом году?", "Обновляем программы и материалы, открываем новые группы по возрастам и уровням, продолжаем ежемесячные отчёты родителям и мотивационную систему с наградами."),
        ("Как записаться?", "Оставьте заявку на сайте или позвоните — пригласим на бесплатную диагностику, покажем филиал и предложим расписание. Можно сразу задать вопросы в Max."),
    ],
}

# ---------------------------------------------------------------- Блог /blog
# Отдельный evergreen-хаб (см. SEO_CONTENT_MAP.md, раздел 3.1): рубрики
# «Родителям», «Учим английский», «Экзамены», «Школа и учёба». Статьи живут
# на алиасах /blog-* и НЕ переезжают из /novosti — это новые тексты.
BLOG_FEED = {"feed_alias": "blog", "feed_label": "Блог"}

BLOG_POST_1 = dict(BLOG_FEED, **{
    "type": "article",
    "alias": "blog-anglijskij-dlya-detej-3-4-goda",
    "title": "Английский для детей 3–4 лет: что реально работает",
    "description": "Что реально работает в английском для детей 3–4 лет: песни, игра, движение. Как не перегрузить малыша и заложить базу без зубрёжки и давления.",
    "category": "Родителям",
    "date": "2026-08-01",
    "reading_time": "8 минут чтения",
    "hero_grad": "linear-gradient(135deg,#2e1a47 0%,#662d92 55%,#8a4fb8 100%)",
    "body": [
        ("h2", "Что ребёнок 3–4 лет действительно может в английском"),
        ("p", "Главная ошибка ожиданий в этом возрасте — ждать от малыша «учебного» результата: чтения, письма, правил, длинных фраз. Реальная цель английского в 3–4 года другая: ребёнок привыкает к звучанию языка, узнаёт слова на слух, реагирует на простые инструкции и повторяет короткие слова и рифмовки. Это фундамент, на котором потом легко строится всё остальное — и он закладывается именно через игру, а не через урок в школьном смысле."),
        ("p", "Хороший ориентир результата для этого возраста выглядит так: малыш показывает названный предмет, выполняет команду вроде «Give me the ball», подпевает знакомую песенку, называет несколько цветов и животных — и, главное, делает это с удовольствием, без слёз и уговоров. Если это есть, английский уже «работает», даже если ребёнок ещё не говорит фразами."),
        ("h2", "Какие форматы работают в 3–4 года"),
        ("ul", [
            "<b>Песни и рифмовки.</b> Ритм и повтор — главный механизм запоминания в этом возрасте: слова из песенок удерживаются годами.",
            "<b>Команды с движением.</b> «Jump!», «Clap your hands», «Touch your nose» — ребёнок связывает слово с действием, и перевод ему просто не нужен.",
            "<b>Предметы и карточки.</b> Слово всегда привязано к тому, что можно потрогать, показать или спрятать.",
            "<b>Короткие занятия 20–30 минут.</b> Дольше малыш в этом возрасте удерживает внимание только на том, что очень нравится.",
            "<b>Постоянная смена активности.</b> За одно занятие — 5–7 коротких эпизодов: песня, игра, карточки, движение, снова песня.",
        ]),
        ("h2", "Что в этом возрасте не работает"),
        ("p", "Симметрично важно понимать, чего делать не стоит — большинство неудач с ранним английским связаны не с ребёнком, а с форматом:"),
        ("ul", [
            "объяснения правил и грамматики — малышу нужна практика через повторение, а не теория;",
            "заучивание алфавита — буквы без звуков и слов в этом возрасте не имеют смысла и быстро забываются;",
            "уроки по 45–60 минут за партой — внимание ребёнка 3–4 лет физиологически короче;",
            "давление «скажи правильно» — страх ошибки в 4 года гасит интерес к языку на месяцы вперёд;",
            "редкие длинные занятия — три раза в неделю по 10 минут дома дают больше, чем час раз в неделю «наотмашь».",
        ]),
        ("h2", "Как понять, что занятия идут в плюс"),
        ("p", "Прогресс в 3–4 года почти никогда не выглядит как «выучил тему». Смотрите на другое: ребёнок сам напевает английскую песенку в машине, вставляет английское слово в русскую фразу («мама, где my ball?»), с готовностью бежит на занятие и не пугается английской речи в мультфильме. Смешивание языков в одном предложении — не проблема, а нормальный этап: так мозг учится держать две системы одновременно."),
        ("p", "Тревожный сигнал выглядит иначе: ребёнок систематически отказывается, плачет перед занятием, замирает при английской речи. Это почти всегда признак неподходящего формата или темпа, а не «нет способностей». Способности к языкам в этом возрасте есть практически у всех детей — вопрос только в подаче."),
        ("h3", "Как проходит первое занятие"),
        ("p", "Первый контакт решает многое, поэтому пробное занятие у нас строится максимально мягко: малыш просто включается в игру вместе с группой — никаких «проверок» и вопросов в лоб. Педагог в это время смотрит на главное: как ребёнок реагирует на английскую речь, включается ли в общую активность, сколько удерживает внимание. После занятия мы честно рассказываем родителям, что увидели, и предлагаем формат — группу сейчас, более мягкий старт или паузу на полгода. Решение всегда за вами, наша задача — дать реалистичную картину."),
        ("h2", "Как мы занимаемся с малышами в Фоксинбурге"),
        ("p", "В нашей программе <a href=\"/doshkolniki\">английского для дошкольников</a> (линейка BABY — для самых маленьких) занятие построено именно по этим принципам: игра, движение, песни и короткие сюжетные задания, мини-группы, в которых педагог видит каждого ребёнка. Никакой зубрёжки и «уроков за партой» — задача этого возраста, чтобы английский стал для малыша привычной и приятной частью жизни. О том, когда вообще стоит начинать, мы подробно писали в статье «<a href=\"/novosti-so-skolki-let-uchit-anglijskij\">Со скольки лет учить английский ребёнку</a>»."),
        ("p", "Перед стартом мы приглашаем на бесплатную диагностику: педагог в игровой форме посмотрит, как малыш реагирует на английскую речь, и честно скажет, готов ли он к группе или стоит подождать полгода. Это снимает главный родительский риск — записаться «на авось»."),
        ("h2", "Частые вопросы родителей трёхлеток"),
        ("p", "<b>«Не помешает ли английский русской речи?»</b> Нет: в этом возрасте языки развиваются параллельно, и контакт со вторым языком в разумном объёме (2–3 коротких занятия в неделю) не замедляет родной. Если у ребёнка есть логопедические особенности, скажите об этом педагогу на диагностике — формат подберём бережнее."),
        ("p", "<b>«Мы сами не знаем английского — сможем ли помогать?»</b> Сможете, и помощь нужна самая простая: включать песенку, хвалить за повторённое слово, играть в «покажи, где cat». Ваш английский в этом возрасте ребёнку почти не нужен — нужны ваш интерес и регулярность."),
        ("p", "<b>«А если малыш стесняется в группе?»</b> Для многих трёхлеток первая мини-группа — вообще первый социальный опыт. Это нормально: педагоги дают время на адаптацию, обычно 2–4 занятия, и не требуют от новичка активности. Стеснительные дети часто оказываются самыми внимательными слушателями — и потом выдают больше всех."),
        ("h3", "Что можно делать дома уже сейчас"),
        ("ul", [
            "одна английская песенка «на постоянке» — в машине, за завтраком, перед сном;",
            "простые команды в игру: «Give me…», «Put it on…», «Jump!» — весело и без перевода;",
            "карточки или книжки с картинками: называете по-английски — малыш показывает;",
            "короткие мультфильмы на английском по 5–10 минут, лучше уже знакомые по-русски;",
            "главное правило: заканчивать раньше, чем надоест, — пусть просит ещё.",
        ]),
    ],
    "related": [
        ("Английский для дошкольников", "/doshkolniki"),
        ("Со скольки лет учить английский", "/novosti-so-skolki-let-uchit-anglijskij"),
        ("Все статьи блога", "/blog"),
    ],
    "faq": [
        ("Правда, что в 3–4 года уже можно начинать английский?", "Да, если формат игровой: песенки, карточки, короткие команды, движение. Никакой зубрёжки и «сиди за партой» — в этом возрасте язык усваивается через игру и повторение."),
        ("Не будет ли мешать английский русской речи?", "Нет. В дошкольном возрасте дети легко разделяют языки, если каждый из них живёт в своём контексте. Русский остаётся основным дома и в саду, английский приходит дозированно — 5–15 минут в день дома и занятия 2 раза в неделю."),
        ("Что должен уметь ребёнок к 4 годам на английском?", "Ничего не «должен». Хороший ориентир: узнаёт знакомые слова, откликается на простые команды, подпевает песенки, может назвать несколько слов-картинок. Это фундамент, а не экзамен."),
        ("Сколько должны длиться домашние занятия с малышом?", "5–15 минут в день, и заканчивать раньше, чем надоест. Короткие ежедневные контакты с языком работают лучше, чем один длинный урок раз в неделю."),
    ],
})

BLOG_POST_2 = dict(BLOG_FEED, **{
    "type": "article",
    "alias": "blog-kak-nauchit-rebenka-chitat-po-anglijski",
    "title": "Как научить ребёнка читать по-английски: phonics для родителей",
    "description": "Phonics простыми словами: как научить ребёнка читать по-английски без зубрёжки. Звуки, слияние букв, домашние шаги и типичные ошибки родителей.",
    "category": "Учим английский",
    "date": "2026-08-03",
    "reading_time": "9 минут чтения",
    "hero_grad": "linear-gradient(135deg,#241a36 0%,#5a2d8f 55%,#8a4fb8 100%)",
    "body": [
        ("h2", "Почему «выучить буквы» — тупиковый путь"),
        ("p", "Русское чтение почти фонетическое: как пишется, примерно так и читается. С английским это не работает: одна и та же буква читается по-разному (сравните cat, cake, car), а одинаковые звуки пишутся разными буквами. Поэтому ребёнок, который вызубрил алфавит «эй-би-си», в тексте всё равно не может прочитать слово cat — он знает названия букв, но не знает их звуки. Именно эту задачу решает подход phonics."),
        ("p", "Phonics — это метод, при котором ребёнок учит не названия букв, а звуки, которые они обозначают, и учится сливать эти звуки в слова: /k/–/æ/–/t/ → cat. Так английский читают дети в англоязычных странах, и так же эффективно это работает для русскоязычных детей."),
        ("h2", "Ключевые звуки, с которых начинают"),
        ("html", "<table><tr><th>Буквы</th><th>Звук</th><th>Пример</th></tr>"
               "<tr><td>c, a, t</td><td>/k/, /æ/, /t/</td><td>cat — сливаем три звука в слово</td></tr>"
               "<tr><td>sh</td><td>/ʃ/</td><td>ship — две буквы, один звук</td></tr>"
               "<tr><td>th</td><td>/θ/ или /ð/</td><td>three, this — звука нет в русском, тренируем отдельно</td></tr>"
               "<tr><td>ee, ea</td><td>/i:/</td><td>see, sea — одинаково звучат, пишутся по-разному</td></tr>"
               "<tr><td>a + «немая e»</td><td>/eɪ/</td><td>cake — финальная e меняет чтение гласной</td></tr></table>"),
        ("p", "Порядок важен: сначала самые частые и однозначные звуки (s, a, t, p, i, n), на которых уже можно собрать десятки слов, и только потом — сложные комбинации вроде th или «немой e». Ребёнок почти сразу начинает читать настоящие слова, и это мощно поддерживает мотивацию."),
        ("h2", "Четыре шага, которые можно делать дома"),
        ("ul", [
            "<b>Звуки, а не буквы.</b> Называйте ребёнку звук: «буква s говорит /с/», — а не «это буква эс».",
            "<b>Слияние на пальцах.</b> Разбивайте слово на звуки и «собирайте» обратно: /d/–/o/–/g/ — что получилось? Dog!",
            "<b>Поиск звука вокруг.</b> Игра «найди дома три предмета на звук /б/» — ball, book, box.",
            "<b>Простые книги для начинающих.</b> Специальные phonics-ридеры, где 90% слов читаются по уже изученным правилам, — ребёнок читает книгу сам и гордится.",
        ]),
        ("h2", "Типичные ошибки родителей"),
        ("ul", [
            "Учить алфавит песенкой и считать это «чтением» — названия букв не помогают прочитать слово.",
            "Торопиться с правилами исключений, пока не закреплены базовые звуки.",
            "Исправлять каждую ошибку чтения вслух — лучше дать дочитать и вернуться к сложному слову один раз, спокойно.",
            "Читать «за ребёнка» сложные слова молча — лучше подсказать звук и дать слить слово самостоятельно.",
        ]),
        ("h2", "Как phonics соотносится со школьной программой"),
        ("p", "В российской начальной школе английское чтение часто вводят через заучивание слов целиком и алфавит — отсюда знакомая картина: ребёнок «выучил» слова к уроку, а в новом тексте не может прочитать ни одного. Phonics не противоречит школьной программе, а дополняет её: ребёнок с навыком слияния звуков читает школьные тексты самостоятельно, а не по памяти. Родители замечают это быстро — домашнее чтение перестаёт быть битвой."),
        ("h2", "Сколько времени занимает путь от звуков к чтению"),
        ("p", "При регулярных занятиях (два раза в неделю плюс 10 минут дома) типичная траектория выглядит так:"),
        ("ul", [
            "<b>1–2 месяц:</b> базовые звуки, слияние простых слов из трёх букв (cat, dog, sun) — ребёнок читает первые слова сам;",
            "<b>3–4 месяц:</b> буквосочетания (sh, ch, th, ee), простые предложения, первые phonics-книжки;",
            "<b>5–6 месяц:</b> «немая e», длинные гласные, короткие тексты на 3–5 предложений;",
            "<b>дальше:</b> рост скорости и объёма — переход от «учусь читать» к «читаю, чтобы узнать».",
        ]),
        ("p", "Эти этапы условны: дошкольник и третьеклассник пройдут их с разной скоростью. Но порядок неизменен — и если ребёнок «застрял», причина почти всегда в том, что один из ранних этапов проскочили. Вернуться на ступень назад — не стыдно, а эффективно: неделю повторяем базовые звуки, и сложные слова вдруг начинают складываться сами."),
        ("p", "Сроки зависят от возраста и стартовой точки, но принцип один: сначала точность, потом скорость. Торопить ребёнка на этапе слияния — значит заложить привычку угадывать вместо чтения. И ещё один практический приём: делайте прогресс видимым — полочка «прочитанных сам» книжек или список освоенных звуков на холодильнике работают на мотивацию сильнее похвал. Ребёнок, который видит, как растёт его личный запас, берёт следующую книгу сам, без уговоров."),
        ("h2", "Частые вопросы родителей про phonics"),
        ("p", "<b>«А когда учить сам алфавит — названия букв?»</b> Названия букв нужны, но позже и для другой задачи: продиктовать фамилию по буквам, найти слово в словаре, разобраться с написанием. Их вводят после того, как звуки закрепились, — тогда ребёнок не путает «буква» и «звук», потому что чтение уже работает."),
        ("p", "<b>«Подойдёт ли phonics ребёнку 8–10 лет, который уже «читает», но угадывает?»</b> Да, и это один из самых благодарных случаев: словарь уже есть, остаётся научить его распаковывать слова по звукам. У школьников переучивание занимает обычно 2–4 месяца, после чего скорость и точность чтения заметно растут — и вместе с ними оценки, потому что перестаёт пугать незнакомый текст."),
        ("p", "<b>«Можно ли освоить phonics только дома?»</b> Базу — да, если у кого-то из взрослых приличное произношение и есть регулярность. Сложность в том, что родитель часто сам передаёт русскоязычное звучание (например, th как «з» или «с»), и ребёнок закрепляет ошибку. Оптимально: системные занятия с педагогом плюс домашняя практика по его заданиям — так домашние 10 минут работают на программу, а не против неё."),
        ("h2", "Как мы учим читать в Фоксинбурге"),
        ("p", "Чтение по системе phonics — отдельное направление в нашей школе: на курсе <a href=\"/reading\">английского чтения</a> дети проходят путь от звуков к уверенному чтению коротких текстов, а в программе для <a href=\"/mladshie-shkolniki\">младших школьников</a> чтение закрепляется вместе с говорением и письмом. Если ребёнок во 2–3 классе до сих пор читает по-английски «по буквам» и гадает — это как раз тот случай, когда несколько месяцев системной работы меняют картину полностью. Приходите на бесплатную диагностику — покажем, с какого звука начать."),
    ],
    "related": [
        ("Курс английского чтения", "/reading"),
        ("Английский для младших школьников", "/mladshie-shkolniki"),
        ("Все статьи блога", "/blog"),
    ],
    "faq": [
        ("С какого возраста учить читать по-английски?", "Обычно с 5–7 лет, когда ребёнок уже умеет читать по-русски или хотя бы знает буквы. Начинают не с алфавита, а со звуков — это и есть подход phonics."),
        ("Что такое phonics простыми словами?", "Это метод, где ребёнок учит не названия букв («буква эй»), а звуки, которые они дают, и учится сливать их в слова: c-a-t → cat. Так чтение становится логичным, а не заучиванием тысяч слов наизусть."),
        ("Можно ли учить чтению дома без педагога?", "Первые шаги — да: звуки букв, простые трёхбуквенные слова, песенки phonics. Но правильное произношение и систему лучше закрепить с педагогом, чтобы не переучивать потом."),
        ("Какая главная ошибка родителей при обучении чтению?", "Учить алфавит по названиям букв и ждать, что ребёнок начнёт читать. Название буквы не помогает прочитать слово: «эй-бэй-си» не складывается в abc. Нужны звуки, а не названия."),
    ],
})

BLOG_POST_3 = dict(BLOG_FEED, **{
    "type": "article",
    "alias": "blog-rebenok-ne-ponimaet-anglijskij-v-shkole",
    "title": "Ребёнок не понимает английский в школе: план на 3 месяца",
    "description": "Ребёнок не понимает английский на уроках? Разбираем 4 причины и даём домашний план на 3 месяца: аудирование, фразы, перенос в школьные темы.",
    "category": "Школа и учёба",
    "date": "2026-08-05",
    "reading_time": "9 минут чтения",
    "hero_grad": "linear-gradient(135deg,#392852 0%,#6237a2 55%,#9d5fc9 100%)",
    "body": [
        ("h2", "Сначала разберитесь, что именно «не понимает»"),
        ("p", "Жалоба «не понимает английский» почти никогда не означает «не понимает ничего». Чаще за ней стоит одна из четырёх конкретных причин — и у каждой своё решение:"),
        ("ul", [
            "<b>Пробелы в базе.</b> Материал идёт нарастающим комом: не выучены слова 2 класса — не складываются фразы 3-го. Ребёнок сидит на уроке как на фильме без субтитров.",
            "<b>Не понимает речь на слух.</b> Текст в тетради читает, а учителя или аудиозапись — нет: слабое аудирование, самый частый случай.",
            "<b>Не понимает, что от него хотят в задании.</b> Слова знает, но инструкции «fill in», «match», «complete» не расшифрованы — паника от неизвестности.",
            "<b>Страх.</b> Понимает, но от страха ошибки отвечает «не знаю» — и со стороны выглядит как «не понимает».",
        ]),
        ("h2", "Домашняя проверка за 20 минут"),
        ("p", "Прежде чем что-то чинить, определите причину. Включите аудио из школьного учебника и попросите пересказать по-русски, о чём оно. Дайте прочитать тот же текст глазами — стало ли понятнее? Попросите выполнить типовое задание из рабочей тетради и понаблюдайте, на каком шаге ребёнок замирает. Если аудио «не идёт», а текст понятен — проблема в аудировании. Если не идёт и текст — в словарной базе. Если материал понятен, но задание «непонятное» — дело в инструкциях или страхе."),
        ("h2", "План на 3 месяца"),
        ("h3", "Месяц 1: открываем уши"),
        ("p", "Главная задача — привыкнуть к живому звучанию языка. Каждый день 10–15 минут: аудио из школьного учебника (следим глазами по тексту, потом слушаем без текста), короткие мультфильмы на уже знакомые темы. Никаких оценок и «что это слово значит?» каждые 30 секунд — задача месяца не понять каждое слово, а перестать бояться потока речи. Параллельно повторяем слова прошлых лет по 5–7 в день, карточками или в приложении."),
        ("h3", "Месяц 2: говорим короткими фразами"),
        ("p", "Когда слух «открылся», подключаем активное использование: пересказ аудио двумя-тремя фразами, ответы на простые вопросы по школьным темам, мини-диалоги с родителем («What did you do today?»). Фразы короткие, но каждый день. Ошибки в этом месяце не исправляем на лету — задача вернуть ребёнку смелость, а не идеальную грамматику."),
        ("h3", "Месяц 3: переносим в школьный контекст"),
        ("p", "Теперь связываем навык со школой: разбираем типовые инструкции заданий (подпишите перевод в тетрадь на полях), делаем домашку «на опережение» по параграфу, который пройдут на следующей неделе, — ребёнок приходит на урок уже знакомым с материалом и впервые за долгое время поднимает руку. Именно этот момент чаще всего становится переломным."),
        ("h2", "Чего делать не стоит"),
        ("ul", [
            "Сидеть над домашкой каждый вечер и злиться — ребёнок свяжет английский с конфликтом, и откат будет сильнее пробела.",
            "Зубрить слова списками «на отлично» к пятнице — без контекста они забываются к понедельнику.",
            "Сравнивать с одноклассниками — мотивацию это не добавляет никогда.",
            "Ждать, что «само рассосётся» — пробел в языке нарастает, как снежный ком, с каждой новой темой.",
        ]),
        ("h2", "Как разговаривать с ребёнком, пока идёт план"),
        ("p", "Три месяца работы легко свести на нет разговорами в духе «опять двойку получил?». Язык — не предмет с сегодняшней контрольной, а навык с длинным циклом. Помогают простые правила:"),
        ("ul", [
            "спрашивайте не «что получил?», а «что сегодня было интересного на английском?»;",
            "хвалите за процесс, а не за оценку: «ты сегодня прочитал целый абзац без подсказок»;",
            "разрешите ошибаться дома сколько угодно — дом — тренировочная площадка, а не экзамен;",
            "делитесь своими неудачами («я тоже забыл, как будет…») — это нормализует трудность;",
            "договоритесь с учителем: короткое письмо «работаем над аудированием, поддержите» меняет отношение к ребёнку на уроке.",
        ]),
        ("h2", "Как закрепить результат после трёх месяцев"),
        ("p", "План на 3 месяца — это перезапуск, а не финиш. Чтобы ребёнок не скатился обратно, нужны две вещи: сохранить ежедневный минимум контакта с языком (10–15 минут аудио или чтения — уже без вашего контроля, по привычке) и следить за точками риска: каникулы, смена учителя, переход в следующий класс. Именно после перерывов пробелы напоминают о себе сильнее всего. Хороший маркер устойчивости: ребёнок сам, без напоминаний, включает знакомый английский контент и не тушуется на уроках. Если это появилось — система заработала, дальше нужна только регулярность. О том, как не потерять навык на больших перерывах, у нас есть отдельный разбор «<a href=\"/novosti-anglijskij-letom-kak-ne-poteryat-navyk\">Английский летом</a>»."),
        ("p", "И последнее. Не сравнивайте ребёнка с ним же «до проблемы» каждую неделю — навык растёт скачками: неделю кажется, что ничего не меняется, потом вдруг выходит целый пласт. Отмечайте изменения раз в месяц, а не ежедневно: так вы увидите реальную динамику и не будете раздавать ложные тревоги ни себе, ни ребёнку. Если через месяц плана сдвигов нет совсем — это сигнал скорректировать причину (возможно, дело не в аудировании, а в базе), а не давить сильнее."),
        ("h2", "Когда нужна внешняя помощь"),
        ("p", "Домашний план работает, если пробел умеренный и у ребёнка сохранилась хоть какая-то мотивация. Если же материал отстаёт на год и больше, ребёнок демонстративно «ненавидит английский» или у родителей нет ресурса заниматься каждый день — эффективнее подключить педагога. В Фоксинбурге такие ситуации разбирают на программе для <a href=\"/mladshie-shkolniki\">младших школьников</a> в мини-группах, а при серьёзном отставании — на <a href=\"/repetitor-nachalnaya-shkola\">индивидуальных занятиях</a>, где педагог закрывает именно те пробелы, которые мешают вашему ребёнку."),
        ("p", "Если хотите понять, в какой точке ваш ребёнок прямо сейчас, — начните с бесплатной диагностики. Это не экзамен: педагог в спокойном формате проверит понимание на слух, чтение и говорение, а потом разложит для вас, что уже работает, где пробел и какой объём работы нужен, чтобы его закрыть. С такой картиной домашний план из этой статьи работает заметно точнее — вы будете знать, какой из трёх месяцев вашему ребёнку нужен первым."),
    ],
    "related": [
        ("Английский для младших школьников", "/mladshie-shkolniki"),
        ("Как понять уровень английского у ребёнка", "/novosti-kak-ponyat-uroven-rebenka-pered-uchebnym-godom"),
        ("Все статьи блога", "/blog"),
    ],
    "faq": [
        ("Ребёнок учит английский в школе, но ничего не понимает. Это нормально?", "Частая ситуация: школьная программа даёт материал большими блоками, и пробелы копятся незаметно. Ребёнок не «неспособный» — ему просто нужно вернуться к тому месту, где он потерял нить, и пройти его в своём темпе."),
        ("Как понять, что проблема именно в пробелах, а не в мотивации?", "Спросите, что проходили на прошлом уроке, и попросите объяснить простое правило или прочитать пару предложений из учебника. Если ребёнок теряется на материале, который «уже проходили», — это пробел в базе, а не лень."),
        ("Можно ли наверстать школьную программу за лето?", "Да, лето — лучшее время для этого: 2 занятия в неделю плюс короткие домашние повторения позволяют спокойно закрыть пробелы класса без гонки."),
        ("Группа или репетитор для отстающего?", "Если пробелы большие и ребёнок стесняется — начать индивидуально, чтобы быстро закрыть базу. Когда появится уверенность, можно перейти в мини-группу по уровню: там больше разговорной практики."),
    ],
})

BLOG_POST_4 = dict(BLOG_FEED, **{
    "type": "article",
    "alias": "blog-vpr-po-anglijskomu-4-klass",
    "title": "ВПР по английскому в 4 классе: что проверяют и как готовиться",
    "description": "Как устроена ВПР по английскому в 4 классе: разделы работы, что должен уметь четвероклассник и как готовиться без стресса и зубрёжки.",
    "category": "Экзамены",
    "date": "2026-08-07",
    "reading_time": "8 минут чтения",
    "hero_grad": "linear-gradient(135deg,#241a36 0%,#662d92 55%,#a05fd4 100%)",
    "body": [
        ("h2", "Что такое ВПР и чем она не является"),
        ("p", "ВПР — всероссийская проверочная работа, которую школы проводят для мониторинга качества обучения. По английскому языку в начальной школе её пишут в 4 классе — по решению школы. Главное, что нужно знать родителю: ВПР — не экзамен. Её результат не влияет на аттестат, не влияет на перевод в следующий класс и не является «вступительным испытанием» в среднюю школу. Это срез: школа и регион смотрят, как усвоена программа, а родители получают честную картину реального уровня ребёнка."),
        ("p", "Поэтому первая задача подготовки — убрать лишний страх. Ребёнок, который идёт на ВПР как на «страшный экзамен», показывает заметно ниже своего реального уровня. Правильная рамка: это проверка того, что ты уже умеешь, — и мы просто спокойно повторим пройденное."),
        ("h2", "Как устроена работа"),
        ("p", "Проверочная работа по английскому в 4 классе укладывается примерно в один урок и проверяет те же навыки, что формирует школьная программа:"),
        ("ul", [
            "<b>Аудирование</b> — прослушать короткий текст или диалог и ответить на вопросы / выбрать верное утверждение. Текст звучит два раза.",
            "<b>Чтение</b> — прочитать небольшой текст и выполнить задания на понимание: соотнести, выбрать, ответить.",
            "<b>Грамматика и лексика</b> — задания на знакомые по программе конструкции: формы глагола to be, Present Simple, множественное число, предлоги, слова основных тем.",
            "<b>Письмо</b> — короткое письменное задание: вставить слова, написать несколько предложений по образцу.",
        ]),
        ("p", "В отдельные годы в состав ВПР по английскому включали и устную часть (говорение). Точный состав работы и регламент лучше уточнить в своей школе — ВПР проводится по её решению, а демоверсии публикуются на официальном сайте ВПР."),
        ("h2", "Что должен уметь четвероклассник"),
        ("ul", [
            "понимать на слух короткие знакомые тексты — рассказы о семье, школе, животных, погоде, увлечениях;",
            "читать и понимать текст на 3–5 предложений без словаря;",
            "знать слова основных тем программы 2–4 классов и писать их без грубых ошибок;",
            "употреблять базовые конструкции: I can…, I like…, There is/are…, have got, простые вопросы и отрицания;",
            "написать несколько связных предложений о себе, семье или любимом герое.",
        ]),
        ("h2", "Как готовиться без стресса"),
        ("ul", [
            "<b>Решите демоверсию заранее.</b> Один спокойный прогон формата дома снимает 80% волнения: ребёнок идёт на знакомое задание, а не в неизвестность.",
            "<b>Тренируйте аудирование.</b> Это самый «хрупкий» навык: 10 минут аудио из учебника в день за 2–3 недели до работы заметно поднимают результат.",
            "<b>Повторяйте слова по темам, а не списками.</b> Семья, школа, животные, еда, погода — по 5–7 слов в день с картинками.",
            "<b>Научите проверять работу.</b> Простая привычка перечитать свои ответы перед сдачей спасает несколько баллов.",
            "<b>Не устраивайте «репетицию казни».</b> Одна-две тренировки в спокойном темпе лучше недели ежедневных пробников.",
        ]),
        ("h2", "Типичные ошибки детей на ВПР"),
        ("p", "По опыту педагогов чаще всего баллы теряются не на незнании, а на невнимательности: ребёнок не дослушал вопрос до конца, перепутал «верно/неверно» в задании на соответствие, забыл заглавную букву в начале предложения или не вписал ответ в бланк. Все эти ошибки — не про язык, а про навык работать с форматом, и они отлично тренируются."),
        ("h2", "Когда начинать готовиться"),
        ("p", "Специальная подготовка к ВПР не должна растягиваться на год — работа слишком короткая и форматная. Разумный ритм такой: в течение 4 класса просто добросовестно проходить школьную программу и читать-слушать чуть больше обычного, а за 3–4 недели до работы добавить форматную подготовку: демоверсия, разбор типовых заданий, тренировка аудирования. Если к концу 3 класса видно, что база проседает (ребёнок не читает простые тексты, путается в базовых конструкциях) — не ждите весны 4 класса: закрывать пробелы в базе лучше с сентября, без привязки к дате ВПР."),
        ("h2", "Как ВПР связана с будущими экзаменами"),
        ("p", "Полезно смотреть на ВПР как на генеральную репетицию экзаменационной культуры: бланки, регламент, незнакомая аудитория, работа на время. Навык спокойно писать контрольную «в незнакомом формате» пригодится в 5–7 классах на следующих ВПР, а потом и на ОГЭ. Именно поэтому мы советуем не списывать и не «выкапывать» варианты заранее: ценность ВПР для ребёнка — честный опыт, а не максимальный балл любой ценой. О том, как устроен следующий большой рубеж, читайте в разборе <a href=\"/blog-struktura-oge-po-anglijskomu\">структуры ОГЭ по английскому</a>."),
        ("h2", "Частые вопросы родителей про ВПР"),
        ("p", "<b>«ВПР обязательна?»</b> По английскому в 4 классе работу проводит школа по своему решению — точный ответ даст ваш классный руководитель. Если школа участвует, написать работу должен каждый ученик, но последствий за низкий балл для ребёнка нет."),
        ("p", "<b>«Нужно ли нанимать репетитора специально под ВПР?»</b> Как правило, нет: объём работы — школьная программа начальных классов. Репетитор или курс нужны в другом случае — когда пробная демоверсия дома показала системные пробелы в базе. Тогда точечная работа с педагогом действительно быстрее и спокойнее домашних попыток «пройти всё»."),
        ("h2", "Если база заметно слабее программы"),
        ("p", "Когда демоверсия дома пошла тяжело — это не приговор, а сигнал: у ребёнка есть пробелы, которые стоит закрыть до средней школы, где требования вырастут. В Фоксинбурге есть отдельная программа <a href=\"/vpr-anglijskij\">подготовки к ВПР по английскому</a>: педагог на бесплатной диагностике определит слабые места, а дальше работа идёт точечно — по тем навыкам, которые проверяет работа. Спокойная системная подготовка даёт не только хороший результат ВПР, но и уверенный старт в 5 классе — а это, в отличие от самой проверочной, действительно важная точка: именно в средней школе английский становится «настоящим» предметом с оценками, которые влияют на отношение ребёнка к языку на годы вперёд."),
    ],
    "related": [
        ("Подготовка к ВПР по английскому", "/vpr-anglijskij"),
        ("Ребёнок не понимает английский в школе", "/blog-rebenok-ne-ponimaet-anglijskij-v-shkole"),
        ("Все статьи блога", "/blog"),
    ],
    "faq": [
        ("Что входит в ВПР по английскому в 4 классе?", "Аудирование, чтение, грамматика и лексика, письмо — всё в рамках программы 4 класса. Устной части в ВПР нет."),
        ("Влияет ли ВПР на аттестат или перевод в следующий класс?", "Нет, ВПР — не экзамен. Это проверка уровня по единым заданиям, оценка за неё носит информационный характер. Но она честно показывает пробелы и готовит к формату будущих ОГЭ."),
        ("За сколько начинать готовиться к ВПР?", "Комфортно — за 2–3 месяца: спокойно повторить программу класса, разобрать формат заданий и написать пару пробников без стресса."),
        ("Чем ВПР отличается от обычной контрольной?", "Задания составлены не учителем, а на федеральном уровне, и формат незнакомый: инструкции, тайминг, бланки. Ребёнок может знать материал, но растеряться — поэтому формат тренируют отдельно."),
    ],
})

BLOG_POST_5 = dict(BLOG_FEED, **{
    "type": "article",
    "alias": "blog-razgovornyj-barjer-u-podrostka",
    "title": "Разговорный барьер у подростка: как помочь заговорить",
    "description": "Подросток понимает английский, но молчит? Разбираем языковой барьер: причины, ошибки родителей и 6 приёмов, которые помогают заговорить.",
    "category": "Учим английский",
    "date": "2026-08-09",
    "reading_time": "8 минут чтения",
    "hero_grad": "linear-gradient(135deg,#2e1a47 0%,#5a2d8f 55%,#9d5fc9 100%)",
    "body": [
        ("h2", "«Понимает всё, но молчит» — что это такое"),
        ("p", "Типичная картина: подросток смотрит видео на английском, понимает учителя, неплохо пишет и читает — но при попытке заговорить замирает, отвечает односложно или отшучивается. Это не отсутствие знаний, а языковой барьер: разрыв между пассивным запасом (что понимаю) и активным (что могу сказать), усиленный страхом ошибки. В подростковом возрасте он особенно силён, потому что добавляется социальный фактор: ошибиться при сверстниках в 13 лет страшнее, чем получить двойку."),
        ("h2", "Почему подростки молчат: четыре причины"),
        ("ul", [
            "<b>Страх публичной ошибки.</b> Опыт «сказал неправильно — класс засмеялся» запоминается надолго.",
            "<b>Перфекционизм.</b> Подросток хочет звучать умно, как по-русски, а получается «как у первоклассника» — и выбирает молчание.",
            "<b>Нет разговорной практики как навыка.</b> Говорение тренируется только говорением: если на уроках 90% времени — учебник и грамматика, речь не откуда взять.",
            "<b>Не о чем говорить «в вакууме».</b> Абстрактные темы из учебника подростку неинтересны — молчание от скуки выглядит так же, как молчание от страха.",
        ]),
        ("h2", "Что не работает"),
        ("ul", [
            "«Ну скажи что-нибудь по-английски!» при гостях — гарантированное усиление барьера.",
            "Исправление каждой ошибки на лету — подросток быстро делает вывод, что молчать безопаснее.",
            "Сравнение с теми, кто «уже свободно говорит».",
            "Дополнительные упражнения на грамматику — знаний обычно уже достаточно, проблема не в них.",
        ]),
        ("h2", "Шесть приёмов, которые работают дома"),
        ("ul", [
            "<b>Вопросы с выбором.</b> Не «расскажи, как прошёл день», а «tea or juice?», «cat person or dog person?» — короткий ответ без риска ошибки как первый шаг.",
            "<b>Английское время — 10 минут в день.</b> Фиксированный короткий слот, когда вся семья говорит только по-английски: можно ломаным, можно со словарём. Регулярность важнее длины.",
            "<b>Его контент, а не учебник.</b> Пересказ серии любимого сериала, текста песни, игрового видео — говорить о своём интересе психологически проще.",
            "<b>Запись голосом.</b> Голосовое самому себе или вам в мессенджере: нет зрителей — нет страха; потом можно вместе послушать и отметить хорошее.",
            "<b>Игры со словами.</b> Alias, «20 вопросов», ассоциации — речь в игровой рамке, где ошибка не наказуема.",
            "<b>Реагировать на смысл, а не на форму.</b> Сказал «I goed» — отвечайте на содержание («Really? Where did you go?»), а форму подправьте позже и один раз.",
        ]),
        ("h2", "Почему мини-группы снимают барьер быстрее"),
        ("p", "Домашние приёмы разогревают, но перелом обычно происходит в среде: когда подросток видит, что другие такие же подростки говорят с ошибками — и ничего страшного. В мини-группе 6–8 человек каждый говорит на каждом занятии, а педагог выстраивает атмосферу, где ошибка — рабочий инструмент, а не позор. Именно на этом построены наши программы для <a href=\"/podrostki\">подростков</a> и курс <a href=\"/razgovornyj-anglijskij\">разговорного английского</a>: коммуникативная методика, темы, которые подросткам реально интересны, и много живой речи с первого занятия."),
        ("h2", "Почему в детстве говорил, а сейчас молчит"),
        ("p", "Родители часто удивляются: в младших классах ребёнок охотно повторял слова и пел песенки, а в 12–14 лет замолчал. Это закономерно, и вот почему. Младший школьник говорит не задумываясь — ему важен процесс, а не впечатление. Подросток впервые слышит себя со стороны: он замечает акцент, понимает, что звучит «по-детски», и болезненно реагирует на любую ухмылку. Плюс растёт разрыв между богатой русской речью и бедной английской: мысль сложная, а инструмент простой — отсюда ощущение «я глупо звучу», которое для подростка невыносимо. Это не регресс, а взросление; барьер в этом возрасте — почти у всех, вопрос только в том, есть ли безопасная среда, чтобы через него пройти."),
        ("h2", "Признаки того, что барьер отступает"),
        ("ul", [
            "подросток начал вставлять английские фразы в речь или переписку — пусть с ошибками и в шутку;",
            "смотрит контент на английском без русских субтитров и не жалуется;",
            "отвечает на ваши английские вопросы, не дожидаясь повтора;",
            "меньше извиняется и «я не знаю, как это сказать», больше подбирает обходные формулировки;",
            "сам предлагает «давай по-английски» — хотя бы в игре.",
        ]),
        ("p", "Каждый из этих сигналов важнее любого теста: они означают, что язык стал для подростка рабочим инструментом, а не школьным предметом. Дальше задача — не расслабляться и не устраивать «проверок»: барьер возвращается быстрее, чем уходит."),
        ("h2", "Частые вопросы родителей"),
        ("p", "<b>«А помогут ли блогеры и игры на английском?»</b> Помогают как фон: они расширяют пассивный запас и приучают ухо. Но барьер — это про активную речь, а она тренируется только ответом живому собеседнику. Смотреть стримы и молчать — всё равно что учиться плавать по видео: полезно, но недостаточно."),
        ("p", "<b>«Стоит ли заставлять говорить, если подросток сопротивляется?»</b> Нет: давление укрепляет барьер, а не пробивает его. Работает обратная стратегия — снизить ставки (короткие игровые форматы, отсутствие оценки за ошибки) и дать безопасную аудиторию. Когда говорить становится нестрашно, сопротивление обычно сходит на нет само."),
        ("h2", "Сколько времени нужно, чтобы заговорить"),
        ("p", "Честный ответ: первые изменения — смелость, короткие ответы без уговоров — видны через 1–2 месяца регулярной разговорной практики (два занятия в неделю плюс домашний фон). Устойчивая свободная речь на знакомые темы — обычно история про полгода-год, в зависимости от стартового уровня. Важно не бросить в точке «ну он уже что-то бормочет»: именно после первых успехов прогресс ускоряется. Определить стартовую точку и реалистичный срок поможет бесплатная диагностика — заодно подросток сам увидит, что говорить он уже умеет больше, чем думает. Это, кстати, частый исход диагностики: ребёнок приходит уверенный, что «совсем не говорит», а через 20 минут спокойной беседы с педагогом выясняется, что проблема не в языке, а в страхе — и это очень обнадёживающее открытие для обеих сторон."),
    ],
    "related": [
        ("Английский для подростков", "/podrostki"),
        ("Разговорный английский", "/razgovornyj-anglijskij"),
        ("Все статьи блога", "/blog"),
    ],
    "faq": [
        ("Почему подросток понимает английский, но не говорит?", "Это языковой барьер: чтение и аудирование он тренировал годами, а говорение — почти никогда, плюс страх ошибиться перед сверстниками. Речь — отдельный навык, и он растёт только из практики в безопасной атмосфере."),
        ("Как помочь подростку заговорить?", "Главное — регулярная речевая практика без давления: мини-группы по возрасту, разговорные встречи, темы из его жизни (игры, музыка, фильмы), где ошибка — нормально, а не стыдно."),
        ("Не поздно ли начинать разговорную практику в 13–15 лет?", "Нет, это отличный возраст: база из школы уже есть, мотивация от реальных интересов — музыки, блогеров, игр — сильная. Обычно первые уверенные фразы появляются через несколько недель регулярной практики."),
        ("Помогут ли фильмы и песни на английском?", "Как поддержка — да: они тренируют восприятие на слух и дают живую лексику. Но смотреть и говорить — разные навыки: без собственной речи барьер не уходит, поэтому нужна именно разговорная практика."),
    ],
})

BLOG_POST_6 = dict(BLOG_FEED, **{
    "type": "article",
    "alias": "blog-struktura-oge-po-anglijskomu",
    "title": "Структура ОГЭ по английскому: разделы и формат заданий",
    "description": "Структура ОГЭ по английскому простыми словами: письменная и устная части, разделы, формат заданий и с чего начать подготовку в 8–9 классе.",
    "category": "Экзамены",
    "date": "2026-08-11",
    "reading_time": "8 минут чтения",
    "hero_grad": "linear-gradient(135deg,#241a36 0%,#5a2d8f 55%,#8a4fb8 100%)",
    "body": [
        ("h2", "Из чего состоит экзамен"),
        ("p", "ОГЭ по английскому сдают в 9 классе — это один из предметов по выбору. Экзамен состоит из двух частей: письменной (аудирование, чтение, грамматика и лексика, письмо) и устной (говорение). Письменная часть занимает 120 минут, устная — около 15 минут вместе с подготовкой. Обе части сдаются в разные дни. Актуальные кодификатор и демоверсию каждый учебный год публикует ФИПИ — перед стартом подготовки сверяйтесь именно с ними: мелкие детали формата могут уточняться."),
        ("h2", "Письменная часть"),
        ("html", "<table><tr><th>Раздел</th><th>Что проверяет</th><th>Формат</th></tr>"
               "<tr><td>Аудирование</td><td>Понимание речи на слух: диалоги и короткие высказывания</td><td>Задания на соответствие и выбор ответа, записи звучат дважды</td></tr>"
               "<tr><td>Чтение</td><td>Понимание текстов: основной смысл, детали, структура</td><td>Тексты + задания на соответствие и выбор варианта</td></tr>"
               "<tr><td>Грамматика и лексика</td><td>Владение формами слов и словарным запасом</td><td>Преобразование слов и подстановка в пропуски</td></tr>"
               "<tr><td>Письмо</td><td>Умение написать личное письмо</td><td>Письмо другу 100–120 слов с ответом на вопросы из письма-стимула</td></tr></table>"),
        ("p", "Ключевой момент про письменную часть: она проверяет не «английский вообще», а умение работать в конкретных форматах. Например, в заданиях на аудирование почти всегда есть ловушки на перефразирование — в записи услышите не те же слова, что в вариантах ответов, а их синонимы. Поэтому тренироваться нужно на материалах именно в формате ОГЭ, а не просто «слушать английский»."),
        ("h2", "Устная часть"),
        ("p", "Говорение сдаётся отдельно и состоит из трёх заданий: чтение короткого текста вслух (оценивается произношение и интонация), монолог по теме с опорой на план и диалог-расспрос с экзаменатором-компьютером: нужно задать вопросы по заданной ситуации и ответить на встречные. Времени на подготовку к каждому заданию — пара минут, ответы записываются."),
        ("p", "Устная часть пугает школьников больше всего, хотя статистически «проваливают» её реже, чем теряют баллы на невнимательности в письменной. Снимается страх одним: регулярной репетицией формата — говорить на время, по плану, вслух. Если дома такой практики нет, её обязательно нужно организовать с педагогом."),
        ("h2", "Как оценивается результат"),
        ("p", "За каждое задание начисляются первичные баллы, которые затем переводятся в привычную пятибалльную шкалу. Шкалу перевода и минимальный порог «тройки» утверждают на конкретный год — точные цифры смотрите в документах ФИПИ и Рособрнадзора текущего сезона. Практический ориентир для спокойствия: для уверенной «четвёрки» обычно достаточно стабильно выполнять большинство заданий базового и среднего уровня — не нужно идеально знать всё."),
        ("h2", "Типичные ошибки девятиклассников по разделам"),
        ("ul", [
            "<b>Аудирование:</b> попытка понять каждое слово вместо поиска нужной информации; паника после первой непонятной фразы — и потерян весь фрагмент.",
            "<b>Чтение:</b> выбор ответа по совпадению слов, а не по смыслу — составители заданий специально кладут в варианты слова из «неправильных» абзацев.",
            "<b>Грамматика:</b> правильная форма слова с орфографической ошибкой — балл теряется целиком, поэтому выписывание ответов нужно тренировать отдельно.",
            "<b>Письмо:</b> нарушение объёма и пропуск вопросов из письма-стимула — чисто форматные потери, самые обидные.",
            "<b>Говорение:</b> монолог не по плану и молчание дольше нескольких секунд в диалоге.",
        ]),
        ("h2", "Как распределить год подготовки"),
        ("p", "Рабочая схема для 9 класса: сентябрь–ноябрь — закрытие пробелов языка (грамматика и словарь по шкалам экзамена), декабрь–февраль — пораздельная тренировка в формате ОГЭ, март–апрель — полные пробники на время с разбором ошибок, май — лёгкое повторение и работа с устной частью. Такой график оставляет запас на школьную нагрузку и не превращает весну в аврал. Если стартуете позже — принцип тот же, просто этапы сжимаются; главное, не начинать сразу с пробников: они показывают проблему, но не решают её."),
        ("h2", "Частые вопросы про ОГЭ по английскому"),
        ("p", "<b>«ОГЭ обязателен?»</b> Да, для аттестата за 9 класс сдают четыре предмета: русский, математику и два по выбору — английский как раз из числа предметов по выбору. Несданный ОГЭ означает пересдачу, поэтому откладывать подготовку «на потом» не стоит."),
        ("p", "<b>«Можно ли подготовиться самостоятельно?»</b> Письменную часть при дисциплине — отчасти да: демоверсии и сборники открыты. Слабое место самоподготовки — аудирование на скорости и устная часть: говорение невозможно натренировать без собеседника, который слушает, поправляет и гоняет по формату. Поэтому даже самостоятельным ребятам мы советуем хотя бы несколько занятий с педагогом на разбор ошибок и прогон говорения."),
        ("p", "<b>«Чем ОГЭ отличается от школьной программы?»</b> Уровнем языка они близки, но экзамен проверяет ещё и умение работать с форматом: распределять время, понимать ловушки в вариантах ответов, укладываться в объём письма. Сильный по школьным меркам ученик без форматной подготовки регулярно недобирает баллы на мелочах."),
        ("h2", "С чего начать подготовку"),
        ("ul", [
            "<b>Скачайте демоверсию ФИПИ</b> и пройдите её один раз целиком — станет ясно, какие разделы даются легко, а какие проседают.",
            "<b>Определите стартовый уровень языка.</b> Если он ниже A2, сначала нужно подтянуть сам язык — формат поверх слабой базы не поможет.",
            "<b>Тренируйте каждый раздел отдельно</b>, а в последние 2–3 месяца — полные варианты на время.",
            "<b>Говорите вслух каждую неделю</b>: устную часть невозможно подготовить «на бумаге».",
            "<b>Начните в 8 классе или в начале 9-го</b> — год спокойной работы даёт предсказуемый результат без марафона.",
        ]),
        ("p", "Пошаговый план подготовки мы разбирали в статье «<a href=\"/novosti-kak-podgotovitsya-k-oge-anglijskij\">Как подготовиться к ОГЭ по английскому</a>». А на курсе <a href=\"/oge-anglijskij\">подготовки к ОГЭ</a> в Фоксинбурге программа строится от диагностики: закрываем пробелы языка, отрабатываем каждый раздел в формате экзамена и несколько раз проходим полный пробник — включая устную часть. Первый шаг — бесплатная диагностика уровня: по её итогам вы получите честную картину — какой балл ребёнок набрал бы сейчас, где теряются очки и какой объём работы стоит между текущей точкой и уверенной сдачей. С этой картиной решение о формате подготовки принимается легко и без паники."),
    ],
    "related": [
        ("Подготовка к ОГЭ по английскому", "/oge-anglijskij"),
        ("Как подготовиться к ОГЭ: план", "/novosti-kak-podgotovitsya-k-oge-anglijskij"),
        ("Все статьи блога", "/blog"),
    ],
    "faq": [
        ("Из чего состоит ОГЭ по английскому?", "Две части: письменная (аудирование, чтение, грамматика и лексика, письмо) и устная (чтение вслух, монолог и диалог по картинке). Письменная сдаётся в один день, устная — в другой."),
        ("Сколько времени даётся на экзамен?", "На письменную часть — 120 минут, на устную — около 15 минут включая подготовку. Тайминг — часть экзамена, его тренируют на пробниках."),
        ("Какой балл нужен для сдачи ОГЭ?", "Минимальный проходной балл устанавливается ежегодно (обычно 29 из 90 для «тройки»). Для уверенной сдачи мы целимся в 45+, чтобы был запас."),
        ("За какое время начинать подготовку к ОГЭ?", "Оптимально — с начала 9 класса или летом перед ним: хватает времени закрыть пробелы и несколько раз пройти весь формат на пробниках."),
    ],
})

BLOG_POST_7 = dict(BLOG_FEED, **{
    "type": "article",
    "alias": "blog-gotov-li-rebenok-k-shkole",
    "title": "Готов ли ребёнок к школе: чек-лист для родителей",
    "description": "Чек-лист готовности ребёнка к школе: социальные, эмоциональные и учебные навыки, красные флаги и как подготовиться за 6 месяцев.",
    "category": "Школа и учёба",
    "date": "2026-08-13",
    "reading_time": "8 минут чтения",
    "hero_grad": "linear-gradient(135deg,#392852 0%,#662d92 55%,#8a4fb8 100%)",
    "body": [
        ("h2", "Готовность к школе — это не «умеет читать»"),
        ("p", "Самый живучий миф: ребёнок готов к школе, если читает, считает и пишет печатными буквами. На практике первоклассники чаще страдают не от нехватки академических навыков, а от того, что не умеют сидеть 30 минут, слушать инструкцию, просить о помощи и переживать ошибку. Педагоги называют это школьной зрелостью — и у неё четыре компонента: эмоциональный (умеет ждать, переключаться, не паниковать при трудности), социальный (взаимодействует со взрослыми и детьми, понимает правила), познавательный (любопытство, удержание внимания, простая логика) и речевой (понимает обращённую речь, строит фразы, связно пересказывает)."),
        ("h2", "Чек-лист: 12 признаков готовности"),
        ("ul", [
            "удерживает внимание на спокойном занятии 20–30 минут;",
            "выполняет инструкцию из 2–3 шагов («возьми тетрадь, открой страницу, обведи»);",
            "доводит начатое до конца, хотя бы с небольшим напоминанием;",
            "может проиграть в игре без истерики и попробовать снова;",
            "просит о помощи словами, а не плачем или отказом;",
            "знает правила очерёдности: ждать своей очереди, не перебивать;",
            "остаётся без родителей на занятии без сильной тревоги;",
            "пересказывает сюжет мультфильма или книги связными предложениями;",
            "понимает «вчера/завтра», «слева/справа», времена года, части суток;",
            "уверенно держит карандаш, пользуется ножницами, лепит и рисует;",
            "считает в пределах 10, сравнивает «больше/меньше», узнаёт основные геометрические формы;",
            "самостоятельно одевается, собирает свои вещи, следит за гигиеной.",
        ]),
        ("p", "Если из 12 пунктов уверенно выполняются 9–10 — всё в порядке, остальное догонится. Ни один пункт сам по себе не является диагнозом: важна общая картина и динамика."),
        ("h2", "Красные флаги, на которые стоит обратить внимание"),
        ("ul", [
            "не может усидеть на месте даже за любимым спокойным занятием 10 минут;",
            "резко негативно реагирует на любые «учебные» ситуации;",
            "не устанавливает контакт с незнакомыми взрослыми даже за несколько встреч;",
            "речь заметно отстаёт: короткие фразы, трудно подбирает слова, непонятно говорит;",
            "любая ошибка или проигрыш вызывает длительную истерику или отказ от деятельности.",
        ]),
        ("p", "Один флаг — повод понаблюдать, несколько систематических — повод проконсультироваться со специалистом до школы, а не в первой четверти."),
        ("h2", "Как помочь за 6 месяцев до школы"),
        ("ul", [
            "<b>Режим и самостоятельность.</b> Постепенно приближайте подъём и отбой к школьным, поручите ребёнку реальные бытовые обязанности.",
            "<b>Игры по правилам.</b> Настольные игры учат очерёдности, проигрышу и удержанию внимания лучше любых прописей.",
            "<b>Много разговоров.</b> Обсуждайте прочитанное, просите пересказывать, задавайте вопросы «почему» и «как ты думаешь» — это тренирует речь и логику одновременно.",
            "<b>Групповой опыт.</b> Регулярные занятия в мини-группе — лучшая репетиция школьного формата: чужой взрослый, правила, сверстники.",
            "<b>Не «натаскивайте» на первый класс.</b> Ребёнку, который всё уже знает, на уроках скучно — и это отдельная проблема.",
        ]),
        ("h2", "Что обычно спрашивают на собеседовании в школу"),
        ("p", "Формальное тестирование при поступлении в первый класс не допускается, но собеседование есть почти везде, и оно удивительно похоже на наш чек-лист: педагог просит назвать себя и родителей, пересказать короткую историю по картинкам, посчитать, сравнить предметы, найти лишнее, ответить на бытовые вопросы («что делают утром?», «чем птица отличается от самолёта?»). Через эти простые задания смотрят не эрудицию, а речь, логику, удержание инструкции и контакт со взрослым — то есть ту самую школьную зрелость."),
        ("h2", "А нужен ли английский до школы"),
        ("p", "Частый вопрос родителей будущих первоклассников. Английский до школы не входит в список обязательных навыков, но работает как сильный «тренажёр» готовности: на хороших детских занятиях ребёнок учится ровно тому, что проверяют на собеседовании, — слушать педагога, работать в мини-группе, не бояться незнакомого взрослого, выполнять инструкции. Плюс появляется языковая база, с которой школьный английский стартует заметно легче. Наша линейка для дошкольников описана на странице <a href=\"/doshkolniki\">английского для дошкольников</a>, а о возрасте старта мы писали в статье «<a href=\"/blog-anglijskij-dlya-detej-3-4-goda\">Английский для детей 3–4 лет</a>»."),
        ("h2", "Частые вопросы родителей будущих первоклассников"),
        ("p", "<b>«Идти в 6,5 или подождать до 7,5?»</b> Решайте не возрастом, а чек-листом: если ребёнок удерживает внимание, общается со взрослыми и переживает трудности — 6,5 не помеха. Если по нескольким пунктам есть сомнения, год в подготовительной группе почти всегда лучше, чем год мучений в первом классе."),
        ("p", "<b>«Нужно ли учить читать до школы?»</b> Обязательного требования нет, но ребёнку, который читает хотя бы по слогам, первые месяцы даются заметно легче — он не тратит весь ресурс на технику чтения. Важнее, впрочем, другое: понимать прочитанное и уметь пересказать. Чтение без понимания педагоги не считают чтением."),
        ("p", "<b>«Что делать, если по чек-листу не готов, а в школу — через полгода?»</b> Не паниковать и не пытаться «прокачать всё» сразу. Выберите 2–3 самых отстающих навыка (обычно это внимание, инструкции и речь) и работайте точечно: настольные игры, разговоры, мини-группа. Полгода при регулярной работе — большой срок, дети в этом возрасте меняются быстро."),
        ("h2", "Как готовим к школе в Фоксинбурге"),
        ("p", "Наша программа <a href=\"/preparation\">подготовки к школе</a> закрывает именно школьную зрелость целиком: в мини-группах дети учатся работать по инструкции, удерживать внимание, общаться и переживать трудности — плюс, разумеется, чтение, счёт, логика и речь в объёме, который ждут в первом классе. Педагоги видят каждого ребёнка и регулярно рассказывают родителям, что уже готово, а над чем ещё работаем. Приходите на бесплатную диагностику — за одно занятие покажем честную картину готовности и план на оставшееся до школы время. Это особенно полезно, если чек-лист выше оставил у вас вопросы: «по бумаге» оценить эмоциональную и социальную зрелость сложнее всего, а педагог, который каждый год выпускает подготовишек, видит эти вещи за одно занятие и подскажет, где нужна поддержка, а где всё в норме и можно выдохнуть."),
    ],
    "related": [
        ("Подготовка к школе", "/preparation"),
        ("Английский для детей 3–4 лет", "/blog-anglijskij-dlya-detej-3-4-goda"),
        ("Все статьи блога", "/blog"),
    ],
    "faq": [
        ("Как понять, готов ли ребёнок к школе?", "Смотрите не на «умеет ли читать», а на базу: умеет слушать инструкцию, доводит короткое задание до конца, держит внимание 15–20 минут, общается со сверстниками, справляется с простыми бытовыми действиями сам."),
        ("Должен ли первоклассник уметь читать и писать?", "По ФГОС — нет, школа обязана принять ребёнка без этих навыков. Но готовая моторика руки, умение слушать и понимать задания заметно облегчают старт."),
        ("Что развивать в последний год перед школой?", "Речь и словарь, логику и счёт в игре, мелкую моторику, фонематический слух (различать звуки в словах) и самостоятельность: одеться, собрать рюкзак, попросить помощи."),
        ("Когда начинать подготовку к школе?", "Спокойно — за год, занятия 2 раза в неделю в игровом формате. За пару месяцев тоже можно усилить отдельные навыки, но без спешки результат устойчивее."),
    ],
})

BLOG_POST_8 = dict(BLOG_FEED, **{
    "type": "article",
    "alias": "blog-onlajn-ili-oflajn-anglijskij",
    "title": "Онлайн или офлайн: какой формат английского выбрать ребёнку",
    "description": "Онлайн или офлайн-занятия английским для ребёнка: честное сравнение по возрасту, целям и дисциплине — и когда лучше работает гибрид.",
    "category": "Родителям",
    "date": "2026-08-15",
    "reading_time": "7 минут чтения",
    "hero_grad": "linear-gradient(135deg,#2e1a47 0%,#6237a2 55%,#9d5fc9 100%)",
    "body": [
        ("h2", "Короткий ответ: зависит от возраста и задачи"),
        ("p", "Спор «онлайн vs офлайн» бессмысленен в абстрактном виде: оба формата работают, но у разных детей и в разных ситуациях. Офлайн сильнее там, где нужны живая дисциплина, движение и социальный контакт. Онлайн выигрывает в гибкости, логистике и доступе к сильному педагогу без привязки к району. Ниже — честное сравнение по критериям, которые реально влияют на результат."),
        ("html", "<table><tr><th>Критерий</th><th>Офлайн</th><th>Онлайн</th></tr>"
               "<tr><td>Дошкольники и 1–2 класс</td><td>Явно лучше: нужны движение, предметы, живой контакт</td><td>Подходит редко и только в коротком игровом виде</td></tr>"
               "<tr><td>Удержание внимания</td><td>Проще: педагог физически рядом</td><td>Требует от ребёнка самодисциплины или родителя рядом</td></tr>"
               "<tr><td>Разговорная практика</td><td>Полноценная: живая группа, игры, парная работа</td><td>Работает, но зависит от качества связи и платформы</td></tr>"
               "<tr><td>Логистика</td><td>Дорога, расписание, привязка к филиалу</td><td>Занимайся из дома, дачи, другого города</td></tr>"
               "<tr><td>Экзамены и индивидуальные цели</td><td>Хорошо</td><td>Хорошо — формат почти не влияет</td></tr>"
               "<tr><td>Пропуски и болезни</td><td>Пропустил — потерял</td><td>Легче подключиться из дома или перенести</td></tr></table>"),
        ("h2", "Когда офлайн однозначно лучше"),
        ("ul", [
            "Ребёнку 3–9 лет: в этом возрасте язык осваивается через движение, предметы и живое общение — экран это беднее.",
            "Ребёнку сложно сосредоточиться дома: компьютер ассоциируется с играми, и удержать рабочий настрой не получается.",
            "Нужна социализация: для стеснительных детей живая мини-группа — это ещё и тренировка общения.",
            "У родителей нет возможности контролировать подключение и присутствовать рядом на старте.",
        ]),
        ("h2", "Когда онлайн — разумный выбор"),
        ("ul", [
            "Подростки: они дисциплинированнее, привыкли к экрану и часто ценят сэкономленное на дорогу время.",
            "Насыщенное расписание: когда между школой, секциями и домом нет часа на дорогу, онлайн — единственный способ сохранить регулярность.",
            "Вы живёте далеко от хорошей школы: сильный педагог онлайн лучше случайного офлайн «рядом с домом».",
            "Частые поездки или переезды: онлайн-формат не даёт обучению прерваться.",
        ]),
        ("h2", "Гибрид: лучшее из двух миров"),
        ("p", "Для многих семей оптимален смешанный режим: основные занятия офлайн, а в периоды болезней, поездок и каникул — онлайн-поддержка, чтобы не терять ритм. Регулярность в изучении языка важнее формата: два занятия в неделю в любом виде лучше идеального формата, который срывается раз в месяц. О том, как сохранять навык на перерывах, мы писали в статье «<a href=\"/novosti-anglijskij-letom-kak-ne-poteryat-navyk\">Английский летом</a>». Гибрид хорошо работает и в обратную сторону: онлайн как база плюс очные разговорные встречи раз в месяц — для семей, которые живут далеко от Долгопрудного, но не хотят терять живую среду совсем."),
        ("h2", "Как понять, что формат не подошёл"),
        ("p", "Формат — не приговор: нормально попробовать один и перейти на другой. Сигналы, что пора менять:"),
        ("ul", [
            "онлайн: ребёнок регулярно отвлекается, занимается «вполсилы», подключения срываются — и вы постоянно вынуждены сидеть рядом;",
            "офлайн: дорога съедает столько сил и времени, что занятия стали стрессом для всей семьи, пропуски растут;",
            "в любом формате: ребёнок месяцами ходит без удовольствия, а видимого прогресса нет — тут дело обычно не в формате, а в программе или группе.",
        ]),
        ("h2", "Что спросить у школы про формат"),
        ("ul", [
            "Совпадает ли программа онлайн и офлайн — или онлайн-версия «урезанная»?",
            "Кто ведёт онлайн-занятия — те же педагоги, что в филиалах?",
            "Можно ли перейти из одного формата в другой в течение года без потери программы?",
            "Что происходит при пропуске: перенос, запись урока, отработка?",
            "Сколько детей в онлайн-группе — мини-группа или вебинар?",
        ]),
        ("p", "Ответы на эти вопросы говорят о школе больше, чем рекламные обещания: честная школа спокойно признаёт ограничения каждого формата и помогает выбрать, а не «впарить» то, что удобнее ей. Запишите ответы — они пригодятся при сравнении двух-трёх вариантов."),
        ("h2", "Частые вопросы про формат"),
        ("p", "<b>«С какого возраста онлайн вообще работает?»</b> Ориентир — примерно 9–10 лет: когда ребёнок способен сам подключиться, удержать внимание за экраном весь урок и не требует взрослого рядом. Младшим онлайн возможен только в коротком игровом формате и с родителем на подхвате — иначе это борьба, а не занятие."),
        ("p", "<b>«Онлайн — это же хуже для глаз и концентрации?»</b> Занятие 30–45 минут с живым педагогом — не мультфильмы и не игры: ребёнок активно работает, а не пялится в экран. Разумная гигиена (перерыв после занятия, нормальное расстояние до экрана) снимает вопрос. А вот усталость от целого дня за компьютером — реальный аргумент: если ребёнок и так много онлайн, офлайн-занятие станет полезной сменой обстановки."),
        ("p", "<b>«А если переедем или поменяется расписание?»</b> Это как раз случай, когда формат должен быть живым: нормальная школа позволяет перейти из офлайна в онлайн (и обратно) с сохранением программы и по возможности педагога. Уточняйте это до покупки абонемента — переезд не должен обнулять обучение."),
        ("h2", "Как это устроено у нас"),
        ("p", "В Фоксинбурге доступны оба формата с одной и той же методикой: <a href=\"/standartnye-offline\">очные занятия</a> в двух филиалах Долгопрудного (Лихачёвский проспект, 76к1 и проспект Ракетостроителей, 9к3) и <a href=\"/online-zanyatiya\">онлайн-занятия</a> с теми же педагогами и программой. На бесплатной диагностике поможем выбрать формат под возраст, характер и расписание вашего ребёнка — и при необходимости формат можно будет поменять."),
        ("p", "Практический сценарий, который мы советуем сомневающимся семьям: начните с диагностики и пробного занятия в том формате, который ближе логистически, — и дайте ребёнку 3–4 недели. Если формат «не пошёл», переход в другой не означает отката: программа и уровень группы сохраняются, меняется только среда. Такой пробный период снимает главный страх выбора — «а вдруг ошибёмся и зря потратим год»: ошибка на месяц почти ничего не стоит, а вот год в чужом формате стоит дорого."),
    ],
    "related": [
        ("Онлайн-занятия", "/online-zanyatiya"),
        ("Очные занятия в Долгопрудном", "/standartnye-offline"),
        ("Все статьи блога", "/blog"),
    ],
    "faq": [
        ("Что эффективнее: онлайн или офлайн?", "Оба формата работают при хорошей методике. Офлайн даёт живую атмосферу и больше движения (важно для малышей), онлайн экономит дорогу и гибче по расписанию. Мы ведём оба — и результат сопоставим."),
        ("С какого возраста ребёнку подходят онлайн-занятия?", "Ориентировочно с 6–7 лет, когда ребёнок удерживает внимание за экраном 30–40 минут. Дошкольникам лучше офлайн: им нужны движение, предметы и живой контакт."),
        ("Как понять, что онлайн-занятия качественные?", "Живой урок с педагогом в реальном времени (не запись), мини-группа или индивидуально, обратная связь после каждого занятия и понятная программа — как в наших онлайн-занятиях."),
        ("Можно ли сочетать онлайн и офлайн?", "Да, это частый формат: будни — онлайн без дороги, часть занятий — очно. Гибрид сохраняет регулярность, а регулярность важнее формата."),
    ],
})

BLOG_POST_9 = dict(BLOG_FEED, **{
    "type": "article",
    "alias": "blog-kitajskij-dlya-detej",
    "title": "Китайский для детей: зачем и когда начинать",
    "description": "Зачем ребёнку китайский язык и когда начинать: тоны, иероглифы, реальная сложность, игровое знакомство и как поддерживать интерес дома.",
    "category": "Родителям",
    "date": "2026-08-17",
    "reading_time": "8 минут чтения",
    "hero_grad": "linear-gradient(135deg,#241a36 0%,#662d92 55%,#a05fd4 100%)",
    "body": [
        ("h2", "Зачем ребёнку китайский — честные причины"),
        ("p", "Китайский сегодня выбирают не как «модный трофей», а по вполне практическим соображениям. Это один из самых распространённых языков мира и язык одной из крупнейших экономик: к выпуску из школы сегодняшний второклассник будет жить в мире, где китайский в бизнесе, науке и технологиях звучит всё чаще. Но для ребёнка есть и более близкая польза: китайский тренирует слух (тоны!), память и внимание к деталям иначе, чем европейские языки, и даёт ребёнку ранний опыт «я могу выучить то, что кажется невозможным» — это очень сильный мотивационный капитал."),
        ("p", "Важно и то, чего ждать не стоит: быстрых результатов. Китайский — марафон, и честный горизонт «заметного умения» измеряется годами. Зато для детей это не проблема: у них эти годы есть, а ранний старт — именно то преимущество, которое нельзя наверстать во взрослом возрасте."),
        ("h2", "Когда начинать"),
        ("p", "Зависит от формата. Игровое знакомство — песни, считалки, отдельные слова, простые иероглифы-картинки — комфортно заходит уже в 5–7 лет: без цели «выучить», просто как расширение кругозора и тренировка слуха. Системное обучение — с тонами, письмом, грамматикой и разговорной практикой — лучше стартует с 8–10 лет, когда ребёнок умеет удерживать внимание, не пугается непривычного звучания и уже имеет опыт изучения хотя бы одного иностранного языка. Если ребёнок уже учит английский, китайский как второй язык воспринимается легче: сама идея «другой системы языка» ему знакома."),
        ("h2", "Что будет сложно — и что на удивление просто"),
        ("ul", [
            "<b>Тоны.</b> Один и тот же слог в разном тоне — разные слова. Для русскоязычного уха это главный вызов, но дети осваивают тоны легче взрослых — именно поэтому старт в детстве так ценен.",
            "<b>Иероглифы.</b> Их не «учат алфавитом», а накапливают постепенно: сначала узнавание, потом письмо самых частых. Современные методики подают их через картинки и истории составных частей.",
            "<b>Грамматика — легко.</b> Приятный сюрприз: нет спряжений, падежей, родов и артиклей. Порядок слов простой и логичный — после английских времён это отдых.",
            "<b>Мотивация.</b> Самое сложное в китайском — не предмет, а дистанция: нужен интересный ребёнку формат, иначе энтузиазм первых месяцев сдувается.",
        ]),
        ("h2", "Как поддерживать интерес дома"),
        ("ul", [
            "мультфильмы и песни на китайском — 10 минут фона в день делают для тонов больше, чем час зубрёжки в неделю;",
            "каллиграфия как игра: писать иероглифы кистью или в специальных прописях детям искренне нравится;",
            "культура вокруг языка: праздники, кухня, мифы, панды — китайский отлично «продаётся» ребёнку через культурный контекст;",
            "не превращайте в второй школьный предмет: на старте интерес важнее объёма.",
        ]),
        ("h2", "Сколько времени до первых результатов"),
        ("p", "Чтобы ожидания были реалистичными, ориентируйтесь на такую шкалу при занятиях два раза в неделю:"),
        ("ul", [
            "<b>1–2 месяц:</b> приветствия, числа, простые фразы о себе; ребёнок различает тоны на слух;",
            "<b>3–6 месяц:</b> бытовые мини-диалоги, несколько десятков иероглифов на узнавание, первые прописи;",
            "<b>год:</b> уверенный разговор на знакомые темы, чтение простых текстов с пиньинем, 150–200 иероглифов;",
            "<b>дальше:</b> накопление словаря и иероглифики, первые международные детские тесты — если есть интерес и цель.",
        ]),
        ("p", "Важно: эта шкала — ориентир, а не норматив. Дети развиваются скачками, и китайский — язык, где «плато» в середине пути случается почти у всех. Хороший педагог предвидит это плато и перестраивает формат заранее: больше игры, меньше прописей, — пока не вернётся движение."),
        ("p", "Главный фактор — регулярность и домашний фон. Ребёнок, который занимается год без пропусков «по чуть-чуть», обгоняет того, кто рвётся интенсивами с паузами. И держите в голове правильную метрику: в китайском успех первого года — это не «свободно говорит», а «не боится тонов, узнаёт иероглифы и с интересом идёт на занятие». С такой базой второй год даёт результаты, которые заметны уже и со стороны."),
        ("h2", "Китайский или немецкий вторым языком?"),
        ("p", "Частая дилемма родителей. Если коротко: немецкий после английского заходит легче (та же латиница, похожая логика), китайский — ярче и «дальше» от привычного, но требует больше времени до видимого результата. Мы подробно сравнивали оба варианта в статье «<a href=\"/novosti-vtoroj-inostrannyj-yazyk-nemeckij-ili-kitajskij\">Второй язык после английского</a>» — с возрастами и рисками перегрузки."),
        ("h2", "Частые вопросы про китайский"),
        ("p", "<b>«Не помешает ли китайский английскому?»</b> Нет, если нагрузка разумная: основной язык (английский) — 2–3 занятия в неделю, китайский на старте — 1–2 в игровом формате. Языки не «смешиваются»: у них разные учителя, материалы и даже системы письма — ребёнок разводит их без усилий."),
        ("p", "<b>«Мы не знаем китайского — как помогать дома?»</b> Так же, как с любым языком: включать песни и мультфильмы, интересоваться («покажи, как пишется кот»), хвалить за старание. Проверять домашние задания без знания языка не нужно — это работа педагога; ваша роль — атмосфера интереса."),
        ("p", "<b>«Не поздно ли начинать подростку?»</b> Не поздно, просто траектория другая: подросток быстрее осваивает систему письма и грамматику, но тональным слухом придётся поработать сознательно. Плюс подросткового старта — осознанная мотивация: многие приходят через интерес к культуре, и он тянет обучение сильнее любых родительских аргументов."),
        ("h2", "Как мы учим китайскому в Фоксинбурге"),
        ("p", "На курсе <a href=\"/kitajskij-yazyk\">китайского языка</a> дети занимаются в мини-группах по той же коммуникативной методике, что и на английском: от тонов и иероглифики — к живой речи, через игры, песни и культурный контекст. Педагоги следят, чтобы темп не обгонял интерес. Попробовать можно на бесплатной диагностике: за одно занятие видно, «зайдёт» ли ребёнку язык — обычно это заметно сразу. Китайский у нас в Долгопрудном ведут очно, а для семей из других городов доступен онлайн-формат — методика и педагоги те же. Если выбираете между вторыми языками, приходите с ребёнком на пробное занятие по обоим: живое впечатление от звучания языка часто решает выбор быстрее, чем любые списки плюсов и минусов."),
    ],
    "related": [
        ("Китайский язык", "/kitajskij-yazyk"),
        ("Второй язык: немецкий или китайский", "/novosti-vtoroj-inostrannyj-yazyk-nemeckij-ili-kitajskij"),
        ("Все статьи блога", "/blog"),
    ],
    "faq": [
        ("Зачем ребёнку китайский, если он ещё учит английский?", "Два языка не мешают друг другу, если каждый идёт в своём ритме. Китайский даёт развитие слуха и памяти (тональность, иероглифы), а английский остаётся базовым иностранным — они отлично дополняют друг друга."),
        ("С какого возраста можно начинать китайский?", "С 6–7 лет в игровом формате: песенки, карточки, простые фразы, знакомство с иероглифами как с картинками. Как и с любым языком, ранний старт — без зубрёжки."),
        ("Правда, что китайский очень сложный?", "Для ребёнка он не сложнее других языков — дети не «боятся» иероглифов и легко копируют тона. Сложность существует в основном в головах взрослых."),
        ("Что даст китайский в будущем?", "Китайский — язык крупнейшей экономики мира: учёба, бизнес, технологии. Плюс сам процесс развивает память, внимание и произношение, что помогает и в английском, и в школе."),
    ],
})

BLOG_POST_10 = dict(BLOG_FEED, **{
    "type": "article",
    "alias": "blog-repetitor-ili-gruppa",
    "title": "Репетитор или группа в Долгопрудном: что выбрать ребёнку",
    "description": "Репетитор или групповые занятия английским в Долгопрудном: сравнение форматов по задачам — развитие, пробелы, экзамены, мотивация и бюджет.",
    "category": "Родителям",
    "date": "2026-08-19",
    "reading_time": "8 минут чтения",
    "hero_grad": "linear-gradient(135deg,#2e1a47 0%,#5a2d8f 55%,#8a4fb8 100%)",
    "body": [
        ("h2", "Короткий ответ: смотря какая задача"),
        ("p", "«Репетитор или курсы» — не вопрос престижа, а вопрос задачи. Группа и репетитор решают разные проблемы, и ошибка выбора стоит дорого: не столько денег, сколько потерянного года и потухшего интереса ребёнка. Общее правило: долгосрочное развитие языка эффективнее в группе, а точечные проблемы и сжатые сроки — с репетитором."),
        ("html", "<table><tr><th>Ситуация</th><th>Что подходит</th><th>Почему</th></tr>"
               "<tr><td>Регулярное изучение языка «вдолгую»</td><td>Мини-группа</td><td>Живое общение, мотивация от сверстников, разговорная практика</td></tr>"
               "<tr><td>Конкретный пробел (тема, навык)</td><td>Репетитор</td><td>Точечная работа именно над вашей проблемой</td></tr>"
               "<tr><td>Экзамен через 3–6 месяцев, база слабая</td><td>Репетитор</td><td>Нужен индивидуальный маршрут и плотный темп</td></tr>"
               "<tr><td>Ребёнок стесняется говорить</td><td>Мини-группа</td><td>Барьер снимается в среде равных, а не один на один со взрослым</td></tr>"
               "<tr><td>Сложное расписание, частые поездки</td><td>Репетитор</td><td>Гибкий график, можно онлайн</td></tr>"
               "<tr><td>Ограниченный бюджет при долгом курсе</td><td>Группа</td><td>Заметно дешевле за месяц регулярных занятий</td></tr></table>"),
        ("h2", "Сильные и слабые стороны группы"),
        ("ul", [
            "<b>Плюс — живая речь.</b> Язык существует для общения: в мини-группе 6–8 человек ребёнок говорит с разными людьми, а не только с педагогом.",
            "<b>Плюс — мотивация.</b> Сверстники, игра, соревновательность и «мы вместе» удерживают интерес годами — репетитору это не воспроизвести.",
            "<b>Плюс — цена.</b> Месяц групповых занятий стоит ощутимо меньше месяца индивидуальных.",
            "<b>Минус — общий темп.</b> Педагог двигается со скоростью группы: сильному может быть скучно, отстающему — быстро.",
            "<b>Минус — фиксированное расписание.</b> Пропустил занятие — материал ушёл вперёд.",
        ]),
        ("h2", "Сильные и слабые стороны репетитора"),
        ("ul", [
            "<b>Плюс — индивидуальный маршрут.</b> Каждая минута занятия работает на конкретную цель вашего ребёнка.",
            "<b>Плюс — гибкость.</b> График, темп, формат (в том числе онлайн) подстраиваются под семью.",
            "<b>Плюс — скорость на точечных задачах.</b> Пробел в грамматике или разгон перед экзаменом закрывается в разы быстрее, чем в группе.",
            "<b>Минус — нет среды.</b> Разговорная практика ограничена диалогом с одним взрослым; для детей это часто скучнее.",
            "<b>Минус — цена при длинной дистанции.</b> Год индивидуальных занятий дважды в неделю — серьёзный бюджет.",
            "<b>Минус — лотерея качества.</b> Частный репетитор без методики и контроля — это кот в мешке; в школе педагогов обучают и проверяют.",
        ]),
        ("h2", "Красные флаги при выборе"),
        ("p", "Выбирая <b>репетитора</b>, насторожитесь, если: нет первичной диагностики и плана («просто позанимаемся»); педагог не даёт обратной связи родителям; занятие сводится к «прочитали параграф и сделали упражнение» — это можно и бесплатно; обещают «с нуля до B2 за полгода». Хороший репетитор на первой встрече больше спрашивает, чем рассказывает."),
        ("p", "Выбирая <b>группу</b>, проверьте: сколько детей реально в группе (после 10–12 человек «разговорная практика» превращается в лекцию); набирают ли по уровню или «куда есть место»; есть ли у школы методика и отчётность для родителей; кто заменяет педагога при болезни. И универсальный тест для обоих форматов — пробное занятие: ребёнок после него либо заинтересован, либо нет, и это видно без всяких тестов."),
        ("h2", "Можно ли совместить — и когда это лучший вариант"),
        ("p", "Да, и часто это оптимум: группа как основа (регулярность, среда, разговорная практика) плюс короткий блок индивидуальных занятий под конкретную задачу — например, подтянуть грамматику перед ВПР или устную часть перед ОГЭ. Так семья не платит за индивидуальный формат весь год, но получает его там, где он реально нужен."),
        ("h2", "Как посчитать стоимость честно"),
        ("p", "Сравнивайте не цену часа, а цену результата. Дешёвый час репетитора без методики, потраченный на «почитали учебник», дороже занятия в группе, где ребёнок реально говорит. Считайте месяц: группа 2 раза в неделю против индивидуальных занятий той же частоты — разница обычно кратная. Именно поэтому для долгой дистанции группа — базовый вариант большинства семей, а репетитор — инструмент на конкретный этап. Актуальные цены на все форматы собраны на странице <a href=\"/tseny\">цен</a>."),
        ("h2", "Частые вопросы"),
        ("p", "<b>«А если ребёнок отстал, но группу уже набрали по уровню?»</b> Правильно собранная группа компенсирует разницу темпов, но не запущенный пробел. Если диагностика показывает отставание на год программы и больше — честнее сначала закрыть его индивидуально, а потом войти в группу своего уровня."),
        ("p", "<b>«Можно ли начать с группы и перейти к репетитору (или наоборот)?»</b> Да, внутри одной школы это безболезненно: программа единая, педагоги передают контекст друг другу. У нас такой переход — штатная ситуация: часть детей перед ОГЭ уходит на индивидуальный блок и возвращается."),
        ("p", "<b>«Как понять, что выбрали не тот формат?»</b> По динамике за 1–2 месяца. Тревожные признаки: ребёнок ходит без удовольствия, домашние задания — битва, а на вопрос «что нового узнал?» ответа нет. Хорошие: ждёт занятий, вставляет английские фразы в речь, виден прогресс в отчётах педагога. Формат, который «не пошёл», — не ошибка, а данные: меняем его и двигаемся дальше, год на это выделять не нужно."),
        ("h2", "Как это устроено в Фоксинбурге"),
        ("p", "У нас есть оба формата, и мы не «продаём» один в ущерб другому: возрастные программы идут в мини-группах 6–8 человек (например, <a href=\"/mladshie-shkolniki\">английский для младших школьников</a>), а для точечных задач и сложных графиков есть <a href=\"/repetitor\">индивидуальные занятия с репетитором</a> — очно в Долгопрудном или онлайн. Подробнее о выборе между школой и частным педагогом — в статье «<a href=\"/novosti-yazykovaya-shkola-ili-repetitor-kak-vybrat\">Языковая школа или репетитор</a>». Начать разумно с бесплатной диагностики: по её результатам честно скажем, какой формат решит вашу задачу — иногда это группа, иногда репетитор, иногда связка. Диагностика в этом вопросе незаменима ещё и потому, что «правильный» ответ зависит не только от задачи, но и от характера ребёнка: один раскрывается в группе, другому комфортнее начать один на один с педагогом — и это видно уже на первой встрече."),
    ],
    "related": [
        ("Индивидуальные занятия с репетитором", "/repetitor"),
        ("Школа или репетитор: как выбрать", "/novosti-yazykovaya-shkola-ili-repetitor-kak-vybrat"),
        ("Все статьи блога", "/blog"),
    ],
    "faq": [
        ("Когда репетитор лучше группы?", "Когда нужен быстрый результат по конкретной задаче: закрыть пробелы, подготовиться к экзамену в сжатый срок или заниматься в нестандартном темпе. Весь фокус занятия — на одном ученике."),
        ("Когда группа лучше репетитора?", "Когда цель — уверенная речь и долгосрочная мотивация: в мини-группе есть живое общение, соревновательность и друзья. Дети часто лучше держат темп рядом со сверстниками."),
        ("Что дешевле: репетитор или группа?", "Занятие в мини-группе заметно доступнее за час. Индивидуальный формат дороже, но быстрее решает точечные задачи — часто оптимально сочетать: база в группе, точечные темы индивидуально."),
        ("Можно ли начать с репетитором, а потом перейти в группу?", "Да, это рабочая схема для стеснительных детей и отстающих: индивидуально закрываем пробелы и снимаем страх ошибки, затем ребёнок уверенно вливается в группу своего уровня."),
    ],
})

BLOG_POST_11 = dict(BLOG_FEED, **{
    "type": "article",
    "alias": "blog-kak-vyuchit-anglijskie-slova-bystro",
    "title": "Как быстро учить английские слова: 7 рабочих способов для детей и взрослых",
    "description": "Как учить английские слова быстро и надолго: интервальное повторение, контекст, карточки и мини-истории — 7 способов, которые работают у детей и взрослых.",
    "category": "Учим английский",
    "date": "2026-07-02",
    "reading_time": "8 минут чтения",
    "hero_grad": "linear-gradient(135deg,#1c2b36 0%,#24495e 55%,#2d6a8f 100%)",
    "body": [
        ("h2", "Почему слова «не учатся»"),
        ("p", "Главная причина, по которой слова вылетают из головы, — способ, которым их учат: список из двадцати слов с переводом, вызубренный вечером перед диктантом. Так работает кратковременная память: наутро слово «помнишь», через неделю — нет. Долговременная память включается иначе — через повторение с интервалами, через картинку и эмоцию, через использование слова в речи. Хорошая новость: «быстро» и «надолго» не противоречат друг другу, просто нужны правильные приёмы. Ниже — семь способов, которые мы ежедневно используем на занятиях и рекомендуем дома."),
        ("h2", "Способ 1. Интервальное повторение"),
        ("p", "Это самый эффективный приём, подтверждённый исследованиями памяти: слово повторяют не десять раз подряд, а в нарастающие промежутки — через день, через три дня, через неделю, через месяц. Мозг получает сигнал «это нужно не разово, а всегда» и переносит слово в долговременное хранилище. Из приложений это умеют Anki и Quizlet, для детей младшего возраста тот же принцип работает с бумажными карточками: коробка с тремя отделениями «новые — повторяю — знаю». Пять минут в день такой работы дают больше, чем час зубрёжки в воскресенье вечером."),
        ("h2", "Способ 2. Учить слова в контексте, а не по одному"),
        ("ul", [
            "Не «apple — яблоко», а «I eat an apple every morning» — слово, живущее в предложении, запоминается вместе с ситуацией и сразу готово к употреблению.",
            "Для детей контекст — это мини-история: смешная фраза про кота запомнится лучше любого списка.",
            "Для взрослых — собственные примеры: предложение о себе и своей жизни цепляется за личный опыт и держится годами.",
        ]),
        ("h2", "Способ 3. Все каналы восприятия сразу"),
        ("p", "Слово надо увидеть, услышать, произнести и написать. Каждый канал — отдельный «крючок» в памяти. С ребёнком это выглядит так: показали карточку, назвали слово с правильным звучанием (аудио из приложения или голос педагога), ребёнок повторил, обвёл или написал слово, показал жестом предмет. Взрослому достаточно дисциплины: не читать слово про себя молча, а обязательно произносить вслух — звучание включает моторику речи и резко повышает запоминание."),
        ("h2", "Способ 4. Карточки — но правильные"),
        ("ul", [
            "На одной стороне — картинка или слово на английском, на другой — пример в предложении, а не только перевод.",
            "Работаем в обе стороны: с английского на русский (понимание) и с русского на английский (воспроизведение) — второе важнее для речи.",
            "Партия — не больше 7–10 новых слов в день: перегруз убивает эффект.",
            "Слова, которые «падали» дважды, выносим в отдельную стопку и возвращаем через день.",
        ]),
        ("h2", "Способ 5. Цеплять к личному опыту"),
        ("p", "Эмоция — самый сильный клей для памяти. Слово «delicious» запомнится мгновенно, если ребёнок скажет его про любимое бабушкино варенье. Приём «расскажи про своё» работает с любой лексикой: учим цвета — описываем свою комнату, учим еду — вчерашний ужин. На наших занятиях педагоги сознательно строят лексику вокруг жизни учеников: это не просто доброта методики, а работа с механикой памяти."),
        ("h2", "Способ 6. Мало, но каждый день"),
        ("p", "Десять минут ежедневно бьют два часа раз в неделю — это закон распределённого обучения. Сформулируйте правило, которое реально выполнимо в вашей семье: «пять карточек за завтраком», «одна песня по дороге в школу», «три предложения про день перед сном». Маленькая, но ежедневная привычка за месяц даёт 150+ слов в работе — темп, который не снится любителям воскресных марафонов. Это же правило работает и на курсах: в наших <a href=\"/mladshie-shkolniki\">программах для младших школьников</a> домашняя работа дозирована именно по принципу «мало, но каждый день»."),
        ("h2", "Способ 7. Использовать слово сразу"),
        ("p", "Выученное, но не использованное слово «уволняется» мозгом за пару недель. Поэтому финальный шаг обязателен: слово должно пройти через речь — в диалоге на занятии, в рассказе о себе, в переписке, хотя бы в мысленном комментарии («I'm walking my dog»). Идеальная среда для этого — разговорная практика: на курсе <a href=\"/razgovornyj-anglijskij\">разговорного английского</a> новая лексика прогоняется через живые диалоги в том же занятии, пока она свежая. Дома помогает простой ритуал: вечером ребёнок рассказывает день, вставляя три новых слова — сначала с подсказками, через неделю без."),
        ("h2", "Чего не делать"),
        ("ul", [
            "Не учить длинные списки «от и до» — после 15 слова эффективность падает почти до нуля.",
            "Не зубрить слова без звучания: английское написание и произношение живут отдельно, и слово надо слышать.",
            "Не ругать за забывание: забыть слово один-два раза — нормальный этап, а не провал.",
            "Не учить слова «про запас» вне темы: лексика должна быть из жизни ребёнка, иначе она не приживётся.",
        ]),
        ("h2", "Частые вопросы"),
        ("p", "<b>«Сколько слов в день реально выучить?»</b> Ребёнку 7–10 лет — 5–7 новых слов, подростку — 8–10, взрослому — 10–12, но только при условии ежедневного повторения. Если повторять не получается, лучше три слова в день, чем пятнадцать «на один раз»."),
        ("p", "<b>«Помогают ли подписи-стикеры на предметах дома?»</b> Да, но с оговоркой: стикеры работают первые пару недель, потом мозг перестаёт их замечать. Обновляйте набор слов и периодически устраивайте игру «найди стикер и скажи слово»."),
        ("p", "<b>«Как проверить, что слово действительно выучено?»</b> Критерий простой: ребёнок использует его сам, без напоминания, в своей фразе — не узнаёт в списке, а именно воспроизводит. До этого момента слово остаётся в стопке «повторяю», каким бы «лёгким» оно ни казалось."),
        ("h2", "Как мы работаем со словами в Фоксинбурге"),
        ("p", "На занятиях в Фоксинбурге лексика не «задаётся списком», а вводится через игру и историю, повторяется по интервальному принципу и сразу прогоняется в разговоре. Родители видят в отчётах, какие слова в работе и какие уже закреплены. Если хотите понять текущий словарный запас ребёнка, начните с <a href=\"/test-uroven\">бесплатного теста уровня</a> — по результатам педагог скажет, какой объём лексики закрыт и с чего двигаться дальше. Подробнее о методике — в статье «<a href=\"/blog-anglijskij-dlya-detej-3-4-goda\">Английский для детей 3–4 лет</a>», где принципы те же, только в игровой упаковке для самых маленьких."),
    ],
    "related": [
        ("Английский для младших школьников", "/mladshie-shkolniki"),
        ("Как научить ребёнка читать по-английски", "/blog-kak-nauchit-rebenka-chitat-po-anglijski"),
        ("Все статьи блога", "/blog"),
    ],
    "faq": [
        ("Правда ли, что у детей память на слова лучше, чем у взрослых?", "У детей лучше непроизвольное запоминание — через игру и повторение в речи. У взрослых сильнее осознанные стратегии: интервальные повторения и ассоциации дают им сопоставимый результат, если заниматься регулярно."),
        ("Стоит ли учить слова с транскрипцией?", "Школьнику — да: транскрипция помогает читать новые слова самостоятельно. Дошкольнику и взрослому на старте важнее аудио: сначала правильное звучание, буквы потом."),
        ("Помогают ли приложения типа Lingualeo и Duolingo?", "Как дополнение — да: они хорошо держат ежедневный ритм. Но приложение не заменяет использование слова в живой речи — без говорения словарь остаётся пассивным."),
        ("Что делать, если ребёнок путает похожие слова?", "Это нормальный этап: разводите пару слов в разные дни и привязывайте к разным картинкам и жестам. Через две-три недели путаница обычно уходит сама."),
    ],
})

BLOG_POST_12 = dict(BLOG_FEED, **{
    "type": "article",
    "alias": "blog-present-simple-dlya-roditelej",
    "title": "Present Simple без слёз: как объяснить ребёнку главное время английского",
    "description": "Present Simple для детей и родителей: простая формула, окончание -s, do/does, типичные ошибки и домашние игры, которые закрепляют время лучше зубрёжки.",
    "category": "Учим английский",
    "date": "2026-07-07",
    "reading_time": "8 минут чтения",
    "hero_grad": "linear-gradient(135deg,#241a36 0%,#3d2a63 55%,#5a3d99 100%)",
    "body": [
        ("h2", "Зачем вообще это время"),
        ("p", "Present Simple — первое и главное время английского: на нём строятся все остальные. Им описывают распорядок дня, факты, привычки и всё, что «вообще» и «обычно»: I play football, she likes cats, the sun rises in the east. Проблема в том, что в русском языке такой конструкции нет — у нас одно настоящее время, а в английском их несколько, — поэтому ребёнку не на что «повесить» правило. Хорошая новость для родителей: объяснить Present Simple можно без терминов, через одну простую идею и три коротких правила."),
        ("h2", "Одна идея вместо зубрёжки"),
        ("p", "Скажите ребёнку так: «Present Simple — это время про то, что бывает всегда или обычно. Не прямо сейчас, а вообще». И сразу — пример из жизни: «Ты чистишь зубы каждый день? Значит, по-английски это I brush my teeth. Сейчас ты зубы не чистишь, но это правда про тебя». Всё остальное — механика, которая надевается на эту идею. Дети отлично понимают категорию «всегда/обычно», потому что она есть в их жизни: школа каждый день, мультики по субботам, тренировка два раза в неделю."),
        ("h2", "Три правила, которые закрывают 90% случаев"),
        ("ul", [
            "<b>Правило 1.</b> Утверждение: подлежащее + глагол. I play, we read, they swim. Никаких окончаний не надо — это радует детей.",
            "<b>Правило 2.</b> С he/she/it глагол получает -s: he plays, she reads, it rains. Приём «сердитая S»: она приходит только к нему, к ней и к «оно».",
            "<b>Правило 3.</b> Вопрос и отрицание строятся с помощником do/does: Do you play? She does not (doesn't) play. И важно: -s «переезжает» к помощнику — правильно «Does she play?», а не «Does she plays?».",
        ]),
        ("h2", "Типичные ошибки — и как их обходить"),
        ("p", "Первая и самая живая ошибка — потерянная -s: «he play» вместо «he plays». Не исправляйте каждый раз резко — играйте в «охоту за буквой S»: ребёнок сам ищет пропавшую букву в предложениях. Вторая ошибка — лишняя -s после does: «Does she likes?». Объяснение-картинка: «S одна на двоих, забрал does — значит, у глагола пусто». Третья — русская привычка ставить «есть/находится» без глагола: «She in the park». Английскому всегда нужен глагол: She <b>is</b> in the park. Глагол to be — единственный, кто живёт без do/does, и его лучше выучить отдельным маленьким блоком: am/is/are."),
        ("h2", "Домашние игры на закрепление"),
        ("ul", [
            "<b>«Распорядок дня».</b> Ребёнок пересказывает свой день по-английски пятью предложениями: I wake up, I eat breakfast... Через неделю — день мамы или кота, чтобы включить he/she и «сердитую S».",
            "<b>«Правда или ложь».</b> Вы говорите фразу: Cats like fish / Fish like cats. Ребёнок отвечает Yes, they do / No, they don't — и попутно тренирует do/does в ответах.",
            "<b>«20 вопросов».</b> Угадывание предмета вопросами Does it live in water? Is it big? — грамматика встраивается в игру без единого упражнения.",
            "<b>Карточки-превращения.</b> На одной стороне I play, на другой — He plays. Ребёнок «превращает» предложения: быстро, наглядно, без нервов.",
        ]),
        ("h2", "Сколько времени нужно на закрепление"),
        ("p", "Правило выучивается за одно занятие, навык — за 3–4 недели регулярной практики по 5–10 минут в день. Нормальный путь выглядит так: первая неделя — ребёнок говорит правильно, когда думает; вторая — начинает ошибаться и сам себя поправлять (это хороший знак!); к четвёртой — -s проставляется автоматически. Если через месяц время «плавает», это не катастрофа, а сигнал нехватки живой практики: грамматика закрепляется только в речи. Именно поэтому на наших занятиях правило никогда не идёт «отдельным уроком» — оно разбирается и тут же прогоняется в диалогах и играх. О том, как устроена такая подача, читайте в разборе «<a href=\"/blog-rebenok-ne-ponimaet-anglijskij-v-shkole\">Ребёнок не понимает английский в школе</a>» — там же о том, почему школьная грамматика часто «не ложится» без разговорной практики."),
        ("h2", "Когда переходить к следующим временам"),
        ("p", "Не раньше, чем Present Simple срабатывает автоматически хотя бы в утверждениях. Следующий шаг — Present Continuous («прямо сейчас»), и контраст двух времён («обычно» против «сейчас») — лучший способ закрепить оба. Торопиться со «всеми двенадцатью временами» не нужно: для младшего школьника достаточно трёх-четырёх, зато твёрдо."),
        ("h2", "Частые вопросы"),
        ("p", "<b>«Я сам(а) плохо помню грамматику — как помогать ребёнку?»</b> Ваша роль — не объяснять правило (это делает педагог), а создавать практику: игры из этой статьи не требуют от вас идеального английского. Достаточно карточек и десяти минут вечером."),
        ("p", "<b>«В школе дают грамматику иначе — не запутается ли ребёнок?»</b> Нет: идея времени одна и та же, различается только упаковка. Ребёнок, понимающий смысл («про всегда и обычно»), легко переводит его на язык школьных терминов — путаница бывает у тех, кто учил только термины без смысла."),
        ("p", "<b>«Нужно ли заставлять писать предложения или достаточно говорить?»</b> В 7–9 лет приоритет у устной речи, но 2–3 письменных предложения в день полезны: письмо замедляет мысль и заставляет заметить пропавшую -s. Десять письменных предложений вместо трёх — уже перегруз, эффект не растёт."),
        ("h2", "Как грамматика идёт у нас"),
        ("p", "В Фоксинбурге грамматика вводится по принципу «смысл — форма — речь»: сначала ребёнок понимает идею, потом собирает конструкцию, потом использует её в игре и диалоге. На курсе <a href=\"/grammar\">грамматики английского</a> все школьные времена разбираются системно, а в возрастных программах — например, <a href=\"/mladshie-shkolniki\">английском для младших школьников</a> — грамматика встроена в коммуникативную программу. Приходите на <a href=\"/test-uroven\">бесплатную диагностику</a>: покажем, какие темы у ребёнка уже крепкие, а где пробелы."),
    ],
    "related": [
        ("Грамматика английского языка", "/grammar"),
        ("Ребёнок не понимает английский в школе", "/blog-rebenok-ne-ponimaet-anglijskij-v-shkole"),
        ("Все статьи блога", "/blog"),
    ],
    "faq": [
        ("В каком классе проходят Present Simple?", "Обычно во 2–3 классе — это первая грамматическая тема школьной программы. Но комфортно усваивается и раньше, в игровой форме, без терминологии."),
        ("Почему ребёнок пишет правильно, а говорит с ошибками?", "Письмо даёт время подумать, речь — нет. Это нормальный порядок освоения: сначала правило работает «на бумаге», автоматизм в речи приходит через 2–4 недели разговорной практики."),
        ("Нужно ли учить термин «Present Simple» самому ребёнку?", "Название полезно для школьных тестов, но вторично. Важнее, чтобы ребёнок чувствовал идею «обычно и всегда» — с ней он распознает время в любом учебнике."),
        ("Что делать с глаголом to be — он же не подчиняется правилу do/does?", "To be — единственное исключение: у него свои формы am/is/are и вопросы без помощника (Is she at home?). Его лучше выучить отдельным мини-блоком до или сразу после Present Simple."),
    ],
})

BLOG_POST_13 = dict(BLOG_FEED, **{
    "type": "article",
    "alias": "blog-anglijskij-v-5-klasse-chto-zhdat",
    "title": "Английский в 5 классе: что меняется и как не отстать",
    "description": "Английский в 5 классе: как меняются требования после начальной школы, почему дети проседают в первой четверти и что делать родителям, чтобы не отстать.",
    "category": "Школа и учёба",
    "date": "2026-07-10",
    "reading_time": "8 минут чтения",
    "hero_grad": "linear-gradient(135deg,#1e2a1e 0%,#2d4a33 55%,#3d7a4d 100%)",
    "body": [
        ("h2", "Что меняется в 5 классе"),
        ("p", "Пятый класс — перелом в изучении английского. В начальной школе язык был «факультативным по духу»: песенки, картинки, минимум письма, оценки мягкие или отсутствуют. В средней школе английский становится полноценным предметом с системными требованиями: грамматика с правилами и проверочными работами, чтение с пересказом, аудирование в формате, похожем на экзаменационный, и первые словарные диктанты, которые реально влияют на оценку. Добавьте общий стресс перехода в среднюю школу — новые учителя, новый класс, больше предметов, — и станет понятно, почему именно в первой четверти 5 класса английский «проседает» у очень многих детей."),
        ("h2", "Почему отстают даже те, кто «хорошо учил»"),
        ("p", "Причина почти всегда одна: в начальной школе ребёнок жил на пассивном запасе — узнавал слова и фразы, — а в пятом требуется активное воспроизведение по правилам. Разница как между «понимаю, о чём песня» и «сам расскажи». Если база была разговорной и системной, переход проходит мягко. Если английский в начальной школе был «для галочки» — пробелы всплывают в первые два месяца, и это нормально: они были всегда, просто стали видимы. Важно не паниковать и не ругать ребёнка за первые тройки: это не регресс, а диагностика."),
        ("h2", "Пять зон риска первой четверти"),
        ("ul", [
            "<b>Грамматика с системой.</b> Present Simple с -s, вопросы с do/does, to be — теперь нужно не «понимать идею», а безошибочно применять в письменных работах.",
            "<b>Письмо.</b> Требования к написанию резко растут: словарные диктанты и предложения по образцу выявляют, кто писал в начальной школе, а кто — нет.",
            "<b>Аудирование.</b> Запись диктора вместо знакомого голоса учителя — дети, не привыкшие слушать «чужой» английский, теряются.",
            "<b>Лексика по темам.</b> Объём растёт вдвое-втрое, и слова требуются в активе: пересказ, ответы на вопросы, мини-монолог.",
            "<b>Самостоятельность.</b> В 5 классе учитель меньше «ведёт за руку»: записать домашнее задание, подготовиться к проверочной — зона ответственности ученика.",
        ]),
        ("h2", "Что делать летом перед 5 классом"),
        ("p", "Июль и август — лучшее время мягко закрыть разрыв, не превращая каникулы в каторгу. Оптимальный план на лето: 2–3 раза в неделю по 30–40 минут. Приоритеты: во-первых, довести до автоматизма Present Simple — это фундамент всей программы пятого класса; во-вторых, восстановить словарный запас начальной школы через карточки и приложения; в-третьих, вернуть привычку к звучащему английскому — мультфильмы и песни 10–15 минут в день. Если хочется системного разгона без перегруза, для этого хорошо подходит <a href=\"/letnyaya-akademiya\">летняя академия</a>: за пару недель в игровом формате дети повторяют всю базу и входят в сентябрь в тонусе. О подготовке к новому учебному году у нас есть отдельный материал: «<a href=\"/novosti-podgotovka-k-novomu-uchebnomu-godu-anglijskij\">Подготовка к новому учебному году по английскому</a>»."),
        ("h2", "Как помогать в течение года"),
        ("ul", [
            "<b>Домашка без боев.</b> Ритуал «сначала английский, 25 минут, потом перерыв» работает лучше, чем вечерние многочасовые посиделки.",
            "<b>Дневник успехов, а не только ошибок.</b> Отмечайте, что получилось: в 5 классе уверенность важнее отдельной оценки.",
            "<b>Фон дома.</b> Песни, сериал для детей с субтитрами, подкасты — 10 минут звучащего английского в день поддерживают аудирование без усилий.",
            "<b>Связь с учителем.</b> Раз в четверть спрашивайте не «какая оценка», а «где пробел» — ответ покажет, над чем работать.",
            "<b>Не сравнивайте с другими детьми.</b> В 5 классе разброс уровня в классе максимальный — это особенность возраста, а не приговор.",
        ]),
        ("h2", "Когда нужна внешняя помощь"),
        ("p", "Три сигнала, что школьной программы не хватает и стоит подключить курсы или педагога: ребёнок стабильно не справляется с проверочными по грамматике, хотя делает домашку; начал говорить «ненавижу английский» (страх предмета — всегда про пробелы, а не про язык); вы сами видите, что отставание растёт от четверти к четверти. На этом этапе эффективнее всего работают мини-группы своего возраста: в программе <a href=\"/mladshie-shkolniki\">английского для школьников</a> программа синхронизирована со школьной, но подаётся коммуникативно — грамматика закрепляется в речи, а не только в упражнениях. Если пробел точечный и его нужно закрыть быстро, подойдёт формат <a href=\"/repetitor\">индивидуальных занятий</a>. О выборе формата у нас есть честный разбор: «<a href=\"/blog-repetitor-ili-gruppa\">Репетитор или группа</a>»."),
        ("h2", "Про оценки: важное уточнение"),
        ("p", "Первая четверть 5 класса почти всегда даёт оценки ниже привычных — это статистика, а не трагедия. Учитель «калибрует» класс и предъявляет новые требования. Задача семьи в этот период — удержать отношение к предмету: ребёнок, который не боится английского, вытянет оценки ко второй четверти. Ребёнок, запуганный первой тройкой, будет саботировать предмет годами. Поэтому реагируйте на первые сложные недели не контролем, а поддержкой — и при необходимости внешней помощью, пока разрыв маленький."),
        ("h2", "Частые вопросы"),
        ("p", "<b>«Мы в начальной школе почти не писали по-английски — это критично?»</b> Не критично, но требует внимания: выделите летом 10 минут в день на списывание коротких предложений и словарные мини-диктанты. Навык письма нарабатывается быстро, если база устная есть."),
        ("p", "<b>«Нужен ли второй учебник/пособие к школьному?»</b> Как правило, нет: лучше глубже проработать школьную программу, чем распыляться. Исключение — грамматический тренажёр, если учитель его рекомендует. О выборе пособий у нас есть отдельный гайд: «<a href=\"/blog-kak-vybrat-posobie-po-anglijskomu\">Как выбрать учебник по английскому</a>»."),
        ("p", "<b>«Ребёнок говорит, что аудирование на уроках „ничего не понятно” — что делать?»</b> Это самая частая жалоба пятиклассников. Дома включайте короткие аудио и видео на уровне чуть ниже школьного — успех возвращает уверенность, а уверенность возвращает понимание. Отдельный разбор темы: «<a href=\"/blog-audirovanie-kak-nauchitsya-ponimat\">Как научиться понимать английскую речь на слух</a>»."),
        ("h2", "Как мы помогаем пятиклассникам"),
        ("p", "В Фоксинбурге переход в среднюю школу — известный рубеж, и мы готовимся к нему заранее: в программах для младших школьников с 4 класса добавляем письменные форматы и «экзаменационное» аудирование, чтобы в сентябре пятого класса дети встречали знакомые задания, а не сюрпризы. Если ваш ребёнок идёт в 5 класс и вы сомневаетесь в базе, начните с <a href=\"/test-uroven\">бесплатной диагностики</a>: по итогам скажем честно, что закрыть летом, а что подтянется в группе в течение первой четверти."),
    ],
    "related": [
        ("Английский для младших школьников", "/mladshie-shkolniki"),
        ("Летняя академия", "/letnyaya-akademiya"),
        ("Все статьи блога", "/blog"),
    ],
    "faq": [
        ("Почему в 5 классе падают оценки по английскому?", "Растут требования: грамматика в письменных работах, аудирование, самостоятельность. Падение в первой четверти — массовое явление; оценки обычно выравниваются ко второй четверти при регулярной работе."),
        ("Стоит ли нанимать помощь «про запас» до первых двоек?", "Если летняя диагностика показывает пробелы — да: закрывать маленький разрыв проще и дешевле, чем накопленный за год. Если база в порядке, достаточно поддерживающего режима дома."),
        ("Мой ребёнок в 5 классе начал говорить, что «английский не нужен» — как реагировать?", "Это почти всегда защитная реакция на трудности, а не убеждение. Снизьте давление, верните успешный опыт (лёгкие тексты, любимые песни) и найдите, где именно сломалось понимание — обычно это одна-две темы."),
        ("Помогает ли изучение английского по мультфильмам в этом возрасте?", "Да, как поддержка аудирования и мотивации: 10–15 минут в день. Но школьную грамматику мультфильмы не закроют — она требует осознанной практики."),
    ],
})

BLOG_POST_14 = dict(BLOG_FEED, **{
    "type": "article",
    "alias": "blog-skolko-stoit-anglijskij-dlya-rebenka",
    "title": "Сколько стоит английский для ребёнка в Долгопрудном: честный разбор цен",
    "description": "Цены на английский для детей в Долгопрудном: сколько стоят группы, индивидуальные занятия и пробный урок, из чего складывается цена и как вернуть 13% по налоговому вычету.",
    "category": "Родителям",
    "date": "2026-07-14",
    "reading_time": "7 минут чтения",
    "hero_grad": "linear-gradient(135deg,#2b1f14 0%,#5a4426 55%,#8a6a35 100%)",
    "body": [
        ("h2", "Коротко: реальные цифры"),
        ("p", "Говорим открыто, потому что вопрос цены — первый вопрос каждой семьи, и прятать его нет смысла. В Фоксинбурге занятия в мини-группах стоят <b>от 9000 ₽ в месяц</b>, индивидуальные занятия с педагогом — <b>2500 ₽ за час</b>, пробное занятие — <b>1125 ₽</b>. Это цены на момент публикации; актуальные тарифы по всем программам всегда собраны на странице <a href=\"/tseny\">цен</a>. А теперь — что стоит за этими цифрами и как сравнивать предложения разных школ и репетиторов, не ошибившись."),
        ("h2", "Из чего складывается цена занятия"),
        ("p", "Цена часа английского — это не «расценка педагога», а сумма нескольких компонентов. Квалификация и постоянное обучение педагогов (методисты, аттестации, повышение квалификации). Размер группы: в группе из 6–8 человек каждый ребёнок получает в разы больше внимания, чем в группе из 15, — и это главный фактор цены группового формата. Методика и материалы: лицензионные учебники, онлайн-платформы, собственные разработки. Помещение: очные занятия в Долгопрудном — это аренда и оборудование классов. Наконец, легальность: школа с образовательной лицензией несёт расходы, которых нет у репетитора «в свободном полёте», — но именно лицензия даёт вам налоговый вычет и оплату маткапиталом, о чём ниже."),
        ("h2", "Сравниваем форматы по-честному"),
        ("ul", [
            "<b>Мини-группа (6–8 детей), от 9000 ₽/мес.</b> При занятиях два раза в неделю выходит самая выгодная цена за час — плюс живая разговорная практика со сверстниками, которую не заменит ни один формат один-на-один.",
            "<b>Индивидуально, 2500 ₽/час.</b> Дороже за час, но каждая минута работает на конкретную задачу вашего ребёнка: пробелы, экзамен, нестандартный темп. Оптимально как точечный инструмент.",
            "<b>Частный репетитор без школы.</b> Цены разбросаны сильно — от очень низких до выше школьных. Проблема не цена, а непредсказуемость: нет методики, отчётности и замены при болезни педагога.",
            "<b>Онлайн-школы.</b> Часто дешевле очных, но сравнивайте размер групп и качество обратной связи: «онлайн на 20 детей» и «мини-группа онлайн» — разные продукты.",
        ]),
        ("p", "Подробное сравнение форматов по задачам — не по ценнику, а по результату — мы делали в статье «<a href=\"/blog-repetitor-ili-gruppa\">Репетитор или группа</a>». Там же таблица: какая ситуация какой формат требует."),
        ("h2", "Скрытые скидки: как вернуть часть суммы"),
        ("p", "Два легальных способа заметно снизить реальную стоимость обучения, о которых забывают многие родители. Первый — <b>налоговый вычет 13%</b>: школа работает по образовательной лицензии, поэтому вы можете вернуть 13% от стоимости обучения ребёнка через налоговую. На годовом абонементе это ощутимая сумма — по сути, полтора-два месяца занятий в подарок от государства. Второй — <b>материнский капитал</b>: обучение в лицензированной школе можно оплачивать средствами маткапитала. Оба механизма — стандартная практика, мы помогаем с документами и справками для налоговой."),
        ("h2", "За что стоит платить, а за что — нет"),
        ("p", "Красные флаги при любой цене: группы больше 10–12 детей под вывеской «разговорной практики»; отсутствие пробного занятия или диагностики; цена «подозрительно дёшево» при обещании «свободного английского за год»; отказ показать лицензию. Зелёные флаги: школа с историей (мы работаем с 2020 года), открытые отзывы с высоким рейтингом (у Фоксинбурга — 5.0), понятная методика, отчётность для родителей и честное «это не наш формат» вместо «у нас всё для всех»."),
        ("h2", "Пробное занятие: как купить один раз и понять всё"),
        ("p", "Прежде чем платить за месяц, используйте пробное занятие (у нас — 1125 ₽): за один урок видно и отношение педагога к детям, и реальный размер группы, и главное — реакцию вашего ребёнка. Вопрос после пробного должен звучать не «понравилось?», а «что делали? что запомнил?». Если ребёнок рассказывает и хочет ещё — формат ваш. Если «нормально, но не хочу» — ищите дальше, деньги на нелюбимый формат потратите зря в любом случае. Пробное занятие проводится в обоих наших филиалах в Долгопрудном — на Лихачёвском шоссе, 76к1 и на проспекте Ракетостроителей, 9к3, — выбирайте ближайший к дому: логистика в длинном курсе важнее, чем кажется."),
        ("h2", "Частые вопросы о ценах"),
        ("p", "<b>«Почему у кого-то дешевле?»</b> Почти всегда ответ — размер группы или квалификация педагога. Считайте не цену месяца, а цену результата: дешёвый год без прогресса дороже честного полугода с движением."),
        ("p", "<b>«Можно ли платить помесячно?»</b> Да, абонемент оплачивается помесячно — долгосрочных «продаж годовых пакетов» у нас нет. Это дисциплинирует и нас: качество должно удерживать семью каждый месяц, а не договор."),
        ("p", "<b>«Входят ли учебники в стоимость?»</b> Зависит от программы: большая часть материалов включена, по лицензионным учебникам администратор честно скажет стоимость заранее, до оплаты абонемента — сюрпризов в середине года не будет."),
        ("p", "<b>«А если ребёнку не подойдёт группа после оплаты?»</b> Такое бывает редко (пробное занятие и диагностика отсекают большинство промахов), но решается штатно: переводим в другую группу по уровню или переносим оплату на индивидуальный формат. Деньги не «сгорают» — решаем задачу ребёнка, а не удерживаем оплату."),
        ("h2", "Итог"),
        ("p", "Честный ответ на вопрос «сколько стоит английский для ребёнка в Долгопрудном»: регулярные занятия в хорошей мини-группе — от 9000 ₽ в месяц, индивидуальный формат — 2500 ₽ в час, а проверить формат до серьёзных трат можно за 1125 ₽ на пробном занятии. С налоговым вычетом 13% реальная цена заметно ниже номинальной. Смотрите актуальные тарифы на странице <a href=\"/tseny\">цен</a> или приходите на бесплатную <a href=\"/test-uroven\">диагностику уровня</a> — заодно честно скажем, какой формат под вашу задачу оптимален по бюджету."),
    ],
    "related": [
        ("Цены на программы", "/tseny"),
        ("Репетитор или группа", "/blog-repetitor-ili-gruppa"),
        ("Все статьи блога", "/blog"),
    ],
    "faq": [
        ("Сколько стоит английский для ребёнка в Долгопрудном?", "В Фоксинбурге мини-группы — от 9000 ₽ в месяц, индивидуальные занятия — 2500 ₽/час, пробное занятие — 1125 ₽. Актуальные тарифы — на странице цен."),
        ("Можно ли получить налоговый вычет за занятия английским?", "Да: школа работает по образовательной лицензии, поэтому родители могут вернуть 13% стоимости обучения ребёнка через налоговый вычет. Мы предоставляем все документы."),
        ("Принимаете ли вы материнский капитал?", "Да, обучение в лицензированной школе можно оплачивать средствами материнского капитала — администраторы помогут оформить заявление."),
        ("Что входит в стоимость месяца занятий в группе?", "Все занятия по расписанию (обычно два раза в неделю), работа педагога, базовые материалы и обратная связь для родителей. По отдельным учебникам стоимость озвучивается заранее."),
    ],
})

BLOG_POST_15 = dict(BLOG_FEED, **{
    "type": "article",
    "alias": "blog-chtenie-na-anglijskom-s-chego-nachat",
    "title": "Чтение на английском: с каких книг начать ребёнку и взрослому",
    "description": "С каких книг начать читать на английском: graded readers по уровням, списки для детей, подростков и взрослых и правила, которые делают чтение привычкой.",
    "category": "Учим английский",
    "date": "2026-07-17",
    "reading_time": "8 минут чтения",
    "hero_grad": "linear-gradient(135deg,#26161f 0%,#4d2440 55%,#7a3560 100%)",
    "body": [
        ("h2", "Почему чтение — главный ускоритель английского"),
        ("p", "Из всех домашних привычек чтение даёт самый высокий возврат на вложенное время: оно одновременно расширяет словарь, тренирует грамматику «на подсознании» (конструкции запоминаются как готовые куски) и учит думать на языке. Но есть условие — книга должна быть правильного уровня. Ошибка большинства: взять «Гарри Поттера» в оригинале через год занятий, споткнуться о пять незнакомых слов в каждой строке и бросить чтение на английском навсегда. Правило простое: в книге для удовольствия вы должны понимать 95–98% слов без словаря. Это значит — начинать не с оригиналов, а с адаптированных книг."),
        ("h2", "Graded readers: книги, созданные для изучающих"),
        ("p", "Адаптированные книги (graded readers) — это та же литература, переписанная на контролируемом словаре: уровень Starter — 300 самых частых слов, Elementary — 600, дальше по нарастающей до Upper-Intermediate. Издательства Penguin Readers, Oxford Bookworms и Cambridge Readers размечают каждую книгу по уровням, так что подобрать «свою» несложно. Внутри — и классика, и детективы, и нон-фикшн: это не «детские упрощения», а полноценные истории. Главный эффект: читатель получает опыт «я прочитал целую книгу на английском» — а этот опыт тянет за собой следующую книгу."),
        ("h2", "С чего начать ребёнку"),
        ("ul", [
            "<b>5–7 лет.</b> Картиночные книги с одной фразой на разворот и аудиосопровождением: серии Usborne First Reading, Oxford Reading Tree. Ребёнок «читает» вместе с диктором — так чтение и аудирование тренируются вместе.",
            "<b>7–10 лет.</b> Простые истории с повторами конструкций: Winnie the Witch, Flat Stanley, адаптированные сказки уровня Starter–Elementary. В этом возрасте работает правило «книга про любимое»: динозавры, футбол, принцессы — интерес важнее «классики».",
            "<b>10–12 лет.</b> Адаптированные приключения и детективы уровня Elementary–Pre-Intermediate, комиксы и графические романы — картинка поддерживает понимание и не даёт споткнуться.",
        ]),
        ("p", "Если ребёнок только учится читать по-английски и пока не готов к книгам, начните с фонетики и коротких слов — у нас есть пошаговый разбор: «<a href=\"/blog-kak-nauchit-rebenka-chitat-po-anglijski\">Как научить ребёнка читать по-английски</a>». А системная работа с чтением — отдельный трек: на курсе <a href=\"/reading\">чтения на английском</a> дети проходят путь от звуков к самостоятельному чтению адаптированных книг."),
        ("h2", "С чего начать подростку"),
        ("p", "Подросткам адаптированные «детские» книги часто кажутся скучными — и это решаемо. Ставка на увлечения: нон-фикшн про игры, блогеров, спорт (у Penguin Readers много современного нон-фикшна); комиксы и манга на английском — формат уважительный для возраста; адаптированные хиты вроде Harry Potter (уровень Pre-Intermediate) — мотивация «читаю то же, что взрослые»; наконец, fan fiction и форумы по любимой вселенной — не «книга», но чтение массовое и добровольное. Принцип один: пусть читает «неполезное», лишь бы читал. Качество текстов подтянется следом за привычкой."),
        ("h2", "С чего начать взрослому"),
        ("ul", [
            "Перечитайте на английском книгу, которую любите по-русски: знакомый сюжет компенсирует половину незнакомых слов.",
            "Возьмите graded reader уровнем ниже вашего: «лёгкая» книга включает режим потока, а не режим словаря.",
            "Нон-фикшн по вашей профессии: лексика знакома по работе, поэтому порог входа ниже, чем в художественной литературе.",
            "Короткие рассказы вместо романов: законченная история за вечер даёт регулярное чувство победы.",
        ]),
        ("p", "Взрослым мы рекомендуем связку «книга + аудиокнига»: слушаете главу и читаете её глазами. Так растёт и словарь, и понимание на слух — а аудирование у взрослых обычно самое слабое место, мы разбирали его в статье «<a href=\"/blog-audirovanie-kak-nauchitsya-ponimat\">Как научиться понимать английскую речь на слух</a>»."),
        ("h2", "Правила, которые делают чтение привычкой"),
        ("ul", [
            "<b>Правило 5 страниц.</b> Читать мало, но каждый день: пять страниц до сна бьют «час в воскресенье».",
            "<b>Без словаря в руке.</b> Незнакомое слово подчеркнули и читаем дальше; смотрим только слова, без которых непонятен смысл абзаца.",
            "<b>Вслух — детям, про себя — взрослым.</b> Ребёнку чтение вслух тренирует произношение; взрослому оно замедляет, лучше читать молча и проговаривать любимые фразы.",
            "<b>Бросать разрешено.</b> Книга, которая «не идёт» после 20 страниц, заменяется без угрызений: задача — привычка, а не подвиг.",
        ]),
        ("h2", "Частые вопросы"),
        ("p", "<b>«Электронная книга или бумажная?»</b> Для взрослых электронная удобнее: встроенный словарь по тапу снимает главное препятствие. Для детей младшего возраста лучше бумага: картинки, перелистывание и меньше экранов."),
        ("p", "<b>«Нормально ли читать билингвы (параллельный перевод)?»</b> На старте — да, но с дисциплиной: сначала абзац на английском, перевод — только для проверки. Если глаз привычно убегает на русскую колонку, билингва превращается в иллюзию чтения."),
        ("p", "<b>«Как понять, что пора переходить на оригиналы?»</b> Когда адаптированная книга вашего уровня читается легко и вы ловите себя на «хочу настоящий текст». Обычно это уровень Intermediate: берите современную прозу (не классику XIX века) и снова — правило 95% понятных слов."),
        ("h2", "Как чтение встроено в наши программы"),
        ("p", "В Фоксинбурге чтение — не факультатив, а часть методики: в возрастных программах дети читают адаптированные книги своего уровня и обсуждают их на занятиях, а на курсе <a href=\"/reading\">чтения</a> навык ставится системно — от фонетики до свободного чтения. Подобрать стартовую точку поможет <a href=\"/test-uroven\">бесплатная диагностика</a>: по её результатам педагог посоветует и уровень graded readers для дома."),
    ],
    "related": [
        ("Курс чтения на английском", "/reading"),
        ("Как научить ребёнка читать по-английски", "/blog-kak-nauchit-rebenka-chitat-po-anglijski"),
        ("Все статьи блога", "/blog"),
    ],
    "faq": [
        ("Что такое graded readers и где их брать?", "Это книги, адаптированные под контролируемый словарь по уровням (Starter, Elementary и далее) — издательства Penguin Readers, Oxford Bookworms, Cambridge Readers. Есть бумажные и электронные версии, многие с аудио."),
        ("Можно ли начинать чтение с «Гарри Поттера» в оригинале?", "Можно, когда уровень близок к Intermediate и вы понимаете 95% слов на странице. Раньше — лучше адаптированная версия той же истории: сюжет тот же, опыт успешный."),
        ("Сколько минут в день ребёнку читать на английском?", "10–15 минут ежедневно достаточно: регулярность важнее объёма. Лучше 5 страниц каждый день, чем час раз в неделю."),
        ("Нужно ли выписывать и учить все незнакомые слова из книги?", "Нет: только частотные слова, которые встретились два-три раза. Единичные редкие слова безопасно пропускать — они не входят в активный словарь этого уровня."),
    ],
})

BLOG_POST_16 = dict(BLOG_FEED, **{
    "type": "article",
    "alias": "blog-kak-vybrat-posobie-po-anglijskomu",
    "title": "Как выбрать учебник по английскому: гайд для родителей",
    "description": "Как выбрать учебник и пособия по английскому для ребёнка: британские линейки, грамматические тренажёры, фонетика, соответствие уровню и чего избегать.",
    "category": "Родителям",
    "date": "2026-07-21",
    "reading_time": "8 минут чтения",
    "hero_grad": "linear-gradient(135deg,#14222b 0%,#1f4550 55%,#2a6f7a 100%)",
    "body": [
        ("h2", "Сначала главное: пособие — инструмент, а не программа"),
        ("p", "Родители часто ищут «самый лучший учебник», надеясь, что правильная книга сама научит ребёнка. Не научит: язык учится в общении и практике, а учебник — это опорная рамка, по которой движется педагог или семья. Поэтому задача выбора звучит иначе: найти пособие, которое соответствует уровню и возрасту ребёнка, закрывает конкретную задачу и не убивает интерес. Разберём по полкам."),
        ("h2", "Основные учебники: британские линейки против российских"),
        ("p", "Главный водораздел — коммуникативные британские курсы (Kid's Box, Super Minds, English File, Solutions для подростков) и традиционные российские УМК, ориентированные на школьную программу. Британские курсы строятся вокруг говорения: каждая тема — от лексики к диалогам и проектам, плюс аудио, видео и онлайн-платформа. Российские учебники сильнее по грамматической систематичности и ближе к школьным проверочным. Идеал зависит от цели: для живого языка — британская линейка, для поддержки школьной программы — российский УМК плюс коммуникативная практика на курсах. В Фоксинбурге возрастные программы — например, <a href=\"/doshkolniki\">английский для дошкольников</a> и <a href=\"/mladshie-shkolniki\">для младших школьников</a> — построены на коммуникативных курсах именно поэтому."),
        ("h2", "Чек-лист выбора основного учебника"),
        ("ul", [
            "<b>Уровень.</b> Учебник должен соответствовать уровню ребёнка (Starters/Movers/Flyers, A1–A2), а не возрасту «по паспорту» — проверяйте на первых уроках: ребёнок должен понимать 80% материала без посторонней помощи.",
            "<b>Возрастная подача.</b> Курс для 7-летних и курс для 12-летних на одном уровне A1 — разные книги: темы, картинки, темп. Не покупайте подростку «детский» учебник и наоборот.",
            "<b>Аудио и видео.</b> Учебник без качественного звукового сопровождения в 2026 году — деньги на ветер: произношение ставится только со звучащей моделью.",
            "<b>Четвёрка навыков.</b> Хороший курс в каждом модуле работает с говорением, аудированием, чтением и письмом — а не сводится к упражнениям «вставь слово».",
            "<b>Онлайн-компонент.</b> Платформа с интерактивными заданиями продлевает занятие дома и снимает с родителей роль «проверяющего».",
        ]),
        ("h2", "Специальные пособия: что докупить под задачу"),
        ("ul", [
            "<b>Фонетика и чтение.</b> Для старта чтения — курсы на базе phonics (например, Oxford Phonics World): звукобуквенные соответствия вместо зубрёжки слов целиком. Подробнее о методе — в статье «<a href=\"/blog-kak-nauchit-rebenka-chitat-po-anglijski\">Как научить ребёнка читать по-английски</a>».",
            "<b>Грамматические тренажёры.</b> Если школьная грамматика «сыплется» — серия Grammar Friends или подобные: одна тема — один разворот, правило картинкой и тренировка. О системе разбора времён читайте в «<a href=\"/blog-present-simple-dlya-roditelej\">Present Simple без слёз</a>».",
            "<b>Словари-картинки.</b> Для дошкольников и младших школьников тематические словари (дом, еда, животные) работают лучше списков: визуальная память ребёнка — главный ресурс.",
            "<b>Адаптированные книги.</b> Graded readers — обязательное дополнение любого курса; как выбрать уровень, рассказали в «<a href=\"/blog-chtenie-na-anglijskom-s-chego-nachat\">Чтение на английском: с чего начать</a>».",
            "<b>Экзаменационные тренажёры.</b> К ОГЭ/ЕГЭ — только официальные форматы последних лет; устаревшие сборники вредны, потому что формат заданий меняется.",
        ]),
        ("h2", "Чего избегать"),
        ("ul", [
            "«Самоучитель английского за 16 часов» и подобные: чудо-методики не существует, а разочарование после них — вполне реальное.",
            "Советские по духу «учебники перевода»: предложения вида «переведите 30 предложений» не учат языку, они учат переводить упражнения.",
            "Пособия без ответов (keys): для домашней работы ключи обязательны, иначе родитель превращается в экзаменатора без квалификации.",
            "Покупка «с запасом на три года»: уровень и интересы ребёнка меняются быстрее, чем вы успеете открыть запасные тома.",
            "Пиратские PDF: у лицензионного учебника — работающее аудио, онлайн-платформа и корректная вёрстка, у скана — ничего из этого.",
        ]),
        ("h2", "Сколько пособий — это достаточно"),
        ("p", "Рабочий минимум семьи, где ребёнок занимается на курсах: основной учебник (его даёт школа или курсы), один тренажёр под слабое место (грамматика или чтение) и адаптированные книги для удовольствия. Всё. Стопка из пяти пособий не ускоряет обучение — она создаёт чувство вины и визуальный шум. Лучше глубже пройти один курс, чем поверхностно три."),
        ("h2", "Частые вопросы"),
        ("p", "<b>«Нужен ли ребёнку отдельный учебник, если он ходит на курсы?»</b> Обычно нет: курсы работают по своей программе и материалам. Докупать стоит только то, что педагог рекомендует под конкретный пробел."),
        ("p", "<b>«Британский учебник или американский — есть разница?»</b> Для ребёнка разница минимальна: современные курсы дают оба варианта произношения. Выбирайте по качеству курса, а не по «диалекту» — на уровне школы это не имеет значения."),
        ("p", "<b>«Помогут ли пособия подготовиться к ВПР?»</b> Частично: тренажёры в формате ВПР полезны за 1–2 месяца до работы, но базу они не заменяют. Как устроена ВПР по английскому в 4 классе и что реально проверяют — в нашем разборе «<a href=\"/blog-vpr-po-anglijskomu-4-klass\">ВПР по английскому</a>»."),
        ("h2", "Как подбираем материалы мы"),
        ("p", "В Фоксинбурге программы собраны на проверенных коммуникативных курсах, а дополнительные пособия педагог рекомендует индивидуально — по результатам <a href=\"/test-uroven\">диагностики уровня</a>. Это избавляет родителей от лотереи в книжном: вы точно знаете, какая книга нужна вашему ребёнку сейчас, а не «вообще хорошая по отзывам». Приходите на бесплатную диагностику — покажем, с чего начинать, и честно скажем, какие пособия из уже купленных пригодятся."),
    ],
    "related": [
        ("Английский для младших школьников", "/mladshie-shkolniki"),
        ("Чтение на английском: с чего начать", "/blog-chtenie-na-anglijskom-s-chego-nachat"),
        ("Все статьи блога", "/blog"),
    ],
    "faq": [
        ("Какой учебник английского лучший для ребёнка?", "Универсально «лучшего» нет: важно соответствие уровню, возрасту и цели. Для живого языка — коммуникативные британские курсы (Kid's Box, Super Minds), для школьной поддержки — российский УМК плюс разговорная практика."),
        ("Нужно ли покупать пособия самим, если ребёнок занимается на курсах?", "Не обязательно: курсы дают свои материалы. Самостоятельно имеет смысл докупать только адаптированные книги для чтения и тренажёр, который педагог порекомендовал под конкретный пробел."),
        ("Можно ли заниматься по бесплатным PDF учебников из интернета?", "Технически можно, но у лицензионного учебника есть аудио, видео и онлайн-платформа — без них курс теряет половину ценности, а у сканов всё это отсутствует или не работает."),
        ("Что важнее: учебник или приложение?", "Разные задачи: учебник даёт систему, приложение — ежедневный ритм и словарную практику. Оптимально сочетание: курс/учебник как остов, приложение — как 10-минутная ежедневная зарядка."),
    ],
})

BLOG_POST_17 = dict(BLOG_FEED, **{
    "type": "article",
    "alias": "blog-letnij-intensiv-itogi-i-plany",
    "title": "Летний интенсив: зачем нужен и как выжать максимум за 2 недели",
    "description": "Летний интенсив по английскому для детей: почему 2 недели летом дают эффект месяцев, кому подходит формат и как закрепить результат до сентября.",
    "category": "Родителям",
    "date": "2026-07-28",
    "reading_time": "8 минут чтения",
    "hero_grad": "linear-gradient(135deg,#2a1e12 0%,#6b4a1e 55%,#a3742a 100%)",
    "body": [
        ("h2", "Почему лето — золотое время для английского"),
        ("p", "В учебном году английский конкурирует за внимание ребёнка с десятью предметами, кружками и домашними заданиями. Летом конкурентов нет — и это главная причина, почему две недели летнего интенсива по эффекту часто равны двум-трём месяцам занятий в сезоне. Вторая причина — плотность: ежедневный контакт с языком запускает механизм «погружения», который при занятиях дважды в неделю просто не успевает включиться. Ребёнок начинает думать на английском уже на третий-четвёртый день — это отмечают и педагоги, и родители. Третья причина профилактическая: за лето без практики дети теряют заметную часть наработанного за год — так называемый summer slide; интенсив не просто удерживает уровень, а уводит вперёд."),
        ("h2", "Что такое интенсив и чем он отличается от лагеря"),
        ("p", "Летний лагерь с английским — это в первую очередь отдых и анимация с языковым фоном. Интенсив — учебный формат: компактная программа с измеримой целью (закрыть тему, разогнать говорение, подготовиться к переходу в новый класс), занятия каждый день, мини-группы, педагог вместо вожатого. При этом формат остаётся летним: игры, проекты, театрализация, выходы на улицу — просто весь игровой механизм работает на языковую задачу. В нашей <a href=\"/letnyaya-akademiya\">Летней академии</a> день построен именно так: утренний языковой блок, затем проектная работа и игры на английском — ребёнок устаёт как от хорошего лагеря, а получает как от курса."),
        ("h2", "Кому интенсив подходит особенно"),
        ("ul", [
            "<b>Будущим первоклассникам и пятиклассникам.</b> Вход в новую школьную реальность с рабочим английским вместо «всё забыл за лето». О переходе в 5 класс — подробно в статье «<a href=\"/blog-anglijskij-v-5-klasse-chto-zhdat\">Английский в 5 классе</a>».",
            "<b>Тем, у кого пробелы.</b> Годовой разрыв закрывается интенсивом мягче, чем догоняющими занятиями в сезоне, когда на ребёнка и так давит школа.",
            "<b>Стыдливым говорунам.</b> Ежедневное общение в мини-группе снимает разговорный барьер за дни, а не месяцы — мы описывали этот механизм в «<a href=\"/blog-razgovornyj-barjer-u-podrostka\">Как подростку преодолеть страх говорить</a>».",
            "<b>Занятым семьям.</b> Две недели днём — и ребёнок при деле с пользой, пока родители работают.",
            "<b>Тем, кто хочет попробовать школу.</b> Интенсив — идеальный «тест-драйв» методики и педагогов перед записью на год.",
        ]),
        ("h2", "Как устроена методика двух недель"),
        ("p", "Принцип — спираль: каждый день вводится немного нового и многократно переиспользуется вчерашнее. Утром — основной блок (лексика и грамматика темы через игру), днём — закрепление в проекте: готовим спектакль, снимаем видеоролик, делаем презентацию, играем в квест. Язык становится инструментом, а не предметом — это и есть коммуникативный подход в чистом виде. К концу первой недели дети перестают замечать, что говорят по-английски; к концу второй — родители на финальном показе обычно спрашивают «это точно мой ребёнок?»."),
        ("h2", "Как родителю усилить эффект"),
        ("ul", [
            "Не спрашивайте «что выучил?» — спрашивайте «что сегодня было смешного?»: ребёнок перескажет день и невольно покажет все новые слова.",
            "Держите дома лёгкий английский фон в дни интенсива: песни из программы, любимый мульт на английском 15 минут — погружение не должно обрываться на пороге.",
            "Не устраивайте «экзамен» в конце: давление съедает главный результат интенсива — отношение «английский — это круто».",
            "Приходите на финальное мероприятие: публичный успех — сильнейший закрепитель мотивации на весь следующий год.",
        ]),
        ("h2", "Как не потерять результат к сентябрю"),
        ("p", "Двухнедельный подъём — это капитал, который либо прирастает, либо тает. Три способа сохранить: во-первых, лёгкий поддерживающий режим до конца лета — 10 минут карточек или одна адаптированная книга в неделю (о том, как выбрать книгу, — в статье «<a href=\"/blog-chtenie-na-anglijskom-s-chego-nachat\">Чтение на английском</a>»); во-вторых, ранняя запись на сентябрьскую программу — переход «интенсив → группа» без паузы сохраняет до 80% прироста; в-третьих, домашние ритуалы из жизни: ужин с «словом дня», короткие диалоги по дороге. Перед стартом учебного года полезно пройти <a href=\"/test-uroven\">диагностику уровня</a> — она покажет, что закрепилось, и определит ребёнка в группу точного уровня."),
        ("h2", "Частые вопросы про интенсив"),
        ("p", "<b>«Не устанет ли ребёнок от ежедневных занятий?»</b> Устаёт от школы — сидячей и оценочной. Летний формат игровой и подвижный: усталость как от лагеря, приятная. Признак правильного интенсива — ребёнок утром сам собирается."),
        ("p", "<b>«Ребёнок с нулевым уровнем — возьмут ли?»</b> Да: группы комплектуются по уровню, и для начинающих интенсив — лучший старт: за две недели формируется база приветствий, первых фраз и, главное, положительное первое впечатление от языка."),
        ("p", "<b>«Что лучше: одна смена две недели или две смены подряд?»</b> Для большинства детей оптимальна одна смена плюс поддерживающий режим. Две подряд — вариант для целевых задач (например, подготовка к переходу или экзамену), но с согласия ребёнка: насильственный второй заход сжигает накопленную мотивацию."),
        ("h2", "Летняя академия в Фоксинбурге"),
        ("p", "Наша <a href=\"/letnyaya-akademiya\">Летняя академия</a> проходит в обоих филиалах в Долгопрудном — на Лихачёвском шоссе и проспекте Ракетостроителей. Группы по возрасту и уровню, педагоги те же, что ведут годовые программы, финальный показ для родителей в конце каждой смены. Количество мест ограничено размером мини-групп — уточняйте расписание смен у администраторов или записывайтесь на диагностику, чтобы забронировать уровень заранее."),
    ],
    "related": [
        ("Летняя академия", "/letnyaya-akademiya"),
        ("Английский перед 1 сентября: план на неделю", "/blog-anglijskij-pered-1-sentyabrya"),
        ("Все статьи блога", "/blog"),
    ],
    "faq": [
        ("Что реально можно достичь за 2 недели интенсива?", "Снять разговорный барьер, закрыть одну-две грамматические темы до автоматизма и добавить 80–120 слов в активный словарь. Главный результат — смена отношения к языку с «предмет» на «инструмент»."),
        ("Интенсив или обычные занятия два раза в неделю летом — что лучше?", "Для разгона и закрытия пробелов — интенсив: ежедневная плотность даёт эффект погружения. Для спокойной поддержки уровня достаточно обычного режима."),
        ("С какого возраста можно на летний интенсив?", "В нашей Летней академии — с дошкольного возраста: для малышей программа полностью игровая, для школьников добавляется проектный блок. Группы делятся по возрасту и уровню."),
        ("Что делать после интенсива, чтобы не растерять результат?", "10 минут лёгкой практики в день до конца лета (карточки, песни, адаптированная книга) и продолжение в группе с сентября без длинной паузы — так сохраняется до 80% прироста."),
    ],
})

BLOG_POST_18 = dict(BLOG_FEED, **{
    "type": "article",
    "alias": "blog-oshibki-v-anglijskom-top-15",
    "title": "15 ошибок в английском, которые делают все русские",
    "description": "15 типичных ошибок русскоязычных в английском: I am agree, can to go, how are you на «нормально» — разбираем, почему они липнут и как от них избавиться.",
    "category": "Учим английский",
    "date": "2026-08-05",
    "reading_time": "9 минут чтения",
    "hero_grad": "linear-gradient(135deg,#2b1414 0%,#5e2424 55%,#8f3a2d 100%)",
    "body": [
        ("h2", "Почему русские ошибаются одинаково"),
        ("p", "Почти все типичные ошибки — это не «плохой английский», а кальки с русского: мы строим английскую фразу по русским чертежам. Знакомство с этими ловушками — самый быстрый способ улучшить речь без нового учебника: вы просто перестаёте говорить «по-русски английскими словами». Собрали 15 самых живучих ошибок, которые слышим у учеников всех возрастов, — с объяснением, откуда каждая растёт, и как её переучить. Детям особенно полезно знать их «в лицо» до того, как они укоренятся."),
        ("h2", "Грамматические кальки"),
        ("ul", [
            "<b>1. I am agree.</b> Калька «я согласен» (краткое прилагательное). По-английски agree — глагол: I agree. Без am.",
            "<b>2. Can to go / must to do.</b> После can/must/should инфинитив идёт без to: I can swim. Запоминалка: «модальные глаголы жадные — to не делят ни с кем».",
            "<b>3. He don't / she don't.</b> Сердитая S: в третьем лице — doesn't и глагол без -s: She doesn't play. Подробный разбор механики — в статье «<a href=\"/blog-present-simple-dlya-roditelej\">Present Simple без слёз</a>».",
            "<b>4. More better / more easier.</b> Сравнительная степень уже встроена: better, easier. More добавляется только к длинным прилагательным: more interesting.",
            "<b>5. Peoples.</b> People — уже множественное число: Many people like coffee. «Народы» — это peoples, но в быту вы имеете в виду «люди».",
            "<b>6. Advices / informations.</b> Эти слова неисчисляемые: some advice, a piece of information. Хотите считать — добавляйте piece/item.",
            "<b>7. I have 10 years.</b> Калька «мне 10 лет». По-английски возраст — это «быть»: I am 10 (years old).",
        ]),
        ("h2", "Ловушки вопросов и ответов"),
        ("ul", [
            "<b>8. «How are you?» — «Normalno».</b> На рутинный вопрос отвечают рутинно: I'm fine, thanks / Pretty good / Not bad. Слово normal в таком ответе звучит странно.",
            "<b>9. Yes, I don't / No, I do.</b> Английский соглашается с фактом, а не с собеседником: «Didn't you sleep?» — «No, I didn't» (нет, не спал). Русское «да, не спал» здесь не работает.",
            "<b>10. What is it? — в косвенной речи.</b> В конструкции «I don't know what is it» порядок слов прямой: I don't know what it is. Вопросительный порядок живёт только в самостоятельном вопросе.",
            "<b>11. Who / which про людей.</b> Про людей — who: The girl who lives next door. Which и that — про предметы (that допустим и про людей, but who — безопаснее).",
        ]),
        ("h2", "Лексические подмены"),
        ("ul", [
            "<b>12. Say vs tell.</b> Say something (to somebody), tell somebody: She said hello. She told me a story. Русское «сказать мне» провоцирует ошибку said me — правильно told me или said to me.",
            "<b>13. Learn vs teach.</b> Русское «учить» покрывает оба глагола, английский — нет: learn — учиться самому, teach — учить кого-то. «Учу английский» (сам) — I learn English.",
            "<b>14. Cooker вместо cook.</b> Плита — cooker, повар — cook. «My dad is a cooker» — классика детских сочинений.",
            "<b>15. Comfortable vs convenient.</b> Удобная одежда/кресло — comfortable, удобное время/расположение — convenient: Is 5 pm convenient for you?",
        ]),
        ("h2", "Бонус-тройка произношения"),
        ("p", "Не ошибки грамматики, но маркеры акцента, которые легко поправить: слово <b>comfortable</b> произносится «кАмфтэбл» (три слога, не четыре); <b>clothes</b> — «клоуз», без «эс» на конце каждого слога; и знаменитый <b>th</b>: язык между зубами, иначе think превращается в sink, а three — в free. С произношением дети справляются быстрее взрослых — если вовремя показать. На наших программах — например, <a href=\"/razgovornyj-anglijskij\">разговорном курсе</a> — фонетика разбирается отдельным блоком именно потому, что «понятный акцент» важнее «идеального»."),
        ("h2", "Как избавляться от привычных ошибок"),
        ("ul", [
            "<b>Не исправляйте всё сразу.</b> Берите одну ошибку в неделю: пятнадцать поправок за раз отбивают желание говорить.",
            "<b>Вывешивайте «ошибку недели» на холодильник.</b> Для ребёнка это игра: поймать маму на I am agree — высший класс.",
            "<b>Замечайте ошибку в чужой речи.</b> Сериалы и видео — отличный полигон: слышать правильную модель сотню раз важнее, чем сто раз повторить правило.",
            "<b>Говорите больше.</b> Автоматизм приходит только из речи: правило, выученное без практики, в диалоге теряется за секунду.",
        ]),
        ("h2", "Частые вопросы"),
        ("p", "<b>«Опасно ли, что ребёнок говорит с ошибками — закрепятся навсегда?»</b> Нет: ошибки — нормальная фаза освоения. Опасно не ошибаться (то есть молчать). Задача взрослых — давать правильную модель и мягко исправлять системные ошибки по одной, а не превращать речь ребёнка в поле для правок."),
        ("p", "<b>«Я взрослый и говорю „I am agree” уже 10 лет — исправимо?»</b> Полностью. Привычные ошибки переучиваются за 2–3 недели осознанной практики: осознали механику (калька с русского), неделю ловите себя, ещё две — и новая модель автоматична. У взрослых это даже быстрее, чем у детей, за счёт осознанности."),
        ("p", "<b>«Где взять полный список типичных ошибок для самопроверки?»</b> Этой подборки хватает для 90% ситуаций; дальше эффективнее не списки, а обратная связь от педагога по вашей реальной речи. На <a href=\"/test-uroven\">бесплатной диагностике</a> педагог разбирает именно ваши живые ошибки — это точнее любого общего списка."),
        ("h2", "Как мы работаем с ошибками"),
        ("p", "В Фоксинбурге исправление ошибок — отдельная методическая линия: педагог фиксирует системные ошибки ученика и возвращает их в игровых дреллях, не перебивая речь. Родители видят динамику в отчётах: какие ошибки ушли, какие в работе. Детям это подаётся как «миссия недели» — поймать и обезвредить очередную русскую ловушку. Хотите узнать, какие из этих 15 живут в речи вашего ребёнка (или вашей)? Приходите на <a href=\"/test-uroven\">бесплатный тест уровня</a> — разберём за одно занятие."),
    ],
    "related": [
        ("Разговорный английский", "/razgovornyj-anglijskij"),
        ("Present Simple без слёз", "/blog-present-simple-dlya-roditelej"),
        ("Все статьи блога", "/blog"),
    ],
    "faq": [
        ("Почему «I am agree» — ошибка?", "Agree — глагол, а не прилагательное, поэтому am не нужен: правильно I agree. Ошибка возникает из-за кальки с русского «я согласен», где «согласен» — краткое прилагательное."),
        ("Нужно ли исправлять каждую ошибку ребёнка в речи?", "Нет: массовые поправки убивают желание говорить. Работаем точечно — одна системная ошибка в неделю, остальное время даём правильную модель в собственной речи."),
        ("Перестану ли я ошибаться, если выучу все правила?", "Правила без речевой практики в диалоге «не срабатывают»: автоматизм приходит из говорения. Правило даёт осознание, речь — навык; нужны оба компонента."),
        ("С каких ошибок начинать работу взрослому?", "С калек-«стычек» в самой частотной речи: I am agree, can to, he don't. Они встречаются в каждом разговоре, поэтому их исправление даёт самый заметный эффект за минимальное время."),
    ],
})

BLOG_POST_19 = dict(BLOG_FEED, **{
    "type": "article",
    "alias": "blog-audirovanie-kak-nauchitsya-ponimat",
    "title": "Аудирование: как научиться понимать английскую речь на слух",
    "description": "Как научиться понимать английский на слух: почему «читаю — понимаю, слушаю — нет», пошаговая тренировка аудирования для детей и взрослых и лучшие источники.",
    "category": "Учим английский",
    "date": "2026-08-11",
    "reading_time": "8 минут чтения",
    "hero_grad": "linear-gradient(135deg,#161f2e 0%,#243a5e 55%,#3a5f9e 100%)",
    "body": [
        ("h2", "«Читаю — всё понимаю, слушаю — ничего». Знакомо?"),
        ("p", "Это самая частая жалоба и детей, и взрослых, и у неё простое объяснение: чтение и аудирование — разные навыки с разной механикой. При чтении вы контролируете темп, можете вернуться и «узнать» слово глазами. На слух речь несётся со скоростью 150 слов в минуту, слова сливаются (going to → gonna, want to → wanna), а знакомое на письме слово в звучании оказывается незнакомцем — скажем, comfortАble мы все читали, но в живой речи это «камфтэбл». Вывод: аудирование не «приложится само» к чтению и грамматике — его надо тренировать отдельно и регулярно. Хорошая новость: это один из самых благодарных навыков, прогресс виден уже через месяц."),
        ("h2", "Принцип 1. Слушать на уровне «чуть ниже»"),
        ("p", "Главная ошибка тренировки — брать материал «на вырост»: подкасты для носителей, фильмы без субтитров, Би-би-си. Рабочая зона — контент, где вы понимаете 80–90%: тогда мозг догадывается об остатке из контекста и растёт. Если понимаете 50% — это не тренировка, а шум. Для детей правило то же: аудиосказка, где ребёнок следит за сюжетом, а не теряется в первой строчке. Поэтому стартовая точка — материалы вашего уровня: graded readers с аудио, учебные подкасты, адаптированные видео. О выборе книг с аудио по уровням — в статье «<a href=\"/blog-chtenie-na-anglijskom-s-chego-nachat\">Чтение на английском</a>»."),
        ("h2", "Принцип 2. Связка «уши + глаза»"),
        ("p", "Самый эффективный приём для старта — слушать и одновременно читать текст: аудиокнига + книга, видео + английские субтитры. Мозг «сшивает» звучание слова с его написанием, и через несколько недель знакомые глазами слова начинают узнаваться и на слух. Схема на одну главу: первый проход — слушаем и читаем; второй — только слушаем; третий — слушаем на перемотке в наушниках по дороге. Детям эта же связка работает с мультфильмами: сначала с английскими субтитрами (не русскими — русские субтитры выключают слушание полностью), потом без."),
        ("h2", "Принцип 3. Мало, но каждый день"),
        ("ul", [
            "<b>10–15 минут ежедневно</b> эффективнее двух часов раз в неделю — навык слухового восприятия строится на частоте контакта.",
            "<b>Активное и фоновое слушание — оба нужны.</b> Активное: сели, послушали, пересказали. Фоновое: английский играет, пока собираетесь в школу — оно приучает ухо к ритму и мелодике языка.",
            "<b>Один источник — много раз.</b> Любимая серия мультфильма на десятый просмотр даёт больше, чем десять новых серий по одному разу: повтор превращает «разобрал» в «узнаю мгновенно».",
            "<b>Дозируйте усталость.</b> Активное слушание утомляет быстро: 15 минут полной концентрации — норма и для взрослого.",
        ]),
        ("h2", "Что слушать: проверенные источники"),
        ("ul", [
            "<b>Дошкольникам и младшим школьникам:</b> песни Super Simple Songs, мультфильмы Peppa Pig, Bluey — короткие серии, ясная артикуляция, бытовая лексика.",
            "<b>Школьникам 10–14:</b> аудиокниги уровня своих graded readers, детские подкасты (Stories Podcast, Brains On!), YouTube-блогеры про их увлечения — игры, лайфхаки, питомцы.",
            "<b>Подросткам:</b> сериалы с английскими субтитрами, интервью с любимыми артистами, TikTok/Shorts на английском — короткий формат идеален для ежедневной дозы.",
            "<b>Взрослым:</b> учебные подкасты (6 Minute English от BBC — идеальная длина и темп), затем подкасты для носителей на знакомые темы, аудиокниги любимых романов.",
        ]),
        ("h2", "Тренируем «декодирование» связной речи"),
        ("p", "Отдельный навык — слышать, где кончается одно слово и начинается другое. Английская речь сцеплена: an apple звучит как «энэпл», did you — как «диджу». Тренируется это диктовкой на слух: берёте 30-секундный кусок аудио, слушаете и записываете, что слышите, потом сверяете с текстом. Пять минут такой работы в день за месяц заметно «распаковывают» слитную речь. Детям диктовку подаём игрой «радиоперехват»: записал сообщение — получил очко. На занятиях в Фоксинбурге аудирование — обязательная часть каждого урока, а на <a href=\"/razgovornyj-anglijskij\">разговорном курсе</a> половина времени уходит именно на связку «понял — ответил»."),
        ("h2", "Как не бросить: правила длинной дистанции"),
        ("ul", [
            "Привяжите слушание к существующей привычке: завтрак, дорога, прогулка с собакой — новая привычка на старой держится лучше.",
            "Слушайте про интересное: мотивация «узнать, чем кончится» сильнее дисциплины.",
            "Отмечайте победы: «понял шутку без субтитров» — повод отметить, таких моментов будет всё больше.",
            "Не паникуйте на «глухих» днях: восприятие на слух идёт волнами, плато перед скачком — норма.",
        ]),
        ("h2", "Частые вопросы"),
        ("p", "<b>«Сколько времени нужно, чтобы начать понимать фильмы без субтитров?»</b> При ежедневных 15 минутах: базовое понимание учебных материалов — через 1–2 месяца, сериалы с английскими субтитрами — через 4–6, фильмы без субтитров — обычно через год-полтора стабильной практики. У детей быстрее: слуховая пластичность выше."),
        ("p", "<b>«Помогает ли музыка на английском?»</b> Как фон и мотивация — да; как основной тренажёр — нет: в песнях искажается ритм и артикуляция. Идеальная связка: песни для удовольствия, подкасты и аудиокниги для навыка."),
        ("p", "<b>«Ребёнок смотрит мультики на английском, но, кажется, просто смотрит картинки. Это работает?»</b> Работает, если мультик на его уровне: пассивное знакомство с ритмом языка — уже вклад. Усилить можно вопросом после серии: «Что случилось с Пеппой?» — пересказ превращает фон в обучение."),
        ("h2", "Как ставим аудирование в Фоксинбурге"),
        ("p", "В наших программах — от <a href=\"/doshkolniki\">дошкольников</a> до <a href=\"/podrostki\">подростков</a> — аудирование встроено в каждое занятие: дети с первого урока слушают живую речь педагога, аудио и видео своего уровня, поэтому «экзаменационное» аудирование в школе не становится для них сюрпризом. Проверить, как ваш ребёнок понимает на слух сейчас, можно на <a href=\"/test-uroven\">бесплатной диагностике</a> — это одна из четырёх шкал, которые мы замеряем."),
    ],
    "related": [
        ("Разговорный английский", "/razgovornyj-anglijskij"),
        ("Чтение на английском: с чего начать", "/blog-chtenie-na-anglijskom-s-chego-nachat"),
        ("Все статьи блога", "/blog"),
    ],
    "faq": [
        ("Почему я понимаю текст, но не понимаю на слух?", "Чтение и аудирование — разные навыки: на слух слова сливаются и звучат иначе, чем пишутся. Аудирование тренируется отдельно — ежедневным слушанием материалов своего уровня."),
        ("Сколько минут в день нужно слушать английский?", "Для заметного прогресса — 10–15 минут активного слушания ежедневно плюс любой объём фонового. Регулярность важнее длительности."),
        ("Смотреть фильмы с русскими или английскими субтитрами?", "Только с английскими: русские субтитры полностью выключают слушание — глаз читает перевод, ухо отдыхает. Если без субтитров тяжело, английские субтитры — рабочий промежуточный этап."),
        ("Помогают ли детям мультфильмы на английском без перевода?", "Да, если мультфильм соответствует уровню: ребёнок должен понимать сюжет. Короткие серии с ясной артикуляцией (Peppa Pig, Bluey) — идеальный стартовый материал."),
    ],
})

BLOG_POST_20 = dict(BLOG_FEED, **{
    "type": "article",
    "alias": "blog-anglijskij-pered-1-sentyabrya",
    "title": "Английский перед 1 сентября: план на последнюю неделю лета",
    "description": "Как за неделю до 1 сентября вернуть английский в рабочее состояние: простой план на 7 дней для школьника — слова, грамматика, аудирование и настрой.",
    "category": "Школа и учёба",
    "date": "2026-08-20",
    "reading_time": "7 минут чтения",
    "hero_grad": "linear-gradient(135deg,#241a36 0%,#2e4a68 55%,#2d6a8f 100%)",
    "body": [
        ("h2", "Зачем нужна «неделя возвращения»"),
        ("p", "За лето без практики английский «оседает»: слова на месте, но достаются медленно, грамматика помнится, но срабатывает через раз. Это нормально и полностью обратимо — но не за один вечер 31 августа. Неделя мягкой работы по 25–30 минут в день возвращает язык в рабочее состояние, и ребёнок входит в первый урок сентября с ощущением «я помню», а не «я всё забыл». Это ощущение задаёт тон всей первой четверти. Ниже — готовый план по дням, подходящий школьникам 3–8 класса; для малышей и старшеклассников ниже даны поправки."),
        ("h2", "День 1–2. Разбудить слова"),
        ("p", "Начинаем не с нового, а с воскрешения старого. Достаньте карточки, приложение или тетрадь прошлого года и прогоните весь накопленный словарь: узнал мгновенно — в стопку «знаю», задумался — «повторить». Задача двух дней — не выучить заново, а составить рабочую стопку «полузабытых» слов (обычно их 20–30) и повторять её по интервалам: утром и вечером по 5 минут. Детям младшего возраста подаём это игрой «археология»: раскопали слово, которое спало всё лето. О методике интервального повторения подробно — в статье «<a href=\"/blog-kak-vyuchit-anglijskie-slova-bystro\">Как быстро учить английские слова</a>»."),
        ("h2", "День 3–4. Оживить грамматику"),
        ("p", "Берём одну опорную тему прошлого года — для большинства это Present Simple — и прогоняем её по короткой схеме: правило одной фразой, пять устных предложений о своём лете (I swam, I visited grandma — тут же и Past Simple освежится), одна игра на вопросы с do/does. Не больше 15 минут в день: цель — вспомнить механику, а не пройти тему заново. Если обнаруживается, что тема не «подзабылась», а «не стояла» никогда — не геройствуйте в последнюю неделю: отметьте её как задачу сентября. Разбор главной опорной темы у нас есть: «<a href=\"/blog-present-simple-dlya-roditelej\">Present Simple без слёз</a>»."),
        ("h2", "День 5. Вернуть ухо"),
        ("p", "Аудирование откатывается за лето сильнее всего. Один день посвящаем только слушанию: 15 минут любимого мультфильма или серии сериала на английском, 10 минут аудиосказки или подкаста уровня «понимаю почти всё». Никаких заданий — просто возвращаем уху привычку к звучащей речи. Если летом английский звучал дома регулярно, этот день можно отдать чтению. О том, как выстраивать слушание в течение года, — в статье «<a href=\"/blog-audirovanie-kak-nauchitsya-ponimat\">Как научиться понимать английскую речь на слух</a>»."),
        ("h2", "День 6. Поговорить"),
        ("p", "Кульминация недели — живая речь. Варианты по нарастающей: ребёнок пересказывает своё лето в пяти предложениях (сначала с черновиком, потом без); семейная игра «20 вопросов» на английском за ужином; для подростков — видеозвонок с другом с курсов или запись голосового рассказа про лето «для педагога». Задача не идеальность, а сломать молчание: первый разговор после паузы всегда самый трудный, и пусть он случится дома, а не у доски. Если говорение — хронически слабое место, сентябрь — лучший момент записаться на <a href=\"/razgovornyj-anglijskij\">разговорный курс</a>: в начале года группы формируются заново, и вход самый комфортный."),
        ("h2", "День 7. Собрать ритуал на год"),
        ("p", "Последний день августа — не про английский, а про систему. Договоритесь о расписании: в какие дни и в какое время ребёнок делает английскую домашку, где лежат карточки, какие 10 минут в день уходят на фоновое слушание. Ритуал, установленный в первую неделю сентября, проживёт весь год; ритуал «как-нибудь» умирает к октябрю. Заодно проверьте техническую часть: записаны ли дни занятий на курсах, куплены ли материалы, работает ли онлайн-платформа."),
        ("h2", "Поправки по возрастам"),
        ("ul", [
            "<b>Будущим первоклассникам:</b> плана не нужно — нужна игра: песни, карточки с картинками, 10 минут мультика в день. Задача — положительное ожидание, а не «готовность». Проверить готовность к школьному английскому можно на <a href=\"/test-gotov-k-shkole\">тесте «Готов к школе»</a>.",
            "<b>Будущим пятиклассникам:</b> добавьте письмо — 3–4 списанных предложения в день, рука за лето отвыкает сильнее головы. Остальное — в статье «<a href=\"/blog-anglijskij-v-5-klasse-chto-zhdat\">Английский в 5 классе</a>».",
            "<b>Девятиклассникам и одиннадцатиклассникам:</b> неделя возвращения обязана включать формат экзамена: один пробный вариант аудирования или устной части. Всё остальное время года уже уйдёт на него. Смотрите программы <a href=\"/oge-anglijskij\">подготовки к ОГЭ</a> и <a href=\"/ege-anglijskij\">к ЕГЭ</a> — места в сентябрьских группах разбирают первыми.",
        ]),
        ("h2", "Частые вопросы"),
        ("p", "<b>«Мы всё лето ничего не делали — недели хватит?»</b> Хватит для возвращения в рабочее состояние — именно это и нужно к 1 сентября. Навёрстывание годовых пробелов — задача не недели, а первой четверти, и решать её лучше с педагогом, а не домашними рывками."),
        ("p", "<b>«Стоит ли в последнюю неделю начинать новое (новую тему, новый учебник)?»</b> Нет: последняя неделя августа — время активации старого. Новое на старте учебного года даст школа и курсы; ваша задача — чтобы ребёнок встретил его с работающим языком."),
        ("p", "<b>«Как понять, к какой группе записывать ребёнка в сентябре, если уровень „поплыл” за лето?»</b> Не гадайте — пройдите <a href=\"/test-uroven\">бесплатную диагностику уровня</a>: она замеряет текущее, а не «весеннее» состояние, и педагог определит ребёнка в группу, где ему будет посильно и интересно. Общий чек-лист подготовки к году — в материале «<a href=\"/novosti-podgotovka-k-novomu-uchebnomu-godu-anglijskij\">Подготовка к новому учебному году</a>»."),
        ("h2", "Сентябрь в Фоксинбурге"),
        ("p", "Группы нового учебного года формируются в последнюю неделю августа — самое время пройти диагностику и занять место в удобном филиале (Лихачёвский 76к1 или Ракетостроителей 9к3). Для тех, кто хочет начать год с разгона, до конца августа идут последние смены <a href=\"/letnyaya-akademiya\">Летней академии</a>. Программы на год — для всех возрастов: от <a href=\"/doshkolniki\">дошкольников</a> до <a href=\"/anglijskij-dlya-vzroslyh\">взрослых</a>; тарифы — на странице <a href=\"/tseny\">цен</a>. До встречи в сентябре!"),
    ],
    "related": [
        ("Бесплатный тест уровня", "/test-uroven"),
        ("Подготовка к новому учебному году", "/novosti-podgotovka-k-novomu-uchebnomu-godu-anglijskij"),
        ("Все статьи блога", "/blog"),
    ],
    "faq": [
        ("Сколько времени нужно, чтобы вспомнить английский после лета?", "Рабочее состояние возвращается за 5–7 дней по 25–30 минут: повторение словаря, одна опорная грамматическая тема, слушание и один живой разговор. Глубокие пробелы — задача первой четверти."),
        ("Что важнее повторить в первую очередь?", "Словарь прошлого года и главную грамматическую тему (для большинства — Present Simple): это остов, на который навешивается всё остальное. Аудирование откатывается сильнее всего — его тоже включаем с первых дней."),
        ("Ребёнок идёт в первый класс — нужна ли подготовка в последнюю неделю?", "Не подготовка, а игра: песни и мультики на английском по 10 минут в день, чтобы язык был знакомым и приятным. Проверить общую готовность поможет тест «Готов к школе»."),
        ("Когда записываться на курсы на новый учебный год?", "В последнюю неделю августа: группы по уровням формируются именно тогда, и диагностика до 1 сентября гарантирует место в группе подходящего уровня и расписания."),
    ],
})

BLOG_POST_21 = dict(BLOG_FEED, **{
    "type": "article",
    "alias": "blog-kruzhok-anglijskogo-dlya-doshkolnika",
    "title": "Кружок английского для дошкольника: как выбрать и не ошибиться",
    "description": "Как выбрать кружок английского для ребёнка 4–6 лет: на что смотреть на пробном занятии, какие вопросы задать, красные флаги и признаки хорошей программы для дошкольников.",
    "category": "Родителям",
    "date": "2026-07-03",
    "reading_time": "8 минут чтения",
    "hero_grad": "linear-gradient(135deg,#241a36 0%,#3a2c5a 55%,#8f4a9e 100%)",
    "body": [
        ("h2", "Почему дошкольный английский — это не «ранняя школа»"),
        ("p", "Хороший кружок английского для дошкольника принципиально отличается от урока для школьника: никаких тетрадей, оценок и «сидим 45 минут». В 4–6 лет язык осваивается через игру, движение, песни и ритуалы — так же, как ребёнок когда-то осваивал русский. Если на занятии дети сидят за партами и списывают буквы — это не «серьёзный подход», это незнание возрастной методики. Правильная цель дошкольного английского скромная и одновременно огромная: ребёнок должен полюбить звучание языка, перестать его бояться и накопить 150–300 слов пассивного запаса к школе. Всё остальное — буквы, правила, чтение — успеется: мы разбирали это в статье «<a href=\"/blog-anglijskij-dlya-detej-3-4-goda\">Английский для детей 3–4 лет</a>»."),
        ("h2", "На что смотреть на пробном занятии"),
        ("p", "Пробное занятие — главный инструмент выбора, и смотреть нужно не на «понравилось ли ребёнку» (это важно, но дети легко вовлекаются), а на механику урока. Хорошие признаки: педагог говорит по-английски 70–80% времени, а русский использует только для безопасности и коротких инструкций; каждые 5–7 минут меняется тип активности (песня → игра → поделка → физминутка); каждый ребёнок проговаривает слова вслух несколько раз за занятие, а не только хором; есть ритуалы приветствия и прощания на английском — они дают ощущение предсказуемости. Тревожные признаки: дети сидят на месте больше 10 минут подряд, педагог переводит каждое слово, «обучение» сводится к раскраскам без речи, а на вопрос ребёнка отвечают «потом»."),
        ("h2", "Вопросы, которые стоит задать администратору"),
        ("ul", [
            "<b>Сколько детей в группе?</b> Для дошкольников комфортный максимум — 6–8 человек: меньше взрослый контроль хаоса, больше речи на каждого.",
            "<b>Какая программа и чем ребёнок будет заниматься к концу года?</b> Внятный ответ звучит как «к концу года дети понимают базовые инструкции, знают 8–10 тем по 15–20 слов, поют 12 песен», а не «у нас авторская методика».",
            "<b>Как узнавать о прогрессе?</b> У дошкольников нет оценок, но должны быть регулярные открытые занятия, видеоотчёты или папка работ.",
            "<b>Что делать, если ребёнок плачет и не отпускает маму?</b> Правильный ответ включает адаптационный период: первые 2–3 занятия родитель может побыть рядом или за дверью.",
            "<b>Кто педагог и какой у него опыт именно с дошкольниками?</b> Отличный преподаватель для подростков может быть слабым для пятилеток — это разные профессии.",
        ]),
        ("h2", "Красные флаги: когда стоит уйти"),
        ("p", "Есть сигналы, после которых пробное занятие можно не досматривать. Первый — обещание «заговорит через три месяца»: честный педагог скажет, что устойчивая спонтанная речь у дошкольника появляется через год-полтора регулярных занятий. Второй — штрафы за пропуски без возможности отработки: у детей 4–6 лет болезни — норма, а не исключение. Третий — отсутствие лицензии на образовательную деятельность, если организация выдаёт документы и набирает группы круглый год. Четвёртый — «у нас только носитель» или «у нас только русскоязычный педагог» как единственное преимущество: важна не паспортная принадлежность педагога, а его умение работать с дошкольной группой. И наконец, насторожитесь, если вам не дают посмотреть занятие даже через стекло или в записи — скрывать там нечего."),
        ("h2", "Формат: как часто и сколько должно длиться занятие"),
        ("p", "Для 4–5 лет оптимальны 2 занятия в неделю по 30–40 минут, для 6–7 лет — 2 раза по 45–60 минут. Одно занятие в неделю для дошкольника почти бесполезно: за шесть дней паузы короткая детская память стирает большую часть материала, и каждое занятие начинается с нуля. Домашние задания в этом возрасте — не письменные упражнения, а «послушай песню», «покажи маме карточки», «найди дома три красных предмета и назови». Если кружок задаёт пятилетке прописи — это перенос школьной модели на несоответствующий возраст. Хотите проверить общую готовность ребёнка к школьному английскому — пройдите наш <a href=\"/test-gotov-k-shkole\">тест «Готов к школе»</a>: он покажет, на что опереться в подготовке."),
        ("h2", "Как это устроено в Фоксинбурге"),
        ("p", "Наша программа для дошкольников построена ровно по этим принципам: группы до 8 человек, занятия в игровом формате 2 раза в неделю, смена активности каждые 5–7 минут, песни, ритуалы и накопление словаря по темам. Первое занятие — пробное, на нём педагог смотрит не только и не столько «знания», сколько то, как ребёнок вступает в контакт, и подбирает группу по темпераменту. Посмотреть программу и расписание можно на странице <a href=\"/doshkolniki\">английского для дошкольников</a>, цены — на странице <a href=\"/tseny\">тарифов</a>. Записаться на пробное занятие в ближайший филиал (Лихачёвский 76к1 или Ракетостроителей 9к3) — через страницу <a href=\"/kontakty\">контактов</a> или напрямую в мессенджере."),
    ],
    "related": [
        ("Английский для дошкольников", "/doshkolniki"),
        ("Тест: готов ли ребёнок к школе", "/test-gotov-k-shkole"),
        ("Все статьи блога", "/blog"),
    ],
    "faq": [
        ("В каком возрасте начинать занятия английским?", "Комфортный старт групповых занятий — 4–5 лет: ребёнок уже удерживает внимание 15–20 минут и идёт на контакт с чужим взрослым. Раньше — только в формате занятий с мамой или домашнего фона (песни, мультфильмы)."),
        ("Сколько детей должно быть в группе для дошкольников?", "Оптимально 4–6, приемлемо до 8. Больше восьми пятилеток один педагог уже не вовлекает в речь — занятие превращается в удержание дисциплины."),
        ("Нужен ли дошкольнику носитель языка?", "Нет: в этом возрасте важнее умение педагога работать с маленькими детьми и его собственное чёткое произношение. Носитель без методического опыта с дошкольниками даёт меньше, чем сильный русскоязычный педагог."),
        ("Как понять, что занятия дают результат?", "Через 3–4 месяца ребёнок начинает узнавать английскую речь, подпевать песням с занятий и вставлять отдельные слова дома. Просите у педагога видео с открытых занятий — это самый честный маркер прогресса."),
    ],
})

BLOG_POST_22 = dict(BLOG_FEED, **{
    "type": "article",
    "alias": "blog-anglijskij-letom-progress",
    "title": "Английский летом: как не потерять прогресс и даже вырасти",
    "description": "План летнего английского для школьника без нервов: сколько минут в день достаточно, что даёт лучший эффект — слова, мультфильмы, чтение, — и кому нужен летний интенсив.",
    "category": "Учим английский",
    "date": "2026-07-08",
    "reading_time": "8 минут чтения",
    "hero_grad": "linear-gradient(135deg,#241a36 0%,#2e5a4a 55%,#3d8f6e 100%)",
    "body": [
        ("h2", "Что происходит с языком за три месяца паузы"),
        ("p", "Исследования «summer slide» — летнего отката — показывают: за каникулы без практики школьник теряет до 20–30% скорости воспроизведения языка. Слова не забываются совсем — они «засыпают»: ребёнок узнаёт их в тексте, но не может вспомнить в речи. Сильнее всего страдают аудирование и беглость говорения, потому что они держатся на свежих нейронных «дорожках». Хорошая новость: для удержания языка не нужны летние зубрёжки. Достаточно 15–20 минут лёгкой практики в день — и ребёнок придёт в сентябре не откатившимся, а подросшим. Ниже — рабочая схема, проверенная на наших учениках."),
        ("h2", "Минимальная летняя доза: 15–20 минут в день"),
        ("p", "Секрет летнего английского — регулярность вместо объёма. Пятнадцать минут каждый день дают больше, чем два часа раз в неделю: короткая ежедневная встреча с языком не даёт «дорожкам» зарасти. Важно, чтобы практика не выглядела уроком: летом работает только то, что ребёнок воспринимает как развлечение или привычку. Идеальная формула дня: 5 минут слов + 10 минут слушания или чтения + английский «фоном» по дороге. Всё. Этого хватит, чтобы в сентябре не тратить первую четверть на «вспоминание». Отдельный бонус: летом у ребёнка есть ресурс внимания, которого нет в учебном году — можно мягко вытянуть то, что не получалось: неправильные глаголы, счёт, предлоги."),
        ("h2", "Слова: летний режим"),
        ("p", "Летом словарь учим не новый, а «полузабытый». Достаньте весь накопленный за год набор — карточки, приложение, темы из учебника — и прогоните его один раз: то, что вспомнилось мгновенно, убираем; то, что «всплыло через три секунды», — в летнюю стопку. Обычно это 40–60 слов. Их повторяем по 5–7 минут утром или перед сном, лучше по принципу интервалов: сегодня, через день, через три дня. Если хотите добавить новое — берите «вкусные» летние темы: еда, животные, путешествия. Готовые подборки с транскрипцией и примерами есть в нашем <a href=\"/english-words\">словаре по темам</a> — например, темы «<a href=\"/english-words/eda\">Еда</a>» и «<a href=\"/english-words/zhivotnye\">Животные</a>». О механике запоминания подробно — в статье «<a href=\"/blog-kak-vyuchit-anglijskie-slova-bystro\">Как быстро учить слова</a>»."),
        ("h2", "Слушание: самый лёгкий навык для лета"),
        ("p", "Аудирование — единственный навык, который летом можно качать вообще без сопротивления: мультфильмы, сериалы, песни и аудиосказки не воспринимаются как учёба. Правила простые: выбирайте контент, где ребёнок понимает 80–90% (ниже — мучение, выше — нет роста); один и тот же эпизод можно смотреть дважды — повторный просмотр превращает «узнавание» в «запоминание»; 10–15 минут в день достаточно. Для младших — песни и короткие мультфильмы, для подростков — видеоблоги на их темы: игры, спорт, лайфстайл. Подробную схему работы со слушанием мы собрали в статье «<a href=\"/blog-audirovanie-kak-nauchitsya-ponimat\">Как научиться понимать английскую речь на слух</a>»."),
        ("h2", "Чтение и говорение: по чуть-чуть"),
        ("p", "Чтение летом — только удовольствие: комиксы, книги про динозавров, фанфики, инструкции к играм — жанр не важен, важен интерес. Десять минут в день поддерживают скорость чтения и пополняют словарь «между строк». С говорением сложнее: без собеседника оно не растёт, но удержать его помогают голосовые «челленджи» — раз в несколько дней ребёнок записывает минутное голосовое о том, как прошёл день (себе, вам, педагогу). Подросткам отлично заходит дневник в мессенджере на английском или переписка с другом с курсов. Играйте за ужином в «слово дня»: каждый должен вставить новое слово в русскую фразу — смешно и работает."),
        ("h2", "Кому летом нужен интенсив, а не «поддержка»"),
        ("ul", [
            "<b>Будущим пятиклассникам</b> — переход в среднюю школу резко поднимает планку: лето — лучшее время спокойно подтянуть базу. См. «<a href=\"/blog-anglijskij-v-5-klasse-chto-zhdat\">Английский в 5 классе</a>».",
            "<b>Девяти- и одиннадцатиклассникам</b> — ОГЭ/ЕГЭ не прощают летнего отката: июль — идеальное время стартовать подготовку без школьной нагрузки.",
            "<b>Тем, кто «отстаёт по школе»</b> — летом нет параллельной нагрузки, и пробелы закрываются в два-три раза быстрее.",
            "<b>Новичкам</b> — начать с нуля летом психологически легче: к сентябрю ребёнок уже «занимается английским», а не «пойдёт на что-то страшное».",
        ]),
        ("p", "Для этих задач в Фоксинбурге работает <a href=\"/letnyaya-akademiya\">Летняя академия</a>: короткие смены, игровой формат для младших и экзаменационный трек для старших. Если семья уезжает — подойдут <a href=\"/online-zanyatiya\">онлайн-занятия</a>: расписание летом гибкое. Вопрос «какой формат выбрать» решается за пять минут нашим <a href=\"/test-format\">тестом формата</a>."),
    ],
    "related": [
        ("Словарь по темам для детей", "/english-words"),
        ("Летняя академия Фоксинбурга", "/letnyaya-akademiya"),
        ("Все статьи блога", "/blog"),
    ],
    "faq": [
        ("Сколько минут в день достаточно летом?", "15–20 минут лёгкой практики ежедневно: 5 минут слов плюс 10–15 минут слушания или чтения. Главное — ежедневность, а не объём: короткие встречи с языком не дают навыку откатиться."),
        ("Ребёнок отказывается от «уроков» летом — что делать?", "Уберите само слово «урок». Летом работают только форматы-развлечения: мультфильмы, песни, комиксы, семейные игры со словами. Встроенная в жизнь практика не требует мотивации."),
        ("Нужно ли летом учить новые темы?", "Не обязательно: приоритет — удержать пройденное. Новое берите только «вкусное» и прикладное: темы словаря про еду, животных, путешествия. Серьёзные новые темы — задача учебного года."),
        ("Когда начинать подготовку к сентябрю?", "Плановую «неделю возвращения» оставьте на конец августа, а июль–август отдайте лёгкому режиму. Если в сентябре ребёнок идёт на курсы, запишитесь заранее — группы по уровням формируются в последнюю неделю августа."),
    ],
})

BLOG_POST_23 = dict(BLOG_FEED, **{
    "type": "article",
    "alias": "blog-present-perfect-prostymi-slovami",
    "title": "Present Perfect простыми словами: объясняем родителям",
    "description": "Present Perfect без терминов: чем он отличается от Past Simple, три жизненные ситуации употребления, слова-маркеры и как помочь ребёнку не путать времена.",
    "category": "Учим английский",
    "date": "2026-07-15",
    "reading_time": "8 минут чтения",
    "hero_grad": "linear-gradient(135deg,#241a36 0%,#26355e 55%,#3f6db3 100%)",
    "body": [
        ("h2", "Почему Present Perfect — самое «несправедливое» время"),
        ("p", "Если ребёнок говорит, что «английская грамматика бессмысленная», почти наверняка речь о Present Perfect. В русском языке ничего похожего нет: прошлое у нас одно, а в английском их минимум три, и выбор между ними меняет смысл фразы. Хуже того, учебники объясняют его через термины: «действие, завершённое к настоящему моменту, имеющее результат». Ребёнок зубрит определение, а на устной части всё равно говорит «I have went». Хорошая новость: для реального владения достаточно понять одну идею и три ситуации. Эта статья объясняет Present Perfect так, чтобы вы могли за десять минут разобраться сами и ещё за десять — объяснить ребёнку. Если не читали наш разбор <a href=\"/blog-present-simple-dlya-roditelej\">Present Simple простыми словами</a> — начните с него, логика та же."),
        ("h2", "Одна идея: «мост между прошлым и сейчас»"),
        ("p", "Сформулируйте для себя так: Past Simple — про прошлое, которое закончилось и осталось там (с указанием, когда именно: yesterday, in 2010, last week). Present Perfect — про прошлое, которое важно прямо сейчас, и время его не называют. Сравните: «I lost my keys yesterday» — вчера потерял, факт из биографии, рассказываю историю. «I have lost my keys» — потерял, и сейчас стою под дверью: важен результат, а не момент. Поэтому Present Perfect нельзя использовать с конкретной датой: как только появляется «yesterday», мост обрушивается и включается Past Simple. Эта одна проверка — «есть ли в фразе точное время в прошлом?» — решает 80% ошибок ребёнка."),
        ("h2", "Три ситуации, в которых нужен Present Perfect"),
        ("p", "Ситуация первая — <b>результат в настоящем</b>: «I have finished my homework» (свободен, можно гулять), «She has broken her leg» (поэтому лежит в гипсе). Ситуация вторая — <b>жизненный опыт без даты</b>: «Have you ever been to London?», «I have never tried sushi» — важно само «было или нет», а не когда. Ситуация третья — <b>длящееся до сих пор состояние</b>: «We have lived here for five years», «He has known her since childhood» — началось в прошлом, продолжается сейчас. Всё. Эти три коробки покрывают почти все школьные упражнения и всю устную часть экзаменов. Остальное — нюансы, которые придут с практикой."),
        ("h2", "Слова-маркеры: шпаргалка на холодильник"),
        ("ul", [
            "<b>Тянут к Present Perfect:</b> just (только что), already (уже), yet (ещё/уже — в вопросах и отрицаниях), ever/never, for + период (for two years), since + точка (since Monday), today, this week.",
            "<b>Тянут к Past Simple:</b> yesterday, last week/month/year, ago (two days ago), in 2015, when-вопросы («When did you…?»).",
            "<b>Правило-лакмус:</b> видишь в предложении точное прошедшее время — ставь Past Simple; время не названо или отрезок «до сих пор» — Present Perfect.",
        ]),
        ("p", "Выучите маркеры вместе с ребёнком как пары-антагонисты: already — yesterday, ever — ago, for — last. Пять минут игры «кто быстрее подхватит маркер» ужина на неделю дают больше, чем страница упражнений."),
        ("h2", "Форма: have/has + третья форма глагола"),
        ("p", "Механически Present Perfect прост: have (для I, you, we, they) или has (для he, she, it) плюс третья форма глагола. Подвох именно в третьей форме: у правильных глаголов она совпадает с прошедшим (work — worked — worked), а у неправильных живёт своей жизнью (go — went — gone, see — saw — seen, do — did — done). Топ-20 неправильных глаголов нужно просто выучить — это единственная «зубрёжная» часть темы. Эффективный способ: короткие личные предложения («I have eaten», «I have forgotten my keys»), а не голые таблицы. И отдельно проработайте has для he/she/it — типичная ошибка «he have» вылезает даже у сильных учеников под стрессом экзамена."),
        ("h2", "Как помочь ребёнку дома, если вы сами «не в теме»"),
        ("p", "Не исправляйте грамматику в свободной речи — это убивает желание говорить. Вместо этого играйте в «Have you ever…?» за ужином: каждый задаёт вопрос про жизненный опыт («Have you ever eaten snails?»), остальные отвечают «Yes, I have / No, I haven't» — это тренировка и формы, и второй ситуации употребления. Второй приём — просите ребёнка объяснить вам правило: попытка объяснить выявляет дыры лучше любого теста. Если тема не складывается неделями и съедает оценки — это сигнал, что нужен педагог: на <a href=\"/podrostki\">занятиях для подростков</a> мы разбираем времена на говорении, а не на зубрёжке. Проверить общий уровень можно на бесплатном <a href=\"/test-uroven\">тесте уровня</a>, а тем, кто готовится к девятому классу, Present Perfect обязательно встретится в <a href=\"/oge-anglijskij\">ОГЭ по английскому</a>."),
    ],
    "related": [
        ("Present Simple без слёз", "/blog-present-simple-dlya-roditelej"),
        ("Подготовка к ОГЭ по английскому", "/oge-anglijskij"),
        ("Все статьи блога", "/blog"),
    ],
    "faq": [
        ("Чем Present Perfect отличается от Past Simple одной фразой?", "Past Simple — про законченное прошлое с указанием, когда (yesterday, in 2010). Present Perfect — про прошлое, важное сейчас: результат, опыт или состояние, длящееся до настоящего момента; точное время не называют."),
        ("Почему нельзя сказать «I have seen him yesterday»?", "Потому что yesterday — точное прошедшее время, а Present Perfect с ним несовместим. Любая конкретная дата в прошлом автоматически переключает фразу на Past Simple: «I saw him yesterday»."),
        ("Какие слова подсказывают, что нужен Present Perfect?", "Just, already, yet, ever, never, for + период, since + точка во времени, today, this week. Противоположный лагерь — yesterday, ago, last week — требует Past Simple."),
        ("Обязательно ли учить таблицу неправильных глаголов?", "Таблицу целиком — нет, а топ-20 самых частых — да: без третьей формы (gone, seen, done, eaten) Present Perfect механически не построить. Учите личными примерами, а не столбиками."),
    ],
})

BLOG_POST_24 = dict(BLOG_FEED, **{
    "type": "article",
    "alias": "blog-multfilmy-na-anglijskom-po-vozrastam",
    "title": "Мультфильмы на английском для детей: подборка по возрастам",
    "description": "Какие мультфильмы и сериалы смотреть на английском в 3–5, 6–9, 10–13 и 14+ лет: критерии выбора по уровню, субтитры «за» и «против», сколько минут в день.",
    "category": "Учим английский",
    "date": "2026-07-22",
    "reading_time": "8 минут чтения",
    "hero_grad": "linear-gradient(135deg,#241a36 0%,#5e2640 55%,#b34a6e 100%)",
    "body": [
        ("h2", "Почему мультфильмы — лучший бесплатный учебник"),
        ("p", "Мультфильм на английском решает сразу три задачи: тренирует аудирование, пополняет словарь в контексте и — главное — не требует мотивации, потому что ребёнок воспринимает его как награду, а не учёбу. Но работает это только при одном условии: уровень речи должен соответствовать ребёнку. Правило простое: понятно должно быть 80–90%. Если меньше — ребёнок смотрит «картинки», язык идёт фоном-шумом; если 100% — нет роста. Второе условие — регулярность: 10–15 минут каждый день эффективнее полутора часов раз в неделю. Общую методику работы со слушанием мы подробно разобрали в статье «<a href=\"/blog-audirovanie-kak-nauchitsya-ponimat\">Как научиться понимать английскую речь на слух</a>», а здесь — конкретные подборки по возрастам."),
        ("h2", "3–5 лет: медленно, коротко, с повторами"),
        ("p", "Дошкольнику нужны серии по 3–7 минут с медленной чёткой речью, простой сюжетной линией и обязательными повторами слов внутри серии. Проверенная классика: «Peppa Pig» — короткие бытовые сюжеты и стандартный английский; «Bluey» — живая семейная речь (чуть быстрее, для 4–5 лет); «Maisy» и «Penelope» — очень медленный темп, идеальны для старта; «Super Simple Songs» — не мультфильм, а песенные миниатюры, с которых удобно начинать вообще с нуля. На этом возрасте родительская задача — смотреть вместе и «достраивать»: прокомментировать по-русски сюжет, повторить за героем слово, поиграть в него после. Наши программы для этого возраста — на странице <a href=\"/doshkolniki\">английского для дошкольников</a>."),
        ("h2", "6–9 лет: сюжеты и юмор"),
        ("p", "Младшему школьнику уже нужен сюжет, иначе он отвернётся. Хорошо заходят: «Paw Patrol» и «Octonauts» — приключенческие серии с предсказуемой структурой, где ребёнок догадывается о смысле по картинке; «Peppa Pig» остаётся актуальной для начинающих; «Sarah and Duck» — спокойная и умная; «Daniel Tiger's Neighbourhood» — про эмоции и социальные навыки с намеренно медленной речью. В этом возрасте появляется полезный приём: смотрим серию дважды — первый раз для удовольствия, второй с паузами, повторяя забавные фразы. Пусть ребёнок выбирает серию сам: личный интерес важнее методически «правильного» выбора. Дополнить просмотр можно тематическими словами из нашего <a href=\"/english-words\">словаря по темам</a> — например, «<a href=\"/english-words/zhivotnye\">Животные</a>» к сериям про зверей."),
        ("h2", "10–13 лет: сериальная эпоха"),
        ("p", "Подростковый возраст — время сериалов и длинных историй. «Gravity Falls» — лучшая точка входа: юмор, загадки, живая речь средней скорости; «Avatar: The Last Airbender» — внятная артикуляция и захватывающий сюжет; «The Owl House», «Hilda» — современные сериалы с богатой разговорной лексикой. Для любителей реальной жизни — детские каналы YouTube с обзорами и влогами: там самый живой современный язык, но темп выше. Важно: в этом возрасте уже работает приём «тень» (shadowing) — ребёнок выбирает любимого персонажа и повторяет его реплики с интонацией. Пять минут «тени» после серии делают для произношения больше, чем час упражнений. Группы для этого возраста — на странице <a href=\"/mladshie-shkolniki\">младших школьников</a>."),
        ("h2", "14+ и взрослый контент: осторожно, но можно"),
        ("p", "Старшекласснику детские сериалы уже неинтересны — и это нормально. Здесь работают подростковые ситкомы («Good Luck Charlie», «Jessie») и молодёжные сериалы с субтитрами, а для сильных — «Friends» и «The Big Bang Theory» (проверьте контент на соответствие вашим семейным нормам). Альтернатива — нехудожественный контент по интересам: тревел-влоги, игровые стримы, научпоп-каналы — язык там живой и мотивация встроенная. Программы для этого возраста — на странице <a href=\"/podrostki\">английского для подростков</a>."),
        ("h2", "Субтитры: за и против"),
        ("ul", [
            "<b>Начинающим (A0–A1):</b> без субтитров или с русскими — но тогда это развлечение, а не практика. Лучше выбирать уровень, где субтитры не нужны.",
            "<b>Средний уровень (A2–B1):</b> английские субтитры — отличный мостик: глаз помогает уху. Не бойтесь их, это легальный учебный приём.",
            "<b>Сильный уровень (B1+):</b> чередуйте: серия с английскими субтитрами, следующая — без. Прогресс заметен уже через месяц.",
            "<b>Красный флаг:</b> русские субтитры на постоянной основе — ребёнок читает по-русски, а английский становится шумом.",
        ]),
        ("h2", "Как встроить просмотр в жизнь без битв"),
        ("p", "Самая рабочая схема — «английский час» как часть экранного времени: ребёнок получает свои обычные мультфильмы, но одна серия в день — на английском. Не торгуйтесь «сначала уроки, потом мультик»: превращение английского в валюту порождает ненависть к языку. Лучше — ритуал: вечерняя серия после ужина всегда английская. И обсуждайте: один вопрос «а что там случилось с Peppa?» после серии переключает просмотр из пассивного в активный. Если хотите, чтобы педагог подобрал контент точно под уровень ребёнка, — приходите на бесплатную <a href=\"/test-uroven\">диагностику уровня</a>, там же определим и стартовую серию."),
    ],
    "related": [
        ("Как научиться понимать речь на слух", "/blog-audirovanie-kak-nauchitsya-ponimat"),
        ("Словарь по темам", "/english-words"),
        ("Все статьи блога", "/blog"),
    ],
    "faq": [
        ("С какого возраста можно смотреть мультфильмы на английском?", "С 3 лет — короткие серии с медленной речью и повторами (Maisy, Penelope, Super Simple Songs). До этого возраста экранное время лучше заменять песнями и живым общением."),
        ("Нужны ли субтитры при просмотре?", "Начинающим — нет: выбирайте уровень, где понятно 80–90% без них. Среднему уровню английские субтитры помогают. Русские субтитры на постоянной основе сводят пользу к нулю."),
        ("Сколько минут в день даёт эффект?", "10–15 минут ежедневно достаточно для удержания и постепенного роста аудирования. Важнее регулярность: каждый день понемногу, а не много раз в неделю."),
        ("Ребёнок смотрит, но не говорит — это нормально?", "Да: мультфильмы качают в первую очередь понимание — это фундамент речи. Чтобы просмотр подталкивал к говорению, добавьте повтор реплик любимого персонажа или обсуждение серии после."),
    ],
})

BLOG_POST_25 = dict(BLOG_FEED, **{
    "type": "article",
    "alias": "blog-pesni-na-anglijskom-dlya-detej",
    "title": "Песни на английском для детей: как музыка учит языку",
    "description": "Почему песни — самый быстрый способ запомнить английские слова, какие песни выбрать для каждого возраста и как превратить прослушивание в практику языка.",
    "category": "Учим английский",
    "date": "2026-07-29",
    "reading_time": "7 минут чтения",
    "hero_grad": "linear-gradient(135deg,#241a36 0%,#5e5226 55%,#b39a3f 100%)",
    "body": [
        ("h2", "Почему песня запоминается лучше карточки"),
        ("p", "Мелодия и ритм включают дополнительные области памяти: слово из песни хранится сразу в трёх «форматах» — как текст, как мелодия и как движение (если ребёнок подпевает и жестикулирует). Поэтому ребёнок, который «не может выучить десять слов по карточкам», без усилий поёт наизусть целую песню из тридцати слов. Песня делает за учителя ещё три вещи: ставит правильную ритмику и интонацию английской фразы (это невозможно выучить по книге), доставляет готовые грамматические конструкции целиком («What's your name?», «I can jump») и создаёт позитивную ассоциацию с языком. Единственное ограничение: песня учит пассивно — чтобы слова перешли в активную речь, их нужно «вытащить» из мелодии в игру. Об этом ниже."),
        ("h2", "3–5 лет: движение плюс повторы"),
        ("p", "Дошкольнику нужны песни с простым циклическим текстом и встроенными действиями: «Head, Shoulders, Knees and Toes» (части тела), «If You're Happy and You Know It» (эмоции и действия), «The Wheels on the Bus» (звуки и транспорт), «Old MacDonald» (животные). Вся классика собрана на каналах Super Simple Songs и Cocomelon — там же темп замедлен под неговорящих детей. Главный приём этого возраста — песня-жест: слово живёт в движении, и ребёнок, показывающий «knees», уже выучил его. Пять-семь песен, доведённых до автоматизма, дают дошкольнику первые 50–70 слов. Подробнее о старте в этом возрасте — в статье «<a href=\"/blog-anglijskij-dlya-detej-3-4-goda\">Английский для детей 3–4 лет</a>» и на странице программы <a href=\"/doshkolniki\">для дошкольников</a>."),
        ("h2", "6–9 лет: сюжетные песни и караоке"),
        ("p", "Младшему школьнику уже интересны песни «со смыслом»: считалки («Five Little Monkeys», «Ten in the Bed»), дни недели и месяцы («Days of the Week», «Months of the Year» — зубрёжка, которую школа требует в первом-втором классе, решается песней за неделю), алфавитные песни для начинающих читать. Появляется караоке-формат: клипы с бегущей строкой текста учат чтению наизусть пропетого — это мягкий мостик к осмысленному чтению. Полезный ритуал: «песня недели» — одна песня слушается каждый день по дороге, к пятнице ребёнок поёт её сам. К песням по темам подтяните словарь из нашего <a href=\"/english-words\">словаря по темам</a>: «<a href=\"/english-words/tsveta\">Цвета</a>», «<a href=\"/english-words/semya\">Семья</a>», «<a href=\"/english-words/shkola\">Школа</a>» — есть готовые таблицы с транскрипцией."),
        ("h2", "10–14 лет: настоящая музыка"),
        ("p", "Подростку «детские» песни не предлагайте — включайте его собственную музыку. Англоязычные хиты, саундтреки к любимым фильмам и играм — всё это полноценная практика, если добавить один шаг: открыть текст. Схема рабочая: слушаем песню → читаем lyrics → разбираем 3–5 незнакомых фраз → поём. Подростки сами не замечают, как выучивают идиомы и сленг, который не даёт ни один учебник. Отдельно хорошо работают каверы и замедленные версии любимых треков — проще разобрать произношение. Предупреждение для родителей: просматривайте тексты заранее, в подростковой музыке встречается взрослый контент. Для этого возраста у нас есть отдельные программы — <a href=\"/podrostki\">английский для подростков</a>, где музыкальные интересы учеников встроены в занятия."),
        ("h2", "Как превратить прослушивание в практику: четыре приёма"),
        ("ul", [
            "<b>Пропуски:</b> распечатайте или покажите текст с пропущенными словами — ребёнок вставляет их на слух. Пять минут, а тренирует и аудирование, и письмо.",
            "<b>Перевод вслух:</b> останавливаем песню, ребёнок пересказывает строку по-русски своими словами (не дословно — смыслом).",
            "<b>Вытащить слово из песни:</b> выученные из песни слова играем вне мелодии — «покажи happy», «найди дома что-нибудь red». Без этого шага слово остаётся «заперт» в песне.",
            "<b>Концерт:</b> раз в месяц — семейный «вечер караоке», где ребёнок исполняет песни месяца. Публичное исполнение — мощнейший закрепляющий ритуал.",
        ]),
        ("h2", "Типичные ошибки родителей"),
        ("p", "Ошибка первая — фон вместо внимания: песни, играющие целый день фоном, ребёнок перестаёт слышать уже на третий день. Короткое внимательное прослушивание в десять раз ценнее. Ошибка вторая — слишком быстрый темп: начинайте с замедленных версий, скорость придёт сама. Ошибка третья — «ты неправильно поёшь»: не поправляйте произношение во время пения, иначе песня превратится в экзамен. Ошибка четвёртая — остановиться на пассивном слушании: без приёмов из списка выше песни дают фоновую разрядку, но не словарь. Хотите системную работу над языком с учётом всех каналов восприятия — приходите на <a href=\"/test-uroven\">бесплатную диагностику</a>: определим уровень и подберём формат, а заодно посоветуем плейлист под возраст."),
    ],
    "related": [
        ("Словарь по темам для детей", "/english-words"),
        ("Английский для дошкольников", "/doshkolniki"),
        ("Все статьи блога", "/blog"),
    ],
    "faq": [
        ("Действительно ли песни помогают учить английский?", "Да: мелодия и ритм включают дополнительные механизмы памяти, поэтому слова из песен запоминаются быстрее и держатся дольше. Но чтобы слова перешли в активную речь, их нужно использовать вне песни — в играх и разговоре."),
        ("Какие песни выбрать для ребёнка 4–5 лет?", "Песни с повторами и действиями: «Head, Shoulders, Knees and Toes», «If You're Happy and You Know It», «Old MacDonald», «The Wheels on the Bus». Пять-семь доведённых до автоматизма песен дают первые 50–70 слов."),
        ("Можно ли учить английский по «взрослой» музыке?", "Подросткам — да, и это работает отлично: слушаем, открываем текст, разбираем 3–5 новых фраз, подпеваем. Родителям стоит заранее просматривать тексты на предмет взрослого содержания."),
        ("Полезен ли английский «фоном» целый день?", "Почти нет: непрерывный фон мозг быстро перестаёт различать. Десять минут внимательного прослушивания с текстом дают больше, чем пять часов фона."),
    ],
})

BLOG_POST_26 = dict(BLOG_FEED, **{
    "type": "article",
    "alias": "blog-domashka-po-anglijskomu-roditel-bez-yazyka",
    "title": "Как помогать с домашкой по английскому, если вы не знаете языка",
    "description": "Практическое руководство для родителей без английского: как контролировать домашние задания, проверять слова и поддерживать ребёнка, не зная языка самому.",
    "category": "Родителям",
    "date": "2026-08-03",
    "reading_time": "8 минут чтения",
    "hero_grad": "linear-gradient(135deg,#241a36 0%,#4a2e5e 55%,#7a3fa3 100%)",
    "body": [
        ("h2", "Главное: вы не обязаны знать английский"),
        ("p", "Самый частый родительский страх — «я не могу помочь с английским, я сам его не знаю». Ответ методистов однозначен: и не нужно. Роль родителя в домашней работе — не роль второго учителя, а роль организатора и поддержки. Исследования показывают, что на успехи ребёнка влияет не уровень языка у родителя, а три вещи: стабильное время и место для домашки, спокойная эмоциональная атмосфера и интерес («ну-ка, расскажи, что сегодня было»). Всё это доступно родителю с любым языковым багажом. А проверку предметной правильности нужно честно делегировать: учителю, ключам в конце учебника и технологиям. Ниже — конкретные инструменты для каждой задачи."),
        ("h2", "Задача №1: организация, а не контроль знаний"),
        ("p", "Ваша зона ответственности — процесс: у ребёнка есть постоянное место, где лежат учебник, тетрадь и карточки; домашка делается в одно и то же время, до гаджетов и мультиков; длительность адекватна возрасту (младшие школьники — 20–30 минут, средняя школа — 40–60). Проверяйте не «правильно ли», а «сделано ли и аккуратно ли»: открытая тетрадь, выполненные упражнения, отсутствие «я на перемене допишу». Такой контроль не требует языка вообще. Полезный ритуал — вопрос в конце: «Что сегодня было самым сложным?» — он учит ребёнка замечать свои трудности, а это первый шаг к самостоятельности. Разбор школьных будней и ожиданий — в статье «<a href=\"/blog-anglijskij-v-5-klasse-chto-zhdat\">Английский в 5 классе: что ждать</a>»."),
        ("h2", "Задача №2: слова — тут вы незаменимы"),
        ("p", "Парадокс: единственная часть домашки, где родитель без языка эффективнее учителя, — проверка слов. Вам не нужно знать произношение: вы держите карточку или список, говорите слово по-русски, ребёнок отвечает по-английски — правильность видна по списку. Произношение проверяйте не ухом, а транскрипцией или кнопкой озвучки: в нашем <a href=\"/english-words\">словаре по темам</a> у каждого слова есть транскрипция, например темы «<a href=\"/english-words/semya\">Семья</a>» и «<a href=\"/english-words/shkola\">Школа</a>» покрывают большую часть школьных списков 2–4 класса. Десять минут такой проверки через день дают больше, чем час самостоятельной зубрёжки ребёнка. Подробная методика — в статье «<a href=\"/blog-kak-vyuchit-anglijskie-slova-bystro\">Как быстро учить английские слова</a>»."),
        ("h2", "Задача №3: письменные задания — проверяем по ключам"),
        ("p", "У большинства школьных учебников есть ответы: в конце книги, в рабочей тетради для учителя или на сайте издательства. Найдите их один раз и положите в закладки — дальше проверка сводится к сверке: подчеркните несовпадающее, пусть ребёнок сам найдёт ошибку. Не пользуйтесь ГДЗ для списывания «для скорости» — ребёнок мгновенно усваивает, что домашку можно «скачать», и перестаёт думать; ГДЗ — инструмент родителя для проверки, а не ученика для переписывания. Переводчики (Google Translate, Яндекс) используйте только для понимания условия задания, а не для выполнения: машинный перевод упражнения на грамматику — это всегда неправильный ответ с точки зрения учителя, потому что упражнение тренирует конкретную конструкцию."),
        ("h2", "Чего делать нельзя: три частые ошибки"),
        ("ul", [
            "<b>Делать домашку вместо ребёнка.</b> Двойной вред: учитель видит несуществующий уровень и не помогает, а ребёнок учится «мама спасёт». Помощь — это наводящие вопросы, а не готовые ответы.",
            "<b>Поправлять произношение «как слышится».</b> Если вы не уверены на сто процентов — не исправляйте: неверная поправка закрепляется сильнее верной речи. Произношение проверяйте озвучкой словаря.",
            "<b>Превращать домашку в битву.</b> Если каждый вечер заканчивается слезами, проблема не в английском, а в перегрузке или пробеле в базе — это повод поговорить с учителем или пройти диагностику, а не давить сильнее.",
        ]),
        ("h2", "Когда домашней помощи уже мало"),
        ("p", "Есть ситуации, где родительская поддержка упирается в потолок: ребёнок систематически не понимает темы и копит тройки; домашка занимает больше часа при норме в двадцать минут; впереди ВПР или ОГЭ, а база «дырявая». Это не провал родителя — это сигнал, что нужна профессиональная помощь: пробелы в грамматике быстро накапливаются, и дальше каждая новая тема строится на пустоте. У нас для таких случаев есть программы для <a href=\"/mladshie-shkolniki\">младших школьников</a> и <a href=\"/podrostki\">подростков</a> с выравниванием под школьную программу, а для занятых семей — <a href=\"/podderzhivayushchie-online\">поддерживающие онлайн-занятия</a>. Точку входа подскажет бесплатная <a href=\"/test-uroven\">диагностика уровня</a>: после неё педагог честно скажет, справитесь ли вы дома или нужен курс."),
    ],
    "related": [
        ("Словарь по темам с транскрипцией", "/english-words"),
        ("Как быстро учить слова", "/blog-kak-vyuchit-anglijskie-slova-bystro"),
        ("Все статьи блога", "/blog"),
    ],
    "faq": [
        ("Можно ли помогать с английским, не зная языка?", "Да: роль родителя — организация процесса и проверка слов по списку, а не объяснение грамматики. Для проверки письменных заданий есть ответы в конце учебника и на сайте издательства."),
        ("Как проверить произношение ребёнка, если я сам не знаю, как правильно?", "Не на слух: используйте транскрипцию и кнопку озвучки в онлайн-словарях. В нашем словаре по темам транскрипция есть у каждого слова — ребёнок читает её сам, а вы сверяете по-русски."),
        ("Можно ли пользоваться Google-переводчиком для домашки?", "Для понимания условия задания — да. Для выполнения упражнений — нет: переводчик не тренирует нужную грамматическую конструкцию, и учитель видит это сразу. Эффект хуже, чем от невыполненной работы."),
        ("Домашка занимает больше часа — это нормально?", "Нет: норма для младших школьников — 20–30 минут. Если больше — либо ребёнок отвлекается, либо есть пробел в базе. Второе решается с педагогом, а не увеличением вечернего времени."),
    ],
})

BLOG_POST_27 = dict(BLOG_FEED, **{
    "type": "article",
    "alias": "blog-shkola-ili-repetitor-otlichiya",
    "title": "Языковая школа или репетитор: 7 отличий, которые решают всё",
    "description": "Чем языковая школа отличается от репетитора: программа и прогрессия, социализация, замены педагога, цена, контроль качества. Кому что подходит — честный разбор.",
    "category": "Родителям",
    "date": "2026-08-07",
    "reading_time": "8 минут чтения",
    "hero_grad": "linear-gradient(135deg,#241a36 0%,#2e4a5e 55%,#3f8fb3 100%)",
    "body": [
        ("h2", "Это разные продукты, а не «дорого и дёшево»"),
        ("p", "Выбор между языковой школой и репетитором родители обычно сводят к цене — и это ошибка, потому что покупаются разные вещи. Репетитор — это индивидуальный педагог со всем вниманием на вашего ребёнка. Школа — это система: программа, методика, группа сверстников, контроль качества и замены. У каждого продукта есть задачи, с которыми он справляется лучше, и задачи, где он проигрывает. Мы уже разбирали частный случай «<a href=\"/blog-repetitor-ili-gruppa\">репетитор или группа</a>», а здесь сравним системно — по семи параметрам, которые реально влияют на результат. Спойлер: для большинства детей правильный ответ — «и то, и другое, но в разные периоды»."),
        ("h2", "Отличие 1–2: программа и сверстники"),
        ("p", "<b>Программа.</b> В школе ребёнок идёт по выстроенной траектории: уровни, учебники, контрольные точки — следующий год опирается на предыдущий. У репетитора программа зависит от конкретного человека: сильный репетитор строит её сам, слабый — «проходит учебник». Преимущество школы в предсказуемости, репетитора — в гибкости: он может остановиться на «дырявой» теме столько, сколько нужно. <b>Сверстники.</b> Язык — инструмент общения, и группа даёт то, чего репетитор дать не может: переговоры, ролевые игры, соревнование, привычку говорить не только с учителем. Дети в группах статистически быстрее ломают языковой барьер. Зато у репетитора ребёнок говорит больше минут за занятие — вопрос, к чему вы готовите: к экзамену или к живому общению."),
        ("h2", "Отличие 3–4: устойчивость и контроль качества"),
        ("p", "<b>Устойчивость.</b> Репетитор — это один человек: заболел, уехал, устал — занятий нет, а найти замену под свободное окно расписания — недели. В школе педагога заменяют, группа и программа остаются, ребёнок не теряет темп. Для длинного обучения (а язык — это годы) устойчивость важнее, чем кажется на старте. <b>Контроль качества.</b> В лицензированной школе педагогов отбирают, обучают и слушают их занятия; есть методист и куда жаловаться. Качество частного репетитора вы проверяете сами — методом проб, ошибок и отзывов. Хороших репетиторов это не умаляет, но лотерея есть, и цена ошибки — полгода учебного времени ребёнка."),
        ("h2", "Отличие 5–7: цена, гибкость, документы"),
        ("ul", [
            "<b>Цена.</b> Групповые занятия в школе в 2–3 раза дешевле индивидуальных у репетитора того же уровня: у нас групповые программы — от 9000 ₽ в месяц, индивидуальные — от 2500 ₽ в час. Но у репетитора «каждая минута — вашего ребёнка»: при точечной задаче (подтянуть тему к контрольной) 4 занятия с репетитором могут быть выгоднее месяца группы.",
            "<b>Гибкость.</b> Репетитор подстраивает расписание и может прийти домой или онлайн в неудобное время; школа даёт стабильное расписание, но и устойчивую рутину — для детей это чаще плюс, чем минус.",
            "<b>Документы и льготы.</b> Лицензированная школа выдаёт документы об обучении, принимает материнский капитал и даёт право на налоговый вычет 13% — это заметная часть стоимости года. Частный репетитор без статуса самозанятого/ИП этого не даёт.",
        ]),
        ("h2", "Кому что подходит: честная таблица"),
        ("p", "Школа (группа) подходит: дошкольникам и младшим школьникам, которым язык нужен «в рост» и важна мотивация компанией; детям с нормальной учебной мотивацией, идущим в общем потоке; семьям, которым важны стабильность и документы. Репетитор подходит: при конкретной ограниченной задаче — закрыть пробел, подготовиться к пересдаче, срочно подтянуть аудирование к ОГЭ; детям с сильным отставанием, которым в группе сначала будет некомфортно; подросткам с «разбитым» расписанием. И рабочая комбинация, которую мы рекомендуем чаще всего: базовый курс в группе плюс 2–4 индивидуальных занятия в четверти на точечные трудности — и цена разумная, и пробелы не копятся. В Фоксинбурге есть оба формата, тарифы — на странице <a href=\"/tseny\">цен</a>, а определиться поможет <a href=\"/test-format\">тест «Какой формат выбрать»</a> и бесплатная <a href=\"/test-uroven\">диагностика уровня</a>."),
    ],
    "related": [
        ("Репетитор или группа: как выбрать", "/blog-repetitor-ili-gruppa"),
        ("Цены на занятия", "/tseny"),
        ("Все статьи блога", "/blog"),
    ],
    "faq": [
        ("Что эффективнее для ребёнка: школа или репетитор?", "Для долгосрочного обучения — школа: программа, сверстники и устойчивость дают системный рост. Репетитор эффективнее для точечных задач: закрыть пробел, срочно подготовиться к экзамену или контрольной."),
        ("Почему занятия в группе дешевле репетитора?", "Стоимость педагога делится на группу: групповые программы стоят от 9000 ₽ в месяц против 2500 ₽ в час за индивидуальное занятие. При этом в группе ребёнок получает практику общения со сверстниками, которую репетитор не даёт."),
        ("Что делать, если репетитор заболел или уволился?", "В этом слабое место частного формата: замена ищется неделями, и ребёнок теряет темп. В школе педагога заменяют без остановки программы — для обучения на годы это критично."),
        ("Даёт ли обучение налоговый вычет?", "Да, если организация имеет образовательную лицензию: можно вернуть 13% от стоимости обучения ребёнка. Лицензированные школы также принимают материнский капитал; частный репетитор без статуса — нет."),
    ],
})

BLOG_POST_28 = dict(BLOG_FEED, **{
    "type": "article",
    "alias": "blog-anglijskij-dlya-postupleniya-v-gimnaziyu",
    "title": "Английский для поступления в гимназию: что проверяют и как готовиться",
    "description": "Как подготовить ребёнка к вступительным по английскому в гимназии и лицеи: что проверяют на собеседовании и тесте, тайминг подготовки и типичные требования.",
    "category": "Школа и учёба",
    "date": "2026-08-12",
    "reading_time": "8 минут чтения",
    "hero_grad": "linear-gradient(135deg,#241a36 0%,#4a5e26 55%,#7ab33f 100%)",
    "body": [
        ("h2", "Почему в гимназию «просто хорошего» английского мало"),
        ("p", "Вступительные испытания по английскому в сильные школы устроены иначе, чем школьная контрольная. Школьная отметка показывает, что ребёнок выполнил программу; гимназический тест ищет запас прочности: словарь за рамками учебника, уверенное чтение незнакомого текста, готовность говорить с незнакомым взрослым. Вторая особенность — конкурс: при равных баллах выигрывает тот, кто свободнее. Поэтому подготовка «по школьному учебнику» почти всегда проигрывает подготовке «на полступеньки выше». Хорошая новость: формат испытаний предсказуем, и за шесть-двенадцать месяцев планомерной работы нужный запас строится у любого ребёнка с нормальной базой."),
        ("h2", "Что обычно проверяют: четыре блока"),
        ("p", "Типовой набор вступительных по английскому (детали уточняйте в конкретной школе — регламенты публикуются на сайтах). <b>Чтение:</b> незнакомый текст 150–250 слов и вопросы на понимание — проверяют не перевод, а умение вытащить смысл и догадаться о незнакомых словах по контексту. <b>Грамматика и словарь:</b> тест формата «вставь пропущенное» на ключевые времена, предлоги, артикли и тематический словарь. <b>Аудирование:</b> короткий диалог или рассказ с заданиями — самый неожиданный блок для детей, которые «всё знают, но не слышат». <b>Собеседование:</b> 3–5 минут разговора — о себе, семье, увлечениях; оценивают не идеальность, а готовность говорить. Если собеседование ребёнка пугает — почитайте наш материал про <a href=\"/blog-razgovornyj-barjer-u-podrostka\">разговорный барьер</a>: приёмы те же."),
        ("h2", "Тайминг: когда начинать"),
        ("ul", [
            "<b>За 12 месяцев</b> — идеальный сценарий: поднимаем общий уровень на полступени выше требуемого, наращиваем словарь по типовым темам, добавляем ежедневное слушание.",
            "<b>За 6 месяцев</b> — рабочий сценарий при нормальной базе: фокус на формате (тесты, чтение с вопросами, собеседование) плюс ликвидация двух-трёх главных пробелов.",
            "<b>За 2–3 месяца</b> — только тренировка формата: пробные тесты, отработка собеседования, уверенность. Поднять уровень за это время невозможно — можно только показать имеющийся на максимум.",
            "<b>За 2 недели</b> — честный ответ: не готовьтесь, а отдохните и отрепетируйте самопрезентацию. Панические рывки перед испытанием вредят.",
        ]),
        ("h2", "Словарь: какие темы гарантированно встретятся"),
        ("p", "Вступительные тесты собираются из предсказуемого набора тем: семья и описание человека, школа и учебные предметы, дом и еда, хобби и спорт, животные, время и распорядок дня. Пройдите по ним нашим <a href=\"/english-words\">словарём по темам</a>: «<a href=\"/english-words/semya\">Семья</a>», «<a href=\"/english-words/shkola\">Школа</a>», «<a href=\"/english-words/eda\">Еда</a>», «<a href=\"/english-words/zhivotnye\">Животные</a>» — там готовые таблицы с транскрипцией и примерами, удобно устроить проверочные прогоны по 10 минут. Важно: на собеседовании словарь проверяется в речи, поэтому слова нужны активные — ребёнок должен не узнавать их, а называть. Приём: после прогона темы ребёнок рассказывает связный монолог на 5–6 предложений («моя семья», «мой школьный день») — это одновременно и словарь, и репетиция собеседования."),
        ("h2", "Собеседование: что тренируем дома"),
        ("p", "Собеседование валит чаще грамматики: ребёнок, свободно читающий тексты, теряется перед вопросом «Tell me about yourself». Тренировка дома занимает пять минут в день. Заготовьте вместе «каркас» из трёх блоков: о себе и семье (5 предложений), об увлечениях (5 предложений), о любимом школьном предмете (3–4 предложения). Прогоняйте вслух в разных вариациях, чтобы это была речь, а не заученный текст: комиссия мгновенно отличает зубрёжку от живого ответа, и второе ценится выше даже с ошибками. Научите ребёнка трём спасательным фразам: «Could you repeat, please?», «I don't know this word, but…», «Let me think» — умение не растеряться ценится наравне со знанием."),
        ("h2", "Как строим подготовку в Фоксинбурге"),
        ("p", "Мы готовим к вступительным испытаниям по той же логике: сначала бесплатная <a href=\"/test-uroven\">диагностика уровня</a> — она показывает разрыв между текущим и требуемым, затем индивидуальный план: групповые программы для <a href=\"/mladshie-shkolniki\">младших школьников</a> и <a href=\"/podrostki\">подростков</a> как база, индивидуальные занятия — на формат и собеседование. Если ребёнок в 3–4 классе, полезно свериться и со школьным треком — статья «<a href=\"/blog-vpr-po-anglijskomu-4-klass\">ВПР по английскому в 4 классе</a>» хорошо показывает, как выглядит «экзаменационный» формат в этом возрасте. Вопросы по конкретной гимназии и срокам задавайте на <a href=\"/kontakty\">странице контактов</a> — подскажем реалистичный план под вашу дату."),
    ],
    "related": [
        ("Бесплатный тест уровня", "/test-uroven"),
        ("Словарь по темам", "/english-words"),
        ("Все статьи блога", "/blog"),
    ],
    "faq": [
        ("Что проверяют на вступительных по английскому в гимназию?", "Четыре блока: чтение незнакомого текста с вопросами, грамматика и словарь в формате теста, аудирование и короткое собеседование. Точный регламент публикует сама школа — уточняйте на её сайте заранее."),
        ("За сколько начинать подготовку к поступлению?", "Идеально за 12 месяцев, рабочий минимум — 6. За 2–3 месяца можно только отрепетировать формат: пробные тесты и собеседование, но не поднять уровень языка."),
        ("Что важнее на собеседовании: безошибочность или беглость?", "Беглость и готовность говорить. Живой ответ с парой ошибок оценивается выше заученного текста: комиссия проверяет, что ребёнок сможет учиться на интенсивной программе, а не декламировать."),
        ("Какой словарь нужен для вступительного теста?", "Предсказуемый набор тем: семья, школа, дом, еда, хобби, животные, распорядок дня. Важно, чтобы слова были активными — ребёнок называет их в речи, а не только узнаёт в тексте."),
    ],
})

BLOG_POST_29 = dict(BLOG_FEED, **{
    "type": "article",
    "alias": "blog-kogda-nachinat-gotovitsya-k-oge",
    "title": "Когда начинать готовиться к ОГЭ по английскому: план по классам",
    "description": "Оптимальные сроки подготовки к ОГЭ по английскому: что делать в 7, 8 и 9 классе, когда нужен курс, а когда хватает самостоятельной работы. Честный план без паники.",
    "category": "Экзамены",
    "date": "2026-08-14",
    "reading_time": "8 минут чтения",
    "hero_grad": "linear-gradient(135deg,#241a36 0%,#5e2e26 55%,#b3603f 100%)",
    "body": [
        ("h2", "Короткий ответ: за два года, а не за два месяца"),
        ("p", "ОГЭ по английскому — экзамен с непропорциональным соотношением «видимая сложность / реальная сложность». Задания выглядят простыми, формат знаком по учебникам, и семьи откладывают подготовку на весну девятого класса. Именно тогда выясняется, что письменная часть требует автоматизма, устная — беглости, а аудирование — тренированного уха, и ничто из этого не наскакивает за восемь недель. Реальные цифры наших выпускников: дети, готовившиеся системно с восьмого класса, сдают на «пять» без стресса; пришедшие в марте девятого — борются за «четыре». Структуру экзамена мы подробно разобрали в статье «<a href=\"/blog-struktura-oge-po-anglijskomu\">Структура ОГЭ по английскому</a>» — а здесь поговорим о сроках."),
        ("h2", "Седьмой класс: закладываем фундамент"),
        ("p", "В седьмом классе никакой «подготовки к ОГЭ» ещё нет — есть строительство базы, от которой зависит всё. Три фундаментальных блока: времена (к концу 7 класса ребёнок должен уверенно различать Present Simple, Present Continuous, Past Simple, Future Simple и Present Perfect — это 70% грамматики экзамена); чтение со скоростью — 10–15 минут в день любого интересного текста; привычка к звучащей речи — мультфильмы или сериалы пару раз в неделю. Если в конце седьмого класса по этим трём пунктам всё в порядке, экзамен перестаёт быть проблемой в принципе. Если есть «дыры» — седьмой класс последний момент, когда они закрываются дёшево, без гонки."),
        ("h2", "Восьмой класс: старт системной подготовки"),
        ("p", "Восьмой класс — оптимальное время войти в экзаменационный трек. Задачи года: довести до автоматизма всю грамматику базового уровня, нарастить активный словарь по кодификатору (список тем ОГЭ официально опубликован), познакомиться с форматом каждого раздела и начать писать письма по шаблону. В конце восьмого класса обязательно прогоните полный пробный вариант в условиях, приближенных к экзамену: с таймером и без подсказок. Результат пробника — это диагноз: он показывает, какие разделы тянут вниз, и позволяет спланировать девятый класс точечно. Именно в восьмом классе стоит подключать курс <a href=\"/oge-anglijskij\">подготовки к ОГЭ</a>: группа идёт по программе экзамена, а педагог ловит типовые ошибки до того, как они закрепятся."),
        ("h2", "Девятый класс: доводка, а не обучение"),
        ("p", "Правильно построенный девятый класс — это не изучение нового, а доводка: сентябрь–ноябрь закрываем остаточные пробелы, декабрь–февраль — тренировочные варианты целиком раз в одну-две недели с разбором ошибок, март–апрель — отработка устной части (её сдают отдельным днём и валятся на ней чаще всего), май — режим «поддержания формы»: короткие прогоны, никакой новой теории. Параллельно следите за балансом: в девятом классе пять экзаменов, и английский не должен съесть время остальных. Если к сентябрю девятого класса пробник показывает стабильную «тройку» — это повод не паниковать, а перейти на индивидуальный формат: в группе уже не успеть выровнять персональные провалы."),
        ("h2", "Пять сигналов, что пора на курс прямо сейчас"),
        ("ul", [
            "Пробный вариант выполняется дольше регламентированного времени — значит, нет автоматизма, и его тренируют только форматными занятиями.",
            "Устная часть вызывает ступор: ребёнок «знает, но не говорит» — барьер ломается регулярным говорением с педагогом, а не зубрёжкой.",
            "Аудирование стабильно самый слабый раздел — ухо тренируется месяцами, откладывать нельзя.",
            "Оценки по школьному английскому не отражают уровень: «пять» в школе и «тройка» на пробнике — частая и опасная комбинация.",
            "Ребёнок демотивирован и саботирует самостоятельную подготовку — группа и педагог снимают с родителя роль надзирателя.",
        ]),
        ("h2", "Как понять текущую точку и спланировать"),
        ("p", "Первый шаг одинаков в любом классе: замерить текущее состояние. Пройдите бесплатную <a href=\"/test-uroven\">диагностику уровня</a> — по её результатам педагог скажет, сколько времени нужно именно вашему ребёнку и какой формат подойдёт: группа, индивидуально или <a href=\"/online-zanyatiya\">онлайн</a>. Наши группы подготовки к ОГЭ стартуют в сентябре и феврале, программа рассчитана на два года с возможностью входа на второй год после пробника. Цены — на странице <a href=\"/tseny\">тарифов</a>; при оплате доступны налоговый вычет 13% и материнский капитал. Для одиннадцатиклассников всё то же самое, только длиннее — смотрите программу <a href=\"/ege-anglijskij\">подготовки к ЕГЭ</a>."),
    ],
    "related": [
        ("Структура ОГЭ по английскому", "/blog-struktura-oge-po-anglijskomu"),
        ("Подготовка к ОГЭ в Фоксинбурге", "/oge-anglijskij"),
        ("Все статьи блога", "/blog"),
    ],
    "faq": [
        ("Когда оптимально начинать готовиться к ОГЭ по английскому?", "Системная подготовка — с восьмого класса: год на базу и формат, год на доводку. Седьмой класс — время укреплять фундамент (времена, чтение, слушание). Старт в девятом классе возможен, но это уже режим догоняющего."),
        ("Можно ли подготовиться к ОГЭ за 3 месяца?", "Только если база уже крепкая: за три месяца отрабатывается формат и уверенность, но не строятся автоматизм грамматики и тренированное аудирование. При слабой базе реалистичная цель такого срока — уверенная «тройка-четвёрка»."),
        ("Что самое сложное в ОГЭ по английскому?", "Статистически — устная часть и аудирование: их не выучить по учебнику, нужны месяцы регулярной практики. Именно эти разделы стоит начинать тренировать раньше всего."),
        ("Нужен ли репетитор или курс в 7–8 классе?", "В седьмом — достаточно хорошего основного курса и домашней регулярности. С восьмого класса экзаменационный курс окупается: педагог знает специфику ОГЭ и ловит типовые ошибки до того, как они закрепятся."),
    ],
})

BLOG_POST_30 = dict(BLOG_FEED, **{
    "type": "article",
    "alias": "blog-halloween-rozhdestvo-foxinburg",
    "title": "Хэллоуин и Рождество в Фоксинбурге: как праздники учат английскому",
    "description": "Зачем языковой школе праздники: как Хэллоуин, Рождество и другие события Фоксинбурга превращаются в практику английского, и как ребёнку участвовать.",
    "category": "Школа и учёба",
    "date": "2026-08-18",
    "reading_time": "7 минут чтения",
    "hero_grad": "linear-gradient(135deg,#241a36 0%,#3d2e5e 55%,#6e3fb3 100%)",
    "body": [
        ("h2", "Праздник как педагогический инструмент"),
        ("p", "В хорошей языковой школе праздники — не «развлечение вместо занятий», а одна из самых мощных форм обучения. На Хэллоуине ребёнок забывает, что «занимается английским»: он гадает загадки, участвует в квесте, кричит «trick or treat!» — и всё это на языке, который в обычном классе достаётся с усилием. Психологи называют это снижением аффективного фильтра: в состоянии игры и азарта языковой барьер падает, и дети говорят в разы больше, чем на уроке. Вторая функция праздников — культурная: язык существует не в вакууме, и ребёнок, знающий, что такое Рождество в англоязычных странах, понимает тексты и фильмы глубже. Третья — социальная: общие события склеивают группу, а от того, нравится ли ребёнку ходить в школу, зависит половина результата."),
        ("h2", "Хэллоуин: главный «языковой» праздник осени"),
        ("p", "Хэллоуин в Фоксинбурге — традиционно самое громкое событие осени. Формат — костюмированный квест на английском: станции с заданиями (загадки, «spell the word», характерные игры вроде «mummy wrap»), костюм-парад с представлением персонажа на английском и традиционный обход «trick or treat». Словарь праздника дети впитывают без усилий: pumpkin, witch, ghost, spooky, costume — эти слова потом годами всплывают в их речи, потому что привязаны к эмоции. Готовимся заранее: за две недели на занятиях разучиваем песни и чант-скороговорки праздника, обсуждаем костюмы. Родителям совет: не шейте костюм «в секрете» — пусть ребёнок сам представит персонажа по-английски, это часть задания."),
        ("h2", "Рождество и Новый год: тёплый английский декабря"),
        ("p", "Декабрьская программа строится вокруг рождественских традиций англоязычных стран: дети узнают, почему англичане вешают носки у камина, кто такой Santa и при чём тут олень Rudolph, что поют carols. Практический слой — письма Санте на английском (лучшее письменное задание года: мотивация встроенная), рождественские песни и праздничное чаепитие, где каждая группа готовит короткое выступление: сценку, песню или стихотворение. Для младших это первый опыт публичного выступления на языке — бесценный для уверенности. Родители на финальное выступление приглашаются: увидеть ребёнка, поющего «Jingle Bells» в обнимку с группой, — лучший ответ на вопрос «а есть ли толк от занятий»."),
        ("h2", "Чем праздник отличается от урока: честное сравнение"),
        ("ul", [
            "<b>Объём речи:</b> на квесте ребёнок говорит по-английски 30–40 минут подряд в живом общении — столько не даёт ни один урок.",
            "<b>Эмоциональная память:</b> слова и фразы, выученные в игре с азартом, запоминаются в разы прочнее классных.",
            "<b>Культура:</b> праздник даёт культурный контекст, без которого тексты и фильмы понимаются «поверхностно».",
            "<b>Мотивация:</b> события, которые ждут, удерживают интерес к языку длинными зимними месяцами лучше любых похвал.",
            "<b>Что праздник НЕ заменяет:</b> системную грамматику и регулярную практику — это витамин, а не основная еда. Основа — занятия в группах <a href=\"/doshkolniki\">дошкольников</a>, <a href=\"/mladshie-shkolniki\">младших школьников</a> и <a href=\"/podrostki\">подростков</a>.",
        ]),
        ("h2", "Как попасть и что нужно знать родителю"),
        ("p", "Праздники открыты для учеников школы, а часть событий — и для гостей по записи: это хороший способ познакомиться со школой вживую, если вы только присматриваетесь. Анонсы публикуются в разделе <a href=\"/novosti\">новостей</a> за две-три недели до события — там же указаны возраст, дресс-код и нужна ли подготовка. Условия участия уточняйте у администраторов через <a href=\"/kontakty\">контакты</a> или в мессенджере. От родителя требуется немного: помочь с костюмом, привести вовремя и не подсказывать из зала — пусть ребёнок сам справляется со станциями. Если ребёнок стеснительный, предупредите педагога: мы всегда даём таким детям роли «при поддержке» — в паре или с ведущим, а не соло."),
        ("h2", "Календарь учебного года"),
        ("p", "Помимо Хэллоуина и Рождества, в годовом цикле Фоксинбурга есть осенний старт с праздником знакомства, зимние читательские марафоны, весенний speaking club-фестиваль и летние смены <a href=\"/letnyaya-akademiya\">Летней академии</a> с тематическими днями. Всё это складывается в среду, где английский — не предмет два раза в неделю, а часть жизни ребёнка. Именно поэтому наши ученики не спрашивают «зачем мне английский» — у них есть ответ из собственного опыта. Следите за анонсами в <a href=\"/novosti\">новостях</a> и приходите: ближайшее событие уже в календаре."),
    ],
    "related": [
        ("Новости и события школы", "/novosti"),
        ("Английский для младших школьников", "/mladshie-shkolniki"),
        ("Все статьи блога", "/blog"),
    ],
    "faq": [
        ("Праздники в школе — это занятия или развлечение?", "Обучение в игровом формате: квесты, загадки и выступления на английском дают 30–40 минут живой речи за событие и снижают языковой барьер. Но праздник дополняет, а не заменяет регулярные занятия."),
        ("Можно ли прийти на праздник, если ребёнок не учится в школе?", "Часть событий открыта для гостей по записи — это хороший способ познакомиться со школой. Следите за анонсами в разделе новостей, там указаны условия участия."),
        ("Сколько стоит участие в праздниках?", "Условия участия зависят от события и публикуются в анонсе каждого праздника — уточняйте у администраторов."),
        ("Ребёнок стеснительный — ему будет комфортно на квесте?", "Да: задания построены для команд, а не для соло, и педагоги заранее распределяют роли так, чтобы стеснительным детям дать позицию «при поддержке». Предупредите педагога — и всё пройдёт мягко."),
    ],
})

BLOG_POST_31 = dict(BLOG_FEED, **{
    "type": "article",
    "alias": "blog-vesennyaya-akademiya-2026-kak-eto-bylo",
    "title": "Весенняя Академия 2026 изнутри: как проходят каникулы с английским",
    "description": "Рассказываем и показываем, как прошла Весенняя Академия Фоксинбурга 2026: занятия, игры и творческие мастер-классы на английском. Реальные фото и видео смены.",
    "category": "Родителям",
    "date": "2026-08-24",
    "reading_time": "5 минут чтения",
    "hero_grad": "linear-gradient(135deg,#1d4a2e 0%,#2bb673 55%,#a3742a 100%)",
    "body": [
        ("h2", "Что такое Весенняя Академия"),
        ("p", "Весенняя Академия — наша каникулярная языковая смена: пока школа отдыхает, английский у нас не отдыхает. В апреле 2026 года смена собрала учеников на занятия, игры и творческие мастер-классы — всё в языковой среде. Никаких скучных уроков за партой: формат Академии — это погружение через живую деятельность."),
        ("h2", "Как проходил день смены"),
        ("p", "Занятия строились вокруг игровых форматов: дети работали в мини-группах, разыгрывали сценки, отгадывали и описывали — говорение запускается само, когда есть зачем. Творческие мастер-классы добавили движения и ручной работы: когда руки заняты, языковой барьер заметно ниже — ребёнок спрашивает, уточняет и обсуждает на английском, не замечая «урока»."),
        ("html", '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:24px 0">'
                 '<img src="/media/life/2026-04-07-canon/9G6A0047.900.webp" alt="Весенняя Академия Фоксинбурга 2026: занятия и игры" loading="lazy" style="width:100%;height:auto;border-radius:16px">'
                 '<img src="/media/life/2026-04-09-canon/9G6A0333.900.webp" alt="Весенняя Академия Фоксинбурга 2026: творческое занятие" loading="lazy" style="width:100%;height:auto;border-radius:16px">'
                 '</div>'),
        ("h2", "Почему каникулярный формат работает"),
        ("ul", [
            "<b>Плотность.</b> Несколько дней подряд в языковой среде дают эффект погружения, которого нет при занятиях дважды в неделю.",
            "<b>Нет давления оценок.</b> Каникулы — это про интерес: дети пробуют говорить смелее, когда никто не ставит баллы.",
            "<b>Новый контекст.</b> Игры, творчество и командные активности — язык становится инструментом, а не предметом.",
            "<b>Профилактика отката.</b> Каникулы без практики откатывают навык назад; смена не просто удерживает уровень, а двигает вперёд.",
        ]),
        ("h2", "Что говорят фотографии"),
        ("p", "Лучше один раз увидеть: мы собрали <a href=\"/vesennyaya-akademiya-2026\">полную историю смены с фотографиями и видео</a> — всё настоящее, снято на занятиях Академии. А если планируете лето — смотрите программу <a href=\"/letnyaya-akademiya\">Летней Академии</a>: там же есть архивное видео прошлой смены."),
        ("h2", "Как попасть на следующую смену"),
        ("p", "Академии проходят на школьных каникулах: весной и летом, в обоих филиалах в Долгопрудном. Группы комплектуются по возрасту и уровню, места ограничены размером мини-групп. Оставьте заявку на диагностику — определим уровень и забронируем место на следующую смену."),
    ],
    "related": [
        ("Весенняя Академия 2026: фото и видео", "/vesennyaya-akademiya-2026"),
        ("Летняя Академия", "/letnyaya-akademiya"),
        ("Все статьи блога", "/blog"),
    ],
    "faq": [
        ("Когда проходят Академии?", "На школьных каникулях: Весенняя — весной, Летняя — летом. Эта смена прошла в апреле 2026 года в Долгопрудном."),
        ("Подойдёт ли Академия ребёнку с нулевым уровнем?", "Да: группы формируются по уровню, а игровой формат — мягкий вход в язык. Перед сменой проводим диагностику, чтобы попасть в правильную группу."),
        ("Чем Академия отличается от обычных занятий?", "Плотностью и форматом: несколько дней подряд в языковой среде, проекты и мастер-классы вместо стандартного урока — эффект погружения."),
    ],
})

BLOG_POST_32 = dict(BLOG_FEED, **{
    "type": "article",
    "alias": "blog-ekskursii-yu-klinika-pozharnaya-stanciya",
    "title": "Урок за пределами класса: экскурсии в Ю-Клинику и на пожарную станцию",
    "description": "В июне 2026 года ученики Фоксинбурга побывали в Ю-Клинике и на пожарной станции. Рассказываем, зачем языковой школе экскурсии и что дети вынесли из этих выездов. Реальные фото.",
    "category": "Родителям",
    "date": "2026-08-24",
    "reading_time": "5 минут чтения",
    "hero_grad": "linear-gradient(135deg,#123b2e 0%,#1d6f5c 55%,#c24712 100%)",
    "body": [
        ("h2", "Зачем языковой школе пожарная станция"),
        ("p", "Потому что язык нужен, чтобы описывать мир — а мир не помещается в учебник. В июне 2026 года наши ученики побывали на двух настоящих площадках: в медицинской Ю-Клинике и на пожарной станции. Это не «выездное мероприятие для галочки», а часть подхода: реальный опыт даёт языку точку опоры — слова привязываются к впечатлениям и запоминаются надолго."),
        ("h2", "Ю-Клиника: профессия изнутри"),
        ("p", "В клинике дети увидели кабинеты и оборудование, послушали специалистов и задали свои вопросы. Знакомство с профессией врача изнутри — без «белого страха»: когда кабинет перестаёт быть страшным неизвестным, детям проще и на приёме, и в разговоре о профессиях на английском."),
        ("h2", "Пожарная станция: техника, которую можно потрогать"),
        ("p", "На пожарной станции всё было по-настоящему: машины, гидранты, экипировка и рассказы спасателей. Дети увидели, как устроена работа людей, которые приходят на помощь, — и увезли домой не только впечатления, но и живые темы для обсуждения на занятиях."),
        ("html", '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:24px 0">'
                 '<img src="/media/life/2026-06--canon/9G6A4289.900.webp" alt="Ученики Фоксинбурга у здания пожарной станции, июнь 2026" loading="lazy" style="width:100%;height:auto;border-radius:16px">'
                 '<img src="/media/life/2026-06--canon/9G6A4238.900.webp" alt="Ученица Фоксинбурга в фирменной кепке на экскурсии, июнь 2026" loading="lazy" style="width:100%;height:auto;border-radius:16px">'
                 '</div>'),
        ("html", '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:24px 0">'
                 '<img src="/media/life/2026-06--canon/9G6A3689.900.webp" alt="Ученики Фоксинбурга на экскурсии: Ю-Клиника и пожарная станция" loading="lazy" style="width:100%;height:auto;border-radius:16px">'
                 '<img src="/media/life/2026-06--canon/9G6A3861.900.webp" alt="Ученики Фоксинбурга на экскурсии в июне 2026" loading="lazy" style="width:100%;height:auto;border-radius:16px">'
                 '</div>'),
        ("h2", "Что дети вынесли из этих выездов"),
        ("ul", [
            "<b>Новые темы для речи.</b> Профессии, здоровье, безопасность — после экскурсии это не строчки в учебнике, а личный опыт, о котором хочется рассказать.",
            "<b>Расширение кругозора.</b> Дети увидели профессии изнутри и задали сотню вопросов — любопытство лучший двигатель обучения.",
            "<b>Уверенность в новых местах.</b> Клиника и станция перестали быть «страшными незнакомыми местами».",
            "<b>Общие воспоминания группы.</b> Совместные впечатления скрепляют группу — а в дружной группе дети говорят смелее.",
        ]),
        ("h2", "Посмотреть, как это было"),
        ("p", "Все фотографии дня — в нашей <a href=\"/ekskursii\">истории экскурсий</a>: 39 настоящих кадров без постановки. А о других событиях школы — на странице «<a href=\"/zhizn-shkoly\">Жизнь школы</a>»."),
        ("h2", "Как узнать о следующих выездах"),
        ("p", "Анонсы экскурсий и мероприятий публикуются в каналах школы и личном кабинете ученика. Хотите, чтобы ваш ребёнок участвовал, — записывайтесь на диагностику: расскажем о программах и ближайших планах."),
    ],
    "related": [
        ("Экскурсии: Ю-Клиника и пожарная станция", "/ekskursii"),
        ("Жизнь школы", "/zhizn-shkoly"),
        ("Все статьи блога", "/blog"),
    ],
    "faq": [
        ("Куда ездят ученики Фоксинбурга?", "В июне 2026 года — в Ю-Клинику и на пожарную станцию. Площадки выбираем так, чтобы дети увидели профессии и мир изнутри."),
        ("Экскурсии входят в программу?", "Экскурсии и мероприятия — часть жизни школы; условия участия зависят от конкретного события, уточняйте у администратора."),
        ("С какого возраста можно участвовать?", "Выезды проходят для групп разного возраста, программу адаптируем под ребят. Уточните у администратора, что планируется для вашей группы."),
    ],
})

BLOG_POST_33 = dict(BLOG_FEED, **{
    "type": "article",
    "alias": "blog-halloween-v-foxinburge-kak-eto-bylo",
    "title": "Хеллоуин в Фоксинбурге: костюмы, игры и английский без скуки",
    "description": "Как проходит Хеллоуин в языковой школе Фоксинбург: костюмы, грим, игры на английском и тыквы. Реальные фото и видео праздника — и зачем языковой школе Хеллоуин.",
    "category": "Родителям",
    "date": "2026-08-25",
    "reading_time": "4 минуты чтения",
    "hero_grad": "linear-gradient(135deg,#1a0f2e 0%,#4a1d6b 55%,#c24712 100%)",
    "body": [
        ("video", {"kicker": "Видео из архива", "title": "Хеллоуин 2025 — как это было", "lead": "Короткий ролик с нашего Хеллоуина: костюмы, реквизит и игра.", "src": "/media/life/2025-10-27-other/570690408558754058.mp4", "poster": "/media/life/2025-10-27-other/570690408558754058.poster.webp"}),
        ("h2", "Зачем языковой школе Хеллоуин"),
        ("p", "Хеллоуин — родной праздник англоязычной культуры, и для нас это готовый языковой контекст: костюмы, trick or treat, страшные (не очень) истории и игры — всё по-английски. Ребёнок не «учит тему Хеллоуин», а живёт в ней: просит конфеты, обсуждает костюмы, участвует в конкурсах. Такой опыт запоминается крепче любого урока по учебнику."),
        ("h2", "Как это было у нас"),
        ("p", "В октябре 2025 года школа превратилась в декорации праздника: паутина, тыквы, привидения — и дети в костюмах, от ведьмочек до супергероев. Программа — игры, конкурсы костюмов и праздничные задания на английском. Смотрите, как это выглядело:"),
        ("html", '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:24px 0">'
                 '<img src="/media/life/no-date-iphone/IMG_2557.900.webp" alt="Хеллоуин в Фоксинбурге 2025: дети в костюмах на празднике" loading="lazy" style="width:100%;height:auto;border-radius:16px">'
                 '<img src="/media/life/no-date-iphone/IMG_2561.900.webp" alt="Хеллоуин в Фоксинбурге: праздничные декорации и реквизит" loading="lazy" style="width:100%;height:auto;border-radius:16px">'
                 '</div>'),
        ("h2", "Что даёт праздник ученикам"),
        ("ul", [
            "<b>Язык в деле.</b> Все игры и задания — на английском: ребёнок использует язык, а не выполняет упражнение.",
            "<b>Культура через опыт.</b> Хеллоуин перестаёт быть картинкой из учебника — дети проживают традицию сами.",
            "<b>Смелость.</b> В костюме и игре говорить на новом языке проще — барьер растворяется в веселье.",
            "<b>Сообщество.</b> Общий праздник сплачивает группу — а в дружной группе и заниматься интереснее.",
        ]),
        ("h2", "Хотите на следующий?"),
        ("p", "Хеллоуин — ежегодная традиция школы, как и Новый год и Выпускной. Фото и видео всех праздников — на странице «<a href=\"/prazdniki\">Праздники в Фоксинбурге</a>», а свежие события — в разделе «<a href=\"/zhizn-shkoly\">Жизнь школы</a>». Запишитесь на бесплатную диагностику — и ваш ребёнок будет в следующих кадрах."),
    ],
    "related": [
        ("Праздники в Фоксинбурге", "/prazdniki"),
        ("Жизнь школы", "/zhizn-shkoly"),
        ("Все статьи блога", "/blog"),
    ],
    "faq": [
        ("Праздники проходят на английском?", "Да: ведущие и педагоги говорят с детьми на английском в игровой форме — это часть языковой среды школы."),
        ("Можно ли прийти на праздник неученику?", "На многие праздники ученики могут привести друга — уточните у администратора конкретное событие."),
        ("Страшно ли малышам на Хеллоуине?", "Нет: атмосфера весёлая, а не жуткая — костюмы, игры и конфеты. Дети визжат от восторга, а не от страха."),
    ],
})

BLOG_POST_34 = dict(BLOG_FEED, **{
    "type": "article",
    "alias": "blog-novyj-god-2026-v-foxinburge",
    "title": "Новый год в Фоксинбурге 2026: Дед Мороз, игры и подарки",
    "description": "Как прошёл Новый год 2026 в языковой школе Фоксинбург: ёлка, Дед Мороз, игры на английском и подарки. Реальные фото и видео праздника.",
    "category": "Родителям",
    "date": "2026-08-25",
    "reading_time": "4 минуты чтения",
    "hero_grad": "linear-gradient(135deg,#0f2e2a 0%,#1d6f5c 55%,#8f3a2d 100%)",
    "body": [
        ("video", {"kicker": "Видео из архива", "title": "Новый год 2026 — фрагмент праздника", "lead": "Ёлка, Дед Мороз и праздничная программа — как это было.", "src": "/media/life/2025-12-20-other/9197161958741947074.mp4", "poster": "/media/life/2025-12-20-other/9197161958741947074.poster.webp"}),
        ("h2", "Праздник, которого ждут весь год"),
        ("p", "Новый год в Фоксинбурге — большая традиция: ёлка, Дед Мороз, праздничная программа и подарки. В декабре 2025 года праздник прошёл в обоих филиалах — и, как всегда у нас, вся программа шла на английском: дети играли, отгадывали загадки и разговаривали с Дедом Морозом в языковой среде, не замечая «урока»."),
        ("html", '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:24px 0">'
                 '<img src="/media/life/no-date-iphone/IMG_2546.900.webp" alt="Новый год 2026 в Фоксинбурге: ученик с праздничным подарком" loading="lazy" style="width:100%;height:auto;border-radius:16px">'
                 '<img src="/media/life/no-date-iphone/IMG_2538.900.webp" alt="Новый год 2026 в Фоксинбурге: снеговик и ёлочные игрушки ручной работы" loading="lazy" style="width:100%;height:auto;border-radius:16px">'
                 '</div>'),
        ("h2", "Что было на празднике"),
        ("ul", [
            "<b>Ёлка и Дед Мороз</b> — настоящий праздник с персонажами, а не «занятие с гирляндой».",
            "<b>Игры и конкурсы на английском</b> — язык работает как инструмент веселья.",
            "<b>Мастер-классы</b> — ёлочные игрушки и поделки ручной работы: праздник остаётся в руках.",
            "<b>Подарки</b> — каждый ребёнок ушёл домой с подарком и впечатлениями.",
        ]),
        ("h2", "Почему мы празднуем по-крупному"),
        ("p", "Праздники — часть методики: язык живёт там, где эмоции. Ребёнок, который смеялся с Дедом Морозом на английском, запомнит эти слова навсегда. Заодно это и память семьи: такие кадры остаются в альбомах надолго. Больше фото и видео — на странице «<a href=\"/prazdniki\">Праздники в Фоксинбурге</a>»."),
        ("h2", "Как попасть на следующий Новый год"),
        ("p", "Новогодние праздники проходят в декабре в обоих филиалах в Долгопрудном. Анонсы — в каналах школы и личном кабинете. Хотите, чтобы ваш ребёнок был с нами, — записывайтесь на бесплатную диагностику, расскажем о программах."),
    ],
    "related": [
        ("Праздники в Фоксинбурге", "/prazdniki"),
        ("Хеллоуин в Фоксинбурге", "/blog-halloween-v-foxinburge-kak-eto-bylo"),
        ("Все статьи блога", "/blog"),
    ],
    "faq": [
        ("Когда проходит новогодний праздник?", "В декабре, до конца первой полугодия — в обоих филиалах. Точные даты анонсируем в каналах школы."),
        ("Праздник проходит на английском?", "Да, вся программа — в языковой среде: игры, загадки и общение с персонажами на английском в игровой форме."),
        ("Можно ли привести друга?", "На многие праздники ученики могут привести друга — уточните условия у администратора."),
    ],
})

BLOG_POSTS = [BLOG_POST_1, BLOG_POST_2, BLOG_POST_3, BLOG_POST_4, BLOG_POST_5,
              BLOG_POST_6, BLOG_POST_7, BLOG_POST_8, BLOG_POST_9, BLOG_POST_10]
BLOG_POSTS_NEW = [BLOG_POST_20, BLOG_POST_19, BLOG_POST_18, BLOG_POST_17, BLOG_POST_16,
                  BLOG_POST_15, BLOG_POST_14, BLOG_POST_13, BLOG_POST_12, BLOG_POST_11]
BLOG_POSTS_NEW3 = [BLOG_POST_21, BLOG_POST_22, BLOG_POST_23, BLOG_POST_24, BLOG_POST_25,
                   BLOG_POST_26, BLOG_POST_27, BLOG_POST_28, BLOG_POST_29, BLOG_POST_30]

PAGES["page_blog.html"] = {
    "type": "feed",
    "hero_grad": "linear-gradient(135deg,#241a36 0%,#392852 55%,#662d92 100%)",
    "eyebrow": "Блог школы Фоксинбург",
    "h1": "Блог для родителей об английском и учёбе",
    "sub": "Практические разборы без воды: как выбрать курсы и формат, понять уровень ребёнка, подготовиться к ВПР и ОГЭ и помочь со школьной учёбой. Пишут педагоги школы Фоксинбург, Долгопрудный.",
    "lead": "Все статьи блога — по рубрикам «Родителям», «Учим английский», «Экзамены» и «Школа и учёба».",
    "feed_kicker": "Статьи",
    "feed_title": "Все статьи блога",
    "intro_html": '<p class="fxb-lead">О разделе: <b>«Родителям»</b> — выбор курсов, формата и второго языка; '
                  '<b>«Учим английский»</b> — чтение, говорение и домашняя практика; <b>«Экзамены»</b> — ВПР, ОГЭ и ЕГЭ без паники; '
                  '<b>«Школа и учёба»</b> — подготовка к школе и поддержка по школьной программе. '
                  'Короткие новости и анонсы школы живут в разделе <a href="/novosti">«Новости»</a>.</p>',
    "articles": [BLOG_POST_34, BLOG_POST_33, BLOG_POST_32, BLOG_POST_31] + BLOG_POSTS_NEW3 + BLOG_POSTS_NEW + BLOG_POSTS,
    "extra_jsonld": [
        webpage_jsonld(
            "CollectionPage",
            "Блог для родителей об английском и учёбе — Фоксинбург",
            "Статьи школы Фоксинбург для родителей: выбор курсов английского, уровень ребёнка, ВПР и ОГЭ, подготовка к школе. Практика без воды.",
            SITE + "/blog",
        ),
        breadcrumb_jsonld([
            ("Главная", SITE + "/"),
            ("Блог", SITE + "/blog"),
        ]),
    ],
}

PAGES["page_blog_anglijskij_dlya_detej_3_4_goda.html"] = BLOG_POST_1
PAGES["page_blog_kak_nauchit_rebenka_chitat_po_anglijski.html"] = BLOG_POST_2
PAGES["page_blog_rebenok_ne_ponimaet_anglijskij_v_shkole.html"] = BLOG_POST_3
PAGES["page_blog_vpr_po_anglijskomu_4_klass.html"] = BLOG_POST_4
PAGES["page_blog_razgovornyj_barjer_u_podrostka.html"] = BLOG_POST_5
PAGES["page_blog_struktura_oge_po_anglijskomu.html"] = BLOG_POST_6
PAGES["page_blog_gotov_li_rebenok_k_shkole.html"] = BLOG_POST_7
PAGES["page_blog_onlajn_ili_oflajn_anglijskij.html"] = BLOG_POST_8
PAGES["page_blog_kitajskij_dlya_detej.html"] = BLOG_POST_9
PAGES["page_blog_repetitor_ili_gruppa.html"] = BLOG_POST_10
PAGES["page_blog_kak_vyuchit_anglijskie_slova_bystro.html"] = BLOG_POST_11
PAGES["page_blog_present_simple_dlya_roditelej.html"] = BLOG_POST_12
PAGES["page_blog_anglijskij_v_5_klasse_chto_zhdat.html"] = BLOG_POST_13
PAGES["page_blog_skolko_stoit_anglijskij_dlya_rebenka.html"] = BLOG_POST_14
PAGES["page_blog_chtenie_na_anglijskom_s_chego_nachat.html"] = BLOG_POST_15
PAGES["page_blog_kak_vybrat_posobie_po_anglijskomu.html"] = BLOG_POST_16
PAGES["page_blog_letnij_intensiv_itogi_i_plany.html"] = BLOG_POST_17
PAGES["page_blog_oshibki_v_anglijskom_top_15.html"] = BLOG_POST_18
PAGES["page_blog_vesennyaya_akademiya_2026_kak_eto_bylo.html"] = BLOG_POST_31
PAGES["page_blog_ekskursii_yu_klinika_pozharnaya_stanciya.html"] = BLOG_POST_32
PAGES["page_blog_halloween_v_foxinburge_kak_eto_bylo.html"] = BLOG_POST_33
PAGES["page_blog_novyj_god_2026_v_foxinburge.html"] = BLOG_POST_34
PAGES["page_blog_audirovanie_kak_nauchitsya_ponimat.html"] = BLOG_POST_19
PAGES["page_blog_anglijskij_pered_1_sentyabrya.html"] = BLOG_POST_20
PAGES["page_blog_kruzhok_anglijskogo_dlya_doshkolnika.html"] = BLOG_POST_21
PAGES["page_blog_anglijskij_letom_progress.html"] = BLOG_POST_22
PAGES["page_blog_present_perfect_prostymi_slovami.html"] = BLOG_POST_23
PAGES["page_blog_multfilmy_na_anglijskom_po_vozrastam.html"] = BLOG_POST_24
PAGES["page_blog_pesni_na_anglijskom_dlya_detej.html"] = BLOG_POST_25
PAGES["page_blog_domashka_po_anglijskomu_roditel_bez_yazyka.html"] = BLOG_POST_26
PAGES["page_blog_shkola_ili_repetitor_otlichiya.html"] = BLOG_POST_27
PAGES["page_blog_anglijskij_dlya_postupleniya_v_gimnaziyu.html"] = BLOG_POST_28
PAGES["page_blog_kogda_nachinat_gotovitsya_k_oge.html"] = BLOG_POST_29
PAGES["page_blog_halloween_rozhdestvo_foxinburg.html"] = BLOG_POST_30


PAGES["page_novosti.html"] = {
    "type": "feed",
    "hero_grad": "linear-gradient(135deg,#2e1a47 0%,#662d92 55%,#8a4fb8 100%)",
    "eyebrow": "Новости школы",
    "h1": "Новости и статьи",
    "sub": "Полезные материалы для родителей, разборы экзаменов и новости о наших программах. Всё, что помогает ориентироваться в обучении и выбирать подходящий курс.",
    "lead": "Последние публикации Фоксинбурга — о языке, школе и летних программах.",
    "intro_html": '<p class="fxb-lead">Большие практические разборы для родителей — о выборе программы, уровне, экзаменах и учёбе — теперь живут в нашем <a href="/blog">блоге</a>. Здесь — короткие новости и анонсы школы.</p>',
    "articles": [NEWS_POST_15, NEWS_POST_14, NEWS_POST_13, NEWS_POST_12, NEWS_POST_11, NEWS_POST_10, NEWS_POST_9, NEWS_POST_8, NEWS_POST_7, NEWS_POST_6, NEWS_POST_5, NEWS_POST_4, NEWS_POST_3, NEWS_POST_2, NEWS_POST_1],
}

PAGES["page_novosti_so_skolki_let_uchit_anglijskij.html"] = NEWS_POST_1
PAGES["page_novosti_kak_podgotovitsya_k_oge_anglijskij.html"] = NEWS_POST_2
PAGES["page_novosti_kak_prohodyat_smeny_letnej_akademii.html"] = NEWS_POST_3
PAGES["page_novosti_vtoroj_inostrannyj_yazyk_nemeckij_ili_kitajskij.html"] = NEWS_POST_4
PAGES["page_novosti_anglijskij_letom_kak_ne_poteryat_navyk.html"] = NEWS_POST_5
PAGES["page_novosti_kak_ponyat_uroven_rebenka_pered_uchebnym_godom.html"] = NEWS_POST_6
PAGES["page_novosti_zapis_na_novyj_uchebnyj_god_anglijskij_nemeckij_kitajskij.html"] = NEWS_POST_7
PAGES["page_novosti_yazykovaya_shkola_ili_repetitor_kak_vybrat.html"] = NEWS_POST_8
PAGES["page_novosti_anglijskij_dlya_vzroslyh_s_nulya_s_chego_nachat.html"] = NEWS_POST_9
PAGES["page_novosti_lozhnye_druzya_perevodchika_slova_kotorye_obmanyvayut.html"] = NEWS_POST_10

PAGES["page_novosti_komu_nuzhen_repetitor_po_anglijskomu_5_priznakov.html"] = NEWS_POST_11
PAGES["page_novosti_otkryt_nabor_na_novyj_uchebnyj_god_2026.html"] = NEWS_POST_12
PAGES["page_novosti_kak_vybrat_programmu_anglijskogo_dlya_rebenka.html"] = NEWS_POST_13
PAGES["page_novosti_podgotovka_k_novomu_uchebnomu_godu_anglijskij.html"] = NEWS_POST_14
PAGES["page_novosti_start_novogo_uchebnogo_goda_2026.html"] = NEWS_POST_15


def main():
    for fname, data in PAGES.items():
        html = render_page(data)
        path = os.path.join(OUT, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        print("wrote", fname, len(html), "bytes")


if __name__ == "__main__":
    main()
