#!/usr/bin/env python3
"""Foxi rigged v2: Meshy rigging/animations -> новые клипы в foxi-rigged.glb.

Этапы (каждый — подкоманда, идемпотентно через work-файлы):
  balance            баланс кредитов Meshy
  library            список action_id из библиотеки анимаций (grep: walk/gesture)
  rig                POST /v1/rigging по публичному model_url -> rig_task_id
  anim               POST /v1/animations для выбранных action_id -> animation GLB
  (склейка — merge_clips.py, правка скиннинга — fix_skin.py)

Ключ: MESHY_API_KEY/MESHY_API_BASE из .env рядом со скриптом (не коммитить!).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "foxi-v2"
# НЕригнутая модель (draco-декодированная): rigging API требует T-pose mesh.
# foxi-rigged.glb (уже ригнутый) даёт 422 "Pose estimation failed".
MODEL_URL = "https://dymova-english.ru/tmp-assets/foxi-unrigged.glb"

def load_env() -> None:
    # приоритет: уже выставленный MESHY_API_KEY > world-pipeline/.env > secrets/meshy.env
    for env in (ROOT / ".env", ROOT.parent / "secrets" / "meshy.env"):
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
        data=json.dumps(payload).encode() if payload is not None else None,
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:2000]
        raise SystemExit(f"HTTP {e.code} {path}: {body}")

def wait_task(path_prefix: str, task_id: str, timeout_sec: int = 1800) -> dict:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        t = api("GET", f"{path_prefix}/{task_id}")
        status = t.get("status")
        print(f"  [{task_id[:8]}] {status} {t.get('progress', '')}", flush=True)
        if status == "SUCCEEDED":
            return t
        if status in ("FAILED", "CANCELED", "EXPIRED"):
            raise SystemExit(f"Task {status}: {json.dumps(t.get('task_error'), ensure_ascii=False)}")
        time.sleep(15)
    raise SystemExit("Timeout waiting for Meshy task")

def cmd_balance() -> None:
    print(json.dumps(api("GET", "/v1/balance"), indent=2))

def cmd_library(query: str) -> None:
    data = api("GET", "/v1/animation-libraries")
    items = data.get("result", data)
    if isinstance(items, dict):
        items = items.get("animations", items.get("data", []))
    out = WORK / "animation-library.json"
    WORK.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(items, ensure_ascii=False, indent=2))
    q = query.lower()
    for it in items:
        name = str(it.get("name", ""))
        if not q or q in name.lower():
            print(f"{it.get('action_id'):>5}  {name}")

def cmd_rig() -> None:
    r = api("POST", "/v1/rigging", {"model_url": MODEL_URL, "height_meters": 1.0})
    task_id = r["result"]
    (WORK / "rig-task.txt").write_text(task_id)
    print("rig task:", task_id)
    t = wait_task("/v1/rigging", task_id)
    (WORK / "rig-result.json").write_text(json.dumps(t, indent=2))
    print(json.dumps({k: t.get(k) for k in ("status", "result", "rigged_character_url")}, indent=2))

def cmd_anim(action_ids: list[int]) -> None:
    rig_task_id = (WORK / "rig-task.txt").read_text().strip()
    (WORK / "animations").mkdir(parents=True, exist_ok=True)
    for aid in action_ids:
        out_json = WORK / "animations" / f"{aid}.json"
        if out_json.exists():
            print(f"action {aid}: уже есть, пропуск")
            continue
        r = api("POST", "/v1/animations", {"rig_task_id": rig_task_id, "action_id": aid, "fps": 30})
        task_id = r["result"]
        print(f"action {aid}: task {task_id}")
        t = wait_task("/v1/animations", task_id)
        out_json.write_text(json.dumps(t, indent=2))
        url = (t.get("result") or {}).get("animation_glb_url") or t.get("animation_glb_url")
        if url:
            dest = WORK / "animations" / f"{aid}.glb"
            urllib.request.urlretrieve(url, dest)
            print(f"  -> {dest} ({dest.stat().st_size // 1024} KB)")

def main() -> None:
    load_env()
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("balance")
    lib = sub.add_parser("library")
    lib.add_argument("--query", default="")
    sub.add_parser("rig")
    anim = sub.add_parser("anim")
    anim.add_argument("action_ids", nargs="+", type=int)
    a = p.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    if a.cmd == "balance":
        cmd_balance()
    elif a.cmd == "library":
        cmd_library(a.query)
    elif a.cmd == "rig":
        cmd_rig()
    elif a.cmd == "anim":
        cmd_anim(a.action_ids)

if __name__ == "__main__":
    main()
