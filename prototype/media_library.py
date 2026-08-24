#!/usr/bin/env python3
"""Media Intelligence Layer + переиспользуемые media-блоки (фаза 2).

Читает `prototype/media/manifest.json` (генерирует build_media.py) и отдаёт
рендеры в стиле build_subpages.py (`*_section()`): story_hero, media_wall,
real_moment, video_story. Все блоки — в дизайн-системе fxb-*, с lazy-загрузкой,
srcset, alt, поддержкой prefers-reduced-motion и доступным лайтбоксом.

REAL DATA FIRST: alt/подписи берутся из манифеста (события подписывает
владелец через media_events.MEDIA_EVENTS), ничего не выдумываем.
"""
from __future__ import annotations

import json
from functools import lru_cache
from html import escape
from pathlib import Path

MANIFEST = Path(__file__).resolve().parent / "media" / "manifest.json"


@lru_cache(maxsize=1)
def load_manifest() -> dict:
    if not MANIFEST.exists():
        return {"series": {}, "items": []}
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def items(series: str | None = None, mtype: str | None = None,
          orientation: str | None = None, event: str | None = None,
          limit: int | None = None) -> list[dict]:
    out = []
    for it in load_manifest()["items"]:
        if series and it["series"] != series:
            continue
        if mtype and it["type"] != mtype:
            continue
        if orientation and it.get("orientation") != orientation:
            continue
        if event and it.get("event") != event:
            continue
        out.append(it)
    # сначала закреплённые/hero, затем по id (стабильно)
    out.sort(key=lambda x: (not x.get("featured"), not x.get("hero"), x["id"]))
    return out[:limit] if limit else out


def get(item_id: str) -> dict | None:
    for it in load_manifest()["items"]:
        if it["id"] == item_id:
            return it
    return None


def series_list() -> list[dict]:
    """Серии с метаданными (для хаба «Жизнь школы»)."""
    m = load_manifest()
    return [{"slug": slug, **info} for slug, info in m["series"].items()]


def img_tag(it: dict, default_size: int = 900, cls: str = "", alt: str | None = None,
            eager: bool = False) -> str:
    srcset = it.get("srcset") or {}
    src = "/media/" + (srcset.get(str(default_size)) or it["src"]).lstrip("/")
    ss = ", ".join(f"/media/{v.lstrip(chr(47))} {k}w" for k, v in sorted(srcset.items(), key=lambda kv: int(kv[0])))
    attrs = f'src="{escape(src, quote=True)}"'
    if ss:
        attrs += f' srcset="{escape(ss, quote=True)}" sizes="(max-width: 760px) 92vw, {default_size}px"'
    attrs += f' alt="{escape(alt if alt is not None else it.get("alt", ""), quote=True)}"'
    if it.get("w") and it.get("h"):
        attrs += f' width="{it["w"]}" height="{it["h"]}"'
    attrs += ' decoding="async"' + (" fetchpriority=\"high\"" if eager else ' loading="lazy"')
    return f'<img class="{cls}" {attrs}>'.replace('class="" ', "")


# --- Компоненты -------------------------------------------------------------

# CSS/лайтбокс подключаются пакетом на страницу — см. life_bundle().
# (Глобальная дедупликация невозможна: PAGES рендерятся при импорте в одном процессе.)

MEDIA_CSS = """
<style>
#fxb-page .fxb-story-hero{position:relative;min-height:min(82vh,780px);display:flex;align-items:flex-end;
  justify-content:flex-start;overflow:hidden;isolation:isolate;
  padding:0 clamp(20px,6vw,80px) clamp(32px,6vh,64px)}#fxb-page .fxb-story-hero>.fxb-sh-media{position:absolute;inset:0;z-index:-1}#fxb-page .fxb-story-hero>.fxb-sh-media img{width:100%;height:100%;object-fit:cover}#fxb-page .fxb-story-hero>.fxb-sh-media::after{content:"";position:absolute;inset:0;
  background:linear-gradient(180deg,rgba(36,26,54,.08) 0%,rgba(36,26,54,.26) 46%,rgba(30,20,48,.82) 100%)}#fxb-page .fxb-sh-glass{position:relative;width:100%;max-width:640px;
  padding:clamp(24px,3vw,36px) clamp(24px,3vw,40px);border-radius:24px;
  background:linear-gradient(135deg,rgba(46,26,71,.85) 0%,rgba(36,26,54,.8) 100%);
  backdrop-filter:blur(16px) saturate(1.15);-webkit-backdrop-filter:blur(16px) saturate(1.15);
  border:1px solid rgba(252,249,81,.35);
  box-shadow:0 24px 70px rgba(20,12,36,.45),inset 0 1px 0 rgba(255,255,255,.08);
  color:#fff}#fxb-page .fxb-sh-glass .fxb-eyebrow{display:inline-flex;align-items:center;gap:8px;margin:0;
  padding:7px 14px;border-radius:999px;background:rgba(252,249,81,.14);
  border:1px solid rgba(252,249,81,.4);color:#fcf951;font-size:12px;font-weight:800;
  letter-spacing:.12em;text-transform:uppercase}#fxb-page .fxb-sh-glass h1,#fxb-page .fxb-sh-glass h2{color:#fff;margin:14px 0 12px;
  font-size:clamp(26px,4.2vw,42px);line-height:1.14;letter-spacing:-.01em}#fxb-page .fxb-sh-glass p{margin:0;font-size:clamp(15px,1.6vw,17px);line-height:1.6;color:#efeaf6;
  max-width:56ch}#fxb-page .fxb-media-wall{columns:3 260px;column-gap:14px}#fxb-page .fxb-media-wall figure{margin:0 0 14px;break-inside:avoid;border-radius:18px;overflow:hidden;
  box-shadow:0 8px 24px rgba(57,40,82,.14);position:relative;cursor:zoom-in;background:#fff}#fxb-page .fxb-media-wall img{width:100%;height:auto;display:block;transition:transform .5s ease}#fxb-page .fxb-media-wall figure:hover img{transform:scale(1.035)}#fxb-page .fxb-mw-more{margin-top:18px;text-align:center}#fxb-page .fxb-real-moment{display:grid;grid-template-columns:1.05fr 1fr;gap:34px;align-items:center}#fxb-page .fxb-real-moment .fxb-rm-media{border-radius:26px;overflow:hidden;box-shadow:0 20px 50px rgba(57,40,82,.2);
  transform:rotate(-1.2deg)}#fxb-page .fxb-real-moment .fxb-rm-media img{width:100%;height:auto;display:block}#fxb-page .fxb-rm-kicker{display:inline-flex;align-items:center;gap:8px;font-size:12px;font-weight:800;
  letter-spacing:.12em;text-transform:uppercase;color:#662d92}#fxb-page .fxb-rm-kicker::before{content:"";width:8px;height:8px;border-radius:50%;background:#fcf951;
  box-shadow:0 0 0 4px rgba(252,249,81,.3)}#fxb-page .fxb-rm-quote{font-size:clamp(19px,2.4vw,26px);line-height:1.38;font-weight:700;color:#241a36;margin:12px 0 0}#fxb-page .fxb-rm-caption{margin-top:12px;color:#6f6883;font-size:14px}#fxb-page .fxb-lb{position:fixed;inset:0;z-index:9999;background:rgba(36,26,54,.9);display:none;
  align-items:center;justify-content:center;padding:4vmin}#fxb-page .fxb-lb.fxb-open{display:flex}#fxb-page .fxb-lb img{max-width:100%;max-height:100%;border-radius:14px;box-shadow:0 30px 90px rgba(0,0,0,.5)}#fxb-page .fxb-lb-close{position:absolute;top:18px;right:22px;font-size:34px;color:#fff;background:none;
  border:0;cursor:pointer;line-height:1}#fxb-page .fxb-lb-prev,#fxb-page .fxb-lb-next{position:absolute;top:50%;transform:translateY(-50%);font-size:40px;
  color:#fff;background:rgba(255,255,255,.08);border:0;border-radius:50%;width:56px;height:56px;cursor:pointer}#fxb-page .fxb-lb-prev{left:14px}#fxb-page .fxb-lb-next{right:14px}
@media (max-width:900px){
#fxb-page .fxb-real-moment{grid-template-columns:1fr;gap:20px}#fxb-page .fxb-story-hero{min-height:72vh;padding:0 16px 24px}#fxb-page .fxb-sh-glass{max-width:100%;padding:22px 20px;border-radius:20px}#fxb-page .fxb-media-wall{columns:2 150px}
}
@media (prefers-reduced-motion:reduce){
#fxb-page .fxb-media-wall img{transition:none}
}
</style>
"""

LIGHTBOX_HTML_JS = """
<div class="fxb-lb" id="fxbLifeLb" role="dialog" aria-modal="true" aria-label="Просмотр фотографии">
  <button class="fxb-lb-close" type="button" aria-label="Закрыть (Esc)">&times;</button>
  <button class="fxb-lb-prev" type="button" aria-label="Предыдущее фото">&#8249;</button>
  <img src="" alt="">
  <button class="fxb-lb-next" type="button" aria-label="Следующее фото">&#8250;</button>
</div>
<script>
(function(){
  if (window.__fxbLifeLb) return; window.__fxbLifeLb = true;
  var lb = document.getElementById('fxbLifeLb');
  if (!lb) return;
  var img = lb.querySelector('img'), items = [], idx = 0, lastFocus = null;
  function collect(){
    items = Array.prototype.slice.call(document.querySelectorAll('[data-fxb-lb]'));
    items.forEach(function(el, i){
      el.addEventListener('click', function(){ open(i); });
      el.addEventListener('keydown', function(e){
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(i); }
      });
    });
  }
  function open(i){
    idx = i; show();
    lb.classList.add('fxb-open');
    lastFocus = document.activeElement;
    lb.querySelector('.fxb-lb-close').focus();
    document.body.style.overflow = 'hidden';
  }
  function show(){
    var el = items[idx]; if (!el) return;
    var full = el.getAttribute('data-fxb-lb');
    img.src = full;
    img.alt = (el.querySelector('img') || {}).alt || '';
  }
  function close(){
    lb.classList.remove('fxb-open');
    document.body.style.overflow = '';
    if (lastFocus) lastFocus.focus();
  }
  function step(d){ idx = (idx + d + items.length) % items.length; show(); }
  lb.querySelector('.fxb-lb-close').addEventListener('click', close);
  lb.querySelector('.fxb-lb-prev').addEventListener('click', function(){ step(-1); });
  lb.querySelector('.fxb-lb-next').addEventListener('click', function(){ step(1); });
  lb.addEventListener('click', function(e){ if (e.target === lb) close(); });
  document.addEventListener('keydown', function(e){
    if (!lb.classList.contains('fxb-open')) return;
    if (e.key === 'Escape') close();
    if (e.key === 'ArrowLeft') step(-1);
    if (e.key === 'ArrowRight') step(1);
  });
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', collect);
  } else { collect(); }
})();
</script>
"""


WOW_CSS = """
<style>
#fxb-page .fxb-wow{position:relative;overflow:hidden;padding:clamp(48px,8vh,96px) 0}
#fxb-page .fxb-wow-dark{background:radial-gradient(1200px 600px at 70% 30%,#3a2456 0%,#1b1230 55%,#120c22 100%);color:#fff}
#fxb-page .fxb-wow-light{background:#fdfbff;color:#241a36}
#fxb-page .fxb-wow-in{display:grid;grid-template-columns:1fr 1.15fr;gap:clamp(24px,4vw,64px);
  align-items:center;max-width:1180px;margin:0 auto;padding:0 24px}
#fxb-page .fxb-wow-flip .fxb-wow-in{grid-template-columns:1.15fr 1fr}
#fxb-page .fxb-wow-flip .fxb-wow-txt{order:2}
#fxb-page .fxb-wow-kicker{display:inline-flex;align-items:center;gap:8px;margin:0 0 14px;
  padding:7px 14px;border-radius:999px;font-size:12px;font-weight:800;letter-spacing:.12em;text-transform:uppercase}
#fxb-page .fxb-wow-dark .fxb-wow-kicker{background:rgba(252,249,81,.14);border:1px solid rgba(252,249,81,.4);color:#fcf951}
#fxb-page .fxb-wow-light .fxb-wow-kicker{background:rgba(102,45,146,.08);border:1px solid rgba(102,45,146,.25);color:#662d92}
#fxb-page .fxb-wow h2{margin:0 0 14px;font-size:clamp(26px,3.6vw,40px);line-height:1.15;letter-spacing:-.01em}
#fxb-page .fxb-wow p{margin:0 0 22px;font-size:clamp(15px,1.6vw,17px);line-height:1.65;max-width:52ch}
#fxb-page .fxb-wow-dark p{color:#e9e3f5}
#fxb-page .fxb-wow-light p{color:#5c5470}
#fxb-page .fxb-wow-media{position:relative}
#fxb-page .fxb-wow-media video,#fxb-page .fxb-wow-media img{display:block;width:100%;height:auto}
#fxb-page .fxb-wow-dark .fxb-wow-media video{mix-blend-mode:screen}
#fxb-page .fxb-wow-light .fxb-wow-media video{mix-blend-mode:multiply}
#fxb-page .fxb-wow-alpha .fxb-wow-media video,#fxb-page .fxb-wow-alpha .fxb-wow-media img{mix-blend-mode:normal}
#fxb-page .fxb-wow-alpha .fxb-wow-media video{filter:drop-shadow(0 24px 48px rgba(36,26,54,.28))}
#fxb-page .fxb-wow-link{display:inline-flex;align-items:center;gap:8px;font-weight:800;font-size:15px;
  color:#fcf951;text-decoration:none;border-bottom:2px solid rgba(252,249,81,.4);padding-bottom:2px}
#fxb-page .fxb-wow-light .fxb-wow-link{color:#662d92;border-color:rgba(102,45,146,.35)}
@media (max-width:900px){
  #fxb-page .fxb-wow-in,#fxb-page .fxb-wow-flip .fxb-wow-in{grid-template-columns:1fr;gap:22px}
  #fxb-page .fxb-wow-flip .fxb-wow-txt{order:0}
}
</style>
"""


def wow_scene(name: str, title: str, lead: str, kicker: str = "WOW",
              theme: str = "dark", flip: bool = False, alpha: bool = False,
              link: tuple[str, str] | None = None) -> str:
    """WOW-сцена: видео без фона.

    alpha=False → blend-mode (dark→screen, light→multiply), name.mp4.
    alpha=True  → настоящая прозрачность: name-alpha-v2.mp4 (HEVC hvc1, Safari)
                  + name-alpha-v2.webm (VP9 alpha, Chrome/Firefox), фон любой.
    link — (href, текст) опциональной ссылки.
    """
    cls = "fxb-wow fxb-wow-dark" if theme == "dark" else "fxb-wow fxb-wow-light"
    if flip:
        cls += " fxb-wow-flip"
    if alpha:
        cls += " fxb-wow-alpha"
    a = (f'<a class="fxb-wow-link" href="{escape(link[0], quote=True)}">{escape(link[1])} →</a>'
         if link else "")
    if alpha:
        base = f"/media/wow/{escape(name, quote=True)}-alpha"
        video = (
            '<video autoplay muted loop playsinline preload="metadata" '
            f'data-wow-alpha data-webp="/media/wow/{escape(name, quote=True)}-anim.webp" '
            f'data-alt="{escape(title, quote=True)}" '
            f'data-mp4="{base}-v4.mp4" data-webm="{base}-v4.webm">'
            "</video>"
        )
    else:
        video = (
            '<video autoplay muted loop playsinline '
            f'preload="metadata" poster="/media/wow/{escape(name, quote=True)}.poster.webp">'
            f'<source src="/media/wow/{escape(name, quote=True)}.mp4" type="video/mp4">'
            "</video>"
        )
    return (
        f'<section class="{cls}"><div class="fxb-wow-in">'
        f'<div class="fxb-wow-txt"><span class="fxb-wow-kicker">{escape(kicker)}</span>'
        f"<h2>{title}</h2><p>{lead}</p>{a}</div>"
        f'<div class="fxb-wow-media">{video}</div></div></section>'
    )


WOW_ALPHA_JS = """
<script>
// WOW alpha: Chrome/Firefox → VP9 WebM; Safari → H.264 flat (data-flat),
// а если flat нет — animated WebP (<img>). hvc1-alpha мерцает на macOS Safari,
// animated WebP тормозит — поэтому приоритет у аппаратного H.264.
(function () {
  var isSafari = /^((?!chrome|chromium|android).)*safari/i.test(navigator.userAgent);
  document.querySelectorAll('video[data-wow-alpha]').forEach(function (v) {
    if (isSafari) {
      var flat = v.getAttribute('data-flat');
      if (flat) { v.src = flat; return; }
      var img = document.createElement('img');
      img.src = v.getAttribute('data-webp');
      img.alt = v.getAttribute('data-alt') || '';
      img.setAttribute('aria-hidden', 'true');
      v.replaceWith(img);
    } else {
      v.src = v.getAttribute('data-webm');
    }
  });
})();
</script>
"""


def media_css() -> str:
    return MEDIA_CSS


def lightbox_unit() -> str:
    return LIGHTBOX_HTML_JS


def life_bundle(*sections: str) -> str:
    """Собирает media-секции страницы в один блок: CSS один раз + лайтбокс в конце.
    Использовать так: "extra_sections": [life_bundle(real_moment(...), media_wall(...))].
    """
    parts = [MEDIA_CSS]
    if any("fxb-wow" in s for s in sections):
        parts.append(WOW_CSS)
    parts += [s for s in sections if s]
    if any("data-fxb-lb" in s for s in sections):
        parts.append(LIGHTBOX_HTML_JS)
    if any("data-wow-alpha" in s for s in sections):
        parts.append(WOW_ALPHA_JS)
    return "\n".join(parts)


def story_hero(item_id: str, h1: str, sub: str, kicker: str = "Жизнь школы") -> str:
    it = get(item_id)
    if not it:
        return ""
    return (
        '<section class="fxb-story-hero">'
        + f'<div class="fxb-sh-media">{img_tag(it, 1600, eager=True)}</div>'
        + '<div class="fxb-sh-glass">'
        + f'<span class="fxb-eyebrow"><span class="fxb-dot"></span>{escape(kicker)}</span>'
        + f"<h1>{h1}</h1><p>{sub}</p>"
        + "</div></section>"
    )


def media_wall(series: str | None = None, event: str | None = None,
               limit: int = 12, title: str | None = None, kicker: str = "Реальные моменты",
               light: bool = False) -> str:
    its = items(series=series, event=event, mtype="image", limit=limit)
    if not its:
        return ""
    bg = " fxb-bg-light" if light else ""
    h = [f'<section class="fxb-section{bg}"><div class="fxb-wrap">']
    if title:
        h.append(f'<div class="fxb-head"><span class="fxb-kicker"><span class="fxb-dot"></span>{escape(kicker)}</span>'
                 f'<h2 class="fxb-h2">{title}</h2></div>')
    h.append('<div class="fxb-media-wall">')
    for it in its:
        full = "/media/" + (it.get("srcset", {}).get("1600") or it["src"]).lstrip("/")
        h.append(
            f'<figure data-fxb-lb="{escape(full, quote=True)}" tabindex="0" role="button" '
            f'aria-label="Открыть фото: {escape(it.get("alt", ""), quote=True)}">'
            + img_tag(it, 900)
            + "</figure>"
        )
    h.append("</div></div></section>")
    return "\n".join(h)


def real_moment(item_id: str, quote: str, kicker: str = "Реальный момент",
                caption: str | None = None, light: bool = True) -> str:
    it = get(item_id)
    if not it:
        return ""
    bg = " fxb-bg-light" if light else ""
    cap = caption or it.get("event") or ""
    return (
        f'<section class="fxb-section{bg}"><div class="fxb-wrap">'
        + '<div class="fxb-real-moment">'
        + f'<div class="fxb-rm-media">{img_tag(it, 1600)}</div>'
        + f'<div><span class="fxb-rm-kicker">{escape(kicker)}</span>'
        + f'<p class="fxb-rm-quote">{quote}</p>'
        + (f'<p class="fxb-rm-caption">{escape(cap)}</p>' if cap else "")
        + "</div></div></div></section>"
    )


def video_story(item_id: str, title: str, lead: str | None = None,
                kicker: str = "Видео", light: bool = True) -> str:
    it = get(item_id)
    if not it or it["type"] != "video":
        return ""
    bg = " fxb-bg-light" if light else ""
    h = [f'<section class="fxb-section{bg}"><div class="fxb-wrap">']
    h.append(f'<div class="fxb-head"><span class="fxb-kicker"><span class="fxb-dot"></span>{escape(kicker)}</span>'
             f'<h2 class="fxb-h2">{title}</h2>')
    if lead:
        h.append(f'<p class="fxb-lead">{lead}</p>')
    h.append('</div><div class="fxb-video-wrap"><div class="fxb-video">')
    poster = f' poster="/media/{escape(it["poster"].lstrip("/"), quote=True)}"' if it.get("poster") else ""
    h.append(f'<video controls playsinline preload="metadata"{poster}>')
    h.append(f'<source src="/media/{escape(it["src"].lstrip("/"), quote=True)}" type="video/mp4">')
    h.append("</video></div></div></div></section>")
    h.append(video_jsonld(it, title))
    return "\n".join(h)


SITE = "https://dymova-english.ru"


def video_jsonld(it: dict, title: str) -> str:
    """VideoObject из реальных данных манифеста (дата/событие/постер) —
    видео попадают в видео-поиск Яндекса/Google. Ничего не выдумываем."""
    import re
    name = re.sub(r"<[^>]+>", "", title)
    data = {
        "@context": "https://schema.org",
        "@type": "VideoObject",
        "name": name,
        "description": it.get("alt") or name,
        "contentUrl": f"{SITE}/media/{it['src'].lstrip('/')}",
        "uploadDate": it.get("date", ""),
        "inLanguage": "ru",
        "isFamilyFriendly": True,
    }
    if it.get("poster"):
        data["thumbnailUrl"] = f"{SITE}/media/{it['poster'].lstrip('/')}"
    if not data["uploadDate"]:
        del data["uploadDate"]
    payload = json.dumps(data, ensure_ascii=False)
    return f'<script type="application/ld+json">{payload}</script>'


# ── Видео-отзывы родителей (папка «видео-отзывы», август 2026) ──────────
VIDEO_REVIEWS = ["IMG_2485", "IMG_2486", "IMG_2488", "IMG_2489",
                 "IMG_2490", "IMG_2491", "IMG_2492"]

VIDEO_REVIEWS_CSS = """
#fxb-vreviews{font-family:'Montserrat',Arial,sans-serif;padding:70px 24px;background:linear-gradient(180deg,#f8f5fc 0%,#fff 100%)}
#fxb-vreviews .fxb-vr-wrap{max-width:1200px;margin:0 auto}
#fxb-vreviews .fxb-vr-kicker{display:inline-flex;align-items:center;gap:10px;font-weight:700;font-size:13px;letter-spacing:.16em;text-transform:uppercase;color:#662d92;background:rgba(102,45,146,.08);padding:9px 16px;border-radius:100px}
#fxb-vreviews .fxb-vr-kicker::before{content:"";width:7px;height:7px;border-radius:50%;background:#c24712}
#fxb-vreviews h2{font-weight:800;font-size:clamp(26px,3.6vw,40px);line-height:1.1;letter-spacing:-.02em;color:#241a36;margin:16px 0 10px}
#fxb-vreviews .fxb-vr-lead{color:#6f6883;font-size:16px;font-weight:500;max-width:640px;margin:0 0 30px}
#fxb-vreviews .fxb-vr-row{display:grid;grid-auto-flow:column;grid-auto-columns:min(240px,62vw);gap:16px;overflow-x:auto;scroll-snap-type:x mandatory;padding:4px 4px 18px;-webkit-overflow-scrolling:touch;scrollbar-width:thin}
#fxb-vreviews .fxb-vr-card{scroll-snap-align:start;position:relative;border-radius:20px;overflow:hidden;background:#241a36;box-shadow:0 18px 36px -20px rgba(57,40,82,.5);aspect-ratio:9/16}
#fxb-vreviews video{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;background:#241a36}
#fxb-vreviews .fxb-vr-note{margin:14px 0 0;font-size:13px;color:#6f6883;font-weight:500}
"""


def video_reviews_block(limit: int | None = None) -> str:
    """Карусель видео-отзывов родителей (реальные ролики, media/reviews/)."""
    names = VIDEO_REVIEWS[:limit] if limit else VIDEO_REVIEWS
    cards, schemas = [], []
    for n in names:
        cards.append(
            '<div class="fxb-vr-card">'
            f'<video controls playsinline preload="none" poster="/media/reviews/{n}.poster.webp">'
            f'<source src="/media/reviews/{n}.mp4" type="video/mp4">'
            "</video></div>"
        )
        payload = json.dumps({
            "@context": "https://schema.org", "@type": "VideoObject",
            "name": "Видео-отзыв родителя о школе Фоксинбург",
            "description": "Родитель ученика языковой школы Фоксинбург (Долгопрудный) делится впечатлением о занятиях.",
            "contentUrl": f"{SITE}/media/reviews/{n}.mp4",
            "thumbnailUrl": f"{SITE}/media/reviews/{n}.poster.webp",
            "inLanguage": "ru", "isFamilyFriendly": True,
        }, ensure_ascii=False)
        schemas.append(f'<script type="application/ld+json">{payload}</script>')
    return (
        '<section id="fxb-vreviews"><div class="fxb-vr-wrap">'
        '<span class="fxb-vr-kicker">Видео-отзывы</span>'
        "<h2>Родители рассказывают сами</h2>"
        '<p class="fxb-vr-lead">Настоящие видео-отзывы родителей наших учеников — без сценария и монтажа.</p>'
        f'<div class="fxb-vr-row">{"".join(cards)}</div>'
        '<p class="fxb-vr-note">Листайте вбок — все отзывы сняты родителями добровольно. Текстовые отзывы — ниже и на Яндекс.Картах.</p>'
        "</div>"
        + "".join(schemas)
        + f"<style>{VIDEO_REVIEWS_CSS}</style></section>"
    )
