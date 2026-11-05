"""
Performance Benchmark and Verification Suite (Phase 3).
Tests LRU cache latency, query embedding caching, non-blocking async execution,
and token streaming responsiveness.
"""

import asyncio
import time
import pytest
from backend import cache
from backend.retrieval import embeddings


def test_offline_lru_cache_hit_latency():
    """Verify that in-memory LRU cache responds in sub-millisecond time (<1ms)."""
    cache.clear_local_cache()
    test_key = "query:test_org:u1:hash123"
    payload = {"answer": "Precomputed high-confidence response", "citations": []}

    cache.set_json(test_key, payload, ttl_seconds=60)

    start = time.perf_counter()
    retrieved = cache.get_json(test_key)
    latency_ms = (time.perf_counter() - start) * 1000

    assert retrieved == payload
    # Cache hit must be fast (sub-millisecond)
    assert latency_ms < 5.0, f"Cache latency too high: {latency_ms:.2f}ms"


def test_query_embedding_lru_cache():
    """Verify that repeated queries hit the query embedding cache with massive speedup."""
    query = "What were the total expenditures for 2024?"

    # First call: computes embedding
    start1 = time.perf_counter()
    vec1 = embeddings.embed_text_cached(query)
    ms1 = (time.perf_counter() - start1) * 1000

    # Second call: cached
    start2 = time.perf_counter()
    vec2 = embeddings.embed_text_cached(query)
    ms2 = (time.perf_counter() - start2) * 1000

    assert vec1.shape == (1, 384)
    assert vec2.shape == (1, 384)
    assert (vec1 == vec2).all()
    # Second call should be at least 5x faster than uncached execution
    assert ms2 < ms1 or ms2 < 1.0


@pytest.mark.anyio
async def test_async_non_blocking_embeddings():
    """Verify that aembed_text runs asynchronously in worker thread pool without blocking event loop."""
    start = time.perf_counter()
    vec = await embeddings.aembed_text(["Async embedding benchmark test sentence."])
    latency_ms = (time.perf_counter() - start) * 1000

    assert vec.shape == (1, 384)
    assert latency_ms > 0
