#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сборка полноценного статического сайта из фрагментов, которые раньше
вставлялись вручную в T123-блоки Tilda.

Берёт:
  - tilda_shapka.html / tilda_footer.html — общая шапка/подвал;
  - page_*.html — контент каждой страницы (вывод build_subpages.py /
    build_course_pages.py, уже актуален после `make build`);
  - main_combined_v7.html — отдельно собранная главная (уже содержит
    шапку и подвал сама, не оборачивается);
  - seo_meta_live.json — title/description/canonical, снятые с реально
    опубликованных страниц Tilda (не выдуманы, см. DEVLOG);
  - seo_schema/ — sitewide LocalBusiness + по-страничные Course/FAQ/
    BreadcrumbList JSON-LD (карта — seo_schema/DEPLOY_MAP.md).

Каждая страница оборачивается в полный HTML5-документ и раскладывается
как dist/<alias>/index.html (чистые URL без .html, под nginx с
`try_files $uri $uri/ index.html`). Плюс sitemap.xml и robots.txt.

Запуск:
  python3 build_static_site.py            # прод-сборка (индексируемая)
  python3 build_static_site.py --noindex  # стейджинг: noindex,nofollow везде
  python3 build_static_site.py --out dist_staging --noindex
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from datetime import datetime

DIR = os.path.dirname(os.path.abspath(__file__))
SITE = "https://dymova-english.ru"

# page_<slug>.html -> alias на сайте. Совпадает с алиасами в
# tilda_upload_subpages.py / tilda_bootstrap_articles.py.
PAGE_ALIASES = {
    "page_doshkolniki.html": "doshkolniki",
    "page_mladshie_shkolniki.html": "mladshie-shkolniki",
    "page_podrostki.html": "podrostki",
    "page_reading.html": "reading",
    "page_grammar.html": "grammar",
    "page_preparation.html": "preparation",
    "page_online_zanyatiya.html": "online-zanyatiya",
    "page_podderzhivayushchie_online.html": "podderzhivayushchie-online",
    "page_standartnye_offline.html": "standartnye-offline",
    "page_letnyaya_akademiya.html": "letnyaya-akademiya",
    "page_kontakty.html": "kontakty",
    "page_policy.html": "policy",
    "page_novosti.html": "novosti",
    "page_vakansii.html": "vakansii",
    "page_oge_anglijskij.html": "oge-anglijskij",
    "page_ege_anglijskij.html": "ege-anglijskij",
    "page_anglijskij_dlya_vzroslyh.html": "anglijskij-dlya-vzroslyh",
    "page_nemeckij_yazyk.html": "nemeckij-yazyk",
    "page_kitajskij_yazyk.html": "kitajskij-yazyk",
    "page_repetitor.html": "repetitor",
    "page_repetitor_nachalnaya_shkola.html": "repetitor-nachalnaya-shkola",
    "page_novosti_so_skolki_let_uchit_anglijskij.html": "novosti-so-skolki-let-uchit-anglijskij",
    "page_novosti_kak_podgotovitsya_k_oge_anglijskij.html": "novosti-kak-podgotovitsya-k-oge-anglijskij",
    "page_novosti_kak_prohodyat_smeny_letnej_akademii.html": "novosti-kak-prohodyat-smeny-letnej-akademii",
    "page_novosti_vtoroj_inostrannyj_yazyk_nemeckij_ili_kitajskij.html": "novosti-vtoroj-inostrannyj-yazyk-nemeckij-ili-kitajskij",
    "page_novosti_anglijskij_letom_kak_ne_poteryat_navyk.html": "novosti-anglijskij-letom-kak-ne-poteryat-navyk",
    "page_novosti_kak_ponyat_uroven_rebenka_pered_uchebnym_godom.html": "novosti-kak-ponyat-uroven-rebenka-pered-uchebnym-godom",
    "page_novosti_zapis_na_novyj_uchebnyj_god_anglijskij_nemeckij_kitajskij.html": "novosti-zapis-na-novyj-uchebnyj-god-anglijskij-nemeckij-kitajskij",
    "page_novosti_yazykovaya_shkola_ili_repetitor_kak_vybrat.html": "novosti-yazykovaya-shkola-ili-repetitor-kak-vybrat",
    "page_novosti_anglijskij_dlya_vzroslyh_s_nulya_s_chego_nachat.html": "novosti-anglijskij-dlya-vzroslyh-s-nulya-s-chego-nachat",
    "page_novosti_lozhnye_druzya_perevodchika_slova_kotorye_obmanyvayut.html": "novosti-lozhnye-druzya-perevodchika-slova-kotorye-obmanyvayut",
    "page_novosti_komu_nuzhen_repetitor_po_anglijskomu_5_priznakov.html": "novosti-komu-nuzhen-repetitor-po-anglijskomu-5-priznakov",
}

# Статьи уже несут собственную Article+BreadcrumbList JSON-LD внутри себя
# (article_jsonld() в build_subpages.py) — им из seo_schema/ ничего не
# добавляем, чтобы не задвоить разметку.
ARTICLE_ALIASES = {a for a in PAGE_ALIASES.values() if a.startswith("novosti-")}

# alias -> список файлов seo_schema/ (кроме sitewide org_localbusiness.html,
# который идёт на каждую страницу). Взято из seo_schema/DEPLOY_MAP.md.
SCHEMA_MAP = {
    "reading": ["course_reading.html", "breadcrumb_reading.html"],
    "grammar": ["course_grammar.html", "breadcrumb_grammar.html"],
    "preparation": ["course_preparation.html", "breadcrumb_preparation.html"],
    "letnyaya-akademiya": ["course_letnyaya-akademiya.html", "breadcrumb_letnyaya-akademiya.html"],
    "kontakty": ["breadcrumb_kontakty.html"],
    "doshkolniki": ["breadcrumb_doshkolniki.html"],
    "mladshie-shkolniki": ["breadcrumb_mladshie-shkolniki.html"],
    "podrostki": ["breadcrumb_podrostki.html"],
    "online-zanyatiya": ["breadcrumb_online-zanyatiya.html"],
    "podderzhivayushchie-online": ["breadcrumb_podderzhivayushchie-online.html"],
    "standartnye-offline": ["breadcrumb_standartnye-offline.html"],
    "novosti": ["breadcrumb_novosti.html"],
    "vakansii": ["breadcrumb_vakansii.html"],
    "oge-anglijskij": ["course_oge-anglijskij.html", "breadcrumb_oge-anglijskij.html"],
    "ege-anglijskij": ["course_ege-anglijskij.html", "breadcrumb_ege-anglijskij.html"],
    "anglijskij-dlya-vzroslyh": ["course_anglijskij-dlya-vzroslyh.html", "breadcrumb_anglijskij-dlya-vzroslyh.html"],
    "nemeckij-yazyk": ["course_nemeckij-yazyk.html", "breadcrumb_nemeckij-yazyk.html"],
    "kitajskij-yazyk": ["course_kitajskij-yazyk.html", "breadcrumb_kitajskij-yazyk.html"],
    "repetitor": ["course_repetitor.html", "breadcrumb_repetitor.html"],
    "repetitor-nachalnaya-shkola": ["course_repetitor-nachalnaya-shkola.html", "breadcrumb_repetitor-nachalnaya-shkola.html"],
}
INDEX_SCHEMA = ["faq.html"]

# Новые статьи этой сессии не были на живой Tilda -> нет записи в
# seo_meta_live.json. Title/description для них уже заданы в самом
# генераторе (NEWS_POST_*["title"/"description"]) — здесь не дублируем
# вручную, а достаём прямо из HTML (<h1>/шапка статьи), см. extract_article_meta().
NEWS_ALIAS_TITLES_FALLBACK = True


def read(fname: str) -> str:
    with open(os.path.join(DIR, fname), "r", encoding="utf-8") as f:
        return f.read()


def read_schema(fname: str) -> str:
    with open(os.path.join(DIR, "seo_schema", fname), "r", encoding="utf-8") as f:
        return f.read()


def extract_article_meta(html: str) -> tuple[str | None, str | None]:
    """Для новых статей без записи в seo_meta_live.json: title из <h1>,
    description — из уже встроенного в страницу Article JSON-LD (та же
    строка, что задана в NEWS_POST_*["description"] в build_subpages.py),
    а не угадывается по первому абзацу тела."""
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    title = re.sub(r"<[^>]+>", "", h1.group(1)).strip() if h1 else None
    desc_m = re.search(r'"description":\s*"((?:[^"\\]|\\.)*)"', html)
    desc = json.loads(f'"{desc_m.group(1)}"') if desc_m else None
    return title, desc


def build_head(alias: str, title: str, description: str, canonical: str, noindex: bool, extra_schema: list[str], og_type: str = "website") -> str:
    robots = "noindex,nofollow" if noindex else "index,follow"
    og_image = f"{SITE}/assets/og-cover.png"
    parts = [
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        PRELOADER_HEAD,
        '<link rel="icon" type="image/png" href="/favicon.png">',
        f"<title>{title}</title>",
        f'<meta name="description" content="{description}">',
        f'<link rel="canonical" href="{canonical}">',
        f'<meta name="robots" content="{robots}">',
        f'<meta property="og:title" content="{title}">',
        f'<meta property="og:description" content="{description}">',
        f'<meta property="og:url" content="{canonical}">',
        f'<meta property="og:type" content="{og_type}">',
        '<meta property="og:locale" content="ru_RU">',
        '<meta property="og:site_name" content="Языковая школа Фоксинбург">',
        f'<meta property="og:image" content="{og_image}">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:image" content="{og_image}">',
        read_schema("org_localbusiness.html"),
    ]
    for fname in extra_schema:
        parts.append(read_schema(fname))
    return "\n".join(parts)


# WOW-эффекты (prototype/wow/) — scroll-reveal, магнитные кнопки, tilt,
# параллакс — подключаются на всех страницах перед </body>.
# 3D-маскот Фокси (prototype/mascot/): ригнутая модель с 17 клипами
# (сессия 41) — ходит по нижней кромке, реагирует на скорость скролла,
# курсор и CTA. three.js и GLB грузятся ПОСЛЕ load + requestIdleCallback.
# ВАЖНО: importmap обязан идти раньше первого <script type="module"> —
# поэтому он вынесен в PRELOADER_BODY (самое начало <body>).
# Чат-виджет Фокси (бот, POST /api/chat) — на всех страницах, правый нижний угол.
# Cookie-согласие (wow/foxi-consent.js) — баннер с localStorage + событие
# 'fxb-consent' для будущего гейтинга аналитики (сессия 46).
WOW_SNIPPET = (
    '<link rel="stylesheet" href="/wow/foxi-wow.css">\n'
    '<link rel="stylesheet" href="/wow/foxi-consent.css">\n'
    '<script type="module" src="/wow/foxi-wow.js"></script>\n'
    "<script>window.FOXI_CONFIG={modelUrl:'/mascot/foxi-rigged.glb'};</script>\n"
    '<script type="module" src="/mascot/mascot.js"></script>\n'
    '<script src="https://bot.dymova-english.ru/widget/foxi.js" defer></script>\n'
    '<script src="/wow/foxi-consent.js" defer></script>'
)


# Заставка-прелоадер (сессия 46, v2.1): РИГНУТЫЙ 3D-Фокси (/mascot/foxi-rigged.glb,
# клип Big_Wave_Hello) машет над полосой загрузки. Статичного webp-фолбэка НЕТ
# (запрос владельца: «только живой») — пока модель грузится, на градиенте
# просто текст и полоса; canvas плавно проявляется при готовности модели.
# Раскладка: крупная надпись «Языковая школа Фоксинбург» сверху, под ней
# маскот, ниже — полоса загрузки; фон — многослойный брендовый градиент
# с жёлтым/оранжевым свечением. Критический CSS инлайном в <head> первым,
# оверлей и скрипты — первыми в <body>: никакой белой вспышки. Прогресс —
# rAF до 90%, скрытие: window.load И (3D готов ИЛИ прошло 5 с), мин. показ
# 1.2 с, принудительно через 8 с; reduced-motion — без анимаций и ожидания 3D.
# Если GLB пришёл после скрытия заставки — 3D-сцену не стартуем (экономим CPU).
PRELOADER_HEAD = (
    "<style>"
    "#fxb-splash{position:fixed;inset:0;z-index:99999;display:grid;place-items:center;"
    "background:"
    "radial-gradient(120% 90% at 50% 26%,rgba(252,249,81,.13) 0%,rgba(252,249,81,0) 55%),"
    "radial-gradient(100% 80% at 82% 92%,rgba(238,115,73,.2) 0%,rgba(238,115,73,0) 60%),"
    "linear-gradient(135deg,#241a36 0%,#392852 42%,#662d92 78%,#7b4fc0 100%);"
    "transition:opacity .5s ease,visibility .5s}"
    "#fxb-splash::after{content:'';position:absolute;inset:0;pointer-events:none;"
    "background:radial-gradient(60% 45% at 50% 34%,rgba(252,249,81,.1) 0%,rgba(252,249,81,0) 70%);"
    "animation:fxbSplashGlow 3.2s ease-in-out infinite}"
    "@keyframes fxbSplashGlow{0%,100%{opacity:.5}50%{opacity:1}}"
    "#fxb-splash.fxb-splash-done{opacity:0;visibility:hidden;pointer-events:none}"
    ".fxb-splash-inner{position:relative;display:flex;flex-direction:column;align-items:center;gap:16px;padding:24px;text-align:center}"
    ".fxb-splash-brand{font-family:'Montserrat',system-ui,-apple-system,sans-serif;font-weight:700;"
    "font-size:clamp(24px,4.6vw,34px);letter-spacing:.03em;color:rgba(255,255,255,.95);"
    "text-shadow:0 2px 18px rgba(0,0,0,.35)}"
    ".fxb-splash-brand b{font-weight:800;color:#fcf951}"
    ".fxb-splash-stage{position:relative;width:220px;height:210px}"
    ".fxb-splash-3d{position:absolute;inset:0;width:220px;height:210px;opacity:0;transition:opacity .5s ease;"
    "filter:drop-shadow(0 14px 30px rgba(0,0,0,.35))}"
    ".fxb-splash-3d-on .fxb-splash-3d{opacity:1}"
    ".fxb-splash-bar{width:220px;height:7px;border-radius:99px;background:rgba(255,255,255,.16);overflow:hidden;"
    "box-shadow:0 2px 12px rgba(0,0,0,.25)}"
    ".fxb-splash-bar span{display:block;height:100%;width:0;border-radius:99px;"
    "background:linear-gradient(90deg,#fcf951,#ee7349);transition:width .25s ease;"
    "animation:fxbSplashBar 1.9s ease-out forwards}"
    "@keyframes fxbSplashBar{0%{width:0}60%{width:55%}100%{width:88%}}"
    "@media (prefers-reduced-motion:reduce){"
    "#fxb-splash::after{animation:none}.fxb-splash-bar span{animation:none;width:60%}}"
    "</style>"
    # three.js вендорен локально (prototype/mascot/vendor, min-сборки) — без задержек на CDN;
    # modulepreload начинает качать модули сразу, fetch в <head> — GLB и draco-wasm,
    # поэтому живой Фокси появляется практически сразу с началом загрузки
    '<link rel="modulepreload" href="/mascot/vendor/three/build/three.module.min.js">'
    '<link rel="modulepreload" href="/mascot/vendor/three/build/three.core.min.js">'
    '<link rel="modulepreload" href="/mascot/vendor/three/examples/jsm/loaders/GLTFLoader.js">'
    '<link rel="modulepreload" href="/mascot/vendor/three/examples/jsm/loaders/DRACOLoader.js">'
    "<script>window.__fxbPre={"
    "glb:fetch('/mascot/foxi-splash.glb').then(function(r){return r.arrayBuffer();}).catch(function(){return null;}),"
    "wasm:fetch('/mascot/vendor/draco/draco_decoder.wasm').catch(function(){})"
    "};</script>"
)

PRELOADER_BODY = (
    '<script type="importmap">{"imports":{'
    '"three":"/mascot/vendor/three/build/three.module.min.js",'
    '"three/addons/":"/mascot/vendor/three/examples/jsm/"'
    "}}</script>\n"
    '<div id="fxb-splash" aria-hidden="true">'
    '<div class="fxb-splash-inner">'
    '<div class="fxb-splash-brand">Языковая школа <b>Фоксинбург</b></div>'
    '<div class="fxb-splash-stage">'
    '<canvas class="fxb-splash-3d" width="220" height="210"></canvas>'
    "</div>"
    '<div class="fxb-splash-bar"><span></span></div>'
    "</div></div>\n"
    "<noscript><style>#fxb-splash{display:none}</style></noscript>\n"
    # прогресс и скрытие — обычный скрипт, работает даже при недоступном CDN
    "<script>(function(){var s=document.getElementById('fxb-splash');if(!s)return;"
    "var bar=s.querySelector('.fxb-splash-bar span'),t0=performance.now(),done=false,loaded=false;"
    "var rm=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;"
    "var MIN=rm?0:1200,WAIT3D=rm?0:5000,MAX=8000;"
    "function pct(v){if(bar)bar.style.width=v+'%';}"
    "function tick(){if(done)return;var t=(performance.now()-t0)/1800;"
    "pct(Math.min(90,Math.round(t*90)));if(t<1)requestAnimationFrame(tick);}"
    "requestAnimationFrame(tick);"
    "function tryHide(){if(done||!loaded)return;"
    "if(!window.__fxb3dReady&&performance.now()-t0<WAIT3D)return;done=true;pct(100);"
    "var wait=Math.max(0,MIN-(performance.now()-t0));"
    "setTimeout(function(){s.classList.add('fxb-splash-done');"
    "setTimeout(function(){if(window.__fxbSplashStop)window.__fxbSplashStop();"
    "s.parentNode&&s.parentNode.removeChild(s);},600);},wait);}"
    "window.addEventListener('load',function(){loaded=true;tryHide();});"
    "document.addEventListener('fxb-splash-3d-ready',tryHide);"
    "setTimeout(function(){loaded=true;tryHide();},MAX);})();</script>\n"
    # ригнутый Фокси — модуль; GLB уже летит с <head> (__fxbPre.glb) — берём буфер
    # через loader.parse, а не ждём повторную загрузку; three.js локальный (vendor)
    "<script type=\"module\">"
    "try{"
    "const THREE=await import('three');"
    "const{GLTFLoader}=await import('three/addons/loaders/GLTFLoader.js');"
    "const{DRACOLoader}=await import('three/addons/loaders/DRACOLoader.js');"
    "const stage=document.querySelector('.fxb-splash-stage');"
    # сеть слишком медленная: заставка уже скрыта, пока качались модули — тихо выходим
    "if(!stage)throw new Error('splash-already-hidden');"
    "const canvas=stage.querySelector('.fxb-splash-3d');"
    "const renderer=new THREE.WebGLRenderer({canvas,alpha:true,antialias:true});"
    "renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));"
    "renderer.setSize(220,210,false);"
    "const scene=new THREE.Scene();"
    "const camera=new THREE.PerspectiveCamera(40,220/210,0.1,50);"
    "camera.position.set(0,1.0,3.2);camera.lookAt(0,0.85,0);"
    "scene.add(new THREE.HemisphereLight(0xffffff,0xd9c8ff,1.05));"
    "const dl=new THREE.DirectionalLight(0xffffff,1.4);dl.position.set(2,4,3);scene.add(dl);"
    "const draco=new DRACOLoader().setDecoderPath('/mascot/vendor/draco/');"
    "const loader=new GLTFLoader().setDRACOLoader(draco);"
    "const onReady=(gltf)=>{"
    "window.__fxb3dReady=true;"
    # заставка уже скрылась (медленная сеть) — сцену не стартуем, цикл не крутим
    "if(!document.getElementById('fxb-splash'))return;"
    "const model=gltf.scene;"
    "const box=new THREE.Box3().setFromObject(model);"
    "const c=box.getCenter(new THREE.Vector3());"
    "model.position.x-=c.x;model.position.z-=c.z;model.position.y-=box.min.y;"
    "const size=box.getSize(new THREE.Vector3());"
    "const body=new THREE.Group();body.add(model);"
    "body.scale.setScalar(1.7/Math.max(size.y,0.001));"
    "scene.add(body);"
    "const mixer=new THREE.AnimationMixer(model);"
    "const clips={};for(const cl of gltf.animations)clips[cl.name]=mixer.clipAction(cl);"
    "(clips['Big_Wave_Hello']||Object.values(clips)[0]).play();"
    "const clock=new THREE.Clock();"
    "renderer.setAnimationLoop(()=>{mixer.update(clock.getDelta());renderer.render(scene,camera);});"
    "window.__fxbSplashStop=()=>renderer.setAnimationLoop(null);"
    "stage.classList.add('fxb-splash-3d-on');"
    "document.dispatchEvent(new Event('fxb-splash-3d-ready'));"
    "};"
    "const pre=(window.__fxbPre&&window.__fxbPre.glb)||Promise.resolve(null);"
    "const onErr=(e)=>{try{window.__fxb3dError=[String((e&&e.message)||e),Object.prototype.toString.call(e),e&&e.type,e&&e.error].join('|');}catch(_){window.__fxb3dError='unserializable';}};"
    "pre.then((buf)=>{"
    "if(buf)loader.parse(buf,'/mascot/',onReady,onErr);"
    "else loader.load('/mascot/foxi-splash.glb',onReady,undefined,onErr);"
    "}).catch(onErr);"
    "}catch(e){window.__fxb3dError=String((e&&e.message)||e);}</script>"
)


def wrap_page(alias: str, content: str, shapka: str, footer: str, meta: dict, noindex: bool) -> str:
    title = meta.get("title") or f"{alias} — Фоксинбург"
    description = meta.get("description") or ""
    canonical = meta.get("canonical") or f"{SITE}/{alias}"
    extra_schema = INDEX_SCHEMA if alias == "index" else SCHEMA_MAP.get(alias, [])
    og_type = "website"
    if alias in ARTICLE_ALIASES:
        extra_schema = []  # уже есть собственная Article+BreadcrumbList
        og_type = "article"
    head = build_head(alias, title, description, canonical, noindex, extra_schema, og_type)
    body = content if alias == "index" else (shapka + "\n" + content + "\n" + footer)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="ru">\n<head>\n' + head + "\n</head>\n<body>\n"
        + PRELOADER_BODY + "\n" + body + "\n"
        + WOW_SNIPPET + "\n</body>\n</html>\n"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist")
    ap.add_argument("--noindex", action="store_true", help="Стейджинг: noindex,nofollow на всех страницах")
    args = ap.parse_args()

    out_dir = os.path.join(DIR, args.out)
    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(DIR, "seo_meta_live.json"), "r", encoding="utf-8") as f:
        seo_meta = json.load(f)

    shapka = read("tilda_shapka.html")
    footer = read("tilda_footer.html")

    written = []

    # Главная — отдельный случай, уже полностью собрана (шапка+блоки+подвал).
    index_content = read("main_combined_v7.html")
    index_meta = seo_meta.get("index", {})
    index_html = wrap_page("index", index_content, "", "", index_meta, args.noindex)
    index_path = os.path.join(out_dir, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_html)
    written.append(("index", "/", os.path.join(DIR, "main_combined_v7.html")))

    missing_meta = []
    for fname, alias in PAGE_ALIASES.items():
        src_path = os.path.join(DIR, fname)
        if not os.path.exists(src_path):
            print(f"!! пропускаю {fname}: файла нет (запусти `make build`)")
            continue
        content = read(fname)
        meta = dict(seo_meta.get(alias, {}))
        if not meta.get("title") or not meta.get("description"):
            t, d = extract_article_meta(content)
            meta.setdefault("title", t)
            meta.setdefault("description", d)
            if not meta.get("title") or not meta.get("description"):
                missing_meta.append(alias)
        meta.setdefault("canonical", f"{SITE}/{alias}")
        html = wrap_page(alias, content, shapka, footer, meta, args.noindex)
        page_dir = os.path.join(out_dir, alias)
        os.makedirs(page_dir, exist_ok=True)
        with open(os.path.join(page_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)
        written.append((alias, f"/{alias}", src_path))

    # sitemap.xml + robots.txt
    # <lastmod> — mtime исходного файла страницы (page_*.html / главная),
    # если он недоступен — дата сборки.
    build_date = datetime.now().date().isoformat()
    urlset = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for alias, path, src in written:
        loc = SITE + (path if path != "/" else "/")
        try:
            lastmod = datetime.fromtimestamp(os.path.getmtime(src)).date().isoformat()
        except OSError:
            lastmod = build_date
        urlset.append(f"  <url><loc>{loc}</loc><lastmod>{lastmod}</lastmod></url>")
    urlset.append("</urlset>")
    with open(os.path.join(out_dir, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write("\n".join(urlset) + "\n")

    if args.noindex:
        robots = "User-agent: *\nDisallow: /\n"
    else:
        robots = f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n"
    with open(os.path.join(out_dir, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(robots)

    # WOW-ассеты (scroll-эффекты; foxi-3d.js/foxi.glb лежат про запас, не подключаются)
    wow_src = os.path.join(DIR, "wow")
    if os.path.isdir(wow_src):
        shutil.copytree(wow_src, os.path.join(out_dir, "wow"), dirs_exist_ok=True)

    # 3D-маскот (mascot.js + ригнутый foxi-rigged.glb). Демо-страницы
    # (index.html, test-rigged.html) и README в прод не уходят.
    mascot_src = os.path.join(DIR, "mascot")
    if os.path.isdir(mascot_src):
        shutil.copytree(mascot_src, os.path.join(out_dir, "mascot"), dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("*.html", "README.md"))

    # Общие ассеты сайта (og-cover.png и т.п.)
    assets_src = os.path.join(DIR, "assets")
    if os.path.isdir(assets_src):
        shutil.copytree(assets_src, os.path.join(out_dir, "assets"), dirs_exist_ok=True)

    # favicon → корень сайта
    favicon_src = os.path.join(DIR, "favicon.png")
    if os.path.exists(favicon_src):
        shutil.copy(favicon_src, os.path.join(out_dir, "favicon.png"))

    print(f"\nСобрано страниц: {len(written)} -> {out_dir}")
    print(f"robots: {'NOINDEX (стейджинг)' if args.noindex else 'индексируемый (прод)'}")
    if missing_meta:
        print(f"!! нет title/description (ни в seo_meta_live.json, ни в <h1>/<p>): {missing_meta}")


if __name__ == "__main__":
    main()
