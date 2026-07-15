"""Índice de termos + suspects (PURO, testável) — o coração do caso de uso.

Emendas:
- E1: cada ocorrência carrega tempo local e global (quando há offset).
- E9: janela de contexto limitada à duração do arquivo; nota de cobertura explícita;
  detecção de suspects não depende de o Whisper preservar CAIXA-ALTA.
"""

from __future__ import annotations

import csv
import io
import re
from collections import Counter
from typing import Any, Optional

from .config import AtadoConfig
from .glossary import normalize, is_acronym_like
from .models import TranscriptDoc
from .timeutil import format_hms, to_global

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _effective_offset(doc: TranscriptDoc, cfg: AtadoConfig) -> Optional[float]:
    if doc.meta.source_start is not None:
        return doc.meta.source_start
    return cfg.source_start_for(doc.meta.source_file)


def _segments_in_window(doc: TranscriptDoc, center: float, window: float) -> str:
    """Texto dos segmentos que sobrepõem [center-w, center+w] no mesmo arquivo."""
    lo, hi = center - window, center + window
    parts = [s.text.strip() for s in doc.segments if s.end >= lo and s.start <= hi]
    return " ".join(p for p in parts if p).strip()


def _term_matches_in_segment(term: str, seg_text: str) -> bool:
    """Casamento whole-word, case/acento-insensível."""
    tnorm = normalize(term)
    if " " in term:
        return tnorm in normalize(seg_text)
    return tnorm in {normalize(tok) for tok in _WORD_RE.findall(seg_text)}


def _word_local_start(term: str, seg) -> float:
    """Timestamp da palavra do termo, se houver alinhamento; senão início do segmento."""
    tnorm = normalize(term)
    for w in seg.words:
        if normalize(w.word) == tnorm and w.start is not None:
            return float(w.start)
    return float(seg.start)


def find_occurrences(
    docs: list[TranscriptDoc],
    terms: list[tuple[str, Optional[str]]],
    cfg: AtadoConfig,
) -> dict[str, list[dict[str, Any]]]:
    """Para cada termo, todas as ocorrências (arquivo, tempo local/global, speaker, contexto)."""
    window = cfg.output.context_window_seconds
    index: dict[str, list[dict[str, Any]]] = {t: [] for t, _ in terms}
    for doc in docs:
        offset = _effective_offset(doc, cfg)
        for seg in doc.segments:
            for term, _meaning in terms:
                if _term_matches_in_segment(term, seg.text):
                    local = _word_local_start(term, seg)
                    index[term].append({
                        "term": term,
                        "file": doc.meta.source_file,
                        "local_start": local,
                        "global_start": to_global(offset, local),
                        "speaker": seg.speaker,
                        "context": _segments_in_window(doc, local, window),
                    })
    return index


def _fmt_time(occ: dict[str, Any]) -> str:
    if occ["global_start"] is not None:
        return f"{format_hms(occ['global_start'])} (local {format_hms(occ['local_start'])})"
    return format_hms(occ["local_start"])


def render_terms_markdown(
    index: dict[str, list[dict[str, Any]]],
    meanings: dict[str, Optional[str]],
    cfg: AtadoConfig,
    n_files: int,
) -> str:
    lines: list[str] = []
    lines.append(f"# {cfg.project} — índice de termos")
    lines.append("")
    lines.append(
        f"> ⚠️ Cobertura: este índice reflete apenas os **{n_files} recortes** fornecidos, "
        "não a gravação completa. Ocorrências fora dos recortes não aparecem."
    )
    lines.append("")
    for term, occs in index.items():
        n = len(occs)
        plural = "ocorrência" if n == 1 else "ocorrências"
        lines.append(f"## {term} — {n} {plural}")
        meaning = meanings.get(term)
        lines.append(f"significado (config): {meaning if meaning else '(desconhecido)'}")
        lines.append("")
        for occ in occs:
            who = occ["speaker"] or "?"
            ctx = occ["context"]
            lines.append(f'- {occ["file"]} @ {_fmt_time(occ)} — {who}: "{ctx}"')
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_terms_csv(
    index: dict[str, list[dict[str, Any]]],
    meanings: dict[str, Optional[str]],
) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["term", "meaning", "file", "global_time", "local_time", "speaker", "context"])
    for term, occs in index.items():
        meaning = meanings.get(term) or ""
        for occ in occs:
            gt = format_hms(occ["global_start"]) if occ["global_start"] is not None else ""
            w.writerow([
                term, meaning, occ["file"], gt,
                format_hms(occ["local_start"]), occ["speaker"] or "", occ["context"],
            ])
    return buf.getvalue()


def find_suspects(
    docs: list[TranscriptDoc],
    known_norms: set[str],
    wordlist: set[str],
    min_count: int = 2,
) -> list[dict[str, Any]]:
    """Candidatos a siglas/nomes mal transcritos NÃO no glossário (§8.1).

    Regra (E9): token fora da wordlist e do glossário, alfabético 2..15, com ≥ min_count
    ocorrências. Marca `acronym_like` (allcaps/caixa interna) para priorizar — sem depender
    de o Whisper preservar a caixa.
    """
    counter: Counter[str] = Counter()
    surface: dict[str, str] = {}
    example: dict[str, str] = {}
    acr: dict[str, bool] = {}

    for doc in docs:
        for seg in doc.segments:
            for tok in _WORD_RE.findall(seg.text):
                norm = normalize(tok)
                if not norm or norm in known_norms or norm in wordlist:
                    continue
                if not (2 <= len(norm) <= 15) or not norm.isalpha():
                    continue
                counter[norm] += 1
                surface.setdefault(norm, tok)
                example.setdefault(norm, seg.text.strip())
                acr[norm] = acr.get(norm, False) or is_acronym_like(tok)

    out = []
    for norm, count in counter.items():
        if count >= min_count:
            out.append({
                "token": surface[norm],
                "count": count,
                "acronym_like": acr[norm],
                "example": example[norm],
            })
    # prioriza siglas evidentes, depois frequência
    out.sort(key=lambda s: (not s["acronym_like"], -s["count"], s["token"].lower()))
    return out


def render_suspects_markdown(suspects: list[dict[str, Any]], project: str) -> str:
    lines = [f"# {project} — suspeitos (siglas/nomes prováveis fora do glossário)", ""]
    if not suspects:
        lines.append("_Nenhum suspeito encontrado._")
        return "\n".join(lines) + "\n"
    for s in suspects:
        flag = " (sigla?)" if s["acronym_like"] else ""
        lines.append(f'- **{s["token"]}** — {s["count"]}x{flag} — ex.: "{s["example"]}"')
    return "\n".join(lines).rstrip() + "\n"
