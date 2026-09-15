"""Озвучка английских слов для урока.

Порядок движков:
1. edge-tts (нейросеть Microsoft, качество для детей)
2. macOS say + Samantha
3. espeak-ng (последний запасной вариант)
"""
from __future__ import annotations

import asyncio
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "data" / "tts"
SAFE = re.compile(r"[^A-Za-z0-9 .,!?'\-]")
MAX_LEN = 80
# Ясный детский голос без «робота» espeak.
EDGE_VOICE = "en-US-AriaNeural"


def _clean(text: str) -> str:
    raw = SAFE.sub("", (text or "").strip())[:MAX_LEN]
    return raw.strip() or "hello"


def media_path(text: str, ext: str) -> Path:
    key = hashlib.sha1(f"foxy2|{_clean(text)}|{ext}".encode("utf-8")).hexdigest()[:16]
    return ROOT / f"{key}.{ext}"


def _usable(path: Path, min_bytes: int = 2000) -> bool:
    return path.exists() and path.stat().st_size >= min_bytes


def _edge_tts(phrase: str, dest: Path) -> bool:
    try:
        import edge_tts  # type: ignore
    except ImportError:
        return False
    dest.unlink(missing_ok=True)
    ROOT.mkdir(parents=True, exist_ok=True)

    async def _run() -> None:
        communicate = edge_tts.Communicate(phrase, EDGE_VOICE, rate="-5%")
        await communicate.save(str(dest))

    try:
        asyncio.run(_run())
    except Exception:
        dest.unlink(missing_ok=True)
        return False
    return _usable(dest, 1500)


def _macos_say(phrase: str, dest: Path) -> bool:
    if not (sys.platform == "darwin" and shutil.which("say")):
        return False
    dest.unlink(missing_ok=True)
    ROOT.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".aiff")
    try:
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
        return _usable(dest, 8000)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        dest.unlink(missing_ok=True)
        tmp.unlink(missing_ok=True)
        return False


def _espeak(phrase: str, dest: Path) -> bool:
    engine = shutil.which("espeak-ng") or shutil.which("espeak")
    if not engine:
        return False
    dest.unlink(missing_ok=True)
    ROOT.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [engine, "-v", "en-us", "-s", 130, "-g", "4", "-w", str(dest), phrase],
            check=True, capture_output=True, timeout=12,
        )
        return _usable(dest, 8000)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, TypeError):
        # -s may need string on some builds
        try:
            subprocess.run(
                [engine, "-v", "en-us", "-s", "130", "-g", "4", "-w", str(dest), phrase],
                check=True, capture_output=True, timeout=12,
            )
            return _usable(dest, 8000)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            dest.unlink(missing_ok=True)
            return False


def synth_english(text: str) -> Path | None:
    """Вернуть путь к mp3 (edge) или wav (say/espeak)."""
    phrase = _clean(text)
    mp3 = media_path(phrase, "mp3")
    if _usable(mp3, 1500):
        return mp3
    if _edge_tts(phrase, mp3):
        return mp3

    wav = media_path(phrase, "wav")
    if _usable(wav, 8000):
        return wav
    if _macos_say(phrase, wav):
        return wav
    if _espeak(phrase, wav):
        return wav
    return None
