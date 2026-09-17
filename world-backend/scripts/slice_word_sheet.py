#!/usr/bin/env python3
"""Нарезает лист 3×3 на квадратные jpg карточек слов.

Пример:
  python scripts/slice_word_sheet.py generated/sheet.png bag bed bus cat dog mug pen sock jug
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "world" / "public" / "learn" / "words"
GUTTER = 0.04  # доля поля внутри каждой ячейки, чтобы отрезать белую рамку


def _open(path: Path):
    try:
        from PIL import Image
    except ImportError as exc:
        raise SystemExit("Нужен Pillow: pip install Pillow") from exc
    return Image.open(path).convert("RGB")


def slice_sheet(src: Path, words: list[str], dest: Path = DEST, gutter: float = GUTTER) -> list[Path]:
    if len(words) != 9:
        raise SystemExit(f"нужно ровно 9 слов, пришло {len(words)}")
    image = _open(src)
    w, h = image.size
    cell_w, cell_h = w / 3, h / 3
    dest.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for i, word in enumerate(words):
        col, row = i % 3, i // 3
        x0 = col * cell_w + cell_w * gutter
        y0 = row * cell_h + cell_h * gutter
        x1 = (col + 1) * cell_w - cell_w * gutter
        y1 = (row + 1) * cell_h - cell_h * gutter
        tile = image.crop((int(x0), int(y0), int(x1), int(y1)))
        side = min(tile.size)
        left = (tile.width - side) // 2
        top = (tile.height - side) // 2
        tile = tile.crop((left, top, left + side, top + side)).resize((768, 768))
        out = dest / f"{word}.jpg"
        tile.save(out, "JPEG", quality=88, optimize=True)
        written.append(out)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Нарезать лист 3×3 на карточки слов")
    parser.add_argument("image", type=Path)
    parser.add_argument("words", nargs=9)
    parser.add_argument("--dest", type=Path, default=DEST)
    args = parser.parse_args()
    if not args.image.exists():
        raise SystemExit(f"нет файла {args.image}")
    paths = slice_sheet(args.image, args.words, dest=args.dest)
    for path in paths:
        print(path, path.stat().st_size)


if __name__ == "__main__":
    main()
