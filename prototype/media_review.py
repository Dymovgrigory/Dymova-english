#!/usr/bin/env python3
"""Генератор контакт-листа медиа-архива для подписи событий владельцем.

Сканирует «фото и видео/», группирует файлы в серии по EXIF-дате и камере,
создаёт превью (webp 480px) в _media_review/ и один HTML-файл media-review.html,
который владелец открывает в браузере и подписывает события.

Запуск: python3 prototype/media_review.py
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "фото и видео"
OUT = ROOT / "_media_review"
HTML = ROOT / "media-review.html"

PHOTO_EXT = {".jpg", ".jpeg", ".png", ".heic"}
SKIP_EXT = {".cr3", ".xlsx", ".csv", ".ds_store"}
VIDEO_EXT = {".mp4", ".mov"}
THUMB_W = 480
MAX_THUMBS_PER_SERIES = 8  # превью на серию, равномерно по съёмке


def exif_date(path: Path) -> str | None:
    """Дата съёмки. Фото — EXIF DateTimeOriginal (Pillow), видео — mdls. YYYY-MM-DD."""
    if path.suffix.lower() in PHOTO_EXT:
        try:
            from PIL import Image

            with Image.open(path) as im:
                ex = im.getexif()
                ifd = ex.get_ifd(0x8769) if ex else {}
                raw = ifd.get(36867) or ex.get(306)
                if raw:
                    return datetime.strptime(raw[:10], "%Y:%m:%d").strftime("%Y-%m-%d")
        except Exception:
            pass
    # fallback: mdls (видео и фото без EXIF)
    try:
        out = subprocess.run(
            ["mdls", "-raw", "-name", "kMDItemContentCreationDate", str(path)],
            capture_output=True, text=True, timeout=20,
        ).stdout.strip()
        if out and out != "(null)":
            d = out[:10]
            # 2026-08-22 — дата массового копирования архива, не дата съёмки
            if d != "2026-08-22":
                return d
    except Exception:
        pass
    # canon без EXIF: номер кадра 3447–4564 — портретная серия июнь 2026
    m = re.match(r"9G6A(\d{4})", path.name)
    if m and 3447 <= int(m.group(1)) <= 4564:
        return "2026-06-??"
    return None


def camera_kind(name: str) -> str:
    if name.startswith("9G6A"):
        return "canon"
    if name.startswith("DSC_"):
        return "nikon"
    if name.startswith("IMG_"):
        return "iphone"
    return "other"


def make_thumb(src: Path, dst: Path) -> bool:
    """Превью через sips (ресайз) + Pillow (webp). Для видео — qlmanage."""
    try:
        if src.suffix.lower() in VIDEO_EXT:
            # qlmanage пишет <name>.mp4.png рядом с dst.parent? Нет: в указанный каталог
            tmp = dst.parent / (dst.stem + ".tmp")
            tmp.mkdir(exist_ok=True)
            subprocess.run(
                ["qlmanage", "-t", "-s", str(THUMB_W), "-o", str(tmp), str(src)],
                capture_output=True, timeout=60,
            )
            pngs = list(tmp.glob("*.png"))
            if not pngs:
                return False
            _png_to_webp(pngs[0], dst)
            for p in tmp.iterdir():
                p.unlink()
            tmp.rmdir()
            return dst.exists()
        # фото: Pillow с учётом EXIF-ориентации; HEIC — через sips
        if src.suffix.lower() in {".jpg", ".jpeg", ".png"}:
            from PIL import Image, ImageOps

            with Image.open(src) as im:
                im = ImageOps.exif_transpose(im).convert("RGB")
                im.thumbnail((THUMB_W, THUMB_W * 2))
                im.save(dst, "WEBP", quality=72, method=4)
            return dst.exists()
        tmp_png = dst.with_suffix(".tmp.png")
        subprocess.run(
            ["sips", "-Z", str(THUMB_W), "-s", "format", "png", str(src), "--out", str(tmp_png)],
            capture_output=True, timeout=60,
        )
        if not tmp_png.exists():
            return False
        _png_to_webp(tmp_png, dst)
        tmp_png.unlink()
        return dst.exists()
    except Exception as e:
        print(f"  ! thumb failed {src.name}: {e}", file=sys.stderr)
        return False


def _png_to_webp(png: Path, dst: Path) -> None:
    from PIL import Image

    with Image.open(png) as im:
        im.convert("RGB").save(dst, "WEBP", quality=72, method=4)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    files = sorted(
        p for p in SRC.iterdir()
        if p.is_file() and p.suffix.lower() not in SKIP_EXT
    )
    print(f"Файлов: {len(files)}")

    series: dict[str, list[dict]] = defaultdict(list)
    for f in files:
        d = exif_date(f) or "без даты"
        kind = camera_kind(f.name)
        key = f"{d} · {kind}"
        series[key].append({
            "name": f.name,
            "path": f,
            "type": "video" if f.suffix.lower() in VIDEO_EXT else "image",
            "date": d,
        })

    # сортировка серий по дате
    ordered = sorted(series.items(), key=lambda kv: kv[0])
    data = []
    for key, items in ordered:
        items.sort(key=lambda x: x["name"])
        # равномерная выборка превью
        if len(items) > MAX_THUMBS_PER_SERIES:
            step = len(items) / MAX_THUMBS_PER_SERIES
            pick = [items[int(i * step)] for i in range(MAX_THUMBS_PER_SERIES)]
        else:
            pick = items
        thumbs = []
        for it in pick:
            dst = OUT / (it["path"].stem + ".webp")
            if not dst.exists():
                if not make_thumb(it["path"], dst):
                    continue
            thumbs.append({"src": f"_media_review/{dst.name}", "name": it["name"], "type": it["type"]})
        data.append({"series": key, "count": len(items), "thumbs": thumbs})
        print(f"{key}: {len(items)} файлов, превью {len(thumbs)}")

    (OUT / "series.json").write_text(json.dumps(data, ensure_ascii=False, indent=1))

    sections = []
    for i, s in enumerate(data, 1):
        imgs = "\n".join(
            f'<figure><img loading="lazy" src="{t["src"]}" alt=""><figcaption>{t["name"]}{" · видео" if t["type"]=="video" else ""}</figcaption></figure>'
            for t in s["thumbs"]
        )
        sections.append(f"""
<section>
  <h2>Серия {i}: {s['series']} <span class="n">({s['count']} файлов)</span></h2>
  <p class="q">Что это за событие? (выпускной / летняя академия / занятия / праздник…) — <b>напишите ответ под этой серией</b>:</p>
  <textarea rows="2" placeholder="Подпись события, например: «Выпускной 2026, филиал Лихачёвский»"></textarea>
  <div class="grid">{imgs}</div>
</section>""")

    HTML.write_text(f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><title>Подпись событий — медиа-архив</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{{font-family:-apple-system,Montserrat,Arial,sans-serif;background:#f4f1fa;color:#241a36;margin:0;padding:24px;max-width:1100px;margin-inline:auto}}
h1{{color:#392852}} h2{{color:#392852;border-top:2px solid #662d92;padding-top:16px;margin-top:40px}}
.n{{color:#6f6883;font-weight:400;font-size:.7em}}
.q{{margin:8px 0 4px}} textarea{{width:100%;font-size:15px;padding:8px;border:2px solid #662d92;border-radius:10px;background:#fff}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;margin-top:12px}}
figure{{margin:0;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px #39285222}}
img{{width:100%;height:180px;object-fit:cover;display:block}}
figcaption{{font-size:11px;padding:6px 8px;color:#6f6883;word-break:break-all}}
</style></head><body>
<h1>Медиа-архив: {sum(s["count"] for s in data)} файлов, {len(data)} серий</h1>
<p>Откройте файл, посмотрите серии и <b>напишите под каждой, что это за событие</b> (можно прямо в мессенджер мне: «Серия 2 — выпускной 2026»). Даты — реальные даты съёмки из камеры.</p>
{''.join(sections)}
</body></html>""", encoding="utf-8")
    print(f"\nГотово: {HTML}")


if __name__ == "__main__":
    main()
