"""Normalização de áudio via ffmpeg (§6.1, risco §14: sempre re-encodar).

Converte qualquer entrada (mp3/m4a/ogg/opus/wav/flac + vídeo mp4/mkv) para WAV mono
16 kHz. O builder de args é puro/testável; a execução é uma casca fina de subprocess.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

SUPPORTED_EXTS = {
    "wav", "mp3", "m4a", "ogg", "opus", "flac", "aac", "wma",  # áudio
    "mp4", "mkv", "mov", "webm", "avi",                         # vídeo (extrai áudio)
}


def is_supported(path: str | Path) -> bool:
    ext = Path(path).suffix.lower().lstrip(".")
    return ext in SUPPORTED_EXTS


def ffmpeg_normalize_args(src: str | Path, dst: str | Path) -> list[str]:
    """Args do ffmpeg para WAV mono 16 kHz PCM 16-bit (extrai áudio de vídeo com -vn)."""
    return [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src),
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        "-c:a", "pcm_s16le",
        str(dst),
    ]


def normalize_audio(src: str | Path, dst: str | Path) -> Path:
    """Executa o ffmpeg; levanta RuntimeError com mensagem clara em caso de falha."""
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg não encontrado no PATH. Instale ffmpeg.")
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ffmpeg_normalize_args(src, dst),
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou em {Path(src).name}:\n{proc.stderr.strip()}")
    return dst


def probe_duration(path: str | Path) -> float:
    """Duração em segundos via ffprobe (0.0 se indisponível)."""
    if shutil.which("ffprobe") is None:
        return 0.0
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(proc.stdout.strip())
    except (ValueError, AttributeError):
        return 0.0
