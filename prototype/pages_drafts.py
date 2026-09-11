# -*- coding: utf-8 -*-
"""Черновики блога из прерванной сессии 2026-09-11 (43 статьи).

Файлы лежат в blog_drafts/*.py, каждый определяет dict POST в контракте
статьи (alias, title, description, category, date, reading_time, hero_grad,
body, related, faq) — как в pages_lang_news.py, но без BLOG_FEED-полей.

Импортируется из build_subpages.py; DRAFT_POSTS подключается в
EXTRA_BLOG_POSTS.
"""

import importlib.util as _ilu
import os as _os
import sys as _sys

if hasattr(_sys.modules.get("__main__"), "PAGES"):
    B = _sys.modules["__main__"]  # build_subpages запущен как скрипт
else:
    import build_subpages as B

DRAFTS_DIR = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "blog_drafts")


def _load_drafts():
    posts = []
    for fname in sorted(_os.listdir(DRAFTS_DIR)):
        if not fname.endswith(".py"):
            continue
        mod_name = "draft_" + fname[:-3].replace("-", "_")
        spec = _ilu.spec_from_file_location(mod_name, _os.path.join(DRAFTS_DIR, fname))
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        posts.append(dict(B.BLOG_FEED, **mod.POST))
    return posts


DRAFT_POSTS = _load_drafts()
