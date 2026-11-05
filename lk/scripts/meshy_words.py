#!/usr/bin/env python3
"""Рисует картинки к словам в Meshy листами 3×3 и режет их на карточки.

Вход: world-backend/app/lk/content/meshy_jobs.json — [{"id": "...", "words": [9 слов],
"prompt": "..."}]. Ключ Meshy берётся из secrets/meshy.env (как у сайта).
Выход: content/meshy_sheets/<id>.png и lk/public/w/m-<слово>.webp.
Повторный запуск не тратит кредиты на уже готовые листы (кэш meshy_client).
"""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "prototype"))
from meshy_client import MeshyClient  # noqa: E402

JOBS = ROOT / "world-backend/app/lk/content/meshy_jobs.json"
SHEETS = ROOT / "world-backend/app/lk/content/meshy_sheets"
OUT = ROOT / "lk/public/w"
WORLD_OUT = ROOT / "world/public/content/words"


def slug(w):
    return re.sub(r"[^a-z0-9]+", "-", w.lower()).strip("-")


def slice_sheet(png: Path, words: list[str], target: str = "lk") -> int:
    from PIL import Image
    im = Image.open(png).convert("RGB")
    W, H = im.size
    cw, ch = W / 3, H / 3
    n = 0
    for i, w in enumerate(words[:9]):
        if not w:
            continue
        c, r = i % 3, i // 3
        g = 0.035
        tile = im.crop((int(c * cw + cw * g), int(r * ch + ch * g), int((c + 1) * cw - cw * g), int((r + 1) * ch - ch * g)))
        if target == "world":  # картинки Мира: world/public/content/words/<слово>.webp
            tile.resize((640, 640), Image.LANCZOS).save(WORLD_OUT / f"{w}.webp", "WEBP", quality=86)
        else:
            tile.resize((480, 480)).save(OUT / f"m-{slug(w)}.webp", "WEBP", quality=84)
        n += 1
    return n


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    SHEETS.mkdir(parents=True, exist_ok=True)
    jobs_file = JOBS
    if len(sys.argv) > 1 and sys.argv[1].endswith(".json"):
        jobs_file = JOBS.parent / sys.argv.pop(1)  # например meshy_redo.json — переделки
    jobs = json.loads(jobs_file.read_text(encoding="utf-8"))
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        jobs = jobs[: int(sys.argv[1])]
    print("листов в работе:", len(jobs))
    c = MeshyClient(max_wait=420)
    print("Meshy:", "включён" if c.enabled else "ВЫКЛЮЧЕН/нет ключа", "| модель:", c.model, "| баланс:", c.balance())
    if not c.enabled:
        return 1

    def run(job):
        out = f"../world-backend/app/lk/content/meshy_sheets/{job['id']}.png"
        p = c.text_to_image(job["prompt"], out=out, aspect_ratio="1:1")
        if p:
            try:
                k = slice_sheet(Path(p), job["words"], job.get("out", "lk"))
            except ImportError:
                k = 9  # нарежет Claude: на этом Python нет Pillow
            print(f"✓ {job['id']}: {k} картинок")
            return k
        print(f"✗ {job['id']}: не получилось")
        return 0

    with ThreadPoolExecutor(max_workers=4) as ex:
        total = sum(ex.map(run, jobs))
    print("Готово картинок:", total, "| баланс после:", c.balance())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
