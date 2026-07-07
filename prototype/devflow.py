#!/usr/bin/env python3
"""Единая точка входа для сборки и минификации прототипа.

Команды:
  build   — пересобрать HTML-страницы из генераторов
  minify  — обновить минифицированные Tilda-блоки
  all     — build + minify
  status  — показать, что устарело или отсутствует
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from minify_block import minify as minify_html

ROOT = Path(__file__).resolve().parent
BLOCK_DIR = ROOT / "tilda_blocks_min"

MINIFY_SOURCES = [
    "tilda_advantages.html",
    "tilda_contacts_map.html",
    "tilda_cta_diagnostika.html",
    "tilda_cta_enrollment.html",
    "tilda_directions.html",
    "tilda_faq.html",
    "tilda_footer.html",
    "tilda_header_unified.html",
    "tilda_languages.html",
    "tilda_onboarding.html",
    "tilda_photobank_gallery.html",
    "tilda_pricing_enrollment.html",
    "tilda_reviews.html",
    "tilda_svedeniya.html",
    "tilda_team.html",
]


@dataclass(frozen=True)
class BuildStep:
    label: str
    script: str


BUILD_STEPS = [
    BuildStep("course pages", "build_course_pages.py"),
    BuildStep("subpages", "build_subpages.py"),
]


def run_script(script: str) -> None:
    subprocess.run([sys.executable, str(ROOT / script)], cwd=ROOT, check=True)


def build() -> None:
    for step in BUILD_STEPS:
        print(f"[build] {step.label}")
        run_script(step.script)


def minify(dry_run: bool = False) -> list[str]:
    BLOCK_DIR.mkdir(parents=True, exist_ok=True)
    changed: list[str] = []
    for source_name in MINIFY_SOURCES:
        source = ROOT / source_name
        target = BLOCK_DIR / f"{source.stem}_min.html"
        if not source.exists():
            raise FileNotFoundError(f"missing source block: {source}")
        rendered = minify_html(source.read_text(encoding="utf-8"))
        if target.exists() and target.read_text(encoding="utf-8") == rendered:
            continue
        changed.append(target.name)
        if dry_run:
            continue
        target.write_text(rendered, encoding="utf-8")
    return changed


def status() -> int:
    missing: list[str] = []
    stale: list[str] = []
    for source_name in MINIFY_SOURCES:
        source = ROOT / source_name
        target = BLOCK_DIR / f"{source.stem}_min.html"
        if not target.exists():
            missing.append(target.name)
            continue
        if source.stat().st_mtime > target.stat().st_mtime:
            stale.append(target.name)
    print(f"tracked sources: {len(MINIFY_SOURCES)}")
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

    if args.command == "build":
        build()
        return 0
    if args.command == "minify":
        changed = minify()
        print(f"updated minified blocks: {len(changed)}")
        for name in changed:
            print(f"  - {name}")
        return 0
    if args.command == "all":
        build()
        changed = minify()
        print(f"updated minified blocks: {len(changed)}")
        for name in changed:
            print(f"  - {name}")
        return 0
    if args.command == "status":
        return status()

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
