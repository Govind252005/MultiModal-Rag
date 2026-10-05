"""
Router — chooses a provider, runs generation, and applies a classified
failover/retry policy instead of unconditionally falling back to local
Ollama on any error (AUDIT_REPORT.md P0-5; brief §52 / §51A.21).

The router is the single seam that generation/answer.py (and the streaming
endpoint in main.py) call into. The retrieval pipeline is completely
untouched by anything here — this module only decides which backend
produces the final answer text (brief §51A.16/§51A.28: one RAG pipeline,
one provider router, no duplicated generation logic per provider).
"""

from __future__ import annotations

import json
import random
import time
import uuid
from typing import Any, Dict, Iterator, List, Optional

from backend import config
from backend.generation import llm_client
from backend.generation.providers import circuit_breaker, errors
from backend.generation.providers.registry import registry
from backend.observability import metrics as obs_metrics

def _log_generation(event: Dict[str, Any]) -> None:
    """Structured LLM observability (brief §6 / §51A.18): a single-line
    JSON print (grep/jq-able) for humans reading logs, AND a push into the
    dependency-free Prometheus registry (observability/metrics.py) for
    dashboards/alerting (brief §125). Both come from this one call site so
    they can never drift apart.

    Never logs: API keys, raw document content, or user query text.
    """
    try:
        print("[llm_observability] " + json.dumps(event, ensure_ascii=False, default=str))
    except Exception:
        pass

    provider = event.get("provider", "unknown")
    status = event.get("status", "unknown")
    try:
        obs_metrics.inc_counter("rag_generation_total", {"provider": provider, "status": status})
        if status == "error":
            obs_metrics.inc_counter(
                "errors_total",
                {"provider": provider, "category": event.get("error_category", "unknown")},
            )
        for field, metric_name in (
            ("total_llm_time_ms", "llm_latency_ms"),
            ("ttft_ms", "llm_ttft_ms"),
        ):
            value = event.get(field)
            if isinstance(value, (int, float)):
                obs_metrics.observe_histogram(metric_name, float(value), {"provider": provider})
        tps = event.get("tokens_per_second")
        if isinstance(tps, (int, float)):
            # Not a latency — reuses the histogram machinery just to get
            # min/mean/count for free from the same render() path, with
            # its own (much smaller) bucket set.
            obs_metrics.observe_histogram(
                "llm_tokens_per_second", float(tps), {"provider": provider},
                buckets=[5, 10, 20, 40, 80, 160],
            )
    except Exception:
        pass


def _backoff_sleep(attempt: int) -> None:
    """Exponential backoff with jitter (brief §97) between same-provider
    retries. Never called for NON_RETRYABLE categories (invalid key/
    request) — those fail immediately, no retry at all, per §97's own
    "never retry ... invalid API key" rule, enforced by the caller only
    reaching this function inside the retryable branch."""
    base = config.PROVIDER_RETRY_BASE_DELAY_SECONDS
    delay = min(base * (2 ** (attempt - 1)), config.PROVIDER_RETRY_MAX_DELAY_SECONDS)
    jitter = random.uniform(0, delay * 0.25)
    time.sleep(delay + jitter)


class Router:
    def get_provider(self, name: Optional[str] = None):
        return registry.get(name or config.DEFAULT_PROVIDER)

    # ------------------------------------------------------------------
    def generate(
        self,
        system: str,
        user: str,
        history: Optional[List[dict]] = None,
        provider: Optional[str] = None,
        user_id: Optional[str] = None,
        image_paths: Optional[List[str]] = None,
        model: Optional[str] = None,
    ) -> str:
        request_id = uuid.uuid4().hex[:12]
        requested_name = provider or config.DEFAULT_PROVIDER
        name = requested_name
        attempts = 0
        last_exc: Optional[BaseException] = None
        last_category = "unknown"

        max_attempts = max(1, config.PROVIDER_RETRY_MAX_ATTEMPTS)

        while True:
            attempts += 1
            prov = registry.get(name)
            start = time.perf_counter()

            if not circuit_breaker.allow_request(name):
                # Skip the network round-trip entirely — the breaker is
                # OPEN for this provider, so treat it the same way a real
                # provider_unavailable error would be treated by the
                # failover logic below, without actually spending a
                # request on a provider we already know is down.
                last_exc = RuntimeError(f"circuit breaker OPEN for provider '{name}'")
                last_category = "provider_unavailable"
                _log_generation({
                    "request_id": request_id, "provider": name,
                    "requested_provider": requested_name, "attempts": attempts,
                    "status": "circuit_open",
                })
            else:
                try:
                    if name == "ollama":
                        text = prov.generate_answer(system, user, history=history)
                    else:
                        text = prov.generate_answer(
                            system, user, history=history,
                            user_id=user_id, image_paths=image_paths,
                            model=model,
                        )
                    circuit_breaker.record_success(name)
                    _log_generation({
                        "request_id": request_id, "provider": name,
                        "requested_provider": requested_name, "attempts": attempts,
                        "status": "ok", "total_llm_time_ms": round((time.perf_counter() - start) * 1000, 1),
                    })
                    return text
                except Exception as exc:
                    last_exc = exc
                    last_category = errors.classify(exc)
                    # Only provider-health categories affect the breaker —
                    # see circuit_breaker.py's docstring for why a bad key
                    # or a rate limit must NEVER trip it.
                    if last_category in ("provider_unavailable", "network_error"):
                        circuit_breaker.record_provider_failure(name)
                    _log_generation({
                        "request_id": request_id, "provider": name,
                        "requested_provider": requested_name, "attempts": attempts,
                        "status": "error", "error_category": last_category,
                        "total_llm_time_ms": round((time.perf_counter() - start) * 1000, 1),
                    })

            # Non-retryable: fail immediately, never failover, never
            # silently substitute a different provider's answer for the
            # one the user explicitly asked for (brief §51A.21).
            if last_category in errors.NON_RETRYABLE:
                break

            # Retryable category but same provider — retry a bounded
            # number of times before considering failover. Exponential
            # backoff + jitter (brief §97) so a transient rate-limit/5xx
            # doesn't get hammered again immediately.
            if name == requested_name and attempts < max_attempts:
                _backoff_sleep(attempts)
                continue

            # Exhausted retries on a retryable error: failover to local
            # Ollama ONLY if explicitly enabled and we're not already
            # using it.
            if (
                name != "ollama"
                and config.PROVIDER_FAILOVER_TO_LOCAL
                and last_category in errors.RETRYABLE
            ):
                name = "ollama"
                attempts = 0
                continue
            break

        raise llm_client.LLMError(
            errors.user_message(last_category, requested_name, last_exc)
        ) from last_exc

    # ------------------------------------------------------------------
    def stream_generate(
        self,
        system: str,
        user: str,
        history: Optional[List[dict]] = None,
        provider: Optional[str] = None,
        user_id: Optional[str] = None,
        image_paths: Optional[List[str]] = None,
        model: Optional[str] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Same classified failover policy as generate(), but yields the
        normalized streaming protocol (see BaseProvider.stream_answer):
        {"delta": ...}* then one {"done": True, "text": ..., "metrics": ...}.
        A "provider" and "requested_provider" field is added to the final
        metrics chunk so callers/observability never misattribute which
        backend actually generated the answer (brief §51A.18/§51A.19)."""
        request_id = uuid.uuid4().hex[:12]
        requested_name = provider or config.DEFAULT_PROVIDER
        name = requested_name
        last_exc: Optional[BaseException] = None
        last_category = "unknown"

        candidates = [requested_name]
        if requested_name != "ollama":
            candidates.append("ollama")

        for name in candidates:
            prov = registry.get(name)
            start = time.perf_counter()
            try:
                stream_kwargs: Dict[str, Any] = {
                    "history": history,
                    "user_id": user_id,
                    "image_paths": image_paths,
                }
                if name != "ollama" and model:
                    stream_kwargs["model"] = model

                for chunk in prov.stream_answer(
                    system, user, **stream_kwargs
                ):
                    if chunk.get("done"):
                        metrics = dict(chunk.get("metrics") or {})
                        metrics.setdefault("provider", name)
                        metrics["requested_provider"] = requested_name
                        _log_generation({
                            "request_id": request_id, **metrics, "status": "ok",
                        })
                        yield {**chunk, "metrics": metrics}
                    else:
                        yield chunk
                return
            except Exception as exc:
                last_exc = exc
                last_category = errors.classify(exc)
                _log_generation({
                    "request_id": request_id, "provider": name,
                    "requested_provider": requested_name, "status": "error",
                    "error_category": last_category,
                    "total_llm_time_ms": round((time.perf_counter() - start) * 1000, 1),
                })
                if last_category in errors.NON_RETRYABLE:
                    break
                if name == "ollama" or not config.PROVIDER_FAILOVER_TO_LOCAL:
                    break
                if last_category not in errors.RETRYABLE:
                    break
                # else: fall through to the next iteration -> try "ollama"
                continue

        raise llm_client.LLMError(
            errors.user_message(last_category, requested_name, last_exc)
        ) from last_exc


router = Router()
