"""Мини-минификатор Tilda-блоков."""

from __future__ import annotations

import re


def minify(src: str) -> str:
    src = re.sub(r"<!--.*?-->", "", src, flags=re.S)
    src = re.sub(r"\n\s*", " ", src)
    src = re.sub(r">\s+<", "><", src)
    src = re.sub(r"[ \t]{2,}", " ", src)
    return src.strip()
