"""Redação de PII best-effort (E8/F8) — PURO, testável.

Substitui padrões de PII (e-mail, CPF, telefone BR) por placeholders estáveis
`[[PII-N]]`. Mesmo valor -> mesmo placeholder. O mapa reverso (placeholder->original)
NUNCA é incluído no kit; é gravado em work/redaction_map.json (modo 0600) pelo chamador.

Limitação declarada: regex sobre fala transcrita tem falsos-negativos (números falados
por extenso, e-mails ditos "fulano arroba..."). Nomes de participantes NÃO são cobertos —
mantê-los como SPEAKER_xx é a mitigação (ver §7.2/E8).
"""

from __future__ import annotations

import re
from typing import Optional

# E-mail
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
# CPF formatado: 000.000.000-00 (com pontuação; o "melhor esforço" não pega falado)
_CPF = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
# Telefone BR: (16) 99123-4567 | 16 99123-4567 | 99123-4567 | +55 16 99123 4567
_PHONE = re.compile(
    r"(?:\+55\s*)?(?:\(?\d{2}\)?\s*)?\d{4,5}[-\s]\d{4}\b"
)

# ordem importa: e-mail antes de telefone (evita casar dígitos dentro de e-mails)
_PATTERNS = [_EMAIL, _CPF, _PHONE]


class Redactor:
    """Acumula um mapa estável placeholder->original entre múltiplas chamadas."""

    def __init__(self, start: int = 1) -> None:
        self.mapping: dict[str, str] = {}      # placeholder -> original
        self._reverse: dict[str, str] = {}     # original -> placeholder
        self._n = start

    def _placeholder_for(self, original: str) -> str:
        if original in self._reverse:
            return self._reverse[original]
        ph = f"[[PII-{self._n}]]"
        self._n += 1
        self.mapping[ph] = original
        self._reverse[original] = ph
        return ph

    def redact(self, text: str) -> str:
        def _sub(m: re.Match) -> str:
            return self._placeholder_for(m.group(0))

        out = text
        for pat in _PATTERNS:
            out = pat.sub(_sub, out)
        return out


def redact_text(text: str, redactor: Optional[Redactor] = None) -> tuple[str, dict[str, str]]:
    """Helper de uma passada: retorna (texto_redigido, mapa placeholder->original)."""
    r = redactor or Redactor()
    out = r.redact(text)
    return out, r.mapping
