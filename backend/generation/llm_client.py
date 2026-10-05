"""
Local LLM client — talks to Ollama running on your machine.

Fully offline. `keep_alive` keeps the model resident between requests so
follow-up questions are fast. Accepts an optional short conversation history
so the model "remembers" earlier turns in the same chat.

Local-inference target (see AUDIT_REPORT.md P1-2/P1-3 and the transformation
brief §4-5): qwen3:4b, thinking disabled, bounded context (num_ctx) and
output length (num_predict), streaming, and a real per-request timeout.
Every one of those is read from config (env-overridable) instead of being
hardcoded.

Start Ollama and pull the model once (see SETUP_GUIDE.md):
    ollama pull qwen3:4b
"""

from __future__ import annotations

import time
import re
from typing import Dict, Generator, List, Optional

from backend import config


class LLMError(RuntimeError):
    pass


_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>\s*", re.IGNORECASE | re.DOTALL)
_FINAL_MARKER_RE = re.compile(
    r"(?:final\s+answer|the\s+answer|the\s+name|answer)\s*(?:is\s*)?[:\-]?\s*",
    re.IGNORECASE,
)
_REASONING_MARKER_RE = re.compile(
    r"\b(we are given|we must|let us|let's|the context includes|let's scan|"
    r"the question asks|therefore|based on the context|we need to|"
    r"okay,? let me|looking at|first,|the other|the key point|"
    r"i need to|let me check|the answer should be|"
    r"the user is asking|so the final answer|seems to be|"
    r"the context states|in the context|wait,|hmm,|note that|"
    r"however,|the draft|the user's|the underlying model|"
    r"the instruction says|the requested information|we don't need|"
    r"the title is|actually,|likely|similarly|the context says|"
    r"first,? i need|i have the retrieved|let me look|the context has|"
    r"it has details|and it says|the question is about|from the context|"
    r"the answer is)\b",
    re.IGNORECASE,
)


def clean_answer(text: str) -> str:
    """Return only the model's final answer, never its reasoning preamble."""
    cleaned = _THINK_BLOCK_RE.sub("", text or "")
    cleaned = re.sub(r"</think>\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"```(?:text|markdown)?\s*|```", "", cleaned,
                     flags=re.IGNORECASE)
    # Normalize citation styles emitted by cloud/local models to the format
    # rendered as clickable citation chips by the frontend.
    cleaned = re.sub(r"【\s*(\d+)\s*】", r"[\1]", cleaned)

    # Small local models sometimes ignore the no-reasoning instruction and
    # write a visible analysis preamble in `content` even with think=False.
    # When they provide a final-answer marker, keep only the last marked
    # answer. This is deliberately conservative so ordinary document text is
    # not rewritten.
    markers = list(_FINAL_MARKER_RE.finditer(cleaned))
    if markers and _REASONING_MARKER_RE.search(cleaned[:markers[-1].start()]):
        cleaned = cleaned[markers[-1].end():]

    return cleaned.strip()


def _client():
    import ollama
    return ollama.Client(host=config.OLLAMA_HOST, timeout=config.OLLAMA_TIMEOUT)


def _build_messages(system: str, user: str,
                     history: Optional[List[Dict[str, str]]]) -> List[Dict[str, str]]:
    messages: List[Dict[str, str]] = [{"role": "system", "content": system}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user})
    return messages


def _chat_options() -> dict:
    return {
        "temperature": config.LLM_TEMPERATURE,
        "num_ctx": config.LLM_NUM_CTX,
        "num_predict": config.OLLAMA_NUM_PREDICT,
    }


def _chat_kwargs(messages: List[Dict[str, str]], model: Optional[str] = None) -> dict:
    kwargs = dict(
        model=model or config.LLM_MODEL,
        messages=messages,
        keep_alive=config.OLLAMA_KEEP_ALIVE,
        options=_chat_options(),
    )
    # Keep reasoning disabled at the API boundary.  Do not rely on the
    # model's default or concatenate Ollama's separate `thinking` field into
    # the user-visible `content` field.
    kwargs["think"] = False
    return kwargs


def chat(
    system: str,
    user: str,
    history: Optional[List[Dict[str, str]]] = None,
    model: Optional[str] = None,
) -> str:
    """system prompt + optional [{'role','content'}...] history + user turn.
    Blocking, non-streaming call — used by callers that need one complete
    string (e.g. multi-hop synthesis). For token-by-token output use
    stream_chat()."""
    messages = _build_messages(system, user, history)
    target_model = model or config.LLM_MODEL
    try:
        try:
            resp = _client().chat(**_chat_kwargs(messages, model=target_model))
        except TypeError:
            # Older ollama-python without `think=` support — retry without it.
            kwargs = _chat_kwargs(messages, model=target_model)
            kwargs.pop("think", None)
            resp = _client().chat(**kwargs)
        return clean_answer(resp["message"]["content"])
    except Exception as exc:
        raise LLMError(
            f"Could not reach the local LLM ('{target_model}' via "
            f"{config.OLLAMA_HOST}). Is Ollama running and the model pulled? "
            f"Original error: {exc}"
        ) from exc


def stream_chat(
    system: str,
    user: str,
    history: Optional[List[Dict[str, str]]] = None,
    model: Optional[str] = None,
) -> Generator[dict, None, None]:
    """Yield {"delta": <token text>} while generating, then a final
    {"done": True, "text": <full text>, "metrics": {...}} chunk.

    metrics (only the fields Ollama actually returns are included — nothing
    is fabricated; see AUDIT_REPORT.md §4 "honesty note"):
        ttft_ms              time to first generated token
        generation_time_ms   time from first token to last token
        total_time_ms        wall-clock time for the whole call
        prompt_tokens        Ollama's prompt_eval_count, if returned
        completion_tokens    Ollama's eval_count, if returned
        tokens_per_second    completion_tokens / (generation_time_ms/1000), if computable
    """
    messages = _build_messages(system, user, history)
    target_model = model or config.LLM_MODEL
    kwargs = _chat_kwargs(messages, model=target_model)
    kwargs["stream"] = True

    start = time.perf_counter()
    first_token_at: Optional[float] = None
    full_text_parts: List[str] = []
    final_chunk: dict = {}

    try:
        try:
            stream = _client().chat(**kwargs)
        except TypeError:
            kwargs.pop("think", None)
            stream = _client().chat(**kwargs)

        for chunk in stream:
            # Ollama can return `thinking` and `content` separately. Only
            # content is an answer; reasoning is intentionally discarded.
            piece = (chunk.get("message") or {}).get("content", "")
            if piece:
                if first_token_at is None:
                    if piece:
                        first_token_at = time.perf_counter()
                if piece:
                    full_text_parts.append(piece)
            if chunk.get("done"):
                final_chunk = chunk
    except Exception as exc:
        raise LLMError(
            f"Could not reach the local LLM ('{config.LLM_MODEL}' via "
            f"{config.OLLAMA_HOST}). Is Ollama running and the model pulled? "
            f"Original error: {exc}"
        ) from exc

    end = time.perf_counter()
    ttft_ms = (first_token_at - start) * 1000 if first_token_at else None
    generation_time_ms = (end - first_token_at) * 1000 if first_token_at else None
    total_time_ms = (end - start) * 1000

    completion_tokens = final_chunk.get("eval_count")
    prompt_tokens = final_chunk.get("prompt_eval_count")
    tokens_per_second = None
    if completion_tokens and generation_time_ms and generation_time_ms > 0:
        tokens_per_second = round(completion_tokens / (generation_time_ms / 1000.0), 2)

    metrics = {
        "provider": "ollama",
        "model": config.LLM_MODEL,
        "context_size": config.LLM_NUM_CTX,
        "thinking_enabled": False,
        "streaming_enabled": True,
        "ttft_ms": round(ttft_ms, 1) if ttft_ms is not None else None,
        "generation_time_ms": round(generation_time_ms, 1) if generation_time_ms is not None else None,
        "total_llm_time_ms": round(total_time_ms, 1),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "tokens_per_second": tokens_per_second,
    }
    final_text = clean_answer("".join(full_text_parts))
    # Do not stream raw model content: it may contain reasoning before the
    # final answer. Emit only the sanitized final answer to the UI.
    if final_text:
        yield {"delta": final_text}
    yield {"done": True, "text": final_text, "metrics": metrics}


def is_available() -> bool:
    try:
        models = _client().list().get("models", [])
        names = [m.get("model", m.get("name", "")) for m in models]
        return any(config.LLM_MODEL.split(":")[0] in n for n in names)
    except Exception:
        return False
