"""Confiança da transcrição (PURO) — valida acurácia sem assistir à reunião (Q6/SPEC D).

Usa os scores de palavra do alinhamento (WhisperX) para sinalizar os trechos de BAIXA
confiança: o usuário revisa só esses (minutos), não a reunião toda. É a resposta prática
ao "como sei que está certo sem assistir".
"""

from __future__ import annotations

from typing import Any, Optional

from .config import AtadoConfig
from .models import Segment, TranscriptDoc
from .timeutil import format_hms, to_global


def segment_confidence(seg: Segment) -> Optional[float]:
    """Confiança média das palavras do segmento (None se não há scores)."""
    scores = [w.score for w in seg.words if w.score is not None]
    if not scores:
        return None
    return sum(scores) / len(scores)


def overall_confidence(docs: list[TranscriptDoc]) -> Optional[float]:
    vals = [c for d in docs for s in d.segments if (c := segment_confidence(s)) is not None]
    return sum(vals) / len(vals) if vals else None


def _effective_offset(doc: TranscriptDoc, cfg: Optional[AtadoConfig]) -> Optional[float]:
    if doc.meta.source_start is not None:
        return doc.meta.source_start
    if cfg is not None:
        return cfg.source_start_for(doc.meta.source_file)
    return None


def low_confidence_segments(
    docs: list[TranscriptDoc],
    threshold: float = 0.55,
    max_items: int = 40,
    cfg: Optional[AtadoConfig] = None,
) -> list[dict[str, Any]]:
    """Segmentos com confiança < threshold, ordenados do pior para o melhor."""
    flagged: list[dict[str, Any]] = []
    for doc in docs:
        offset = _effective_offset(doc, cfg)
        for seg in doc.segments:
            c = segment_confidence(seg)
            if c is not None and c < threshold and seg.text.strip():
                flagged.append({
                    "file": doc.meta.source_file,
                    "local_start": seg.start,
                    "global_start": to_global(offset, seg.start),
                    "speaker": seg.speaker,
                    "confidence": c,
                    "text": seg.text.strip(),
                })
    flagged.sort(key=lambda f: f["confidence"])
    return flagged[:max_items]


def render_confidence_markdown(
    docs: list[TranscriptDoc],
    cfg: AtadoConfig,
    threshold: float = 0.55,
    max_items: int = 40,
) -> str:
    overall = overall_confidence(docs)
    flagged = low_confidence_segments(docs, threshold=threshold, max_items=max_items, cfg=cfg)
    lines = [f"# {cfg.project} — confiança da transcrição", ""]
    if overall is not None:
        lines.append(f"- Confiança média geral: **{overall*100:.0f}%**")
    lines.append(f"- Trechos abaixo de {threshold*100:.0f}% (revisar): **{len(flagged)}**")
    lines.append("")
    lines.append("> Revise só estes trechos para validar a transcrição sem assistir à reunião toda.")
    lines.append("")
    if not flagged:
        lines.append("_Nenhum trecho de baixa confiança._")
        return "\n".join(lines) + "\n"
    for f in flagged:
        t = format_hms(f["global_start"]) if f["global_start"] is not None else format_hms(f["local_start"])
        who = f" {f['speaker']}" if f["speaker"] else ""
        lines.append(f'- **{f["confidence"]*100:.0f}%** — {f["file"]} @ {t}{who}: "{f["text"]}"')
    return "\n".join(lines).rstrip() + "\n"
