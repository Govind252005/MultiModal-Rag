"""
Provider router regression tests (transformation brief §143: "every
discovered vulnerability/bug must become a regression test").

This suite exists because a real infinite-loop bug was found in
generation/providers/router.py during this transformation (a
str_replace edit shifted indentation by one level, stranding the
failover-to-Ollama logic after an unconditional `continue`, making it
unreachable — see CHANGES.md for the full story). These tests were
first written as one-off scratch scripts to catch and verify the fix;
this file is that same test logic, cleaned up into a permanent,
reusable suite instead of living only in a conversation transcript.

Runs with: pytest tests/unit/test_provider_router.py
Can also run directly: python tests/unit/test_provider_router.py
(uses a tiny manual runner at the bottom — see the note there for why).

Isolation approach: router.py, its error-classification module, and the
circuit breaker all get imported fresh under fake `config`/`registry`
modules for each test, via the `load_router()` helper below — this
avoids needing FastAPI/torch/chromadb installed (none of router.py's
actual logic touches those), which is what lets this suite run in a
minimal Python environment.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import time
import types
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"


class FakeAuthError(Exception):
    status_code = 401


class FakeRateLimit(Exception):
    status_code = 429


class FakeServerError(Exception):
    status_code = 503


class FakeProvider:
    """A minimal stand-in for a real provider (OllamaProvider,
    OpenAIProvider, etc.) — fails `fail_times` times with `fail_with`,
    then succeeds."""

    def __init__(self, name: str, fail_with: Exception = None, fail_times: int = 0):
        self.name = name
        self.fail_with = fail_with
        self.fail_times = fail_times
        self.calls = 0

    def generate_answer(self, system, user, history=None, user_id=None, image_paths=None, model=None):
        self.calls += 1
        if self.fail_with and self.calls <= self.fail_times:
            raise self.fail_with
        return f"answer-from-{self.name}"

    def stream_answer(self, system, user, history=None, user_id=None, image_paths=None, model=None):
        self.calls += 1
        if self.fail_with and self.calls <= self.fail_times:
            raise self.fail_with
        yield {"delta": "hi"}
        yield {"done": True, "text": "hi", "metrics": {}}


class FakeRegistry:
    def __init__(self, providers: dict):
        self._providers = providers

    def get(self, name):
        return self._providers[name]


def load_router(providers: dict, failover: bool = True, max_attempts: int = 2,
                base_delay: float = 0.01, max_delay: float = 0.1,
                circuit_threshold: int = 1000, circuit_cooldown: float = 0.01):
    """Imports a FRESH copy of router.py (and its dependencies) under a
    fake config/registry, so each test gets an isolated module instance
    with no state leaking from a previous test's circuit breaker, etc."""
    fake_config = types.ModuleType("config")
    fake_config.DEFAULT_PROVIDER = "groq"
    fake_config.PROVIDER_FAILOVER_TO_LOCAL = failover
    fake_config.PROVIDER_RETRY_MAX_ATTEMPTS = max_attempts
    fake_config.PROVIDER_RETRY_BASE_DELAY_SECONDS = base_delay
    fake_config.PROVIDER_RETRY_MAX_DELAY_SECONDS = max_delay
    fake_config.CIRCUIT_BREAKER_FAILURE_THRESHOLD = circuit_threshold
    fake_config.CIRCUIT_BREAKER_COOLDOWN_SECONDS = circuit_cooldown
    sys.modules["config"] = fake_config
    sys.path.insert(0, str(BACKEND))

    backend_pkg = types.ModuleType("backend")
    backend_pkg.__path__ = [str(BACKEND)]
    sys.modules["backend"] = backend_pkg
    sys.modules["backend.config"] = fake_config
    backend_pkg.config = fake_config

    generation_pkg = types.ModuleType("generation")
    generation_pkg.__path__ = [str(BACKEND / "generation")]
    sys.modules["generation"] = generation_pkg
    sys.modules["backend.generation"] = generation_pkg

    llm_client_spec = importlib.util.spec_from_file_location(
        "generation.llm_client", str(BACKEND / "generation" / "llm_client.py"))
    llm_client = importlib.util.module_from_spec(llm_client_spec)
    sys.modules["generation.llm_client"] = llm_client
    sys.modules["backend.generation.llm_client"] = llm_client
    llm_client_spec.loader.exec_module(llm_client)

    providers_pkg = types.ModuleType("generation.providers")
    providers_pkg.__path__ = [str(BACKEND / "generation" / "providers")]
    sys.modules["generation.providers"] = providers_pkg
    sys.modules["backend.generation.providers"] = providers_pkg

    errors_spec = importlib.util.spec_from_file_location(
        "generation.providers.errors", str(BACKEND / "generation" / "providers" / "errors.py"))
    errors = importlib.util.module_from_spec(errors_spec)
    sys.modules["generation.providers.errors"] = errors
    sys.modules["backend.generation.providers.errors"] = errors
    errors_spec.loader.exec_module(errors)

    cb_spec = importlib.util.spec_from_file_location(
        "generation.providers.circuit_breaker",
        str(BACKEND / "generation" / "providers" / "circuit_breaker.py"))
    circuit_breaker = importlib.util.module_from_spec(cb_spec)
    sys.modules["generation.providers.circuit_breaker"] = circuit_breaker
    sys.modules["backend.generation.providers.circuit_breaker"] = circuit_breaker
    cb_spec.loader.exec_module(circuit_breaker)
    circuit_breaker.reset()

    obs_spec = importlib.util.spec_from_file_location(
        "observability.metrics", str(BACKEND / "observability" / "metrics.py"))
    obs_metrics = importlib.util.module_from_spec(obs_spec)
    obs_pkg = types.ModuleType("observability")
    obs_pkg.__path__ = [str(BACKEND / "observability")]
    sys.modules["observability"] = obs_pkg
    sys.modules["observability.metrics"] = obs_metrics
    sys.modules["backend.observability"] = obs_pkg
    sys.modules["backend.observability.metrics"] = obs_metrics
    obs_spec.loader.exec_module(obs_metrics)

    registry_module = types.ModuleType("generation.providers.registry")
    registry_module.registry = FakeRegistry(providers)
    sys.modules["generation.providers.registry"] = registry_module
    sys.modules["backend.generation.providers.registry"] = registry_module

    router_spec = importlib.util.spec_from_file_location(
        "generation.providers.router", str(BACKEND / "generation" / "providers" / "router.py"))
    router_mod = importlib.util.module_from_spec(router_spec)
    sys.modules["generation.providers.router"] = router_mod
    sys.modules["backend.generation.providers.router"] = router_mod
    router_spec.loader.exec_module(router_mod)

    return router_mod.router, llm_client, errors, circuit_breaker


# ---------------------------------------------------------------- tests
def test_invalid_key_fails_immediately_no_failover():
    providers = {"groq": FakeProvider("groq", fail_with=FakeAuthError(), fail_times=999),
                "ollama": FakeProvider("ollama")}
    router, llm_client, errors, cb = load_router(providers)
    raised = False
    try:
        router.generate("s", "u", provider="groq")
    except llm_client.LLMError:
        raised = True
    assert raised
    assert providers["groq"].calls == 1
    assert providers["ollama"].calls == 0


def test_transient_rate_limit_recovers_without_failover():
    providers = {"groq": FakeProvider("groq", fail_with=FakeRateLimit(), fail_times=1),
                "ollama": FakeProvider("ollama")}
    router, llm_client, errors, cb = load_router(providers)
    result = router.generate("s", "u", provider="groq")
    assert result == "answer-from-groq"
    assert providers["ollama"].calls == 0


def test_exhausted_retries_fail_over_to_ollama():
    providers = {"groq": FakeProvider("groq", fail_with=FakeRateLimit(), fail_times=999),
                "ollama": FakeProvider("ollama")}
    router, llm_client, errors, cb = load_router(providers)
    result = router.generate("s", "u", provider="groq")
    assert result == "answer-from-ollama"
    assert providers["groq"].calls == 2  # PROVIDER_RETRY_MAX_ATTEMPTS
    assert providers["ollama"].calls == 1


def test_failover_disabled_raises_instead_of_falling_back():
    providers = {"groq": FakeProvider("groq", fail_with=FakeRateLimit(), fail_times=999),
                "ollama": FakeProvider("ollama")}
    router, llm_client, errors, cb = load_router(providers, failover=False)
    raised = False
    try:
        router.generate("s", "u", provider="groq")
    except llm_client.LLMError:
        raised = True
    assert raised
    assert providers["ollama"].calls == 0


def test_streaming_failover_reports_actual_provider_used():
    providers = {"groq": FakeProvider("groq", fail_with=FakeRateLimit(), fail_times=999),
                "ollama": FakeProvider("ollama")}
    router, llm_client, errors, cb = load_router(providers)
    chunks = list(router.stream_generate("s", "u", provider="groq"))
    assert chunks[-1]["metrics"]["provider"] == "ollama"
    assert chunks[-1]["metrics"]["requested_provider"] == "groq"


def test_no_infinite_loop_on_exhausted_retries():
    """Regression test for the exact bug this file exists to prevent:
    a str_replace edit once stranded the failover logic after an
    unconditional `continue`, causing this exact call to spin forever.
    A hard iteration/time budget here means a regression fails loudly
    (assertion or timeout) instead of hanging the test run."""
    providers = {"groq": FakeProvider("groq", fail_with=FakeServerError(), fail_times=999),
                "ollama": FakeProvider("ollama")}
    router, llm_client, errors, cb = load_router(providers, max_attempts=1)
    start = time.perf_counter()
    try:
        router.generate("s", "u", provider="groq")
    except llm_client.LLMError:
        pass
    elapsed = time.perf_counter() - start
    assert elapsed < 5.0, f"router.generate took {elapsed}s — possible infinite-loop regression"
    assert providers["groq"].calls <= 5, f"groq called {providers['groq'].calls} times — expected ~1"


def test_circuit_breaker_opens_after_threshold_and_skips_calls():
    providers = {"groq": FakeProvider("groq", fail_with=FakeServerError(), fail_times=999),
                "ollama": FakeProvider("ollama")}
    router, llm_client, errors, cb = load_router(
        providers, failover=False, max_attempts=1, circuit_threshold=3, circuit_cooldown=0.05)
    for _ in range(3):
        try:
            router.generate("s", "u", provider="groq")
        except llm_client.LLMError:
            pass
    assert cb.get_status()["groq"]["state"] == "OPEN"
    calls_before = providers["groq"].calls
    try:
        router.generate("s", "u", provider="groq")
    except llm_client.LLMError:
        pass
    assert providers["groq"].calls == calls_before, "circuit breaker should have skipped the real call"


def test_backoff_sleeps_between_retries_but_not_on_non_retryable():
    providers = {"groq": FakeProvider("groq", fail_with=FakeRateLimit(), fail_times=2),
                "ollama": FakeProvider("ollama")}
    router, llm_client, errors, cb = load_router(providers, max_attempts=3, base_delay=0.05, max_delay=1)
    start = time.perf_counter()
    result = router.generate("s", "u", provider="groq")
    elapsed = time.perf_counter() - start
    assert result == "answer-from-groq"
    assert elapsed >= 0.14, f"expected real backoff delay, only took {elapsed}s"

    providers2 = {"groq": FakeProvider("groq", fail_with=FakeAuthError(), fail_times=999),
                 "ollama": FakeProvider("ollama")}
    router2, llm_client2, errors2, cb2 = load_router(
        providers2, max_attempts=3, base_delay=2.0, max_delay=10)
    start2 = time.perf_counter()
    try:
        router2.generate("s", "u", provider="groq")
    except llm_client2.LLMError:
        pass
    elapsed2 = time.perf_counter() - start2
    assert elapsed2 < 0.5, f"non-retryable error should fail fast, took {elapsed2}s"


ALL_TESTS = [
    test_invalid_key_fails_immediately_no_failover,
    test_transient_rate_limit_recovers_without_failover,
    test_exhausted_retries_fail_over_to_ollama,
    test_failover_disabled_raises_instead_of_falling_back,
    test_streaming_failover_reports_actual_provider_used,
    test_no_infinite_loop_on_exhausted_retries,
    test_circuit_breaker_opens_after_threshold_and_skips_calls,
    test_backoff_sleeps_between_retries_but_not_on_non_retryable,
]


if __name__ == "__main__":
    # Manual runner — pytest isn't installed in every environment this
    # file might run in (it wasn't in the one this suite was authored
    # in). This gives the same pass/fail signal without that dependency;
    # `pytest tests/unit/test_provider_router.py` works identically once
    # pytest is available.
    failed = 0
    for test in ALL_TESTS:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {test.__name__}: {exc}")
    print(f"\n{len(ALL_TESTS) - failed}/{len(ALL_TESTS)} passed")
    sys.exit(1 if failed else 0)
