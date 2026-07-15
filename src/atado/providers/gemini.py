"""Adapter Google Gemini (grounding). SDK google-genai importado tardiamente."""

from __future__ import annotations

import os
from typing import Optional

from .base import DEFAULT_MODELS, ProviderError


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: Optional[str] = None):
        self._key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not self._key:
            raise ProviderError("GEMINI_API_KEY ausente (defina via env).")

    def supports_search(self) -> bool:
        return True  # grounding com Google Search

    def chat(self, messages: list[dict], *, model: Optional[str] = None,
             system: Optional[str] = None) -> str:
        try:
            from google import genai  # lazy
            from google.genai import types
        except ImportError as e:
            raise ProviderError("SDK google-genai ausente: pip install -e '.[providers]'") from e
        client = genai.Client(api_key=self._key)
        model = model or DEFAULT_MODELS["gemini"]
        # concatena a conversa (Gemini usa 'contents'); system via system_instruction
        contents = []
        for m in messages:
            if m.get("role") == "system":
                continue
            role = "user" if m["role"] == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part(text=m["content"])]))
        cfg = types.GenerateContentConfig(
            system_instruction=system,
            tools=[types.Tool(google_search=types.GoogleSearch())],
        )
        try:
            resp = client.models.generate_content(model=model, contents=contents, config=cfg)
        except Exception:
            resp = client.models.generate_content(
                model=model, contents=contents,
                config=types.GenerateContentConfig(system_instruction=system))
        return (getattr(resp, "text", None) or "").strip()
