"""
Provider registry — maps provider name strings to provider instances.
"""

from __future__ import annotations

from typing import Dict

from backend.generation.providers.base import BaseProvider
from backend.generation.providers.ollama_provider import OllamaProvider
from backend.generation.providers.gemini_provider import GeminiProvider
from backend.generation.providers.cloud_providers import OpenAIProvider, ClaudeProvider, GroqProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: Dict[str, BaseProvider] = {}
        for cls in (OllamaProvider, GeminiProvider, OpenAIProvider, ClaudeProvider, GroqProvider):
            p = cls()
            self._providers[p.name] = p

    def get(self, name: str) -> BaseProvider:
        p = self._providers.get(name)
        if p is None:
            raise KeyError(f"Unknown provider: {name!r}")
        return p

    def names(self) -> list[str]:
        return list(self._providers.keys())


registry = ProviderRegistry()
