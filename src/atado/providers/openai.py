"""Adapter OpenAI (Responses API com busca opcional). SDK importado tardiamente."""

from __future__ import annotations

import os
from typing import Optional

from .base import DEFAULT_MODELS, ProviderError


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: Optional[str] = None):
        self._key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self._key:
            raise ProviderError("OPENAI_API_KEY ausente (defina via env).")

    def supports_search(self) -> bool:
        return True  # web_search tool (Responses API)

    def chat(self, messages: list[dict], *, model: Optional[str] = None,
             system: Optional[str] = None) -> str:
        try:
            from openai import OpenAI  # lazy
        except ImportError as e:
            raise ProviderError("SDK openai ausente: pip install -e '.[providers]'") from e
        client = OpenAI(api_key=self._key)
        model = model or DEFAULT_MODELS["openai"]
        input_msgs = []
        if system:
            input_msgs.append({"role": "system", "content": system})
        input_msgs += [{"role": m["role"], "content": m["content"]}
                       for m in messages if m.get("role") != "system"]
        try:
            resp = client.responses.create(
                model=model, input=input_msgs, tools=[{"type": "web_search"}])
        except Exception:
            resp = client.responses.create(model=model, input=input_msgs)
        return (getattr(resp, "output_text", None) or "").strip()
