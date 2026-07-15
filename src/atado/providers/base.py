"""Abstração mínima de provedor (Protocol) — sem framework pesado (E11)."""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

# E11: model ids NÃO são hard-coded no comportamento; são defaults documentados,
# lidos do config/--model e passíveis de override. Verifique o id atual ao usar.
DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-5",
    "openai": "gpt-5",
    "gemini": "gemini-2.5-pro",
    "ollama": "llama3.1",
}


class ProviderError(RuntimeError):
    pass


@runtime_checkable
class ChatProvider(Protocol):
    name: str

    def chat(self, messages: list[dict], *, model: Optional[str] = None,
             system: Optional[str] = None) -> str:
        """Envia a conversa e retorna a resposta do assistente (texto)."""
        ...

    def supports_search(self) -> bool:
        """True se o provedor oferece ferramenta de busca na web nativa."""
        ...


def get_provider(name: str, api_key: Optional[str] = None) -> ChatProvider:
    """Instancia o adapter do provedor. Import tardio do SDK (extra `providers`)."""
    name = name.lower()
    if name == "anthropic":
        from .anthropic import AnthropicProvider
        return AnthropicProvider(api_key=api_key)
    if name == "openai":
        from .openai import OpenAIProvider
        return OpenAIProvider(api_key=api_key)
    if name == "gemini":
        from .gemini import GeminiProvider
        return GeminiProvider(api_key=api_key)
    if name == "ollama":
        from .ollama import OllamaProvider
        return OllamaProvider()
    raise ProviderError(f"Provedor desconhecido: {name} "
                        f"(use: {', '.join(DEFAULT_MODELS)})")
