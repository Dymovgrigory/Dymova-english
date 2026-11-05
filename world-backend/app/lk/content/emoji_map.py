"""Подбор картинки (Fluent Emoji 3D, MIT) к слову: ручные соответствия + авто по названию."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = json.load(open(os.path.join(HERE, "sources/lk_words_sources.json"), encoding="utf-8"))
META = _SRC["emoji_meta"]
D3 = set(_SRC["emoji_3d"])
BY_CLDR = {v["cldr"].lower(): k for k, v in META.items()}
BY_KW = {}
for k, v in META.items():
    for kw in v.get("keywords", []):
        BY_KW.setdefault(kw.lower(), []).append(k)

# слово → cldr-название эмодзи («-» = картинку не ставим осознанно)
MANUAL = {}
_mf = os.path.join(HERE, "emoji_manual.txt")
if os.path.exists(_mf):
    for line in open(_mf, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            a, b = line.split("=", 1)
            MANUAL[a.strip().lower()] = b.strip().lower()

BAD_GROUPS = {"Flags"}

def asset_path(asset):
    for cand in (f"assets/{asset}/3D/", f"assets/{asset}/Default/3D/"):
        hits = sorted(p for p in D3 if p.startswith(cand))
        if hits:
            return hits[0]
    return None

def pick_emoji(word, topics=()):
    w = word.lower()
    if w in MANUAL:
        name = MANUAL[w]
        if name == "-":
            return None
        asset = BY_CLDR.get(name)
        return {"asset": asset, "path": asset_path(asset), "glyph": META[asset]["glyph"]} if asset else None
    cands = []
    for form in (w, w.rstrip("s"), w + " face"):
        if form in BY_CLDR:
            cands.append(BY_CLDR[form])
    if not cands and w in BY_KW and ("general" not in topics and "little-words" not in topics):
        cands = [k for k in BY_KW[w] if META[k].get("group") not in BAD_GROUPS][:1]
    for asset in cands:
        p = asset_path(asset)
        if p:
            return {"asset": asset, "path": p, "glyph": META[asset]["glyph"]}
    return None
