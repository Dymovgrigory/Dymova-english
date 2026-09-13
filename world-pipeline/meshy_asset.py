#!/usr/bin/env python3
"""Foxinburg World asset pipeline: Meshy text-to-3d -> optimize -> registry.

Usage:
  python3 meshy_asset.py --id school-foxcoin --prompt "..." \
      [--texture-prompt "..."] [--category collectibles] [--no-refine]

Читает MESHY_API_KEY/MESHY_API_BASE из .env рядом со скриптом.
Результат: assets/<id>/<id>-v1.glb (draco+webp), запись в asset-registry.json.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REGISTRY = ROOT / "asset-registry.json"

def load_env() -> None:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))

def api(method: str, path: str, payload: dict | None = None) -> dict:
    base = os.environ.get("MESHY_API_BASE", "https://api.meshy.ai/openapi")
    key = os.environ["MESHY_API_KEY"]
    req = urllib.request.Request(
        f"{base}{path}",
        method=method,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        data=json.dumps(payload).encode() if payload else None,
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)

def wait_task(task_id: str, timeout_sec: int = 900) -> dict:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        t = api("GET", f"/v2/text-to-3d/{task_id}")
        status = t.get("status")
        print(f"  [{task_id[:8]}] {status} {t.get('progress', '')}", flush=True)
        if status == "SUCCEEDED":
            return t
        if status in ("FAILED", "CANCELED"):
            raise SystemExit(f"Task {status}: {t.get('task_error')}")
        time.sleep(10)
    raise SystemExit("Timeout waiting for Meshy task")

def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, dest)

def optimize(src: Path, dest: Path) -> None:
    subprocess.run(
        ["npx", "-y", "@gltf-transform/cli", "optimize", str(src), str(dest),
         "--compress", "draco", "--texture-compress", "webp",
         "--texture-size", "512", "--simplify", "false"],
        check=True, cwd=src.parent,
    )

def update_registry(entry: dict) -> None:
    data = json.loads(REGISTRY.read_text()) if REGISTRY.exists() else {"version": 1, "assets": []}
    data["assets"] = [a for a in data["assets"] if a["assetId"] != entry["assetId"]] + [entry]
    REGISTRY.write_text(json.dumps(data, ensure_ascii=False, indent=2))

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--id", required=True, help="snake-case asset id, напр. school-foxcoin")
    p.add_argument("--prompt", required=True)
    p.add_argument("--texture-prompt", default=None)
    p.add_argument("--category", default="props")
    p.add_argument("--no-refine", action="store_true", help="только геометрия (preview)")
    a = p.parse_args()

    load_env()
    out = ROOT / "assets" / a.id
    out.mkdir(parents=True, exist_ok=True)

    print("== preview (геометрия) ==")
    task = api("POST", "/v2/text-to-3d", {"mode": "preview", "prompt": a.prompt, "should_remesh": True})
    prev = wait_task(task["result"])
    download(prev["model_urls"]["glb"], out / f"{a.id}-raw.glb")
    if prev.get("thumbnail_url"):
        download(prev["thumbnail_url"], out / f"{a.id}-thumb.png")

    final_task = prev
    if not a.no_refine:
        print("== refine (текстура) ==")
        payload = {"mode": "refine", "preview_task_id": task["result"], "enable_pbr": True}
        if a.texture_prompt:
            payload["texture_prompt"] = a.texture_prompt
        task2 = api("POST", "/v2/text-to-3d", payload)
        final_task = wait_task(task2["result"])
        download(final_task["model_urls"]["glb"], out / f"{a.id}-textured.glb")
        if final_task.get("thumbnail_url"):
            download(final_task["thumbnail_url"], out / f"{a.id}-thumb.png")

    print("== optimize (draco+webp) ==")
    src = out / (f"{a.id}-textured.glb" if not a.no_refine else f"{a.id}-raw.glb")
    optimize(src, out / f"{a.id}-v1.glb")
    size_kb = (out / f"{a.id}-v1.glb").stat().st_size // 1024

    update_registry({
        "assetId": a.id,
        "type": "model/gltf-binary",
        "url": f"assets/{a.id}/{a.id}-v1.glb",
        "thumbnail": f"assets/{a.id}/{a.id}-thumb.png",
        "version": 1,
        "category": a.category,
        "lod": ["v1"],
        "mobileVariant": f"assets/{a.id}/{a.id}-v1.glb",
        "desktopVariant": f"assets/{a.id}/{a.id}-v1.glb",
        "dependencies": [],
        "sizeKb": size_kb,
        "source": {"provider": "meshy", "task": final_task["id"], "prompt": a.prompt},
    })
    print(f"OK: {out}/{a.id}-v1.glb ({size_kb} KB), registry updated")

if __name__ == "__main__":
    main()
