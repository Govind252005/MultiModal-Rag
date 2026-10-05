"""
Base LLM Provider abstraction for evaluation.
Defines standard interface: generate(), stream(), get_usage(), is_available().
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterator, List, Optional


class BaseEvalProvider(ABC):
    """Abstract base class for all evaluation LLM providers."""

    name: str = "base"
    model: str = "unknown"

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Executes a completion and returns a standard dictionary:
        {
            "text": str,
            "latency_ms": float,
            "ttft_ms": Optional[float],
            "prompt_tokens": Optional[int],
            "completion_tokens": Optional[int],
            "total_tokens": Optional[int],
            "tokens_per_second": Optional[float],
            "error": Optional[str],
            "raw_metrics": Dict[str, Any],
        }
        """
        pass

    @abstractmethod
    def stream(
        self,
        prompt: str,
        system: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ) -> Iterator[Dict[str, Any]]:
        """Streams tokens yielding chunks."""
        pass

    @abstractmethod
    def get_usage(self) -> Dict[str, Any]:
        """Returns cumulative usage statistics across queries."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if the provider is currently reachable and configured."""
        pass
