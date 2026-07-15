"""Diarização via pyannote (F3). Casca fina + atribuição de falante PURA/testável.

pyannote 4.x usa a pipeline community-1; carregamos o áudio em memória (waveform) para
contornar o torchcodec quebrado com ffmpeg 8. Falhas viram mensagens instrutivas —
diarização é sempre OPCIONAL (§13.2), o caminho --no-diarize permanece intacto.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .models import TranscriptDoc

# pipelines pyannote a tentar, em ordem
_PIPELINES = ["pyannote/speaker-diarization-3.1", "pyannote/speaker-diarization-community-1"]


def assign_speakers_by_overlap(segments: list, turns: list[tuple[float, float, str]]) -> None:
    """Atribui a cada segmento o falante do turno com maior sobreposição temporal (in-place).

    `turns` = [(start, end, speaker), ...]. Segmentos sem sobreposição ficam sem speaker.
    """
    for seg in segments:
        best_overlap = 0.0
        best_spk: Optional[str] = None
        for t_start, t_end, spk in turns:
            overlap = min(seg.end, t_end) - max(seg.start, t_start)
            if overlap > best_overlap:
                best_overlap = overlap
                best_spk = spk
        if best_spk is not None:
            seg.speaker = best_spk
            for w in seg.words:
                w.speaker = best_spk


class DiarizationError(RuntimeError):
    pass


def _load_pipeline(hf_token: str, device: str):
    from pyannote.audio import Pipeline  # lazy
    import torch

    last_err = None
    for name in _PIPELINES:
        # pyannote 4.x usa token=; <4 usa use_auth_token=. Tenta ambos.
        for kwargs in ({"token": hf_token}, {"use_auth_token": hf_token}):
            try:
                pipe = Pipeline.from_pretrained(name, **kwargs)
            except TypeError:
                continue  # kwarg incompatível com esta versão do pyannote
            except Exception as e:
                last_err = e
                break  # kwarg certo, mas outro erro (ex.: 401) — não tenta o outro kwarg
            if pipe is None:
                last_err = DiarizationError(f"pyannote retornou None para {name} (licença?).")
                break
            try:
                pipe.to(torch.device(device))
            except Exception:
                pass
            return pipe

    msg = str(last_err) if last_err else ""
    if any(k in msg.lower() for k in ("401", "gated", "restricted", "unauthorized")):
        raise DiarizationError(
            "Acesso negado (401) aos modelos de diarização do pyannote. Verifique:\n"
            "  1) aceite as licenças de pyannote/speaker-diarization-3.1 E "
            "pyannote/segmentation-3.0 (e/ou speaker-diarization-community-1) na sua conta HF;\n"
            "  2) o HF_TOKEN precisa de leitura de repositórios 'gated' — em tokens fine-grained,\n"
            "     marque 'Read access to contents of all public gated repos you can access'.\n"
            f"Detalhe: {msg[:200]}"
        )
    raise DiarizationError(
        "Não foi possível carregar a diarização do pyannote. "
        f"Verifique HF_TOKEN e as licenças. Erro: {msg[:300]}"
    )


def diarize_doc(
    doc: TranscriptDoc,
    wav_path: str | Path,
    *,
    hf_token: Optional[str],
    min_speakers: Optional[int] = None,
    max_speakers: Optional[int] = None,
    device: str = "cuda",
) -> TranscriptDoc:
    """Adiciona speakers ao doc via pyannote. Levanta DiarizationError em falha."""
    if not hf_token:
        raise DiarizationError(
            "HF_TOKEN ausente — necessário para diarização (pyannote). "
            "Defina no .env ou use --no-diarize."
        )
    import numpy as np
    import torch
    import whisperx

    from .asr import _prepare_cuda_libs
    _prepare_cuda_libs()

    audio = whisperx.load_audio(str(wav_path))  # float32 mono 16k (via ffmpeg, sem torchcodec)
    waveform = torch.from_numpy(np.ascontiguousarray(audio)).unsqueeze(0)

    pipe = _load_pipeline(hf_token, device)
    kwargs = {}
    if min_speakers is not None:
        kwargs["min_speakers"] = min_speakers
    if max_speakers is not None:
        kwargs["max_speakers"] = max_speakers

    diarization = pipe({"waveform": waveform, "sample_rate": 16000}, **kwargs)

    turns: list[tuple[float, float, str]] = []
    for turn, _track, speaker in diarization.itertracks(yield_label=True):
        turns.append((float(turn.start), float(turn.end), str(speaker)))

    assign_speakers_by_overlap(doc.segments, turns)
    doc.meta.diarized = True
    n_speakers = len({t[2] for t in turns})
    doc.meta.extra["n_speakers"] = n_speakers
    return doc
