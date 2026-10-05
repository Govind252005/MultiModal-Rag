"""
Groq Cloud LLM Provider adapter for evaluation.
Never logs, exposes, or commits the GROQ_API_KEY.
Uses standard HTTP/REST or groq SDK to communicate with Groq cloud.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Iterator, List, Optional
from evaluation.providers.base_provider import BaseEvalProvider


class GroqEvalProvider(BaseEvalProvider):
    name = "groq"

    def __init__(
        self,
        model: str = "openai/gpt-oss-120b",
        api_key: Optional[str] = None,
        timeout: int = 60,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ):
        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        self.max_tokens = max_tokens
        # Retrieve key safely from env var
        self._api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self.api_base = "https://api.groq.com/openai/v1"
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._total_calls = 0

    def is_available(self) -> bool:
        if not self._api_key or not self._api_key.strip():
            return False
        # Optional lightweight ping
        return True

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        if not self.is_available():
            return {
                "text": "",
                "latency_ms": 0.0,
                "ttft_ms": None,
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": None,
                "tokens_per_second": None,
                "error": "GROQ_API_KEY environment variable not set.",
                "raw_metrics": {},
            }

        url = f"{self.api_base}/chat/completions"
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        for h in (history or []):
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
        }

        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        req = urllib.request.Request(url, data=body, method="POST", headers=headers)

        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                data = json.loads(resp.read().decode("utf-8"))
                choice = data.get("choices", [{}])[0]
                text = choice.get("message", {}).get("content", "")
                usage = data.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens")
                completion_tokens = usage.get("completion_tokens")
                total_tokens = usage.get("total_tokens")

                if prompt_tokens:
                    self._total_prompt_tokens += prompt_tokens
                if completion_tokens:
                    self._total_completion_tokens += completion_tokens
                self._total_calls += 1

                tps = None
                if completion_tokens and elapsed_ms > 0:
                    tps = round(completion_tokens / (elapsed_ms / 1000.0), 2)

                return {
                    "text": text,
                    "latency_ms": round(elapsed_ms, 2),
                    "ttft_ms": None,  # Non-streaming doesn't isolate TTFT
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "tokens_per_second": tps,
                    "error": None,
                    "raw_metrics": usage,
                }
        except Exception as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            return {
                "text": "",
                "latency_ms": round(elapsed_ms, 2),
                "ttft_ms": None,
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": None,
                "tokens_per_second": None,
                "error": str(e),
                "raw_metrics": {},
            }

    def stream(
        self,
        prompt: str,
        system: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ) -> Iterator[Dict[str, Any]]:
        # For simplicity, calls generate and yields single delta
        res = self.generate(prompt, system, history, **kwargs)
        yield {"delta": res["text"], "done": True, "metrics": res}

    def get_usage(self) -> Dict[str, Any]:
        return {
            "provider": self.name,
            "model": self.model,
            "total_calls": self._total_calls,
            "total_prompt_tokens": self._total_prompt_tokens,
            "total_completion_tokens": self._total_completion_tokens,
            "total_tokens": self._total_prompt_tokens + self._total_completion_tokens,
        }
