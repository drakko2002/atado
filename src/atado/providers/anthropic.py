"""Adapter Anthropic (Messages API). SDK importado tardiamente (extra `providers`)."""

from __future__ import annotations

import os
from typing import Optional

from .base import DEFAULT_MODELS, ProviderError


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: Optional[str] = None):
        self._key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self._key:
            raise ProviderError("ANTHROPIC_API_KEY ausente (defina via env).")

    def supports_search(self) -> bool:
        return True  # web_search server-side tool

    def chat(self, messages: list[dict], *, model: Optional[str] = None,
             system: Optional[str] = None) -> str:
        try:
            import anthropic  # lazy
        except ImportError as e:
            raise ProviderError("SDK anthropic ausente: pip install -e '.[providers]'") from e
        client = anthropic.Anthropic(api_key=self._key)
        model = model or DEFAULT_MODELS["anthropic"]
        conv = [m for m in messages if m.get("role") != "system"]
        kwargs = dict(model=model, max_tokens=4096, messages=conv)
        if system:
            kwargs["system"] = system
        # web_search é server-side; id pode mudar (E11) — degrada sem tools em caso de erro
        try:
            resp = client.messages.create(
                **kwargs, tools=[{"type": "web_search_20250305", "name": "web_search"}])
        except Exception:
            resp = client.messages.create(**kwargs)
        return "".join(getattr(b, "text", "") for b in resp.content
                       if getattr(b, "type", "") == "text").strip()
