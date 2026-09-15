"""Озвучка английских слов для урока. На Mac — системный say, иначе тишина (клиент возьмёт Web Speech)."""
from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "data" / "tts"
SAFE = re.compile(r"[^A-Za-z0-9 .,!?'\-]")
MAX_LEN = 80


def _clean(text: str) -> str:
    raw = SAFE.sub("", (text or "").strip())[:MAX_LEN]
    return raw.strip() or "hello"


def wav_path(text: str) -> Path:
    key = hashlib.sha1(f"foxy1|{_clean(text)}".encode("utf-8")).hexdigest()[:16]
    return ROOT / f"{key}.wav"


def _usable(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < 8000:
        return False
    try:
        import wave
        with wave.open(str(path), "rb") as wav:
            return wav.getnframes() > 2000 and wav.getframerate() > 0
    except Exception:
        return path.stat().st_size > 12000


def synth_english(text: str) -> Path | None:
    phrase = _clean(text)
    dest = wav_path(phrase)
    if _usable(dest):
        return dest
    dest.unlink(missing_ok=True)
    ROOT.mkdir(parents=True, exist_ok=True)
    try:
        if sys.platform == "darwin" and shutil.which("say"):
            tmp = dest.with_suffix(".aiff")
            spoken = f"[[pbas 58]] {phrase}"
            subprocess.run(
                ["say", "-v", "Samantha", "-r", "148", "-o", str(tmp), spoken],
                check=True, capture_output=True, timeout=12,
            )
            af = shutil.which("afconvert")
            if af:
                subprocess.run(
                    [af, str(tmp), str(dest), "-f", "WAVE", "-d", "LEI16@22050"],
                    check=True, capture_output=True, timeout=12,
                )
                tmp.unlink(missing_ok=True)
            else:
                tmp.replace(dest)
        else:
            engine = shutil.which("espeak-ng") or shutil.which("espeak")
            if not engine:
                return dest if dest.exists() else None
            subprocess.run(
                [engine, "-v", "en", "-s", "140", "-w", str(dest), phrase],
                check=True, capture_output=True, timeout=12,
            )
        if _usable(dest):
            return dest
        dest.unlink(missing_ok=True)
        return None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        dest.unlink(missing_ok=True)
        return None
