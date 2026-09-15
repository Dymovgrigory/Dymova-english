#!/usr/bin/env python3
"""Предгенерация озвучки всех слов и фраз курса — урок не ждёт синтеза."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.world.catalog import load_units
from app.world.tts import synth_english


def phrases() -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for unit in load_units().values():
        for word in unit["words"]:
            for text in (word.get("en"), word.get("example_en")):
                if text and text not in seen:
                    seen.add(text)
                    out.append(text)
        for phrase in unit["phrases"]:
            text = phrase.get("en")
            if text and text not in seen:
                seen.add(text)
                out.append(text)
    return out


def main() -> None:
    ok = miss = 0
    for text in phrases():
        path = synth_english(text)
        if path:
            ok += 1
            print("ok", text)
        else:
            miss += 1
            print("skip", text)
    print(f"ready={ok} missing={miss}")
    if miss and ok == 0:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
