"""Uso imediato: transcreve os áudios do WhatsApp enquanto o projeto é construído.

O transcribe() do faster-whisper processa UM arquivo por vez, então percorremos
todos os áudios em loop. Ajuste PASTA/PADRAO se os arquivos estiverem em outro lugar.
"""
import glob
import os
import re

from faster_whisper import WhisperModel

PASTA = os.path.expanduser("~/Downloads")
PADRAO = "WhatsApp Audio 2026-07-15*.mp3"


def ordem_natural(caminho):
    """Ordena '17.07.36' antes de '17.07.36(2)' e numera os parênteses direito."""
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", caminho)]


arquivos = sorted(glob.glob(os.path.join(PASTA, PADRAO)), key=ordem_natural)
if not arquivos:
    raise SystemExit(f"Nenhum áudio encontrado em {PASTA!r} com o padrão {PADRAO!r}")

m = WhisperModel("small", device="cpu", compute_type="int8")

for caminho in arquivos:
    print(f"\n=== {os.path.basename(caminho)} ===")
    segs, _ = m.transcribe(caminho, language="pt")
    for s in segs:
        print(f"[{s.start:.1f}s] {s.text}")
