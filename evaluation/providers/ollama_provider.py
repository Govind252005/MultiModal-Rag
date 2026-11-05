"""
Ollama Provider adapter for evaluation.
Communicates with local Ollama daemon (default: qwen3:4b) and captures latency and token usage.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Iterator, List, Optional
from evaluation.providers.base_provider import BaseEvalProvider


class OllamaEvalProvider(BaseEvalProvider):
    name = "ollama"

    def __init__(
        self,
        model: str = "qwen3:4b",
        host: str = "http://localhost:11434",
        timeout: int = 120,
        num_ctx: int = 4096,
        temperature: float = 0.1,
    ):
        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout
        self.num_ctx = num_ctx
        self.temperature = temperature
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._total_calls = 0

    def is_available(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.host}/api/tags")
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    models = [m.get("name") for m in data.get("models", [])]
                    # Check if requested model or prefix exists
                    return any(self.model in m for m in models) or len(models) > 0
        except Exception:
            pass
        return False

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        url = f"{self.host}/api/chat"
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        for h in (history or []):
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_ctx": kwargs.get("num_ctx", self.num_ctx),
                "temperature": kwargs.get("temperature", self.temperature),
            },
        }

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=body, method="POST", headers={"Content-Type": "application/json"}
        )

        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                data = json.loads(resp.read().decode("utf-8"))
                msg = data.get("message", {}).get("content", "")
                prompt_tokens = data.get("prompt_eval_count")
                completion_tokens = data.get("eval_count")
                total_tokens = (
                    (prompt_tokens or 0) + (completion_tokens or 0)
                    if (prompt_tokens or completion_tokens)
                    else None
                )

                if prompt_tokens:
                    self._total_prompt_tokens += prompt_tokens
                if completion_tokens:
                    self._total_completion_tokens += completion_tokens
                self._total_calls += 1

                tps = None
                eval_duration = data.get("eval_duration")  # in nanoseconds
                if eval_duration and completion_tokens:
                    tps = round(completion_tokens / (eval_duration / 1e9), 2)

                return {
                    "text": msg,
                    "latency_ms": round(elapsed_ms, 2),
                    "ttft_ms": round(data.get("prompt_eval_duration", 0) / 1e6, 2) if data.get("prompt_eval_duration") else None,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "tokens_per_second": tps,
                    "error": None,
                    "raw_metrics": data,
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
        url = f"{self.host}/api/chat"
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        for h in (history or []):
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {"num_ctx": self.num_ctx, "temperature": self.temperature},
        }

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=body, method="POST", headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            for line in resp:
                if line:
                    data = json.loads(line.decode("utf-8"))
                    delta = data.get("message", {}).get("content", "")
                    yield {"delta": delta, "done": data.get("done", False)}

    def get_usage(self) -> Dict[str, Any]:
        return {
            "provider": self.name,
            "model": self.model,
            "total_calls": self._total_calls,
            "total_prompt_tokens": self._total_prompt_tokens,
            "total_completion_tokens": self._total_completion_tokens,
            "total_tokens": self._total_prompt_tokens + self._total_completion_tokens,
        }
