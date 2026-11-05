#!/usr/bin/env python3
"""Рисует Фокси в разных позах и одежде (Meshy, листы 3×3) и режет на прозрачные картинки.

Вход: world-backend/app/lk/content/meshy_foxi.json — [{"id", "poses": [9 имён], "prompt"}].
Выход: world/public/content/foxi/<поза>.webp и lk/public/foxi/<поза>.webp (фон убран).
Ключ Meshy — из secrets/meshy.env (как у остальных картинок). Повторный запуск берёт кэш.
"""
import json
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "prototype"))
from meshy_client import MeshyClient  # noqa: E402

JOBS = ROOT / "world-backend/app/lk/content/meshy_foxi.json"
OUTS = [ROOT / "world/public/content/foxi", ROOT / "lk/public/foxi"]


def cut_white(tile):
    """Убирает белый фон заливкой от краёв (белое внутри фигуры — грудка, зубы — не трогаем)."""
    im = tile.convert("RGBA")
    w, h = im.size
    px = im.load()
    seen = bytearray(w * h)
    q = deque()
    for x in range(w):
        q.extend(((x, 0), (x, h - 1)))
    for y in range(h):
        q.extend(((0, y), (w - 1, y)))
    while q:
        x, y = q.popleft()
        if not (0 <= x < w and 0 <= y < h) or seen[y * w + x]:
            continue
        seen[y * w + x] = 1
        r, g, b, _ = px[x, y]
        if min(r, g, b) < 228 or max(r, g, b) - min(r, g, b) > 22:
            continue
        px[x, y] = (255, 255, 255, 0)
        q.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    box = im.getbbox()
    return im.crop(box) if box else im


def slice_sheet(png: Path, poses: list[str]) -> int:
    from PIL import Image
    im = Image.open(png).convert("RGB")
    W, H = im.size
    cw, ch = W / 3, H / 3
    n = 0
    for i, pose in enumerate(poses[:9]):
        c, r = i % 3, i // 3
        g = 0.02
        tile = im.crop((int(c * cw + cw * g), int(r * ch + ch * g), int((c + 1) * cw - cw * g), int((r + 1) * ch - ch * g)))
        fox = cut_white(tile)
        fox.thumbnail((560, 560), Image.LANCZOS)
        canvas = Image.new("RGBA", (600, 600), (0, 0, 0, 0))
        canvas.paste(fox, ((600 - fox.width) // 2, 600 - fox.height - 10), fox)
        for out in OUTS:
            out.mkdir(parents=True, exist_ok=True)
            canvas.save(out / f"{pose}.webp", "WEBP", quality=88)
        n += 1
    return n


def main():
    jobs = json.loads(JOBS.read_text(encoding="utf-8"))
    c = MeshyClient(max_wait=420)
    print("Meshy:", "включён" if c.enabled else "ВЫКЛЮЧЕН/нет ключа", "| баланс:", c.balance())
    if not c.enabled:
        return 1
    total = 0
    for job in jobs:
        p = c.text_to_image(job["prompt"], out=f"../world-backend/app/lk/content/meshy_sheets/{job['id']}.png", aspect_ratio="1:1")
        if not p:
            print(f"✗ {job['id']}: не получилось")
            continue
        try:
            k = slice_sheet(Path(p), job["poses"])
        except ImportError:
            k = 0
            print("  нет Pillow — нарежет Claude")
        print(f"✓ {job['id']}: {k} Фокси")
        total += k
    print("Готово Фокси:", total, "| баланс после:", c.balance())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
