"""Сборка базы слов ЛК (2026-11-05).

Источники (content/sources/lk_words_sources.json, скачаны 05.11.2026):
* CEFR-J Wordlist 1.5 (Tono Laboratory, TUFS; бесплатно, с указанием источника) — уровни A1/A2;
* ipa-dict en_UK / en_US (open-dict-data, MIT) — транскрипция IPA;
* Microsoft Fluent UI Emoji 3D (MIT) — картинки к словам.
Переводы и темы — content/words/*.txt (составлены для школы).
Результат: content/words.json (наборы по темам и уровням) и список нужных картинок.
"""
import csv, glob, io, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = json.load(open(os.path.join(HERE, "sources/lk_words_sources.json"), encoding="utf-8"))

# ---------- уровни CEFR-J ----------
LEVEL = {}
for r in csv.DictReader(io.StringIO(SRC["cefrj"])):
    for w in r["headword"].split("/"):
        w = w.strip().lower()
        if w and (w not in LEVEL or r["CEFR"] < LEVEL[w]):
            LEVEL[w] = r["CEFR"]

# ---------- IPA ----------
def _ipa_dict(text):
    d = {}
    for line in text.splitlines():
        if "\t" not in line:
            continue
        w, p = line.split("\t", 1)
        d.setdefault(w.lower(), p.split(",")[0].strip().strip("/"))
    return d
IPA_UK, IPA_US = _ipa_dict(SRC["ipa_uk"]), _ipa_dict(SRC["ipa_us"])
IPA_FIX = {"hippo": "ˈhɪpəʊ", "kitten": "ˈkɪtn", "trainers": "ˈtreɪnəz", "pyjamas": "pəˈdʒɑːməz",
           "ok": "ˌəʊˈkeɪ", "t-shirt": "ˈtiː ʃɜːt", "pe": "ˌpiː ˈiː", "tv": "ˌtiː ˈviː", "id": "ˌaɪ ˈdiː",
           "app": "æp", "email": "ˈiːmeɪl", "online": "ˌɒnˈlaɪn", "smartphone": "ˈsmɑːtfəʊn",
           "laptop": "ˈlæptɒp", "website": "ˈwebsaɪt", "superhero": "ˈsuːpəhɪərəʊ", "hedgehog": "ˈhedʒhɒɡ",
           "headteacher": "ˌhedˈtiːtʃə", "skateboarding": "ˈskeɪtbɔːdɪŋ", "snowboarding": "ˈsnəʊbɔːdɪŋ",
           "firefighter": "ˈfaɪəfaɪtə", "schoolbag": "ˈskuːlbæɡ", "stomachache": "ˈstʌmək eɪk",
           "o'clock": "əˈklɒk"}
def ipa(phrase):
    key = phrase.lower()
    if key in IPA_FIX:
        return IPA_FIX[key]
    parts = []
    for w in re.split(r"[ ]+", key):
        w2 = w.strip(".,!?")
        p = IPA_FIX.get(w2) or IPA_UK.get(w2) or IPA_US.get(w2)
        if not p and "-" in w2:
            sub = [IPA_UK.get(x) or IPA_US.get(x) for x in w2.split("-")]
            p = " ".join(sub) if all(sub) else None
        if not p:
            return ""
        parts.append(p)
    return " ".join(parts)

# ---------- темы ----------
TOPICS = {
 "animals": ("Животные", "🐾", "#FF9F43"), "food": ("Еда и напитки", "🍎", "#FF6B6B"),
 "family": ("Семья и люди", "👨‍👩‍👧", "#F368E0"), "body": ("Тело", "🖐️", "#FECA57"),
 "clothes": ("Одежда", "👕", "#54A0FF"), "home": ("Дом", "🏠", "#1DD1A1"),
 "school": ("Школа", "🎒", "#5F27CD"), "toys": ("Игрушки и игры", "🧸", "#FF9FF3"),
 "nature": ("Природа", "🌳", "#10AC84"), "weather": ("Погода и времена года", "☀️", "#48DBFB"),
 "transport": ("Транспорт", "🚗", "#EE5253"), "city": ("Город", "🏙️", "#576574"),
 "jobs": ("Профессии", "👩‍⚕️", "#0ABDE3"), "sport": ("Спорт", "⚽", "#FF9F1A"),
 "hobbies": ("Хобби и музыка", "🎸", "#C44569"), "colours": ("Цвета", "🎨", "#F8B500"),
 "numbers": ("Числа", "🔢", "#3867D6"), "time": ("Время и календарь", "📅", "#8854D0"),
 "feelings": ("Чувства", "😊", "#FD9644"), "actions": ("Действия", "🏃", "#20BF6B"),
 "describing": ("Какой? Описания", "✨", "#A55EEA"), "health": ("Здоровье", "💊", "#EB3B5A"),
 "travel": ("Путешествия", "✈️", "#2D98DA"), "shopping": ("Покупки и деньги", "🛍️", "#FA8231"),
 "technology": ("Техника и интернет", "💻", "#4B7BEC"), "people": ("Характер и внешность", "🙂", "#E15F41"),
 "space": ("Космос и наука", "🚀", "#3C40C6"), "fairy": ("Сказки и волшебство", "🧚", "#BE2EDD"),
 "phrases": ("Вежливые фразы", "💬", "#26DE81"), "little-words": ("Маленькие важные слова", "🔤", "#778CA3"),
 "general": ("Словарь школьника", "📚", "#4B6584"),
}

def load_words():
    entries, order = {}, []
    for path in sorted(glob.glob(os.path.join(HERE, "words", "*.txt"))):
        topic = None
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                topic = line[1:]
                continue
            en, ru = [x.strip() for x in line.split("|", 1)]
            key = en.lower()
            if key not in entries:
                entries[key] = {"en": en, "ru": ru, "topics": [], "ru_by_topic": {}}
                order.append(key)
            e = entries[key]
            if topic not in e["topics"]:
                e["topics"].append(topic)
            e["ru_by_topic"].setdefault(topic, ru)
            # разные значения в разных темах: orange — апельсин / оранжевый
            parts = [p.strip() for p in e["ru"].split(";")]
            for p in ru.split(";"):
                if p.strip() not in parts and len(parts) < 3:
                    parts.append(p.strip())
            e["ru"] = "; ".join(parts)
    return entries, order

def level_of(en):
    lv = LEVEL.get(en.lower())
    if not lv and " " in en:
        lvs = [LEVEL.get(w) for w in en.lower().split()]
        lv = max(lvs) if all(lvs) else None
    return (lv or "A1").lower()

VERSION = "2026-11-05.1"
KIDS_ORDER = """hello goodbye cat dog fish bird duck cow pig horse sheep rabbit mouse frog lion tiger
elephant monkey giraffe zebra bear panda red blue yellow green orange pink purple brown black white
one two three four five six seven eight nine ten apple banana orange pear grape cake ice_cream milk
juice water bread cheese egg pizza chocolate mum dad brother sister baby grandma grandpa boy girl
head eye ear nose mouth hand leg foot hair tooth ball doll teddy_bear robot kite balloon car bus train
plane boat bike house door window table chair bed book pen pencil bag teacher school sun moon star
tree flower rain snow cloud hat cap shoe sock t-shirt dress jacket happy sad big small hot cold
yes no please thank_you""".split()
KIDS_FIRST = ["animals", "food", "colours", "numbers", "family", "body", "toys", "clothes", "phrases"]
PART = 40


def _load_examples():
    # предложения-примеры (по методике Cambridge YLE слово вводится в контексте, а не парой «слово — перевод»)
    ex = {}
    for line in open(os.path.join(HERE, "words", "sentences.txt"), encoding="utf-8"):
        if "|" in line:
            w, s = line.rstrip("\n").split("|", 1)
            ex.setdefault(w.strip(), s.strip())
    return ex


EXAMPLES = None


def _w(e, topic=None):
    global EXAMPLES
    if EXAMPLES is None:
        EXAMPLES = _load_examples()
    ru = e["ru_by_topic"].get(topic, e["ru"]) if topic else e["ru"]
    img = e.get("img_by_topic", {}).get(topic, e["img"]) if topic else e["img"]
    return {"en": e["en"], "ru": ru, "ipa": e["ipa"], "img": img, "level": e["level"], "ex": EXAMPLES.get(e["en"], "")}


def build_sets(words):
    """Наборы: по темам (части по 40 слов) и по уровням."""
    sets, pos = [], 100
    by_topic = {}
    for e in words:
        for t in e["topics"]:
            by_topic.setdefault(t, []).append(e)
    for t, (title, icon, color) in TOPICS.items():
        items = by_topic.get(t, [])
        if not items:
            continue
        # сначала слова с картинкой и уровня A1 — так легче начать
        items = sorted(items, key=lambda e: (e["level"] != "a1", not e["img"]))
        n_parts = -(-len(items) // PART)
        size = -(-len(items) // n_parts)
        parts = [items[i:i + size] for i in range(0, len(items), size)]
        for n, chunk in enumerate(parts, 1):
            pos += 1
            sets.append({"code": f"topic:{t}:{n}", "title": title + (f" · {n}" if len(parts) > 1 else ""),
                         "kind": "topic", "topic": t, "icon": icon, "color": color, "cefr": "",
                         "position": pos, "words": [_w(e, t) for e in chunk]})
    # «Первые слова» — ручной порядок для 4–7 лет (как в Cambridge Starters):
    # сначала то, что ребёнок видит и трогает каждый день.
    by_en = {e["en"].lower(): e for e in words}
    kids = []
    for w in KIDS_ORDER:
        e = by_en.get(w.replace("_", " "))
        if e and e not in kids:  # без фото — цвет/цифра/плитка в ЛК
            kids.append(e)
    levels = [("level:pre-a1", "Первые слова · Starters", "pre-a1", "sprout", "#FF9F43", kids[:160]),
              ("level:a1", "Уровень A1 · Movers", "a1", "graduation-cap", "#20BF6B", [e for e in words if e["level"] == "a1"]),
              ("level:a2", "Уровень A2 · Flyers", "a2", "graduation-cap", "#3867D6", [e for e in words if e["level"] == "a2"])]
    for i, (code, title, cefr, icon, color, items) in enumerate(levels):
        sets.append({"code": code, "title": title, "kind": "level", "topic": "", "icon": icon, "color": color,
                     "cefr": cefr, "position": 10 * (i + 1), "words": [_w(e) for e in items]})
    return sets


if __name__ == "__main__":
    entries, order = load_words()
    from emoji_map import pick_emoji, MANUAL  # noqa
    MANUAL_TOPIC = {k for k in MANUAL if "@" in k}
    out = []
    no_ipa, no_img = [], []
    for k in order:
        e = entries[k]
        e["ipa"] = ipa(e["en"])
        e["level"] = level_of(e["en"])
        e["emoji"] = pick_emoji(e["en"], e["topics"])
        if not e["ipa"]:
            no_ipa.append(e["en"])
        if not e["emoji"]:
            no_img.append(e["en"])
        out.append(e)
    slug = lambda em: ("/wimg/" + re.sub(r"[^a-z0-9]+", "-", em["asset"].lower()).strip("-") + ".webp") if em else ""
    PUB = os.path.join(HERE, "..", "..", "..", "..", "lk", "public", "w")
    def photo(en):
        f = "m-" + re.sub(r"[^a-z0-9]+", "-", en.lower()).strip("-") + ".webp"
        return "/w/" + f if os.path.exists(os.path.join(PUB, f)) else ""
    for e in out:
        e.pop("emoji")
        # картинки — только реалистичные (Meshy, проверенные вручную); эмодзи больше не используем
        e["img"] = photo(e["en"])
        e["img_by_topic"] = {}
        # в «Цветах» и «Числах» картинка рисуется в ЛК (цветной образец / цифра),
        # чтобы orange-цвет не показывался апельсином, а light — лампой
        for t in e["topics"]:
            if t in ("colours", "numbers"):
                e["img_by_topic"][t] = ""
    no_img[:] = [e["en"] for e in out if not e["img"]]
    sets = build_sets(out)
    json.dump({"version": VERSION, "topics": TOPICS, "sets": sets},
              open(os.path.join(HERE, "words.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print("наборов:", len(sets))
    print("слов:", len(out), "| без IPA:", len(no_ipa), "| без картинки:", len(no_img))
    print("NO IPA:", ", ".join(no_ipa))
    print("NO IMG:", ", ".join(no_img))
