"""
Stub providers for OpenAI, Anthropic (Claude), and Groq.

Each validates its key with a minimal API call and delegates generation to
the respective SDK.  All three follow the same pattern as GeminiProvider.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Iterator, List, Optional

from backend import config
from backend.generation.providers.base import BaseProvider

# ------------------------------------------------------------------ helpers

def _get_key(user_id: Optional[str], provider: str) -> str:
    if not user_id:
        raise ValueError(f"{provider} requires an API key.")
    from backend import keystore
    key = keystore.get_key(user_id, provider)
    if not key:
        raise ValueError(f"No {provider} API key found for this account.")
    return key


# ------------------------------------------------------------------ OpenAI

class OpenAIProvider(BaseProvider):
    name = "openai"

    def generate_answer(
        self,
        system: str,
        user: str,
        history: Optional[List[dict]] = None,
        user_id: Optional[str] = None,
        image_paths: Optional[List[str]] = None,
    ) -> str:
        from openai import OpenAI  # type: ignore
        key = _get_key(user_id, "openai")
        client = OpenAI(api_key=key, timeout=config.CLOUD_TIMEOUT)
        messages = [{"role": "system", "content": system}]
        for t in history or []:
            messages.append({"role": t["role"], "content": t["content"]})
        messages.append({"role": "user", "content": user})
        resp = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=messages,
            temperature=config.CLOUD_TEMPERATURE,
            max_tokens=config.CLOUD_MAX_TOKENS,
        )
        return resp.choices[0].message.content or ""

    def validate_api_key(self, key: str) -> bool:
        try:
            from openai import OpenAI  # type: ignore
            OpenAI(api_key=key, timeout=10).models.list()
            return True
        except Exception:
            return False

    def stream_answer(
        self,
        system: str,
        user: str,
        history: Optional[List[dict]] = None,
        user_id: Optional[str] = None,
        image_paths: Optional[List[str]] = None,
    ) -> Iterator[Dict[str, Any]]:
        from openai import OpenAI  # type: ignore
        key = _get_key(user_id, "openai")
        client = OpenAI(api_key=key, timeout=config.CLOUD_TIMEOUT)
        messages = [{"role": "system", "content": system}]
        for t in history or []:
            messages.append({"role": t["role"], "content": t["content"]})
        messages.append({"role": "user", "content": user})

        start = time.perf_counter()
        first_token_at = None
        parts: List[str] = []
        usage = None
        try:
            stream = client.chat.completions.create(
                model=config.OPENAI_MODEL, messages=messages,
                temperature=config.CLOUD_TEMPERATURE, max_tokens=config.CLOUD_MAX_TOKENS,
                stream=True, stream_options={"include_usage": True},
            )
        except TypeError:
            # Older SDK without stream_options support.
            stream = client.chat.completions.create(
                model=config.OPENAI_MODEL, messages=messages,
                temperature=config.CLOUD_TEMPERATURE, max_tokens=config.CLOUD_MAX_TOKENS,
                stream=True,
            )
        for event in stream:
            if getattr(event, "usage", None):
                usage = event.usage
            choices = getattr(event, "choices", None) or []
            if not choices:
                continue
            delta = getattr(choices[0].delta, "content", None)
            if delta:
                if first_token_at is None:
                    first_token_at = time.perf_counter()
                parts.append(delta)
                yield {"delta": delta}

        end = time.perf_counter()
        ttft_ms = (first_token_at - start) * 1000 if first_token_at else None
        gen_ms = (end - first_token_at) * 1000 if first_token_at else None
        completion_tokens = getattr(usage, "completion_tokens", None) if usage else None
        yield {
            "done": True, "text": "".join(parts),
            "metrics": {
                "provider": "openai", "model": config.OPENAI_MODEL,
                "streaming_enabled": True,
                "ttft_ms": round(ttft_ms, 1) if ttft_ms is not None else None,
                "generation_time_ms": round(gen_ms, 1) if gen_ms is not None else None,
                "total_llm_time_ms": round((end - start) * 1000, 1),
                "prompt_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
                "completion_tokens": completion_tokens,
                "tokens_per_second": (
                    round(completion_tokens / (gen_ms / 1000.0), 2)
                    if completion_tokens and gen_ms else None
                ),
            },
        }

    def supports_streaming(self) -> bool:
        return True

    def supports_function_calling(self) -> bool:
        return True


# ------------------------------------------------------------------ Anthropic

class ClaudeProvider(BaseProvider):
    name = "claude"

    def generate_answer(
        self,
        system: str,
        user: str,
        history: Optional[List[dict]] = None,
        user_id: Optional[str] = None,
        image_paths: Optional[List[str]] = None,
    ) -> str:
        import anthropic  # type: ignore
        key = _get_key(user_id, "claude")
        client = anthropic.Anthropic(api_key=key, timeout=config.CLOUD_TIMEOUT)
        messages = []
        for t in history or []:
            messages.append({"role": t["role"], "content": t["content"]})
        messages.append({"role": "user", "content": user})
        resp = client.messages.create(
            model=config.CLAUDE_MODEL,
            system=system,
            messages=messages,
            temperature=config.CLOUD_TEMPERATURE,
            max_tokens=config.CLOUD_MAX_TOKENS,
        )
        return resp.content[0].text if resp.content else ""

    def validate_api_key(self, key: str) -> bool:
        try:
            import anthropic  # type: ignore
            anthropic.Anthropic(api_key=key, timeout=10).models.list()
            return True
        except Exception:
            return False

    def stream_answer(
        self,
        system: str,
        user: str,
        history: Optional[List[dict]] = None,
        user_id: Optional[str] = None,
        image_paths: Optional[List[str]] = None,
    ) -> Iterator[Dict[str, Any]]:
        import anthropic  # type: ignore
        key = _get_key(user_id, "claude")
        client = anthropic.Anthropic(api_key=key, timeout=config.CLOUD_TIMEOUT)
        messages = []
        for t in history or []:
            messages.append({"role": t["role"], "content": t["content"]})
        messages.append({"role": "user", "content": user})

        start = time.perf_counter()
        first_token_at = None
        parts: List[str] = []
        final_message = None
        with client.messages.stream(
            model=config.CLAUDE_MODEL, system=system, messages=messages,
            temperature=config.CLOUD_TEMPERATURE, max_tokens=config.CLOUD_MAX_TOKENS,
        ) as stream:
            for text in stream.text_stream:
                if text:
                    if first_token_at is None:
                        first_token_at = time.perf_counter()
                    parts.append(text)
                    yield {"delta": text}
            final_message = stream.get_final_message()

        end = time.perf_counter()
        ttft_ms = (first_token_at - start) * 1000 if first_token_at else None
        gen_ms = (end - first_token_at) * 1000 if first_token_at else None
        usage = getattr(final_message, "usage", None)
        completion_tokens = getattr(usage, "output_tokens", None) if usage else None
        yield {
            "done": True, "text": "".join(parts),
            "metrics": {
                "provider": "claude", "model": config.CLAUDE_MODEL,
                "streaming_enabled": True,
                "ttft_ms": round(ttft_ms, 1) if ttft_ms is not None else None,
                "generation_time_ms": round(gen_ms, 1) if gen_ms is not None else None,
                "total_llm_time_ms": round((end - start) * 1000, 1),
                "prompt_tokens": getattr(usage, "input_tokens", None) if usage else None,
                "completion_tokens": completion_tokens,
                "tokens_per_second": (
                    round(completion_tokens / (gen_ms / 1000.0), 2)
                    if completion_tokens and gen_ms else None
                ),
            },
        }

    def supports_streaming(self) -> bool:
        return True

    def supports_function_calling(self) -> bool:
        return True


# ------------------------------------------------------------------ Groq

class GroqProvider(BaseProvider):
    name = "groq"

    # Known stable Groq models for fast offline fallback/reference
    DEFAULT_MODELS = [
        {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B Versatile", "context_window": 128000},
        {"id": "llama-3.1-8b-instant", "name": "Llama 3.1 8B Instant", "context_window": 128000},
        {"id": "llama-3.2-11b-vision-preview", "name": "Llama 3.2 11B Vision", "context_window": 128000},
        {"id": "llama-3.2-3b-preview", "name": "Llama 3.2 3B Preview", "context_window": 128000},
        {"id": "llama-3.2-1b-preview", "name": "Llama 3.2 1B Preview", "context_window": 128000},
        {"id": "mixtral-8x7b-32768", "name": "Mixtral 8x7B 32k", "context_window": 32768},
        {"id": "gemma2-9b-it", "name": "Gemma 2 9B IT", "context_window": 8192},
        {"id": "deepseek-r1-distill-llama-70b", "name": "DeepSeek R1 Distill Llama 70B", "context_window": 128000},
    ]

    def get_model_list(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch available models from Groq cloud if key is available, else return defaults."""
        try:
            key = _get_key(user_id, "groq")
        except Exception:
            return list(self.DEFAULT_MODELS)

        try:
            from groq import Groq  # type: ignore
            client = Groq(api_key=key, timeout=10)
            res = client.models.list()
            models_data = getattr(res, "data", []) or []
            chat_models = []
            for m in models_data:
                mid = getattr(m, "id", "") or ""
                # Filter out audio/whisper/moderation models
                if not mid or "whisper" in mid.lower() or "guard" in mid.lower():
                    continue
                chat_models.append({
                    "id": mid,
                    "name": mid,
                    "context_window": getattr(m, "context_window", None),
                })
            if chat_models:
                # Prioritize llama-3.3-70b-versatile and llama-3.1-8b-instant at top
                def _sort_key(item: dict) -> int:
                    mid = item["id"]
                    if "llama-3.3-70b" in mid:
                        return 0
                    if "llama-3.1-8b" in mid:
                        return 1
                    return 2
                chat_models.sort(key=_sort_key)
                return chat_models
        except Exception:
            pass
        return list(self.DEFAULT_MODELS)

    def generate_answer(
        self,
        system: str,
        user: str,
        history: Optional[List[dict]] = None,
        user_id: Optional[str] = None,
        image_paths: Optional[List[str]] = None,
        model: Optional[str] = None,
    ) -> str:
        from groq import Groq  # type: ignore
        key = _get_key(user_id, "groq")
        client = Groq(api_key=key, timeout=config.CLOUD_TIMEOUT)
        messages = [{"role": "system", "content": system}]
        for t in history or []:
            messages.append({"role": t["role"], "content": t["content"]})
        messages.append({"role": "user", "content": user})
        target_model = model or config.GROQ_MODEL
        resp = client.chat.completions.create(
            model=target_model,
            messages=messages,
            temperature=config.CLOUD_TEMPERATURE,
            max_tokens=config.CLOUD_MAX_TOKENS,
        )
        return resp.choices[0].message.content or ""

    def validate_api_key(self, key: str) -> bool:
        try:
            from groq import Groq  # type: ignore
            Groq(api_key=key, timeout=10).models.list()
            return True
        except Exception:
            return False

    def stream_answer(
        self,
        system: str,
        user: str,
        history: Optional[List[dict]] = None,
        user_id: Optional[str] = None,
        image_paths: Optional[List[str]] = None,
        model: Optional[str] = None,
    ) -> Iterator[Dict[str, Any]]:
        from groq import Groq  # type: ignore
        key = _get_key(user_id, "groq")
        client = Groq(api_key=key, timeout=config.CLOUD_TIMEOUT)
        messages = [{"role": "system", "content": system}]
        for t in history or []:
            messages.append({"role": t["role"], "content": t["content"]})
        messages.append({"role": "user", "content": user})

        target_model = model or config.GROQ_MODEL
        start = time.perf_counter()
        first_token_at = None
        parts: List[str] = []
        usage = None
        stream = client.chat.completions.create(
            model=target_model, messages=messages,
            temperature=config.CLOUD_TEMPERATURE, max_tokens=config.CLOUD_MAX_TOKENS,
            stream=True,
        )
        for event in stream:
            choices = getattr(event, "choices", None) or []
            xusage = getattr(event, "x_groq", None)
            if xusage is not None:
                usage = getattr(xusage, "usage", None)
            if not choices:
                continue
            delta = getattr(choices[0].delta, "content", None)
            if delta:
                if first_token_at is None:
                    first_token_at = time.perf_counter()
                parts.append(delta)
                yield {"delta": delta}

        end = time.perf_counter()
        ttft_ms = (first_token_at - start) * 1000 if first_token_at else None
        gen_ms = (end - first_token_at) * 1000 if first_token_at else None
        completion_tokens = getattr(usage, "completion_tokens", None) if usage else None
        yield {
            "done": True, "text": "".join(parts),
            "metrics": {
                "provider": "groq", "model": target_model,
                "streaming_enabled": True,
                "ttft_ms": round(ttft_ms, 1) if ttft_ms is not None else None,
                "generation_time_ms": round(gen_ms, 1) if gen_ms is not None else None,
                "total_llm_time_ms": round((end - start) * 1000, 1),
                "prompt_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
                "completion_tokens": completion_tokens,
                "tokens_per_second": (
                    round(completion_tokens / (gen_ms / 1000.0), 2)
                    if completion_tokens and gen_ms else None
                ),
            },
        }

    def supports_streaming(self) -> bool:
        return True
