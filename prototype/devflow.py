#!/usr/bin/env python3
"""Единая точка входа для минификации прототипа.

Команды:
  build   — обновить минифицированные Tilda-блоки
  minify  — то же самое
  all     — build + status
  status  — показать, что устарело или отсутствует
"""

from __future__ import annotations

import argparse
from pathlib import Path

from minify_block import minify as minify_html

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "tilda_blocks_min"

SOURCE_FILES = [
    "foxinburg-onboarding.html",
    "tilda_advantages.html",
    "tilda_cta_diagnostika.html",
    "tilda_directions.html",
    "tilda_dropdown_menu.html",
    "tilda_languages.html",
    "tilda_onboarding.html",
    "tilda_photobank_gallery.html",
    "tilda_photobank_head.html",
    "tilda_slogan.html",
    "tilda_summerbar.html",
    "tilda_svedeniya.html",
    "tilda_team.html",
    "tilda_topbar.html",
]


def minify(dry_run: bool = False) -> list[str]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    changed: list[str] = []
    for name in SOURCE_FILES:
        source = ROOT / name
        target = OUT_DIR / f"{source.stem}_min.html"
        if not source.exists():
            raise FileNotFoundError(f"missing source block: {source}")
        rendered = minify_html(source.read_text(encoding="utf-8"))
        if target.exists() and target.read_text(encoding="utf-8") == rendered:
            continue
        changed.append(target.name)
        if not dry_run:
            target.write_text(rendered, encoding="utf-8")
    return changed


def status() -> int:
    missing: list[str] = []
    stale: list[str] = []
    for name in SOURCE_FILES:
        source = ROOT / name
        target = OUT_DIR / f"{source.stem}_min.html"
        if not target.exists():
            missing.append(target.name)
            continue
        if source.stat().st_mtime > target.stat().st_mtime:
            stale.append(target.name)
    print(f"tracked sources: {len(SOURCE_FILES)}")
    print(f"missing minified: {len(missing)}")
    print(f"stale minified: {len(stale)}")
    if missing:
        print("missing:")
        for name in missing:
            print(f"  - {name}")
    if stale:
        print("stale:")
        for name in stale:
            print(f"  - {name}")
    return 1 if missing or stale else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build")
    sub.add_parser("minify")
    sub.add_parser("all")
    sub.add_parser("status")
    sub.add_parser("help")
    args = parser.parse_args()

    if args.command in {"build", "minify"}:
        changed = minify()
        print(f"updated minified blocks: {len(changed)}")
        for name in changed:
            print(f"  - {name}")
        return 0
    if args.command == "all":
        changed = minify()
        print(f"updated minified blocks: {len(changed)}")
        for name in changed:
            print(f"  - {name}")
        return status()
    if args.command == "status":
        return status()

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
