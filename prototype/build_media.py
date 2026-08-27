#!/usr/bin/env python3
"""Медиа-конвейер «Жизнь школы» (фаза 1 media-first трансформации).

Сырьё: `фото и видео/` (реальные съёмки школы, ~2,4 ГБ).
Выход: `prototype/media/life/<серия>/` — веб-ассеты:
  - фото: `-1600.webp` (hero, q75) и `-900.webp` (card, q75), EXIF-ориентация применена;
  - видео: `.mp4` (H.264 ≤1280px через avconvert) + постер `-poster.webp` (qlmanage);
и манифест `prototype/media/manifest.json` (см. media_library.py).

Правила:
  - CR3/HEIC/XLSX/CSV пропускаем (CR3 — RAW-дубли, JPG-пары уже в архиве).
  - Только подтверждённые метаданные: серия = EXIF-дата + камера, без выдуманных событий.
  - Подписи событий владельца подключаются через MEDIA_EVENTS в media_events.py.

Запуск: make media  (или python3 prototype/build_media.py)
Идемпотентно: уже обработанные файлы пропускаются.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from media_review import PHOTO_EXT, VIDEO_EXT, SKIP_EXT, camera_kind, exif_date  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "фото и видео"
OUT = ROOT / "prototype" / "media" / "life"
MANIFEST = ROOT / "prototype" / "media" / "manifest.json"

HERO_W, CARD_W = 1600, 900
VIDEO_PRESET = "Preset1280x720"
VIDEO_PRESET_SMALL = "Preset640x480"
VIDEO_MAX_BYTES = 8 * 1024 * 1024  # бюджет: видео на сайте ≤ 8 МБ
MIN_PHOTO_W = 1200  # iPhone-мелочь — только card-размер


def series_slug(key: str) -> str:
    """'2026-05-16 · nikon' → '2026-05-16-nikon'; 'без даты · iphone' → 'no-date-iphone'."""
    date, _, kind = key.partition(" · ")
    date = "no-date" if date.startswith("без") else date.replace("?", "")
    return f"{date}-{kind}".strip("-")


def process_photo(src: Path, dst_dir: Path) -> dict | None:
    from PIL import Image, ImageOps

    actual = src
    if src.suffix.lower() == ".heic" and shutil.which("sips"):
        # Pillow не читает HEIC — конвертируем через sips во временный JPEG
        tmp_jpg = dst_dir / (src.stem + ".heic-tmp.jpg")
        r = subprocess.run(
            ["sips", "-s", "format", "jpeg", str(src), "--out", str(tmp_jpg)],
            capture_output=True, timeout=120,
        )
        if r.returncode == 0 and tmp_jpg.exists():
            actual = tmp_jpg
    try:
        with Image.open(actual) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            w, h = im.size
            base = dst_dir / src.stem
            out_big = base.with_suffix(".1600.webp")
            out_small = base.with_suffix(".900.webp")
            if not out_small.exists():
                small = im.copy()
                small.thumbnail((CARD_W, CARD_W * 2))
                small.save(out_small, "WEBP", quality=75, method=4)
            if w >= MIN_PHOTO_W and not out_big.exists():
                big = im.copy()
                big.thumbnail((HERO_W, HERO_W * 2))
                big.save(out_big, "WEBP", quality=75, method=4)
            return {
                "w": w, "h": h,
                "orientation": "landscape" if w >= h else "portrait",
                "src": f"life/{dst_dir.name}/{out_big.name}" if out_big.exists() else f"life/{dst_dir.name}/{out_small.name}",
                "srcset": {
                    "900": f"life/{dst_dir.name}/{out_small.name}",
                    **({"1600": f"life/{dst_dir.name}/{out_big.name}"} if out_big.exists() else {}),
                },
            }
    except Exception as e:
        print(f"  ! фото пропущено {src.name}: {e}", file=sys.stderr)
        return None
    finally:
        if actual is not src:
            actual.unlink(missing_ok=True)


def _ffmpeg_convert(src: Path, out_mp4: Path) -> bool:
    """ffmpeg (предпочтительно): H.264 CRF 28, ≤1280px, faststart; при переборе — 640px CRF 32."""
    attempts = [
        ["-vf", "scale='min(1280,iw)':-2", "-crf", "28"],
        ["-vf", "scale=640:-2", "-crf", "32"],
        ["-vf", "scale=480:-2", "-crf", "35"],
    ]
    for i, vf in enumerate(attempts):
        tmp = out_mp4.with_suffix(f".ff{i}.mp4")
        tmp.unlink(missing_ok=True)
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", str(src), *vf,
             "-c:v", "libx264", "-preset", "medium", "-pix_fmt", "yuv420p",
             "-movflags", "+faststart", "-c:a", "aac", "-b:a", "96k", str(tmp)],
            capture_output=True, text=True, timeout=1800,
        )
        if r.returncode != 0 or not tmp.exists():
            tmp.unlink(missing_ok=True)
            continue
        if tmp.stat().st_size <= VIDEO_MAX_BYTES:
            tmp.rename(out_mp4)
            return True
        tmp.unlink(missing_ok=True)
    return False


def process_video(src: Path, dst_dir: Path) -> dict | None:
    base = dst_dir / src.stem
    out_mp4 = base.with_suffix(".mp4")
    out_poster = base.with_suffix(".poster.webp")
    try:
        if not out_mp4.exists():
            ok = False
            if shutil.which("ffmpeg"):
                ok = _ffmpeg_convert(src, out_mp4)
            else:
                for preset in (VIDEO_PRESET, VIDEO_PRESET_SMALL):
                    tmp = out_mp4.with_suffix(".m4v")
                    tmp.unlink(missing_ok=True)
                    r = subprocess.run(
                        ["avconvert", "--source", str(src), "-o", str(tmp), "-p", preset],
                        capture_output=True, text=True, timeout=600,
                    )
                    if r.returncode != 0 or not tmp.exists():
                        continue
                    if tmp.stat().st_size <= VIDEO_MAX_BYTES or preset == VIDEO_PRESET_SMALL:
                        if tmp.stat().st_size <= VIDEO_MAX_BYTES:
                            tmp.rename(out_mp4)
                            ok = True
                        break
            if not ok:
                print(f"  ! видео пропущено (>{VIDEO_MAX_BYTES // 1024 // 1024} МБ даже после сжатия): {src.name}",
                      file=sys.stderr)
                return None
        if not out_poster.exists():
            if shutil.which("ffmpeg"):
                tmp_png = base.with_suffix(".poster-tmp.png")
                subprocess.run(
                    ["ffmpeg", "-y", "-ss", "1", "-i", str(src),
                     "-frames:v", "1", "-vf", "scale=900:-2", str(tmp_png)],
                    capture_output=True, timeout=300,
                )
                if tmp_png.exists():
                    from PIL import Image

                    with Image.open(tmp_png) as im:
                        im.convert("RGB").save(out_poster, "WEBP", quality=75, method=4)
                    tmp_png.unlink(missing_ok=True)
            else:
                tmpdir = dst_dir / (src.stem + ".tmpth")
                tmpdir.mkdir(exist_ok=True)
                subprocess.run(
                    ["qlmanage", "-t", "-s", str(CARD_W), "-o", str(tmpdir), str(src)],
                    capture_output=True, timeout=120,
                )
                pngs = list(tmpdir.glob("*.png"))
                if pngs:
                    from PIL import Image

                    with Image.open(pngs[0]) as im:
                        im.convert("RGB").save(out_poster, "WEBP", quality=75, method=4)
                shutil.rmtree(tmpdir, ignore_errors=True)
        # размеры из afinfo не берём — они ненадёжны; постер даёт геометрию
        w = h = None
        if out_poster.exists():
            from PIL import Image

            with Image.open(out_poster) as im:
                w, h = im.size
        return {
            "w": w, "h": h,
            "orientation": ("landscape" if (w or 0) >= (h or 0) else "portrait"),
            "src": f"life/{dst_dir.name}/{out_mp4.name}",
            "poster": f"life/{dst_dir.name}/{out_poster.name}" if out_poster.exists() else None,
        }
    except Exception as e:
        print(f"  ! видео пропущено {src.name}: {e}", file=sys.stderr)
        return None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    files = sorted(
        p for p in SRC.iterdir()
        if p.is_file() and p.suffix.lower() not in SKIP_EXT
    )

    series: dict[str, list[Path]] = defaultdict(list)
    dates: dict[str, str] = {}
    for f in files:
        d = exif_date(f) or "без даты"
        key = f"{d} · {camera_kind(f.name)}"
        series[key].append(f)
        dates[key] = d

    # подписи событий владельца (заполняются после фазы 0)
    try:
        from media_events import MEDIA_EVENTS  # type: ignore
    except ImportError:
        MEDIA_EVENTS = {}

    items = []
    for key in sorted(series):
        slug = series_slug(key)
        dst_dir = OUT / slug
        dst_dir.mkdir(exist_ok=True)
        ev = MEDIA_EVENTS.get(key, {})
        n = 0
        for f in series[key]:
            is_video = f.suffix.lower() in VIDEO_EXT
            meta = process_video(f, dst_dir) if is_video else process_photo(f, dst_dir)
            if not meta:
                continue
            n += 1
            items.append({
                "id": f"{slug}/{f.stem}",
                "type": "video" if is_video else "image",
                "series": slug,
                "date": None if dates[key].startswith(("без",)) or "?" in dates[key] else dates[key],
                "event": ev.get("event"),
                "alt": ev.get("alt", "Занятия и события языковой школы Фоксинбург в Долгопрудном"),
                "tags": ev.get("tags", []),
                "featured": False,
                "hero": False,
                **meta,
            })
        print(f"{key} → {slug}: {n}/{len(series[key])}")

    MANIFEST.write_text(json.dumps({
        "series": {series_slug(k): {"key": k, "date": dates[k], "count": len(v),
                                    **MEDIA_EVENTS.get(k, {})}
                   for k, v in sorted(series.items())},
        "items": items,
    }, ensure_ascii=False, indent=1))
    total = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    print(f"\nИтого: {len(items)} элементов, {total / 1024 / 1024:.1f} МБ → {OUT}")
    print(f"Манифест: {MANIFEST}")


if __name__ == "__main__":
    main()
