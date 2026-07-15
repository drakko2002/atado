"""Parser tolerante da saída do agente + import seguro no atado.yaml (E5/E6).

Fonte ÚNICA das sentinelas de bloco (E5): usada pelo protocolo (F6, few-shot) e por
este parser (F7), impedindo drift.

Segurança (E6): todo campo importado passa por `validate_field` (rejeita tags YAML,
quebras de linha e caracteres de controle, limita tamanho) ANTES de tocar o config.
O import opera sobre um CommentedMap (ruamel), preservando comentários/ordem.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

# --- E5: sentinelas canônicas (uma única definição) -------------------------
SENTINELS = {
    "tabela": "TABELA_RESOLVIDA",
    "narrativa": "NARRATIVA",
    "pendencias": "PENDENCIAS",
}
HEADING_PREFIX = "## "  # nível canônico dos blocos no protocolo

_MAX_FIELD = 500
_YAML_TAG = re.compile(r"(^|\s)!!?[\w./:]+")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

# aceita ## ou ### e PENDENCIAS/PENDÊNCIAS (tolerante)
_HEADING_RE = re.compile(
    r"^#{2,3}\s*(TABELA_RESOLVIDA|NARRATIVA|PEND[EÊ]NCIAS)\b.*$",
    re.IGNORECASE | re.MULTILINE,
)


def _strip_accents(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def validate_field(value: str) -> str:
    """Valida e devolve um campo importado (E6). Levanta ValueError se suspeito."""
    if value is None:
        return ""
    v = str(value).strip()
    if len(v) > _MAX_FIELD:
        raise ValueError(f"campo muito longo ({len(v)} > {_MAX_FIELD}): {v[:40]!r}...")
    if "\n" in v or "\r" in v or _CONTROL.search(v):
        raise ValueError(f"campo com quebra de linha/controle não permitido: {v[:40]!r}")
    if _YAML_TAG.search(v):
        raise ValueError(f"campo com tag YAML não permitido (possível injeção): {v[:40]!r}")
    return v


def _block_key(raw_heading: str) -> str:
    h = _strip_accents(raw_heading).upper()
    if "TABELA_RESOLVIDA" in h:
        return "tabela"
    if "NARRATIVA" in h:
        return "narrativa"
    if "PENDENCIAS" in h:
        return "pendencias"
    return ""


def _split_blocks(text: str) -> dict[str, str]:
    """Divide o texto em blocos pelos cabeçalhos-sentinela."""
    matches = list(_HEADING_RE.finditer(text))
    blocks: dict[str, str] = {}
    for i, m in enumerate(matches):
        key = _block_key(m.group(0))
        if not key:
            continue
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        blocks[key] = text[start:end].strip()
    return blocks


def _parse_table(block: str) -> list[dict[str, Any]]:
    """Parseia uma tabela markdown por NOME de coluna (tolerante a ordem/extras)."""
    rows_raw = [ln for ln in block.splitlines() if ln.strip().startswith("|")]
    if len(rows_raw) < 2:
        return []

    def cells(line: str) -> list[str]:
        parts = line.strip().strip("|").split("|")
        return [c.strip() for c in parts]

    header = [_strip_accents(h).lower() for h in cells(rows_raw[0])]

    def col_index(*names: str) -> int:
        for n in names:
            if n in header:
                return header.index(n)
        return -1

    i_sigla = col_index("sigla", "termo", "term")
    i_signif = col_index("significado", "meaning")
    i_conf = col_index("confianca", "confidence")
    i_prov = col_index("proveniencia", "provenance", "fonte")
    i_alias = col_index("variantes/aliases", "aliases", "variantes", "alias")

    out: list[dict[str, Any]] = []
    for line in rows_raw[1:]:
        c = cells(line)
        # pula a linha separadora (---|---)
        if all(set(x) <= set("-: ") for x in c):
            continue
        if i_sigla < 0 or i_sigla >= len(c) or not c[i_sigla]:
            continue

        def get(idx: int) -> str:
            return c[idx] if 0 <= idx < len(c) else ""

        aliases_raw = get(i_alias)
        aliases = [a.strip() for a in re.split(r"[,;/]", aliases_raw) if a.strip()] if aliases_raw else []
        out.append({
            "sigla": validate_field(c[i_sigla]),
            "significado": validate_field(get(i_signif)),
            "confianca": validate_field(get(i_conf)),
            "proveniencia": validate_field(get(i_prov)),
            "aliases": [validate_field(a) for a in aliases],
        })
    return out


def parse_agent_output(text: str) -> dict[str, Any]:
    """Extrai {tabela, narrativa, pendencias} da saída do agente. Tolerante ao formato."""
    blocks = _split_blocks(text)
    if "tabela" not in blocks:
        raise ValueError(
            "Bloco TABELA_RESOLVIDA não encontrado. Verifique se a saída do agente "
            "contém o cabeçalho '## TABELA_RESOLVIDA' com a tabela markdown."
        )
    return {
        "tabela": _parse_table(blocks["tabela"]),
        "narrativa": blocks.get("narrativa", "").strip(),
        "pendencias": blocks.get("pendencias", "").strip(),
    }


# ------------------------------------------------------------------ import
def _norm(s: str) -> str:
    return _strip_accents(str(s)).casefold().strip()


def import_into_config(cfg_map: Any, parsed: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    """Aplica a TABELA_RESOLVIDA a um CommentedMap (ruamel), preservando comentários.

    Retorna (cfg_map_atualizado, resumo). Atualiza meaning/aliases de termos existentes
    e adiciona novos termos. Não persiste NARRATIVA/PENDENCIAS aqui (isso é feito à parte).
    """
    glossary = cfg_map.get("glossary")
    if glossary is None:
        glossary = {}
        cfg_map["glossary"] = glossary
    terms = glossary.get("terms")
    if terms is None:
        terms = []
        glossary["terms"] = terms

    by_norm: dict[str, Any] = {}
    for entry in terms:
        if isinstance(entry, dict) and entry.get("term"):
            by_norm[_norm(entry["term"])] = entry

    summary = {"updated": [], "added": [], "aliases_added": []}

    for row in parsed["tabela"]:
        sigla = row["sigla"]
        if not sigla:
            continue
        meaning = row["significado"] or None
        aliases = row.get("aliases", [])
        key = _norm(sigla)

        if key in by_norm:
            entry = by_norm[key]
            if meaning:
                entry["meaning"] = meaning
                summary["updated"].append(sigla)
            if aliases:
                existing = entry.get("aliases") or []
                existing_norm = {_norm(a) for a in existing}
                for a in aliases:
                    if _norm(a) not in existing_norm and _norm(a) != key:
                        existing.append(a)
                        summary["aliases_added"].append((sigla, a))
                entry["aliases"] = existing
        else:
            new_entry = {"term": sigla, "meaning": meaning, "aliases": list(aliases)}
            terms.append(new_entry)
            by_norm[key] = new_entry
            summary["added"].append(sigla)

    return cfg_map, summary
