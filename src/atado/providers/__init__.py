"""Adapters finos sobre SDKs oficiais (sem LangChain/frameworks). F9, opcional."""

from .base import ChatProvider, get_provider, DEFAULT_MODELS, ProviderError

__all__ = ["ChatProvider", "get_provider", "DEFAULT_MODELS", "ProviderError"]
