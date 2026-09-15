"""Тематические листы 3×3 для генерации карточек слов в Meshy.

Каждый лист — 9 слов. Одна генерация nano-banana-pro (9 кредитов) закрывает
девять объектов в одном стиле. Нарезка: scripts/slice_word_sheet.py.
"""
from __future__ import annotations

SHEETS: list[dict] = [
    {"id": "pilot-thumbs", "words": ["bag", "bed", "bus", "cat", "dog", "mug", "pen", "sock", "jug"]},
    {"id": "school-kit", "words": ["book", "pencil", "rubber", "ruler", "case", "desk", "chair", "lamp", "box"]},
    {"id": "home", "words": ["room", "door", "mat", "cup", "hat", "cap", "bell", "well", "hill"]},
    {"id": "pets", "words": ["bird", "fish", "pig", "rat", "owl", "pet", "fox", "duck", "hen"]},
    {"id": "food", "words": ["apple", "banana", "milk", "cake", "bread", "egg", "ham", "jam", "corn"]},
    {"id": "travel", "words": ["car", "train", "ship", "van", "park", "road", "town", "boat", "sport"]},
    {"id": "nature", "words": ["sun", "moon", "tree", "wood", "night", "light", "rain", "star", "farm"]},
    {"id": "body-act", "words": ["feet", "hair", "neck", "chin", "kick", "jog", "sing", "song", "burn"]},
    {"id": "satp", "words": ["sat", "pat", "tap", "tin", "top", "pan", "pin", "map", "man"]},
    {"id": "inmd", "words": ["dig", "lid", "din", "dim", "sand", "gap", "pot", "hot", "cot"]},
    {"id": "gock", "words": ["cut", "kit", "pick", "pack", "rip", "rug", "rib", "hit", "hop"]},
    {"id": "ckeur", "words": ["bat", "bun", "fan", "fog", "fit", "leg", "lip", "lap", "net"]},
    {"id": "hbff", "words": ["puff", "huff", "cuff", "sniff", "stuff", "fill", "pull", "mess", "kiss"]},
    {"id": "llss", "words": ["pass", "less", "boss", "jet", "job", "vet", "vat", "web", "wet"]},
    {"id": "jvwx", "words": ["win", "wag", "wig", "mix", "wax", "tax", "yap", "yell", "yet"]},
    {"id": "yzqu", "words": ["yak", "zip", "zap", "zoo", "buzz", "fizz", "jazz", "quiz", "quit"]},
    {"id": "chsh", "words": ["quick", "quack", "quilt", "chop", "rich", "dish", "shed", "path", "ring"]},
    {"id": "aiee", "words": ["long", "king", "hang", "wait", "sail", "tail", "bee", "high", "fight"]},
    {"id": "ooar", "words": ["sight", "coat", "soap", "loaf", "toad", "food", "boot", "spoon", "foot"]},
    {"id": "owear", "words": ["cook", "arm", "jar", "fork", "turn", "cow", "boil", "soil", "point"]},
    {"id": "sounds", "words": ["oil", "join", "ear", "hear", "near", "year", "dear", "air", "fair"]},
    {"id": "pairs", "words": ["pair", "stairs", "chip", "chat", "shop", "cash", "thin", "thick", "moth"]},
    {"id": "rest", "words": ["pain", "right", "fur", "coin", "log", "pit", "tip", "nap", "hiss"]},
]


def sheet_by_id(sheet_id: str) -> dict:
    for sheet in SHEETS:
        if sheet["id"] == sheet_id:
            return sheet
    raise KeyError(sheet_id)
