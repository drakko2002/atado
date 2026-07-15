"""Glossário: montagem do initial_prompt + passe de correção fuzzy (PURO, testável).

Emendas aplicadas (SPEC C):
- E2: scorer fixo (rapidfuzz.fuzz.ratio), casefold + remoção de acentos em ambos os
  operandos, detecção independente de CAIXA-ALTA (Whisper emite siglas em minúsculas),
  limiar ~80 configurável.
- E7: wordlist injetada como argumento (testes usam fixture pequena determinística).
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Iterable, Optional

from rapidfuzz import fuzz

from .config import Glossary

_WORD_RE = re.compile(r"\w+", re.UNICODE)
# sigla toda maiúscula: 2-8 letras (com acento) e/ou dígitos.
_ACRONYM_ALLCAPS = re.compile(r"^[A-ZÀ-Ý0-9]{2,8}$")


def normalize(token: str) -> str:
    """casefold + remoção de acentos — usado em lookup de wordlist e no fuzzy."""
    nfkd = unicodedata.normalize("NFKD", token)
    no_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    return no_accents.casefold().strip()


def is_acronym_like(token: str) -> bool:
    """Heurística de sigla/nome próprio (independe de o Whisper ter mantido a caixa)."""
    if _ACRONYM_ALLCAPS.match(token):
        return True
    # caixa "interna"/mista: maiúscula depois do 1º caractere + tem minúscula
    # (pega DSpace, iPhone, camelCase; ignora Titlecase comum como "Reunião").
    if len(token) >= 2 and any(c.isupper() for c in token[1:]) and any(c.islower() for c in token):
        return True
    return False


def load_wordlist(path: str | Path) -> set[str]:
    """Carrega a wordlist PT (normalizada). Ignora comentários e linhas vazias."""
    words: set[str] = set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        words.add(normalize(line))
    return words


def default_wordlist_path() -> Path:
    return Path(__file__).with_name("wordlist_pt.txt")


# ---------------------------------------------------------------- initial_prompt
def _estimate_tokens(text: str) -> int:
    """Estimativa barata de tokens (~4 chars/token). Documentado como aproximação (E9)."""
    return max(1, round(len(text) / 4))


def build_initial_prompt(glossary: Glossary, max_tokens: int = 200) -> str:
    """Monta o initial_prompt: contexto + lista de termos (com significados).

    Aliases NÃO entram (§4.1). Prioriza termos; trunca o contexto livre se estourar.
    """
    term_bits = []
    for t in glossary.terms:
        if t.meaning:
            term_bits.append(f"{t.term} ({t.meaning})")
        else:
            term_bits.append(t.term)
    terms_line = ""
    if term_bits:
        terms_line = "Siglas e nomes citados: " + ", ".join(term_bits) + "."

    context = " ".join((glossary.context or "").split())

    def assemble(ctx: str) -> str:
        parts = [p for p in (ctx.strip(), terms_line) if p]
        return " ".join(parts).strip()

    prompt = assemble(context)
    if _estimate_tokens(prompt) <= max_tokens:
        return prompt

    # Estourou: preservar a linha de termos e truncar o contexto por palavras.
    budget_for_ctx = max_tokens - _estimate_tokens(terms_line) - 1
    if budget_for_ctx <= 0:
        return terms_line
    words = context.split()
    truncated = ""
    for w in words:
        candidate = (truncated + " " + w).strip()
        if _estimate_tokens(candidate) > budget_for_ctx:
            break
        truncated = candidate
    return assemble(truncated)


# ---------------------------------------------------------------- passe de correção
def _candidate_index(glossary: Glossary) -> list[tuple[str, str]]:
    """Lista (forma_normalizada, canônico) para cada termo e alias."""
    idx: list[tuple[str, str]] = []
    for t in glossary.terms:
        canonical = t.term
        for surface in [t.term, *t.aliases]:
            idx.append((normalize(surface), canonical))
    return idx


def apply_corrections(
    text: str,
    glossary: Glossary,
    wordlist: Iterable[str],
    threshold: int = 80,
) -> tuple[str, list[tuple[str, str]]]:
    """Corrige tokens fora da wordlist que casam (fuzzy) com um termo/alias do glossário.

    Retorna (texto_corrigido, [(token_original, canônico), ...]).
    Nunca toca palavras da wordlist (comuns do PT). Tokens já na grafia canônica não
    são contados como substituição.
    """
    wl = set(wordlist)
    candidates = _candidate_index(glossary)
    canon_norms = {normalize(t.term): t.term for t in glossary.terms}
    subs: list[tuple[str, str]] = []

    def repl(match: re.Match) -> str:
        token = match.group(0)
        norm = normalize(token)
        if not norm:
            return token
        # nunca corrigir palavras comuns
        if norm in wl:
            return token
        # já é a grafia canônica de algum termo -> não conta como substituição
        if norm in canon_norms:
            return canon_norms[norm]
        best_score = -1.0
        best_canon: Optional[str] = None
        for cand_norm, canonical in candidates:
            score = fuzz.ratio(norm, cand_norm)
            if score > best_score:
                best_score = score
                best_canon = canonical
        if best_canon is not None and best_score >= threshold:
            subs.append((token, best_canon))
            return best_canon
        return token

    corrected = _WORD_RE.sub(repl, text)
    return corrected, subs
