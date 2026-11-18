"""
OllamaProvider — wraps the existing llm_client so the rest of the codebase
can treat local Qwen exactly like any cloud provider.
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional

from backend.generation import llm_client
from backend.generation.providers.base import BaseProvider


class OllamaProvider(BaseProvider):
    name = "ollama"

    def generate_answer(
        self,
        system: str,
        user: str,
        history: Optional[List[dict]] = None,
        user_id: Optional[str] = None,
        image_paths: Optional[List[str]] = None,
        model: Optional[str] = None,
    ) -> str:
        # Ollama/Qwen text-only; image_paths silently ignored
        return llm_client.chat(system, user, history=history, model=model)

    def stream_answer(
        self,
        system: str,
        user: str,
        history: Optional[List[dict]] = None,
        user_id: Optional[str] = None,
        image_paths: Optional[List[str]] = None,
        model: Optional[str] = None,
    ) -> Iterator[Dict[str, Any]]:
        # llm_client.stream_chat() already yields the normalized
        # {"delta": ...} / {"done": True, "text": ..., "metrics": ...} shape.
        yield from llm_client.stream_chat(system, user, history=history, model=model)

    def get_model_list(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        import backend.config as b_config
        target = getattr(b_config, "LLM_MODEL", "qwen2.5:7b-instruct")
        return [{"id": target, "name": target}]

    def validate_api_key(self, key: str) -> bool:
        return True  # local; no key needed

    def is_available(self) -> bool:
        return llm_client.is_available()

    def supports_streaming(self) -> bool:
        from backend import config
        return config.OLLAMA_STREAM
