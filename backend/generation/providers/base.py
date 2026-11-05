"""Abstract base class every LLM provider must implement."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Iterator, List, Optional


class BaseProvider(ABC):
    name: str  # registry key, e.g. "gemini"

    @abstractmethod
    def generate_answer(
        self,
        system: str,
        user: str,
        history: Optional[List[dict]] = None,
        user_id: Optional[str] = None,
        image_paths: Optional[List[str]] = None,
        model: Optional[str] = None,
    ) -> str:
        """Return a complete answer string."""

    def stream_answer(
        self,
        system: str,
        user: str,
        history: Optional[List[dict]] = None,
        user_id: Optional[str] = None,
        image_paths: Optional[List[str]] = None,
        model: Optional[str] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Normalized streaming protocol used by every provider (brief
        §51A.17: the frontend/router should not need a separate streaming
        implementation per provider):

            yields {"delta": "<token text>"} zero or more times, then exactly
            one final {"done": True, "text": "<full answer>",
            "metrics": {"provider": ..., "model": ..., ...}} chunk.

        Default implementation (used by any provider that doesn't override
        this): falls back to one non-streamed call and reports it as a
        single chunk, with `streaming_enabled: False` so callers/metrics
        never claim token-level streaming that didn't actually happen.
        """
        start = time.perf_counter()
        text = self.generate_answer(system, user, history, user_id=user_id,
                                     image_paths=image_paths, model=model)
        elapsed_ms = (time.perf_counter() - start) * 1000
        if text:
            yield {"delta": text}
        yield {
            "done": True,
            "text": text,
            "metrics": {
                "provider": self.name,
                "model": model or getattr(self, "model", ""),
                "streaming_enabled": False,
                "total_llm_time_ms": round(elapsed_ms, 1),
            },
        }

    @abstractmethod
    def validate_api_key(self, key: str) -> bool:
        """Return True if the key is accepted by the provider."""

    def get_model_list(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return []

    def supports_images(self) -> bool:
        return False

    def supports_streaming(self) -> bool:
        return False

    def supports_function_calling(self) -> bool:
        return False

    def is_available(self) -> bool:
        """Return True if the provider can serve requests right now."""
        return True
