"""Contrato de dados do transcript (E3) — fonte única para asr/merge/terms/kit.

`speaker` é opcional em todo o pipeline (suporta `--no-diarize`).
As fixtures de teste e a saída real de `asr.py` DEVEM validar contra estes modelos.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Word(BaseModel):
    """Palavra alinhada (word timestamps do WhisperX)."""

    model_config = ConfigDict(extra="ignore")

    word: str
    start: Optional[float] = None
    end: Optional[float] = None
    score: Optional[float] = None
    speaker: Optional[str] = None


class Segment(BaseModel):
    """Segmento de fala: {start, end, speaker?, text, words[]}."""

    model_config = ConfigDict(extra="ignore")

    start: float
    end: float
    text: str = ""
    speaker: Optional[str] = None
    words: list[Word] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_order(self) -> "Segment":
        if self.end < self.start:
            raise ValueError(f"end ({self.end}) < start ({self.start})")
        return self


class TranscriptMeta(BaseModel):
    """Metadados por arquivo transcrito."""

    model_config = ConfigDict(extra="ignore")

    source_file: str
    duration: float
    model: str
    language: str
    diarized: bool = False
    atado_version: str = "0.1.0"
    # Offset da posição do recorte na gravação-mãe (E1). None = desconhecido.
    source_start: Optional[float] = None
    # Metadados livres adicionais (hardware, tempo, etc.)
    extra: dict[str, Any] = Field(default_factory=dict)


class TranscriptDoc(BaseModel):
    """Documento de transcript por arquivo."""

    model_config = ConfigDict(extra="ignore")

    meta: TranscriptMeta
    segments: list[Segment] = Field(default_factory=list)

    def compact_dict(self) -> dict[str, Any]:
        """Versão compacta (sem words[]) para consolidated.json (SPEC A §7)."""
        return {
            "meta": self.meta.model_dump(),
            "segments": [
                {
                    "start": s.start,
                    "end": s.end,
                    "speaker": s.speaker,
                    "text": s.text,
                }
                for s in self.segments
            ],
        }
