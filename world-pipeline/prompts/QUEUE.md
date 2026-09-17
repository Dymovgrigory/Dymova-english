# Очередь генерации Meshy (продолжить с новым ключом)

Ключ кладётся в `secrets/meshy.env` (`MESHY_API_KEY=...`). Модель и промпты не менять (STYLE_LOCK).
Каждая картинка — 9 кредитов. После генерации — визуальная проверка сеткой (не должно быть «домиков»
вместо предметов) и коммит.

## 1. Spotlight 1 — переделать «домики» (18 шт., ~162 кр.)

```bash
python3 world-pipeline/diorama_art.py words:sp1.m2,sp1.m3,sp1.m4,sp1.m5 --force --only \
  word-pencil-case word-toy word-car word-plane word-ball word-tree word-run word-jump word-climb \
  word-biscuit word-egg word-bread word-chocolate word-play word-seaside
```

Слова new, under, big: сначала вернуть пути картинок в `content/spotlight/sp1/m2.json` / `m3.json`
(`"image": "words/new.webp"` и т.д.), затем
`python3 world-pipeline/diorama_art.py words:sp1.m2,sp1.m3 --force --only word-new word-under word-big`.

## 2. Spotlight 2–4 — все слова в стиле «живой миниатюры» (~430 шт., ~3900 кр.)

```bash
python3 -c "import sys; sys.path.insert(0,'world-pipeline'); import diorama_art as d, json; \
ids=[json.loads(p.read_text())['id'] for p in sorted(d.CONTENT.glob('sp[234]/*.json'))]; print(d.assign_missing_images(ids))"
python3 world-pipeline/diorama_art.py words:sp2.m0,sp2.m1,sp2.m2,sp2.m3,sp2.m4,sp2.m5,sp2.m6
python3 world-pipeline/diorama_art.py words:sp3.m0,sp3.m1,sp3.m2,sp3.m3,sp3.m4,sp3.m5,sp3.m6,sp3.m7,sp3.m8
python3 world-pipeline/diorama_art.py words:sp4.m0,sp4.m1,sp4.m2,sp4.m3,sp4.m4,sp4.m5,sp4.m6,sp4.m7,sp4.m8
```

## 3. Замок — башни классов как здания (4 шт. без фона, ~36 кр.)

Башни `world/public/content/towers/sp{1..4}.webp` (темы — `TOWER_THEMES` в `diorama_art.py`) —
макеты зданий Замка. Для карты Замка нужны варианты без фона (`remove_background`).
