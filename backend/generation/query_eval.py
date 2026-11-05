"""
Query Evaluation and Terminal Scorecard Logger for RAG queries.

Computes and prints structured real-time metrics to terminal stdout whenever
a query is run (from frontend or API). Does not alter existing terminal
evaluation datasets or scripts.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


def print_query_metrics(
    query: str,
    provider: str,
    model: str,
    retrieval_ms: float,
    hit_count: int,
    generation_ms: float,
    ttft_ms: Optional[float] = None,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    tokens_per_sec: Optional[float] = None,
    faithfulness_score: Optional[float] = None,
    supported_claims: int = 0,
    total_claims: int = 0,
    used_llm: bool = True,
    session_id: Optional[str] = None,
) -> None:
    """Print a clean, visually distinct metric scorecard directly to stdout."""
    total_latency_ms = retrieval_ms + generation_ms
    divider = "-" * 64

    print("\n" + "=" * 64)
    print(f"[EVAL] RAG QUERY METRICS | Session: {session_id or 'N/A'}")
    print("=" * 64)
    print(f"  Query:            \"{query[:58]}{'...' if len(query) > 58 else ''}\"")
    print(f"  Active LLM:       {provider.upper()} ({model})")
    print(f"  LLM Used:         {'Yes' if used_llm else 'No (Extractive Fallback)'}")
    print(divider)
    print("  LATENCY BREAKDOWN:")
    print(f"    - Retrieval:     {retrieval_ms:8.1f} ms  (Hits: {hit_count})")
    print(f"    - Generation:    {generation_ms:8.1f} ms")
    if ttft_ms is not None:
        print(f"    - TTFT:          {ttft_ms:8.1f} ms")
    print(f"    - Total E2E:     {total_latency_ms:8.1f} ms")
    print(divider)
    print("  THROUGHPUT & TOKENS:")
    if prompt_tokens is not None or completion_tokens is not None:
        p_tok = prompt_tokens if prompt_tokens is not None else 0
        c_tok = completion_tokens if completion_tokens is not None else 0
        print(f"    - Prompt Tokens:     {p_tok:6d}")
        print(f"    - Completion Tokens: {c_tok:6d}")
        print(f"    - Total Tokens:      {p_tok + c_tok:6d}")
    if tokens_per_sec is not None:
        print(f"    - Output Speed:      {tokens_per_sec:6.1f} tokens/sec")
    elif completion_tokens and generation_ms > 0:
        calc_tps = completion_tokens / (generation_ms / 1000.0)
        print(f"    - Output Speed:      {calc_tps:6.1f} tokens/sec (est)")
    else:
        print("    - Token metrics:     N/A (Local extractive/offline)")
    print(divider)
    print("  QUALITY & FAITHFULNESS:")
    if faithfulness_score is not None:
        pct = faithfulness_score * 100
        status = "HIGH" if pct >= 70 else ("MEDIUM" if pct >= 40 else "LOW")
        print(f"    - Faithfulness:      {faithfulness_score:.2f} ({pct:.1f}% grounded) [{status}]")
        print(f"    - Claim Grounding:   {supported_claims}/{total_claims} claims supported by sources")
    else:
        print("    - Faithfulness:      N/A")
    print("=" * 64 + "\n", flush=True)



def evaluate_query_and_log(
    query: str,
    answer: str,
    retrieved_hits: List[Dict[str, Any]],
    provider: str,
    model: str,
    retrieval_ms: float,
    generation_ms: float,
    metrics: Optional[Dict[str, Any]] = None,
    used_llm: bool = True,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Computes semantic faithfulness via FaithfulnessJudge and prints the scorecard.
    Returns a unified dict suitable for persistence into session storage.
    """
    metrics = metrics or {}
    ttft_ms = metrics.get("ttft_ms")
    prompt_tokens = metrics.get("prompt_tokens")
    completion_tokens = metrics.get("completion_tokens")
    tps = metrics.get("tokens_per_second")

    # Evaluate semantic faithfulness using existing FaithfulnessJudge
    faithfulness_score = None
    supported_claims = 0
    total_claims = 0
    try:
        from evaluation.judges.faithfulness_judge import FaithfulnessJudge
        judge = FaithfulnessJudge()
        contexts = [h.get("snippet", "") for h in retrieved_hits if h.get("snippet")]
        judgement = judge.judge_faithfulness(answer, contexts)
        faithfulness_score = judgement.get("faithfulness_score")
        supported_claims = judgement.get("supported_claims", 0)
        total_claims = judgement.get("total_claims", 0)
    except Exception as exc:
        # Evaluation should never crash user query response
        faithfulness_score = None

    print_query_metrics(
        query=query,
        provider=provider,
        model=model,
        retrieval_ms=retrieval_ms,
        hit_count=len(retrieved_hits),
        generation_ms=generation_ms,
        ttft_ms=ttft_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        tokens_per_sec=tps,
        faithfulness_score=faithfulness_score,
        supported_claims=supported_claims,
        total_claims=total_claims,
        used_llm=used_llm,
        session_id=session_id,
    )

    return {
        "provider": provider,
        "model": model,
        "retrieval_ms": round(retrieval_ms, 1),
        "generation_ms": round(generation_ms, 1),
        "total_latency_ms": round(retrieval_ms + generation_ms, 1),
        "ttft_ms": ttft_ms,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "tokens_per_second": tps,
        "faithfulness_score": faithfulness_score,
        "supported_claims": supported_claims,
        "total_claims": total_claims,
        "used_llm": used_llm,
    }
