#!/usr/bin/env python3
"""Позы Foxy для тренажёра: Meshy image-to-image по маскоту из брендбука → прозрачный WebP.

Usage:
  python3 world-pipeline/foxy_poses.py [pose ...]     # по умолчанию все позы
"""
from __future__ import annotations

import base64
import io
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from word_art import api, load_key  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "Маскот Фоксинбург.PNG"
OUT = ROOT / "world" / "public" / "content" / "foxy"
WORK = ROOT / "world-pipeline" / "word-art" / "foxy"
API = "https://api.meshy.ai/openapi/v1/image-to-image"
MODEL = "nano-banana-pro"
SIZE = 640

CHARACTER = (
    "Keep exactly the same character from the reference: the orange fox mascot with big blue eyes, yellow T-shirt "
    "with the purple castle logo and the word Фоксинбург, purple shorts, purple backpack, white-purple sneakers. "
    "Same premium soft 3D cartoon style, full body, centered, plain background. "
)
POSES = {
    "cheer": "Pose: jumping for joy with both arms raised high, huge happy smile, celebrating a victory.",
    "wave": "Pose: standing and waving hello with one paw, friendly welcoming smile.",
    "think": "Pose: thinking, one paw on the chin, looking up curiously with a small smile.",
    "oops": "Pose: kind encouraging expression, slight shrug with open paws, as if saying 'no problem, try again'.",
}


def reference_uri() -> str:
    image = Image.open(REFERENCE).convert("RGB")
    image.thumbnail((1024, 1024))
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()


def make_pose(pose: str, key: str, reference: str) -> str:
    task = api("POST", API, key, {
        "ai_model": MODEL, "prompt": CHARACTER + POSES[pose], "reference_image_urls": [reference],
        "aspect_ratio": "1:1", "remove_background": True,
    })["result"]
    deadline = time.time() + 900
    while time.time() < deadline:
        status = api("GET", f"{API}/{task}", key)
        if status["status"] == "SUCCEEDED":
            WORK.mkdir(parents=True, exist_ok=True)
            raw = WORK / f"{pose}-{task[:8]}.png"
            urllib.request.urlretrieve(status["image_urls"][0], raw)
            image = Image.open(raw).convert("RGBA")
            bbox = image.getbbox()
            if bbox:
                image = image.crop(bbox)
            image.thumbnail((SIZE, SIZE), Image.LANCZOS)
            canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
            canvas.paste(image, ((SIZE - image.width) // 2, SIZE - image.height), image)
            OUT.mkdir(parents=True, exist_ok=True)
            canvas.save(OUT / f"{pose}.webp", "WEBP", quality=90)
            return f"{pose}: готово ({raw.name})"
        if status["status"] in ("FAILED", "CANCELED"):
            return f"{pose}: {status['status']} {status.get('task_error')}"
        time.sleep(8)
    return f"{pose}: timeout"


def main() -> None:
    poses = sys.argv[1:] or list(POSES)
    key, reference = load_key(), reference_uri()
    with ThreadPoolExecutor(max_workers=4) as pool:
        for line in pool.map(lambda p: make_pose(p, key, reference), poses):
            print(line, flush=True)


if __name__ == "__main__":
    main()
