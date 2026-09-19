#!/usr/bin/env python3
"""Правка скиннинга сырого rigged GLB от Meshy (процедура из prototype/mascot/README.md).

Три правки, которые были утеряны вместе с исходным скриптом сессии 42 —
восстановлены по README:

1. **Хвост**: в скелете Meshy biped нет кости хвоста, вершины хвоста сидят на
   `Hips` и в танцах улетали сквозь тело. Добавляется кость `Tail` (ребёнок
   `Hips`, локальная матрица полная, т.к. у `Armature` scale 0.01), вершины
   хвоста (доминирующий joint = Hips, позади тела) перевешиваются на неё 100%.
   Дальше хвост управляется процедурно из mascot.js.
2. **Рюкзак/лямки**: фиолетовые вершины (цвет текстуры по UV: purple & y>0.48),
   сидевшие на Left/RightShoulder/Head/neck/LeftArm, перевешиваются на
   `Spine02` (100%).
3. **Материал**: alphaMode OPAQUE (было BLEND + doubleSided — мерцание),
   KHR_materials_specular → 1.0, emissiveFactor 0.45.

ВХОД: GLB БЕЗ draco (декодируй заранее:
`npx @gltf-transform/cli optimize in.glb decoded.glb --compress false
 --texture-compress false --simplify false`).

Usage:
  python3 fix_skin.py raw.glb fixed.glb [--tail-z -0.15] [--tail-y-max 0.55]
Зависимости: numpy, Pillow.
"""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

import numpy as np
from PIL import Image

from merge_clips import read_glb, write_glb

COMPONENT_NP = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
TYPE_COUNT = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}


def read_accessor(gltf: dict, bin_chunk: bytearray, idx: int) -> np.ndarray:
    acc = gltf["accessors"][idx]
    bv = gltf["bufferViews"][acc["bufferView"]]
    start = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    n = TYPE_COUNT[acc["type"]]
    dtype = COMPONENT_NP[acc["componentType"]]
    arr = np.frombuffer(bytes(bin_chunk[start:start + acc["count"] * n * np.dtype(dtype).itemsize]), dtype=dtype)
    return arr.reshape(acc["count"], n) if n > 1 else arr


def write_accessor(gltf: dict, bin_chunk: bytearray, idx: int, arr: np.ndarray) -> None:
    """Перезаписывает accessor на месте (форма/тип не меняются)."""
    acc = gltf["accessors"][idx]
    bv = gltf["bufferViews"][acc["bufferView"]]
    start = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    raw = np.ascontiguousarray(arr).astype(COMPONENT_NP[acc["componentType"]]).tobytes()
    assert len(raw) == acc["count"] * TYPE_COUNT[acc["type"]] * np.dtype(COMPONENT_NP[acc["componentType"]]).itemsize
    bin_chunk[start:start + len(raw)] = raw


def find_joint(skin: dict, nodes: list[dict], name: str) -> int:
    for pos, node_idx in enumerate(skin["joints"]):
        if nodes[node_idx].get("name") == name:
            return pos
    raise SystemExit(f"joint '{name}' не найден в скинe")


def reweight(joints: np.ndarray, weights: np.ndarray, mask: np.ndarray, joint_pos: int) -> int:
    idx = np.where(mask)[0]
    joints[idx] = 0
    joints[idx, 0] = joint_pos
    weights[idx] = 0.0
    weights[idx, 0] = 1.0
    return len(idx)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("src", type=Path)
    p.add_argument("out", type=Path)
    p.add_argument("--tail-z", type=float, default=-0.15, help="хвост: z меньше порога (позади тела)")
    p.add_argument("--tail-y-max", type=float, default=0.6, help="хвост: y не выше (не цеплять голову/уши)")
    a = p.parse_args()

    gltf, bin_chunk = read_glb(a.src)
    nodes = gltf["nodes"]
    skin = gltf["skins"][0]
    by_name = {n.get("name"): i for i, n in enumerate(nodes)}

    hips_joint = find_joint(skin, nodes, "Hips")
    spine02_joint = find_joint(skin, nodes, "Spine02")

    # --- 1. кость Tail: ребёнок Hips, полная локальная матрица (Armature со scale) ---
    hips_node = nodes[by_name["Hips"]]
    armature_scale = 0.01
    for anc_idx in by_name.values():
        pass  # scale ищем у корня арматуры ниже
    for n in nodes:
        if "Armature" in (n.get("name") or ""):
            armature_scale = (n.get("scale") or [1, 1, 1])[0]
    hips_world_t = hips_node.get("translation", [0, 0, 0])
    tail_translation = [
        hips_world_t[0],
        hips_world_t[1] + 0.05 / armature_scale,
        hips_world_t[2] - 0.20 / armature_scale,  # позади, в координатах арматуры
    ]
    tail_node_idx = len(nodes)
    nodes.append({"name": "Tail", "translation": tail_translation})
    hips_node.setdefault("children", []).append(tail_node_idx)
    skin["joints"].append(tail_node_idx)
    tail_joint = len(skin["joints"]) - 1
    # inverseBindMatrix для Tail — единичная с переносом к основанию хвоста (мир)
    ibm = read_accessor(gltf, bin_chunk, skin["inverseBindMatrices"]).reshape(-1, 16)
    new_ibm = np.eye(4, dtype=np.float32)
    new_ibm[:3, 3] = [-tail_translation[0] * armature_scale,
                      -tail_translation[1] * armature_scale,
                      -tail_translation[2] * armature_scale]
    ibm_acc = gltf["accessors"][skin["inverseBindMatrices"]]
    ibm_bv = gltf["bufferViews"][ibm_acc["bufferView"]]
    ibm_start = ibm_bv.get("byteOffset", 0) + ibm_acc.get("byteOffset", 0)
    new_raw = new_ibm.T.astype(np.float32).tobytes()  # glTF column-major
    ibm_acc["count"] += 1
    ibm_bv["byteLength"] += len(new_raw)
    bin_chunk[ibm_start:ibm_start] = new_raw  # вставка сдвигает остальные bufferView!
    # сдвиг byteOffset всех bufferView после точки вставки
    for bv in gltf["bufferViews"]:
        if bv is not ibm_bv and bv.get("byteOffset", 0) > ibm_bv.get("byteOffset", 0):
            bv["byteOffset"] = bv.get("byteOffset", 0) + len(new_raw)

    # --- 2. вершины: POSITION/JOINTS_0/WEIGHTS_0 (+UV для рюкзака) ---
    total_tail = total_pack = 0
    for mesh in gltf.get("meshes", []):
        for prim in mesh["primitives"]:
            attrs = prim["attributes"]
            if "JOINTS_0" not in attrs or "WEIGHTS_0" not in attrs:
                continue
            pos = read_accessor(gltf, bin_chunk, attrs["POSITION"]).astype(np.float32)
            joints = read_accessor(gltf, bin_chunk, attrs["JOINTS_0"]).copy()
            weights = read_accessor(gltf, bin_chunk, attrs["WEIGHTS_0"]).astype(np.float32).copy()
            dominant = joints[np.arange(len(joints)), np.argmax(weights, axis=1)]

            # хвост: сидит на Hips, позади тела, не выше спины
            tail_mask = (dominant == hips_joint) & (pos[:, 2] < a.tail_z) & (pos[:, 1] < a.tail_y_max)
            total_tail += reweight(joints, weights, tail_mask, tail_joint)

            # рюкзак/лямки: фиолетовые по текстуре, верх тела, не на Spine02
            if "TEXCOORD_0" in attrs and gltf.get("images"):
                uv = read_accessor(gltf, bin_chunk, attrs["TEXCOORD_0"]).astype(np.float32)
                img_idx = gltf["textures"][gltf["materials"][prim["material"]]
                          ["pbrMetallicRoughness"]["baseColorTexture"]["index"]]["source"]
                image = gltf["images"][img_idx]
                bv = gltf["bufferViews"][image["bufferView"]]
                tex = Image.open(__import__("io").BytesIO(
                    bytes(bin_chunk[bv.get("byteOffset", 0):bv.get("byteOffset", 0) + bv["byteLength"]]))).convert("RGB")
                tex_arr = np.asarray(tex)
                px = (np.clip(uv[:, 0], 0, 1) * (tex.width - 1)).astype(int)
                py = (np.clip(uv[:, 1], 0, 1) * (tex.height - 1)).astype(int)
                rgb = tex_arr[py, px].astype(np.int32)
                purple = (rgb[:, 2] > 110) & (rgb[:, 0] > 80) & (rgb[:, 2] > rgb[:, 1] + 30)
                pack_mask = purple & (pos[:, 1] > 0.48) & (dominant != spine02_joint) & ~tail_mask
                total_pack += reweight(joints, weights, pack_mask, spine02_joint)

            write_accessor(gltf, bin_chunk, attrs["JOINTS_0"], joints)
            write_accessor(gltf, bin_chunk, attrs["WEIGHTS_0"], weights)

    # --- 3. материалы: OPAQUE, односторонние, specular 1.0, эмиссия 0.45 ---
    for mat in gltf.get("materials", []):
        mat["alphaMode"] = "OPAQUE"
        mat["doubleSided"] = False
        spec = mat.get("extensions", {}).get("KHR_materials_specular")
        if spec is not None:
            spec["specularFactor"] = 1.0
            if "specularColorFactor" in spec:
                spec["specularColorFactor"] = [1.0, 1.0, 1.0]
        mat["emissiveFactor"] = [0.45, 0.45, 0.45]

    gltf["buffers"][0]["byteLength"] = len(bin_chunk)
    write_glb(a.out, gltf, bin_chunk)
    print(f"хвост: перевешено {total_tail} вершин на Tail (joint #{tail_joint})")
    print(f"рюкзак: перевешено {total_pack} вершин на Spine02")
    print(f"OK: {a.out} ({a.out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
