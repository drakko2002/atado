"""Guardrails contra vazamento de segredos (HF key e chaves de provedores).

- mask_secrets: mascara padrões de token em qualquer texto ANTES de logar/gravar (defesa
  em profundidade — o token não deveria estar lá, mas nunca escrevemos um segredo em
  saída/relatório/erro).
- scan_text / looks_like_secret: detecção usada pelo `atado check` e pelo scanner de repo.
"""

from __future__ import annotations

import re

# (padrão, rótulo). Ordem importa (mais específico antes).
_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"hf_[A-Za-z0-9]{20,}"), "HF_TOKEN"),
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"), "ANTHROPIC_KEY"),
    (re.compile(r"AIza[0-9A-Za-z_\-]{30,}"), "GOOGLE_KEY"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"), "GITHUB_TOKEN"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "OPENAI_KEY"),
]


def mask_secrets(text: str) -> str:
    """Substitui qualquer segredo reconhecido por um placeholder redigido."""
    if not text:
        return text
    out = text
    for pat, label in _PATTERNS:
        out = pat.sub(f"[[{label}_REDACTED]]", out)
    return out


def scan_text(text: str) -> list[str]:
    """Retorna os rótulos dos segredos detectados no texto (vazio = limpo)."""
    found = []
    for pat, label in _PATTERNS:
        if pat.search(text or ""):
            found.append(label)
    return found


def looks_like_secret(value: str) -> bool:
    return bool(scan_text(value))
