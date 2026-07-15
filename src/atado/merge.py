"""Consolidação de transcripts (PURO, testável).

Emendas:
- E1: emite timestamps LOCAL e, quando há offset, GLOBAL reconstruído do encontro.
- E10: natural-sort que trata o padrão do WhatsApp ("...36.mp3" antes de "...36(1).mp3");
  ordenação por offset quando disponível; nunca rotula name/mtime como cronológico.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from .config import AtadoConfig
from .models import TranscriptDoc
from .timeutil import format_hms, to_global

_TOKEN_RE = re.compile(r"\d+|\D+")
_DUP_RE = re.compile(r"\((\d+)\)$")


def natural_key(name: str) -> tuple:
    """Chave de ordenação natural robusta ao padrão do WhatsApp.

    - Remove a extensão.
    - Detecta sufixo de duplicata "(N)" (base sem sufixo vem antes de (1), (2)...).
    - Tokeniza em runs numéricos/alfabéticos, comparando números como inteiros.
    """
    stem = name.rsplit(".", 1)[0]
    dup = 0
    m = _DUP_RE.search(stem)
    if m:
        dup = int(m.group(1))
        stem = stem[: m.start()]
    tokens = []
    for tok in _TOKEN_RE.findall(stem):
        if tok.isdigit():
            tokens.append((0, int(tok), ""))
        else:
            tokens.append((1, 0, tok))
    return (tuple(tokens), dup)


def _effective_offset(doc: TranscriptDoc, cfg: AtadoConfig) -> Optional[float]:
    if doc.meta.source_start is not None:
        return doc.meta.source_start
    return cfg.source_start_for(doc.meta.source_file)


def order_docs(
    docs: list[TranscriptDoc],
    cfg: AtadoConfig,
    mtimes: Optional[dict[str, float]] = None,
) -> list[TranscriptDoc]:
    """Ordena os docs conforme cfg.order. mtimes injetado como dado (mantém pureza)."""
    order = cfg.order
    if order == "name":
        return sorted(docs, key=lambda d: natural_key(d.meta.source_file))
    if order == "mtime":
        mt = mtimes or {}
        return sorted(docs, key=lambda d: (mt.get(d.meta.source_file, 0.0),
                                           natural_key(d.meta.source_file)))
    if order == "manual":
        pos = {name: i for i, name in enumerate(cfg.manual_order)}
        return sorted(
            docs,
            key=lambda d: (pos.get(d.meta.source_file, len(pos)),
                           natural_key(d.meta.source_file)),
        )
    if order == "offset":
        INF = float("inf")
        return sorted(
            docs,
            key=lambda d: (
                _effective_offset(d, cfg) if _effective_offset(d, cfg) is not None else INF,
                natural_key(d.meta.source_file),
            ),
        )
    return list(docs)


def _fmt_ref(local: float, offset: Optional[float]) -> str:
    """'[08:03 (00:03)]' quando há offset; '[00:03]' quando só local."""
    g = to_global(offset, local)
    if g is None:
        return f"[{format_hms(local)}]"
    return f"[{format_hms(g)} ({format_hms(local)})]"


def _speakers_in(doc: TranscriptDoc) -> list[str]:
    seen = []
    for s in doc.segments:
        if s.speaker and s.speaker not in seen:
            seen.append(s.speaker)
    return seen


def consolidate_markdown(docs: list[TranscriptDoc], cfg: AtadoConfig) -> str:
    """Corpus legível: sumário + transcripts em sequência, refs local(+global)."""
    ordered = order_docs(docs, cfg)
    total_dur = sum(d.meta.duration for d in ordered)
    has_offsets = any(_effective_offset(d, cfg) is not None for d in ordered)

    lines: list[str] = []
    lines.append(f"# {cfg.project} — corpus consolidado")
    lines.append("")
    lines.append(f"- Áudios: {len(ordered)}")
    lines.append(f"- Duração total (dos recortes): {format_hms(total_dur)}")
    speakers_note = ", ".join(
        f"{d.meta.source_file}: {len(_speakers_in(d))}" for d in ordered
    ) or "—"
    lines.append(f"- Falantes por arquivo: {speakers_note}")
    if not has_offsets and cfg.order in ("name", "mtime"):
        lines.append(
            f"- ⚠️ Ordem `{cfg.order}` NÃO é cronológica do encontro "
            "(sem offsets configurados; ver `files[].source_start`)."
        )
    lines.append("")

    for d in ordered:
        offset = _effective_offset(d, cfg)
        dur = format_hms(d.meta.duration)
        head = f"## {d.meta.source_file} (duração {dur}"
        if offset is not None:
            head += f", início no encontro {format_hms(offset)}"
        head += ")"
        lines.append(head)
        lines.append("")
        for s in d.segments:
            ref = _fmt_ref(s.start, offset)
            who = f" {s.speaker}:" if s.speaker else ""
            lines.append(f"{ref}{who} {s.text.strip()}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def consolidate_json(docs: list[TranscriptDoc], cfg: AtadoConfig) -> dict[str, Any]:
    """Estrutura compacta machine-readable (sem words[]), com global_start quando há offset."""
    ordered = order_docs(docs, cfg)
    files_out = []
    for d in ordered:
        offset = _effective_offset(d, cfg)
        segs = []
        for s in d.segments:
            entry = {
                "start": s.start,
                "end": s.end,
                "speaker": s.speaker,
                "text": s.text,
            }
            g = to_global(offset, s.start)
            if g is not None:
                entry["global_start"] = g
            segs.append(entry)
        files_out.append({
            "source_file": d.meta.source_file,
            "duration": d.meta.duration,
            "source_start": offset,
            "speakers": _speakers_in(d),
            "segments": segs,
        })
    return {
        "project": cfg.project,
        "n_files": len(ordered),
        "total_duration": sum(d.meta.duration for d in ordered),
        "has_global_timeline": any(f["source_start"] is not None for f in files_out),
        "files": files_out,
    }
