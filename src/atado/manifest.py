"""Cache/manifest de transcrição (E10) — PURO/testável, escrita atômica.

Reprocessa quando QUALQUER campo que afeta a transcrição muda (não só com --force):
hash do input, modelo, idioma, flag de diarização, e hash do glossário
(initial_prompt + aliases da correção). Status != "ok" também força reprocesso.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Optional

from .config import AtadoConfig
from .glossary import build_initial_prompt


def file_input_hash(path: str | Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def transcription_signature(cfg: AtadoConfig, model: str, language: str, diarize: bool) -> str:
    """Assinatura dos parâmetros que afetam o resultado da transcrição."""
    glossary_repr = {
        "initial_prompt": build_initial_prompt(cfg.glossary),
        "aliases": sorted(
            (t.term, tuple(sorted(t.aliases))) for t in cfg.glossary.terms
        ),
        "correction_threshold": cfg.correction.threshold,
        "correction_enabled": cfg.correction.enabled,
    }
    payload = {
        "model": model,
        "language": language,
        "diarize": bool(diarize),
        "glossary": glossary_repr,
    }
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


class Manifest:
    def __init__(self, entries: Optional[dict[str, Any]] = None):
        self.entries: dict[str, Any] = entries or {}

    @classmethod
    def load(cls, path: str | Path) -> "Manifest":
        p = Path(path)
        if not p.exists():
            return cls({})
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls({})
        return cls(data.get("files", {}))

    def needs_processing(self, filename: str, input_hash: str, signature: str) -> bool:
        e = self.entries.get(filename)
        if e is None:
            return True
        if e.get("status") != "ok":
            return True
        return e.get("input_hash") != input_hash or e.get("signature") != signature

    def record(
        self,
        filename: str,
        input_hash: str,
        signature: str,
        outputs: list[str],
        status: str,
        error: Optional[str] = None,
        atado_version: str = "0.1.0",
    ) -> None:
        self.entries[filename] = {
            "input_hash": input_hash,
            "signature": signature,
            "outputs": outputs,
            "status": status,
            "error": error,
            "atado_version": atado_version,
        }

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(
            json.dumps({"files": self.entries}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, p)  # escrita atômica
