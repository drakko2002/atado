"""Adapter Ollama (local, SEM busca). Degrada para pesquisa mediada (protocolo §6.3)."""

from __future__ import annotations

import os
from typing import Optional

from .base import DEFAULT_MODELS, ProviderError


class OllamaProvider:
    name = "ollama"

    def __init__(self, host: Optional[str] = None):
        self._host = host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    def supports_search(self) -> bool:
        return False  # sem busca: o protocolo emite PESQUISAR: e o usuário cola resultados

    def chat(self, messages: list[dict], *, model: Optional[str] = None,
             system: Optional[str] = None) -> str:
        try:
            import requests  # lazy
        except ImportError as e:
            raise ProviderError("requests ausente: pip install -e '.[providers]'") from e
        model = model or DEFAULT_MODELS["ollama"]
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs += [{"role": m["role"], "content": m["content"]}
                 for m in messages if m.get("role") != "system"]
        try:
            r = requests.post(f"{self._host}/api/chat",
                              json={"model": model, "messages": msgs, "stream": False},
                              timeout=600)
            r.raise_for_status()
        except Exception as e:
            raise ProviderError(f"Falha ao falar com Ollama em {self._host}: {e}") from e
        return (r.json().get("message", {}).get("content", "") or "").strip()
