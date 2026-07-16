"""Chunking de arquivos longos (SPEC D, D1) — PURO/testável.

- `plan_chunks`: divide [0, duração] em janelas de `chunk_length` com `chunk_overlap`,
  ajustando (snap) a fronteira ao silêncio mais próximo quando disponível.
- `merge_chunks`: reconstrói os segmentos do arquivo a partir dos transcripts dos chunks,
  deslocando por `offset` e removendo duplicatas na região de sobreposição.
"""

from __future__ import annotations

from typing import NamedTuple, Optional

from .glossary import normalize
from .models import Segment, TranscriptDoc, Word


class Chunk(NamedTuple):
    index: int
    start: float   # início no tempo do ARQUIVO
    end: float     # fim no tempo do arquivo

    @property
    def offset(self) -> float:
        return self.start

    @property
    def length(self) -> float:
        return self.end - self.start


def plan_chunks(
    duration: float,
    chunk_length: float,
    chunk_overlap: float,
    silences: Optional[list[float]] = None,
    silence_snap: float = 30.0,
) -> list[Chunk]:
    """Planeja os blocos que cobrem [0, duration]. Arquivo curto → 1 bloco."""
    if duration <= chunk_length:
        return [Chunk(0, 0.0, duration)]

    chunks: list[Chunk] = []
    start = 0.0
    idx = 0
    while start < duration - 1e-6:
        target_end = min(start + chunk_length, duration)
        end = target_end
        if silences and target_end < duration:
            near = [s for s in silences if abs(s - target_end) <= silence_snap and s > start]
            if near:
                end = min(near, key=lambda s: abs(s - target_end))
        chunks.append(Chunk(idx, start, end))
        if end >= duration - 1e-6:
            break
        start = max(end - chunk_overlap, start + 1.0)
        idx += 1
    return chunks


def _shift_segment(seg: Segment, offset: float) -> Segment:
    return Segment(
        start=seg.start + offset,
        end=seg.end + offset,
        text=seg.text,
        speaker=seg.speaker,
        words=[Word(word=w.word,
                    start=(w.start + offset) if w.start is not None else None,
                    end=(w.end + offset) if w.end is not None else None,
                    score=w.score, speaker=w.speaker) for w in seg.words],
    )


def merge_chunks(chunks: list[Chunk], docs: list[TranscriptDoc]) -> list[Segment]:
    """Reconstrói os segmentos do arquivo (tempo local-do-arquivo), sem duplicatas.

    Cada segmento é atribuído ao chunk cuja janela [corte_anterior, corte_posterior] contém
    seu centro (o corte entre chunks i e i+1 é o ponto médio da sobreposição). Uma passada
    final remove duplicatas quase-idênticas remanescentes na fronteira.
    """
    assert len(chunks) == len(docs), "chunks e docs devem ter o mesmo tamanho"
    n = len(chunks)

    def cut_after(i: int) -> float:
        if i >= n - 1:
            return float("inf")
        return (chunks[i].end + chunks[i + 1].start) / 2.0

    def cut_before(i: int) -> float:
        if i == 0:
            return float("-inf")
        return (chunks[i - 1].end + chunks[i].start) / 2.0

    merged: list[Segment] = []
    for i, (ch, doc) in enumerate(zip(chunks, docs)):
        lo, hi = cut_before(i), cut_after(i)
        for seg in doc.segments:
            s = _shift_segment(seg, ch.offset)
            center = (s.start + s.end) / 2.0
            if lo <= center < hi:
                merged.append(s)

    merged.sort(key=lambda s: (s.start, s.end))

    # passada final: remove duplicata de FRONTEIRA — segmentos de chunks vizinhos que
    # cobrem o MESMO trecho (sobreposição temporal significativa) com texto parecido.
    # Fala legítima repetida tem tempos DISJUNTOS, então não é afetada.
    from rapidfuzz import fuzz
    deduped: list[Segment] = []
    for s in merged:
        drop = False
        for prev in reversed(deduped[-4:]):
            if prev.end <= s.start:  # sem sobreposição temporal → não é dup de fronteira
                continue
            overlap = min(prev.end, s.end) - max(prev.start, s.start)
            shorter = min(prev.end - prev.start, s.end - s.start) or 1e-9
            na, nb = normalize(prev.text), normalize(s.text)
            if overlap / shorter > 0.5 and na and nb and (
                    fuzz.ratio(na, nb) >= 80 or nb in na or na in nb):
                drop = True
                break
        if not drop:
            deduped.append(s)
    return deduped
