"""Casca fina do WhisperX (transcribe/align/diarize) — import tardio de torch/whisperx.

Seam injetável: `pipeline.py` recebe uma função `transcribe_fn`; em produção é
`whisperx_transcribe`, em teste é um fake. Assim o wiring é testado sem GPU (E4/E10).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from .models import Segment, TranscriptDoc, TranscriptMeta, Word

# cache de modelos carregados (evita recarregar por arquivo)
_MODEL_CACHE: dict = {}
_ALIGN_CACHE: dict = {}


def _prepare_cuda_libs() -> None:
    """Pré-carrega as libs CUDA do torch para o CTranslate2 encontrar cuDNN/cuBLAS na GPU.

    Nota: mutar LD_LIBRARY_PATH em runtime NÃO afeta o processo atual (o ld.so já resolveu
    os paths no startup); serve só para subprocessos. O mecanismo que de fato funciona é
    importar torch ANTES do CTranslate2 usar a GPU — torch carrega sua cuDNN 9 no processo,
    e o CT2 reaproveita esses símbolos. Fazemos isso explicitamente aqui.
    """
    try:
        import torch  # noqa: F401 — pré-carrega cuDNN/cuBLAS no processo
    except Exception:
        pass
    try:
        import site
        roots = [Path(p) for p in site.getsitepackages()] + [Path(sys.prefix) / "lib"]
        libdirs = []
        for root in roots:
            nv = root / "nvidia"
            if nv.is_dir():
                for pkg in ("cudnn", "cublas"):
                    d = nv / pkg / "lib"
                    if d.is_dir():
                        libdirs.append(str(d))
        if libdirs:  # best-effort para subprocessos
            cur = os.environ.get("LD_LIBRARY_PATH", "")
            parts = [d for d in libdirs if d not in cur.split(":")]
            if parts:
                os.environ["LD_LIBRARY_PATH"] = ":".join(parts + ([cur] if cur else []))
    except Exception:
        pass


def map_asr_error(exc: Exception) -> str:
    """Traduz erros comuns de GPU/ASR em mensagens instrutivas (E10)."""
    msg = str(exc)
    if "libcudnn_ops_infer.so.8" in msg or "libcudnn" in msg and ".so.8" in msg:
        return ("Incompatibilidade cuDNN: CTranslate2 espera cuDNN 8, mas o sistema tem 9. "
                "Use ctranslate2>=4.5 (feito na matriz do atado) ou instale nvidia-cudnn-cu12.")
    if "out of memory" in msg.lower() or "CUDA out of memory" in msg:
        return ("VRAM insuficiente. Use --compute-type int8 e/ou --model medium, "
                "ou reduza o batch_size.")
    if "CUDA" in msg and "no kernel image" in msg.lower():
        return "Wheel do torch incompatível com a GPU/CUDA. Reinstale torch para seu CUDA."
    return msg


def _load_model(model_name: str, device: str, compute_type: str, language: str,
                initial_prompt: Optional[str]):
    key = (model_name, device, compute_type, language)
    if key not in _MODEL_CACHE:
        import whisperx  # lazy
        # Opções anti-alucinação: em áudio longo o large-v3 entra em loops de repetição.
        # condition_on_previous_text=False corta a cascata; no_repeat_ngram evita n-gramas
        # repetidos; repetition_penalty desincentiva loops.
        asr_options = {
            "condition_on_previous_text": False,
            "no_repeat_ngram_size": 3,
            "repetition_penalty": 1.15,
        }
        if initial_prompt:
            asr_options["initial_prompt"] = initial_prompt
        _MODEL_CACHE[key] = whisperx.load_model(
            model_name, device, compute_type=compute_type, language=language,
            asr_options=asr_options,
        )
    return _MODEL_CACHE[key]


def _load_align(language: str, device: str):
    if language not in _ALIGN_CACHE:
        import whisperx  # lazy
        _ALIGN_CACHE[language] = whisperx.load_align_model(language_code=language, device=device)
    return _ALIGN_CACHE[language]


def whisperx_transcribe(
    wav_path: str | Path,
    *,
    source_file: str,
    model: str,
    device: str,
    compute_type: str,
    language: str,
    initial_prompt: Optional[str] = None,
    batch_size: int = 8,
    align: bool = True,
    duration: float = 0.0,
    source_start: Optional[float] = None,
    atado_version: str = "0.1.0",
) -> TranscriptDoc:
    """Transcreve (e alinha) um WAV → TranscriptDoc (sem diarização)."""
    _prepare_cuda_libs()
    import whisperx  # lazy

    audio = whisperx.load_audio(str(wav_path))
    mdl = _load_model(model, device, compute_type, language, initial_prompt)
    # NÃO faz retry no mesmo processo: um OOM de CUDA envenena o contexto (erros sticky),
    # então a única cura é usar um batch_size que caiba de início (derivado da VRAM).
    result = mdl.transcribe(audio, batch_size=batch_size)
    segments = result.get("segments", [])

    if align and segments:
        try:
            model_a, metadata = _load_align(language, device)
            result = whisperx.align(segments, model_a, metadata, audio, device,
                                    return_char_alignments=False)
            segments = result.get("segments", segments)
        except Exception:
            pass  # sem alinhamento: mantém segmentos sem words

    segs: list[Segment] = []
    for s in segments:
        words = []
        for w in s.get("words", []) or []:
            words.append(Word(
                word=w.get("word", ""),
                start=w.get("start"),
                end=w.get("end"),
                score=w.get("score"),
                speaker=w.get("speaker"),
            ))
        segs.append(Segment(
            start=float(s.get("start", 0.0)),
            end=float(s.get("end", s.get("start", 0.0))),
            text=(s.get("text") or "").strip(),
            speaker=s.get("speaker"),
            words=words,
        ))

    meta = TranscriptMeta(
        source_file=source_file, duration=duration, model=model, language=language,
        diarized=False, atado_version=atado_version, source_start=source_start,
        extra={"device": device, "compute_type": compute_type},
    )
    return TranscriptDoc(meta=meta, segments=segs)
