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
import json
from html import escape
from build_course_pages import zayavka_unit

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
#fxb-page .fxb-video-wrap{max-width:400px;margin:0 auto}
#fxb-page .fxb-video{position:relative;width:100%;border-radius:24px;overflow:hidden;background:#241a36;box-shadow:0 30px 60px -30px rgba(57,40,82,.6);border:1px solid rgba(57,40,82,.1)}
#fxb-page .fxb-video video{display:block;width:100%;height:auto}
</style>
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
#fxb-page .fxb-breadcrumbs{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;align-items:center;margin:0 auto 28px;font-size:13px;font-weight:700;color:rgba(57,40,82,.72)}
#fxb-page .fxb-breadcrumbs a{color:var(--purple-2)}
#fxb-page .fxb-breadcrumbs a:hover{color:var(--orange)}
#fxb-page .fxb-breadcrumbs span{color:rgba(57,40,82,.44)}
#fxb-page .fxb-related{max-width:760px;margin:44px auto 0}
#fxb-page .fxb-related h2{font-size:22px;font-weight:800;color:var(--ink);margin-bottom:14px}
#fxb-page .fxb-related-list{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
#fxb-page .fxb-related-list a{display:block;background:#fff;border:1px solid rgba(57,40,82,.08);border-radius:16px;padding:16px 18px;box-shadow:0 12px 28px -20px rgba(57,40,82,.35);color:var(--purple-2);font-weight:800;line-height:1.35}
#fxb-page .fxb-related-list a:hover{border-color:rgba(102,45,146,.22);color:var(--orange)}
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
#fxb-page .fxb-news-card{display:flex;flex-direction:column;background:#fff;border:1px solid rgba(57,40,82,.08);border-radius:20px;overflow:hidden;box-shadow:0 16px 36px -22px rgba(57,40,82,.4);transition:transform .35s,box-shadow .35s,border-color .35s}
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
ROADMAP = "https://raw.githubusercontent.com/Dymovgrigory/Dymova-english/3060ea827cc6304ed2419454ea5bbf9e6d7c19f0/brand-assets/roadmaps/"


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
    if p.get("advantages"):
        h.append(card_grid_section(p.get("adv_kicker", "Почему мы"), p["adv_title"], p.get("adv_lead"), p["advantages"], light=False))
    if p.get("team"):
        h.append(card_grid_section("Педагоги", p["team_title"], p.get("team_lead"), p["team"], light=True))
    if p.get("ladder"):
        h.append(ladder_section(p.get("ladder_kicker", "Лестница знаний"), p["ladder_title"], p.get("ladder_lead"), p["ladder"], light=False))
    if p.get("video"):
        v = p["video"]
        h.append(video_section(v.get("kicker", "Видео"), v["title"], v.get("lead"), v["src"], v["poster"], light=True))
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
    h.append(JS)
    return "\n".join(h)


def article_jsonld(p):
    url = SITE + "/" + p["alias"]
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
            {"@type": "ListItem", "position": 2, "name": "Новости", "item": SITE + "/novosti"},
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
    h.append('<div id="fxb-page" class="fxb-feed-page">')
    h.append('<section class="fxb-hero" style="background:' + p["hero_grad"] + '">')
    h.append('<div class="fxb-hero-bg"><img class="fxb-hd1" src="' + DECOR_SWIRL + '" alt="" loading="lazy"><img class="fxb-hd2" src="' + DECOR_FOX + '" alt="" loading="lazy"></div>')
    h.append('<div class="fxb-hero-inner">')
    h.append('<span class="fxb-eyebrow"><span class="fxb-dot"></span>' + p["eyebrow"] + '</span>')
    h.append('<h1 class="fxb-h1">' + p["h1"] + '</h1>')
    h.append('<p class="fxb-sub">' + p["sub"] + '</p>')
    h.append('</div></section>')
    h.append('<section class="fxb-section"><div class="fxb-wrap">')
    h.append('<div class="fxb-head"><span class="fxb-kicker"><span class="fxb-dot"></span>Архив</span>')
    h.append('<h2 class="fxb-h2">Последние статьи</h2>')
    if p.get("lead"):
        h.append('<p class="fxb-lead">' + p["lead"] + '</p>')
    h.append('</div>')
    h.append('<div class="fxb-feed-grid">')
    for art in sorted(p["articles"], key=lambda a: a["date"], reverse=True):
        h.append(news_card(art))
    h.append('</div></div></section>')
    h.append('</div>')
    h.append(CSS)
    h.append(FEED_CSS)
    h.append(JS)
    return "\n".join(h)


def article_page(p):
    h = []
    h.append('<div id="fxb-page" class="fxb-blog-page">')
    h.append('<section class="fxb-hero" style="background:' + p["hero_grad"] + '">')
    h.append('<div class="fxb-hero-bg"><img class="fxb-hd1" src="' + DECOR_SWIRL + '" alt="" loading="lazy"><img class="fxb-hd2" src="' + DECOR_FOX + '" alt="" loading="lazy"></div>')
    h.append('<div class="fxb-hero-inner">')
    h.append('<span class="fxb-eyebrow"><span class="fxb-dot"></span>' + escape(p["category"]) + '</span>')
    h.append('<h1 class="fxb-h1">' + p["title"] + '</h1>')
    h.append('<div class="fxb-article-meta"><span>' + escape(format_date_ru(p["date"])) + '</span><span>' + escape(p["reading_time"]) + '</span></div>')
    h.append('</div></section>')
    h.append('<section class="fxb-section"><div class="fxb-wrap">')
    h.append('<nav class="fxb-breadcrumbs"><a href="/">Главная</a><span>→</span><a href="/novosti">Новости</a><span>→</span><span>' + escape(p["title"]) + '</span></nav>')
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
    "ladder_title": 'Лестница знаний — программа по <span class="fxb-accent">годам</span>',
    "ladder_lead": "Наши курсы для младших школьников по ступеням: посмотрите подробную карту тем на учебный год по каждому уровню.",
    "ladder": [
        {"group":"Английский · My level", "items":[
           ("My level 1", "6–8 лет · Pre-A1", ROADMAP+"my-level-1.png"),
           ("My level 2", "8–9 лет · Pre-A1 → A1", ROADMAP+"my-level-2.png"),
           ("My level 3", "9–10 лет · A1", ROADMAP+"my-level-3.png"),
           ("My level 4", "10–11 лет · A1 → A2", ROADMAP+"my-level-4.png"),
        ]},
        {"group":"Английский · Super Minds", "items":[
           ("Super Minds 1", "7–8 лет · Pre-A1", ROADMAP+"super-minds-1.png"),
           ("Super Minds 2", "8–9 лет · A1", ROADMAP+"super-minds-2.png"),
           ("Super Minds 3", "9–10 лет · A1–A2", ROADMAP+"super-minds-3.png"),
           ("Super Minds 4", "10–11 лет · A2", ROADMAP+"super-minds-4.png"),
        ]},
        {"group":"Китайский язык", "items":[
           ("Веселый урок", "1–4 класс · 中文 HSK 1", ROADMAP+"veselyj-urok-1-4-klass.png"),
        ]},
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
    "ladder_title": 'Лестница знаний — программа по <span class="fxb-accent">годам</span>',
    "ladder_lead": "Курсы для подростков по ступеням: откройте карту тем на учебный год по каждому уровню.",
    "ladder": [
        {"group":"Английский · Get involved", "items":[
           ("Get involved A1", "11–13 лет · A1", ROADMAP+"get-involved-a1.png"),
           ("Get involved A2", "12–14 лет · A2", ROADMAP+"get-involved-a2.png"),
        ]},
        {"group":"Китайский язык", "items":[
           ("Открывая Китай", "5 класс + · 中文 HSK 1–2", ROADMAP+"otkryvaya-kitaj-5-klass.png"),
        ]},
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
    "video": {
        "kicker": "Как это проходит",
        "title": 'Летняя Академия — <span class="fxb-accent">вживую</span>',
        "lead": "Атмосфера смены: как проходят занятия, проекты и общение в Академии.",
        "src": "https://cdn.jsdelivr.net/gh/Dymovgrigory/Dymova-english@gh-pages/media/summer-academy.mp4",
        "poster": "https://cdn.jsdelivr.net/gh/Dymovgrigory/Dymova-english@gh-pages/media/summer-academy-poster.jpg",
    },
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
        ("group", "До 7 человек", "Мини-группы по уровню и целям"),
    ],
    "adv_title": 'Почему выбирают <span class="fxb-accent">Фоксинбург</span>',
    "adv_lead": "Языковая школа в Долгопрудном с 2020 года — с лицензией, своей методикой и вниманием к каждому ученику.",
    "advantages": [
        ("shield", "Лицензия и опыт с 2020 года", "Официальная образовательная лицензия и годы практики в обучении детей и взрослых."),
        ("check", "Маткапитал и налоговый вычет", "Занятия можно оплатить материнским капиталом и вернуть 13% стоимости налоговым вычетом."),
        ("group", "Мини-группы", "Небольшие группы по уровню и возрасту — педагог видит и слышит каждого ученика."),
        ("chart", "Ежемесячный отчёт", "Каждый месяц — подробный индивидуальный отчёт от педагога об успеваемости ребёнка."),
        ("monitor", "Оффлайн и онлайн", "Два филиала в Долгопрудном рядом с МФТИ и удобный онлайн-формат — как вам удобно."),
        ("star", "Рейтинг 4,8 и своё приложение", "Высокие оценки родителей и мобильное приложение, где дети тренируют слова и копят награды."),
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
        ("А если у ребёнка слабый уровень?", "Начнём с бесплатной диагностики, подберём группу по уровню и подтянем базу параллельно с отработкой формата экзамена."),
        ("Можно ли оплатить материнским капиталом?", "Да. Занятия можно оплатить материнским капиталом, а также вернуть 13% стоимости налоговым вычетом."),
        ("Занятия очно или онлайн?", "Есть оба формата: очно в Долгопрудном (два филиала рядом с МФТИ) и онлайн."),
        ("Сколько человек в группе?", "Занимаемся в мини-группах до 7 человек, подобранных по уровню и целям."),
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
        ("group", "До 7 человек", "Мини-группы по уровню"),
    ],
    "adv_title": 'Почему выбирают <span class="fxb-accent">Фоксинбург</span>',
    "adv_lead": "Языковая школа в Долгопрудном с 2020 года — с лицензией, своей методикой и вниманием к каждому ученику.",
    "advantages": [
        ("shield", "Лицензия и опыт с 2020 года", "Официальная образовательная лицензия и годы практики в обучении детей и взрослых."),
        ("check", "Маткапитал и налоговый вычет", "Занятия можно оплатить материнским капиталом и вернуть 13% стоимости налоговым вычетом."),
        ("group", "Мини-группы", "Небольшие группы по уровню и возрасту — педагог видит и слышит каждого ученика."),
        ("chart", "Ежемесячный отчёт", "Каждый месяц — подробный индивидуальный отчёт от педагога об успеваемости ребёнка."),
        ("monitor", "Оффлайн и онлайн", "Два филиала в Долгопрудном рядом с МФТИ и удобный онлайн-формат — как вам удобно."),
        ("star", "Рейтинг 4,8 и своё приложение", "Высокие оценки родителей и мобильное приложение, где дети тренируют слова и копят награды."),
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
        ("Сколько человек в группе?", "Мини-группы до 7 человек, подобранные по уровню."),
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
    "adv_title": 'Почему выбирают <span class="fxb-accent">Фоксинбург</span>',
    "adv_lead": "Языковая школа в Долгопрудном с 2020 года — с лицензией, своей методикой и вниманием к каждому ученику.",
    "advantages": [
        ("shield", "Лицензия и опыт с 2020 года", "Официальная образовательная лицензия и годы практики в обучении детей и взрослых."),
        ("check", "Маткапитал и налоговый вычет", "Занятия можно оплатить материнским капиталом и вернуть 13% стоимости налоговым вычетом."),
        ("group", "Мини-группы", "Небольшие группы по уровню и возрасту — педагог видит и слышит каждого ученика."),
        ("chart", "Ежемесячный отчёт", "Каждый месяц — подробный индивидуальный отчёт от педагога об успеваемости ребёнка."),
        ("monitor", "Оффлайн и онлайн", "Два филиала в Долгопрудном рядом с МФТИ и удобный онлайн-формат — как вам удобно."),
        ("star", "Рейтинг 4,8 и своё приложение", "Высокие оценки родителей и мобильное приложение, где дети тренируют слова и копят награды."),
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
    "adv_title": 'Почему выбирают <span class="fxb-accent">Фоксинбург</span>',
    "adv_lead": "Языковая школа в Долгопрудном с 2020 года — с лицензией, своей методикой и вниманием к каждому ученику.",
    "advantages": [
        ("shield", "Лицензия и опыт с 2020 года", "Официальная образовательная лицензия и годы практики в обучении детей и взрослых."),
        ("check", "Маткапитал и налоговый вычет", "Занятия можно оплатить материнским капиталом и вернуть 13% стоимости налоговым вычетом."),
        ("group", "Мини-группы", "Небольшие группы по уровню и возрасту — педагог видит и слышит каждого ученика."),
        ("chart", "Ежемесячный отчёт", "Каждый месяц — подробный индивидуальный отчёт от педагога об успеваемости ребёнка."),
        ("monitor", "Оффлайн и онлайн", "Два филиала в Долгопрудном рядом с МФТИ и удобный онлайн-формат — как вам удобно."),
        ("star", "Рейтинг 4,8 и своё приложение", "Высокие оценки родителей и мобильное приложение, где дети тренируют слова и копят награды."),
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
}

NEWS_POST_3 = {
    "type": "article",
    "alias": "novosti-kak-prohodyat-smeny-letnej-akademii",
    "title": "Как проходят смены Летней Академии",
    "description": "Рассказываем, как устроены смены Летней Академии: тематические недели, проекты, мини-группы и комфортный утренний формат.",
    "category": "События школы",
    "date": "2025-06-25",
    "reading_time": "7 минут чтения",
    "hero_grad": "linear-gradient(135deg,#ee7349 0%,#f7971e 50%,#fcc419 100%)",
    "body": [
        ("video", {
            "kicker": "Видео",
            "title": "Летняя Академия — вживую",
            "lead": "Короткий ролик показывает атмосферу смен: как дети занимаются, общаются и включаются в проекты.",
            "src": "https://cdn.jsdelivr.net/gh/Dymovgrigory/Dymova-english@gh-pages/media/summer-academy.mp4",
            "poster": "https://cdn.jsdelivr.net/gh/Dymovgrigory/Dymova-english@gh-pages/media/summer-academy-poster.jpg",
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
}

PAGES["page_novosti.html"] = {
    "type": "feed",
    "hero_grad": "linear-gradient(135deg,#2e1a47 0%,#662d92 55%,#8a4fb8 100%)",
    "eyebrow": "Новости школы",
    "h1": "Новости и статьи",
    "sub": "Полезные материалы для родителей, разборы экзаменов и новости о наших программах. Всё, что помогает ориентироваться в обучении и выбирать подходящий курс.",
    "lead": "Последние публикации Фоксинбурга — о языке, школе и летних программах.",
    "articles": [NEWS_POST_3, NEWS_POST_2, NEWS_POST_1],
}

PAGES["page_novosti_so_skolki_let_uchit_anglijskij.html"] = NEWS_POST_1
PAGES["page_novosti_kak_podgotovitsya_k_oge_anglijskij.html"] = NEWS_POST_2
PAGES["page_novosti_kak_prohodyat_smeny_letnej_akademii.html"] = NEWS_POST_3


def main():
    for fname, data in PAGES.items():
        html = render_page(data)
        path = os.path.join(OUT, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        print("wrote", fname, len(html), "bytes")


if __name__ == "__main__":
    main()
