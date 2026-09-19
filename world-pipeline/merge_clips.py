#!/usr/bin/env python3
"""Склейка анимационных клипов из Meshy animation GLB в базовую ригнутую модель.

Берёт анимации из одного или нескольких GLB (результат /v1/animations) и
добавляет их в базовый GLB, перепривязывая каналы по ИМЕНАМ нод скелета
(индексы в разных файлах не совпадают). Каналы на ноды, которых нет в базе,
пропускаются с предупреждением. Базовый файл не затирается.

Usage:
  python3 merge_clips.py BASE.glb OUT.glb ANIM1.glb [ANIM2.glb ...]
      [--rename OldName=NewName ...]

Чистый Python, без зависимостей: GLB = 12-байтный заголовок + JSON chunk + BIN chunk.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

COMPONENT_SIZE = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
TYPE_COUNT = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}


def read_glb(path: Path) -> tuple[dict, bytearray]:
    data = path.read_bytes()
    magic, version, _length = struct.unpack("<III", data[:12])
    assert magic == 0x46546C67 and version == 2, f"{path}: не GLB v2"
    offset = 12
    gltf: dict | None = None
    bin_chunk = bytearray()
    while offset < len(data):
        chunk_len, chunk_type = struct.unpack("<II", data[offset:offset + 8])
        chunk = data[offset + 8:offset + 8 + chunk_len]
        if chunk_type == 0x4E4F534A:  # JSON
            gltf = json.loads(chunk)
        elif chunk_type == 0x004E4942:  # BIN
            bin_chunk = bytearray(chunk)
        offset += 8 + chunk_len
    if gltf is None:
        raise SystemExit(f"{path}: нет JSON chunk")
    return gltf, bin_chunk


def write_glb(path: Path, gltf: dict, bin_chunk: bytearray) -> None:
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    bin_chunk += b"\x00" * (-len(bin_chunk) % 4)
    total = 12 + 8 + len(js) + 8 + len(bin_chunk)
    with path.open("wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, total))
        f.write(struct.pack("<II", len(js), 0x4E4F534A))
        f.write(js)
        f.write(struct.pack("<II", len(bin_chunk), 0x004E4942))
        f.write(bin_chunk)


def accessor_span(accessor: dict) -> int:
    return COMPONENT_SIZE[accessor["componentType"]] * TYPE_COUNT[accessor["type"]] * accessor["count"]


def copy_accessor(gltf_src: dict, bin_src: bytearray, gltf_dst: dict, bin_dst: bytearray, idx: int) -> int:
    """Копирует accessor (только bufferView-based) в dst, возвращает новый индекс."""
    acc = dict(gltf_src["accessors"][idx])
    bv = dict(gltf_src["bufferViews"][acc["bufferView"]])
    start = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    length = accessor_span(acc)
    raw = bin_src[start:start + length]
    if len(raw) < length:
        raise SystemExit(f"accessor {idx}: данных меньше ожидаемого ({len(raw)} < {length})")
    bin_dst += b"\x00" * (-len(bin_dst) % 4)
    new_bv = {"buffer": 0, "byteOffset": len(bin_dst), "byteLength": length}
    bin_dst += raw
    gltf_dst.setdefault("bufferViews", []).append(new_bv)
    acc["bufferView"] = len(gltf_dst["bufferViews"]) - 1
    acc["byteOffset"] = 0
    gltf_dst.setdefault("accessors", []).append(acc)
    return len(gltf_dst["accessors"]) - 1


def merge(base_path: Path, out_path: Path, anim_paths: list[Path], renames: dict[str, str]) -> None:
    gltf_base, bin_base = read_glb(base_path)
    node_index_by_name = {n.get("name"): i for i, n in enumerate(gltf_base.get("nodes", []))}
    existing = {a.get("name") for a in gltf_base.get("animations", [])}
    print(f"база: {len(existing)} клипов: {sorted(existing)}")

    for anim_path in anim_paths:
        gltf_src, bin_src = read_glb(anim_path)
        src_nodes = gltf_src.get("nodes", [])
        for anim in gltf_src.get("animations", []):
            name = renames.get(anim.get("name", ""), anim.get("name") or anim_path.stem)
            if name in existing:
                print(f"  ! клип '{name}' уже есть в базе — пропуск ({anim_path.name})")
                continue
            samplers = []
            for smp in anim["samplers"]:
                samplers.append({
                    "input": copy_accessor(gltf_src, bin_src, gltf_base, bin_base, smp["input"]),
                    "output": copy_accessor(gltf_src, bin_src, gltf_base, bin_base, smp["output"]),
                    "interpolation": smp.get("interpolation", "LINEAR"),
                })
            channels = []
            skipped: set[str] = set()
            for ch in anim["channels"]:
                target = ch["target"]
                node_name = src_nodes[target["node"]].get("name")
                if node_name not in node_index_by_name:
                    skipped.add(str(node_name))
                    continue
                channels.append({
                    "sampler": ch["sampler"],
                    "target": {"node": node_index_by_name[node_name], "path": target["path"]},
                })
            if not channels:
                print(f"  ! клип '{name}': ни одного канала на кости базы — пропуск")
                continue
            gltf_base.setdefault("animations", []).append(
                {"name": name, "samplers": samplers, "channels": channels})
            existing.add(name)
            print(f"  + '{name}': {len(channels)} каналов"
                  + (f", пропущены ноды: {sorted(skipped)}" if skipped else ""))

    gltf_base["buffers"][0]["byteLength"] = len(bin_base) + (-len(bin_base) % 4)
    write_glb(out_path, gltf_base, bin_base)
    size_kb = out_path.stat().st_size // 1024
    print(f"OK: {out_path} ({size_kb} KB), клипов: {len(gltf_base['animations'])}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("base", type=Path)
    p.add_argument("out", type=Path)
    p.add_argument("anims", nargs="+", type=Path)
    p.add_argument("--rename", nargs="*", default=[],
                   help="OldName=NewName — переименовать клип при вставке")
    a = p.parse_args()
    renames = dict(r.split("=", 1) for r in a.rename)
    merge(a.base, a.out, a.anims, renames)


if __name__ == "__main__":
    main()
